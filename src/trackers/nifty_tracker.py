"""
Live NIFTY current-month futures — 5th-level bid/ask price-book tracker.

Automatically resolves the near-month NIFTY futures contract on NFO.
Writes to nifty_price_book.*

Run:
    python -m src.trackers.nifty_tracker
"""

import time
import threading

from kiteconnect import KiteTicker

from src.shared.auth_docker import get_kite_session, API_KEY
from src.shared.price_book import PriceBookWriter
from src.shared.instruments import get_nearest_future
from src.shared.logger import get_logger
from src.shared import config

log = get_logger("NIFTY")


def run_tracker():
    kite, access_token = get_kite_session()

    tracker_config = config.FUTURES_TRACKERS["nifty"]
    exchange = tracker_config["exchange"]
    underlying = tracker_config["underlying"]
    excel_file = tracker_config["excel_file"].name
    title = tracker_config["title"]

    symbol, instrument_token = get_nearest_future(kite, exchange, underlying)
    log.info(f"Tracking {symbol} | Instrument token: {instrument_token}")

    writer = PriceBookWriter(excel_file, title=title)
    kws = KiteTicker(API_KEY, access_token)

    def on_ticks(ws, ticks):
        for tick in ticks:
            try:
                price = tick.get("last_price")
                depth = tick.get("depth", {})
                buy_levels = depth.get("buy", [])
                sell_levels = depth.get("sell", [])

                bid5 = buy_levels[4] if len(buy_levels) >= 5 else {}
                bid5_price = bid5.get("price")
                bid5_qty = bid5.get("quantity")

                ask5 = sell_levels[4] if len(sell_levels) >= 5 else {}
                ask5_price = ask5.get("price")
                ask5_qty = ask5.get("quantity")

                log.info(
                    f"{symbol} Price: {price} | "
                    f"5th Bid: {bid5_price} x {bid5_qty} | "
                    f"5th Ask: {ask5_price} x {ask5_qty}"
                )

                if bid5_price:
                    writer.update(bid5_price, bid_qty=bid5_qty)
                if ask5_price:
                    writer.update(ask5_price, ask_qty=ask5_qty)
            except Exception as e:
                log.error(f"Error processing tick: {e}", exc_info=True)

    def on_connect(ws, response):
        log.info(f"WebSocket connected. Subscribing to {instrument_token}.")
        ws.subscribe([instrument_token])
        ws.set_mode(ws.MODE_FULL, [instrument_token])

    def on_close(ws, code, reason):
        log.warning(f"WebSocket closed: {code} {reason}")
        log.info(f"Attempting to reconnect in {config.RECONNECT_DELAY_SECONDS}s...")
        time.sleep(config.RECONNECT_DELAY_SECONDS)
        kws.connect(threaded=False)

    def on_error(ws, code, reason):
        log.error(f"WebSocket error: {code} {reason}")

    kws.on_ticks = on_ticks
    kws.on_connect = on_connect
    kws.on_close = on_close
    kws.on_error = on_error

    def periodic_save():
        while True:
            time.sleep(config.SAVE_EVERY_SECONDS)
            writer.flush()
            log.info("Excel/JSON/HTML price book saved.")

    threading.Thread(target=periodic_save, daemon=True).start()

    log.info("Connecting to KiteTicker websocket...")
    kws.connect(threaded=False)


if __name__ == "__main__":
    try:
        run_tracker()
    except KeyboardInterrupt:
        log.info("Stopped by user.")
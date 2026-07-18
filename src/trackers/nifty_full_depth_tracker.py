"""
Live NIFTY full depth tracker — all 10 buy + 10 sell levels.

Run:
    python -m src.trackers.nifty_full_depth_tracker
"""

import time
import threading

from kiteconnect import KiteTicker

from src.shared.auth import get_kite_session, API_KEY
from src.shared.price_book import PriceBookWriter
from src.shared.instruments import get_nearest_future
from src.shared.logger import get_logger
from src.shared import config

log = get_logger("NIFTY_DEPTH")


def run_tracker():
    kite, access_token = get_kite_session()

    tracker_config = config.FUTURES_TRACKERS["nifty_full_depth"]
    exchange = tracker_config["exchange"]
    underlying = tracker_config["underlying"]
    excel_file = tracker_config["excel_file"].name
    title = tracker_config["title"]

    symbol, instrument_token = get_nearest_future(kite, exchange, underlying)
    log.info(f"Tracking {symbol} (full depth) | Instrument token: {instrument_token}")

    writer = PriceBookWriter(excel_file, title=title)
    kws = KiteTicker(API_KEY, access_token)

    def on_ticks(ws, ticks):
        for tick in ticks:
            try:
                depth = tick.get("depth", {})
                buy_levels = depth.get("buy", [])
                sell_levels = depth.get("sell", [])

                # Process all buy levels
                for level in buy_levels:
                    price = level.get("price")
                    qty = level.get("quantity")
                    if price:
                        writer.update(price, bid_qty=qty)

                # Process all sell levels
                for level in sell_levels:
                    price = level.get("price")
                    qty = level.get("quantity")
                    if price:
                        writer.update(price, ask_qty=qty)

                log.info(f"{symbol} | Bid levels: {len(buy_levels)} | Ask levels: {len(sell_levels)}")
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
"""
Live options — 5th-level bid/ask price-book tracker, generic across any
underlying (MCX CRUDEOIL, NFO NIFTY, BFO SENSEX, or anything else you add).

Edit the OPTIONS list in src/shared/config.py to add/remove strikes.

Run:
    python -m src.trackers.options_tracker
"""

import os
import json
import time
import threading
from datetime import datetime

from kiteconnect import KiteTicker

from src.shared.auth import get_kite_session, API_KEY
from src.shared.price_book import PriceBookWriter
from src.shared.instruments import get_nearest_weekly_option
from src.shared.logger import get_logger
from src.shared import config

log = get_logger("OPTIONS")

MANIFEST_FILE = config.OUTPUT_DIR / "options_manifest.json"


def write_options_manifest():
    """Writes options_manifest.json listing the active options in config.OPTIONS,
    so dashboard.html can dynamically build one CE tab + one PE tab per entry.
    """
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "options": [
            {
                "label": opt["label"],
                "file_prefix": opt["file_prefix"],
                "ce_file": f"{opt['file_prefix']}_ce_price_book.json",
                "pe_file": f"{opt['file_prefix']}_pe_price_book.json",
            }
            for opt in config.OPTIONS
        ],
    }

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    log.info(f"Wrote options manifest with {len(config.OPTIONS)} entries")


def build_routing_table(kite):
    """Resolves every CE/PE leg to its nearest-weekly-expiry instrument token
    and builds a PriceBookWriter for each leg.

    Returns {instrument_token: (option_type, symbol, writer)}
    """
    instruments_by_exchange = {}
    for opt in config.OPTIONS:
        exch = opt["exchange"]
        if exch not in instruments_by_exchange:
            instruments_by_exchange[exch] = kite.instruments(exch)

    routing = {}
    for opt in config.OPTIONS:
        instruments = instruments_by_exchange[opt["exchange"]]

        ce_symbol, ce_token, ce_expiry = get_nearest_weekly_option(
            kite, opt["exchange"], opt["underlying"], opt["strike"], "CE"
        )
        pe_symbol, pe_token, pe_expiry = get_nearest_weekly_option(
            kite, opt["exchange"], opt["underlying"], opt["strike"], "PE"
        )

        ce_writer = PriceBookWriter(
            f"{opt['file_prefix']}_ce_price_book.xlsx",
            title=f"{opt['label']} CE ({ce_expiry.strftime('%d-%b')})",
            price_step=None,  # no rounding — exact option premium prices
        )
        pe_writer = PriceBookWriter(
            f"{opt['file_prefix']}_pe_price_book.xlsx",
            title=f"{opt['label']} PE ({pe_expiry.strftime('%d-%b')})",
            price_step=None,  # no rounding — exact option premium prices
        )

        routing[ce_token] = ("CE", ce_symbol, ce_writer)
        routing[pe_token] = ("PE", pe_symbol, pe_writer)

        log.info(
            f"Resolved {opt['label']}: "
            f"CE={ce_symbol} (token {ce_token}, expiry {ce_expiry}), "
            f"PE={pe_symbol} (token {pe_token}, expiry {pe_expiry})"
        )

    return routing


def run_tracker():
    write_options_manifest()
    kite, access_token = get_kite_session()
    routing = build_routing_table(kite)
    all_tokens = list(routing.keys())

    log.info(f"Tracking {len(all_tokens)} option contracts")

    kws = KiteTicker(API_KEY, access_token)

    def on_ticks(ws, ticks):
        for tick in ticks:
            entry = routing.get(tick.get("instrument_token"))
            if not entry:
                continue

            option_type, symbol, writer = entry

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
                    f"[{option_type}] {symbol} Price: {price} | "
                    f"5th Bid: {bid5_price} x {bid5_qty} | "
                    f"5th Ask: {ask5_price} x {ask5_qty}"
                )

                if bid5_price:
                    writer.update(bid5_price, bid_qty=bid5_qty)
                if ask5_price:
                    writer.update(ask5_price, ask_qty=ask5_qty)
            except Exception as e:
                log.error(f"Error processing {option_type} tick: {e}", exc_info=True)

    def on_connect(ws, response):
        log.info(f"WebSocket connected. Subscribing to {len(all_tokens)} contracts.")
        ws.subscribe(all_tokens)
        ws.set_mode(ws.MODE_FULL, all_tokens)

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
            for _, _, writer in routing.values():
                writer.flush()
            log.info("All CE/PE Excel/JSON/HTML price books saved.")

    threading.Thread(target=periodic_save, daemon=True).start()

    log.info("Connecting to KiteTicker websocket...")
    kws.connect(threaded=False)


if __name__ == "__main__":
    try:
        run_tracker()
    except KeyboardInterrupt:
        log.info("Stopped by user.")
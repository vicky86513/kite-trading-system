"""
Shared instrument-resolution helper.

Finds the near-month futures contract for a given underlying on a given
exchange (nearest expiry >= today), so no tracker script needs to hardcode
a contract symbol that goes stale every month/expiry.
"""

from datetime import date
from .logger import get_logger

log = get_logger("INSTRUMENTS")


def get_nearest_future(kite, exchange, name):
    """
    Returns (tradingsymbol_with_exchange, instrument_token) for the
    nearest-expiry FUT contract matching `name` on `exchange`.

    Examples:
        get_nearest_future(kite, "MCX", "CRUDEOIL")  -> MCX crude oil future
        get_nearest_future(kite, "NFO", "NIFTY")      -> NIFTY future
        get_nearest_future(kite, "BFO", "SENSEX")     -> SENSEX future
    """
    try:
        instruments = kite.instruments(exchange)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch instruments from {exchange}: {e}")

    if not instruments:
        raise RuntimeError(f"No instruments found on {exchange}")

    futures = [
        i for i in instruments
        if i.get("name") == name
        and i.get("instrument_type") == "FUT"
        and i.get("expiry")
        and i["expiry"] >= date.today()
    ]

    if not futures:
        available_names = sorted(
            set(
                i.get("name")
                for i in instruments
                if i.get("instrument_type") == "FUT"
            )
        )
        raise RuntimeError(
            f"❌ No {name} futures contracts found on {exchange} with expiry >= today.\n"
            f"Available futures: {', '.join(available_names)}"
        )

    nearest = min(futures, key=lambda i: i["expiry"])
    symbol = f"{exchange}:{nearest['tradingsymbol']}"
    token = nearest["instrument_token"]

    log.info(f"Resolved {name}: {symbol} (token {token}, expiry {nearest['expiry']})")

    return symbol, token


def get_nearest_weekly_option(kite, exchange, underlying, strike, option_type):
    """
    Finds the option contract (CE or PE) for `underlying`/`strike` on
    `exchange` with the nearest expiry >= today.

    Since weekly expiries happen every week (the monthly is just the last
    weekly of the month), "nearest" is always the next weekly expiry, not
    the monthly one.
    """
    try:
        instruments = kite.instruments(exchange)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch instruments from {exchange}: {e}")

    candidates = [
        i for i in instruments
        if i.get("name") == underlying
        and i.get("instrument_type") == option_type
        and float(i.get("strike", 0)) == float(strike)
        and i.get("expiry")
        and i["expiry"] >= date.today()
    ]

    if not candidates:
        raise RuntimeError(
            f"❌ No {option_type} contract found for {underlying} "
            f"strike {strike} on {exchange}.\n"
            f"Check that the strike matches an actual listed strike."
        )

    nearest = min(candidates, key=lambda i: i["expiry"])
    symbol = f"{exchange}:{nearest['tradingsymbol']}"
    token = nearest["instrument_token"]
    expiry = nearest["expiry"]

    log.info(
        f"Resolved {underlying} {strike} {option_type}: "
        f"{symbol} (token {token}, expiry {expiry})"
    )

    return symbol, token, expiry
"""
Global configuration for trading system.
All paths, constants, and settings in one place.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# DIRECTORIES
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "Excel"
LOG_DIR = DATA_DIR / "Logs"
CACHE_DIR = DATA_DIR / "cache"

# Create directories if missing
for directory in [DATA_DIR, OUTPUT_DIR, LOG_DIR, CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# CACHE FILES
# ============================================================================

KITE_SESSION_FILE = CACHE_DIR / "kite_session.json"

# ============================================================================
# API SETTINGS
# ============================================================================

REFRESH_MS = 4000
FRESH_WINDOW_SECONDS = 10
SAVE_EVERY_SECONDS = 5
OPTIONS_MANIFEST_REFRESH_MS = 30000

# ============================================================================
# FUTURES TRACKERS CONFIGURATION
# ============================================================================

FUTURES_TRACKERS = {
    "mcx_crude_oil": {
        "exchange": "MCX",
        "underlying": "CRUDEOIL",
        "excel_file": OUTPUT_DIR / "crude_oil_price_book.xlsx",
        "title": "MCX Crude Oil Futures",
        "price_step": 10,
    },
    "nifty": {
        "exchange": "NFO",
        "underlying": "NIFTY",
        "excel_file": OUTPUT_DIR / "nifty_price_book.xlsx",
        "title": "NIFTY Current-Month Futures",
        "price_step": 10,
    },
    "nifty_full_depth": {
        "exchange": "NFO",
        "underlying": "NIFTY",
        "excel_file": OUTPUT_DIR / "nifty_full_depth.xlsx",
        "title": "NIFTY Full Depth",
        "price_step": 10,
    },
    "sensex": {
        "exchange": "BFO",
        "underlying": "SENSEX",
        "excel_file": OUTPUT_DIR / "sensex_price_book.xlsx",
        "title": "SENSEX Current-Month Futures",
        "price_step": 10,
    },
}

# ============================================================================
# OPTIONS CONFIGURATION
# ============================================================================
# >>> EDIT THIS LIST to add/remove option strikes <<<

OPTIONS = [
    {
        "label": "NIFTY 24200",
        "file_prefix": "nifty_24200",
        "exchange": "NFO",
        "underlying": "NIFTY",
        "strike": 24200,
    },
    {
        "label": "NIFTY 23800",
        "file_prefix": "nifty_23800",
        "exchange": "NFO",
        "underlying": "NIFTY",
        "strike": 23800,
    },
    # {
    #     "label": "CRUDEOIL 7650",
    #     "file_prefix": "crudeoil_7650",
    #     "exchange": "MCX",
    #     "underlying": "CRUDEOIL",
    #     "strike": 7650,
    # },
    # Add more strikes here as needed
]

# ============================================================================
# NIFTY FUTURES FLOW TRACKER
# ============================================================================

NIFTY_FUTURES_FLOW = {
    "exchange": "NFO",
    "underlying": "NIFTY",
    "excel_file": OUTPUT_DIR / "nifty_futures_flow.xlsx",
    "json_file": OUTPUT_DIR / "nifty_futures_flow.json",
    "title": "NIFTY Futures Current Expiry Market Flow",
}

# Flow analysis settings
FLOW_ANALYSIS = {
    "large_trade_percentile": 90.0,  # Classify as "large" if >90th percentile
    "metrics_save_interval": 5,  # Save metrics every N seconds
    "historical_depth": 100,  # Keep last N metrics for trend analysis
}

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-6s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# ============================================================================
# RECONNECTION SETTINGS
# ============================================================================

RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY_SECONDS = 5

# ============================================================================
# FEATURE FLAGS
# ============================================================================

DEBUG = os.getenv("DEBUG", "false").lower() == "true"
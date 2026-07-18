# Setup Guide

## Prerequisites

- Python 3.8+
- pip package manager
- Zerodha Kite API credentials

## Installation

### 1. Clone/Download Project

```bash
cd kite-trading-system
2. Create Virtual Environment
python -m venv .venv

# Activate
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows
3. Install Dependencies
pip install -r requirements.txt
4. Get API Credentials
Go to Zerodha Kite
Login with your account
Go to Settings → API Tokens
Create a new token
Note your API Key and API Secret
5. Create .env File
Create .env in project root:

KITE_API_KEY=your_api_key
KITE_API_SECRET=your_api_secret
DEBUG=false
⚠️ Never commit .env to git!

Running Trackers
Single Tracker
python -m src.trackers.nifty_tracker
Multiple Trackers
Open separate terminals:

# Terminal 1
python -m src.trackers.nifty_tracker

# Terminal 2
python -m src.trackers.mcx_crude_oil_tracker

# Terminal 3
python -m src.trackers.options_tracker

All Trackers Together
python -m src.orchestration.run_all
Viewing Dashboard
1. Start Local Server
cd web
python -m http.server 8000
2. Open Dashboard
Visit: http://localhost:8000/dashboard.html

Output Files
All data is saved in data/:

data/
├── Excel/              # Price books
│   ├── nifty_price_book_2026-07-17.xlsx
│   ├── nifty_price_book_2026-07-17.json
│   └── nifty_price_book_2026-07-17.html
├── Logs/               # Trading logs
│   └── trading_logs_2026-07-17.txt
└── cache/              # Session cache
    └── kite_session.json
Configuring Options
Edit src/shared/config.py:

OPTIONS = [
    {
        "label": "NIFTY 24200",
        "file_prefix": "nifty_24200",
        "exchange": "NFO",
        "underlying": "NIFTY",
        "strike": 24200,
    },
    # Add more strikes here
]
Then restart options_tracker.py.

Troubleshooting
"No API key"
Check .env file exists and has correct values
Restart tracker
"Authentication failed"
Get new request token from Kite login page
Update .env if API key/secret changed
No data in dashboard
Ensure tracker is running (should see logs)
Check market hours (9:15-15:30 IST)
Verify data/Excel/ has .json files
Dashboard stuck
Refresh page (F5)
Check browser console for errors
Ensure python -m http.server 8000 is running in web/ folder
Next Steps
Read docs/ARCHITECTURE.md for design details
Check README.md for feature overview
Look at data/Logs/trading_logs_.txt for detailed logs
---

### **25. `docs/ARCHITECTURE.md`**
```markdown
# Architecture

## Project Structure

src/shared/ → Shared modules (reusable across all trackers) src/trackers/ → Individual tracker scripts src/orchestration/ → Runner scripts for multiple trackers web/ → Dashboard (HTML/JS) data/ → Outputs (Excel, Logs, Cache) tests/ → Unit tests docs/ → Documentation

## Data Flow

KiteTicker (WebSocket) ↓ Tick Data ↓ PriceBookWriter ├→ Excel (.xlsx) ├→ JSON (.json) └→ HTML (.html) ↓ Dashboard (web/dashboard.html) Polls JSON files every 4 seconds Displays live data

## Key Modules

### `auth.py` - Authentication
- Handles Kite Connect login
- Caches access token daily
- Reuses token if still valid

### `config.py` - Central Configuration
- All paths, settings, options in one place
- Easy to modify tracker behavior

### `logger.py` - Unified Logging
- All trackers log to same file per day
- Daily rotation at midnight
- Console + file output

### `instruments.py` - Smart Instrument Resolution
- Automatically finds nearest-month contracts
- Resolves weekly options correctly
- No hardcoded symbols needed

### `price_book.py` - Data Aggregation
- Accumulates bid/ask quantity by price
- Writes Excel/JSON/HTML
- Thread-safe operations

## Tracker Types

### Futures Trackers
- `nifty_tracker.py` - NIFTY futures
- `mcx_crude_oil_tracker.py` - Crude Oil futures
- `sensex_tracker.py` - SENSEX futures
- `nifty_full_depth_tracker.py` - Full 10-level depth

All futures track 5th level (5 buy + 5 sell levels).

### Options Tracker
- `options_tracker.py` - CE/PE options

Configurable in `config.py` → `OPTIONS` list.
Supports multiple underlyings & strikes.
Each CE/PE gets its own separate file.

## WebSocket Handling

```python
KiteTicker
├→ on_connect()    → Subscribe to instruments
├→ on_ticks()      → Process incoming data
├→ on_error()      → Log errors
└→ on_close()      → Auto-reconnect
All trackers use this pattern. Reconnection is automatic.

Dashboard Architecture
dashboard.html
├→ Polls data/Excel/*.json every 4 seconds
├→ Renders tables dynamically
├→ Supports multi-tab switching (one per instrument)
└→ Shows live imbalance & depth visualization
No backend API needed — reads from static JSON files only.

Thread Safety
PriceBookWriter uses threading.Lock() for self.book access
Snapshot pattern in flush() prevents race conditions
Safe for concurrent updates from WebSocket + periodic save
Daily Rollover
At midnight: all files automatically roll over to new date
Fresh Excel file created: crude_oil_price_book_2026-07-18.xlsx
Existing data not lost (backed up with old date in filename)
No restart needed — automatic
Error Handling
Try-catch around all tick processing
Validation on API responses
Graceful degradation (skip bad ticks, continue)
Detailed logging of all errors
Auto-reconnect on connection loss
Performance
Memory: ~50MB per tracker (in-memory price book)
CPU: <1% per tracker (idle, spikes on tick bursts)
Disk: ~1-5MB per day (Excel/JSON/HTML files)
Network: 1 WebSocket per tracker (minimal overhead)
Extension Points
Add New Futures
Edit config.py → FUTURES_TRACKERS:

FUTURES_TRACKERS = {
    "your_new_tracker": {
        "exchange": "NFO",
        "underlying": "SYMBOL",
        "excel_file": OUTPUT_DIR / "file.xlsx",
        "title": "Display Name",
    },
}
Create src/trackers/your_new_tracker.py (copy nifty_tracker.py).

Add New Options
Edit config.py → OPTIONS:

OPTIONS = [
    {
        "label": "YOUR LABEL",
        "file_prefix": "prefix",
        "exchange": "NFO",
        "underlying": "SYMBOL",
        "strike": 25000,
    },
]
No code changes needed — options_tracker.py handles it automatically.
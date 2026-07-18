# Kite Trading System 📊

Live options & futures tracker with real-time WebSocket streaming, Excel export, and interactive dashboard.

## Features

- 📡 **Real-time Streaming** - WebSocket-based tick data
- 📊 **Live Price Books** - 5-level market depth tracking
- 📈 **Multi-Instrument** - Futures (MCX, NFO, BFO) & Options (CE/PE)
- 📁 **Excel Export** - Daily price books with cumulative data
- 🌐 **Interactive Dashboard** - Real-time visualization
- 📝 **Unified Logging** - All trackers log to one file per day
- 🔄 **Auto-Reconnect** - Graceful reconnection on disconnect

## Quick Start

### Installation

```bash
# Create virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
Setup
Get API Credentials

Visit Zerodha Kite
Create API credentials
Get your API key and secret
Create .env file:

KITE_API_KEY=your_key
KITE_API_SECRET=your_secret
DEBUG=false
Run a tracker:

python -m src.trackers.nifty_tracker
Usage
Run Single Tracker
# NIFTY futures
python -m src.trackers.nifty_tracker

# MCX Crude Oil
python -m src.trackers.mcx_crude_oil_tracker

# Options (CE/PE)
python -m src.trackers.options_tracker

# SENSEX futures
python -m src.trackers.sensex_tracker
Run All Trackers Together
python -m src.orchestration.run_all
View Dashboard
# Terminal 1: Start tracker(s)
python -m src.trackers.nifty_tracker

# Terminal 2: Start web server
cd web
python -m http.server 8000
Then open http://localhost:8000/dashboard.html in browser.

Output
All data stored in data/:

data/
├── Excel/                          # Price books & manifest
│   ├── nifty_price_book_2026-07-17.xlsx
│   ├── crude_oil_price_book_2026-07-17.json
│   └── options_manifest.json
├── Logs/                           # Trading logs
│   └── trading_logs_2026-07-17.txt
└── cache/                          # Session cache
    └── kite_session.json
Project Structure
src/
├── shared/              # Shared modules
│   ├── auth.py
│   ├── config.py
│   ├── instruments.py
│   ├── logger.py
│   └── price_book.py
├── trackers/            # Live tracker scripts
│   ├── mcx_crude_oil_tracker.py
│   ├── nifty_tracker.py
│   ├── options_tracker.py
│   └── sensex_tracker.py
└── orchestration/       # Runner scripts
    └── run_all.py

web/
└── dashboard.html       # Interactive dashboard

data/
├── Excel/               # Price books
├── Logs/                # Logs
└── cache/               # Session cache
Configuration
Edit src/shared/config.py to:

Change refresh rate
Add/modify tracker settings
Configure options strikes
Troubleshooting
No data appearing?

Check .env file has correct API keys
Verify market is open (9:15-15:30 IST)
Check data/Logs/trading_logs_<date>.txt
Dashboard not updating?

Ensure tracker is running
Check browser console for errors
Verify data files exist in data/Excel/
Authentication failed?

Get new request token from Kite login page
Check API credentials in .env
See auth logs in data/Logs/
License
Private use - Not for redistribution

---

### **5. `src/__init__.py`**
```python
"""Trading system package."""
__version__ = "1.0.0"
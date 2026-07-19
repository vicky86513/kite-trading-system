#!/bin/bash

set -e

echo "================================================"
echo "🚀 NIFTY FUTURES TRADING SYSTEM"
echo "================================================"

# Create necessary directories
mkdir -p data/Excel data/Logs data/cache

# Start the trading system in background
echo "Starting trading system orchestration..."
python -m src.orchestration.run_all &
TRADING_PID=$!

# Start web server (Python's built-in HTTP server)
echo "Starting web server on port 8000..."
cd web
python -m http.server 8000 --directory . &
WEB_PID=$!

echo "================================================"
echo "✓ All services started"
echo "📊 Dashboard: http://localhost:8000/dashboard.html"
echo "================================================"

# Keep container running
wait $TRADING_PID $WEB_PID
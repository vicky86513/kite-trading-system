"""
Live NIFTY Futures Current Expiry Market Flow Tracker

Tracks the current (nearest) active NIFTY Futures contract and performs
comprehensive market flow analysis including:

- Top 5 order book tracking
- Aggressive trade volume analysis
- CVD (Cumulative Volume Delta)
- Large trade detection
- Cancellation estimation
- Absorption detection
- OI (Open Interest) analysis
- Market Flow Score generation

The system automatically handles expiry rollover to the next active contract.

Run:
    python -m src.trackers.nifty_futures_flow_tracker
"""

import time
import threading
import json
from datetime import datetime, date
from pathlib import Path
from collections import deque
from typing import Dict, List, Optional

from kiteconnect import KiteTicker

from src.shared.auth_docker import get_kite_session, API_KEY
from src.shared.instruments import get_nearest_future
from src.shared.logger import get_logger
from src.shared import config
from src.shared.market_flow_signals import (
    select_current_nifty_future,
    OrderBook,
    OrderLevel,
    Trade,
    FlowMetrics,
    calculate_nifty_future_flow_metrics,
    generate_nifty_future_flow_signal,
)

log = get_logger("NIFTY_FLOW")


class NiftyFuturesFlowTracker:
    """Main tracker class for NIFTY Futures flow analysis."""

    def __init__(self):
        self.kite = None
        self.access_token = None
        self.current_symbol = None
        self.current_token = None
        self.current_expiry = None
        
        # Market data
        self.current_ltp = 0.0
        self.current_volume = 0
        self.current_oi = 0
        self.bid_levels: List[OrderLevel] = []
        self.ask_levels: List[OrderLevel] = []
        self.trades: List[Trade] = []
        
        # Historical tracking
        self.metrics_history: deque = deque(maxlen=config.FLOW_ANALYSIS["historical_depth"])
        self.current_metrics: Optional[FlowMetrics] = None
        self.previous_metrics: Optional[FlowMetrics] = None
        self.previous_book: Optional[OrderBook] = None
        
        # WebSocket
        self.kws = None
        self.subscription_mode = "FULL"  # FULL = 10 buy + 10 sell levels
        
        # File management
        self.json_file = config.NIFTY_FUTURES_FLOW["json_file"]
        self.metrics_lock = threading.Lock()

    def initialize(self):
        """Initialize tracker."""
        log.info("🚀 Initializing NIFTY Futures Flow Tracker...")
        
        # Authenticate
        self.kite, self.access_token = get_kite_session()
        
        # Select current expiry
        self.select_expiry()
        
        # Setup WebSocket
        self.setup_websocket()

    def select_expiry(self):
        """Select current (nearest) active NIFTY Futures expiry."""
        log.info("🔍 Selecting current NIFTY Futures expiry...")
        
        try:
            symbol, token, expiry = select_current_nifty_future(self.kite)
            self.current_symbol = symbol
            self.current_token = token
            self.current_expiry = expiry
            
            log.info(
                f"✓ Current expiry selected:\n"
                f"   Symbol: {symbol}\n"
                f"   Token: {token}\n"
                f"   Expiry: {expiry}"
            )
        except Exception as e:
            log.error(f"✗ Failed to select expiry: {e}")
            raise

    def setup_websocket(self):
        """Setup KiteTicker WebSocket."""
        log.info("🔗 Setting up WebSocket connection...")
        
        self.kws = KiteTicker(API_KEY, self.access_token)
        
        self.kws.on_ticks = self.on_ticks
        self.kws.on_connect = self.on_connect
        self.kws.on_close = self.on_close
        self.kws.on_error = self.on_error

    def on_connect(self, ws, response):
        """WebSocket connected."""
        log.info(f"✓ WebSocket connected. Subscribing to {self.current_token}...")
        ws.subscribe([self.current_token])
        ws.set_mode(ws.MODE_FULL, [self.current_token])
        log.info(f"✓ Subscribed to {self.current_symbol} in FULL mode")

    def on_ticks(self, ws, ticks):
        """Process incoming ticks."""
        for tick in ticks:
            try:
                if tick.get("instrument_token") != self.current_token:
                    continue
                
                self.process_tick(tick)
            except Exception as e:
                log.error(f"✗ Error processing tick: {e}", exc_info=True)

    def process_tick(self, tick: Dict):
        """Process single tick update."""
        # Extract price data
        self.current_ltp = tick.get("last_price", 0.0)
        self.current_volume = tick.get("volume", 0)
        self.current_oi = tick.get("oi", 0)
        
        # Extract order book
        depth = tick.get("depth", {})
        
        # Process bid levels (5-10)
        buy_levels = depth.get("buy", [])
        self.bid_levels = [
            OrderLevel(
                price=level.get("price"),
                quantity=level.get("quantity"),
                timestamp=datetime.now()
            )
            for level in buy_levels[:10]
        ]
        
        # Process ask levels (5-10)
        sell_levels = depth.get("sell", [])
        self.ask_levels = [
            OrderLevel(
                price=level.get("price"),
                quantity=level.get("quantity"),
                timestamp=datetime.now()
            )
            for level in sell_levels[:10]
        ]
        
        log.debug(
            f"📊 Tick update: LTP={self.current_ltp}, "
            f"Bid Levels={len(self.bid_levels)}, Ask Levels={len(self.ask_levels)}"
        )

    def on_close(self, ws, code, reason):
        """WebSocket closed."""
        log.warning(f"⚠ WebSocket closed: {code} {reason}")
        log.info(f"Attempting to reconnect in {config.RECONNECT_DELAY_SECONDS}s...")
        time.sleep(config.RECONNECT_DELAY_SECONDS)
        self.kws.connect(threaded=False)

    def on_error(self, ws, code, reason):
        """WebSocket error."""
        log.error(f"✗ WebSocket error: {code} {reason}")

    def calculate_metrics_periodically(self):
        """Periodically calculate flow metrics."""
        while True:
            try:
                time.sleep(config.FLOW_ANALYSIS["metrics_save_interval"])
                
                if not self.bid_levels or not self.ask_levels:
                    continue
                
                # Create current order book
                current_book = OrderBook(
                    instrument=self.current_symbol,
                    underlying="NIFTY",
                    expiry=self.current_expiry,
                    ltp=self.current_ltp,
                    bid_levels=self.bid_levels,
                    ask_levels=self.ask_levels,
                    volume=self.current_volume,
                    open_interest=self.current_oi,
                    timestamp=datetime.now(),
                )
                
                # Calculate metrics
                with self.metrics_lock:
                    self.previous_metrics = self.current_metrics
                    self.current_metrics = calculate_nifty_future_flow_metrics(
                        current_book=current_book,
                        trades=self.trades,
                        previous_metrics=self.previous_metrics,
                        previous_book=self.previous_book,
                    )
                    self.previous_book = current_book
                    self.metrics_history.append(self.current_metrics)
                
                # Generate signal
                signal = generate_nifty_future_flow_signal(self.current_metrics)
                
                # Save data
                self.save_metrics(signal)
                
                # Log summary
                log.info(
                    f"📊 NIFTY FLOW UPDATE\n"
                    f"   Signal: {signal.signal} (Score: {signal.score})\n"
                    f"   LTP: {self.current_ltp} ({self.current_metrics.price_change_pct:+.2f}%)\n"
                    f"   Agg Buy: {self.current_metrics.aggressive_buy_volume:,} | "
                    f"Agg Sell: {self.current_metrics.aggressive_sell_volume:,}\n"
                    f"   CVD: {self.current_metrics.cvd:+,} | "
                    f"OI: {self.current_metrics.oi_change:+,}\n"
                    f"   Absorption: {self.current_metrics.absorption_level}"
                )
                
                # Check for expiry rollover
                self.check_expiry_rollover()
                
            except Exception as e:
                log.error(f"✗ Error in metrics calculation: {e}", exc_info=True)

    def check_expiry_rollover(self):
        """Check if current contract has expired, rollover if needed."""
        if datetime.now().date() > self.current_expiry:
            log.warning(f"⚠ Current expiry {self.current_expiry} has passed!")
            log.info("🔄 Performing expiry rollover...")
            
            try:
                # Unsubscribe from old contract
                if self.kws and self.current_token:
                    self.kws.unsubscribe([self.current_token])
                
                # Select new expiry
                old_expiry = self.current_expiry
                old_symbol = self.current_symbol
                self.select_expiry()
                
                # Reset metrics for new contract
                self.trades.clear()
                self.previous_metrics = None
                self.metrics_history.clear()
                
                # Subscribe to new contract
                self.kws.subscribe([self.current_token])
                self.kws.set_mode(self.kws.MODE_FULL, [self.current_token])
                
                log.info(
                    f"✓ Expiry rollover completed:\n"
                    f"   Old: {old_symbol} ({old_expiry})\n"
                    f"   New: {self.current_symbol} ({self.current_expiry})"
                )
            except Exception as e:
                log.error(f"✗ Expiry rollover failed: {e}", exc_info=True)

    def save_metrics(self, signal):
        """Save metrics to JSON file."""
        try:
            data = {
                "timestamp": datetime.now().isoformat(),
                "instrument": self.current_symbol,
                "underlying": "NIFTY",
                "expiry": self.current_expiry.isoformat(),
                "signal": {
                    "type": signal.signal,
                    "score": signal.score,
                    "confidence": signal.confidence,
                    "reasons": signal.reasons,
                },
                "metrics": {
                    "ltp": self.current_metrics.ltp,
                    "price_change": self.current_metrics.price_change,
                    "price_change_pct": self.current_metrics.price_change_pct,
                    "volume": self.current_metrics.volume,
                    "volume_change_pct": self.current_metrics.volume_change_pct,
                    "open_interest": self.current_metrics.open_interest,
                    "oi_change": self.current_metrics.oi_change,
                    "oi_change_pct": self.current_metrics.oi_change_pct,
                    "order_book": {
                        "bid_levels_5": [
                            {"price": l.price, "quantity": l.quantity}
                            for l in self.bid_levels[:5]
                        ],
                        "ask_levels_5": [
                            {"price": l.price, "quantity": l.quantity}
                            for l in self.ask_levels[:5]
                        ],
                        "total_bid_qty": self.current_metrics.total_bid_qty,
                        "total_ask_qty": self.current_metrics.total_ask_qty,
                        "bid_ask_imbalance": self.current_metrics.bid_ask_imbalance,
                        "weighted_imbalance": self.current_metrics.weighted_imbalance,
                    },
                    "trade_flow": {
                        "aggressive_buy_volume": self.current_metrics.aggressive_buy_volume,
                        "aggressive_sell_volume": self.current_metrics.aggressive_sell_volume,
                        "delta": self.current_metrics.delta,
                        "cvd": self.current_metrics.cvd,
                        "avg_trade_qty": self.current_metrics.avg_trade_qty,
                        "largest_trade_qty": self.current_metrics.largest_trade_qty,
                        "large_trade_ratio": self.current_metrics.large_trade_ratio,
                    },
                    "liquidity": {
                        "cancellation_ratio": self.current_metrics.cancellation_ratio,
                        "absorption_level": self.current_metrics.absorption_level,
                    },
                },
            }
            
            with open(self.json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        
        except Exception as e:
            log.error(f"✗ Failed to save metrics: {e}")

    def run(self):
        """Main run method."""
        log.info("=" * 70)
        log.info("🚀 NIFTY FUTURES CURRENT EXPIRY FLOW TRACKER")
        log.info("=" * 70)
        
        try:
            # Initialize
            self.initialize()
            
            # Start metrics calculation thread
            metrics_thread = threading.Thread(
                target=self.calculate_metrics_periodically,
                daemon=True,
                name="MetricsCalculator"
            )
            metrics_thread.start()
            log.info("✓ Metrics calculation thread started")
            
            # Connect WebSocket (blocking)
            log.info("Connecting to KiteTicker...")
            self.kws.connect(threaded=False)
        
        except KeyboardInterrupt:
            log.info("🛑 Stopped by user")
        except Exception as e:
            log.error(f"✗ Fatal error: {e}", exc_info=True)
            raise


def main():
    """Entry point."""
    tracker = NiftyFuturesFlowTracker()
    tracker.run()


if __name__ == "__main__":
    main()
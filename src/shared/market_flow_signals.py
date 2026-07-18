"""
Market Flow Signals Analysis Engine

Calculates order-flow metrics specifically for the current expiry
NIFTY Futures contract. Includes:
- Top 5 order book analysis
- Aggressive trade detection
- CVD (Cumulative Volume Delta)
- Large trade detection
- Cancellation estimation
- OI analysis
- Market Flow Score generation
"""

from datetime import datetime, date
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict
import math

from .logger import get_logger

log = get_logger("MARKET_FLOW")


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class OrderLevel:
    """Single price level in order book."""
    price: float
    quantity: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OrderBook:
    """Complete order book snapshot."""
    instrument: str
    underlying: str
    expiry: date
    ltp: float
    bid_levels: List[OrderLevel]
    ask_levels: List[OrderLevel]
    timestamp: datetime = field(default_factory=datetime.now)
    volume: int = 0
    open_interest: int = 0


@dataclass
class Trade:
    """Individual trade record."""
    price: float
    quantity: int
    side: str  # "BUY" or "SELL"
    timestamp: datetime = field(default_factory=datetime.now)
    is_large: bool = False
    is_aggressive: bool = False


@dataclass
class FlowMetrics:
    """Calculated flow metrics."""
    timestamp: datetime = field(default_factory=datetime.now)
    instrument: str = ""
    underlying: str = ""
    expiry: date = field(default_factory=date.today)
    
    # Order Book
    total_bid_qty: int = 0
    total_ask_qty: int = 0
    weighted_bid_depth: float = 0.0
    weighted_ask_depth: float = 0.0
    bid_ask_imbalance: float = 0.0  # (bid-ask)/(bid+ask)
    weighted_imbalance: float = 0.0
    
    # Trade Flow
    aggressive_buy_volume: int = 0
    aggressive_sell_volume: int = 0
    delta: int = 0
    cvd: int = 0  # Cumulative Volume Delta
    avg_trade_qty: float = 0.0
    largest_trade_qty: int = 0
    large_trade_ratio: float = 0.0  # large_trades / total_trades
    
    # Liquidity
    bid_liquidity_consumed: int = 0
    ask_liquidity_consumed: int = 0
    
    # Price & Volume
    ltp: float = 0.0
    price_change: float = 0.0
    price_change_pct: float = 0.0
    volume: int = 0
    volume_change_pct: float = 0.0
    
    # Open Interest
    open_interest: int = 0
    oi_change: int = 0
    oi_change_pct: float = 0.0
    
    # Flow Direction
    flow_direction: str = ""  # "BULLISH", "BEARISH", "NEUTRAL"
    cancellation_ratio: float = 0.0
    absorption_level: str = ""  # "STRONG", "NORMAL", "WEAK"


@dataclass
class FlowSignal:
    """Final market flow signal."""
    timestamp: datetime = field(default_factory=datetime.now)
    instrument: str = ""
    underlying: str = ""
    expiry: date = field(default_factory=date.today)
    
    signal: str = ""  # "STRONG BUY", "BUY", "NEUTRAL", "SELL", "STRONG SELL"
    score: int = 0  # -100 to +100
    confidence: str = ""  # "VERY HIGH", "HIGH", "MEDIUM", "LOW"
    
    reasons: List[str] = field(default_factory=list)
    metrics: FlowMetrics = field(default_factory=FlowMetrics)


# ============================================================================
# EXPIRY SELECTION
# ============================================================================


def select_current_nifty_future(kite, current_time: datetime = None) -> Tuple[str, int, date]:
    """
    Select the nearest valid active NIFTY Futures expiry.
    
    Returns:
        (symbol_with_exchange, instrument_token, expiry_date)
    
    Example:
        symbol, token, expiry = select_current_nifty_future(kite)
        # Returns: ("NFO:NIFTY30JUL26FUT", 123456, date(2026, 7, 30))
    """
    if current_time is None:
        current_time = datetime.now()
    
    current_date = current_time.date()
    
    try:
        instruments = kite.instruments("NFO")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch NFO instruments: {e}")
    
    # Filter NIFTY futures with expiry >= today
    nifty_futures = [
        i for i in instruments
        if i.get("name") == "NIFTY"
        and i.get("instrument_type") == "FUT"
        and i.get("expiry")
        and i["expiry"] >= current_date
    ]
    
    if not nifty_futures:
        raise RuntimeError(
            f"❌ No valid NIFTY Futures contracts found with expiry >= {current_date}"
        )
    
    # Select nearest expiry
    nearest = min(nifty_futures, key=lambda i: i["expiry"])
    
    symbol = f"NFO:{nearest['tradingsymbol']}"
    token = nearest["instrument_token"]
    expiry = nearest["expiry"]
    
    log.info(
        f"✓ Selected current NIFTY Futures: {symbol} "
        f"(token {token}, expiry {expiry})"
    )
    
    return symbol, token, expiry


# ============================================================================
# ORDER BOOK ANALYSIS
# ============================================================================


def calculate_order_book_metrics(book: OrderBook) -> Dict:
    """Calculate metrics from order book."""
    metrics = {}
    
    # Total quantities
    bid_qty = sum(level.quantity for level in book.bid_levels)
    ask_qty = sum(level.quantity for level in book.ask_levels)
    
    metrics["total_bid_qty"] = bid_qty
    metrics["total_ask_qty"] = ask_qty
    
    # Raw imbalance
    total = bid_qty + ask_qty
    if total > 0:
        metrics["bid_ask_imbalance"] = (bid_qty - ask_qty) / total
    else:
        metrics["bid_ask_imbalance"] = 0.0
    
    # Weighted imbalance (closer levels weighted more)
    weighted_bid = 0.0
    weighted_ask = 0.0
    
    for i, level in enumerate(book.bid_levels[:5], 1):
        weight = (6 - i) / 15  # 5/15, 4/15, 3/15, 2/15, 1/15
        weighted_bid += level.quantity * weight
    
    for i, level in enumerate(book.ask_levels[:5], 1):
        weight = (6 - i) / 15
        weighted_ask += level.quantity * weight
    
    metrics["weighted_bid_depth"] = weighted_bid
    metrics["weighted_ask_depth"] = weighted_ask
    
    weighted_total = weighted_bid + weighted_ask
    if weighted_total > 0:
        metrics["weighted_imbalance"] = (weighted_bid - weighted_ask) / weighted_total
    else:
        metrics["weighted_imbalance"] = 0.0
    
    return metrics


# ============================================================================
# TRADE FLOW ANALYSIS
# ============================================================================


def classify_aggressive_trades(
    trades: List[Trade],
    previous_book: Optional[OrderBook],
    current_book: OrderBook,
    ltp_change: float
) -> Tuple[int, int, float]:
    """
    Classify trades as aggressive buy/sell.
    
    A trade is aggressive if:
    - BUY: Executes at/above ask (lifting offer)
    - SELL: Executes at/below bid (hitting bid)
    
    Returns:
        (aggressive_buy_volume, aggressive_sell_volume, avg_trade_qty)
    """
    aggressive_buy = 0
    aggressive_sell = 0
    total_qty = 0
    total_trades = 0
    
    if not trades:
        return 0, 0, 0.0
    
    for trade in trades:
        total_qty += trade.quantity
        total_trades += 1
        
        # Simple heuristic: if price moved up, likely aggressive buys
        # if price moved down, likely aggressive sells
        if ltp_change > 0:
            aggressive_buy += trade.quantity
        elif ltp_change < 0:
            aggressive_sell += trade.quantity
        else:
            # Use bid/ask spread
            if current_book.bid_levels and current_book.ask_levels:
                mid_price = (
                    current_book.bid_levels[0].price +
                    current_book.ask_levels[0].price
                ) / 2
                if trade.price >= mid_price:
                    aggressive_buy += trade.quantity
                else:
                    aggressive_sell += trade.quantity
    
    avg_qty = total_qty / total_trades if total_trades > 0 else 0.0
    
    return aggressive_buy, aggressive_sell, avg_qty


def calculate_cvd(
    current_trades: List[Trade],
    previous_cvd: int = 0
) -> Tuple[int, int]:
    """
    Calculate Cumulative Volume Delta.
    CVD = Sum of (Buy Volume - Sell Volume)
    
    Returns:
        (current_cvd, cvd_change)
    """
    buy_volume = sum(t.quantity for t in current_trades if t.side == "BUY")
    sell_volume = sum(t.quantity for t in current_trades if t.side == "SELL")
    
    delta = buy_volume - sell_volume
    current_cvd = previous_cvd + delta
    
    return current_cvd, delta


def detect_large_trades(
    trades: List[Trade],
    threshold_percentile: float = 90.0
) -> Tuple[List[Trade], float]:
    """Detect unusually large trades."""
    if not trades:
        return [], 0.0
    
    quantities = [t.quantity for t in trades]
    threshold = sorted(quantities)[int(len(quantities) * threshold_percentile / 100)]
    
    large_trades = [t for t in trades if t.quantity >= threshold]
    ratio = len(large_trades) / len(trades) if trades else 0.0
    
    for trade in large_trades:
        trade.is_large = True
    
    return large_trades, ratio


def estimate_cancellations(
    current_book: OrderBook,
    previous_book: Optional[OrderBook]
) -> float:
    """
    Estimate order cancellations.
    
    If order book size decreased without corresponding trades,
    orders were likely cancelled.
    """
    if not previous_book:
        return 0.0
    
    prev_total = sum(l.quantity for l in previous_book.bid_levels) + \
                 sum(l.quantity for l in previous_book.ask_levels)
    curr_total = sum(l.quantity for l in current_book.bid_levels) + \
                 sum(l.quantity for l in current_book.ask_levels)
    
    if prev_total > 0:
        cancellation_ratio = (prev_total - curr_total) / prev_total
        return max(0.0, cancellation_ratio)
    
    return 0.0


def detect_absorption(
    current_book: OrderBook,
    aggressive_buy: int,
    aggressive_sell: int
) -> str:
    """
    Detect liquidity absorption.
    
    If aggressive buy >> ask depth, asks are being "absorbed"
    If aggressive sell >> bid depth, bids are being "absorbed"
    """
    total_ask_qty = sum(l.quantity for l in current_book.ask_levels[:5])
    total_bid_qty = sum(l.quantity for l in current_book.bid_levels[:5])
    
    absorption_level = "NORMAL"
    
    if aggressive_buy > 0 and total_ask_qty > 0:
        absorption_ratio = aggressive_buy / total_ask_qty
        if absorption_ratio > 2.0:
            absorption_level = "STRONG"
        elif absorption_ratio > 1.0:
            absorption_level = "MODERATE"
    
    if aggressive_sell > 0 and total_bid_qty > 0:
        absorption_ratio = aggressive_sell / total_bid_qty
        if absorption_ratio > 2.0:
            absorption_level = "STRONG"
        elif absorption_ratio > 1.0:
            absorption_level = "MODERATE"
    
    return absorption_level


# ============================================================================
# MAIN FLOW METRICS CALCULATION
# ============================================================================


def calculate_nifty_future_flow_metrics(
    current_book: OrderBook,
    trades: List[Trade],
    previous_metrics: Optional[FlowMetrics] = None,
    previous_book: Optional[OrderBook] = None
) -> FlowMetrics:
    """
    Calculate comprehensive flow metrics for current expiry NIFTY Futures.
    
    Includes:
    - Order book analysis (top 5)
    - Aggressive trade volume
    - CVD
    - Large trade detection
    - Cancellation estimation
    - Absorption detection
    - OI analysis
    """
    metrics = FlowMetrics(
        instrument=current_book.instrument,
        underlying=current_book.underlying,
        expiry=current_book.expiry,
        ltp=current_book.ltp,
        volume=current_book.volume,
        open_interest=current_book.open_interest,
    )
    
    # 1. Order book metrics
    ob_metrics = calculate_order_book_metrics(current_book)
    metrics.total_bid_qty = ob_metrics["total_bid_qty"]
    metrics.total_ask_qty = ob_metrics["total_ask_qty"]
    metrics.bid_ask_imbalance = ob_metrics["bid_ask_imbalance"]
    metrics.weighted_bid_depth = ob_metrics["weighted_bid_depth"]
    metrics.weighted_ask_depth = ob_metrics["weighted_ask_depth"]
    metrics.weighted_imbalance = ob_metrics["weighted_imbalance"]
    
    # 2. Price changes
    if previous_metrics:
        metrics.price_change = current_book.ltp - previous_metrics.ltp
        if previous_metrics.ltp != 0:
            metrics.price_change_pct = (metrics.price_change / previous_metrics.ltp) * 100
        
        metrics.volume_change_pct = (
            ((current_book.volume - previous_metrics.volume) / previous_metrics.volume * 100)
            if previous_metrics.volume > 0 else 0
        )
        
        metrics.oi_change = current_book.open_interest - previous_metrics.open_interest
        if previous_metrics.open_interest > 0:
            metrics.oi_change_pct = (
                (metrics.oi_change / previous_metrics.open_interest) * 100
            )
    
    # 3. Trade flow analysis
    if trades:
        agg_buy, agg_sell, avg_qty = classify_aggressive_trades(
            trades, previous_book, current_book, metrics.price_change
        )
        metrics.aggressive_buy_volume = agg_buy
        metrics.aggressive_sell_volume = agg_sell
        metrics.delta = agg_buy - agg_sell
        metrics.avg_trade_qty = avg_qty
        
        large_trades, large_ratio = detect_large_trades(trades)
        metrics.largest_trade_qty = max([t.quantity for t in trades], default=0)
        metrics.large_trade_ratio = large_ratio
        
        # CVD
        prev_cvd = previous_metrics.cvd if previous_metrics else 0
        current_cvd, _ = calculate_cvd(trades, prev_cvd)
        metrics.cvd = current_cvd
    
    # 4. Cancellations
    metrics.cancellation_ratio = estimate_cancellations(current_book, previous_book)
    
    # 5. Absorption
    metrics.absorption_level = detect_absorption(
        current_book,
        metrics.aggressive_buy_volume,
        metrics.aggressive_sell_volume
    )
    
    # 6. Flow direction
    if metrics.aggressive_buy_volume > metrics.aggressive_sell_volume * 1.2:
        metrics.flow_direction = "BULLISH"
    elif metrics.aggressive_sell_volume > metrics.aggressive_buy_volume * 1.2:
        metrics.flow_direction = "BEARISH"
    else:
        metrics.flow_direction = "NEUTRAL"
    
    return metrics


# ============================================================================
# MARKET FLOW SIGNAL GENERATION
# ============================================================================


def generate_nifty_future_flow_signal(metrics: FlowMetrics) -> FlowSignal:
    """
    Generate explainable market flow signal for current expiry NIFTY Futures.
    
    Weighting:
    - 30% = Aggressive Buy vs Sell Volume
    - 20% = CVD Direction
    - 15% = Weighted Top 5 Order Book Imbalance
    - 15% = Volume Spike
    - 10% = Open Interest Context
    - 10% = Price Response
    """
    signal = FlowSignal(
        instrument=metrics.instrument,
        underlying=metrics.underlying,
        expiry=metrics.expiry,
        metrics=metrics,
    )
    
    reasons = []
    
    # 1. Aggressive volume (30%)
    total_agg = metrics.aggressive_buy_volume + metrics.aggressive_sell_volume
    agg_score = 0
    if total_agg > 0:
        buy_ratio = metrics.aggressive_buy_volume / total_agg
        agg_score = int((buy_ratio - 0.5) * 200)  # -100 to +100
        
        if buy_ratio > 0.65:
            reasons.append("✓ Aggressive buying dominant (>65%)")
        elif buy_ratio > 0.55:
            reasons.append("⚬ Slight aggressive buying bias (55-65%)")
        elif buy_ratio < 0.35:
            reasons.append("✓ Aggressive selling dominant (>65%)")
        elif buy_ratio < 0.45:
            reasons.append("⚬ Slight aggressive selling bias (35-45%)")
        else:
            reasons.append("⚬ Balanced aggressive flow")
    
    # 2. CVD Direction (20%)
    cvd_score = 0
    if metrics.cvd > 0:
        cvd_score = min(40, int(metrics.cvd / 100000))
        reasons.append(f"✓ CVD strongly positive (+{metrics.cvd:,})")
    elif metrics.cvd < 0:
        cvd_score = max(-40, int(metrics.cvd / 100000))
        reasons.append(f"✓ CVD strongly negative ({metrics.cvd:,})")
    else:
        reasons.append("⚬ CVD neutral")
    
    # 3. Weighted Imbalance (15%)
    imb_score = int(metrics.weighted_imbalance * 75)
    if metrics.weighted_imbalance > 0.15:
        reasons.append(f"✓ Strong bid-side imbalance ({metrics.weighted_imbalance:.2%})")
    elif metrics.weighted_imbalance < -0.15:
        reasons.append(f"✓ Strong ask-side imbalance ({metrics.weighted_imbalance:.2%})")
    else:
        reasons.append(f"⚬ Balanced order book ({metrics.weighted_imbalance:.2%})")
    
    # 4. Volume Spike (15%)
    vol_score = 0
    if metrics.volume_change_pct > 20:
        vol_score = min(30, int(metrics.volume_change_pct / 2))
        reasons.append(f"✓ High volume spike (+{metrics.volume_change_pct:.1f}%)")
    elif metrics.volume_change_pct < -20:
        vol_score = max(-30, int(metrics.volume_change_pct / 2))
        reasons.append(f"✓ Volume decline ({metrics.volume_change_pct:.1f}%)")
    else:
        reasons.append(f"⚬ Normal volume ({metrics.volume_change_pct:.1f}%)")
    
    # 5. Open Interest Context (10%)
    oi_score = 0
    if metrics.oi_change > 0 and metrics.price_change > 0:
        oi_score = 15
        reasons.append("✓ OI ↑ + Price ↑ = Long buildup")
    elif metrics.oi_change > 0 and metrics.price_change < 0:
        oi_score = -15
        reasons.append("✓ OI ↑ + Price ↓ = Short buildup")
    elif metrics.oi_change < 0 and metrics.price_change > 0:
        oi_score = 10
        reasons.append("⚬ OI ↓ + Price ↑ = Short covering")
    elif metrics.oi_change < 0 and metrics.price_change < 0:
        oi_score = -10
        reasons.append("⚬ OI ↓ + Price ↓ = Long unwinding")
    else:
        reasons.append("⚬ OI neutral")
    
    # 6. Price Response (10%)
    price_score = 0
    if metrics.price_change > 0:
        price_score = min(20, int(metrics.price_change_pct))
        reasons.append(f"✓ Price positive (+{metrics.price_change_pct:.2f}%)")
    elif metrics.price_change < 0:
        price_score = max(-20, int(metrics.price_change_pct))
        reasons.append(f"✓ Price negative ({metrics.price_change_pct:.2f}%)")
    else:
        reasons.append("⚬ Price unchanged")
    
    # Absorption context
    if metrics.absorption_level == "STRONG":
        reasons.append(f"✓ {metrics.absorption_level} liquidity absorption")
    elif metrics.absorption_level == "MODERATE":
        reasons.append(f"⚬ {metrics.absorption_level} liquidity absorption")
    
    # Calculate final score
    # 30% agg + 20% cvd + 15% imb + 15% vol + 10% oi + 10% price
    total_score = int(
        (agg_score * 0.30) +
        (cvd_score * 0.20) +
        (imb_score * 0.15) +
        (vol_score * 0.15) +
        (oi_score * 0.10) +
        (price_score * 0.10)
    )
    
    signal.score = max(-100, min(100, total_score))
    
    # Generate signal text
    if signal.score >= 70:
        signal.signal = "STRONG BUY"
        signal.confidence = "VERY HIGH"
    elif signal.score >= 40:
        signal.signal = "BUY"
        signal.confidence = "HIGH"
    elif signal.score >= 10:
        signal.signal = "MILD BUY"
        signal.confidence = "MEDIUM"
    elif signal.score <= -70:
        signal.signal = "STRONG SELL"
        signal.confidence = "VERY HIGH"
    elif signal.score <= -40:
        signal.signal = "SELL"
        signal.confidence = "HIGH"
    elif signal.score <= -10:
        signal.signal = "MILD SELL"
        signal.confidence = "MEDIUM"
    else:
        signal.signal = "NEUTRAL"
        signal.confidence = "LOW"
    
    signal.reasons = reasons
    
    log.info(
        f"📊 NIFTY FUTURES FLOW SIGNAL\n"
        f"   Expiry: {signal.expiry}\n"
        f"   Signal: {signal.signal}\n"
        f"   Score: {signal.score}\n"
        f"   Confidence: {signal.confidence}"
    )
    
    return signal
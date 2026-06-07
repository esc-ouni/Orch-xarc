"""
Pydantic models for Orch-xarc.

Every tool in the registry accepts and returns models from this module,
making tool outputs directly composable as inputs to downstream tools.

Sections:
  1. Binance (ticker / kline)
  2. Polymarket (events, CLOB orderbooks, prices)
  3. Kalshi (markets, prices)
  4. Math / Arbitrage (probabilities, strike comparison, legs, plans)
  5. Ops (scans, health, agent summaries)
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
#  1. Binance
# ═══════════════════════════════════════════════════════════


class BinanceTickerRequest(BaseModel):
    """Request params for Binance spot ticker."""
    symbol: str = Field(default="BTCUSDT", description="Trading pair symbol.")


class BinanceTicker(BaseModel):
    """Binance spot ticker response."""
    symbol: str
    price: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BinanceKlineRequest(BaseModel):
    """Request params for Binance kline (candlestick) data."""
    symbol: str = Field(default="BTCUSDT")
    interval: str = Field(default="1h")
    start_time_ms: int = Field(description="Candle open time in epoch ms.")
    limit: int = Field(default=1, ge=1, le=1000)


class BinanceKline(BaseModel):
    """Single Binance kline (OHLCV)."""
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


# ═══════════════════════════════════════════════════════════
#  2. Polymarket
# ═══════════════════════════════════════════════════════════


class MarketUrls(BaseModel):
    """Resolved URLs for the current hourly market on both platforms."""
    polymarket: str
    kalshi: str
    target_time_utc: datetime


class PolymarketEventRequest(BaseModel):
    """Query parameters for the Polymarket Gamma API."""
    slug: str = Field(description="Event slug, e.g. 'bitcoin-up-or-down-…'.")


class PolymarketMarket(BaseModel):
    """A single binary market inside a Polymarket event."""
    condition_id: str = ""
    question: str = ""
    outcomes: list[str] = Field(default_factory=list)
    outcome_prices: list[float] = Field(default_factory=list)
    clob_token_ids: list[str] = Field(default_factory=list)


class PolymarketEvent(BaseModel):
    """Top-level Polymarket event returned by Gamma API."""
    id: str = ""
    slug: str = ""
    title: str = ""
    markets: list[PolymarketMarket] = Field(default_factory=list)


class CLOBOrderBookRequest(BaseModel):
    """Request for the Polymarket CLOB orderbook."""
    token_id: str = Field(description="CLOB token ID for one outcome.")


class CLOBOrder(BaseModel):
    """A single order on the CLOB."""
    price: float
    size: float


class CLOBOrderBook(BaseModel):
    """Full orderbook snapshot from the Polymarket CLOB."""
    bids: list[CLOBOrder] = Field(default_factory=list)
    asks: list[CLOBOrder] = Field(default_factory=list)
    asset_id: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PolymarketPrice(BaseModel):
    """Processed price for a single Polymarket outcome."""
    outcome: str = Field(description="'Up' or 'Down'.")
    best_bid: float = 0.0
    best_ask: float = 0.0
    mid: float = 0.0
    spread: float = 0.0


class PolymarketPricePair(BaseModel):
    """Paired Up/Down prices for the current Polymarket event."""
    up: PolymarketPrice
    down: PolymarketPrice
    slug: str = ""
    price_to_beat: float | None = Field(
        default=None,
        description="Binance 1h candle open price — the strike.",
    )
    current_btc_price: float | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════
#  3. Kalshi
# ═══════════════════════════════════════════════════════════


class KalshiMarketRequest(BaseModel):
    """Query parameters for the Kalshi markets endpoint."""
    event_ticker: str
    limit: int = Field(default=100, ge=1, le=200)
    cursor: str | None = None


class KalshiMarket(BaseModel):
    """Parsed Kalshi market with extracted strike price."""
    ticker: str = ""
    subtitle: str = ""
    strike: float = Field(description="Strike extracted from subtitle, e.g. 96250.0")
    yes_bid: int = Field(default=0, description="Yes bid in cents.")
    yes_ask: int = Field(default=0, description="Yes ask in cents.")
    no_bid: int = Field(default=0, description="No bid in cents.")
    no_ask: int = Field(default=0, description="No ask in cents.")


class KalshiPrice(BaseModel):
    """Kalshi prices normalized to dollars [0.0 – 1.0]."""
    strike: float
    yes_bid: float = 0.0
    yes_ask: float = 0.0
    no_bid: float = 0.0
    no_ask: float = 0.0


class KalshiEventMarkets(BaseModel):
    """All markets for a single Kalshi event."""
    event_ticker: str
    current_price: float | None = None
    markets: list[KalshiMarket] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════
#  4. Math / Arbitrage
# ═══════════════════════════════════════════════════════════


class ImpliedProbability(BaseModel):
    """Implied probability derived from a market price."""
    platform: str
    outcome: str
    probability: float = Field(ge=0.0, le=1.0)
    raw_price: float


class StrikeRelationship(str, enum.Enum):
    POLY_ABOVE = "poly_above_kalshi"
    POLY_BELOW = "poly_below_kalshi"
    EQUAL = "equal"


class StrikeComparison(BaseModel):
    """Result of comparing Polymarket vs Kalshi strike prices."""
    poly_strike: float
    kalshi_strike: float
    relationship: StrikeRelationship


class ArbitrageLeg(BaseModel):
    """One leg of a two-legged arbitrage trade."""
    platform: str = Field(description="'polymarket' or 'kalshi'.")
    side: str = Field(description="'Up', 'Down', 'Yes', or 'No'.")
    cost: float = Field(ge=0.0, le=1.0)


class ArbitrageCheck(BaseModel):
    """Result of checking one pair of positions for arbitrage."""
    leg_a: ArbitrageLeg
    leg_b: ArbitrageLeg
    total_cost: float
    is_arbitrage: bool = False
    margin: float = 0.0
    strategy_label: str = ""
    kalshi_strike: float = 0.0


class ArbitrageOpportunity(BaseModel):
    """A confirmed arbitrage opportunity with metadata."""
    check: ArbitrageCheck
    strategy_description: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExecutionPlan(BaseModel):
    """
    Structured plan returned by the arbitrage subagent.

    This is the final output of the isolated subagent — it contains ranked
    opportunities, a recommendation, confidence score, and risk notes.
    """
    opportunities: list[ArbitrageOpportunity] = Field(default_factory=list)
    best_opportunity: ArbitrageCheck | None = None
    recommended_action: str = "no_action"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_notes: list[str] = Field(default_factory=list)
    total_checks_performed: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════
#  5. Ops
# ═══════════════════════════════════════════════════════════


class ScanRequest(BaseModel):
    """Input for triggering an arbitrage scan."""
    scan_id: str = ""
    platforms: list[str] = Field(default_factory=lambda: ["polymarket", "kalshi"])
    max_markets: int = Field(default=20, ge=1, le=100)


class ScanResult(BaseModel):
    """Output of a completed arbitrage scan."""
    scan_id: str
    execution_plan: ExecutionPlan | None = None
    opportunities_found: int = 0
    duration_ms: float = 0.0
    tool_calls_count: int = 0
    errors: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthStatus(BaseModel):
    """System health report."""
    status: str = "ok"
    uptime_seconds: float = 0.0
    version: str = "0.1.0"
    rate_limiters: dict[str, Any] = Field(default_factory=dict)
    tool_count: int = 0


class ToolCallRecord(BaseModel):
    """Record of a single tool invocation for observability."""
    tool_name: str
    namespace: str
    duration_ms: float
    success: bool
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentRunSummary(BaseModel):
    """Summary of a complete agent run."""
    run_id: str
    scan_id: str = ""
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    total_tool_calls: int = 0
    total_errors: int = 0
    duration_ms: float = 0.0
    result: ScanResult | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

"""Unit tests for Pydantic models."""
from __future__ import annotations
import pytest
from pydantic import ValidationError
from src.core.models import (
    BinanceTicker, BinanceKlineRequest, CLOBOrder, CLOBOrderBook,
    PolymarketPrice, ArbitrageLeg, ArbitrageCheck, ExecutionPlan,
    ScanRequest, ScanResult, HealthStatus, StrikeComparison,
    StrikeRelationship, ImpliedProbability, KalshiMarket,
)


class TestBinanceTicker:
    def test_valid(self):
        t = BinanceTicker(symbol="BTCUSDT", price=97500.0)
        assert t.price == 97500.0

class TestCLOBOrder:
    def test_valid(self):
        o = CLOBOrder(price=0.55, size=100.0)
        assert o.price == 0.55

class TestPolymarketPrice:
    def test_defaults(self):
        p = PolymarketPrice(outcome="Up")
        assert p.best_bid == 0.0

class TestArbitrageLeg:
    def test_valid(self):
        leg = ArbitrageLeg(platform="polymarket", side="Down", cost=0.42)
        assert leg.cost == 0.42

    def test_cost_bounds(self):
        with pytest.raises(ValidationError):
            ArbitrageLeg(platform="x", side="y", cost=1.5)

class TestImpliedProbability:
    def test_bounds(self):
        with pytest.raises(ValidationError):
            ImpliedProbability(platform="x", outcome="y", probability=1.5, raw_price=1.5)

class TestStrikeComparison:
    def test_enum(self):
        sc = StrikeComparison(
            poly_strike=98000, kalshi_strike=97000,
            relationship=StrikeRelationship.POLY_ABOVE,
        )
        assert sc.relationship == StrikeRelationship.POLY_ABOVE

class TestExecutionPlan:
    def test_defaults(self):
        p = ExecutionPlan()
        assert p.recommended_action == "no_action"
        assert p.confidence == 0.0

class TestScanRequest:
    def test_defaults(self):
        sr = ScanRequest()
        assert "polymarket" in sr.platforms

class TestKalshiMarket:
    def test_valid(self):
        m = KalshiMarket(strike=97500.0, yes_ask=52)
        assert m.strike == 97500.0

class TestHealthStatus:
    def test_defaults(self):
        h = HealthStatus()
        assert h.status == "ok"

"""
Unit tests for all 14 math_logic tools.

These are pure functions — no mocking needed.
"""

from __future__ import annotations

import pytest

from src.tools.math_logic.tools import (
    build_arbitrage_check,
    build_arbitrage_leg,
    build_execution_plan,
    calc_arbitrage_margin,
    calc_expected_value,
    calc_implied_prob,
    calc_inverse_prob,
    calc_no_price_from_yes,
    calc_total_cost,
    check_arbitrage_condition,
    compare_strikes,
    determine_strategy_legs,
    rank_opportunities,
    validate_orderbook_freshness,
)


class TestCalcImpliedProb:
    def test_normal_price(self) -> None:
        result = calc_implied_prob.invoke({"price": 0.65, "platform": "poly", "outcome": "Up"})
        assert result["probability"] == 0.65
        assert result["platform"] == "poly"

    def test_clamps_above_one(self) -> None:
        result = calc_implied_prob.invoke({"price": 1.5})
        assert result["probability"] == 1.0

    def test_clamps_below_zero(self) -> None:
        result = calc_implied_prob.invoke({"price": -0.1})
        assert result["probability"] == 0.0


class TestCalcInverseProb:
    def test_normal(self) -> None:
        assert calc_inverse_prob.invoke({"probability": 0.7}) == pytest.approx(0.3)

    def test_zero(self) -> None:
        assert calc_inverse_prob.invoke({"probability": 0.0}) == 1.0

    def test_one(self) -> None:
        assert calc_inverse_prob.invoke({"probability": 1.0}) == 0.0


class TestCalcNoPriceFromYes:
    def test_normal(self) -> None:
        assert calc_no_price_from_yes.invoke({"yes_price": 0.6}) == pytest.approx(0.4)

    def test_edge(self) -> None:
        assert calc_no_price_from_yes.invoke({"yes_price": 1.0}) == 0.0


class TestCompareStrikes:
    def test_poly_above(self) -> None:
        result = compare_strikes.invoke({"poly_strike": 98000, "kalshi_strike": 97000})
        assert result["relationship"] == "poly_above_kalshi"

    def test_poly_below(self) -> None:
        result = compare_strikes.invoke({"poly_strike": 97000, "kalshi_strike": 98000})
        assert result["relationship"] == "poly_below_kalshi"

    def test_equal(self) -> None:
        result = compare_strikes.invoke({"poly_strike": 97500, "kalshi_strike": 97500})
        assert result["relationship"] == "equal"


class TestDetermineStrategyLegs:
    def test_poly_above(self) -> None:
        comp = {"relationship": "poly_above_kalshi", "poly_strike": 98000, "kalshi_strike": 97000}
        result = determine_strategy_legs.invoke({"strike_comparison": comp})
        assert result["poly_side"] == "Down"
        assert result["kalshi_side"] == "Yes"

    def test_poly_below(self) -> None:
        comp = {"relationship": "poly_below_kalshi", "poly_strike": 97000, "kalshi_strike": 98000}
        result = determine_strategy_legs.invoke({"strike_comparison": comp})
        assert result["poly_side"] == "Up"
        assert result["kalshi_side"] == "No"

    def test_equal_returns_both(self) -> None:
        comp = {"relationship": "equal", "poly_strike": 97500, "kalshi_strike": 97500}
        result = determine_strategy_legs.invoke({"strike_comparison": comp})
        assert len(result["strategies"]) == 2


class TestBuildArbitrageLeg:
    def test_builds_correctly(self) -> None:
        result = build_arbitrage_leg.invoke({"platform": "polymarket", "side": "Down", "cost": 0.42})
        assert result["platform"] == "polymarket"
        assert result["side"] == "Down"
        assert result["cost"] == 0.42


class TestCalcTotalCost:
    def test_sum(self) -> None:
        assert calc_total_cost.invoke({"leg_a_cost": 0.42, "leg_b_cost": 0.55}) == pytest.approx(0.97)


class TestCheckArbitrageCondition:
    def test_arbitrage_exists(self) -> None:
        assert check_arbitrage_condition.invoke({"total_cost": 0.95}) is True

    def test_no_arbitrage(self) -> None:
        assert check_arbitrage_condition.invoke({"total_cost": 1.02}) is False

    def test_exact_one(self) -> None:
        assert check_arbitrage_condition.invoke({"total_cost": 1.0}) is False


class TestCalcArbitrageMargin:
    def test_positive_margin(self) -> None:
        assert calc_arbitrage_margin.invoke({"total_cost": 0.95}) == pytest.approx(0.05)

    def test_negative_margin(self) -> None:
        assert calc_arbitrage_margin.invoke({"total_cost": 1.05}) == pytest.approx(-0.05)


class TestBuildArbitrageCheck:
    def test_full_check_arb(self) -> None:
        result = build_arbitrage_check.invoke({
            "poly_platform": "polymarket",
            "poly_side": "Down",
            "poly_cost": 0.42,
            "kalshi_platform": "kalshi",
            "kalshi_side": "Yes",
            "kalshi_cost": 0.52,
            "kalshi_strike": 97000,
            "strategy_label": "Poly Down + Kalshi Yes",
        })
        assert result["total_cost"] == pytest.approx(0.94)
        assert result["is_arbitrage"] is True
        assert result["margin"] == pytest.approx(0.06)

    def test_full_check_no_arb(self) -> None:
        result = build_arbitrage_check.invoke({
            "poly_platform": "polymarket",
            "poly_side": "Up",
            "poly_cost": 0.57,
            "kalshi_platform": "kalshi",
            "kalshi_side": "No",
            "kalshi_cost": 0.57,
            "kalshi_strike": 98000,
            "strategy_label": "Poly Up + Kalshi No",
        })
        assert result["is_arbitrage"] is False


class TestRankOpportunities:
    def test_ranks_by_margin(self) -> None:
        checks = [
            {"is_arbitrage": True, "margin": 0.02, "total_cost": 0.98},
            {"is_arbitrage": True, "margin": 0.08, "total_cost": 0.92},
            {"is_arbitrage": False, "margin": 0.0, "total_cost": 1.05},
            {"is_arbitrage": True, "margin": 0.05, "total_cost": 0.95},
        ]
        result = rank_opportunities.invoke({"checks": checks})
        assert len(result) == 3  # Only profitable
        assert result[0]["margin"] == 0.08
        assert result[1]["margin"] == 0.05

    def test_empty_input(self) -> None:
        result = rank_opportunities.invoke({"checks": []})
        assert result == []


class TestBuildExecutionPlan:
    def test_with_opportunities(self) -> None:
        opps = [
            {"margin": 0.08, "total_cost": 0.92, "is_arbitrage": True,
             "strategy_label": "test", "kalshi_strike": 97000,
             "leg_a": {}, "leg_b": {}},
        ]
        plan = build_execution_plan.invoke({"opportunities": opps, "total_checks": 10})
        assert plan["recommended_action"] == "strong_buy"
        assert plan["confidence"] == 0.95
        assert plan["total_checks_performed"] == 10

    def test_no_opportunities(self) -> None:
        plan = build_execution_plan.invoke({"opportunities": [], "total_checks": 5})
        assert plan["recommended_action"] == "no_action"
        assert plan["confidence"] == 0.0


class TestCalcExpectedValue:
    def test_ev(self) -> None:
        assert calc_expected_value.invoke({"margin": 0.05, "probability": 0.8}) == pytest.approx(0.04)


class TestValidateOrderbookFreshness:
    def test_fresh(self) -> None:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        assert validate_orderbook_freshness.invoke({"timestamp_iso": now, "max_age_seconds": 60}) is True

    def test_stale(self) -> None:
        assert validate_orderbook_freshness.invoke({"timestamp_iso": "2020-01-01T00:00:00+00:00"}) is False

    def test_invalid(self) -> None:
        assert validate_orderbook_freshness.invoke({"timestamp_iso": "not-a-date"}) is False

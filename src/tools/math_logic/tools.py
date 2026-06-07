"""
Math / Arbitrage namespace — 14 tools for probability calculations,
strike comparison, arbitrage detection, and execution plan building.

These are pure functions with no external I/O — they operate entirely
on Pydantic-typed data passed in from the platform tools.

This namespace is the SCOPED TOOL SET for the arbitrage subagent.
"""

from __future__ import annotations

from datetime import datetime, timezone

from langchain_core.tools import tool


# ═══════════════════════════════════════════════════════════
#  Tools
# ═══════════════════════════════════════════════════════════


@tool
def calc_implied_prob(price: float, platform: str = "unknown", outcome: str = "unknown") -> dict:
    """Calculate the implied probability from a market price.

    In binary markets, the price IS the implied probability.
    A price of 0.65 means the market implies a 65% chance.

    Args:
        price: Market price in [0.0, 1.0].
        platform: Source platform name.
        outcome: Outcome label (e.g., 'Up', 'Yes').

    Returns:
        Dict with platform, outcome, probability, raw_price.
    """
    prob = max(0.0, min(1.0, price))
    return {
        "platform": platform,
        "outcome": outcome,
        "probability": round(prob, 6),
        "raw_price": price,
    }


@tool
def calc_inverse_prob(probability: float) -> float:
    """Calculate the complementary probability (1 - p).

    Args:
        probability: Probability value in [0.0, 1.0].

    Returns:
        1 - probability, clamped to [0.0, 1.0].
    """
    return round(max(0.0, min(1.0, 1.0 - probability)), 6)


@tool
def calc_no_price_from_yes(yes_price: float) -> float:
    """Calculate the theoretical No price from a Yes price.

    In an efficient binary market: yes_price + no_price = 1.0.

    Args:
        yes_price: Yes price in [0.0, 1.0].

    Returns:
        Theoretical No price (1.0 - yes_price).
    """
    return round(max(0.0, 1.0 - yes_price), 6)


@tool
def compare_strikes(poly_strike: float, kalshi_strike: float) -> dict:
    """Compare Polymarket and Kalshi strike prices.

    This determines which arbitrage strategy to apply:
    - poly > kalshi → Buy Poly Down + Kalshi Yes
    - poly < kalshi → Buy Poly Up + Kalshi No
    - equal → Check both strategies

    Args:
        poly_strike: Polymarket strike (Binance 1h open price).
        kalshi_strike: Kalshi market strike price.

    Returns:
        Dict with poly_strike, kalshi_strike, relationship ('poly_above_kalshi', 'poly_below_kalshi', or 'equal').
    """
    if poly_strike > kalshi_strike:
        rel = "poly_above_kalshi"
    elif poly_strike < kalshi_strike:
        rel = "poly_below_kalshi"
    else:
        rel = "equal"

    return {
        "poly_strike": poly_strike,
        "kalshi_strike": kalshi_strike,
        "relationship": rel,
    }


@tool
def determine_strategy_legs(strike_comparison: dict) -> dict:
    """Determine which legs to use for the arbitrage strategy.

    Based on the strike comparison result:
    - poly_above_kalshi → Poly Down + Kalshi Yes (guaranteed ≥1 win)
    - poly_below_kalshi → Poly Up + Kalshi No (guaranteed ≥1 win)
    - equal → returns both strategies to check

    Args:
        strike_comparison: Output of compare_strikes.

    Returns:
        Dict with poly_side, kalshi_side, and strategy label.
    """
    rel = strike_comparison.get("relationship", "equal")

    if rel == "poly_above_kalshi":
        return {
            "poly_side": "Down",
            "kalshi_side": "Yes",
            "strategy": "Buy Poly DOWN + Kalshi YES",
            "strategies": [{"poly_side": "Down", "kalshi_side": "Yes"}],
        }
    elif rel == "poly_below_kalshi":
        return {
            "poly_side": "Up",
            "kalshi_side": "No",
            "strategy": "Buy Poly UP + Kalshi NO",
            "strategies": [{"poly_side": "Up", "kalshi_side": "No"}],
        }
    else:  # equal
        return {
            "poly_side": "both",
            "kalshi_side": "both",
            "strategy": "Check both: Down+Yes and Up+No",
            "strategies": [
                {"poly_side": "Down", "kalshi_side": "Yes"},
                {"poly_side": "Up", "kalshi_side": "No"},
            ],
        }


@tool
def build_arbitrage_leg(platform: str, side: str, cost: float) -> dict:
    """Build a single arbitrage leg.

    Args:
        platform: 'polymarket' or 'kalshi'.
        side: Position side ('Up', 'Down', 'Yes', 'No').
        cost: Cost to buy this position in [0.0, 1.0].

    Returns:
        Dict representing one leg of the arbitrage trade.
    """
    return {
        "platform": platform,
        "side": side,
        "cost": round(cost, 6),
    }


@tool
def calc_total_cost(leg_a_cost: float, leg_b_cost: float) -> float:
    """Calculate the total cost of a two-legged arbitrage trade.

    Args:
        leg_a_cost: Cost of leg A (e.g., Poly Down price).
        leg_b_cost: Cost of leg B (e.g., Kalshi Yes price).

    Returns:
        Total cost as sum of both legs.
    """
    return round(leg_a_cost + leg_b_cost, 6)


@tool
def check_arbitrage_condition(total_cost: float) -> bool:
    """Check if a total cost represents an arbitrage opportunity.

    In binary markets, if the combined cost of two complementary
    positions is less than $1.00, a risk-free profit exists.

    Args:
        total_cost: Combined cost of both legs.

    Returns:
        True if total_cost < 1.0 (arbitrage exists).
    """
    return total_cost < 1.0


@tool
def calc_arbitrage_margin(total_cost: float) -> float:
    """Calculate the arbitrage margin (risk-free profit per unit).

    Args:
        total_cost: Combined cost of both legs.

    Returns:
        Margin as 1.0 - total_cost. Positive means profit.
    """
    return round(1.0 - total_cost, 6)


@tool
def build_arbitrage_check(
    poly_platform: str,
    poly_side: str,
    poly_cost: float,
    kalshi_platform: str,
    kalshi_side: str,
    kalshi_cost: float,
    kalshi_strike: float,
    strategy_label: str = "",
) -> dict:
    """Build a complete arbitrage check result.

    Composes: build_arbitrage_leg × 2 + calc_total_cost + check_arbitrage_condition + calc_arbitrage_margin.

    Args:
        poly_platform: Always 'polymarket'.
        poly_side: 'Up' or 'Down'.
        poly_cost: Cost of the Polymarket leg.
        kalshi_platform: Always 'kalshi'.
        kalshi_side: 'Yes' or 'No'.
        kalshi_cost: Cost of the Kalshi leg (in dollars).
        kalshi_strike: Kalshi strike price.
        strategy_label: Human-readable strategy description.

    Returns:
        Complete check result dict with legs, total_cost, is_arbitrage, margin.
    """
    total = round(poly_cost + kalshi_cost, 6)
    is_arb = total < 1.0
    margin = round(1.0 - total, 6) if is_arb else 0.0

    return {
        "leg_a": {"platform": poly_platform, "side": poly_side, "cost": poly_cost},
        "leg_b": {"platform": kalshi_platform, "side": kalshi_side, "cost": kalshi_cost},
        "total_cost": total,
        "is_arbitrage": is_arb,
        "margin": margin,
        "strategy_label": strategy_label,
        "kalshi_strike": kalshi_strike,
    }


@tool
def rank_opportunities(checks: list[dict]) -> list[dict]:
    """Rank arbitrage checks by margin, best first.

    Filters to only include actual arbitrage opportunities (margin > 0),
    then sorts by margin descending.

    Args:
        checks: List of arbitrage check dicts from build_arbitrage_check.

    Returns:
        Sorted list with only profitable opportunities.
    """
    profitable = [c for c in checks if c.get("is_arbitrage", False)]
    return sorted(profitable, key=lambda c: c.get("margin", 0), reverse=True)


@tool
def build_execution_plan(
    opportunities: list[dict],
    total_checks: int = 0,
) -> dict:
    """Build a final execution plan from ranked opportunities.

    This is the subagent's terminal tool — it produces the structured
    result that gets returned to the parent agent.

    Args:
        opportunities: Ranked list of profitable arbitrage checks.
        total_checks: Total number of checks performed.

    Returns:
        Execution plan dict with best opportunity, recommendation, confidence, and risk notes.
    """
    if not opportunities:
        return {
            "opportunities": [],
            "best_opportunity": None,
            "recommended_action": "no_action",
            "confidence": 0.0,
            "risk_notes": ["No arbitrage opportunities found in current scan."],
            "total_checks_performed": total_checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    best = opportunities[0]
    margin = best.get("margin", 0)

    # Confidence heuristic based on margin size
    if margin >= 0.05:
        confidence = 0.95
        action = "strong_buy"
    elif margin >= 0.02:
        confidence = 0.75
        action = "buy"
    elif margin >= 0.005:
        confidence = 0.5
        action = "monitor"
    else:
        confidence = 0.3
        action = "weak_signal"

    risk_notes = []
    if margin < 0.01:
        risk_notes.append("Margin is very thin — execution costs may exceed profit.")
    if len(opportunities) == 1:
        risk_notes.append("Only one opportunity found — limited diversification.")

    return {
        "opportunities": [
            {
                "check": opp,
                "strategy_description": opp.get("strategy_label", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for opp in opportunities
        ],
        "best_opportunity": best,
        "recommended_action": action,
        "confidence": confidence,
        "risk_notes": risk_notes,
        "total_checks_performed": total_checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@tool
def calc_expected_value(margin: float, probability: float) -> float:
    """Calculate expected value of an arbitrage trade.

    Args:
        margin: Risk-free margin per unit.
        probability: Estimated probability that the trade executes successfully.

    Returns:
        Expected value as margin × probability.
    """
    return round(margin * probability, 6)


@tool
def validate_orderbook_freshness(timestamp_iso: str, max_age_seconds: float = 30.0) -> bool:
    """Check if an orderbook timestamp is fresh enough.

    Args:
        timestamp_iso: ISO format timestamp of the orderbook.
        max_age_seconds: Maximum acceptable age in seconds.

    Returns:
        True if the orderbook is fresh (within max_age_seconds).
    """
    try:
        ts = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        age = (now - ts).total_seconds()
        return age <= max_age_seconds
    except (ValueError, TypeError):
        return False


# ── Export ──────────────────────────────────────────────────

MATH_LOGIC_TOOLS = [
    calc_implied_prob,
    calc_inverse_prob,
    calc_no_price_from_yes,
    compare_strikes,
    determine_strategy_legs,
    build_arbitrage_leg,
    calc_total_cost,
    check_arbitrage_condition,
    calc_arbitrage_margin,
    build_arbitrage_check,
    rank_opportunities,
    build_execution_plan,
    calc_expected_value,
    validate_orderbook_freshness,
]

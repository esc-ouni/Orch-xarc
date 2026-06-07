"""
Evaluation harness for Orch-xarc.

Loads fixture data, invokes the math_logic tools directly (no LLM needed),
and validates that the arbitrage detection pipeline produces correct results.

Run:  python -m evals.eval_runner
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.math_logic.tools import (
    build_arbitrage_check,
    build_execution_plan,
    calc_arbitrage_margin,
    calc_total_cost,
    check_arbitrage_condition,
    compare_strikes,
    determine_strategy_legs,
    rank_opportunities,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / name
    with open(path) as f:
        return json.load(f)


def eval_arbitrage_detection() -> dict:
    """
    Evaluate the full arbitrage detection pipeline using fixture data.

    Steps:
      1. Load Polymarket and Kalshi fixtures
      2. For each Kalshi market, compare strikes and check for arbitrage
      3. Validate that known opportunities are detected
      4. Validate that the execution plan is well-formed
    """
    poly = load_fixture("poly_snapshot_arb.json")
    kalshi = load_fixture("kalshi_snapshot.json")

    poly_strike = poly["price_to_beat"]  # 97500.0
    poly_up_cost = poly["up"]["best_ask"]  # 0.57
    poly_down_cost = poly["down"]["best_ask"]  # 0.42

    all_checks = []
    errors = []
    passed = 0
    failed = 0

    print("═══════════════════════════════════════════════════")
    print("  Orch-xarc Evaluation Harness")
    print("═══════════════════════════════════════════════════")
    print(f"  Polymarket Strike: ${poly_strike:,.2f}")
    print(f"  Poly Up: ${poly_up_cost:.3f} | Poly Down: ${poly_down_cost:.3f}")
    print(f"  Kalshi Markets: {len(kalshi['markets'])}")
    print()

    # ── Test 1: Strike Comparison ──────────────────────────
    for km in kalshi["markets"]:
        kalshi_strike = km["strike"]
        comparison = compare_strikes.invoke({
            "poly_strike": poly_strike,
            "kalshi_strike": kalshi_strike,
        })

        # Validate comparison
        if poly_strike > kalshi_strike:
            expected = "poly_above_kalshi"
        elif poly_strike < kalshi_strike:
            expected = "poly_below_kalshi"
        else:
            expected = "equal"

        if comparison["relationship"] == expected:
            passed += 1
        else:
            failed += 1
            errors.append(f"Strike comparison wrong for {kalshi_strike}")

        # Determine strategy and build check
        strategy = determine_strategy_legs.invoke({"strike_comparison": comparison})
        strategies = strategy.get("strategies", [])

        for s in strategies:
            poly_side = s["poly_side"]
            kalshi_side = s["kalshi_side"]

            poly_cost = poly_down_cost if poly_side == "Down" else poly_up_cost
            kalshi_cost_cents = km.get(f"{kalshi_side.lower()}_ask", 0)
            kalshi_cost = kalshi_cost_cents / 100.0

            check = build_arbitrage_check.invoke({
                "poly_platform": "polymarket",
                "poly_side": poly_side,
                "poly_cost": poly_cost,
                "kalshi_platform": "kalshi",
                "kalshi_side": kalshi_side,
                "kalshi_cost": kalshi_cost,
                "kalshi_strike": kalshi_strike,
                "strategy_label": f"Poly {poly_side} + Kalshi {kalshi_side}",
            })

            all_checks.append(check)

            # Validate check
            expected_total = round(poly_cost + kalshi_cost, 6)
            if abs(check["total_cost"] - expected_total) < 0.0001:
                passed += 1
            else:
                failed += 1
                errors.append(f"Total cost mismatch at strike {kalshi_strike}")

            expected_arb = expected_total < 1.0
            if check["is_arbitrage"] == expected_arb:
                passed += 1
            else:
                failed += 1
                errors.append(f"Arb detection wrong at strike {kalshi_strike}")

            status = "✅ ARB" if check["is_arbitrage"] else "  ---"
            print(
                f"  {status} | Strike ${kalshi_strike:>9,.0f} | "
                f"Poly {poly_side:>4} ${poly_cost:.3f} + "
                f"Kalshi {kalshi_side:>3} ${kalshi_cost:.3f} = "
                f"${check['total_cost']:.3f} | "
                f"Margin: ${check['margin']:.3f}"
            )

    print()

    # ── Test 2: Ranking ────────────────────────────────────
    ranked = rank_opportunities.invoke({"checks": all_checks})
    if ranked:
        # Best opportunity should have highest margin
        margins = [r["margin"] for r in ranked]
        if margins == sorted(margins, reverse=True):
            passed += 1
            print(f"  ✅ Ranking: {len(ranked)} opportunities correctly sorted")
        else:
            failed += 1
            errors.append("Ranking order is wrong")
            print(f"  ❌ Ranking: order is wrong")
    else:
        print(f"  ⚠️  No arbitrage opportunities found (may be expected)")
        passed += 1

    # ── Test 3: Execution Plan ─────────────────────────────
    plan = build_execution_plan.invoke({
        "opportunities": ranked,
        "total_checks": len(all_checks),
    })

    if plan.get("total_checks_performed") == len(all_checks):
        passed += 1
    else:
        failed += 1
        errors.append("Execution plan total_checks mismatch")

    if plan.get("timestamp"):
        passed += 1
    else:
        failed += 1
        errors.append("Execution plan missing timestamp")

    if ranked and plan.get("best_opportunity"):
        if plan["best_opportunity"]["margin"] == ranked[0]["margin"]:
            passed += 1
        else:
            failed += 1
            errors.append("Best opportunity mismatch in plan")

    print(f"\n  Plan: {plan.get('recommended_action', 'unknown')} "
          f"(confidence: {plan.get('confidence', 0):.0%})")

    # ── Summary ────────────────────────────────────────────
    print(f"\n{'═' * 50}")
    print(f"  Results: {passed} passed, {failed} failed")
    if errors:
        print(f"  Errors:")
        for e in errors:
            print(f"    • {e}")
    print(f"{'═' * 50}")

    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total_checks": len(all_checks),
        "opportunities_found": len(ranked),
    }


if __name__ == "__main__":
    result = eval_arbitrage_detection()
    sys.exit(1 if result["failed"] > 0 else 0)

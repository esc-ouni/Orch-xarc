"""
Unit tests for Kalshi tools (non-HTTP tools only — parsing, sorting, filtering).
"""

from __future__ import annotations

import pytest

from src.tools.kalshi.tools import (
    kalshi_extract_event_ticker,
    kalshi_parse_strike_from_subtitle,
    kalshi_build_market_entry,
    kalshi_normalize_prices_to_dollars,
    kalshi_sort_markets_by_strike,
    kalshi_find_closest_to_strike,
    kalshi_select_market_window,
    kalshi_get_yes_ask,
    kalshi_get_no_ask,
    kalshi_get_yes_bid,
    kalshi_get_no_bid,
    kalshi_filter_markets_by_range,
)


class TestKalshiExtractEventTicker:
    def test_normal_url(self) -> None:
        result = kalshi_extract_event_ticker.invoke(
            {"url": "https://kalshi.com/markets/kxbtcd"}
        )
        assert result == "KXBTCD"

    def test_trailing_slash(self) -> None:
        result = kalshi_extract_event_ticker.invoke(
            {"url": "https://kalshi.com/markets/kxbtcd/"}
        )
        assert result == "KXBTCD"


class TestKalshiParseStrike:
    def test_normal(self) -> None:
        result = kalshi_parse_strike_from_subtitle.invoke(
            {"subtitle": "$96,250 or above"}
        )
        assert result == 96250.0

    def test_no_match(self) -> None:
        result = kalshi_parse_strike_from_subtitle.invoke(
            {"subtitle": "No dollar sign here"}
        )
        assert result == 0.0

    def test_large_number(self) -> None:
        result = kalshi_parse_strike_from_subtitle.invoke(
            {"subtitle": "$100,000 to $100,249"}
        )
        assert result == 100000.0


class TestKalshiBuildMarketEntry:
    def test_builds_correctly(self) -> None:
        raw = {
            "ticker": "KXBTCD-T1",
            "subtitle": "$97,500 or above",
            "yes_bid": 50,
            "yes_ask": 52,
            "no_bid": 47,
            "no_ask": 49,
        }
        result = kalshi_build_market_entry.invoke({"raw_market": raw})
        assert result["strike"] == 97500.0
        assert result["yes_ask"] == 52
        assert result["ticker"] == "KXBTCD-T1"


class TestKalshiNormalizePrices:
    def test_converts_cents_to_dollars(self) -> None:
        market = {"strike": 97500.0, "yes_bid": 50, "yes_ask": 52, "no_bid": 47, "no_ask": 49}
        result = kalshi_normalize_prices_to_dollars.invoke({"market": market})
        assert result["yes_ask"] == pytest.approx(0.52)
        assert result["no_ask"] == pytest.approx(0.49)


class TestKalshiSortMarkets:
    def test_sorts_ascending(self) -> None:
        markets = [
            {"strike": 98000},
            {"strike": 96000},
            {"strike": 97000},
        ]
        result = kalshi_sort_markets_by_strike.invoke({"markets": markets})
        assert result[0]["strike"] == 96000
        assert result[-1]["strike"] == 98000


class TestKalshiFindClosest:
    def test_finds_exact(self) -> None:
        markets = [{"strike": 96000}, {"strike": 97000}, {"strike": 98000}]
        idx = kalshi_find_closest_to_strike.invoke(
            {"markets": markets, "target_strike": 97000}
        )
        assert idx == 1

    def test_finds_nearest(self) -> None:
        markets = [{"strike": 96000}, {"strike": 97000}, {"strike": 98000}]
        idx = kalshi_find_closest_to_strike.invoke(
            {"markets": markets, "target_strike": 97200}
        )
        assert idx == 1

    def test_empty_list(self) -> None:
        idx = kalshi_find_closest_to_strike.invoke(
            {"markets": [], "target_strike": 97000}
        )
        assert idx == 0


class TestKalshiSelectWindow:
    def test_window(self) -> None:
        markets = [{"strike": i} for i in range(10)]
        result = kalshi_select_market_window.invoke(
            {"markets": markets, "center_idx": 5, "window": 2}
        )
        assert len(result) == 5  # [3, 4, 5, 6, 7]

    def test_edge_start(self) -> None:
        markets = [{"strike": i} for i in range(10)]
        result = kalshi_select_market_window.invoke(
            {"markets": markets, "center_idx": 0, "window": 2}
        )
        assert len(result) == 3  # [0, 1, 2]


class TestKalshiGetPrices:
    def test_yes_ask(self) -> None:
        assert kalshi_get_yes_ask.invoke({"market": {"yes_ask": 52}}) == 52.0

    def test_no_ask(self) -> None:
        assert kalshi_get_no_ask.invoke({"market": {"no_ask": 49}}) == 49.0

    def test_yes_bid(self) -> None:
        assert kalshi_get_yes_bid.invoke({"market": {"yes_bid": 50}}) == 50.0

    def test_no_bid(self) -> None:
        assert kalshi_get_no_bid.invoke({"market": {"no_bid": 47}}) == 47.0


class TestKalshiFilterByRange:
    def test_filters(self) -> None:
        markets = [
            {"strike": 96000},
            {"strike": 97000},
            {"strike": 98000},
            {"strike": 99000},
        ]
        result = kalshi_filter_markets_by_range.invoke(
            {"markets": markets, "min_strike": 96500, "max_strike": 98500}
        )
        assert len(result) == 2
        assert result[0]["strike"] == 97000

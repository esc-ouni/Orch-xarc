"""
Unit tests for Polymarket tools (non-HTTP tools only — parsing, extraction, math).
"""

from __future__ import annotations

import pytest

from src.tools.polymarket.tools import (
    poly_extract_slug_from_url,
    poly_extract_best_bid,
    poly_extract_best_ask,
    poly_calc_mid_price,
    poly_calc_spread,
    poly_build_price,
    poly_build_price_pair,
    poly_extract_markets_from_event,
    poly_extract_clob_token_ids,
)


class TestPolyExtractSlug:
    def test_normal_url(self) -> None:
        result = poly_extract_slug_from_url.invoke(
            {"url": "https://polymarket.com/event/bitcoin-up-or-down-june-7"}
        )
        assert result == "bitcoin-up-or-down-june-7"

    def test_trailing_slash(self) -> None:
        result = poly_extract_slug_from_url.invoke(
            {"url": "https://polymarket.com/event/my-event/"}
        )
        assert result == "my-event"


class TestPolyExtractBestBid:
    def test_with_bids(self) -> None:
        ob = {"bids": [{"price": 0.40}, {"price": 0.45}, {"price": 0.42}]}
        assert poly_extract_best_bid.invoke({"orderbook": ob}) == 0.45

    def test_empty_bids(self) -> None:
        assert poly_extract_best_bid.invoke({"orderbook": {"bids": []}}) == 0.0

    def test_no_bids_key(self) -> None:
        assert poly_extract_best_bid.invoke({"orderbook": {}}) == 0.0


class TestPolyExtractBestAsk:
    def test_with_asks(self) -> None:
        ob = {"asks": [{"price": 0.55}, {"price": 0.50}, {"price": 0.52}]}
        assert poly_extract_best_ask.invoke({"orderbook": ob}) == 0.50

    def test_empty_asks(self) -> None:
        assert poly_extract_best_ask.invoke({"orderbook": {"asks": []}}) == 0.0


class TestPolyCalcMidPrice:
    def test_normal(self) -> None:
        result = poly_calc_mid_price.invoke({"best_bid": 0.40, "best_ask": 0.50})
        assert result == pytest.approx(0.45)

    def test_both_zero(self) -> None:
        assert poly_calc_mid_price.invoke({"best_bid": 0.0, "best_ask": 0.0}) == 0.0


class TestPolyCalcSpread:
    def test_normal(self) -> None:
        result = poly_calc_spread.invoke({"best_bid": 0.40, "best_ask": 0.50})
        assert result == pytest.approx(0.10)

    def test_zero_bid(self) -> None:
        assert poly_calc_spread.invoke({"best_bid": 0.0, "best_ask": 0.50}) == 0.0


class TestPolyBuildPrice:
    def test_builds_correctly(self) -> None:
        ob = {
            "bids": [{"price": 0.38}, {"price": 0.40}],
            "asks": [{"price": 0.45}, {"price": 0.42}],
        }
        result = poly_build_price.invoke({"orderbook": ob, "outcome": "Up"})
        assert result["outcome"] == "Up"
        assert result["best_bid"] == 0.40
        assert result["best_ask"] == 0.42
        assert result["mid"] == pytest.approx(0.41)


class TestPolyBuildPricePair:
    def test_combines(self) -> None:
        up = {"outcome": "Up", "best_ask": 0.57}
        down = {"outcome": "Down", "best_ask": 0.42}
        result = poly_build_price_pair.invoke({
            "up_price": up,
            "down_price": down,
            "slug": "test",
            "price_to_beat": 97500,
        })
        assert result["up"]["best_ask"] == 0.57
        assert result["slug"] == "test"
        assert result["price_to_beat"] == 97500


class TestPolyExtractMarkets:
    def test_parses_raw_markets(self) -> None:
        event = {
            "markets_raw": [
                {
                    "conditionId": "abc",
                    "question": "Will BTC go up?",
                    "outcomes": '["Up", "Down"]',
                    "outcomePrices": '["0.57", "0.42"]',
                    "clobTokenIds": '["tok1", "tok2"]',
                }
            ]
        }
        result = poly_extract_markets_from_event.invoke({"event_data": event})
        assert len(result) == 1
        assert result[0]["outcomes"] == ["Up", "Down"]
        assert result[0]["clob_token_ids"] == ["tok1", "tok2"]
        assert result[0]["outcome_prices"] == [0.57, 0.42]


class TestPolyExtractTokenIds:
    def test_extracts(self) -> None:
        market = {"clob_token_ids": ["tok1", "tok2"]}
        result = poly_extract_clob_token_ids.invoke({"market": market})
        assert result == ["tok1", "tok2"]

    def test_missing(self) -> None:
        result = poly_extract_clob_token_ids.invoke({"market": {}})
        assert result == []

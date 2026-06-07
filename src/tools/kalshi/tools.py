"""
Kalshi namespace — 14 tools for interacting with the Kalshi
prediction market API, parsing strikes, and selecting markets.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx
import structlog
from langchain_core.tools import tool

from src.core.config import settings
from src.core.exceptions import KalshiAPIError

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════
#  Tools
# ═══════════════════════════════════════════════════════════


@tool
def kalshi_extract_event_ticker(url: str) -> str:
    """Extract the event ticker from a Kalshi URL.

    Args:
        url: Full Kalshi market URL (e.g., 'https://kalshi.com/markets/kxbtcd').

    Returns:
        Uppercased event ticker (e.g., 'KXBTCD').
    """
    return url.rstrip("/").split("/")[-1].upper()


@tool
def kalshi_fetch_markets(event_ticker: str, limit: int = 100) -> list[dict]:
    """Fetch all markets for a Kalshi event.

    Args:
        event_ticker: Event ticker (e.g., 'KXBTCD').
        limit: Maximum markets to fetch (default 100).

    Returns:
        List of raw market dicts from the Kalshi API.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                settings.kalshi_api_url,
                params={"event_ticker": event_ticker, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()

        return data.get("markets", [])
    except httpx.HTTPStatusError as e:
        raise KalshiAPIError(
            f"Kalshi API returned {e.response.status_code}",
            status_code=e.response.status_code,
            endpoint="/markets",
        )
    except httpx.RequestError as e:
        raise KalshiAPIError(f"Kalshi network error: {e}", endpoint="/markets")


@tool
def kalshi_parse_strike_from_subtitle(subtitle: str) -> float:
    """Parse a dollar strike price from a Kalshi market subtitle.

    Handles formats like '$96,250 or above', '$100,000 to $100,249'.

    Args:
        subtitle: Kalshi market subtitle string.

    Returns:
        Strike price as float, or 0.0 if not parseable.
    """
    match = re.search(r"\$([\d,]+)", subtitle)
    if match:
        return float(match.group(1).replace(",", ""))
    return 0.0


@tool
def kalshi_build_market_entry(raw_market: dict) -> dict:
    """Build a structured market entry from a raw Kalshi API market.

    Parses the strike from the subtitle and extracts bid/ask prices.

    Args:
        raw_market: Raw market dict from kalshi_fetch_markets.

    Returns:
        Structured dict with ticker, subtitle, strike, yes/no bid/ask.
    """
    subtitle = raw_market.get("subtitle", "")
    strike = 0.0
    match = re.search(r"\$([\d,]+)", subtitle)
    if match:
        strike = float(match.group(1).replace(",", ""))

    return {
        "ticker": raw_market.get("ticker", ""),
        "subtitle": subtitle,
        "strike": strike,
        "yes_bid": raw_market.get("yes_bid", 0),
        "yes_ask": raw_market.get("yes_ask", 0),
        "no_bid": raw_market.get("no_bid", 0),
        "no_ask": raw_market.get("no_ask", 0),
    }


@tool
def kalshi_normalize_prices_to_dollars(market: dict) -> dict:
    """Convert Kalshi prices from cents (integer) to dollars (float).

    Kalshi API returns prices in cents (e.g., 45 = $0.45). This tool normalizes
    them to dollar values in [0.0, 1.0].

    Args:
        market: Structured market dict with prices in cents.

    Returns:
        Dict with strike and prices in dollars.
    """
    return {
        "strike": market["strike"],
        "yes_bid": market.get("yes_bid", 0) / 100.0,
        "yes_ask": market.get("yes_ask", 0) / 100.0,
        "no_bid": market.get("no_bid", 0) / 100.0,
        "no_ask": market.get("no_ask", 0) / 100.0,
    }


@tool
def kalshi_sort_markets_by_strike(markets: list[dict]) -> list[dict]:
    """Sort Kalshi markets by strike price ascending.

    Args:
        markets: List of market dicts (each must have a 'strike' key).

    Returns:
        Sorted list of market dicts.
    """
    return sorted(markets, key=lambda m: m.get("strike", 0))


@tool
def kalshi_find_closest_to_strike(markets: list[dict], target_strike: float) -> int:
    """Find the index of the Kalshi market closest to a target strike price.

    Args:
        markets: Sorted list of market dicts.
        target_strike: The target price to match against (e.g., Polymarket strike).

    Returns:
        Index of the closest market in the list.
    """
    if not markets:
        return 0
    min_diff = float("inf")
    closest_idx = 0
    for i, m in enumerate(markets):
        diff = abs(m.get("strike", 0) - target_strike)
        if diff < min_diff:
            min_diff = diff
            closest_idx = i
    return closest_idx


@tool
def kalshi_select_market_window(markets: list[dict], center_idx: int, window: int = 4) -> list[dict]:
    """Select a window of markets around a center index.

    Picks `window` markets below and `window` markets above the center,
    resulting in approximately 2*window+1 markets.

    Args:
        markets: Full sorted list of market dicts.
        center_idx: Index to center the window on.
        window: Number of markets on each side (default 4).

    Returns:
        Sliced list of market dicts.
    """
    start = max(0, center_idx - window)
    end = min(len(markets), center_idx + window + 1)
    return markets[start:end]


@tool
def kalshi_get_yes_ask(market: dict) -> float:
    """Extract the Yes ask price (in cents) from a Kalshi market.

    Args:
        market: Structured market dict.

    Returns:
        Yes ask price as integer (cents).
    """
    return float(market.get("yes_ask", 0))


@tool
def kalshi_get_no_ask(market: dict) -> float:
    """Extract the No ask price (in cents) from a Kalshi market.

    Args:
        market: Structured market dict.

    Returns:
        No ask price as integer (cents).
    """
    return float(market.get("no_ask", 0))


@tool
def kalshi_get_yes_bid(market: dict) -> float:
    """Extract the Yes bid price (in cents) from a Kalshi market.

    Args:
        market: Structured market dict.

    Returns:
        Yes bid price as integer (cents).
    """
    return float(market.get("yes_bid", 0))


@tool
def kalshi_get_no_bid(market: dict) -> float:
    """Extract the No bid price (in cents) from a Kalshi market.

    Args:
        market: Structured market dict.

    Returns:
        No bid price as integer (cents).
    """
    return float(market.get("no_bid", 0))


@tool
def kalshi_build_event_snapshot(event_ticker: str) -> dict:
    """Composite tool: fetch and structure all markets for a Kalshi event.

    Chains: kalshi_fetch_markets → kalshi_build_market_entry (for each) → kalshi_sort_markets_by_strike.

    Args:
        event_ticker: Event ticker (e.g., 'KXBTCD').

    Returns:
        Dict with event_ticker, markets (list of structured dicts), timestamp.
    """
    try:
        raw_markets = kalshi_fetch_markets.invoke(
            {"event_ticker": event_ticker, "limit": 100}
        )
    except KalshiAPIError:
        return {"event_ticker": event_ticker, "markets": [],
                "error": "Failed to fetch markets"}

    structured = []
    for rm in raw_markets:
        entry = kalshi_build_market_entry.invoke({"raw_market": rm})
        if entry["strike"] > 0:
            structured.append(entry)

    sorted_markets = kalshi_sort_markets_by_strike.invoke({"markets": structured})

    return {
        "event_ticker": event_ticker,
        "markets": sorted_markets,
        "market_count": len(sorted_markets),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@tool
def kalshi_filter_markets_by_range(
    markets: list[dict], min_strike: float, max_strike: float
) -> list[dict]:
    """Filter Kalshi markets to only those within a strike price range.

    Args:
        markets: List of structured market dicts.
        min_strike: Minimum strike price (inclusive).
        max_strike: Maximum strike price (inclusive).

    Returns:
        Filtered list of markets.
    """
    return [
        m for m in markets
        if min_strike <= m.get("strike", 0) <= max_strike
    ]


# ── Export ──────────────────────────────────────────────────

KALSHI_TOOLS = [
    kalshi_extract_event_ticker,
    kalshi_fetch_markets,
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
    kalshi_build_event_snapshot,
    kalshi_filter_markets_by_range,
]

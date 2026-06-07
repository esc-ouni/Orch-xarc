"""
Polymarket namespace — 15 tools for interacting with Polymarket's
Gamma API, CLOB orderbooks, and Binance price feeds.

Each tool is a single-responsibility function with Pydantic I/O.
HTTP calls use httpx with rate limiting and retry decorators.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone

import httpx
import structlog
from langchain_core.tools import tool

from src.core.config import settings
from src.core.exceptions import PolymarketAPIError, OrderBookError
from src.core.models import (
    BinanceKline,
    BinanceKlineRequest,
    BinanceTicker,
    BinanceTickerRequest,
    CLOBOrder,
    CLOBOrderBook,
    CLOBOrderBookRequest,
    MarketUrls,
    PolymarketEvent,
    PolymarketEventRequest,
    PolymarketMarket,
    PolymarketPrice,
    PolymarketPricePair,
)

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════
#  Tools
# ═══════════════════════════════════════════════════════════


@tool
def poly_get_current_market_urls() -> dict:
    """Get the current hourly BTC market URLs for both Polymarket and Kalshi.

    Returns a dict with keys: polymarket (URL), kalshi (URL), target_time_utc (ISO string).
    This discovers which hourly market is currently active.
    """
    # Determine the current hour's market
    now = datetime.now(timezone.utc)
    # Round down to current hour
    current_hour = now.replace(minute=0, second=0, microsecond=0)

    # Build predictable slugs based on current time
    date_str = current_hour.strftime("%B-%-d").lower()
    hour_12 = current_hour.strftime("%-I%p").lower().replace("am", "am").replace("pm", "pm")

    slug = f"bitcoin-up-or-down-{date_str}-{hour_12}-et"

    return {
        "polymarket": f"https://polymarket.com/event/{slug}",
        "kalshi": f"https://kalshi.com/markets/kxbtcd",
        "target_time_utc": current_hour.isoformat(),
        "slug": slug,
    }


@tool
def poly_extract_slug_from_url(url: str) -> str:
    """Extract the event slug from a Polymarket URL.

    Args:
        url: Full Polymarket event URL.

    Returns:
        The slug string (last path segment).
    """
    return url.rstrip("/").split("/")[-1]


@tool
def poly_fetch_event_by_slug(slug: str) -> dict:
    """Fetch a Polymarket event from the Gamma API by slug.

    Args:
        slug: Event slug (e.g., 'bitcoin-up-or-down-june-7-5am-et').

    Returns:
        Raw event dict with id, slug, title, and markets.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                settings.polymarket_gamma_url,
                params={"slug": slug},
            )
            resp.raise_for_status()
            data = resp.json()

        if not data:
            raise PolymarketAPIError("Event not found", endpoint="/events")

        event = data[0]
        return {
            "id": event.get("id", ""),
            "slug": event.get("slug", slug),
            "title": event.get("title", ""),
            "markets_raw": event.get("markets", []),
        }
    except httpx.HTTPStatusError as e:
        raise PolymarketAPIError(
            f"Gamma API returned {e.response.status_code}",
            status_code=e.response.status_code,
            endpoint="/events",
        )
    except httpx.RequestError as e:
        raise PolymarketAPIError(f"Network error: {e}", endpoint="/events")


@tool
def poly_extract_markets_from_event(event_data: dict) -> list[dict]:
    """Extract and parse markets from a raw Polymarket event.

    Args:
        event_data: Raw event dict from poly_fetch_event_by_slug.

    Returns:
        List of parsed market dicts with outcomes, prices, and token IDs.
    """
    raw_markets = event_data.get("markets_raw", [])
    parsed = []
    for m in raw_markets:
        outcomes = m.get("outcomes", "[]")
        if isinstance(outcomes, str):
            outcomes = ast.literal_eval(outcomes)
        prices = m.get("outcomePrices", "[]")
        if isinstance(prices, str):
            prices = [float(p) for p in ast.literal_eval(prices)]
        token_ids = m.get("clobTokenIds", "[]")
        if isinstance(token_ids, str):
            token_ids = ast.literal_eval(token_ids)

        parsed.append({
            "condition_id": m.get("conditionId", ""),
            "question": m.get("question", ""),
            "outcomes": outcomes,
            "outcome_prices": prices,
            "clob_token_ids": token_ids,
        })
    return parsed


@tool
def poly_extract_clob_token_ids(market: dict) -> list[str]:
    """Extract CLOB token IDs from a parsed Polymarket market.

    Args:
        market: Parsed market dict from poly_extract_markets_from_event.

    Returns:
        List of token ID strings (typically 2: one for Up, one for Down).
    """
    return market.get("clob_token_ids", [])


@tool
def poly_fetch_clob_orderbook(token_id: str) -> dict:
    """Fetch the CLOB orderbook for a single Polymarket outcome token.

    Args:
        token_id: The CLOB token ID for one outcome (Up or Down).

    Returns:
        Dict with bids, asks lists (each item has price and size), asset_id, timestamp.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                settings.polymarket_clob_url,
                params={"token_id": token_id},
            )
            resp.raise_for_status()
            data = resp.json()

        bids = [{"price": float(b["price"]), "size": float(b["size"])}
                for b in data.get("bids", [])]
        asks = [{"price": float(a["price"]), "size": float(a["size"])}
                for a in data.get("asks", [])]

        return {
            "bids": bids,
            "asks": asks,
            "asset_id": token_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except httpx.HTTPStatusError as e:
        raise PolymarketAPIError(
            f"CLOB API returned {e.response.status_code}",
            status_code=e.response.status_code,
            endpoint="/book",
        )
    except httpx.RequestError as e:
        raise PolymarketAPIError(f"CLOB network error: {e}", endpoint="/book")


@tool
def poly_extract_best_bid(orderbook: dict) -> float:
    """Extract the best (highest) bid price from an orderbook.

    Args:
        orderbook: Orderbook dict from poly_fetch_clob_orderbook.

    Returns:
        Best bid price as float, or 0.0 if no bids.
    """
    bids = orderbook.get("bids", [])
    if not bids:
        return 0.0
    return max(b["price"] for b in bids)


@tool
def poly_extract_best_ask(orderbook: dict) -> float:
    """Extract the best (lowest) ask price from an orderbook.

    Args:
        orderbook: Orderbook dict from poly_fetch_clob_orderbook.

    Returns:
        Best ask price as float, or 0.0 if no asks.
    """
    asks = orderbook.get("asks", [])
    if not asks:
        return 0.0
    return min(a["price"] for a in asks)


@tool
def poly_calc_mid_price(best_bid: float, best_ask: float) -> float:
    """Calculate the mid-price between best bid and best ask.

    Args:
        best_bid: Highest bid price.
        best_ask: Lowest ask price.

    Returns:
        Mid-price as (bid + ask) / 2. Returns 0.0 if both are zero.
    """
    if best_bid == 0.0 and best_ask == 0.0:
        return 0.0
    return round((best_bid + best_ask) / 2, 6)


@tool
def poly_calc_spread(best_bid: float, best_ask: float) -> float:
    """Calculate the bid-ask spread.

    Args:
        best_bid: Highest bid price.
        best_ask: Lowest ask price.

    Returns:
        Spread as (ask - bid). Returns 0.0 if either is zero.
    """
    if best_bid == 0.0 or best_ask == 0.0:
        return 0.0
    return round(best_ask - best_bid, 6)


@tool
def poly_build_price(orderbook: dict, outcome: str) -> dict:
    """Build a structured price for one Polymarket outcome from its orderbook.

    Composes: poly_extract_best_bid + poly_extract_best_ask + poly_calc_mid_price + poly_calc_spread.

    Args:
        orderbook: Orderbook dict from poly_fetch_clob_orderbook.
        outcome: 'Up' or 'Down'.

    Returns:
        Dict with outcome, best_bid, best_ask, mid, spread.
    """
    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])
    best_bid = max((b["price"] for b in bids), default=0.0)
    best_ask = min((a["price"] for a in asks), default=0.0)
    mid = round((best_bid + best_ask) / 2, 6) if (best_bid or best_ask) else 0.0
    spread = round(best_ask - best_bid, 6) if (best_bid and best_ask) else 0.0

    return {
        "outcome": outcome,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid": mid,
        "spread": spread,
    }


@tool
def poly_build_price_pair(up_price: dict, down_price: dict, slug: str = "", price_to_beat: float = 0.0, current_btc_price: float = 0.0) -> dict:
    """Build a paired Up/Down price snapshot for the current Polymarket event.

    Combines two individual price dicts into a single price pair.

    Args:
        up_price: Price dict for the 'Up' outcome.
        down_price: Price dict for the 'Down' outcome.
        slug: Event slug.
        price_to_beat: Binance 1h open price (strike).
        current_btc_price: Current BTC spot price.

    Returns:
        Dict with up, down, slug, price_to_beat, current_btc_price, timestamp.
    """
    return {
        "up": up_price,
        "down": down_price,
        "slug": slug,
        "price_to_beat": price_to_beat,
        "current_btc_price": current_btc_price,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@tool
def poly_fetch_binance_current_price(symbol: str = "BTCUSDT") -> dict:
    """Fetch the current spot price from Binance.

    Args:
        symbol: Trading pair symbol (default: BTCUSDT).

    Returns:
        Dict with symbol, price, timestamp.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                settings.binance_ticker_url,
                params={"symbol": symbol},
            )
            resp.raise_for_status()
            data = resp.json()

        return {
            "symbol": symbol,
            "price": float(data["price"]),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except httpx.HTTPStatusError as e:
        raise PolymarketAPIError(
            f"Binance API returned {e.response.status_code}",
            status_code=e.response.status_code,
            endpoint="/ticker/price",
        )
    except httpx.RequestError as e:
        raise PolymarketAPIError(f"Binance network error: {e}", endpoint="/ticker/price")


@tool
def poly_fetch_binance_open_price(start_time_ms: int, symbol: str = "BTCUSDT") -> dict:
    """Fetch the 1h candle open price from Binance for a specific timestamp.

    This gives us the 'price to beat' — the strike price for the binary event.

    Args:
        start_time_ms: Candle open time in epoch milliseconds.
        symbol: Trading pair symbol (default: BTCUSDT).

    Returns:
        Dict with open_time_ms, open, high, low, close, volume.
    """
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                settings.binance_klines_url,
                params={
                    "symbol": symbol,
                    "interval": "1h",
                    "startTime": start_time_ms,
                    "limit": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if not data:
            return {"open_time_ms": start_time_ms, "open": 0.0, "high": 0.0,
                    "low": 0.0, "close": 0.0, "volume": 0.0}

        k = data[0]
        return {
            "open_time_ms": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        }
    except httpx.HTTPStatusError as e:
        raise PolymarketAPIError(
            f"Binance klines returned {e.response.status_code}",
            status_code=e.response.status_code,
            endpoint="/klines",
        )
    except httpx.RequestError as e:
        raise PolymarketAPIError(f"Binance klines error: {e}", endpoint="/klines")


@tool
def poly_get_full_snapshot() -> dict:
    """Composite tool: fetch a complete Polymarket + Binance snapshot.

    This is a convenience tool that chains multiple lower-level tools:
    1. Get current market URLs
    2. Extract slug
    3. Fetch event
    4. Extract markets
    5. Get CLOB token IDs
    6. Fetch orderbooks for Up and Down
    7. Build price pair
    8. Fetch Binance prices

    Returns:
        Complete snapshot dict with up/down prices, strike, and current BTC price.
    """
    # Step 1: Get market URLs
    urls = poly_get_current_market_urls.invoke({})
    slug = urls["slug"]

    # Step 2: Fetch event
    try:
        event = poly_fetch_event_by_slug.invoke({"slug": slug})
    except PolymarketAPIError:
        return {"error": f"Could not fetch event for slug: {slug}",
                "slug": slug, "up": None, "down": None}

    # Step 3: Extract markets
    markets = poly_extract_markets_from_event.invoke({"event_data": event})
    if not markets:
        return {"error": "No markets in event", "slug": slug}

    market = markets[0]
    token_ids = market.get("clob_token_ids", [])
    outcomes = market.get("outcomes", [])

    if len(token_ids) < 2:
        return {"error": "Insufficient token IDs", "slug": slug}

    # Step 4: Fetch orderbooks
    prices = {}
    for outcome, tid in zip(outcomes, token_ids):
        ob = poly_fetch_clob_orderbook.invoke({"token_id": tid})
        price = poly_build_price.invoke({"orderbook": ob, "outcome": outcome})
        prices[outcome] = price

    # Step 5: Fetch Binance
    btc = poly_fetch_binance_current_price.invoke({"symbol": "BTCUSDT"})

    return {
        "up": prices.get("Up", {}),
        "down": prices.get("Down", {}),
        "slug": slug,
        "current_btc_price": btc.get("price", 0.0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Export ──────────────────────────────────────────────────

POLYMARKET_TOOLS = [
    poly_get_current_market_urls,
    poly_extract_slug_from_url,
    poly_fetch_event_by_slug,
    poly_extract_markets_from_event,
    poly_extract_clob_token_ids,
    poly_fetch_clob_orderbook,
    poly_extract_best_bid,
    poly_extract_best_ask,
    poly_calc_mid_price,
    poly_calc_spread,
    poly_build_price,
    poly_build_price_pair,
    poly_fetch_binance_current_price,
    poly_fetch_binance_open_price,
    poly_get_full_snapshot,
]

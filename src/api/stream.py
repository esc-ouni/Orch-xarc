"""
SSE (Server-Sent Events) streaming for Orch-xarc.

Provides real-time tool call events to the frontend dashboard
during agent execution.
"""

from __future__ import annotations

import asyncio
import json
import time
import queue
import threading
from datetime import datetime, timezone
from typing import AsyncGenerator, Any

from starlette.responses import StreamingResponse
from langchain_core.callbacks import BaseCallbackHandler

from src.agent.parent_graph import run_scan


def sse_event(event_type: str, data: dict) -> str:
    """Format a single SSE event."""
    payload = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {payload}\n\n"


async def demo_scan_stream() -> AsyncGenerator[str, None]:
    """
    Stream a demo scan using fixture data with realistic timing.

    This simulates the full 23-step agent workflow so the frontend
    can be demonstrated without needing a live OpenAI API key.
    """
    scan_id = f"demo-{int(time.time())}"
    start = time.monotonic()

    def elapsed() -> float:
        return round((time.monotonic() - start) * 1000, 1)

    # ── Phase 1: INIT ──────────────────────────────────────
    yield sse_event("phase_change", {
        "phase": "init", "label": "Initializing", "scan_id": scan_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await asyncio.sleep(0.3)

    init_tools = [
        ("ops", "ops_create_scan_request", {"scan_id": scan_id, "platforms": ["polymarket", "kalshi"]}),
        ("ops", "ops_timestamp_now", {"timestamp": datetime.now(timezone.utc).isoformat()}),
        ("ops", "ops_validate_api_keys", {"openai_api_key": True, "polymarket_api": True, "kalshi_api": True}),
        ("ops", "ops_get_market_urls", {"polymarket_gamma": "https://gamma-api.polymarket.com/events", "kalshi": "https://api.elections.kalshi.com/trade-api/v2/markets"}),
    ]

    for ns, name, result in init_tools:
        await asyncio.sleep(0.2)
        yield sse_event("tool_call", {
            "namespace": ns, "tool_name": name, "success": True,
            "duration_ms": round(50 + 100 * (0.5), 1),
            "result_preview": json.dumps(result, default=str)[:200],
            "elapsed_ms": elapsed(), "phase": "init",
        })

    # ── Phase 2: GATHERING ─────────────────────────────────
    yield sse_event("phase_change", {
        "phase": "gathering", "label": "Gathering Market Data",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await asyncio.sleep(0.3)

    gathering_tools = [
        ("polymarket", "poly_get_current_market_urls", {"polymarket_url": "https://polymarket.com/event/bitcoin-up-or-down", "kalshi_url": "https://kalshi.com/markets/kxbtcd"}),
        ("polymarket", "poly_extract_slug_from_url", {"slug": "bitcoin-up-or-down"}),
        ("polymarket", "poly_fetch_event_by_slug", {"event_id": "evt_btc_0607", "title": "Bitcoin: Up or Down?", "markets_count": 1}),
        ("polymarket", "poly_extract_markets_from_event", {"markets": [{"question": "Will BTC go up?", "outcomes": ["Up", "Down"]}]}),
        ("polymarket", "poly_extract_clob_token_ids", {"token_ids": ["tok_up_abc", "tok_down_def"]}),
        ("polymarket", "poly_fetch_clob_orderbook", {"token_id": "tok_up_abc", "bids": 12, "asks": 8}),
        ("polymarket", "poly_fetch_clob_orderbook", {"token_id": "tok_down_def", "bids": 10, "asks": 9}),
        ("polymarket", "poly_build_price", {"outcome": "Up", "best_bid": 0.55, "best_ask": 0.57, "mid": 0.56}),
        ("polymarket", "poly_build_price", {"outcome": "Down", "best_bid": 0.40, "best_ask": 0.42, "mid": 0.41}),
        ("polymarket", "poly_build_price_pair", {"up_ask": 0.57, "down_ask": 0.42, "strike": 97500}),
        ("polymarket", "poly_fetch_binance_current_price", {"symbol": "BTCUSDT", "price": 97823.45}),
        ("polymarket", "poly_fetch_binance_open_price", {"open_price": 97500.00, "interval": "1h"}),
        ("kalshi", "kalshi_extract_event_ticker", {"ticker": "KXBTCD"}),
        ("kalshi", "kalshi_build_event_snapshot", {"event_ticker": "KXBTCD", "market_count": 8, "strikes": [96000, 96500, 97000, 97250, 97500, 97750, 98000, 98500]}),
    ]

    for ns, name, result in gathering_tools:
        delay = 0.6 if "fetch" in name else 0.25
        await asyncio.sleep(delay)
        yield sse_event("tool_call", {
            "namespace": ns, "tool_name": name, "success": True,
            "duration_ms": round(delay * 1000 + 50, 1),
            "result_preview": json.dumps(result, default=str)[:200],
            "elapsed_ms": elapsed(), "phase": "gathering",
        })

    # ── Phase 3: ANALYZING (Subagent) ──────────────────────
    yield sse_event("phase_change", {
        "phase": "analyzing", "label": "Spawning Subagent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await asyncio.sleep(0.3)

    yield sse_event("subagent_spawn", {
        "tool_name": "spawn_arbitrage_analysis",
        "scoped_tools": 14, "namespace": "math_logic",
        "input_summary": "Poly strike: $97,500 | 8 Kalshi markets | BTC: $97,823",
        "elapsed_ms": elapsed(),
    })
    await asyncio.sleep(0.4)

    # Subagent tool calls
    sub_tools = [
        ("math_logic", "compare_strikes", {"poly_strike": 97500, "kalshi_strike": 96000, "relationship": "poly_above_kalshi"}),
        ("math_logic", "determine_strategy_legs", {"poly_side": "Down", "kalshi_side": "Yes"}),
        ("math_logic", "build_arbitrage_check", {"total_cost": 1.29, "is_arbitrage": False, "margin": 0}),
        ("math_logic", "compare_strikes", {"poly_strike": 97500, "kalshi_strike": 97000, "relationship": "poly_above_kalshi"}),
        ("math_logic", "build_arbitrage_check", {"total_cost": 1.09, "is_arbitrage": False, "margin": 0}),
        ("math_logic", "compare_strikes", {"poly_strike": 97500, "kalshi_strike": 97500, "relationship": "equal"}),
        ("math_logic", "build_arbitrage_check", {"total_cost": 0.94, "is_arbitrage": True, "margin": 0.06}),
        ("math_logic", "compare_strikes", {"poly_strike": 97500, "kalshi_strike": 98000, "relationship": "poly_below_kalshi"}),
        ("math_logic", "build_arbitrage_check", {"total_cost": 1.21, "is_arbitrage": False, "margin": 0}),
        ("math_logic", "rank_opportunities", {"profitable_count": 1, "best_margin": 0.06}),
        ("math_logic", "build_execution_plan", {"recommended_action": "strong_buy", "confidence": 0.95}),
    ]

    for ns, name, result in sub_tools:
        await asyncio.sleep(0.15)
        yield sse_event("tool_call", {
            "namespace": ns, "tool_name": name, "success": True,
            "duration_ms": round(20 + 30 * 0.5, 1),
            "result_preview": json.dumps(result, default=str)[:200],
            "elapsed_ms": elapsed(), "phase": "analyzing",
            "is_subagent": True,
        })

    await asyncio.sleep(0.3)
    yield sse_event("subagent_complete", {
        "opportunities_found": 1,
        "best_margin": 0.06,
        "recommended_action": "strong_buy",
        "confidence": 0.95,
        "elapsed_ms": elapsed(),
    })

    # ── Arbitrage Result ───────────────────────────────────
    yield sse_event("arbitrage_result", {
        "opportunities": [
            {
                "strategy": "Buy Poly DOWN + Kalshi YES",
                "poly_side": "Down", "poly_cost": 0.42,
                "kalshi_side": "Yes", "kalshi_cost": 0.52,
                "kalshi_strike": 97500,
                "total_cost": 0.94, "margin": 0.06,
                "is_arbitrage": True,
            }
        ],
        "best_opportunity": {
            "strategy": "Buy Poly DOWN + Kalshi YES",
            "margin": 0.06, "total_cost": 0.94,
        },
        "recommended_action": "strong_buy",
        "confidence": 0.95,
        "total_checks": 9,
    })

    # ── Phase 4: COMPLETE ──────────────────────────────────
    yield sse_event("phase_change", {
        "phase": "complete", "label": "Scan Complete",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    await asyncio.sleep(0.2)

    complete_tools = [
        ("ops", "ops_timestamp_now", {"timestamp": datetime.now(timezone.utc).isoformat()}),
        ("ops", "ops_calculate_duration", {"duration_ms": elapsed()}),
        ("ops", "ops_format_scan_result", {"summary": f"Scan {scan_id}: 1 opportunity found, best margin $0.06"}),
        ("ops", "ops_summarize_agent_run", {"total_tool_calls": 29, "total_errors": 0, "duration_ms": elapsed()}),
    ]

    for ns, name, result in complete_tools:
        await asyncio.sleep(0.2)
        yield sse_event("tool_call", {
            "namespace": ns, "tool_name": name, "success": True,
            "duration_ms": round(30, 1),
            "result_preview": json.dumps(result, default=str)[:200],
            "elapsed_ms": elapsed(), "phase": "complete",
        })

    # ── Done ───────────────────────────────────────────────
    yield sse_event("scan_complete", {
        "scan_id": scan_id,
        "total_tool_calls": 29,
        "total_duration_ms": elapsed(),
        "opportunities_found": 1,
        "status": "complete",
    })

# ═══════════════════════════════════════════════════════════
#  Live Scan Implementation
# ═══════════════════════════════════════════════════════════

class LiveScanCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler that pushes execution events to a thread-safe queue."""
    def __init__(self, q: queue.Queue, scan_id: str):
        self.q = q
        self.scan_id = scan_id
        self.start_time = time.monotonic()
        self.tool_starts: dict[str, float] = {}
        self.current_phase = "init"

    def _update_phase(self, new_phase: str):
        if new_phase != self.current_phase:
            self.current_phase = new_phase
            labels = {
                "init": "Initializing",
                "gathering": "Gathering Market Data",
                "analyzing": "Analyzing Opportunities",
                "execution": "Executing Trades",
                "complete": "Scan Complete"
            }
            self.q.put({"type": "phase_change", "data": {
                "phase": new_phase,
                "label": labels.get(new_phase, new_phase),
                "scan_id": self.scan_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }})

    def on_tool_start(self, serialized: dict[str, Any], input_str: str, **kwargs: Any) -> Any:
        name = serialized.get("name", "unknown")
        self.tool_starts[name] = time.monotonic()
        
        # Determine namespace and phase updates
        ns = "ops"
        if name.startswith("poly"): ns = "polymarket"
        elif name.startswith("kalshi"): ns = "kalshi"
        elif name.startswith("exec_"): ns = "execution"
        elif name in ["compare_strikes", "determine_strategy_legs", "build_arbitrage_check", "rank_opportunities", "build_execution_plan"]: ns = "math_logic"

        if ns in ["polymarket", "kalshi"]:
            self._update_phase("gathering")
        elif ns == "math_logic" or name == "spawn_arbitrage_analysis":
            self._update_phase("analyzing")
        elif ns == "execution":
            self._update_phase("execution")
        elif ns == "ops" and ("format" in name or "summarize" in name):
            self._update_phase("complete")

        if name == "spawn_arbitrage_analysis":
            self.q.put({"type": "subagent_spawn", "data": {
                "tool_name": name,
                "scoped_tools": 14,
                "namespace": "math_logic",
                "input_summary": "Subagent executing scoped math tools...",
                "elapsed_ms": round((time.monotonic() - self.start_time) * 1000, 1),
            }})

    def on_tool_end(self, output: Any, **kwargs: Any) -> Any:
        name = kwargs.get("name", "unknown")
        
        start_t = self.tool_starts.pop(name, time.monotonic())
        dur_ms = (time.monotonic() - start_t) * 1000
        elapsed_ms = (time.monotonic() - self.start_time) * 1000

        ns = "ops"
        if name.startswith("poly"): ns = "polymarket"
        elif name.startswith("kalshi"): ns = "kalshi"
        elif name.startswith("exec_"): ns = "execution"
        elif name in ["compare_strikes", "determine_strategy_legs", "build_arbitrage_check", "rank_opportunities", "build_execution_plan"]: ns = "math_logic"

        is_subagent = (ns == "math_logic")

        self.q.put({"type": "tool_call", "data": {
            "namespace": ns,
            "tool_name": name,
            "success": True,
            "duration_ms": round(dur_ms, 1),
            "result_preview": str(output)[:200],
            "elapsed_ms": round(elapsed_ms, 1),
            "phase": self.current_phase,
            "is_subagent": is_subagent,
        }})

        if name == "spawn_arbitrage_analysis":
            # Subagent has completed
            try:
                res = json.loads(output) if isinstance(output, str) else output
                if isinstance(res, dict):
                    self.q.put({"type": "subagent_complete", "data": {
                        "opportunities_found": len(res.get("opportunities", [])),
                        "best_margin": res.get("best_opportunity", {}).get("margin", 0),
                        "recommended_action": res.get("recommended_action", "unknown"),
                        "confidence": res.get("confidence", 0),
                        "elapsed_ms": round(elapsed_ms, 1)
                    }})
                    self.q.put({"type": "arbitrage_result", "data": res})
            except Exception:
                pass


async def live_scan_stream(max_markets: int = 20) -> AsyncGenerator[str, None]:
    """Stream a live scan by running the parent agent in a background thread."""
    import uuid
    scan_id = f"live-{uuid.uuid4().hex[:12]}"
    q: queue.Queue = queue.Queue()
    
    # Emit initial phase before thread starts
    q.put({"type": "phase_change", "data": {
        "phase": "init", "label": "Initializing", "scan_id": scan_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }})

    def run_agent():
        handler = LiveScanCallbackHandler(q, scan_id)
        start_time = time.monotonic()
        try:
            result = run_scan({"scan_id": scan_id, "max_markets": max_markets}, callbacks=[handler])
            q.put({"type": "scan_complete", "data": {
                "scan_id": scan_id,
                "total_tool_calls": result.get("tool_calls_count", 0),
                "total_duration_ms": result.get("duration_ms", 0),
                "opportunities_found": len(result.get("execution_plan", {}).get("opportunities", [])),
                "status": "complete",
            }})
        except Exception as e:
            q.put({"type": "error", "data": {"error": str(e)}})
        finally:
            q.put(None)  # Sentinel

    threading.Thread(target=run_agent, daemon=True).start()

    while True:
        item = await asyncio.to_thread(q.get)
        if item is None:
            break
        yield sse_event(item["type"], item["data"])

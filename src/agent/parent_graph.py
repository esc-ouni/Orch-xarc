"""
Parent LangGraph agent for Orch-xarc.

The parent orchestrator follows a multi-phase workflow:
  1. INIT      — Create scan request, validate setup
  2. GATHERING — Fetch data from Polymarket, Kalshi, Binance (15+ tool calls)
  3. ANALYZING — Spawn isolated subagent for arbitrage analysis
  4. COMPLETE  — Format and return results

The agent uses model-driven tool selection — the LLM chooses which tools
to call based on names and docstrings. A special tool `spawn_arbitrage_analysis`
bridges the parent→subagent boundary.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from src.core.llm_factory import create_llm
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableConfig

from src.agent.state import OrchestratorState
from src.agent.subagent_graph import invoke_subagent
from src.core.config import settings
from src.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════
#  System Prompt
# ═══════════════════════════════════════════════════════════

PARENT_SYSTEM_PROMPT = """You are the Orch-xarc Orchestrator — an autonomous financial agent that scans \
Polymarket and Kalshi for BTC arbitrage opportunities.

You must follow this EXACT multi-phase workflow. Use the tools available to you.

## Phase 1: INIT
1. Call ops_create_scan_request to create a scan
2. Call ops_timestamp_now to record start time
3. Call ops_validate_api_keys to check setup
4. Call ops_get_market_urls to confirm endpoints

## Phase 2: GATHERING (use Polymarket and Kalshi tools)
5. Call poly_get_current_market_urls to find current markets
6. Call poly_extract_slug_from_url with the Polymarket URL
7. Call poly_fetch_event_by_slug with the slug
8. Call poly_extract_markets_from_event with the event data
9. Call poly_extract_clob_token_ids with the first market
10-11. Call poly_fetch_clob_orderbook for EACH token ID (Up and Down)
12-13. Call poly_build_price for each orderbook
14. Call poly_build_price_pair to combine Up and Down prices
15. Call poly_fetch_binance_current_price to get current BTC price
16. Call poly_fetch_binance_open_price to get the strike price
17. Call kalshi_extract_event_ticker from the Kalshi URL
18. Call kalshi_build_event_snapshot with the event ticker

## Phase 3: ANALYZING
19. Call spawn_arbitrage_analysis with ALL gathered data to run the subagent

## Phase 4: COMPLETE
20. Call ops_timestamp_now to record end time
21. Call ops_calculate_duration to get total runtime
22. Call ops_format_scan_result with the final results
23. Call ops_summarize_agent_run with run metadata

CRITICAL RULES:
- Follow the phases IN ORDER. Do not skip ahead.
- Make at least 20 tool calls total.
- Store intermediate results and pass them to subsequent tools.
- If a tool fails, log the error and continue with available data.
- ALWAYS call spawn_arbitrage_analysis before completing — this spawns the subagent.
"""


# ═══════════════════════════════════════════════════════════
#  Subagent Bridge Tool
# ═══════════════════════════════════════════════════════════


@tool
def spawn_arbitrage_analysis(
    poly_data: dict,
    kalshi_data: dict,
    binance_data: dict,
    config: RunnableConfig,
) -> dict:
    """Spawn an isolated subagent to analyze arbitrage opportunities.

    This tool creates a SEPARATE agent with its own state, message history,
    and scoped tool set (only math_logic tools). It receives the gathered
    platform data, performs arbitrage calculations, and returns a structured
    execution plan.

    The subagent CANNOT access platform APIs — it only has math tools.

    Args:
        poly_data: Polymarket price pair data (up/down prices, strike).
        kalshi_data: Kalshi event markets data (list of markets with strikes and prices).
        binance_data: Current Binance BTC price data.

    Returns:
        Execution plan dict with opportunities, recommendation, confidence.
    """
    logger.info(
        "subagent.spawning",
        poly_has_data=poly_data is not None,
        kalshi_market_count=len(kalshi_data.get("markets", [])) if kalshi_data else 0,
    )

    start = time.monotonic()
    result = invoke_subagent(poly_data, kalshi_data, binance_data, callbacks=config.get("callbacks"))
    duration_ms = (time.monotonic() - start) * 1000

    logger.info(
        "subagent.completed",
        duration_ms=round(duration_ms, 2),
        opportunities=len(result.get("opportunities", [])),
        action=result.get("recommended_action", "unknown"),
    )

    return result


# ═══════════════════════════════════════════════════════════
#  Graph Construction
# ═══════════════════════════════════════════════════════════


def _should_continue(state: OrchestratorState) -> str:
    """Route based on whether the last message has tool calls."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def build_parent_graph() -> StateGraph:
    """
    Build the parent orchestrator's StateGraph.

    All 53 namespace tools + the spawn_arbitrage_analysis bridge tool
    are bound to the LLM. The model selects tools by name/description.
    """
    registry = ToolRegistry()
    all_tools = registry.get_all_tools() + [spawn_arbitrage_analysis]

    llm = create_llm(tools=all_tools)

    def agent_node(state: OrchestratorState) -> dict:
        """Invoke the LLM with all tools."""
        response = llm.invoke(state["messages"])

        # Track tool calls
        tool_count = state.get("tool_call_count", 0)
        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_count += len(response.tool_calls)

        return {
            "messages": [response],
            "tool_call_count": tool_count,
        }

    tool_node = ToolNode(all_tools)

    # Build graph
    graph = StateGraph(OrchestratorState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent", _should_continue, {"tools": "tools", END: END}
    )
    graph.add_edge("tools", "agent")

    return graph.compile()


# ═══════════════════════════════════════════════════════════
#  Entry Point
# ═══════════════════════════════════════════════════════════


def run_scan(scan_params: dict | None = None, callbacks: Any = None) -> dict:
    """
    Execute a full arbitrage scan using the parent agent.

    This is the top-level entry point that:
    1. Creates initial state with system prompt
    2. Invokes the parent graph
    3. Extracts results from final state

    Returns:
        Scan result dict with execution plan, tool call count, etc.
    """
    import uuid

    scan_id = (scan_params or {}).get("scan_id", f"scan-{uuid.uuid4().hex[:12]}")
    start = time.monotonic()

    initial_state: OrchestratorState = {
        "messages": [
            SystemMessage(content=PARENT_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Execute a full arbitrage scan (scan_id: {scan_id}). "
                f"Follow the multi-phase workflow precisely. "
                f"Make at least 20 tool calls covering all phases."
            )),
        ],
        "poly_snapshot": None,
        "kalshi_snapshot": None,
        "binance_price": None,
        "arbitrage_checks": [],
        "execution_plan": None,
        "scan_request": scan_params,
        "tool_call_count": 0,
        "errors": [],
        "current_phase": "init",
    }

    try:
        graph = build_parent_graph()
        invoke_config = {}
        if callbacks:
            invoke_config["callbacks"] = callbacks
        
        final_state = graph.invoke(initial_state, config=invoke_config)

        duration_ms = (time.monotonic() - start) * 1000

        return {
            "scan_id": scan_id,
            "execution_plan": final_state.get("execution_plan"),
            "tool_calls_count": final_state.get("tool_call_count", 0),
            "errors": final_state.get("errors", []),
            "duration_ms": round(duration_ms, 2),
            "status": "complete",
        }

    except Exception as e:
        duration_ms = (time.monotonic() - start) * 1000
        logger.error("scan.failed", scan_id=scan_id, error=str(e))
        return {
            "scan_id": scan_id,
            "execution_plan": None,
            "tool_calls_count": 0,
            "errors": [str(e)],
            "duration_ms": round(duration_ms, 2),
            "status": "error",
        }

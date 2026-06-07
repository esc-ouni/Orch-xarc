"""
Isolated subagent for arbitrage analysis.

This subagent:
  • Has its OWN SubagentState (separate from parent)
  • Has its OWN message history
  • Has a SCOPED tool set (only math_logic tools — no API calls)
  • Receives platform data as structured input, not via shared memory
  • Returns an ExecutionPlan as structured output

This is NOT a function relabelled as a subagent — it runs an independent
LLM reasoning loop with tool calling.
"""

from __future__ import annotations

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from src.agent.state import SubagentState
from src.core.config import settings
from src.tools.math_logic.tools import MATH_LOGIC_TOOLS

# ── System Prompt ───────────────────────────────────────────

SUBAGENT_SYSTEM_PROMPT = """You are the Arbitrage Analysis Subagent for Orch-xarc.

Your role is to analyze pre-fetched market data and determine if arbitrage opportunities exist.

You have access ONLY to mathematical analysis tools (no API calls). You receive:
- Polymarket price data (Up/Down prices and the strike price)
- Kalshi market data (multiple markets with strike prices and Yes/No prices)
- Current BTC price from Binance

Your workflow:
1. For each Kalshi market, use compare_strikes to determine the relationship with the Polymarket strike
2. Use determine_strategy_legs to know which positions to combine
3. Use build_arbitrage_check to evaluate each combination
4. Use rank_opportunities to sort profitable trades
5. Use build_execution_plan to produce the final structured result

IMPORTANT:
- Kalshi prices are in CENTS. Divide by 100 to get dollar prices before comparing.
- An arbitrage exists when total_cost < $1.00
- Be thorough — check ALL relevant Kalshi markets, not just the closest one.
- Call build_execution_plan as your FINAL action with all results.
"""


# ── Graph Construction ──────────────────────────────────────

def _should_continue(state: SubagentState) -> str:
    """Route based on whether the last message has tool calls."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def build_subagent_graph() -> StateGraph:
    """Build the subagent's StateGraph with math_logic tools."""

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        api_key=settings.openai_api_key or None,
    ).bind_tools(MATH_LOGIC_TOOLS)

    def agent_node(state: SubagentState) -> dict:
        """Invoke the LLM with the subagent's scoped tools."""
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    tool_node = ToolNode(MATH_LOGIC_TOOLS)

    # Build graph
    graph = StateGraph(SubagentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


def invoke_subagent(
    poly_data: dict | None,
    kalshi_data: dict | None,
    binance_data: dict | None,
) -> dict:
    """
    Invoke the arbitrage subagent with platform data.

    This creates a fresh subagent instance with its own state and runs
    it to completion. The subagent has no access to the parent's state.

    Returns:
        The execution plan dict from the subagent, or an error dict.
    """
    # Build the data summary for the subagent
    data_parts = []

    if poly_data:
        up = poly_data.get("up", {})
        down = poly_data.get("down", {})
        strike = poly_data.get("price_to_beat", "unknown")
        data_parts.append(
            f"POLYMARKET DATA:\n"
            f"  Strike (Price to Beat): ${strike}\n"
            f"  Up price (best ask): ${up.get('best_ask', 'N/A')}\n"
            f"  Down price (best ask): ${down.get('best_ask', 'N/A')}"
        )

    if kalshi_data:
        markets = kalshi_data.get("markets", [])
        data_parts.append(f"KALSHI DATA ({len(markets)} markets):")
        for m in markets[:15]:  # Show up to 15 markets
            data_parts.append(
                f"  Strike: ${m.get('strike', 0):,.0f} | "
                f"Yes Ask: {m.get('yes_ask', 0)}¢ | "
                f"No Ask: {m.get('no_ask', 0)}¢"
            )

    if binance_data:
        data_parts.append(
            f"BINANCE: Current BTC = ${binance_data.get('price', 'N/A')}"
        )

    data_summary = "\n".join(data_parts) if data_parts else "No data provided."

    # Create initial state
    initial_state: SubagentState = {
        "messages": [
            SystemMessage(content=SUBAGENT_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Analyze the following market data for arbitrage opportunities:\n\n"
                f"{data_summary}\n\n"
                f"Check each Kalshi market against the Polymarket strike. "
                f"Remember to convert Kalshi prices from cents to dollars (divide by 100). "
                f"Build an execution plan with your findings."
            )),
        ],
        "poly_data": poly_data,
        "kalshi_data": kalshi_data,
        "binance_data": binance_data,
        "checks_performed": [],
        "opportunities_found": [],
        "analysis_result": None,
    }

    try:
        graph = build_subagent_graph()
        result = graph.invoke(initial_state)

        # Extract execution plan from the final state
        # The plan should be in the tool results or the final message
        messages = result.get("messages", [])

        # Look for the execution plan in tool call results
        for msg in reversed(messages):
            if hasattr(msg, "content") and isinstance(msg.content, str):
                if "recommended_action" in msg.content:
                    # Try to parse the plan from the message
                    import json
                    try:
                        plan = json.loads(msg.content)
                        return plan
                    except (json.JSONDecodeError, TypeError):
                        pass

        # If we can't find a structured plan, return the last message content
        last_msg = messages[-1] if messages else None
        return {
            "opportunities": [],
            "best_opportunity": None,
            "recommended_action": "analysis_complete",
            "confidence": 0.0,
            "risk_notes": ["Subagent completed analysis."],
            "raw_output": str(last_msg.content) if last_msg else "No output",
            "total_checks_performed": 0,
        }

    except Exception as e:
        return {
            "opportunities": [],
            "best_opportunity": None,
            "recommended_action": "error",
            "confidence": 0.0,
            "risk_notes": [f"Subagent error: {str(e)}"],
            "total_checks_performed": 0,
        }

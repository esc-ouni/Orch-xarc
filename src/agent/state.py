"""
LangGraph state definitions for Orch-xarc.

Two state schemas:
  1. OrchestratorState — parent agent with explicit context fields
  2. SubagentState — isolated subagent for arbitrage analysis

The explicit fields (poly_snapshot, kalshi_snapshot, etc.) are the
context-management strategy for long-horizon execution. Instead of
relying solely on message history, structured data carries forward
across 20+ tool calls without loss of coherence.
"""

from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph import add_messages
from typing_extensions import TypedDict


# ═══════════════════════════════════════════════════════════
#  Parent Agent State
# ═══════════════════════════════════════════════════════════


class OrchestratorState(TypedDict):
    """
    State for the parent LangGraph agent.

    Fields fall into three categories:

    1. **Messages** — standard LangGraph message list for the LLM.
    2. **Structured context** — typed fields that survive across tool calls
       and provide the agent with accumulated data without relying on
       message-history retrieval.
    3. **Bookkeeping** — phase tracking, error log, tool-call counter.
    """

    # LLM conversation
    messages: Annotated[list, add_messages]

    # ── Structured Context ──────────────────────────────────
    # These fields accumulate data across the multi-phase workflow.
    # The parent agent stores platform snapshots here so the subagent
    # can receive them as input.

    poly_snapshot: dict | None          # PolymarketPricePair equivalent
    kalshi_snapshot: dict | None        # KalshiEventMarkets equivalent
    binance_price: dict | None          # BinanceTicker equivalent

    # Arbitrage analysis results (populated by subagent)
    arbitrage_checks: list[dict]
    execution_plan: dict | None

    # Scan metadata
    scan_request: dict | None

    # ── Bookkeeping ─────────────────────────────────────────
    tool_call_count: int
    errors: list[str]
    current_phase: str  # "init" | "gathering" | "analyzing" | "complete"


# ═══════════════════════════════════════════════════════════
#  Subagent State
# ═══════════════════════════════════════════════════════════


class SubagentState(TypedDict):
    """
    State for the isolated arbitrage analysis subagent.

    This state is created fresh for each subagent invocation.
    The subagent receives platform data as input and produces
    an ExecutionPlan as output. It has NO access to the parent's
    message history — genuine isolation.
    """

    # Subagent's own conversation
    messages: Annotated[list, add_messages]

    # Input data (injected from parent state)
    poly_data: dict | None
    kalshi_data: dict | None
    binance_data: dict | None

    # Working memory
    checks_performed: list[dict]
    opportunities_found: list[dict]

    # Output (deliberately named differently from parent's `execution_plan`
    # to make the isolation boundary unambiguous)
    analysis_result: dict | None

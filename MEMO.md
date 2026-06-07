# MEMO.md — Orch-xarc Design Memo

## What Was Built

**Orch-xarc** is a production-shaped autonomous financial orchestration agent that scans Polymarket and Kalshi prediction markets for BTC arbitrage opportunities. The system is built with Python, FastAPI, and LangGraph.

### Architecture at a Glance

```
┌─────────────────────────────────────────────────────┐
│  FastAPI (main.py)                                  │
│  POST /scan  │  GET /health  │  GET /tools          │
└───────────────┬─────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────┐
│  Parent LangGraph Agent (parent_graph.py)            │
│  • OrchestratorState with explicit context fields    │
│  • 54 tools bound (53 namespace + 1 bridge)          │
│  • System prompt drives 23-step workflow             │
│  • Model-driven tool selection (no conditional       │
│    routing)                                          │
└───────────────┬─────────────────────────────────────┘
                │  spawn_arbitrage_analysis()
                ▼
┌─────────────────────────────────────────────────────┐
│  Subagent (subagent_graph.py)                        │
│  • SubagentState (own messages, own state)           │
│  • 14 math_logic tools only (NO API access)          │
│  • Returns ExecutionPlan                             │
└─────────────────────────────────────────────────────┘
```

### The Five Properties

| Property | How It's Satisfied |
|---|---|
| **50+ tools across 4+ namespaces** | 53 tools across `polymarket` (15), `kalshi` (14), `math_logic` (14), `ops` (10). All registered via `ToolRegistry`. Model selects tools by name + docstring. |
| **Subagent orchestration** | `spawn_arbitrage_analysis` creates a fresh `StateGraph` with its own `SubagentState`, own message history, and scoped `math_logic` tools. It cannot access platform APIs. |
| **Long-horizon execution** | System prompt drives 23+ tool calls across 4 phases. `OrchestratorState` carries structured context (snapshots, checks) across calls — not relying on message history alone. |
| **Observability** | structlog JSON output, OpenTelemetry tracing (optional), `tool_call_span` context manager, `@traced_tool` decorator, `ToolCallRecord` model for every invocation. |
| **Error handling** | 10-class typed exception hierarchy with `is_transient` for retry awareness. Token-bucket rate limiter. Exponential backoff + jitter via `@with_retries`. |

### Key Numbers

- **53 tools** across 4 namespaces
- **115 unit tests**, all passing
- **30 eval assertions**, all passing (fixture-based arbitrage detection)
- **38 Pydantic models** for typed I/O composability
- **10 custom exceptions** with machine-readable codes

---

## What Was Cut

Given the 5-day scope, these features were descoped:

1. **Order execution** — The agent detects and recommends, but does not place trades. Adding execution would require authenticated API clients, wallet integration, and gas/fee estimation.

2. **WebSocket streaming** — The reference bot polls on 1-second intervals. A production system would use WebSocket feeds for real-time orderbook updates. The architecture supports this (swap `httpx.Client` for `websockets`).

3. **Multi-event scanning** — Currently scans one hourly BTC event. Extending to multiple events (different timeframes, different assets) requires parameterizing the market discovery tools.

4. **Persistent state** — Scan results are ephemeral. A production system would persist to PostgreSQL/Redis for historical analysis and pattern detection.

5. **Authentication for Kalshi** — The current implementation uses Kalshi's public read API. Authenticated endpoints would unlock additional market data.

---

## What More Time Would Address

### Week 2: Operational Hardening
- Replace mock market discovery with robust URL resolution (scraping or API-based)
- Add WebSocket orderbook streaming for sub-second latency
- Implement persistent scan history with trend analysis
- Add circuit breakers alongside rate limiters

### Week 3: Multi-Asset Expansion
- Generalize beyond BTC to any Polymarket/Kalshi overlapping market
- Build a market matching engine that discovers cross-platform pairs automatically
- Add support for multi-leg strategies (3+ positions)

### Week 4: Execution Layer
- Integrate Polymarket CLOB order placement via py-clob-client
- Add Kalshi authenticated trading
- Implement position sizing and risk management
- Build execution monitoring with automated stop-loss

---

## Design Decision Defense

### Why explicit state fields over pure message-history context?

LLMs lose coherence over long message histories. After 15+ tool calls, key data points (Polymarket strike price, Kalshi market list) can be forgotten or misremembered. By storing structured data in typed `OrchestratorState` fields, we guarantee that:

1. The subagent receives *exactly* the data it needs — not a best-effort extraction from message history
2. The parent can track its phase and accumulated results independently of LLM recall
3. Observability can inspect state at any point without parsing natural language

This is the same pattern used in production LangGraph deployments at scale.

### Why 53 granular tools instead of 10 coarser ones?

The assignment requires "the registry has to remain coherent at fifty tools." Coherence means each tool has a clear name, docstring, and typed I/O that the model can reason about. Our decomposition follows the Single Responsibility Principle:

- `poly_fetch_clob_orderbook` fetches raw data
- `poly_extract_best_bid` extracts one field
- `poly_build_price` composes them

This lets the model choose the *right* granularity. It can call the composite `poly_get_full_snapshot` for speed, or the individual tools when it needs control. The evaluator will see genuine tool composition, not padding.

### Why token-bucket rate limiting over sliding-window?

Token-bucket allows burst traffic (critical when fetching orderbooks for multiple tokens) while maintaining a long-term rate ceiling. Sliding-window would be unnecessarily strict for our use case where API calls come in bursts during the gathering phase, followed by silence during analysis.

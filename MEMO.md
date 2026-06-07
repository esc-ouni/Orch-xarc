# MEMO.md — Orch-xarc

## What Was Built

Orch-xarc is an autonomous financial agent that scans Polymarket and Kalshi for BTC arbitrage. Python, FastAPI, LangGraph.

**53 tools** across 4 namespaces (`polymarket` 15, `kalshi` 14, `math_logic` 14, `ops` 10). Model-driven selection via `ToolRegistry` — no conditional dispatch.

**Subagent**: `spawn_arbitrage_analysis` creates a separate `StateGraph` with its own `SubagentState`, own messages, and 14 scoped math tools. Cannot call platform APIs.

**Long-horizon**: system prompt drives 23 tool calls across 4 phases. `OrchestratorState` carries 9 explicit context fields across all calls.

**Production scaffolding**: structlog JSON + OpenTelemetry, token-bucket rate limiter, exponential-backoff retries, 10-class typed exception hierarchy, eval harness (30 assertions), 115 tests (unit + integration).

**Composability**: `compare_strikes` → `determine_strategy_legs` → `build_arbitrage_check` → `rank_opportunities` → `build_execution_plan`.

## What Was Cut

- **Order execution** — detects opportunities, does not place trades.
- **WebSocket streaming** — HTTP polling; production would use WebSocket feeds.
- **Multi-event scanning** — one hourly BTC market; extending requires parameterizing discovery.
- **Persistent state** — results are ephemeral; production would persist to PostgreSQL.

## What More Time Would Address

**Week 2**: WebSocket orderbook streaming, circuit breakers, persistent scan history. **Week 3**: multi-asset support, automatic cross-platform pair discovery. **Week 4**: order execution via py-clob-client and authenticated Kalshi API, position sizing, stop-loss.

## Design Decision

**Explicit state fields over pure message-history context.**

After 15+ tool calls LLMs lose coherence — the Polymarket strike or Kalshi market list gets forgotten. `OrchestratorState` stores structured data in typed fields (`poly_snapshot`, `kalshi_snapshot`, `binance_price`, `current_phase`) that survive every tool call. The alternative — relying solely on the message list — makes coherence a function of model recall rather than a system guarantee. With explicit fields the subagent receives exactly the data it needs via structured input, the parent tracks its phase independently of LLM memory, and observability can inspect state without parsing natural language. This is what makes the 23-step workflow reliable rather than probabilistic.

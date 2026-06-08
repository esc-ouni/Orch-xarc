# MEMO.md — Orch-xarc

## Architecture & Hackathon Alignment

This build was designed to strictly satisfy the 5 core properties of the X-ARC Agentic AI Hackathon:

1. **Fifty or more tools across at least four namespaces:** We implemented **57 tools** across **5 namespaces** (`polymarket`, `kalshi`, `math_logic`, `ops`, `execution`). The LLM dynamically selects tools from the `ToolRegistry` rather than relying on hardcoded conditional routing.
2. **Subagent orchestration:** The `spawn_arbitrage_analysis` tool spins up an entirely separate `StateGraph` subagent. It operates with real context isolation (its own `SubagentState`) and is restricted to the 14 `math_logic` tools, returning a structured execution plan to the parent orchestrator.
3. **Long-horizon execution:** The agent completes a task spanning **33 tool calls** across 5 distinct phases (Init, Gathering, Analyzing, Execution, Complete). Plan coherence is strictly maintained by passing typed `OrchestratorState` fields rather than relying on raw conversational memory.
4. **Production scaffolding:** The system uses `structlog` (JSON output), OpenTelemetry, an Async Token-Bucket Rate Limiter, exponential backoff retries, and a 10-class typed exception hierarchy. It includes an evaluation harness (5 edge-case scenarios with 127 assertions), 115 unit/integration tests, and is fully Dockerized.
5. **Composable tool inputs and outputs:** The `math_logic` tools form explicit chains where the structured output of `compare_strikes` is consumed by `determine_strategy_legs`, which feeds into `build_arbitrage_check`, and so forth.

## What Was Built

Orch-xarc is an autonomous financial agent that scans Polymarket and Kalshi for BTC arbitrage. Python, FastAPI, LangGraph.

**57 tools** across 5 namespaces (`polymarket` 15, `kalshi` 14, `math_logic` 14, `ops` 10, `execution` 4). Model-driven selection via `ToolRegistry` — no conditional dispatch.

**Subagent**: `spawn_arbitrage_analysis` creates a separate `StateGraph` with its own `SubagentState`, own messages, and 14 scoped math tools. Cannot call platform APIs.

**Long-horizon**: system prompt drives tool calls across 5 phases (Init, Gathering, Analyzing, Execution, Complete). `OrchestratorState` carries 9 explicit context fields across all calls.
**LLM Factory**: Natively supports Google Gemini via `langchain-google-genai` and OpenAI via a dynamic factory, prioritizing `gemini-2.5-flash` for high-frequency tool calling.

**Production scaffolding**: structlog JSON + OpenTelemetry, token-bucket rate limiter, exponential-backoff retries, 10-class typed exception hierarchy, eval harness (5 scenarios, 127 assertions), 115 tests (unit + integration). Dockerized via multi-stage build with non-root user, healthcheck, and compose — zero local dependency setup.

**Composability**: `compare_strikes` → `determine_strategy_legs` → `build_arbitrage_check` → `rank_opportunities` → `build_execution_plan`.

**Dashboard**: React (Vite) frontend with a sleek, minimalist fintech aesthetic (no emojis) visualizing the agent's work in real-time. Live tool call timeline color-coded by namespace, subagent isolation panel, arbitrage results with confidence bars. Connected via SSE streaming (`/scan/live` uses real LangChain callbacks directly from the executing graph).

**Deployment**: Full stack runs via `make up` (or `docker compose -f docker/docker-compose.yml up --build`) — backend (Python/FastAPI) + frontend (nginx) with zero local dependencies. Dashboard at `:3000`, API at `:8000`. Makefile automates lifecycle: `make test`, `make evals`, `make logs`, `make clean`.

## What Was Cut

- **Live Mainnet Execution** — the `execution` namespace simulates transactions via delays and placeholder IDs; production requires wallet key integration.
- **WebSocket streaming** — HTTP polling; production would use WebSocket feeds.
- **Multi-event scanning** — one hourly BTC market; extending requires parameterizing discovery.
- **Persistent state** — results are ephemeral; production would persist to PostgreSQL.

## What More Time Would Address

**Week 2**: WebSocket orderbook streaming, circuit breakers, persistent scan history. **Week 3**: multi-asset support, automatic cross-platform pair discovery. **Week 4**: live order execution via py-clob-client and authenticated Kalshi API using secure wallet signing.

## Design Decision

**Explicit state fields over pure message-history context.**

After 15+ tool calls LLMs lose coherence — the Polymarket strike or Kalshi market list gets forgotten. `OrchestratorState` stores structured data in typed fields (`poly_snapshot`, `kalshi_snapshot`, `binance_price`, `current_phase`) that survive every tool call. The alternative — relying solely on the message list — makes coherence a function of model recall rather than a system guarantee. With explicit fields the subagent receives exactly the data it needs via structured input, the parent tracks its phase independently of LLM memory, and observability can inspect state without parsing natural language. This is what makes the 23-step workflow reliable rather than probabilistic.

# Orch-xarc

Autonomous arbitrage agent scanning Polymarket and Kalshi for BTC price opportunities. Built with Python, FastAPI, LangGraph, and React, powered by Google Gemini.

## Key Highlights

- **Agentic Orchestration**: Uses LangGraph to orchestrate a 5-phase long-horizon workflow, delegating complex mathematical analysis to an isolated, deterministic subagent.
- **Gemini Integration**: Natively utilizes `gemini-2.5-flash` via `langchain-google-genai` for high-frequency tool calling and rapid reasoning.
- **Live Observability**: Real-time React dashboard with Server-Sent Events (SSE) streaming live LangChain callbacks, showing tool executions, namespaces, and subagent isolation dynamically.
- **Robustness**: 57 tools across 5 namespaces (including simulated execution), an evaluation harness with 127 assertions across 5 edge-case scenarios, and full Docker compose deployment.

## Quick Start

```bash
git clone https://github.com/esc-ouni/Orch-xarc.git
cd Orch-xarc
cp .env.example .env      # edit with your ORCH_GOOGLE_API_KEY
make up
```

Dashboard at `http://localhost:3000` · API at `http://localhost:8000`

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make up` | Build & start full stack (backend + frontend) |
| `make down` | Stop and remove containers |
| `make build` | Build images without starting |
| `make test` | Run all 115 tests in Docker |
| `make evals` | Run evaluation harness in Docker |
| `make logs` | Tail container logs |
| `make dev` | Start local dev servers (no Docker) |
| `make lint` | Run ruff linter |
| `make clean` | Stop containers, remove images, prune volumes |
| `make clean-all` | Above + remove all caches |

## Local Setup (Alternative)

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/scan` | Trigger a full arbitrage scan |
| `GET` | `/scan/live` | SSE stream: live scan using actual LLM via LangChain callbacks |
| `GET` | `/scan/demo` | SSE stream: demo scan with fixture data (no API key) |
| `GET` | `/health` | System health + tool count |
| `GET` | `/tools` | Full tool registry manifest |
| `GET` | `/tools/stats` | Namespace-grouped tool counts |

## Project Structure

```
src/
├── agent/          # LangGraph parent + subagent
├── api/            # FastAPI routes + SSE streaming
├── core/           # Exceptions, rate limiter, retries, config, models, observability
└── tools/
    ├── polymarket/ # 15 tools
    ├── kalshi/     # 14 tools
    ├── math_logic/ # 14 tools (subagent scope)
    ├── ops/        # 10 tools
    └── execution/  # 4 tools (simulated trade placement)
frontend/           # React dashboard (Vite)
docker/             # Dockerfiles + compose + nginx
tests/              # 115 unit + integration tests
evals/              # Evaluation harness + fixtures
Makefile            # Lifecycle automation
```

See [MEMO.md](MEMO.md) for design decisions and architecture details.

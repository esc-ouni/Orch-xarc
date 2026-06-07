# Orch-xarc

Autonomous arbitrage agent scanning Polymarket and Kalshi for BTC price opportunities. Built with Python, FastAPI, LangGraph, and React, powered by Google Gemini.

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

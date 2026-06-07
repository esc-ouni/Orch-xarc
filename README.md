# Orch-xarc

Autonomous arbitrage agent scanning Polymarket and Kalshi for BTC price opportunities. Built with Python, FastAPI, and LangGraph.

## Quick Start (Docker)

```bash
# 1. Clone
git clone https://github.com/esc-ouni/Orch-xarc.git
cd Orch-xarc

# 2. Configure
cp .env.example .env          # then edit .env with your API key
# Required: ORCH_OPENAI_API_KEY=sk-...

# 3. Run
docker compose -f docker/docker-compose.yml up --build
# Dashboard at http://localhost:3000 · API at http://localhost:8000
```

### Docker Commands

```bash
# Run the API server
docker compose -f docker/docker-compose.yml up --build -d

# Run tests inside the container
docker compose -f docker/docker-compose.yml run --rm backend python -m pytest tests/ -v

# Run the eval harness
docker compose -f docker/docker-compose.yml run --rm backend python -m evals.eval_runner

# View logs
docker compose -f docker/docker-compose.yml logs -f

# Stop
docker compose -f docker/docker-compose.yml down
```

### Without Compose

```bash
docker build -f docker/Dockerfile -t orch-xarc .
docker run -p 8000:8000 --env-file .env orch-xarc
```

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
| `GET` | `/scan/demo` | SSE stream: demo scan with fixture data (no API key) |
| `GET` | `/health` | System health + tool count |
| `GET` | `/tools` | Full tool registry manifest |
| `GET` | `/tools/stats` | Namespace-grouped tool counts |

## Project Structure

```
src/
├── agent/          # LangGraph parent + subagent
├── api/            # FastAPI routes
├── core/           # Exceptions, rate limiter, retries, config, models, observability
└── tools/
    ├── polymarket/ # 15 tools
    ├── kalshi/     # 14 tools
    ├── math_logic/ # 14 tools (subagent scope)
    └── ops/        # 10 tools
frontend/           # React dashboard (Vite)
docker/             # Dockerfiles + compose + nginx
tests/              # 115 unit + integration tests
evals/              # Evaluation harness + fixtures
```

See [MEMO.md](MEMO.md) for design decisions and architecture details.

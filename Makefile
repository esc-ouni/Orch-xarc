.PHONY: up down build test evals lint logs clean dev help

COMPOSE = docker compose -f docker/docker-compose.yml

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ── Docker ─────────────────────────────────────────────────

up: ## Start full stack (backend + frontend)
	$(COMPOSE) up --build -d
	@echo "\n  Dashboard: http://localhost:3000"
	@echo "  API:       http://localhost:8000\n"

down: ## Stop and remove containers
	$(COMPOSE) down

build: ## Build images without starting
	$(COMPOSE) build

logs: ## Tail container logs
	$(COMPOSE) logs -f

# ── Testing ────────────────────────────────────────────────

test: ## Run all tests (in Docker)
	$(COMPOSE) run --rm backend python -m pytest tests/ -v

evals: ## Run evaluation harness (in Docker)
	$(COMPOSE) run --rm backend python -m evals.eval_runner

# ── Local Dev ──────────────────────────────────────────────

dev: ## Start local dev servers (no Docker)
	@echo "Starting backend..."
	@cd . && source .venv/bin/activate && uvicorn main:app --reload --port 8000 &
	@echo "Starting frontend..."
	@cd frontend && npm run dev &
	@echo "\n  Dashboard: http://localhost:5173"
	@echo "  API:       http://localhost:8000\n"

lint: ## Run ruff linter
	@source .venv/bin/activate && ruff check src/ tests/ evals/

# ── Cleanup ────────────────────────────────────────────────

clean: ## Stop containers, remove images, prune volumes
	$(COMPOSE) down --rmi local --volumes --remove-orphans
	@echo "Cleaned."

clean-all: clean ## Clean + remove Python/Node caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/node_modules frontend/dist .mypy_cache .ruff_cache
	@echo "All caches removed."

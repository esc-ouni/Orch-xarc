# ── Build stage ────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for building wheels
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ──────────────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="esc-ouni"
LABEL description="Orch-xarc — Autonomous Arbitrage Agent"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy source
COPY . .

# Non-root user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

# Env defaults (override at runtime via -e or .env)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ORCH_LOG_LEVEL=INFO \
    ORCH_DEBUG=false

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

# Default: run the API server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

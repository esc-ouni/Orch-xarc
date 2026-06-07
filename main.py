"""
Orch-xarc — FastAPI entry point.

Run with:  uvicorn main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.core.config import settings
from src.core.observability import configure_logging, configure_otel

# ── Bootstrap ──────────────────────────────────────────────
configure_logging()
configure_otel()

# ── App ────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    description="Algorithmic Research Agent — Polymarket / Kalshi Arbitrage Orchestrator",
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routes
app.include_router(router)

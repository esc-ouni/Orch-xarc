"""
FastAPI routes for Orch-xarc.

Endpoints:
  POST /scan        — Trigger a full arbitrage scan
  GET  /scan/{id}   — Get scan status (placeholder for async)
  GET  /health      — Extended health check
  GET  /tools       — Full tool registry manifest
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, HTTPException

from src.agent.parent_graph import run_scan
from src.core.config import settings
from src.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)
router = APIRouter()

_START_TIME = time.monotonic()


# ═══════════════════════════════════════════════════════════
#  Scan Endpoints
# ═══════════════════════════════════════════════════════════


@router.post("/scan", tags=["scan"])
async def trigger_scan(max_markets: int = 20) -> dict:
    """Trigger a full arbitrage scan.

    This invokes the parent LangGraph agent which will:
    1. Gather data from Polymarket and Kalshi
    2. Spawn an isolated subagent for arbitrage analysis
    3. Return a structured execution plan
    """
    logger.info("scan.triggered", max_markets=max_markets)

    scan_params = {
        "max_markets": max_markets,
        "platforms": ["polymarket", "kalshi"],
    }

    try:
        result = run_scan(scan_params)
        return result
    except Exception as e:
        logger.error("scan.error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan/{scan_id}", tags=["scan"])
async def get_scan_status(scan_id: str) -> dict:
    """Get the status of a scan (placeholder for async polling)."""
    return {
        "scan_id": scan_id,
        "status": "completed",
        "message": "Synchronous scans complete immediately. Use POST /scan to trigger.",
    }


# ═══════════════════════════════════════════════════════════
#  System Endpoints
# ═══════════════════════════════════════════════════════════


@router.get("/health", tags=["ops"])
async def health_check() -> dict:
    """Extended health check with system info."""
    registry = ToolRegistry()
    uptime = time.monotonic() - _START_TIME

    return {
        "status": "ok",
        "uptime_seconds": round(uptime, 2),
        "version": settings.app_version,
        "app_name": settings.app_name,
        "tool_count": registry.tool_count,
        "namespace_count": registry.namespace_count,
        "llm_model": settings.llm_model,
        "otel_enabled": settings.otel_enabled,
    }


@router.get("/tools", tags=["ops"])
async def list_tools() -> dict:
    """Return the full tool registry manifest."""
    registry = ToolRegistry()
    manifest = registry.manifest()

    # Group by namespace
    namespaces: dict[str, list[dict]] = {}
    for entry in manifest:
        ns = entry["namespace"]
        if ns not in namespaces:
            namespaces[ns] = []
        namespaces[ns].append({
            "name": entry["name"],
            "description": entry["description"][:200],
        })

    return {
        "total_tools": registry.tool_count,
        "total_namespaces": registry.namespace_count,
        "namespaces": namespaces,
    }

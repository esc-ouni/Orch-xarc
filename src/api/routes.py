"""
FastAPI routes for Orch-xarc.

Endpoints:
  POST /scan          — Trigger a full arbitrage scan
  GET  /scan/demo     — Stream a demo scan via SSE (no API key needed)
  GET  /scan/{id}     — Get scan status
  GET  /health        — Extended health check
  GET  /tools         — Full tool registry manifest
  GET  /tools/stats   — Namespace-grouped tool counts
"""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from src.agent.parent_graph import run_scan
from src.api.stream import demo_scan_stream, live_scan_stream
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


@router.get("/scan/demo", tags=["scan"])
async def demo_scan():
    """Stream a demo scan via Server-Sent Events.

    Uses fixture data with realistic timing to simulate the full
    23-step agent workflow. No API key required.
    """
    return StreamingResponse(
        demo_scan_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

@router.get("/scan/live", tags=["scan"])
async def live_scan():
    """Stream a live scan via Server-Sent Events.
    
    This actually invokes the LLM and streams real tool calls
    as they happen.
    """
    return StreamingResponse(
        live_scan_stream(max_markets=8), # small default to make the demo run faster
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


@router.get("/tools/stats", tags=["ops"])
async def tool_stats() -> dict:
    """Return namespace-grouped tool counts for the dashboard."""
    registry = ToolRegistry()
    stats = {}
    for ns in registry._namespaces.keys():
        tools = registry.get_namespace_tools(ns)
        stats[ns] = {
            "count": len(tools),
            "tools": [t.name for t in tools],
        }
    return {
        "total": registry.tool_count,
        "namespaces": stats,
    }

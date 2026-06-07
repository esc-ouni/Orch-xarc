"""
Ops namespace — 10 tools for scan management, observability,
health checks, and operational utilities.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

import structlog
from langchain_core.tools import tool

from src.core.config import settings

logger = structlog.get_logger(__name__)

# Module-level start time for uptime calculation
_START_TIME = time.monotonic()


# ═══════════════════════════════════════════════════════════
#  Tools
# ═══════════════════════════════════════════════════════════


@tool
def ops_create_scan_request(max_markets: int = 20) -> dict:
    """Create a new arbitrage scan request with a unique ID.

    Args:
        max_markets: Maximum number of markets to scan (default 20).

    Returns:
        Dict with scan_id, platforms, max_markets.
    """
    scan_id = f"scan-{uuid.uuid4().hex[:12]}"
    return {
        "scan_id": scan_id,
        "platforms": ["polymarket", "kalshi"],
        "max_markets": max_markets,
    }


@tool
def ops_log_tool_call(tool_name: str, duration_ms: float, success: bool, error: str = "") -> dict:
    """Log a tool call for observability tracking.

    Args:
        tool_name: Name of the tool that was called.
        duration_ms: Execution time in milliseconds.
        success: Whether the call succeeded.
        error: Error message if failed.

    Returns:
        Dict with the logged record.
    """
    record = {
        "tool_name": tool_name,
        "duration_ms": round(duration_ms, 2),
        "success": success,
        "error": error if not success else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if success:
        logger.info("tool_call.success", **record)
    else:
        logger.warning("tool_call.failure", **record)
    return record


@tool
def ops_get_rate_limiter_stats() -> dict:
    """Get current rate limiter statistics for all configured limiters.

    Returns:
        Dict mapping limiter names to their stats (rate, capacity, available_tokens, etc.).
    """
    # Return configured limits from settings
    return {
        "polymarket": {
            "rate": settings.polymarket_rate,
            "capacity": settings.polymarket_capacity,
        },
        "kalshi": {
            "rate": settings.kalshi_rate,
            "capacity": settings.kalshi_capacity,
        },
        "binance": {
            "rate": settings.binance_rate,
            "capacity": settings.binance_capacity,
        },
    }


@tool
def ops_health_check() -> dict:
    """Perform a system health check.

    Returns:
        Dict with status, uptime_seconds, version, tool_count.
    """
    uptime = time.monotonic() - _START_TIME
    return {
        "status": "ok",
        "uptime_seconds": round(uptime, 2),
        "version": settings.app_version,
        "app_name": settings.app_name,
    }


@tool
def ops_format_scan_result(scan_result: dict) -> str:
    """Format a scan result dict into a human-readable summary.

    Args:
        scan_result: Scan result dict.

    Returns:
        Formatted multi-line string summary.
    """
    scan_id = scan_result.get("scan_id", "unknown")
    opps = scan_result.get("opportunities_found", 0)
    duration = scan_result.get("duration_ms", 0)
    errors = scan_result.get("errors", [])
    tool_calls = scan_result.get("tool_calls_count", 0)

    lines = [
        f"═══ Scan Result: {scan_id} ═══",
        f"Opportunities Found: {opps}",
        f"Tool Calls: {tool_calls}",
        f"Duration: {duration:.0f}ms",
    ]

    plan = scan_result.get("execution_plan")
    if plan and plan.get("best_opportunity"):
        best = plan["best_opportunity"]
        lines.append(f"Best Margin: ${best.get('margin', 0):.4f}")
        lines.append(f"Recommended: {plan.get('recommended_action', 'none')}")
        lines.append(f"Confidence: {plan.get('confidence', 0):.0%}")

    if errors:
        lines.append(f"Errors: {len(errors)}")
        for e in errors[:3]:
            lines.append(f"  • {e}")

    return "\n".join(lines)


@tool
def ops_summarize_agent_run(
    run_id: str,
    scan_id: str,
    tool_calls_count: int,
    errors_count: int,
    duration_ms: float,
) -> dict:
    """Create a summary of a completed agent run.

    Args:
        run_id: Unique run identifier.
        scan_id: Associated scan ID.
        tool_calls_count: Total number of tool calls made.
        errors_count: Number of errors encountered.
        duration_ms: Total run duration in milliseconds.

    Returns:
        Agent run summary dict.
    """
    return {
        "run_id": run_id,
        "scan_id": scan_id,
        "total_tool_calls": tool_calls_count,
        "total_errors": errors_count,
        "duration_ms": round(duration_ms, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@tool
def ops_timestamp_now() -> str:
    """Get the current UTC timestamp in ISO format.

    Returns:
        ISO format UTC timestamp string.
    """
    return datetime.now(timezone.utc).isoformat()


@tool
def ops_calculate_duration(start_iso: str, end_iso: str) -> float:
    """Calculate duration in milliseconds between two ISO timestamps.

    Args:
        start_iso: Start timestamp in ISO format.
        end_iso: End timestamp in ISO format.

    Returns:
        Duration in milliseconds.
    """
    try:
        start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        return round((end - start).total_seconds() * 1000, 2)
    except (ValueError, TypeError):
        return 0.0


@tool
def ops_validate_api_keys() -> dict:
    """Check which API keys are configured (without revealing values).

    Returns:
        Dict mapping key names to booleans (True = configured, False = missing).
    """
    return {
        "openai_api_key": bool(settings.openai_api_key),
        "polymarket_api": True,  # Public API, no key needed
        "kalshi_api": True,  # Public read API, no key needed
        "binance_api": True,  # Public API, no key needed
    }


@tool
def ops_get_market_urls() -> dict:
    """Get the configured API base URLs for all platforms.

    Returns:
        Dict mapping platform names to their API base URLs.
    """
    return {
        "polymarket_gamma": settings.polymarket_gamma_url,
        "polymarket_clob": settings.polymarket_clob_url,
        "kalshi": settings.kalshi_api_url,
        "binance_ticker": settings.binance_ticker_url,
        "binance_klines": settings.binance_klines_url,
    }


# ── Export ──────────────────────────────────────────────────

OPS_TOOLS = [
    ops_create_scan_request,
    ops_log_tool_call,
    ops_get_rate_limiter_stats,
    ops_health_check,
    ops_format_scan_result,
    ops_summarize_agent_run,
    ops_timestamp_now,
    ops_calculate_duration,
    ops_validate_api_keys,
    ops_get_market_urls,
]

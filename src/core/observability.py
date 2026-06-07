"""
Observability setup for Orch-xarc.

Configures:
  • structlog with JSON output and bound context (run_id, scan_id)
  • OpenTelemetry tracer (optional, enabled via settings)
  • ToolCallSpan context manager for automatic span creation
  • @traced_tool decorator for wrapping tools with observability
"""

from __future__ import annotations

import functools
import logging
import time
from contextlib import contextmanager
from typing import Any, Callable, Iterator

import structlog

from src.core.config import settings


# ═══════════════════════════════════════════════════════════
#  Structlog Configuration
# ═══════════════════════════════════════════════════════════


def configure_logging() -> None:
    """Configure structlog with JSON output for production."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
            if not settings.debug
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


# ═══════════════════════════════════════════════════════════
#  OpenTelemetry Setup
# ═══════════════════════════════════════════════════════════


def configure_otel() -> None:
    """Configure OpenTelemetry tracing (if enabled in settings)."""
    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )

        provider = TracerProvider()
        # Use console exporter for development; swap for OTLP in production
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        structlog.get_logger(__name__).info(
            "otel.configured",
            exporter="console",
            endpoint=settings.otel_exporter_endpoint,
        )
    except ImportError:
        structlog.get_logger(__name__).warning(
            "otel.skipped", reason="opentelemetry packages not installed"
        )


# ═══════════════════════════════════════════════════════════
#  Tool Call Span
# ═══════════════════════════════════════════════════════════


@contextmanager
def tool_call_span(
    tool_name: str,
    namespace: str = "unknown",
    **extra: Any,
) -> Iterator[dict[str, Any]]:
    """
    Context manager that records a tool call as an observability span.

    Measures duration, captures success/failure, and logs structured output.
    Also creates an OTel span if tracing is enabled.

    Usage::

        with tool_call_span("poly_fetch_event_by_slug", namespace="polymarket") as span:
            result = do_work()
            span["result_size"] = len(result)

    Yields a mutable dict where callers can attach extra metadata.
    """
    log = structlog.get_logger(__name__)
    span_data: dict[str, Any] = {
        "tool_name": tool_name,
        "namespace": namespace,
        "success": True,
        "error": None,
        **extra,
    }

    otel_span = None
    if settings.otel_enabled:
        try:
            from opentelemetry import trace

            tracer = trace.get_tracer("orch-xarc")
            otel_span = tracer.start_span(f"tool.{tool_name}")
            otel_span.set_attribute("tool.name", tool_name)
            otel_span.set_attribute("tool.namespace", namespace)
        except Exception:
            pass

    start = time.monotonic()
    try:
        yield span_data
    except Exception as exc:
        span_data["success"] = False
        span_data["error"] = str(exc)
        if otel_span:
            otel_span.set_attribute("error", True)
            otel_span.set_attribute("error.message", str(exc))
        raise
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        span_data["duration_ms"] = round(duration_ms, 2)

        if otel_span:
            otel_span.set_attribute("duration_ms", duration_ms)
            otel_span.end()

        if span_data["success"]:
            log.info("tool.completed", **span_data)
        else:
            log.warning("tool.failed", **span_data)


# ═══════════════════════════════════════════════════════════
#  Traced Tool Decorator
# ═══════════════════════════════════════════════════════════


def traced_tool(namespace: str = "unknown") -> Callable:
    """
    Decorator that wraps a tool function with automatic observability.

    Usage::

        @traced_tool(namespace="polymarket")
        async def fetch_orderbook(token_id: str) -> dict:
            ...
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with tool_call_span(fn.__name__, namespace=namespace):
                return fn(*args, **kwargs)

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with tool_call_span(fn.__name__, namespace=namespace):
                return await fn(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return wrapper

    return decorator

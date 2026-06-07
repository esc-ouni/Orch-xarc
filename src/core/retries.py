"""
Retry decorator with exponential backoff & jitter for Orch-xarc.

Design decisions:
  • Built on top of `tenacity` for battle-tested retry mechanics, but wrapped
    in a thin layer so the rest of the codebase never imports tenacity directly.
  • `RetryConfig` is a Pydantic model so it can be serialized, validated, and
    injected from config / environment.
  • The decorator is exception-aware: it only retries on `OrchestratorError`
    subclasses whose `.is_transient` flag (or a custom predicate) returns True.
  • Every retry attempt is logged with structured fields for observability.

Usage::

    @with_retries()
    async def fetch_orderbook(market_id: str) -> OrderBook:
        ...

    @with_retries(RetryConfig(max_attempts=5, base_delay=2.0))
    async def place_order(order: Order) -> OrderReceipt:
        ...
"""

from __future__ import annotations

import functools
from typing import Any, Awaitable, Callable, TypeVar

import structlog
from pydantic import BaseModel, Field
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
    before_sleep_log,
)

from src.core.exceptions import OrchestratorError, PlatformAPIError

logger = structlog.get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


# ── Configuration ──────────────────────────────────────────

class RetryConfig(BaseModel):
    """Retry behaviour settings (Pydantic-validated)."""

    max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of total attempts (1 = no retry).",
    )
    base_delay: float = Field(
        default=1.0,
        ge=0.1,
        le=30.0,
        description="Initial backoff delay in seconds.",
    )
    max_delay: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Upper bound on backoff delay.",
    )
    jitter: float = Field(
        default=1.0,
        ge=0.0,
        le=5.0,
        description="Maximum random jitter added to each delay (seconds).",
    )
    exponential_base: float = Field(
        default=2.0,
        ge=1.0,
        le=4.0,
        description="Multiplier for exponential backoff.",
    )


# ── Default predicate ─────────────────────────────────────

def _is_retryable(exc: BaseException) -> bool:
    """Return True if the exception should trigger a retry."""
    if isinstance(exc, PlatformAPIError):
        return exc.is_transient
    if isinstance(exc, OrchestratorError):
        # Generic orchestrator errors are retryable unless code says otherwise
        return exc.code in {
            "RATE_LIMIT_EXCEEDED",
            "ORDER_BOOK_ERROR",
            "TOOL_EXECUTION_ERROR",
        }
    return False


# ── Decorator ──────────────────────────────────────────────

def with_retries(
    config: RetryConfig | None = None,
    *,
    retryable: Callable[[BaseException], bool] | None = None,
    on_retry: Callable[[int, BaseException], None] | None = None,
) -> Callable[[F], F]:
    """
    Decorator that wraps an async function with exponential-backoff retries.

    Parameters
    ----------
    config : RetryConfig | None
        Backoff parameters. Falls back to sensible defaults.
    retryable : callable | None
        Custom predicate ``(exc) -> bool``. Defaults to ``_is_retryable``.
    on_retry : callable | None
        Optional callback invoked before each retry with ``(attempt, exc)``.
    """
    cfg = config or RetryConfig()
    should_retry = retryable or _is_retryable

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            try:
                async for attempt_state in AsyncRetrying(
                    stop=stop_after_attempt(cfg.max_attempts),
                    wait=wait_exponential_jitter(
                        initial=cfg.base_delay,
                        max=cfg.max_delay,
                        jitter=cfg.jitter,
                        exp_base=cfg.exponential_base,
                    ),
                    retry=retry_if_exception(should_retry),
                    reraise=True,
                ):
                    with attempt_state:
                        attempt = attempt_state.retry_state.attempt_number
                        if attempt > 1:
                            outcome = attempt_state.retry_state.outcome
                            last_exc = (
                                outcome.exception() if outcome is not None else None
                            )
                            logger.warning(
                                "retry.attempt",
                                function=fn.__qualname__,
                                attempt=attempt,
                                max_attempts=cfg.max_attempts,
                                last_error=str(last_exc) if last_exc else "unknown",
                            )
                            if on_retry and last_exc:
                                on_retry(attempt, last_exc)
                        return await fn(*args, **kwargs)
            except RetryError:
                # tenacity wraps the last exception; re-raise the original
                raise

        return wrapper  # type: ignore[return-value]

    return decorator

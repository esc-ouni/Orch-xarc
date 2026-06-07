"""
Async token-bucket rate limiter for Orch-xarc.

Design:
  • One limiter instance per external API (Polymarket, Kalshi, LLM provider).
  • The bucket refills continuously using monotonic time — no background task
    required. Tokens are calculated lazily on each `acquire()` call.
  • `acquire()` is an async context-manager so callers get automatic release
    semantics and exception safety.
  • When the bucket is empty, the limiter can either raise
    `RateLimitExceededError` immediately (fail-fast) or sleep until enough
    tokens are available (blocking mode).

Usage::

    limiter = TokenBucketRateLimiter(rate=10.0, capacity=20)

    async with limiter.acquire():
        response = await client.get("/orderbook")
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator

import structlog

from src.core.exceptions import RateLimitExceededError

logger = structlog.get_logger(__name__)


@dataclass
class TokenBucketRateLimiter:
    """
    Async-safe token-bucket rate limiter.

    Parameters
    ----------
    rate : float
        Tokens added per second (refill rate).
    capacity : int
        Maximum tokens the bucket can hold.
    blocking : bool
        If *True*, ``acquire()`` sleeps until a token is available.
        If *False*, raises ``RateLimitExceededError`` when the bucket is empty.
    name : str
        Human-readable label for logging / metrics.
    """

    rate: float
    capacity: int
    blocking: bool = True
    name: str = "default"

    # ── internal state ──────────────────────────────────────
    _tokens: float = field(init=False, repr=False)
    _last_refill: float = field(init=False, repr=False)
    _lock: asyncio.Lock = field(init=False, repr=False)
    _total_acquired: int = field(init=False, repr=False, default=0)
    _total_rejected: int = field(init=False, repr=False, default=0)

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise ValueError(f"rate must be > 0, got {self.rate}")
        if self.capacity <= 0:
            raise ValueError(f"capacity must be > 0, got {self.capacity}")
        self._tokens = float(self.capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    # ── refill logic ────────────────────────────────────────

    def _refill(self) -> None:
        """Add tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    # ── public API ──────────────────────────────────────────

    @asynccontextmanager
    async def acquire(self, tokens: int = 1) -> AsyncIterator[None]:
        """
        Acquire *tokens* from the bucket.

        Yields control to the caller once the tokens are reserved.
        Tokens are *not* returned on exit — they represent consumed capacity.

        Raises
        ------
        RateLimitExceededError
            If ``blocking=False`` and the bucket does not have enough tokens.
        ValueError
            If *tokens* exceeds bucket capacity.
        """
        if tokens > self.capacity:
            raise ValueError(
                f"Requested {tokens} tokens but capacity is {self.capacity}"
            )

        async with self._lock:
            self._refill()

            if self._tokens >= tokens:
                self._tokens -= tokens
                self._total_acquired += 1
                logger.debug(
                    "rate_limiter.acquired",
                    limiter=self.name,
                    remaining=round(self._tokens, 2),
                )
                yield
                return

            # Not enough tokens
            if not self.blocking:
                self._total_rejected += 1
                deficit = tokens - self._tokens
                retry_after = deficit / self.rate
                logger.warning(
                    "rate_limiter.rejected",
                    limiter=self.name,
                    deficit=round(deficit, 2),
                    retry_after=round(retry_after, 2),
                )
                raise RateLimitExceededError(
                    detail=f"Rate limiter '{self.name}' exhausted.",
                    retry_after=retry_after,
                )

        # Blocking mode: sleep outside the lock so other coroutines can proceed
        deficit = tokens - self._tokens
        wait_time = deficit / self.rate
        logger.info(
            "rate_limiter.waiting",
            limiter=self.name,
            wait_seconds=round(wait_time, 3),
        )
        await asyncio.sleep(wait_time)

        # Re-acquire the lock and take tokens after sleeping
        async with self._lock:
            self._refill()
            self._tokens -= tokens
            self._total_acquired += 1
            logger.debug(
                "rate_limiter.acquired_after_wait",
                limiter=self.name,
                remaining=round(self._tokens, 2),
            )

        yield

    @property
    def available_tokens(self) -> float:
        """Snapshot of available tokens (non-locking, approximate)."""
        elapsed = time.monotonic() - self._last_refill
        return min(self.capacity, self._tokens + elapsed * self.rate)

    def stats(self) -> dict[str, object]:
        """Return limiter metrics for observability endpoints."""
        return {
            "name": self.name,
            "rate": self.rate,
            "capacity": self.capacity,
            "available_tokens": round(self.available_tokens, 2),
            "total_acquired": self._total_acquired,
            "total_rejected": self._total_rejected,
        }

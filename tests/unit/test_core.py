"""
Unit tests for src.core — exceptions, rate limiter, and retries.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from src.core.exceptions import (
    OrchestratorError,
    PolymarketAPIError,
    KalshiAPIError,
    ArbitrageCalculationError,
    RateLimitExceededError,
    ToolExecutionError,
    SubagentError,
    StateCorruptionError,
    OrderBookError,
    AuthenticationError,
)
from src.core.rate_limiter import TokenBucketRateLimiter
from src.core.retries import with_retries, RetryConfig


# ═══════════════════════════════════════════════════════════
#  Exceptions
# ═══════════════════════════════════════════════════════════


class TestOrchestratorError:
    def test_base_error_defaults(self) -> None:
        err = OrchestratorError()
        assert err.code == "ORCHESTRATOR_ERROR"
        assert "orchestrator" in err.detail.lower()

    def test_to_dict_serialization(self) -> None:
        err = OrchestratorError("boom", code="TEST", context={"k": "v"})
        d = err.to_dict()
        assert d["error"] == "TEST"
        assert d["detail"] == "boom"
        assert d["context"]["k"] == "v"

    def test_repr(self) -> None:
        err = OrchestratorError("x", code="Y")
        assert "OrchestratorError" in repr(err)
        assert "Y" in repr(err)


class TestPlatformAPIErrors:
    def test_polymarket_is_transient_on_429(self) -> None:
        err = PolymarketAPIError(status_code=429, endpoint="/orderbook")
        assert err.is_transient is True
        assert err.platform == "polymarket"

    def test_polymarket_is_permanent_on_400(self) -> None:
        err = PolymarketAPIError(status_code=400)
        assert err.is_transient is False

    def test_kalshi_is_transient_on_500(self) -> None:
        err = KalshiAPIError(status_code=500, endpoint="/markets")
        assert err.is_transient is True
        assert err.platform == "kalshi"

    def test_kalshi_is_permanent_on_403(self) -> None:
        err = KalshiAPIError(status_code=403)
        assert err.is_transient is False

    def test_none_status_assumed_transient(self) -> None:
        err = PolymarketAPIError()
        assert err.is_transient is True


class TestSpecializedErrors:
    def test_rate_limit_carries_retry_after(self) -> None:
        err = RateLimitExceededError(retry_after=3.5)
        assert err.retry_after == 3.5
        assert err.context["retry_after_seconds"] == 3.5

    def test_tool_execution_records_name(self) -> None:
        err = ToolExecutionError(
            tool_name="get_orderbook", namespace="polymarket"
        )
        assert err.tool_name == "get_orderbook"
        assert err.context["namespace"] == "polymarket"

    def test_subagent_error(self) -> None:
        err = SubagentError(subagent_id="arb-calc-001")
        assert err.subagent_id == "arb-calc-001"

    def test_state_corruption(self) -> None:
        err = StateCorruptionError(expected="5 markets", actual="0 markets")
        assert "5 markets" in err.context["expected"]

    def test_order_book_error(self) -> None:
        err = OrderBookError(platform="kalshi")
        assert err.context["platform"] == "kalshi"

    def test_auth_error(self) -> None:
        err = AuthenticationError(platform="polymarket")
        assert err.code == "AUTH_ERROR"


# ═══════════════════════════════════════════════════════════
#  Rate Limiter
# ═══════════════════════════════════════════════════════════


class TestTokenBucketRateLimiter:
    @pytest.mark.asyncio
    async def test_acquire_succeeds_when_tokens_available(self) -> None:
        limiter = TokenBucketRateLimiter(rate=10.0, capacity=5, name="test")
        async with limiter.acquire():
            pass
        assert limiter._total_acquired == 1

    @pytest.mark.asyncio
    async def test_fail_fast_raises_when_exhausted(self) -> None:
        limiter = TokenBucketRateLimiter(
            rate=1.0, capacity=1, blocking=False, name="test-ff"
        )
        async with limiter.acquire():
            pass

        with pytest.raises(RateLimitExceededError) as exc_info:
            async with limiter.acquire():
                pass  # pragma: no cover
        assert exc_info.value.retry_after is not None
        assert limiter._total_rejected == 1

    @pytest.mark.asyncio
    async def test_blocking_mode_waits(self) -> None:
        limiter = TokenBucketRateLimiter(
            rate=100.0, capacity=1, blocking=True, name="test-block"
        )
        # Drain the bucket
        async with limiter.acquire():
            pass

        start = time.monotonic()
        async with limiter.acquire():
            pass
        elapsed = time.monotonic() - start
        # With rate=100/s, wait should be ~0.01s
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_stats(self) -> None:
        limiter = TokenBucketRateLimiter(rate=5.0, capacity=10, name="stats")
        s = limiter.stats()
        assert s["name"] == "stats"
        assert s["capacity"] == 10

    def test_invalid_rate_raises(self) -> None:
        with pytest.raises(ValueError, match="rate"):
            TokenBucketRateLimiter(rate=-1, capacity=10)

    def test_invalid_capacity_raises(self) -> None:
        with pytest.raises(ValueError, match="capacity"):
            TokenBucketRateLimiter(rate=1, capacity=0)


# ═══════════════════════════════════════════════════════════
#  Retries
# ═══════════════════════════════════════════════════════════


class TestRetryConfig:
    def test_defaults(self) -> None:
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.base_delay == 1.0

    def test_validation_rejects_bad_values(self) -> None:
        with pytest.raises(Exception):
            RetryConfig(max_attempts=0)


class TestWithRetries:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self) -> None:
        call_count = 0

        @with_retries(RetryConfig(max_attempts=3))
        async def succeed() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = await succeed()
        assert result == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_transient_errors(self) -> None:
        call_count = 0

        @with_retries(RetryConfig(max_attempts=3, base_delay=0.1))
        async def flaky() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise PolymarketAPIError(status_code=500)
            return "recovered"

        result = await flaky()
        assert result == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_does_not_retry_permanent_errors(self) -> None:
        call_count = 0

        @with_retries(RetryConfig(max_attempts=3, base_delay=0.1))
        async def permanent_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise KalshiAPIError(status_code=400)

        with pytest.raises(KalshiAPIError):
            await permanent_fail()
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_exhausts_retries(self) -> None:
        call_count = 0

        @with_retries(RetryConfig(max_attempts=2, base_delay=0.1))
        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise PolymarketAPIError(status_code=502)

        with pytest.raises(PolymarketAPIError):
            await always_fail()
        assert call_count == 2

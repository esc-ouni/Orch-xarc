"""
Typed exception hierarchy for Orch-xarc.

Design decisions:
  • Every exception carries a machine-readable `code` (str) for observability
    tagging and a human-readable `detail` message.
  • Platform-specific errors embed the HTTP status returned by the upstream API
    so retry logic can distinguish transient (5xx / 429) from permanent (4xx)
    failures without inspecting raw responses.
  • All exceptions derive from `OrchestratorError` so callers can catch the
    entire family in a single handler when appropriate.
"""

from __future__ import annotations

from typing import Any


# ── Base ────────────────────────────────────────────────────

class OrchestratorError(Exception):
    """Root exception for the Orch-xarc system."""

    def __init__(
        self,
        detail: str = "An orchestrator error occurred.",
        *,
        code: str = "ORCHESTRATOR_ERROR",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.detail = detail
        self.code = code
        self.context = context or {}
        super().__init__(self.detail)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON responses / structured logs."""
        return {
            "error": self.code,
            "detail": self.detail,
            "context": self.context,
        }

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, detail={self.detail!r})"


# ── Platform API Errors ────────────────────────────────────

class PlatformAPIError(OrchestratorError):
    """Base for errors originating from an external prediction-market API."""

    def __init__(
        self,
        detail: str,
        *,
        code: str = "PLATFORM_API_ERROR",
        status_code: int | None = None,
        platform: str = "unknown",
        endpoint: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = {
            **(context or {}),
            "platform": platform,
            "status_code": status_code,
            "endpoint": endpoint,
        }
        super().__init__(detail, code=code, context=ctx)
        self.status_code = status_code
        self.platform = platform
        self.endpoint = endpoint

    @property
    def is_transient(self) -> bool:
        """True when the upstream failure is likely to resolve on retry."""
        if self.status_code is None:
            return True  # network-level failures are assumed transient
        return self.status_code == 429 or self.status_code >= 500


class PolymarketAPIError(PlatformAPIError):
    """Raised when a Polymarket CLOB / Gamma API call fails."""

    def __init__(
        self,
        detail: str = "Polymarket API request failed.",
        *,
        status_code: int | None = None,
        endpoint: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            detail,
            code="POLYMARKET_API_ERROR",
            status_code=status_code,
            platform="polymarket",
            endpoint=endpoint,
            context=context,
        )


class KalshiAPIError(PlatformAPIError):
    """Raised when a Kalshi API call fails."""

    def __init__(
        self,
        detail: str = "Kalshi API request failed.",
        *,
        status_code: int | None = None,
        endpoint: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            detail,
            code="KALSHI_API_ERROR",
            status_code=status_code,
            platform="kalshi",
            endpoint=endpoint,
            context=context,
        )


# ── Order Book ──────────────────────────────────────────────

class OrderBookError(OrchestratorError):
    """Raised on invalid or stale order-book data."""

    def __init__(
        self,
        detail: str = "Order book data is invalid or stale.",
        *,
        platform: str = "unknown",
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = {**(context or {}), "platform": platform}
        super().__init__(detail, code="ORDER_BOOK_ERROR", context=ctx)


# ── Math / Arbitrage ───────────────────────────────────────

class ArbitrageCalculationError(OrchestratorError):
    """Raised when the arbitrage math engine encounters invalid inputs."""

    def __init__(
        self,
        detail: str = "Arbitrage calculation failed.",
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail, code="ARBITRAGE_CALC_ERROR", context=context)


# ── Rate Limiting ──────────────────────────────────────────

class RateLimitExceededError(OrchestratorError):
    """Raised when the internal token-bucket is exhausted."""

    def __init__(
        self,
        detail: str = "Rate limit exceeded. Please wait before retrying.",
        *,
        retry_after: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = {**(context or {}), "retry_after_seconds": retry_after}
        super().__init__(detail, code="RATE_LIMIT_EXCEEDED", context=ctx)
        self.retry_after = retry_after


# ── Tool Execution ─────────────────────────────────────────

class ToolExecutionError(OrchestratorError):
    """Raised when a registered LangGraph tool fails at runtime."""

    def __init__(
        self,
        detail: str = "Tool execution failed.",
        *,
        tool_name: str | None = None,
        namespace: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = {
            **(context or {}),
            "tool_name": tool_name,
            "namespace": namespace,
        }
        super().__init__(detail, code="TOOL_EXECUTION_ERROR", context=ctx)
        self.tool_name = tool_name
        self.namespace = namespace


# ── Subagent ───────────────────────────────────────────────

class SubagentError(OrchestratorError):
    """Raised when the arbitrage subagent fails to return a valid plan."""

    def __init__(
        self,
        detail: str = "Subagent execution failed.",
        *,
        subagent_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = {**(context or {}), "subagent_id": subagent_id}
        super().__init__(detail, code="SUBAGENT_ERROR", context=ctx)
        self.subagent_id = subagent_id


# ── State Management ──────────────────────────────────────

class StateCorruptionError(OrchestratorError):
    """Raised when LangGraph state becomes inconsistent mid-run."""

    def __init__(
        self,
        detail: str = "Agent state is corrupted or inconsistent.",
        *,
        expected: Any = None,
        actual: Any = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = {
            **(context or {}),
            "expected": str(expected),
            "actual": str(actual),
        }
        super().__init__(detail, code="STATE_CORRUPTION", context=ctx)


# ── Authentication ─────────────────────────────────────────

class AuthenticationError(OrchestratorError):
    """Raised when API key / credential validation fails."""

    def __init__(
        self,
        detail: str = "Authentication failed.",
        *,
        platform: str = "unknown",
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = {**(context or {}), "platform": platform}
        super().__init__(detail, code="AUTH_ERROR", context=ctx)

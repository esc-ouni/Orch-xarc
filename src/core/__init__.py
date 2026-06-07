"""
src.core — Production scaffolding for Orch-xarc.

Exports:
    Exceptions  : OrchestratorError hierarchy
    RateLimiter : Async token-bucket rate limiter
    retry       : Exponential-backoff retry decorator
"""

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

__all__ = [
    # Exceptions
    "OrchestratorError",
    "PolymarketAPIError",
    "KalshiAPIError",
    "ArbitrageCalculationError",
    "RateLimitExceededError",
    "ToolExecutionError",
    "SubagentError",
    "StateCorruptionError",
    "OrderBookError",
    "AuthenticationError",
    # Rate limiting
    "TokenBucketRateLimiter",
    # Retries
    "with_retries",
    "RetryConfig",
]

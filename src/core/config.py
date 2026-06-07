"""
Application configuration loaded from environment variables.

Uses ``pydantic-settings`` so every field can be overridden via env vars
prefixed with ``ORCH_``.  Defaults are safe for local development.

Usage::

    from src.core.config import settings
    print(settings.polymarket_gamma_url)
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for Orch-xarc."""

    model_config = SettingsConfigDict(
        env_prefix="ORCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── API Base URLs ──────────────────────────────────────
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com/events"
    polymarket_clob_url: str = "https://clob.polymarket.com/book"
    kalshi_api_url: str = "https://api.elections.kalshi.com/trade-api/v2/markets"
    binance_ticker_url: str = "https://api.binance.com/api/v3/ticker/price"
    binance_klines_url: str = "https://api.binance.com/api/v3/klines"

    # ── LLM ────────────────────────────────────────────────
    openai_api_key: str = Field(default="", description="OpenAI API key.")
    google_api_key: str = Field(default="", description="Google AI API key (for Gemini).")
    llm_model: str = Field(default="gemini-2.5-flash", description="Model for LangGraph agent.")
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    # ── Rate Limiting ──────────────────────────────────────
    polymarket_rate: float = Field(default=5.0, description="Polymarket requests/sec.")
    polymarket_capacity: int = Field(default=10)
    kalshi_rate: float = Field(default=3.0, description="Kalshi requests/sec.")
    kalshi_capacity: int = Field(default=6)
    binance_rate: float = Field(default=10.0, description="Binance requests/sec.")
    binance_capacity: int = Field(default=20)

    # ── Retry Defaults ─────────────────────────────────────
    default_max_retries: int = Field(default=3, ge=1, le=10)
    default_retry_base_delay: float = Field(default=1.0, ge=0.1)

    # ── Observability ──────────────────────────────────────
    log_level: str = Field(default="INFO")
    otel_enabled: bool = Field(default=False)
    otel_exporter_endpoint: str = Field(default="http://localhost:4317")

    # ── App ────────────────────────────────────────────────
    app_name: str = "Orch-xarc"
    app_version: str = "0.1.0"
    debug: bool = False


# Singleton instance
settings = Settings()

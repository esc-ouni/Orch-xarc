"""Unit tests for ops tools."""

from __future__ import annotations
import pytest
from src.tools.ops.tools import (
    ops_create_scan_request, ops_health_check, ops_timestamp_now,
    ops_calculate_duration, ops_validate_api_keys, ops_get_market_urls,
    ops_format_scan_result, ops_get_rate_limiter_stats,
)

class TestOpsCreateScanRequest:
    def test_creates_with_id(self):
        r = ops_create_scan_request.invoke({"max_markets": 15})
        assert r["scan_id"].startswith("scan-")
        assert r["max_markets"] == 15

class TestOpsHealthCheck:
    def test_returns_ok(self):
        r = ops_health_check.invoke({})
        assert r["status"] == "ok"

class TestOpsTimestampNow:
    def test_returns_iso(self):
        r = ops_timestamp_now.invoke({})
        assert "T" in r

class TestOpsCalculateDuration:
    def test_calculates(self):
        r = ops_calculate_duration.invoke({
            "start_iso": "2025-01-01T00:00:00+00:00",
            "end_iso": "2025-01-01T00:00:01+00:00",
        })
        assert r == pytest.approx(1000.0)

    def test_invalid(self):
        assert ops_calculate_duration.invoke({"start_iso": "x", "end_iso": "y"}) == 0.0

class TestOpsValidateApiKeys:
    def test_returns_booleans(self):
        r = ops_validate_api_keys.invoke({})
        assert isinstance(r["openai_api_key"], bool)

class TestOpsGetMarketUrls:
    def test_returns_urls(self):
        r = ops_get_market_urls.invoke({})
        assert r["polymarket_gamma"].startswith("http")

class TestOpsFormatScanResult:
    def test_formats(self):
        scan = {"scan_id": "scan-test", "opportunities_found": 2,
                "duration_ms": 1500, "tool_calls_count": 25, "errors": []}
        r = ops_format_scan_result.invoke({"scan_result": scan})
        assert "scan-test" in r

class TestOpsGetRateLimiterStats:
    def test_returns_all(self):
        r = ops_get_rate_limiter_stats.invoke({})
        assert "polymarket" in r

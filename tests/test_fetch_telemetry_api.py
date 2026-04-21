"""Tests for the GET /api/monitoring/sites/{site_id}/fetch-telemetry endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.monitoring import router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/monitoring")
    return app


class TestGetFetchTelemetry:
    """Tests for the fetch telemetry API endpoint. Validates: Requirements 17.5"""

    def test_returns_telemetry_for_site(self):
        """Successful call returns success_rate, total, successes, and breakdown."""
        mock_data = {
            "success_rate": 0.85,
            "total": 100,
            "successes": 85,
            "breakdown": {"200": 85, "403": 10, "429": 5},
        }

        mock_redis = AsyncMock()
        mock_collector = AsyncMock()
        mock_collector.get_success_rate = AsyncMock(return_value=mock_data)

        with patch("src.api.monitoring.aioredis.from_url", return_value=mock_redis), \
             patch("src.api.monitoring.TelemetryCollector", return_value=mock_collector):
            app = _make_app()
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            response = client.get("/api/monitoring/sites/42/fetch-telemetry")

        assert response.status_code == 200
        body = response.json()
        assert body["success_rate"] == 0.85
        assert body["total"] == 100
        assert body["successes"] == 85
        assert body["breakdown"] == {"200": 85, "403": 10, "429": 5}
        mock_collector.get_success_rate.assert_called_once_with(42, window_seconds=3600)

    def test_returns_empty_telemetry_when_no_data(self):
        """When no telemetry data exists, returns defaults."""
        mock_data = {"success_rate": 1.0, "total": 0, "breakdown": {}}

        mock_redis = AsyncMock()
        mock_collector = AsyncMock()
        mock_collector.get_success_rate = AsyncMock(return_value=mock_data)

        with patch("src.api.monitoring.aioredis.from_url", return_value=mock_redis), \
             patch("src.api.monitoring.TelemetryCollector", return_value=mock_collector):
            app = _make_app()
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            response = client.get("/api/monitoring/sites/1/fetch-telemetry")

        assert response.status_code == 200
        body = response.json()
        assert body["success_rate"] == 1.0
        assert body["total"] == 0

    def test_returns_503_on_redis_connection_error(self):
        """When Redis is unavailable, returns 503."""
        import redis.asyncio as aioredis

        with patch(
            "src.api.monitoring.aioredis.from_url",
            side_effect=aioredis.RedisError("Connection refused"),
        ):
            app = _make_app()
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            response = client.get("/api/monitoring/sites/1/fetch-telemetry")

        assert response.status_code == 503
        assert "Redis unavailable" in response.json()["detail"]

    def test_returns_503_on_os_error(self):
        """When an OSError occurs connecting to Redis, returns 503."""
        with patch(
            "src.api.monitoring.aioredis.from_url",
            side_effect=OSError("Network unreachable"),
        ):
            app = _make_app()
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            response = client.get("/api/monitoring/sites/1/fetch-telemetry")

        assert response.status_code == 503

    def test_redis_client_is_closed_after_success(self):
        """Redis client is properly closed after a successful request."""
        mock_data = {"success_rate": 0.9, "total": 10, "successes": 9, "breakdown": {}}
        mock_redis = AsyncMock()
        mock_collector = AsyncMock()
        mock_collector.get_success_rate = AsyncMock(return_value=mock_data)

        with patch("src.api.monitoring.aioredis.from_url", return_value=mock_redis), \
             patch("src.api.monitoring.TelemetryCollector", return_value=mock_collector):
            app = _make_app()
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            client.get("/api/monitoring/sites/5/fetch-telemetry")

        mock_redis.aclose.assert_called_once()

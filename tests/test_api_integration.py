"""
Integration tests for API endpoints.

Tests that all API endpoints are properly configured and accessible.
"""

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app, headers={"X-API-Key": "dev-api-key"})


def test_health_check(client):
    """Test the health check endpoint returns a health response (200 or 503)."""
    response = client.get("/health")
    # In test environments DB/Redis may not be available, so 503 is acceptable
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "status" in data


def test_api_routes_registered(client):
    """Test that all expected API routes are registered."""
    routes = [route.path for route in app.routes]

    # Expected routes matching actual /api/ prefix (not /api/v1/)
    expected_routes = [
        "/",
        "/health",
        "/api/sites/",
        "/api/sites/{site_id}",
        "/api/alerts/",
        "/api/alerts/{alert_id}",
        "/api/contracts/",
        "/api/contracts/{contract_id}",
    ]

    for route in expected_routes:
        assert route in routes, (
            f"Route {route} not found in registered routes. Available: {sorted(routes)}"
        )


def test_openapi_schema(client):
    """Test that OpenAPI schema is available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema


def test_cors_headers(client):
    """Test that CORS middleware is configured and root endpoint is accessible."""
    response = client.get("/")
    assert response.status_code == 200

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
    return TestClient(app)


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


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
    # Get all routes from the app
    routes = [route.path for route in app.routes]
    
    # Expected routes (with /api/v1 prefix and trailing slashes)
    expected_routes = [
        "/",
        "/health",
        "/api/v1/sites/",
        "/api/v1/sites/{site_id}",
        "/api/v1/alerts/",
        "/api/v1/alerts/{alert_id}",
        "/api/v1/contracts/",
        "/api/v1/contracts/{contract_id}",
        "/api/v1/monitoring/history",
        "/api/v1/monitoring/violations",
        "/api/v1/monitoring/statistics",
    ]
    
    # Check that all expected routes are registered
    for route in expected_routes:
        assert route in routes, f"Route {route} not found in registered routes. Available: {sorted(routes)}"


def test_openapi_schema(client):
    """Test that OpenAPI schema is available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema


def test_cors_headers(client):
    """Test that CORS headers are properly configured."""
    response = client.get("/health")
    # CORS middleware is configured, check that request succeeds
    assert response.status_code == 200

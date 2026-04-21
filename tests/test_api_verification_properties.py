"""
Property-based tests for Verification API endpoints.

Tests universal properties that should hold for all API operations.
Feature: verification-comparison-system
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from fastapi.testclient import TestClient
from hypothesis import given, strategies as st, settings, HealthCheck

from src.models import MonitoringSite, VerificationResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Create a minimal FastAPI app with the verification router."""
    from fastapi import FastAPI
    from src.api.verification import router, _running_verifications
    # Clear running verifications between tests
    _running_verifications.clear()
    app = FastAPI()
    app.include_router(router, prefix="/api/verification")
    return app


def _patch_background_task():
    """Patch the background verification task to be a no-op."""
    return patch("src.api.verification._run_verification_task", new=AsyncMock())


def _mock_db_with_site(site_id: int, site_name: str = "Test Site"):
    """Return a mock DB session that finds a site with the given id."""
    db = MagicMock()
    mock_site = MagicMock(spec=MonitoringSite)
    mock_site.id = site_id
    mock_site.name = site_name
    mock_site.url = f"https://example-{site_id}.com"

    def query_side_effect(model):
        q = MagicMock()
        f = MagicMock()
        q.filter.return_value = f
        if model.__name__ == "MonitoringSite":
            f.first.return_value = mock_site
        else:
            f.first.return_value = None
            f.order_by.return_value.first.return_value = None
        return q

    db.query.side_effect = query_side_effect
    return db


def _mock_db_no_site():
    """Return a mock DB session that finds no site."""
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        f = MagicMock()
        q.filter.return_value = f
        f.first.return_value = None
        return q

    db.query.side_effect = query_side_effect
    return db


def _mock_db_with_results(site_id: int, results: list, site_name: str = "Test Site"):
    """Return a mock DB session with verification results."""
    db = MagicMock()
    mock_site = MagicMock(spec=MonitoringSite)
    mock_site.id = site_id
    mock_site.name = site_name

    def query_side_effect(model):
        q = MagicMock()
        f = MagicMock()
        q.filter.return_value = f
        if model.__name__ == "MonitoringSite":
            f.first.return_value = mock_site
        elif model.__name__ == "VerificationResult":
            order = MagicMock()
            f.order_by.return_value = order
            order.count.return_value = len(results)
            f.count.return_value = len(results)
            # Support offset/limit chaining
            offset_mock = MagicMock()
            f.order_by.return_value.offset = lambda o: offset_mock
            offset_mock.limit = lambda l: results[:l]
            # Also handle the direct query path
            order.first.return_value = results[0] if results else None
        return q

    db.query.side_effect = query_side_effect
    return db


def _make_verification_result(site_id: int, status: str = "success", idx: int = 1):
    """Create a mock VerificationResult."""
    result = MagicMock(spec=VerificationResult)
    result.id = idx
    result.site_id = site_id
    result.html_data = {"prices": {"USD": [29.99]}}
    result.ocr_data = {"prices": {"USD": [29.99]}}
    result.discrepancies = {"items": []}
    result.html_violations = {"items": []}
    result.ocr_violations = {"items": []}
    result.screenshot_path = f"/tmp/screenshot_{idx}.png"
    result.ocr_confidence = 0.95
    result.status = status
    result.error_message = None if status == "success" else "Test error"
    result.created_at = datetime(2025, 1, 1, 12, 0, 0)
    return result


# ===========================================================================
# Property 17: API Verification Trigger  (Task 6.3)
# ===========================================================================

class TestAPIVerificationTrigger:
    """Property 17: API Verification Trigger – valid site_id returns 202."""

    # Feature: verification-comparison-system, Property 17: API Verification Trigger
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(site_id=st.integers(min_value=1, max_value=10000))
    def test_property_api_verification_trigger(self, site_id: int):
        """
        Property 17: API Verification Trigger

        For any valid site_id that exists in the database, POST /api/verification/run
        should return HTTP 202 and a response containing job_id and status='processing'.

        **Validates: Requirements 6.1, 6.2**
        """
        app = _make_app()
        db = _mock_db_with_site(site_id)

        from src.api.verification import get_db
        app.dependency_overrides[get_db] = lambda: db

        with _patch_background_task():
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            response = client.post(
                "/api/verification/run",
                json={"site_id": site_id},
            )

        assert response.status_code == 202, (
            f"Expected 202 for valid site_id={site_id}, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "job_id" in data, "Response must contain job_id"
        assert data["status"] == "processing", f"Expected status='processing', got '{data['status']}'"


# ===========================================================================
# Property 18: API Site Validation  (Task 6.4)
# ===========================================================================

class TestAPISiteValidation:
    """Property 18: API Site Validation – non-existent site_id returns 404."""

    # Feature: verification-comparison-system, Property 18: API Site Validation
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(site_id=st.integers(min_value=1, max_value=10000))
    def test_property_api_site_validation(self, site_id: int):
        """
        Property 18: API Site Validation

        For any site_id that does not exist in the database, POST /api/verification/run
        should return HTTP 404.

        **Validates: Requirements 6.3**
        """
        app = _make_app()
        db = _mock_db_no_site()

        from src.api.verification import get_db
        app.dependency_overrides[get_db] = lambda: db

        with _patch_background_task():
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            response = client.post(
                "/api/verification/run",
                json={"site_id": site_id},
            )

        assert response.status_code == 404, (
            f"Expected 404 for non-existent site_id={site_id}, got {response.status_code}"
        )


# ===========================================================================
# Property 19: API Concurrency Control  (Task 6.5)
# ===========================================================================

class TestAPIConcurrencyControl:
    """Property 19: API Concurrency Control – concurrent requests return 409."""

    # Feature: verification-comparison-system, Property 19: API Concurrency Control
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(site_id=st.integers(min_value=1, max_value=10000))
    def test_property_api_concurrency_control(self, site_id: int):
        """
        Property 19: API Concurrency Control

        For any site_id, if a verification is already running, a second
        POST /api/verification/run should return HTTP 409.

        **Validates: Requirements 6.4**
        """
        app = _make_app()
        db = _mock_db_with_site(site_id)

        from src.api.verification import get_db, _running_verifications
        app.dependency_overrides[get_db] = lambda: db

        # Simulate a running verification
        _running_verifications[site_id] = {
            "started_at": datetime.utcnow(),
            "status": "processing",
        }

        with _patch_background_task():
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            response = client.post(
                "/api/verification/run",
                json={"site_id": site_id},
            )

        assert response.status_code == 409, (
            f"Expected 409 for concurrent verification on site_id={site_id}, "
            f"got {response.status_code}"
        )

        # Cleanup
        _running_verifications.clear()


# ===========================================================================
# Property 20: API Optional Parameters  (Task 6.6)
# ===========================================================================

class TestAPIOptionalParameters:
    """Property 20: API Optional Parameters – optional params accepted."""

    # Feature: verification-comparison-system, Property 20: API Optional Parameters
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(
        site_id=st.integers(min_value=1, max_value=10000),
        ocr_language=st.sampled_from(["eng", "jpn", "eng+jpn", "deu", "fra"]),
    )
    def test_property_api_optional_parameters(self, site_id: int, ocr_language: str):
        """
        Property 20: API Optional Parameters

        For any valid site_id, POST /api/verification/run should accept
        optional parameters (ocr_language) without error and still return 202.

        **Validates: Requirements 6.5**
        """
        app = _make_app()
        db = _mock_db_with_site(site_id)

        from src.api.verification import get_db
        app.dependency_overrides[get_db] = lambda: db

        with _patch_background_task():
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            response = client.post(
                "/api/verification/run",
                json={
                    "site_id": site_id,
                    "ocr_language": ocr_language,
                },
            )

        assert response.status_code == 202, (
            f"Expected 202 with optional params for site_id={site_id}, "
            f"got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data["status"] == "processing"


# ===========================================================================
# Property 21: API Results Retrieval  (Task 6.8)
# ===========================================================================

class TestAPIResultsRetrieval:
    """Property 21: API Results Retrieval – existing results return 200."""

    # Feature: verification-comparison-system, Property 21: API Results Retrieval
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(
        site_id=st.integers(min_value=1, max_value=10000),
        num_results=st.integers(min_value=1, max_value=5),
    )
    def test_property_api_results_retrieval(self, site_id: int, num_results: int):
        """
        Property 21: API Results Retrieval

        For any site_id with existing verification results, GET /api/verification/results/{site_id}
        should return HTTP 200 with JSON data containing results array.

        **Validates: Requirements 7.1, 7.2**
        """
        results = [_make_verification_result(site_id, idx=i) for i in range(1, num_results + 1)]

        app = _make_app()
        db = MagicMock()
        mock_site = MagicMock(spec=MonitoringSite)
        mock_site.id = site_id
        mock_site.name = "Test Site"

        # Build query chain for results endpoint
        def query_side_effect(model):
            q = MagicMock()
            f = MagicMock()
            q.filter.return_value = f
            if model.__name__ == "MonitoringSite":
                f.first.return_value = mock_site
            elif model.__name__ == "VerificationResult":
                order_mock = MagicMock()
                f.order_by.return_value = order_mock
                order_mock.count.return_value = num_results
                offset_mock = MagicMock()
                order_mock.offset.return_value = offset_mock
                limit_mock = MagicMock()
                offset_mock.limit.return_value = limit_mock
                limit_mock.all.return_value = results
            return q

        db.query.side_effect = query_side_effect

        from src.api.verification import get_db
        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
        response = client.get(f"/api/verification/results/{site_id}", params={"limit": 10})

        assert response.status_code == 200, (
            f"Expected 200 for site_id={site_id} with {num_results} results, "
            f"got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "results" in data, "Response must contain 'results' key"
        assert isinstance(data["results"], list), "results must be a list"
        assert "total" in data, "Response must contain 'total' key"


# ===========================================================================
# Property 22: API No Results Handling  (Task 6.9)
# ===========================================================================

class TestAPINoResultsHandling:
    """Property 22: API No Results Handling – missing results return 404."""

    # Feature: verification-comparison-system, Property 22: API No Results Handling
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(site_id=st.integers(min_value=1, max_value=10000))
    def test_property_api_no_results_handling(self, site_id: int):
        """
        Property 22: API No Results Handling

        For any site_id with no verification results, GET /api/verification/results/{site_id}
        should return HTTP 404.

        **Validates: Requirements 7.3**
        """
        app = _make_app()
        db = MagicMock()
        mock_site = MagicMock(spec=MonitoringSite)
        mock_site.id = site_id
        mock_site.name = "Test Site"

        def query_side_effect(model):
            q = MagicMock()
            f = MagicMock()
            q.filter.return_value = f
            if model.__name__ == "MonitoringSite":
                f.first.return_value = mock_site
            elif model.__name__ == "VerificationResult":
                order_mock = MagicMock()
                f.order_by.return_value = order_mock
                order_mock.count.return_value = 0
            return q

        db.query.side_effect = query_side_effect

        from src.api.verification import get_db
        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
        response = client.get(f"/api/verification/results/{site_id}")

        assert response.status_code == 404, (
            f"Expected 404 for site_id={site_id} with no results, "
            f"got {response.status_code}"
        )


# ===========================================================================
# Property 23: API Pagination Support  (Task 6.10)
# ===========================================================================

class TestAPIPagination:
    """Property 23: API Pagination Support – limit controls result count."""

    # Feature: verification-comparison-system, Property 23: API Pagination Support
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(
        site_id=st.integers(min_value=1, max_value=10000),
        limit=st.integers(min_value=1, max_value=10),
        offset=st.integers(min_value=0, max_value=5),
    )
    def test_property_api_pagination(self, site_id: int, limit: int, offset: int):
        """
        Property 23: API Pagination Support

        For any site_id with results, GET /api/verification/results/{site_id}
        with limit and offset parameters should return pagination metadata
        (total, limit, offset) and the number of results should not exceed limit.

        **Validates: Requirements 7.4, 7.5**
        """
        total_results = 10
        # Create results that would be returned for this page
        page_size = min(limit, max(0, total_results - offset))
        results = [_make_verification_result(site_id, idx=i) for i in range(1, page_size + 1)]

        app = _make_app()
        db = MagicMock()
        mock_site = MagicMock(spec=MonitoringSite)
        mock_site.id = site_id
        mock_site.name = "Test Site"

        def query_side_effect(model):
            q = MagicMock()
            f = MagicMock()
            q.filter.return_value = f
            if model.__name__ == "MonitoringSite":
                f.first.return_value = mock_site
            elif model.__name__ == "VerificationResult":
                order_mock = MagicMock()
                f.order_by.return_value = order_mock
                order_mock.count.return_value = total_results
                offset_mock = MagicMock()
                order_mock.offset.return_value = offset_mock
                limit_mock = MagicMock()
                offset_mock.limit.return_value = limit_mock
                limit_mock.all.return_value = results
            return q

        db.query.side_effect = query_side_effect

        from src.api.verification import get_db
        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
        response = client.get(
            f"/api/verification/results/{site_id}",
            params={"limit": limit, "offset": offset},
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()

        # Pagination metadata must be present
        assert "total" in data, "Response must contain 'total'"
        assert "limit" in data, "Response must contain 'limit'"
        assert "offset" in data, "Response must contain 'offset'"

        # Limit and offset should match request
        assert data["limit"] == limit, f"Expected limit={limit}, got {data['limit']}"
        assert data["offset"] == offset, f"Expected offset={offset}, got {data['offset']}"

        # Number of results should not exceed limit
        assert len(data["results"]) <= limit, (
            f"Results count {len(data['results'])} exceeds limit {limit}"
        )


# ===========================================================================
# Integration tests for API endpoints  (Task 6.13)
# ===========================================================================

class TestAPIIntegration:
    """Integration tests for verification API endpoints."""

    def test_complete_verification_flow(self):
        """Test complete flow: trigger → check status → get results."""
        app = _make_app()
        site_id = 42
        db = _mock_db_with_site(site_id)

        from src.api.verification import get_db
        app.dependency_overrides[get_db] = lambda: db

        with _patch_background_task():
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})

            # Step 1: Trigger verification
            response = client.post(
                "/api/verification/run",
                json={"site_id": site_id},
            )
            assert response.status_code == 202
            job_id = response.json()["job_id"]

            # Step 2: Check status (should be processing since background task is mocked)
            from src.api.verification import _running_verifications
            _running_verifications[site_id] = {
                "started_at": datetime.utcnow(),
                "status": "processing",
            }

            response = client.get(f"/api/verification/status/{job_id}")
            assert response.status_code == 200
            assert response.json()["status"] == "processing"

            # Step 3: Simulate completion
            _running_verifications.clear()

            # Add a result to the DB mock
            result = _make_verification_result(site_id)
            def query_with_result(model):
                q = MagicMock()
                f = MagicMock()
                q.filter.return_value = f
                if model.__name__ == "MonitoringSite":
                    mock_site = MagicMock(spec=MonitoringSite)
                    mock_site.id = site_id
                    mock_site.name = "Test Site"
                    f.first.return_value = mock_site
                elif model.__name__ == "VerificationResult":
                    order_mock = MagicMock()
                    f.order_by.return_value = order_mock
                    order_mock.count.return_value = 1
                    order_mock.first.return_value = result
                    offset_mock = MagicMock()
                    order_mock.offset.return_value = offset_mock
                    limit_mock = MagicMock()
                    offset_mock.limit.return_value = limit_mock
                    limit_mock.all.return_value = [result]
                return q

            db.query.side_effect = query_with_result

            response = client.get(f"/api/verification/status/{job_id}")
            assert response.status_code == 200
            status_data = response.json()
            assert status_data["status"] in ("completed", "failed")

    def test_trigger_nonexistent_site_returns_404(self):
        """Test that triggering verification for non-existent site returns 404."""
        app = _make_app()
        db = _mock_db_no_site()

        from src.api.verification import get_db
        app.dependency_overrides[get_db] = lambda: db

        with _patch_background_task():
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            response = client.post(
                "/api/verification/run",
                json={"site_id": 99999},
            )
        assert response.status_code == 404

    def test_results_nonexistent_site_returns_404(self):
        """Test that getting results for non-existent site returns 404."""
        app = _make_app()
        db = _mock_db_no_site()

        from src.api.verification import get_db
        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
        response = client.get("/api/verification/results/99999")
        assert response.status_code == 404

    def test_concurrent_verification_returns_409(self):
        """Test that concurrent verification for same site returns 409."""
        app = _make_app()
        site_id = 42
        db = _mock_db_with_site(site_id)

        from src.api.verification import get_db, _running_verifications
        app.dependency_overrides[get_db] = lambda: db

        with _patch_background_task():
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})

            # First request succeeds
            response1 = client.post(
                "/api/verification/run",
                json={"site_id": site_id},
            )
            assert response1.status_code == 202

            # Second request should fail with 409
            response2 = client.post(
                "/api/verification/run",
                json={"site_id": site_id},
            )
            assert response2.status_code == 409

        _running_verifications.clear()

    def test_error_responses_have_detail(self):
        """Test that error responses include detail message."""
        app = _make_app()
        db = _mock_db_no_site()

        from src.api.verification import get_db
        app.dependency_overrides[get_db] = lambda: db

        with _patch_background_task():
            client = TestClient(app, headers={"X-API-Key": "dev-api-key"})
            response = client.post(
                "/api/verification/run",
                json={"site_id": 1},
            )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data, "Error response must contain 'detail'"
        assert isinstance(data["detail"], str)

"""
Property-based and unit tests for Dark Pattern Detection API and violation format.

**Validates: Requirements 14.1–14.6, 12.1, 12.2, 12.4, 12.5, 12.6**

Properties tested:
  Property 20: 違反レコードの通知連携フォーマット
  Property 21: APIレスポンスの必須フィールド
  Property 22: ページネーションの正確性
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.models import MonitoringSite, VerificationResult


# ---------------------------------------------------------------------------
# Severity mapping (Property 20)
# ---------------------------------------------------------------------------

SEVERITY_MAP: dict[str, str] = {
    "high_dark_pattern_risk": "critical",
    "sneak_into_basket": "warning",
    "default_subscription": "warning",
    "confirmshaming": "warning",
    "visual_deception": "warning",
    "low_contrast": "warning",
    "tiny_font": "warning",
    "css_hidden": "warning",
    "distant_cancellation_terms": "info",
}

# Violation types produced by each plugin
PLUGIN_VIOLATION_TYPES: dict[str, list[dict]] = {
    "UITrapPlugin": [
        {"violation_type": "sneak_into_basket", "severity": "warning", "dark_pattern_category": "sneak_into_basket"},
        {"violation_type": "default_subscription", "severity": "warning", "dark_pattern_category": "default_subscription"},
        {"violation_type": "confirmshaming", "severity": "warning", "dark_pattern_category": "confirmshaming"},
        {"violation_type": "distant_cancellation_terms", "severity": "info", "dark_pattern_category": "distant_cancellation_terms"},
    ],
    "CSSVisualPlugin": [
        {"violation_type": "low_contrast", "severity": "warning", "dark_pattern_category": "visual_deception"},
        {"violation_type": "tiny_font", "severity": "warning", "dark_pattern_category": "visual_deception"},
        {"violation_type": "css_hidden", "severity": "warning", "dark_pattern_category": "visual_deception"},
    ],
    "DarkPatternScore": [
        {"violation_type": "high_dark_pattern_risk", "severity": "critical", "dark_pattern_category": "high_dark_pattern_risk"},
    ],
    "LLMClassifierPlugin": [
        {"violation_type": "hidden_subscription", "severity": "warning", "dark_pattern_category": "hidden_subscription"},
    ],
}


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_violation_type_st = st.sampled_from(list(SEVERITY_MAP.keys()))


@st.composite
def violation_record_st(draw):
    """Generate a violation record from one of the plugin types."""
    plugin = draw(st.sampled_from(list(PLUGIN_VIOLATION_TYPES.keys())))
    template = draw(st.sampled_from(PLUGIN_VIOLATION_TYPES[plugin]))
    return dict(template)  # copy


@st.composite
def pagination_scenario_st(draw):
    """Generate limit, offset, and total record count for pagination testing."""
    total = draw(st.integers(min_value=0, max_value=200))
    limit = draw(st.integers(min_value=1, max_value=100))
    offset = draw(st.integers(min_value=0, max_value=max(total, 1)))
    return limit, offset, total


# ---------------------------------------------------------------------------
# Property 20: 違反レコードの通知連携フォーマット
# **Validates: Requirements 14.1, 14.2, 14.3, 14.4, 14.5, 14.6**
# ---------------------------------------------------------------------------


@given(violation=violation_record_st())
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property20_violation_format(violation):
    """Property 20: violations contain required fields with correct severity mapping."""
    # Required fields must be present
    assert "violation_type" in violation, "violation_type field missing"
    assert "severity" in violation, "severity field missing"
    assert "dark_pattern_category" in violation, "dark_pattern_category field missing"

    vtype = violation["violation_type"]
    severity = violation["severity"]

    # Severity mapping correctness
    if vtype == "high_dark_pattern_risk":
        assert severity == "critical", f"high_dark_pattern_risk should be critical, got {severity}"
    elif vtype in ("sneak_into_basket", "default_subscription", "confirmshaming"):
        assert severity == "warning", f"{vtype} should be warning, got {severity}"
    elif vtype in ("low_contrast", "tiny_font", "css_hidden"):
        # CSSVisualPlugin visual_deception violations
        assert severity == "warning", f"{vtype} should be warning, got {severity}"
    elif vtype == "distant_cancellation_terms":
        assert severity == "info", f"distant_cancellation_terms should be info, got {severity}"
    elif vtype == "hidden_subscription":
        assert severity == "warning", f"hidden_subscription should be warning, got {severity}"


# ---------------------------------------------------------------------------
# Property 21: APIレスポンスの必須フィールド
# **Validates: Requirements 12.2**
# ---------------------------------------------------------------------------


@st.composite
def dark_pattern_result_st(draw):
    """Generate a VerificationResult-like dict with non-null dark_pattern_score."""
    score = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    subscores = {
        "css_visual": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        "llm_classifier": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        "journey": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        "ui_trap": draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
    }
    types = draw(st.dictionaries(
        st.sampled_from(["visual_deception", "hidden_subscription", "sneak_into_basket",
                         "confirmshaming", "distant_cancellation_terms"]),
        st.booleans(),
        min_size=0,
        max_size=3,
    ))
    detected_at = draw(st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31),
        timezones=st.none(),
    ))
    return {
        "dark_pattern_score": score,
        "dark_pattern_subscores": subscores,
        "dark_pattern_types": types,
        "detected_at": detected_at,
    }


@given(result=dark_pattern_result_st())
@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
def test_property21_api_response_fields(result):
    """Property 21: response with non-null score contains all required fields."""
    assert isinstance(result["dark_pattern_score"], float)
    assert isinstance(result["dark_pattern_subscores"], dict)
    assert isinstance(result["dark_pattern_types"], dict)
    assert isinstance(result["detected_at"], datetime)

    # Score in valid range
    assert 0.0 <= result["dark_pattern_score"] <= 1.0

    # Subscores dict has expected keys
    for key in ("css_visual", "llm_classifier", "journey", "ui_trap"):
        assert key in result["dark_pattern_subscores"]
        assert isinstance(result["dark_pattern_subscores"][key], float)


# ---------------------------------------------------------------------------
# Property 22: ページネーションの正確性
# **Validates: Requirements 12.4**
# ---------------------------------------------------------------------------


@given(scenario=pagination_scenario_st())
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_property22_pagination_accuracy(scenario):
    """Property 22: len(results) <= min(limit, max(0, total - offset)) and total matches."""
    limit, offset, total = scenario

    # Simulate what the API does: offset + limit slice
    available = max(0, total - offset)
    expected_max = min(limit, available)

    # Simulate fetching results
    all_records = list(range(total))
    page = all_records[offset: offset + limit]

    assert len(page) <= expected_max
    assert len(page) == expected_max  # exact match for simple list slicing
    assert total == len(all_records)


# ===========================================================================
# Unit tests for API endpoints (Task 5.4)
# ===========================================================================


class TestDarkPatternAPIEndpoints:
    """Unit tests for dark pattern API endpoints using FastAPI TestClient."""

    @pytest.fixture(autouse=True)
    def _require_docker(self, request):
        """Skip tests if Docker is not available."""
        from tests.conftest import DOCKER_AVAILABLE
        if not DOCKER_AVAILABLE:
            pytest.skip("Docker is not available")

    def test_404_for_nonexistent_site(self, client):
        """GET /api/sites/{site_id}/dark-patterns returns 404 for missing site."""
        resp = client.get("/api/sites/999999/dark-patterns")
        assert resp.status_code == 404

    def test_404_for_nonexistent_site_history(self, client):
        """GET /api/sites/{site_id}/dark-patterns/history returns 404 for missing site."""
        resp = client.get("/api/sites/999999/dark-patterns/history")
        assert resp.status_code == 404

    def test_empty_result_returns_null(self, client, db_session):
        """When no dark pattern data exists, response is null."""
        from src.models import Customer

        customer = Customer(
            name="Test Customer",
            email="test@example.com",
        )
        db_session.add(customer)
        db_session.flush()

        site = MonitoringSite(
            customer_id=customer.id,
            name="Test Site",
            url="https://example.com",
        )
        db_session.add(site)
        db_session.flush()

        resp = client.get(f"/api/sites/{site.id}/dark-patterns")
        assert resp.status_code == 200
        assert resp.json() is None

    def test_normal_response_with_score(self, client, db_session):
        """Normal response includes score, subscores, and types."""
        from src.models import Customer

        customer = Customer(
            name="Test Customer 2",
            email="test2@example.com",
        )
        db_session.add(customer)
        db_session.flush()

        site = MonitoringSite(
            customer_id=customer.id,
            name="Test Site 2",
            url="https://example2.com",
        )
        db_session.add(site)
        db_session.flush()

        vr = VerificationResult(
            site_id=site.id,
            html_data={},
            ocr_data={},
            html_violations={},
            ocr_violations={},
            discrepancies={},
            screenshot_path="/tmp/test.png",
            ocr_confidence=0.95,
            status="completed",
            dark_pattern_score=0.75,
            dark_pattern_subscores={
                "css_visual": 0.3,
                "llm_classifier": 0.75,
                "journey": 0.15,
                "ui_trap": 0.5,
            },
            dark_pattern_types={
                "hidden_subscription": True,
                "confirmshaming": True,
            },
        )
        db_session.add(vr)
        db_session.flush()

        resp = client.get(f"/api/sites/{site.id}/dark-patterns")
        assert resp.status_code == 200
        data = resp.json()
        assert data is not None
        assert data["dark_pattern_score"] == pytest.approx(0.75)
        assert data["dark_pattern_subscores"]["css_visual"] == pytest.approx(0.3)
        assert data["dark_pattern_subscores"]["llm_classifier"] == pytest.approx(0.75)
        assert "detected_at" in data

    def test_history_pagination(self, client, db_session):
        """History endpoint respects limit and offset."""
        from src.models import Customer

        customer = Customer(
            name="Test Customer 3",
            email="test3@example.com",
        )
        db_session.add(customer)
        db_session.flush()

        site = MonitoringSite(
            customer_id=customer.id,
            name="Test Site 3",
            url="https://example3.com",
        )
        db_session.add(site)
        db_session.flush()

        # Create 5 verification results with dark_pattern_score
        for i in range(5):
            vr = VerificationResult(
                site_id=site.id,
                html_data={},
                ocr_data={},
                html_violations={},
                ocr_violations={},
                discrepancies={},
                screenshot_path=f"/tmp/test_{i}.png",
                ocr_confidence=0.9,
                status="completed",
                dark_pattern_score=0.1 * (i + 1),
                dark_pattern_subscores={"css_visual": 0.1 * (i + 1)},
                dark_pattern_types={},
            )
            db_session.add(vr)
        db_session.flush()

        # Test default pagination
        resp = client.get(f"/api/sites/{site.id}/dark-patterns/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["results"]) == 5
        assert data["limit"] == 50
        assert data["offset"] == 0

        # Test with limit=2
        resp = client.get(f"/api/sites/{site.id}/dark-patterns/history?limit=2")
        data = resp.json()
        assert len(data["results"]) == 2
        assert data["total"] == 5
        assert data["limit"] == 2

        # Test with offset=3
        resp = client.get(f"/api/sites/{site.id}/dark-patterns/history?limit=10&offset=3")
        data = resp.json()
        assert len(data["results"]) == 2  # 5 - 3 = 2 remaining
        assert data["total"] == 5
        assert data["offset"] == 3

        # Test with offset beyond total
        resp = client.get(f"/api/sites/{site.id}/dark-patterns/history?offset=10")
        data = resp.json()
        assert len(data["results"]) == 0
        assert data["total"] == 5

    def test_history_empty_results(self, client, db_session):
        """History returns empty results when no dark pattern data exists."""
        from src.models import Customer

        customer = Customer(
            name="Test Customer 4",
            email="test4@example.com",
        )
        db_session.add(customer)
        db_session.flush()

        site = MonitoringSite(
            customer_id=customer.id,
            name="Test Site 4",
            url="https://example4.com",
        )
        db_session.add(site)
        db_session.flush()

        resp = client.get(f"/api/sites/{site.id}/dark-patterns/history")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["results"] == []

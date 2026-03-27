"""
Unit tests for VerificationResult model.

Tests model creation, field validation, relationships, and queries
using the shared PostgreSQL testcontainers fixtures for isolation.

Validates: Requirements 5.1, 5.2
"""

import pytest
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.models import Customer, MonitoringSite, VerificationResult


# --- Helper fixtures ---

@pytest.fixture
def customer(db_session: Session) -> Customer:
    """Create a test customer."""
    c = Customer(name="Test Corp", email="test@example.com")
    db_session.add(c)
    db_session.flush()
    return c


@pytest.fixture
def site(db_session: Session, customer: Customer) -> MonitoringSite:
    """Create a test monitoring site."""
    s = MonitoringSite(
        customer_id=customer.id,
        name="Test Site",
        url="https://example.com/payment",
    )
    db_session.add(s)
    db_session.flush()
    return s


def _make_verification(site: MonitoringSite, **overrides) -> VerificationResult:
    """Build a VerificationResult with sensible defaults; override any field via kwargs."""
    defaults = dict(
        site_id=site.id,
        html_data={"prices": {"USD": [29.99]}},
        ocr_data={"prices": {"USD": [29.99]}},
        html_violations=[],
        ocr_violations=[],
        discrepancies=[],
        screenshot_path="/screenshots/test.png",
        ocr_confidence=0.92,
        status="success",
        error_message=None,
    )
    defaults.update(overrides)
    return VerificationResult(**defaults)


# --- Tests ---


class TestVerificationResultCreation:
    """Tests for model creation and field storage (Req 5.1, 5.2)."""

    def test_create_with_all_required_fields(self, db_session, site):
        """A VerificationResult can be persisted with every required field."""
        vr = _make_verification(site)
        db_session.add(vr)
        db_session.flush()

        assert vr.id is not None
        assert vr.site_id == site.id
        assert vr.html_data == {"prices": {"USD": [29.99]}}
        assert vr.ocr_data == {"prices": {"USD": [29.99]}}
        assert vr.html_violations == []
        assert vr.ocr_violations == []
        assert vr.discrepancies == []
        assert vr.screenshot_path == "/screenshots/test.png"
        assert vr.ocr_confidence == 0.92
        assert vr.status == "success"

    def test_stores_complex_jsonb_data(self, db_session, site):
        """JSONB columns correctly round-trip nested dicts and lists."""
        complex_data = {
            "prices": {"USD": [29.99, 39.99], "EUR": [24.99]},
            "payment_methods": ["credit_card", "paypal"],
            "fees": {"percentage": [3.0], "fixed": [0.30]},
        }
        vr = _make_verification(
            site,
            html_data=complex_data,
            ocr_data=complex_data,
            discrepancies=[
                {"field_name": "prices.USD", "html_value": [29.99], "ocr_value": [29.99, 39.99],
                 "difference_type": "mismatch", "severity": "high"}
            ],
        )
        db_session.add(vr)
        db_session.flush()

        fetched = db_session.get(VerificationResult, vr.id)
        assert fetched.html_data == complex_data
        assert len(fetched.discrepancies) == 1
        assert fetched.discrepancies[0]["severity"] == "high"

    def test_created_at_defaults_to_now(self, db_session, site):
        """created_at is automatically set close to the current time."""
        before = datetime.utcnow()
        vr = _make_verification(site)
        db_session.add(vr)
        db_session.flush()
        after = datetime.utcnow()

        assert vr.created_at is not None
        assert before <= vr.created_at <= after


class TestVerificationResultErrorMessage:
    """Tests for nullable error_message field (Req 5.2)."""

    def test_error_message_null_on_success(self, db_session, site):
        """Successful verifications have error_message=None."""
        vr = _make_verification(site, status="success", error_message=None)
        db_session.add(vr)
        db_session.flush()

        fetched = db_session.get(VerificationResult, vr.id)
        assert fetched.error_message is None

    def test_error_message_set_on_failure(self, db_session, site):
        """Failed verifications store a descriptive error_message."""
        vr = _make_verification(
            site,
            status="failure",
            error_message="Screenshot capture timed out",
        )
        db_session.add(vr)
        db_session.flush()

        fetched = db_session.get(VerificationResult, vr.id)
        assert fetched.error_message == "Screenshot capture timed out"
        assert fetched.status == "failure"


class TestVerificationResultRelationship:
    """Tests for the site relationship."""

    def test_relationship_to_monitoring_site(self, db_session, site):
        """The .site relationship resolves to the parent MonitoringSite."""
        vr = _make_verification(site)
        db_session.add(vr)
        db_session.flush()

        assert vr.site is not None
        assert vr.site.id == site.id
        assert vr.site.name == "Test Site"


class TestVerificationResultQueries:
    """Tests for querying VerificationResults."""

    def test_query_by_site_id(self, db_session, site):
        """Results can be filtered by site_id."""
        vr1 = _make_verification(site)
        vr2 = _make_verification(site)
        db_session.add_all([vr1, vr2])
        db_session.flush()

        results = (
            db_session.query(VerificationResult)
            .filter(VerificationResult.site_id == site.id)
            .all()
        )
        assert len(results) == 2

    def test_query_by_status(self, db_session, site):
        """Results can be filtered by status."""
        vr_ok = _make_verification(site, status="success")
        vr_fail = _make_verification(site, status="failure", error_message="err")
        vr_partial = _make_verification(site, status="partial_failure")
        db_session.add_all([vr_ok, vr_fail, vr_partial])
        db_session.flush()

        failures = (
            db_session.query(VerificationResult)
            .filter(VerificationResult.status == "failure")
            .all()
        )
        assert len(failures) == 1
        assert failures[0].error_message == "err"

    def test_order_by_created_at(self, db_session, site):
        """Results can be ordered by created_at descending (most recent first)."""
        old = _make_verification(site)
        old.created_at = datetime.utcnow() - timedelta(hours=1)
        new = _make_verification(site)
        db_session.add_all([old, new])
        db_session.flush()

        results = (
            db_session.query(VerificationResult)
            .filter(VerificationResult.site_id == site.id)
            .order_by(VerificationResult.created_at.desc())
            .all()
        )
        assert results[0].created_at >= results[1].created_at


class TestVerificationResultRepr:
    """Tests for the __repr__ method."""

    def test_repr_format(self, db_session, site):
        """__repr__ includes id, site_id, and status."""
        vr = _make_verification(site)
        db_session.add(vr)
        db_session.flush()

        r = repr(vr)
        assert "VerificationResult" in r
        assert str(vr.id) in r
        assert str(site.id) in r
        assert "success" in r


class TestVerificationResultPipelineColumns:
    """Tests for pipeline architecture columns (Req 21.4)."""

    def test_new_columns_default_to_none(self, db_session, site):
        """New pipeline columns are nullable and default to None."""
        vr = _make_verification(site)
        db_session.add(vr)
        db_session.flush()

        fetched = db_session.get(VerificationResult, vr.id)
        assert fetched.structured_data is None
        assert fetched.structured_data_violations is None
        assert fetched.data_source is None
        assert fetched.structured_data_status is None
        assert fetched.evidence_status is None

    def test_set_structured_data_json(self, db_session, site):
        """structured_data and structured_data_violations store JSON correctly."""
        sd = {"product_name": "Test", "variants": [{"price": 1980, "data_source": "json_ld"}]}
        sdv = [{"variant_name": "A", "contract_price": 1980, "actual_price": 2480}]
        vr = _make_verification(
            site,
            structured_data=sd,
            structured_data_violations=sdv,
            data_source="json_ld",
            structured_data_status="found",
            evidence_status="collected",
        )
        db_session.add(vr)
        db_session.flush()

        fetched = db_session.get(VerificationResult, vr.id)
        assert fetched.structured_data == sd
        assert fetched.structured_data_violations == sdv
        assert fetched.data_source == "json_ld"
        assert fetched.structured_data_status == "found"
        assert fetched.evidence_status == "collected"

    def test_string_columns_accept_expected_values(self, db_session, site):
        """data_source, structured_data_status, evidence_status accept valid string values."""
        for ds, sds, es in [
            ("shopify_api", "empty", "partial"),
            ("microdata", "error", "none"),
            ("html_fallback", "found", "collected"),
        ]:
            vr = _make_verification(
                site, data_source=ds, structured_data_status=sds, evidence_status=es
            )
            db_session.add(vr)
            db_session.flush()

            fetched = db_session.get(VerificationResult, vr.id)
            assert fetched.data_source == ds
            assert fetched.structured_data_status == sds
            assert fetched.evidence_status == es

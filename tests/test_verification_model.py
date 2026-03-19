"""
Unit tests for VerificationResult model.

Tests model creation, field validation, relationships, and queries
using a SQLite in-memory database for isolation.

Validates: Requirements 5.1, 5.2
"""

import pytest
from datetime import datetime, timedelta

from sqlalchemy import create_engine, event, JSON
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import JSONB

from src.models import Base, Customer, MonitoringSite, VerificationResult


# --- SQLite JSONB compatibility ---
# SQLite doesn't support JSONB, so we remap it to JSON for testing.

@event.listens_for(Base.metadata, "column_reflect")
def _remap_jsonb(inspector, table, column_info):
    if isinstance(column_info["type"], JSONB):
        column_info["type"] = JSON()


# Patch JSONB to JSON at the dialect level for table creation
_original_compile = None


@pytest.fixture(scope="module")
def engine():
    """Create a SQLite in-memory engine with JSONB→JSON compilation support."""
    eng = create_engine("sqlite:///:memory:")

    # Register a compilation rule so JSONB renders as JSON in SQLite
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def _compile_jsonb_sqlite(type_, compiler, **kw):
        return "JSON"

    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture
def db_session(engine):
    """Provide a transactional database session that rolls back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


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

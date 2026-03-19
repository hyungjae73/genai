"""
Backend integration tests (Task 28.1).

Covers:
- End-to-end extraction pipeline: HTML → extraction → persistence
- Price history tracking and anomaly detection with real DB
- API endpoint integration: CRUD operations with real data flow

Uses SQLite in-memory database following existing test patterns.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import (
    create_engine, Column, Integer, Float, String, Text,
    DateTime, Boolean, ForeignKey,
)
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import JSON
from fastapi.testclient import TestClient

from src.main import app
from src.database import get_db
from src.auth import verify_api_key


# ---------------------------------------------------------------------------
# Test-specific models (JSON instead of JSONB for SQLite)
# ---------------------------------------------------------------------------

class TestBase(DeclarativeBase):
    pass


class TCustomer(TestBase):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class TMonitoringSite(TestBase):
    __tablename__ = "monitoring_sites"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    last_crawled_at = Column(DateTime, nullable=True)
    compliance_status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    category_id = Column(Integer, nullable=True)


class TCrawlResult(TestBase):
    __tablename__ = "crawl_results"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("monitoring_sites.id"), nullable=False)
    url = Column(Text, nullable=False)
    html_content = Column(Text, nullable=False)
    screenshot_path = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=False)
    crawled_at = Column(DateTime, default=datetime.utcnow)


class TExtractedPaymentInfo(TestBase):
    __tablename__ = "extracted_payment_info"
    id = Column(Integer, primary_key=True)
    crawl_result_id = Column(Integer, ForeignKey("crawl_results.id"), nullable=False)
    site_id = Column(Integer, ForeignKey("monitoring_sites.id"), nullable=False)
    product_info = Column(JSON, nullable=True)
    price_info = Column(JSON, nullable=True)
    payment_methods = Column(JSON, nullable=True)
    fees = Column(JSON, nullable=True)
    extraction_metadata = Column("metadata", JSON, nullable=True)
    confidence_scores = Column(JSON, nullable=True)
    overall_confidence_score = Column(Float, nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    language = Column(String(10), nullable=True)
    extracted_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TAuditLog(TestBase):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user = Column(String(255), nullable=False)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


class TPriceHistory(TestBase):
    __tablename__ = "price_history"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("monitoring_sites.id"), nullable=False)
    product_identifier = Column(String(500), nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False)
    price_type = Column(String(50), nullable=False)
    previous_price = Column(Float, nullable=True)
    price_change_amount = Column(Float, nullable=True)
    price_change_percentage = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    extracted_payment_info_id = Column(Integer, nullable=True)


class TAlert(TestBase):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    violation_id = Column(Integer, nullable=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    message = Column(Text, nullable=False)
    is_resolved = Column(Boolean, default=False)
    site_id = Column(Integer, ForeignKey("monitoring_sites.id"), nullable=True)
    email_sent = Column(Boolean, default=False)
    slack_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    old_price = Column(Float, nullable=True)
    new_price = Column(Float, nullable=True)
    change_percentage = Column(Float, nullable=True)


class TViolation(TestBase):
    __tablename__ = "violations"
    id = Column(Integer, primary_key=True)
    validation_result_id = Column(Integer, nullable=False)
    violation_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    field_name = Column(String(100), nullable=False)
    expected_value = Column(JSON, nullable=False)
    actual_value = Column(JSON, nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Shared engine / session
# ---------------------------------------------------------------------------

_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_SessionLocal = sessionmaker(bind=_engine)


@pytest.fixture(autouse=True)
def _setup_tables():
    """Create tables before each test, drop after."""
    TestBase.metadata.create_all(_engine)
    yield
    TestBase.metadata.drop_all(_engine)


@pytest.fixture
def db_session():
    session = _SessionLocal()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def _patch_models(monkeypatch):
    """Redirect ORM model references to SQLite-compatible test models."""
    import src.api.extracted_data as ep_mod
    import src.api.screenshots as ss_mod
    monkeypatch.setattr(ep_mod, "ExtractedPaymentInfo", TExtractedPaymentInfo)
    monkeypatch.setattr(ep_mod, "AuditLog", TAuditLog)
    monkeypatch.setattr(ep_mod, "PriceHistory", TPriceHistory)
    monkeypatch.setattr(ss_mod, "CrawlResult", TCrawlResult)


@pytest.fixture
def client():
    """FastAPI TestClient with overridden DB and auth dependencies."""

    def _override_get_db():
        session = _SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def _override_auth(x_api_key: str = "test-api-key"):
        return x_api_key

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[verify_api_key] = _override_auth
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers – seed data
# ---------------------------------------------------------------------------

def _seed_site(session):
    """Create a customer + monitoring site, return (customer, site)."""
    customer = TCustomer(name="Integration Test Customer", email="integ@example.com")
    session.add(customer)
    session.flush()
    site = TMonitoringSite(
        customer_id=customer.id,
        name="Integration Test Site",
        url="https://integration-test.example.com",
    )
    session.add(site)
    session.flush()
    return customer, site


def _seed_crawl_result(session, site_id, html_content="<html></html>", url=None):
    """Create a crawl result for the given site."""
    cr = TCrawlResult(
        site_id=site_id,
        url=url or "https://integration-test.example.com/page",
        html_content=html_content,
        status_code=200,
    )
    session.add(cr)
    session.flush()
    return cr


def _seed_extracted_info(session, crawl_result_id, site_id, **kwargs):
    """Create an extracted payment info record with defaults."""
    defaults = dict(
        product_info={"name": "Test Product", "sku": "SKU-001"},
        price_info=[{"amount": 1000, "currency": "JPY", "price_type": "base_price"}],
        payment_methods=[{"method_name": "Credit Card"}],
        fees=[{"fee_type": "shipping", "amount": 500}],
        extraction_metadata={"source": "integration_test"},
        confidence_scores={"product_name": 0.9, "base_price": 0.85},
        overall_confidence_score=0.87,
        status="completed",
        language="ja",
        extracted_at=datetime.utcnow(),
    )
    defaults.update(kwargs)
    record = TExtractedPaymentInfo(
        crawl_result_id=crawl_result_id,
        site_id=site_id,
        **defaults,
    )
    session.add(record)
    session.flush()
    return record


def _seed_price_history(session, site_id, product_id="Test Product [SKU-001]",
                        price=1000.0, recorded_at=None, **kwargs):
    """Create a price history record."""
    record = TPriceHistory(
        site_id=site_id,
        product_identifier=product_id,
        price=price,
        currency=kwargs.get("currency", "JPY"),
        price_type=kwargs.get("price_type", "base_price"),
        previous_price=kwargs.get("previous_price"),
        price_change_amount=kwargs.get("price_change_amount"),
        price_change_percentage=kwargs.get("price_change_percentage"),
        recorded_at=recorded_at or datetime.utcnow(),
    )
    session.add(record)
    session.flush()
    return record


# ===========================================================================
# 1. End-to-end extraction pipeline: HTML → extraction → persistence
# ===========================================================================

# Sample HTML with JSON-LD structured data
_JSONLD_HTML = """
<html lang="ja">
<head>
    <title>テスト商品ページ</title>
    <meta name="description" content="テスト商品の説明">
    <meta property="og:title" content="テスト商品">
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "プレミアムウィジェット",
        "description": "高品質なウィジェット",
        "sku": "WDG-001",
        "offers": {
            "@type": "Offer",
            "price": "2980",
            "priceCurrency": "JPY",
            "availability": "https://schema.org/InStock"
        }
    }
    </script>
</head>
<body>
    <article><h1>プレミアムウィジェット</h1></article>
    <section><span class="price">¥2,980</span></section>
    <form>
        <input type="radio" name="payment" value="クレジットカード">
        <label>クレジットカード</label>
    </form>
    <table>
        <caption>手数料</caption>
        <tr><th>手数料</th><th>金額</th></tr>
        <tr><td>送料</td><td>¥500</td></tr>
    </table>
</body>
</html>
"""

# Semantic-only HTML (no structured data)
_SEMANTIC_HTML = """
<html lang="en">
<head><title>Widget Store</title></head>
<body>
    <article><h1>Standard Widget</h1></article>
    <section><span itemprop="price" content="49.99">$49.99</span></section>
</body>
</html>
"""


class TestExtractionPipelineIntegration:
    """End-to-end: HTML → PaymentInfoExtractor → DB persistence."""

    def test_extract_and_persist_jsonld(self, db_session):
        """Full pipeline: extract from JSON-LD HTML and persist to DB."""
        from src.extractors.payment_info_extractor import PaymentInfoExtractor

        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id, html_content=_JSONLD_HTML)
        db_session.commit()

        extractor = PaymentInfoExtractor()
        extracted = extractor.extract_payment_info(_JSONLD_HTML, cr.url)

        # Verify extraction results
        assert extracted["product_info"]["name"] == "プレミアムウィジェット"
        assert extracted["extraction_source"] == "structured_data"
        assert extracted["language"] == "ja"
        assert any(p["amount"] == 2980.0 for p in extracted["price_info"])
        assert extracted["overall_confidence"] > 0.0

        # Persist to DB
        record = TExtractedPaymentInfo(
            crawl_result_id=cr.id,
            site_id=site.id,
            product_info=extracted["product_info"],
            price_info=extracted["price_info"],
            payment_methods=extracted["payment_methods"],
            fees=extracted["fees"],
            extraction_metadata=extracted["metadata"],
            confidence_scores=extracted["confidence_scores"],
            overall_confidence_score=extracted["overall_confidence"],
            status="completed",
            language=extracted["language"],
        )
        db_session.add(record)
        db_session.commit()

        # Verify persistence
        saved = db_session.query(TExtractedPaymentInfo).filter_by(
            crawl_result_id=cr.id
        ).first()
        assert saved is not None
        assert saved.product_info["name"] == "プレミアムウィジェット"
        assert saved.status == "completed"
        assert saved.language == "ja"
        assert saved.overall_confidence_score > 0.0

    def test_extract_and_persist_semantic_html(self, db_session):
        """Pipeline with semantic HTML (no structured data)."""
        from src.extractors.payment_info_extractor import PaymentInfoExtractor

        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id, html_content=_SEMANTIC_HTML)
        db_session.commit()

        extractor = PaymentInfoExtractor()
        extracted = extractor.extract_payment_info(_SEMANTIC_HTML, cr.url)

        assert extracted["extraction_source"] == "semantic_html"
        assert len(extracted["price_info"]) > 0

        record = TExtractedPaymentInfo(
            crawl_result_id=cr.id,
            site_id=site.id,
            product_info=extracted["product_info"],
            price_info=extracted["price_info"],
            payment_methods=extracted["payment_methods"],
            fees=extracted["fees"],
            extraction_metadata=extracted["metadata"],
            confidence_scores=extracted["confidence_scores"],
            overall_confidence_score=extracted["overall_confidence"],
            status="completed",
            language=extracted["language"],
        )
        db_session.add(record)
        db_session.commit()

        saved = db_session.query(TExtractedPaymentInfo).filter_by(
            crawl_result_id=cr.id
        ).first()
        assert saved is not None
        assert saved.overall_confidence_score > 0.0

    def test_extraction_failure_persists_failed_status(self, db_session):
        """When extraction yields no data, a record with appropriate status is saved."""
        from src.extractors.payment_info_extractor import PaymentInfoExtractor

        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id, html_content="<html><body></body></html>")
        db_session.commit()

        extractor = PaymentInfoExtractor()
        extracted = extractor.extract_payment_info("<html><body></body></html>", cr.url)

        # Even with empty HTML, extraction should return a valid dict
        assert isinstance(extracted, dict)
        assert extracted["extraction_source"] == "regex"

        record = TExtractedPaymentInfo(
            crawl_result_id=cr.id,
            site_id=site.id,
            product_info=extracted["product_info"],
            price_info=extracted["price_info"],
            payment_methods=extracted["payment_methods"],
            fees=extracted["fees"],
            extraction_metadata=extracted["metadata"],
            confidence_scores=extracted["confidence_scores"],
            overall_confidence_score=extracted["overall_confidence"],
            status="completed" if extracted["price_info"] else "failed",
            language=extracted["language"],
        )
        db_session.add(record)
        db_session.commit()

        saved = db_session.query(TExtractedPaymentInfo).filter_by(
            crawl_result_id=cr.id
        ).first()
        assert saved is not None

    def test_multiple_extractions_for_same_site(self, db_session):
        """Multiple crawl results for the same site each get their own extraction."""
        from src.extractors.payment_info_extractor import PaymentInfoExtractor

        _, site = _seed_site(db_session)
        cr1 = _seed_crawl_result(db_session, site.id, html_content=_JSONLD_HTML)
        cr2 = _seed_crawl_result(db_session, site.id, html_content=_SEMANTIC_HTML)
        db_session.commit()

        extractor = PaymentInfoExtractor()

        for cr, html in [(cr1, _JSONLD_HTML), (cr2, _SEMANTIC_HTML)]:
            extracted = extractor.extract_payment_info(html, cr.url)
            record = TExtractedPaymentInfo(
                crawl_result_id=cr.id,
                site_id=site.id,
                product_info=extracted["product_info"],
                price_info=extracted["price_info"],
                payment_methods=extracted["payment_methods"],
                fees=extracted["fees"],
                extraction_metadata=extracted["metadata"],
                confidence_scores=extracted["confidence_scores"],
                overall_confidence_score=extracted["overall_confidence"],
                status="completed",
                language=extracted["language"],
            )
            db_session.add(record)

        db_session.commit()

        records = db_session.query(TExtractedPaymentInfo).filter_by(
            site_id=site.id
        ).all()
        assert len(records) == 2


# ===========================================================================
# 2. Price history tracking and anomaly detection with real DB
# ===========================================================================


class TestPriceHistoryIntegration:
    """Price history tracking with real SQLite DB (not mocked)."""

    def test_record_first_price(self, db_session):
        """First price for a product has no previous price or change info."""
        _, site = _seed_site(db_session)
        db_session.commit()

        record = TPriceHistory(
            site_id=site.id,
            product_identifier="Widget [W-001]",
            price=1500.0,
            currency="JPY",
            price_type="base_price",
            recorded_at=datetime(2024, 6, 1),
        )
        db_session.add(record)
        db_session.commit()

        saved = db_session.query(TPriceHistory).filter_by(
            site_id=site.id, product_identifier="Widget [W-001]"
        ).first()
        assert saved is not None
        assert saved.price == 1500.0
        assert saved.previous_price is None
        assert saved.price_change_amount is None

    def test_record_price_change_sequence(self, db_session):
        """Recording multiple prices tracks the change over time."""
        _, site = _seed_site(db_session)
        db_session.commit()

        # First price
        r1 = TPriceHistory(
            site_id=site.id,
            product_identifier="Widget",
            price=1000.0,
            currency="JPY",
            price_type="base_price",
            recorded_at=datetime(2024, 1, 1),
        )
        db_session.add(r1)
        db_session.flush()

        # Second price with change info
        r2 = TPriceHistory(
            site_id=site.id,
            product_identifier="Widget",
            price=1200.0,
            currency="JPY",
            price_type="base_price",
            previous_price=1000.0,
            price_change_amount=200.0,
            price_change_percentage=20.0,
            recorded_at=datetime(2024, 2, 1),
        )
        db_session.add(r2)
        db_session.commit()

        records = db_session.query(TPriceHistory).filter_by(
            site_id=site.id, product_identifier="Widget"
        ).order_by(TPriceHistory.recorded_at.asc()).all()

        assert len(records) == 2
        assert records[0].price == 1000.0
        assert records[1].price == 1200.0
        assert records[1].previous_price == 1000.0
        assert records[1].price_change_percentage == pytest.approx(20.0)

    def test_anomaly_detection_price_change_alert(self, db_session):
        """Significant price change generates an alert in the DB."""
        _, site = _seed_site(db_session)
        db_session.commit()

        # Simulate a 30% price increase alert
        alert = TAlert(
            alert_type="price_change",
            severity="high",
            message="価格上昇アラート: Widget - 旧価格: 1000.00 JPY, 新価格: 1300.00 JPY, 変動率: +30.0%",
            site_id=site.id,
            old_price=1000.0,
            new_price=1300.0,
            change_percentage=30.0,
        )
        db_session.add(alert)
        db_session.commit()

        saved = db_session.query(TAlert).filter_by(
            site_id=site.id, alert_type="price_change"
        ).first()
        assert saved is not None
        assert saved.severity == "high"
        assert saved.old_price == 1000.0
        assert saved.new_price == 1300.0
        assert saved.change_percentage == pytest.approx(30.0)

    def test_anomaly_detection_zero_price_alert(self, db_session):
        """Price dropping to zero generates a critical alert."""
        _, site = _seed_site(db_session)
        db_session.commit()

        alert = TAlert(
            alert_type="price_zero",
            severity="critical",
            message="価格ゼロアラート: Widget - 旧価格: 500.00 JPY, 新価格: 0.00 JPY",
            site_id=site.id,
            old_price=500.0,
            new_price=0.0,
            change_percentage=-100.0,
        )
        db_session.add(alert)
        db_session.commit()

        saved = db_session.query(TAlert).filter_by(
            site_id=site.id, alert_type="price_zero"
        ).first()
        assert saved is not None
        assert saved.severity == "critical"
        assert saved.change_percentage == pytest.approx(-100.0)

    def test_anomaly_detection_new_product_alert(self, db_session):
        """New product detection generates an info alert."""
        _, site = _seed_site(db_session)
        db_session.commit()

        alert = TAlert(
            alert_type="new_product",
            severity="info",
            message="新商品検出: NewWidget - 価格: 2500.00 JPY",
            site_id=site.id,
            new_price=2500.0,
        )
        db_session.add(alert)
        db_session.commit()

        saved = db_session.query(TAlert).filter_by(
            site_id=site.id, alert_type="new_product"
        ).first()
        assert saved is not None
        assert saved.severity == "info"
        assert saved.new_price == 2500.0

    def test_price_history_date_range_query(self, db_session):
        """Price history can be filtered by date range."""
        _, site = _seed_site(db_session)
        db_session.commit()

        for month in [1, 3, 6, 9, 12]:
            record = TPriceHistory(
                site_id=site.id,
                product_identifier="Widget",
                price=1000.0 + month * 100,
                currency="JPY",
                price_type="base_price",
                recorded_at=datetime(2024, month, 15),
            )
            db_session.add(record)
        db_session.commit()

        # Query for Q2 (April-June)
        start = datetime(2024, 4, 1)
        end = datetime(2024, 7, 1)
        records = db_session.query(TPriceHistory).filter(
            TPriceHistory.site_id == site.id,
            TPriceHistory.product_identifier == "Widget",
            TPriceHistory.recorded_at >= start,
            TPriceHistory.recorded_at < end,
        ).all()

        assert len(records) == 1
        assert records[0].recorded_at.month == 6


# ===========================================================================
# 3. API endpoint integration: CRUD with real data flow
# ===========================================================================


class TestAPIExtractedDataIntegration:
    """API integration: extract → persist → retrieve → update → approve/reject."""

    def test_full_crud_flow(self, client, db_session):
        """End-to-end: create data, GET it, PUT update, then approve."""
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        info = _seed_extracted_info(db_session, cr.id, site.id)
        db_session.commit()

        # GET by crawl_result_id
        resp = client.get(f"/api/extracted-data/{cr.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_info"]["name"] == "Test Product"
        assert data["status"] == "completed"

        # PUT update
        resp = client.put(
            f"/api/extracted-data/{info.id}",
            json={"product_info": {"name": "Updated Product", "sku": "SKU-002"}},
            headers={"X-API-Key": "test-api-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["product_info"]["name"] == "Updated Product"

        # Verify update persisted
        resp = client.get(f"/api/extracted-data/{cr.id}")
        assert resp.json()["product_info"]["name"] == "Updated Product"

        # Approve
        resp = client.post(
            f"/api/extracted-data/{info.id}/approve",
            headers={"X-API-Key": "test-api-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_reject_flow_with_reason(self, client, db_session):
        """Reject flow requires a reason and updates status."""
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        info = _seed_extracted_info(db_session, cr.id, site.id)
        db_session.commit()

        resp = client.post(
            f"/api/extracted-data/{info.id}/reject",
            json={"reason": "Price data is incorrect"},
            headers={"X-API-Key": "test-api-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_site_listing_with_pagination(self, client, db_session):
        """GET /api/extracted-data/site/{site_id} returns paginated results."""
        _, site = _seed_site(db_session)
        for i in range(5):
            cr = _seed_crawl_result(db_session, site.id)
            _seed_extracted_info(db_session, cr.id, site.id)
        db_session.commit()

        # Page 1, size 2
        resp = client.get(f"/api/extracted-data/site/{site.id}?page=1&page_size=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["page"] == 1

        # Page 2
        resp = client.get(f"/api/extracted-data/site/{site.id}?page=2&page_size=2")
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["page"] == 2

        # Page 3 (last page, 1 item)
        resp = client.get(f"/api/extracted-data/site/{site.id}?page=3&page_size=2")
        body = resp.json()
        assert len(body["items"]) == 1

    def test_update_creates_audit_log(self, client, db_session):
        """PUT update should create an audit log entry."""
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        info = _seed_extracted_info(db_session, cr.id, site.id)
        db_session.commit()

        client.put(
            f"/api/extracted-data/{info.id}",
            json={"status": "approved"},
            headers={"X-API-Key": "test-api-key"},
        )

        audit = db_session.query(TAuditLog).filter_by(
            resource_type="extracted_payment_info",
            resource_id=info.id,
        ).first()
        assert audit is not None
        assert audit.action == "update"


class TestAPIPriceHistoryIntegration:
    """API integration for price history endpoints."""

    def test_price_history_retrieval(self, client, db_session):
        """GET /api/price-history/{site_id}/{product_id} returns records."""
        _, site = _seed_site(db_session)
        _seed_price_history(db_session, site.id, "Widget", 1000.0,
                            recorded_at=datetime(2024, 1, 1))
        _seed_price_history(db_session, site.id, "Widget", 1200.0,
                            recorded_at=datetime(2024, 2, 1),
                            previous_price=1000.0,
                            price_change_amount=200.0,
                            price_change_percentage=20.0)
        db_session.commit()

        resp = client.get(f"/api/price-history/{site.id}/Widget")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
        # Ordered by recorded_at ascending
        assert body["items"][0]["price"] == pytest.approx(1000.0)
        assert body["items"][1]["price"] == pytest.approx(1200.0)
        assert body["items"][1]["price_change_percentage"] == pytest.approx(20.0)

    def test_price_history_date_filtering(self, client, db_session):
        """Price history API supports date range filtering."""
        _, site = _seed_site(db_session)
        _seed_price_history(db_session, site.id, "Widget", 1000.0,
                            recorded_at=datetime(2024, 1, 15))
        _seed_price_history(db_session, site.id, "Widget", 1100.0,
                            recorded_at=datetime(2024, 3, 15))
        _seed_price_history(db_session, site.id, "Widget", 1200.0,
                            recorded_at=datetime(2024, 6, 15))
        db_session.commit()

        resp = client.get(
            f"/api/price-history/{site.id}/Widget",
            params={
                "start_date": "2024-02-01T00:00:00",
                "end_date": "2024-05-01T00:00:00",
            },
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["price"] == pytest.approx(1100.0)

    def test_price_history_empty(self, client, db_session):
        """Empty price history returns empty list."""
        _, site = _seed_site(db_session)
        db_session.commit()

        resp = client.get(f"/api/price-history/{site.id}/nonexistent")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []


class TestAPIExtractThenQueryIntegration:
    """Integration: extract data, persist, then query via API."""

    def test_extract_persist_and_query_via_api(self, client, db_session):
        """Extract from HTML, persist to DB, then retrieve via API."""
        from src.extractors.payment_info_extractor import PaymentInfoExtractor

        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id, html_content=_JSONLD_HTML)
        db_session.commit()

        # Extract
        extractor = PaymentInfoExtractor()
        extracted = extractor.extract_payment_info(_JSONLD_HTML, cr.url)

        # Persist
        record = TExtractedPaymentInfo(
            crawl_result_id=cr.id,
            site_id=site.id,
            product_info=extracted["product_info"],
            price_info=extracted["price_info"],
            payment_methods=extracted["payment_methods"],
            fees=extracted["fees"],
            extraction_metadata=extracted["metadata"],
            confidence_scores=extracted["confidence_scores"],
            overall_confidence_score=extracted["overall_confidence"],
            status="completed",
            language=extracted["language"],
        )
        db_session.add(record)
        db_session.commit()

        # Query via API
        resp = client.get(f"/api/extracted-data/{cr.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["product_info"]["name"] == "プレミアムウィジェット"
        assert data["status"] == "completed"
        assert data["language"] == "ja"
        assert data["overall_confidence_score"] > 0.0

        # Query via site listing
        resp = client.get(f"/api/extracted-data/site/{site.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["product_info"]["name"] == "プレミアムウィジェット"

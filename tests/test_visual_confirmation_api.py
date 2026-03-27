"""
Tests for visual confirmation API endpoints (Task 33.6).

Covers:
- GET /api/crawl/extracted/{crawl_result_id}/visual-confirmation
  - no_data, partial, complete extraction status cases
  - 404 for missing crawl result
- POST /api/crawl/extracted/{crawl_result_id}/manual-input
  - Saves with source="manual" and confidence_score=1.0
  - Creates audit log entry
  - 404 for missing crawl result

Validates: Requirements 29.1, 29.7, 29.8

Uses shared PostgreSQL testcontainers fixtures from conftest.py.
"""

import pytest
from datetime import datetime

from src.models import (
    AuditLog,
    Customer,
    CrawlResult,
    ExtractedPaymentInfo,
    MonitoringSite,
)


# ---------------------------------------------------------------------------
# Helpers – seed data
# ---------------------------------------------------------------------------


def _seed_base(session):
    """Create a customer, site, and crawl result for testing."""
    customer = Customer(name="Test Co", email="test@example.com")
    session.add(customer)
    session.flush()

    site = MonitoringSite(
        customer_id=customer.id,
        name="Test Site",
        url="https://example.com",
    )
    session.add(site)
    session.flush()

    crawl = CrawlResult(
        site_id=site.id,
        url="https://example.com/page",
        html_content="<html><body><h1>Test</h1></body></html>",
        screenshot_path="screenshots/2024/01/1/test.png",
        status_code=200,
    )
    session.add(crawl)
    session.flush()
    return customer, site, crawl


# ===========================================================================
# GET /api/crawl/extracted/{crawl_result_id}/visual-confirmation
# ===========================================================================

class TestVisualConfirmationEndpoint:
    """Tests for the visual confirmation data endpoint."""

    def test_returns_no_data_when_no_records(self, client, db_session):
        """no_data status when no extracted records exist."""
        _customer, _site, crawl = _seed_base(db_session)
        resp = client.get(f"/api/crawl/extracted/{crawl.id}/visual-confirmation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["extraction_status"] == "no_data"
        assert data["html_data"] is None
        assert data["ocr_data"] is None
        assert data["raw_html"] is not None
        assert data["screenshot_url"] is not None

    def test_returns_partial_when_only_product_name(self, client, db_session):
        """partial status when only product_name is populated."""
        _customer, _site, crawl = _seed_base(db_session)
        record = ExtractedPaymentInfo(
            crawl_result_id=crawl.id,
            site_id=_site.id,
            source="html",
            product_info={"name": "テスト商品"},
            price_info=[],
            payment_methods=[],
            fees=[],
            confidence_scores={},
            overall_confidence_score=0.5,
            status="pending",
        )
        db_session.add(record)
        db_session.flush()

        resp = client.get(f"/api/crawl/extracted/{crawl.id}/visual-confirmation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["extraction_status"] == "partial"
        assert data["html_data"] is not None

    def test_returns_complete_when_name_and_price(self, client, db_session):
        """complete status when product_name and price are both populated."""
        _customer, _site, crawl = _seed_base(db_session)
        record = ExtractedPaymentInfo(
            crawl_result_id=crawl.id,
            site_id=_site.id,
            source="html",
            product_info={"name": "テスト商品"},
            price_info=[{"amount": 1000, "currency": "JPY"}],
            payment_methods=[],
            fees=[],
            confidence_scores={},
            overall_confidence_score=0.9,
            status="pending",
        )
        db_session.add(record)
        db_session.flush()

        resp = client.get(f"/api/crawl/extracted/{crawl.id}/visual-confirmation")
        assert resp.status_code == 200
        assert resp.json()["extraction_status"] == "complete"

    def test_returns_404_for_missing_crawl_result(self, client, db_session):
        """404 when crawl_result_id does not exist."""
        _seed_base(db_session)
        resp = client.get("/api/crawl/extracted/999999/visual-confirmation")
        assert resp.status_code == 404


# ===========================================================================
# POST /api/crawl/extracted/{crawl_result_id}/manual-input
# ===========================================================================

class TestManualInputEndpoint:
    """Tests for the manual extraction input endpoint."""

    def test_saves_manual_input_with_source_manual(self, client, db_session):
        """Manual input creates record with source=manual and confidence=1.0."""
        _customer, _site, crawl = _seed_base(db_session)
        payload = {
            "product_name": "手動入力商品",
            "price": "1500",
            "currency": "JPY",
            "payment_methods": ["クレジットカード"],
            "additional_fees": "送料500円",
        }
        resp = client.post(
            f"/api/crawl/extracted/{crawl.id}/manual-input",
            json=payload,
            headers={"X-API-Key": "dev-api-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "manual"
        assert data["overall_confidence_score"] == 1.0
        assert data["status"] == "approved"
        assert data["product_info"]["name"] == "手動入力商品"

    def test_creates_audit_log(self, client, db_session):
        """Manual input creates an audit log entry."""
        _customer, _site, crawl = _seed_base(db_session)
        payload = {"product_name": "テスト", "price": "100"}
        client.post(
            f"/api/crawl/extracted/{crawl.id}/manual-input",
            json=payload,
            headers={"X-API-Key": "dev-api-key"},
        )
        logs = db_session.query(AuditLog).all()
        assert len(logs) == 1
        assert logs[0].action == "manual_input"
        assert logs[0].resource_type == "extracted_payment_info"

    def test_returns_404_for_missing_crawl_result(self, client, db_session):
        """404 when crawl_result_id does not exist."""
        _seed_base(db_session)
        payload = {"product_name": "テスト"}
        resp = client.post(
            "/api/crawl/extracted/999999/manual-input",
            json=payload,
            headers={"X-API-Key": "dev-api-key"},
        )
        assert resp.status_code == 404

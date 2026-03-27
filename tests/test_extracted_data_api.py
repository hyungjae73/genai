"""
Tests for extracted data API endpoints (Task 13.4).

Covers:
- GET /api/extracted-data/{crawl_result_id} - normal and error cases
- GET /api/extracted-data/site/{site_id} - pagination
- PUT /api/extracted-data/{id} - update with auth
- POST /api/extracted-data/{id}/approve - approval workflow
- POST /api/extracted-data/{id}/reject - rejection workflow
- GET /api/price-history/{site_id}/{product_id} - price history with date filtering
- DELETE /api/screenshots/{crawl_result_id} - screenshot deletion
"""

import pytest
from datetime import datetime

from src.models import (
    Customer,
    MonitoringSite,
    CrawlResult,
    ExtractedPaymentInfo,
    PriceHistory,
)


# ---------------------------------------------------------------------------
# Helpers – seed data
# ---------------------------------------------------------------------------


def _seed_site(session):
    """Create a customer + monitoring site, return (customer, site)."""
    customer = Customer(name="Test Customer", email="test@example.com")
    session.add(customer)
    session.flush()

    site = MonitoringSite(
        customer_id=customer.id,
        name="Test Site",
        url="https://example.com",
    )
    session.add(site)
    session.flush()
    return customer, site


def _seed_crawl_result(session, site_id):
    """Create a crawl result for the given site."""
    cr = CrawlResult(
        site_id=site_id,
        url="https://example.com/page",
        html_content="<html></html>",
        status_code=200,
    )
    session.add(cr)
    session.flush()
    return cr



def _seed_extracted_info(
    session,
    crawl_result_id,
    site_id,
    status="pending",
    overall_confidence=0.85,
    extracted_at=None,
):
    """Create an extracted payment info record."""
    record = ExtractedPaymentInfo(
        crawl_result_id=crawl_result_id,
        site_id=site_id,
        product_info={"name": "Test Product", "sku": "SKU-001"},
        price_info=[{"amount": 1000, "currency": "JPY"}],
        payment_methods=[{"method_name": "Credit Card"}],
        fees=[{"fee_type": "shipping", "amount": 500}],
        extraction_metadata={"source": "test"},
        confidence_scores={"product_name": 0.9, "base_price": 0.8},
        overall_confidence_score=overall_confidence,
        status=status,
        language="ja",
        extracted_at=extracted_at or datetime.utcnow(),
    )
    session.add(record)
    session.flush()
    return record


def _seed_price_history(session, site_id, product_id="product-1", price=1000.0, recorded_at=None):
    """Create a price history record."""
    record = PriceHistory(
        site_id=site_id,
        product_identifier=product_id,
        price=price,
        currency="JPY",
        price_type="base_price",
        recorded_at=recorded_at or datetime.utcnow(),
    )
    session.add(record)
    session.flush()
    return record


# ===================================================================
# GET /api/extracted-data/{crawl_result_id} – normal & error cases
# ===================================================================


class TestGetExtractedDataByCrawlResult:
    """Tests for GET /api/extracted-data/{crawl_result_id}."""

    def test_returns_extracted_data(self, client, db_session):
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        info = _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        resp = client.get("/api/extracted-data/{}".format(cr.id))
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == info.id
        assert data["crawl_result_id"] == cr.id
        assert data["site_id"] == site.id
        assert data["product_info"]["name"] == "Test Product"
        assert data["status"] == "pending"
        assert data["language"] == "ja"

    def test_returns_most_recent_record(self, client, db_session):
        """When multiple records exist for a crawl_result_id, return the latest."""
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        _seed_extracted_info(
            db_session, cr.id, site.id,
            overall_confidence=0.5,
            extracted_at=datetime(2024, 1, 1),
        )
        newer = _seed_extracted_info(
            db_session, cr.id, site.id,
            overall_confidence=0.9,
            extracted_at=datetime(2024, 6, 1),
        )
        db_session.flush()

        resp = client.get("/api/extracted-data/{}".format(cr.id))
        assert resp.status_code == 200
        assert resp.json()["id"] == newer.id

    def test_not_found(self, client):
        resp = client.get("/api/extracted-data/99999")
        assert resp.status_code == 404

    def test_response_includes_confidence_scores(self, client, db_session):
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        data = client.get("/api/extracted-data/{}".format(cr.id)).json()
        assert "confidence_scores" in data
        assert data["overall_confidence_score"] == pytest.approx(0.85)


# ===================================================================
# GET /api/extracted-data/site/{site_id} – pagination
# ===================================================================


class TestGetExtractedDataBySite:
    """Tests for GET /api/extracted-data/site/{site_id}."""

    def test_returns_paginated_results(self, client, db_session):
        _, site = _seed_site(db_session)
        for i in range(3):
            cr = _seed_crawl_result(db_session, site.id)
            _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        resp = client.get("/api/extracted-data/site/{}".format(site.id))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["page"] == 1
        assert body["page_size"] == 50
        assert len(body["items"]) == 3

    def test_pagination_page_size(self, client, db_session):
        _, site = _seed_site(db_session)
        for _ in range(5):
            cr = _seed_crawl_result(db_session, site.id)
            _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        resp = client.get("/api/extracted-data/site/{}?page=1&page_size=2".format(site.id))
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["page"] == 1
        assert body["page_size"] == 2

    def test_pagination_second_page(self, client, db_session):
        _, site = _seed_site(db_session)
        for _ in range(5):
            cr = _seed_crawl_result(db_session, site.id)
            _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        resp = client.get("/api/extracted-data/site/{}?page=2&page_size=2".format(site.id))
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["page"] == 2

    def test_pagination_beyond_last_page(self, client, db_session):
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        resp = client.get("/api/extracted-data/site/{}?page=100&page_size=50".format(site.id))
        body = resp.json()
        assert body["total"] == 1
        assert len(body["items"]) == 0

    def test_empty_site(self, client, db_session):
        _, site = _seed_site(db_session)
        db_session.flush()

        resp = client.get("/api/extracted-data/site/{}".format(site.id))
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_invalid_page_param(self, client, db_session):
        """page < 1 should be rejected by FastAPI validation."""
        _, site = _seed_site(db_session)
        db_session.flush()

        resp = client.get("/api/extracted-data/site/{}?page=0".format(site.id))
        assert resp.status_code == 422


# ===================================================================
# PUT /api/extracted-data/{id} – update
# ===================================================================


class TestUpdateExtractedData:
    """Tests for PUT /api/extracted-data/{id}."""

    def test_update_product_info(self, client, db_session):
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        info = _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        resp = client.put(
            "/api/extracted-data/{}".format(info.id),
            json={"product_info": {"name": "Updated Product", "sku": "NEW-SKU"}},
            headers={"X-API-Key": "dev-api-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["product_info"]["name"] == "Updated Product"

    def test_update_status(self, client, db_session):
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        info = _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        resp = client.put(
            "/api/extracted-data/{}".format(info.id),
            json={"status": "approved"},
            headers={"X-API-Key": "dev-api-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_update_not_found(self, client):
        resp = client.put(
            "/api/extracted-data/99999",
            json={"status": "approved"},
            headers={"X-API-Key": "dev-api-key"},
        )
        assert resp.status_code == 404

    def test_update_partial_fields(self, client, db_session):
        """Only the supplied fields should change."""
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        info = _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        resp = client.put(
            "/api/extracted-data/{}".format(info.id),
            json={"fees": [{"fee_type": "tax", "amount": 100}]},
            headers={"X-API-Key": "dev-api-key"},
        )
        assert resp.status_code == 200
        data = resp.json()
        # fees updated
        assert data["fees"][0]["fee_type"] == "tax"
        # product_info unchanged
        assert data["product_info"]["name"] == "Test Product"


# ===================================================================
# POST /api/extracted-data/{id}/approve
# ===================================================================


class TestApproveExtractedData:
    """Tests for POST /api/extracted-data/{id}/approve."""

    def test_approve_success(self, client, db_session):
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        info = _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        resp = client.post(
            "/api/extracted-data/{}/approve".format(info.id),
            headers={"X-API-Key": "dev-api-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_approve_not_found(self, client):
        resp = client.post(
            "/api/extracted-data/99999/approve",
            headers={"X-API-Key": "dev-api-key"},
        )
        assert resp.status_code == 404


# ===================================================================
# POST /api/extracted-data/{id}/reject
# ===================================================================


class TestRejectExtractedData:
    """Tests for POST /api/extracted-data/{id}/reject."""

    def test_reject_success(self, client, db_session):
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        info = _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        resp = client.post(
            "/api/extracted-data/{}/reject".format(info.id),
            json={"reason": "Incorrect price data"},
            headers={"X-API-Key": "dev-api-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_reject_not_found(self, client):
        resp = client.post(
            "/api/extracted-data/99999/reject",
            json={"reason": "bad data"},
            headers={"X-API-Key": "dev-api-key"},
        )
        assert resp.status_code == 404

    def test_reject_requires_reason(self, client, db_session):
        """Missing reason field should fail validation."""
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        info = _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        resp = client.post(
            "/api/extracted-data/{}/reject".format(info.id),
            json={},
            headers={"X-API-Key": "dev-api-key"},
        )
        assert resp.status_code == 422

    def test_reject_empty_reason(self, client, db_session):
        """Empty string reason should fail validation (min_length=1)."""
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        info = _seed_extracted_info(db_session, cr.id, site.id)
        db_session.flush()

        resp = client.post(
            "/api/extracted-data/{}/reject".format(info.id),
            json={"reason": ""},
            headers={"X-API-Key": "dev-api-key"},
        )
        assert resp.status_code == 422


# ===================================================================
# GET /api/price-history/{site_id}/{product_id}
# ===================================================================


class TestGetPriceHistory:
    """Tests for GET /api/price-history/{site_id}/{product_id}."""

    def test_returns_price_history(self, client, db_session):
        _, site = _seed_site(db_session)
        _seed_price_history(db_session, site.id, "prod-1", 1000)
        _seed_price_history(db_session, site.id, "prod-1", 1200)
        db_session.flush()

        resp = client.get("/api/price-history/{}/prod-1".format(site.id))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    def test_empty_history(self, client, db_session):
        _, site = _seed_site(db_session)
        db_session.flush()

        resp = client.get("/api/price-history/{}/nonexistent".format(site.id))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_date_range_filtering(self, client, db_session):
        _, site = _seed_site(db_session)
        _seed_price_history(
            db_session, site.id, "prod-1", 1000,
            recorded_at=datetime(2024, 1, 15),
        )
        _seed_price_history(
            db_session, site.id, "prod-1", 1100,
            recorded_at=datetime(2024, 3, 15),
        )
        _seed_price_history(
            db_session, site.id, "prod-1", 1200,
            recorded_at=datetime(2024, 6, 15),
        )
        db_session.flush()

        resp = client.get(
            "/api/price-history/{}/prod-1".format(site.id),
            params={
                "start_date": "2024-02-01T00:00:00",
                "end_date": "2024-05-01T00:00:00",
            },
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["price"] == pytest.approx(1100)

    def test_filters_by_product_id(self, client, db_session):
        """Records for other products should not appear."""
        _, site = _seed_site(db_session)
        _seed_price_history(db_session, site.id, "prod-A", 500)
        _seed_price_history(db_session, site.id, "prod-B", 700)
        db_session.flush()

        resp = client.get("/api/price-history/{}/prod-A".format(site.id))
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["product_identifier"] == "prod-A"

    def test_ordered_by_recorded_at_asc(self, client, db_session):
        _, site = _seed_site(db_session)
        _seed_price_history(
            db_session, site.id, "prod-1", 1200,
            recorded_at=datetime(2024, 6, 1),
        )
        _seed_price_history(
            db_session, site.id, "prod-1", 1000,
            recorded_at=datetime(2024, 1, 1),
        )
        db_session.flush()

        resp = client.get("/api/price-history/{}/prod-1".format(site.id))
        items = resp.json()["items"]
        assert items[0]["price"] == pytest.approx(1000)
        assert items[1]["price"] == pytest.approx(1200)


# ===================================================================
# DELETE /api/screenshots/{crawl_result_id}
# ===================================================================


class TestDeleteScreenshot:
    """Tests for DELETE /api/screenshots/{crawl_result_id}."""

    def test_delete_screenshot_not_found_crawl_result(self, client):
        resp = client.delete("/api/screenshots/99999")
        assert resp.status_code == 404

    def test_delete_screenshot_no_screenshot(self, client, db_session):
        """Crawl result exists but has no screenshot."""
        _, site = _seed_site(db_session)
        cr = _seed_crawl_result(db_session, site.id)
        db_session.flush()

        resp = client.delete("/api/screenshots/{}".format(cr.id))
        assert resp.status_code == 404

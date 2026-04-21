"""
Unit tests for schedule CRUD API and site settings update endpoints.

Tests cover:
- GET/POST/PUT /api/sites/{site_id}/schedule
- PUT /api/sites/{site_id} with pre_capture_script, crawl_priority, plugin_config
- 404 for non-existent site_id
- 422 for invalid JSON in pre_capture_script
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from src.main import app
from src.database import get_db
from src.models import MonitoringSite, CrawlSchedule


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_site(site_id=1):
    site = MonitoringSite()
    site.id = site_id
    site.customer_id = 1
    site.name = "Test Site"
    site.url = "https://example.com"
    site.is_active = True
    site.compliance_status = "pending"
    site.created_at = datetime(2024, 1, 1)
    site.last_crawled_at = None
    site.category_id = None
    site.pre_capture_script = None
    site.crawl_priority = "normal"
    site.etag = None
    site.last_modified_header = None
    site.plugin_config = None
    return site


def _make_schedule(site_id=1, schedule_id=1):
    sched = CrawlSchedule()
    sched.id = schedule_id
    sched.site_id = site_id
    sched.priority = "normal"
    sched.next_crawl_at = datetime(2024, 6, 1, 12, 0, 0)
    sched.interval_minutes = 1440
    sched.last_etag = None
    sched.last_modified = None
    return sched


class FakeQuery:
    """Chainable query mock."""

    def __init__(self, result=None):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


def _override_db(site=None, schedule=None, *, site_for_schedule=True):
    """Return a get_db override that returns a mock session.

    When both site and schedule are provided, the first query(MonitoringSite)
    returns site, and query(CrawlSchedule) returns schedule.
    """
    def _get_db():
        db = MagicMock()

        def query_side_effect(model):
            if model is MonitoringSite:
                return FakeQuery(site)
            if model is CrawlSchedule:
                return FakeQuery(schedule)
            return FakeQuery(None)

        db.query.side_effect = query_side_effect

        def _refresh(obj):
            # Simulate DB assigning an id on commit/refresh
            if hasattr(obj, 'id') and obj.id is None:
                obj.id = 1

        db.refresh.side_effect = _refresh
        yield db

    return _get_db


@pytest.fixture
def client():
    return TestClient(app, headers={"X-API-Key": "dev-api-key"})


# ---------------------------------------------------------------------------
# Schedule CRUD tests (Task 13.1)
# ---------------------------------------------------------------------------

class TestGetSchedule:
    def test_get_schedule_success(self, client):
        site = _make_site()
        schedule = _make_schedule()
        app.dependency_overrides[get_db] = _override_db(site=site, schedule=schedule)
        try:
            resp = client.get("/api/sites/1/schedule")
            assert resp.status_code == 200
            data = resp.json()
            assert data["site_id"] == 1
            assert data["priority"] == "normal"
            assert data["interval_minutes"] == 1440
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_get_schedule_site_not_found(self, client):
        app.dependency_overrides[get_db] = _override_db(site=None, schedule=None)
        try:
            resp = client.get("/api/sites/9999/schedule")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_get_schedule_not_found(self, client):
        site = _make_site()
        app.dependency_overrides[get_db] = _override_db(site=site, schedule=None)
        try:
            resp = client.get("/api/sites/1/schedule")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestCreateSchedule:
    def test_create_schedule_success(self, client):
        site = _make_site()
        # No existing schedule
        app.dependency_overrides[get_db] = _override_db(site=site, schedule=None)
        try:
            resp = client.post(
                "/api/sites/1/schedule",
                json={"priority": "high", "interval_minutes": 720},
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["priority"] == "high"
            assert data["interval_minutes"] == 720
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_create_schedule_site_not_found(self, client):
        app.dependency_overrides[get_db] = _override_db(site=None, schedule=None)
        try:
            resp = client.post(
                "/api/sites/9999/schedule",
                json={"priority": "normal"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_create_schedule_conflict(self, client):
        site = _make_site()
        existing = _make_schedule()
        app.dependency_overrides[get_db] = _override_db(site=site, schedule=existing)
        try:
            resp = client.post(
                "/api/sites/1/schedule",
                json={"priority": "normal"},
            )
            assert resp.status_code == 409
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_create_schedule_invalid_priority(self, client):
        site = _make_site()
        app.dependency_overrides[get_db] = _override_db(site=site, schedule=None)
        try:
            resp = client.post(
                "/api/sites/1/schedule",
                json={"priority": "invalid_value"},
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_db, None)


class TestUpdateSchedule:
    def test_update_schedule_success(self, client):
        site = _make_site()
        schedule = _make_schedule()
        app.dependency_overrides[get_db] = _override_db(site=site, schedule=schedule)
        try:
            resp = client.put(
                "/api/sites/1/schedule",
                json={"priority": "low", "interval_minutes": 60},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["priority"] == "low"
            assert data["interval_minutes"] == 60
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_update_schedule_site_not_found(self, client):
        app.dependency_overrides[get_db] = _override_db(site=None, schedule=None)
        try:
            resp = client.put(
                "/api/sites/9999/schedule",
                json={"priority": "high"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_update_schedule_not_found(self, client):
        site = _make_site()
        app.dependency_overrides[get_db] = _override_db(site=site, schedule=None)
        try:
            resp = client.put(
                "/api/sites/1/schedule",
                json={"priority": "high"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Site settings update tests (Task 13.2)
# ---------------------------------------------------------------------------

class TestUpdateSiteSettings:
    """Tests for PUT /api/sites/{site_id} with pipeline fields."""

    def test_update_pre_capture_script_valid(self, client):
        site = _make_site()
        app.dependency_overrides[get_db] = _override_db(site=site)
        try:
            resp = client.put(
                "/api/sites/1",
                json={
                    "pre_capture_script": [{"action": "click", "selector": ".btn"}],
                },
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_update_pre_capture_script_invalid_json_string(self, client):
        site = _make_site()
        app.dependency_overrides[get_db] = _override_db(site=site)
        try:
            resp = client.put(
                "/api/sites/1",
                json={"pre_capture_script": "not valid json {{{"},
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_update_pre_capture_script_not_array(self, client):
        site = _make_site()
        app.dependency_overrides[get_db] = _override_db(site=site)
        try:
            resp = client.put(
                "/api/sites/1",
                json={"pre_capture_script": {"action": "click"}},
            )
            assert resp.status_code == 422
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_update_crawl_priority(self, client):
        site = _make_site()
        app.dependency_overrides[get_db] = _override_db(site=site)
        try:
            resp = client.put(
                "/api/sites/1",
                json={"crawl_priority": "high"},
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_update_plugin_config(self, client):
        site = _make_site()
        app.dependency_overrides[get_db] = _override_db(site=site)
        try:
            resp = client.put(
                "/api/sites/1",
                json={"plugin_config": {"disabled": ["ShopifyPlugin"]}},
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_update_site_not_found(self, client):
        app.dependency_overrides[get_db] = _override_db(site=None)
        try:
            resp = client.put(
                "/api/sites/9999",
                json={"crawl_priority": "high"},
            )
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_update_pre_capture_script_null_clears(self, client):
        site = _make_site()
        site.pre_capture_script = [{"action": "click", "selector": ".x"}]
        app.dependency_overrides[get_db] = _override_db(site=site)
        try:
            resp = client.put(
                "/api/sites/1",
                json={"pre_capture_script": None},
            )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(get_db, None)

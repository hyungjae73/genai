"""
Unit tests for CrawlContext and VariantCapture dataclasses.

Tests serialization/deserialization, field defaults, and round-trip behavior.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext, VariantCapture


# --- VariantCapture tests ---


class TestVariantCapture:
    def test_basic_creation(self):
        now = datetime(2024, 1, 15, 10, 30, 0)
        vc = VariantCapture(
            variant_name="デフォルト",
            image_path="/screenshots/test.png",
            captured_at=now,
        )
        assert vc.variant_name == "デフォルト"
        assert vc.image_path == "/screenshots/test.png"
        assert vc.captured_at == now
        assert vc.metadata == {}

    def test_creation_with_metadata(self):
        now = datetime(2024, 1, 15, 10, 30, 0)
        vc = VariantCapture(
            variant_name="オプションA",
            image_path="/screenshots/opt_a.png",
            captured_at=now,
            metadata={"precapture_label": "バリアントA"},
        )
        assert vc.metadata == {"precapture_label": "バリアントA"}

    def test_to_dict(self):
        now = datetime(2024, 1, 15, 10, 30, 0)
        vc = VariantCapture(
            variant_name="test",
            image_path="/img.png",
            captured_at=now,
            metadata={"key": "value"},
        )
        d = vc.to_dict()
        assert d["variant_name"] == "test"
        assert d["image_path"] == "/img.png"
        assert d["captured_at"] == "2024-01-15T10:30:00"
        assert d["metadata"] == {"key": "value"}

    def test_from_dict(self):
        data = {
            "variant_name": "test",
            "image_path": "/img.png",
            "captured_at": "2024-01-15T10:30:00",
            "metadata": {"key": "value"},
        }
        vc = VariantCapture.from_dict(data)
        assert vc.variant_name == "test"
        assert vc.image_path == "/img.png"
        assert vc.captured_at == datetime(2024, 1, 15, 10, 30, 0)
        assert vc.metadata == {"key": "value"}

    def test_from_dict_missing_metadata(self):
        data = {
            "variant_name": "test",
            "image_path": "/img.png",
            "captured_at": "2024-01-15T10:30:00",
        }
        vc = VariantCapture.from_dict(data)
        assert vc.metadata == {}

    def test_round_trip(self):
        now = datetime(2024, 1, 15, 10, 30, 0)
        original = VariantCapture(
            variant_name="バリアントA",
            image_path="/screenshots/variant_a.png",
            captured_at=now,
            metadata={"ocr_confidence": 0.95},
        )
        restored = VariantCapture.from_dict(original.to_dict())
        assert restored.variant_name == original.variant_name
        assert restored.image_path == original.image_path
        assert restored.captured_at == original.captured_at
        assert restored.metadata == original.metadata

    def test_from_dict_with_datetime_object(self):
        """from_dict should handle datetime objects directly (not just strings)."""
        now = datetime(2024, 1, 15, 10, 30, 0)
        data = {
            "variant_name": "test",
            "image_path": "/img.png",
            "captured_at": now,
            "metadata": {},
        }
        vc = VariantCapture.from_dict(data)
        assert vc.captured_at == now


# --- CrawlContext tests ---


def _make_site(site_id: int = 1, name: str = "Test Site", url: str = "https://example.com") -> MonitoringSite:
    """Create a minimal MonitoringSite for testing."""
    site = MonitoringSite()
    site.id = site_id
    site.name = name
    site.url = url
    return site


class TestCrawlContext:
    def test_basic_creation(self):
        site = _make_site()
        ctx = CrawlContext(site=site, url="https://example.com/product")
        assert ctx.site is site
        assert ctx.url == "https://example.com/product"
        assert ctx.html_content is None
        assert ctx.screenshots == []
        assert ctx.extracted_data == {}
        assert ctx.violations == []
        assert ctx.evidence_records == []
        assert ctx.errors == []
        assert ctx.metadata == {}

    def test_creation_with_all_fields(self):
        site = _make_site()
        now = datetime(2024, 1, 15, 10, 30, 0)
        screenshots = [
            VariantCapture("default", "/img.png", now, {"key": "val"})
        ]
        ctx = CrawlContext(
            site=site,
            url="https://example.com",
            html_content="<html></html>",
            screenshots=screenshots,
            extracted_data={"price": 1980},
            violations=[{"type": "price_mismatch"}],
            evidence_records=[{"ocr_text": "1980円"}],
            errors=[{"message": "timeout"}],
            metadata={"pagefetcher_etag": "abc123"},
        )
        assert ctx.html_content == "<html></html>"
        assert len(ctx.screenshots) == 1
        assert ctx.extracted_data == {"price": 1980}
        assert len(ctx.violations) == 1
        assert len(ctx.evidence_records) == 1
        assert len(ctx.errors) == 1
        assert ctx.metadata["pagefetcher_etag"] == "abc123"

    def test_to_dict(self):
        site = _make_site(site_id=42)
        ctx = CrawlContext(
            site=site,
            url="https://example.com",
            html_content="<html></html>",
            extracted_data={"price": 1980},
            metadata={"structureddata_empty": False},
        )
        d = ctx.to_dict()
        assert d["site_id"] == 42
        assert d["url"] == "https://example.com"
        assert d["html_content"] == "<html></html>"
        assert d["screenshots"] == []
        assert d["extracted_data"] == {"price": 1980}
        assert d["violations"] == []
        assert d["evidence_records"] == []
        assert d["errors"] == []
        assert d["metadata"] == {"structureddata_empty": False}

    def test_to_dict_with_screenshots(self):
        site = _make_site()
        now = datetime(2024, 1, 15, 10, 30, 0)
        ctx = CrawlContext(
            site=site,
            url="https://example.com",
            screenshots=[
                VariantCapture("default", "/img1.png", now),
                VariantCapture("optionA", "/img2.png", now),
            ],
        )
        d = ctx.to_dict()
        assert len(d["screenshots"]) == 2
        assert d["screenshots"][0]["variant_name"] == "default"
        assert d["screenshots"][1]["variant_name"] == "optionA"

    def test_from_dict_with_site(self):
        site = _make_site(site_id=42)
        data = {
            "site_id": 42,
            "url": "https://example.com",
            "html_content": "<html></html>",
            "screenshots": [],
            "extracted_data": {"price": 1980},
            "violations": [{"type": "mismatch"}],
            "evidence_records": [],
            "errors": [],
            "metadata": {"key": "value"},
        }
        ctx = CrawlContext.from_dict(data, site=site)
        assert ctx.site is site
        assert ctx.url == "https://example.com"
        assert ctx.html_content == "<html></html>"
        assert ctx.extracted_data == {"price": 1980}
        assert len(ctx.violations) == 1
        assert ctx.metadata == {"key": "value"}

    def test_from_dict_without_site_creates_minimal(self):
        data = {
            "site_id": 99,
            "url": "https://example.com",
            "html_content": None,
            "screenshots": [],
            "extracted_data": {},
            "violations": [],
            "evidence_records": [],
            "errors": [],
            "metadata": {},
        }
        ctx = CrawlContext.from_dict(data)
        assert ctx.site.id == 99
        assert ctx.url == "https://example.com"

    def test_from_dict_with_screenshots(self):
        site = _make_site()
        data = {
            "site_id": 1,
            "url": "https://example.com",
            "screenshots": [
                {
                    "variant_name": "default",
                    "image_path": "/img.png",
                    "captured_at": "2024-01-15T10:30:00",
                    "metadata": {},
                }
            ],
            "extracted_data": {},
            "violations": [],
            "evidence_records": [],
            "errors": [],
            "metadata": {},
        }
        ctx = CrawlContext.from_dict(data, site=site)
        assert len(ctx.screenshots) == 1
        assert ctx.screenshots[0].variant_name == "default"
        assert ctx.screenshots[0].captured_at == datetime(2024, 1, 15, 10, 30, 0)

    def test_round_trip(self):
        site = _make_site(site_id=7)
        now = datetime(2024, 1, 15, 10, 30, 0)
        original = CrawlContext(
            site=site,
            url="https://example.com/product",
            html_content="<html><body>test</body></html>",
            screenshots=[
                VariantCapture("default", "/img1.png", now, {"key": "val"}),
                VariantCapture("optionA", "/img2.png", now),
            ],
            extracted_data={"product_name": "テスト商品", "price": 1980},
            violations=[{"type": "price_mismatch", "variant": "optionA"}],
            evidence_records=[{"ocr_text": "1980円", "confidence": 0.95}],
            errors=[{"message": "timeout", "plugin": "ShopifyPlugin"}],
            metadata={
                "structureddata_empty": False,
                "pagefetcher_etag": "abc123",
            },
        )
        serialized = original.to_dict()
        restored = CrawlContext.from_dict(serialized, site=site)

        assert restored.site.id == original.site.id
        assert restored.url == original.url
        assert restored.html_content == original.html_content
        assert len(restored.screenshots) == len(original.screenshots)
        for orig_s, rest_s in zip(original.screenshots, restored.screenshots):
            assert rest_s.variant_name == orig_s.variant_name
            assert rest_s.image_path == orig_s.image_path
            assert rest_s.captured_at == orig_s.captured_at
            assert rest_s.metadata == orig_s.metadata
        assert restored.extracted_data == original.extracted_data
        assert restored.violations == original.violations
        assert restored.evidence_records == original.evidence_records
        assert restored.errors == original.errors
        assert restored.metadata == original.metadata

    def test_from_dict_missing_optional_fields(self):
        """from_dict should handle missing optional fields gracefully."""
        site = _make_site()
        data = {
            "site_id": 1,
            "url": "https://example.com",
        }
        ctx = CrawlContext.from_dict(data, site=site)
        assert ctx.html_content is None
        assert ctx.screenshots == []
        assert ctx.extracted_data == {}
        assert ctx.violations == []
        assert ctx.evidence_records == []
        assert ctx.errors == []
        assert ctx.metadata == {}

    def test_mutable_defaults_are_independent(self):
        """Each CrawlContext instance should have independent mutable defaults."""
        site = _make_site()
        ctx1 = CrawlContext(site=site, url="https://a.com")
        ctx2 = CrawlContext(site=site, url="https://b.com")
        ctx1.violations.append({"type": "test"})
        ctx1.metadata["key"] = "value"
        assert ctx2.violations == []
        assert ctx2.metadata == {}

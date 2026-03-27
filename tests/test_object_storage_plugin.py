"""
Unit tests for ObjectStoragePlugin.

Feature: crawl-pipeline-architecture
Validates: Requirements 13.1-13.7
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext, VariantCapture
from src.pipeline.plugins.object_storage_plugin import (
    ObjectStoragePlugin,
    build_storage_path,
)


def _make_mock_client(success=True, url_prefix="https://storage.example.com/bucket"):
    """Create a mock storage client."""
    client = MagicMock()
    if success:
        def upload_file(bucket, object_name, file_path):
            return f"{url_prefix}/{object_name}"
        client.upload_file = MagicMock(side_effect=upload_file)
    else:
        client.upload_file = MagicMock(side_effect=Exception("Upload failed"))
    return client


def _make_ctx(screenshots=None, evidence_records=None):
    """Helper to build a CrawlContext."""
    site = MonitoringSite(id=42, name="Test Site", url="https://example.com")
    ctx = CrawlContext(site=site, url="https://example.com")
    if screenshots:
        ctx.screenshots = screenshots
    if evidence_records:
        ctx.evidence_records = evidence_records
    return ctx


# ------------------------------------------------------------------
# should_run (Req 13.1)
# ------------------------------------------------------------------


class TestShouldRun:
    def test_returns_true_when_screenshots_have_local_paths(self):
        ctx = _make_ctx(screenshots=[
            VariantCapture(variant_name="A", image_path="/tmp/screenshot.png", captured_at=datetime.now()),
        ])
        plugin = ObjectStoragePlugin()
        assert plugin.should_run(ctx) is True

    def test_returns_true_when_evidence_has_local_paths(self):
        ctx = _make_ctx(evidence_records=[
            {"screenshot_path": "/tmp/evidence.png", "roi_image_path": None},
        ])
        plugin = ObjectStoragePlugin()
        assert plugin.should_run(ctx) is True

    def test_returns_false_when_no_local_paths(self):
        ctx = _make_ctx(screenshots=[
            VariantCapture(variant_name="A", image_path="https://storage.com/img.png", captured_at=datetime.now()),
        ])
        plugin = ObjectStoragePlugin()
        assert plugin.should_run(ctx) is False

    def test_returns_false_when_empty(self):
        ctx = _make_ctx()
        plugin = ObjectStoragePlugin()
        assert plugin.should_run(ctx) is False

    def test_returns_true_for_roi_image_path(self):
        ctx = _make_ctx(evidence_records=[
            {"screenshot_path": "https://already.uploaded.com/img.png", "roi_image_path": "/tmp/roi.png"},
        ])
        plugin = ObjectStoragePlugin()
        assert plugin.should_run(ctx) is True


# ------------------------------------------------------------------
# execute — successful upload (Req 13.2, 13.5)
# ------------------------------------------------------------------


class TestExecuteSuccess:
    @pytest.mark.asyncio
    async def test_replaces_screenshot_path_with_url(self):
        """Req 13.5: アップロード成功時はストレージ URL に置換。"""
        client = _make_mock_client(success=True)
        ctx = _make_ctx(screenshots=[
            VariantCapture(variant_name="A", image_path="/tmp/screenshot.png", captured_at=datetime.now()),
        ])

        plugin = ObjectStoragePlugin(storage_client=client)
        result = await plugin.execute(ctx)

        assert result.screenshots[0].image_path.startswith("https://")
        assert "screenshot.png" in result.screenshots[0].image_path
        assert result.metadata["objectstorage_upload_count"] == 1

    @pytest.mark.asyncio
    async def test_replaces_evidence_paths_with_urls(self):
        client = _make_mock_client(success=True)
        ctx = _make_ctx(evidence_records=[
            {"screenshot_path": "/tmp/evidence.png", "roi_image_path": "/tmp/roi.png"},
        ])

        plugin = ObjectStoragePlugin(storage_client=client)
        result = await plugin.execute(ctx)

        assert result.evidence_records[0]["screenshot_path"].startswith("https://")
        assert result.evidence_records[0]["roi_image_path"].startswith("https://")
        assert result.metadata["objectstorage_upload_count"] == 2

    @pytest.mark.asyncio
    async def test_skips_already_uploaded_paths(self):
        client = _make_mock_client(success=True)
        ctx = _make_ctx(screenshots=[
            VariantCapture(variant_name="A", image_path="https://already.uploaded.com/img.png", captured_at=datetime.now()),
        ])

        plugin = ObjectStoragePlugin(storage_client=client)
        result = await plugin.execute(ctx)

        # Should not upload already-uploaded files
        client.upload_file.assert_not_called()
        assert result.screenshots[0].image_path == "https://already.uploaded.com/img.png"


# ------------------------------------------------------------------
# execute — upload failure (Req 13.6)
# ------------------------------------------------------------------


class TestExecuteFailure:
    @pytest.mark.asyncio
    async def test_keeps_local_path_on_failure(self):
        """Req 13.6: アップロード失敗時はローカルパスを維持。"""
        client = _make_mock_client(success=False)
        ctx = _make_ctx(screenshots=[
            VariantCapture(variant_name="A", image_path="/tmp/screenshot.png", captured_at=datetime.now()),
        ])

        plugin = ObjectStoragePlugin(storage_client=client)
        result = await plugin.execute(ctx)

        # Local path should be preserved
        assert result.screenshots[0].image_path == "/tmp/screenshot.png"
        assert result.metadata["objectstorage_error_count"] == 1
        assert len(result.errors) >= 1

    @pytest.mark.asyncio
    async def test_keeps_evidence_local_path_on_failure(self):
        client = _make_mock_client(success=False)
        ctx = _make_ctx(evidence_records=[
            {"screenshot_path": "/tmp/evidence.png", "roi_image_path": "/tmp/roi.png"},
        ])

        plugin = ObjectStoragePlugin(storage_client=client)
        result = await plugin.execute(ctx)

        assert result.evidence_records[0]["screenshot_path"] == "/tmp/evidence.png"
        assert result.evidence_records[0]["roi_image_path"] == "/tmp/roi.png"

    @pytest.mark.asyncio
    async def test_no_client_records_error(self):
        ctx = _make_ctx(screenshots=[
            VariantCapture(variant_name="A", image_path="/tmp/screenshot.png", captured_at=datetime.now()),
        ])
        plugin = ObjectStoragePlugin(storage_client=None)
        result = await plugin.execute(ctx)

        assert len(result.errors) == 1
        assert "No storage client" in result.errors[0]["error"]


# ------------------------------------------------------------------
# Storage path format (Req 13.7)
# ------------------------------------------------------------------


class TestStoragePathFormat:
    def test_build_storage_path(self):
        """Req 13.7: {bucket}/{site_id}/{date}/{filename} 形式。"""
        path = build_storage_path("my-bucket", "42", "2024-01-15", "screenshot.png")
        assert path == "my-bucket/42/2024-01-15/screenshot.png"

    def test_path_with_nested_filename(self):
        path = build_storage_path("bucket", "1", "2024-01-01", "roi_crop.png")
        assert path == "bucket/1/2024-01-01/roi_crop.png"


# ------------------------------------------------------------------
# Environment variable configuration (Req 13.3)
# ------------------------------------------------------------------


class TestEnvConfiguration:
    def test_default_values(self):
        plugin = ObjectStoragePlugin()
        assert plugin.endpoint == "localhost:9000"
        assert plugin.bucket == "crawl-evidence"

    def test_custom_env_values(self, monkeypatch):
        monkeypatch.setenv("STORAGE_ENDPOINT", "s3.amazonaws.com")
        monkeypatch.setenv("STORAGE_BUCKET", "prod-bucket")
        monkeypatch.setenv("STORAGE_REGION", "ap-northeast-1")

        plugin = ObjectStoragePlugin()
        assert plugin.endpoint == "s3.amazonaws.com"
        assert plugin.bucket == "prod-bucket"
        assert plugin.region == "ap-northeast-1"


# ------------------------------------------------------------------
# Plugin name
# ------------------------------------------------------------------


class TestPluginName:
    def test_name(self):
        plugin = ObjectStoragePlugin()
        assert plugin.name == "ObjectStoragePlugin"

"""
ObjectStoragePlugin — Reporter ステージ プラグイン。

MinIO SDK で S3 互換ストレージにスクリーンショットと証拠画像をアップロードする。
アップロード成功時はローカルパスをストレージ URL に置換。
失敗時はローカルパスを維持（フォールバック）。

Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin

logger = logging.getLogger(__name__)


class StorageClient(Protocol):
    """Protocol for S3-compatible storage client (dependency injection)."""

    def upload_file(self, bucket: str, object_name: str, file_path: str) -> str:
        """Upload a file and return the storage URL."""
        ...


class ObjectStoragePlugin(CrawlPlugin):
    """S3 互換ストレージにファイルをアップロードするプラグイン。

    MinIO SDK を使用して screenshots と evidence_records の画像を
    オブジェクトストレージにアップロードする。

    環境変数:
        STORAGE_ENDPOINT: ストレージエンドポイント
        STORAGE_ACCESS_KEY: アクセスキー
        STORAGE_SECRET_KEY: シークレットキー
        STORAGE_BUCKET: バケット名
        STORAGE_REGION: リージョン

    パス形式: {bucket}/{site_id}/{date}/{filename}

    Requirements: 13.1-13.7
    """

    def __init__(self, storage_client: StorageClient | None = None):
        """Initialize ObjectStoragePlugin.

        Args:
            storage_client: Optional storage client for dependency injection.
                            If None, creates a real MinIO client from env vars.
        """
        self._storage_client = storage_client

    @property
    def endpoint(self) -> str:
        return os.environ.get("STORAGE_ENDPOINT", "localhost:9000")

    @property
    def access_key(self) -> str:
        return os.environ.get("STORAGE_ACCESS_KEY", "minioadmin")

    @property
    def secret_key(self) -> str:
        return os.environ.get("STORAGE_SECRET_KEY", "minioadmin")

    @property
    def bucket(self) -> str:
        return os.environ.get("STORAGE_BUCKET", "crawl-evidence")

    @property
    def region(self) -> str:
        return os.environ.get("STORAGE_REGION", "us-east-1")

    def should_run(self, ctx: CrawlContext) -> bool:
        """screenshots または evidence_records に画像ファイルパスがある場合に True。"""
        # Check screenshots for image paths
        for screenshot in ctx.screenshots:
            if screenshot.image_path and self._is_local_path(screenshot.image_path):
                return True

        # Check evidence_records for image paths
        for record in ctx.evidence_records:
            if self._has_image_path(record):
                return True

        return False

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """スクリーンショットと証拠画像をオブジェクトストレージにアップロードする。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            ローカルパスをストレージ URL に置換した CrawlContext
        """
        client = self._get_client()
        if client is None:
            ctx.errors.append({
                "plugin": self.name,
                "stage": "reporter",
                "error": "No storage client available",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return ctx

        site_id = str(ctx.site.id)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        upload_count = 0
        error_count = 0

        # Upload screenshots
        for screenshot in ctx.screenshots:
            if screenshot.image_path and self._is_local_path(screenshot.image_path):
                try:
                    storage_url = self._upload_file(
                        client, site_id, date_str, screenshot.image_path
                    )
                    screenshot.image_path = storage_url
                    upload_count += 1
                except Exception as e:
                    error_count += 1
                    logger.warning(
                        "Failed to upload screenshot %s: %s",
                        screenshot.image_path, e,
                    )
                    ctx.errors.append({
                        "plugin": self.name,
                        "stage": "reporter",
                        "error": f"Screenshot upload failed: {e}",
                        "file": screenshot.image_path,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    # Keep local path (fallback) — don't modify image_path

        # Upload evidence record images
        for record in ctx.evidence_records:
            for path_key in ("screenshot_path", "roi_image_path"):
                path_value = record.get(path_key)
                if path_value and self._is_local_path(path_value):
                    try:
                        storage_url = self._upload_file(
                            client, site_id, date_str, path_value
                        )
                        record[path_key] = storage_url
                        upload_count += 1
                    except Exception as e:
                        error_count += 1
                        logger.warning(
                            "Failed to upload evidence %s: %s", path_value, e,
                        )
                        ctx.errors.append({
                            "plugin": self.name,
                            "stage": "reporter",
                            "error": f"Evidence upload failed: {e}",
                            "file": path_value,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                        # Keep local path (fallback)

        ctx.metadata["objectstorage_upload_count"] = upload_count
        ctx.metadata["objectstorage_error_count"] = error_count

        return ctx

    def _upload_file(
        self,
        client: StorageClient,
        site_id: str,
        date_str: str,
        file_path: str,
    ) -> str:
        """Upload a single file and return the storage URL.

        Path format: {bucket}/{site_id}/{date}/{filename}
        """
        filename = Path(file_path).name
        object_name = f"{site_id}/{date_str}/{filename}"
        return client.upload_file(self.bucket, object_name, file_path)

    def _get_client(self) -> StorageClient | None:
        """Get the storage client (injected or default)."""
        return self._storage_client

    def _is_local_path(self, path: str) -> bool:
        """Check if a path is a local file path (not a URL)."""
        if not path:
            return False
        return not path.startswith(("http://", "https://", "s3://"))

    def _has_image_path(self, record: dict[str, Any]) -> bool:
        """Check if an evidence record has local image paths."""
        for key in ("screenshot_path", "roi_image_path"):
            path = record.get(key)
            if path and self._is_local_path(path):
                return True
        return False


def build_storage_path(bucket: str, site_id: str, date_str: str, filename: str) -> str:
    """Build the storage object path.

    Public utility function for testing.

    Args:
        bucket: Storage bucket name
        site_id: Site ID
        date_str: Date string (YYYY-MM-DD)
        filename: Original filename

    Returns:
        Storage path in format {bucket}/{site_id}/{date}/{filename}
    """
    return f"{bucket}/{site_id}/{date_str}/{filename}"

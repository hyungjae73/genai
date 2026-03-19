"""
Storage management module.

Provides StorageManager for automatic cleanup of old screenshots,
storage monitoring, and alert generation when usage is high.
"""

import logging
import os
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.models import Alert
from src.screenshot_manager import ScreenshotManager

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_RETENTION_DAYS = 90
DEFAULT_STORAGE_QUOTA_MB = float(os.getenv("STORAGE_QUOTA_MB", "10240"))  # 10 GB
DEFAULT_ALERT_THRESHOLD_PERCENT = 80.0


class StorageManager:
    """
    Manages screenshot storage lifecycle.

    Responsibilities:
    - Automatic cleanup of screenshots older than the retention period
    - Daily storage usage logging
    - Alert generation when storage usage exceeds threshold
    - Manual deletion support via API
    """

    def __init__(
        self,
        db: Session,
        screenshot_manager: Optional[ScreenshotManager] = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
        storage_quota_mb: float = DEFAULT_STORAGE_QUOTA_MB,
        alert_threshold_percent: float = DEFAULT_ALERT_THRESHOLD_PERCENT,
    ):
        """
        Initialize StorageManager.

        Args:
            db: SQLAlchemy database session.
            screenshot_manager: ScreenshotManager instance (created if None).
            retention_days: Number of days to retain screenshots.
            storage_quota_mb: Storage quota in megabytes.
            alert_threshold_percent: Usage percentage that triggers a warning alert.
        """
        self.db = db
        self.screenshot_manager = screenshot_manager or ScreenshotManager()
        self.retention_days = retention_days
        self.storage_quota_mb = storage_quota_mb
        self.alert_threshold_percent = alert_threshold_percent

    def run_cleanup(self) -> int:
        """
        Delete screenshots older than the retention period.

        Returns:
            Number of files deleted.
        """
        deleted = self.screenshot_manager.cleanup_old_screenshots(
            retention_days=self.retention_days,
        )
        logger.info(
            "Storage cleanup: deleted %d files (retention=%d days)",
            deleted,
            self.retention_days,
        )
        return deleted

    def log_storage_usage(self) -> dict:
        """
        Log current storage usage statistics.

        Returns:
            Storage usage dict with total_files, total_size_bytes, total_size_mb.
        """
        usage = self.screenshot_manager.get_storage_usage()
        logger.info(
            "Daily storage usage: files=%d, size=%.2f MB",
            usage["total_files"],
            usage["total_size_mb"],
        )
        return usage

    def check_storage_alert(self) -> Optional[Alert]:
        """
        Check if storage usage exceeds the alert threshold.

        If usage exceeds the configured percentage of the quota,
        a warning alert is created and persisted.

        Returns:
            Alert object if threshold exceeded, else None.
        """
        usage = self.screenshot_manager.get_storage_usage()
        usage_mb = usage["total_size_mb"]

        if self.storage_quota_mb <= 0:
            return None

        usage_percent = (usage_mb / self.storage_quota_mb) * 100.0

        if usage_percent >= self.alert_threshold_percent:
            message = (
                f"ストレージ使用率警告: {usage_percent:.1f}% "
                f"({usage_mb:.2f} MB / {self.storage_quota_mb:.2f} MB)"
            )
            alert = Alert(
                alert_type="storage_warning",
                severity="warning",
                message=message,
            )
            self.db.add(alert)
            self.db.flush()
            logger.warning("Storage alert: %s", message)
            return alert

        return None

    def run_daily_maintenance(self) -> dict:
        """
        Run all daily maintenance tasks: cleanup, logging, and alert check.

        Returns:
            Summary dict with deleted_count, usage, and alert (if any).
        """
        deleted = self.run_cleanup()
        usage = self.log_storage_usage()
        alert = self.check_storage_alert()

        return {
            "deleted_count": deleted,
            "usage": usage,
            "alert": alert,
        }

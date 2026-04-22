"""
NotificationPlugin - Reporter ステージ通知プラグイン。

AlertPlugin 実行後に動作し、ダークパターン違反検出時に
Slack/メール通知を Celery タスク経由で非同期送信する。

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.5, 3.1, 3.6, 5.2, 6.1, 6.2, 6.3, 8.1, 8.5
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin
from src.pipeline.plugins.duplicate_suppression import DuplicateSuppressionChecker
from src.pipeline.plugins.notification_config import (
    NotificationConfig,
    merge_notification_config,
)
from src.pipeline.plugins.notification_template import NotificationTemplateRenderer

logger = logging.getLogger(__name__)


class NotificationPlugin(CrawlPlugin):
    """Reporter ステージ通知プラグイン。AlertPlugin 実行後に動作。

    通知設定マージ → 重複判定 → テンプレート生成 → Celery タスク投入の
    フローで Slack/メール通知を送信する。

    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5
    """

    def __init__(self, session_factory=None, celery_app=None):
        """Initialize NotificationPlugin.

        Args:
            session_factory: Callable that returns a DB session.
            celery_app: Celery application instance for async task submission.
        """
        self._session_factory = session_factory
        self._celery_app = celery_app
        self._renderer = NotificationTemplateRenderer()

    def should_run(self, ctx: CrawlContext) -> bool:
        """violations >= 1 かつ通知チャネルが1つ以上有効。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            True if violations exist and at least one channel is enabled
        """
        if len(ctx.violations) < 1:
            return False

        try:
            config = self._resolve_config(ctx)
            return config.slack_enabled or config.email_enabled
        except Exception:
            return False

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """通知設定マージ → 重複判定 → テンプレート生成 → Celery タスク投入。

        エラー時は ctx.errors に記録しパイプラインを中断しない。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            metadata に通知結果を追記した CrawlContext
        """
        try:
            # 1. Merge notification config
            config = self._resolve_config(ctx)

            # 2. Extract violation types and filter duplicates
            violation_types = list({
                v.get("violation_type", "unknown")
                for v in ctx.violations
                if v.get("violation_type")
            })

            new_violation_types = violation_types
            if self._session_factory is not None:
                try:
                    checker = DuplicateSuppressionChecker(self._session_factory)
                    new_violation_types = checker.filter_new_violations(
                        site_id=ctx.site.id,
                        violation_types=violation_types,
                        window_hours=config.suppression_window_hours,
                    )
                except Exception as e:
                    logger.error("Duplicate check failed, sending all: %s", e)
                    ctx.errors.append({
                        "plugin": self.name,
                        "stage": "reporter",
                        "error": f"Duplicate check failed: {e}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            # Filter violations to only new ones
            if new_violation_types != violation_types:
                suppressed = set(violation_types) - set(new_violation_types)
                ctx.metadata["notification_suppressed_types"] = list(suppressed)

            new_violations = [
                v for v in ctx.violations
                if v.get("violation_type") in new_violation_types
            ]

            if not new_violations:
                ctx.metadata["notification_status"] = "all_suppressed"
                ctx.metadata["notification_sent"] = False
                return ctx

            # 3. Render templates
            slack_payload = None
            email_subject = None
            email_body = None

            if config.slack_enabled:
                slack_payload = self._renderer.render_slack_payload(
                    new_violations, config, ctx.site
                )

            if config.email_enabled:
                email_subject, email_body = self._renderer.render_email(
                    new_violations, config, ctx.site
                )

            # 4. Build Celery task payload
            task_payload = {
                "site_id": ctx.site.id,
                "violations": new_violations,
                "slack_enabled": config.slack_enabled,
                "slack_payload": slack_payload,
                "slack_webhook_url": config.slack_webhook_url,
                "email_enabled": config.email_enabled,
                "email_subject": email_subject,
                "email_body": email_body,
                "email_recipients": config.email_recipients,
            }

            # 5. Submit to Celery or fallback to sync
            submitted = False
            if self._celery_app is not None:
                try:
                    self._celery_app.send_task(
                        "src.notification_tasks.send_notification",
                        args=[task_payload],
                        queue="notification",
                    )
                    submitted = True
                except Exception as e:
                    logger.warning("Celery submit failed, trying sync: %s", e)
                    ctx.errors.append({
                        "plugin": self.name,
                        "stage": "reporter",
                        "error": f"Celery submit failed: {e}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            if not submitted:
                # Sync fallback
                try:
                    self._sync_send(task_payload)
                except Exception as e:
                    logger.error("Sync send fallback failed: %s", e)
                    ctx.errors.append({
                        "plugin": self.name,
                        "stage": "reporter",
                        "error": f"Sync send fallback failed: {e}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            # 6. Record metadata
            channels = []
            if config.slack_enabled:
                channels.append("slack")
            if config.email_enabled:
                channels.append("email")

            ctx.metadata["notification_sent"] = True
            ctx.metadata["notification_channels"] = channels
            ctx.metadata["notification_violation_count"] = len(new_violations)

        except Exception as e:
            logger.error("NotificationPlugin failed: %s", e)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "reporter",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            ctx.metadata["notification_sent"] = False
            ctx.metadata["notification_error"] = str(e)

        return ctx

    def _resolve_config(self, ctx: CrawlContext) -> NotificationConfig:
        """Resolve notification config from context site.

        Args:
            ctx: Pipeline context

        Returns:
            Merged NotificationConfig
        """
        customer_email = ""
        try:
            customer_email = ctx.site.customer.email
        except (AttributeError, TypeError) as e:
            logger.debug("Customer email not available: %s", e)

        site_config = None
        try:
            site_config = ctx.site.plugin_config
        except AttributeError as e:
            logger.debug("Site plugin_config not available: %s", e)

        return merge_notification_config(customer_email, site_config)

    def _sync_send(self, payload: dict[str, Any]) -> None:
        """Synchronous fallback send when Celery is unavailable.

        Args:
            payload: The notification task payload
        """
        # Import here to avoid circular imports
        try:
            from src.notification_tasks import _send_slack, _send_email

            if payload.get("slack_enabled") and payload.get("slack_webhook_url"):
                _send_slack(payload["slack_webhook_url"], payload["slack_payload"])

            if payload.get("email_enabled") and payload.get("email_recipients"):
                _send_email(
                    payload["email_recipients"],
                    payload["email_subject"],
                    payload["email_body"],
                )
        except ImportError:
            logger.warning("notification_tasks not available for sync fallback")
            raise

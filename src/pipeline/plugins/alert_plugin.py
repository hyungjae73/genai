"""
AlertPlugin — Reporter ステージ プラグイン。

各違反に対して Alert レコードを生成し DB に保存する。
severity は違反の種類に基づいて設定する。

Requirements: 14.1, 14.2, 14.3
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin

logger = logging.getLogger(__name__)


class AlertPlugin(CrawlPlugin):
    """違反に対して Alert レコードを生成するプラグイン。

    各違反に対して1つの Alert レコードを生成する。
    severity は違反の種類に基づいて設定:
    - 価格不一致 (price_mismatch) → "warning"
    - 構造化データ取得失敗 (structured_data_failure) → "info"
    - その他 → "warning" (デフォルト)

    Requirements: 14.1, 14.2, 14.3
    """

    def __init__(self, session_factory=None):
        """Initialize AlertPlugin.

        Args:
            session_factory: Optional callable() -> session for DB access.
                             Useful for dependency injection in tests.
        """
        self._session_factory = session_factory

    def should_run(self, ctx: CrawlContext) -> bool:
        """violations が1件以上存在する場合に True を返す。"""
        return len(ctx.violations) >= 1

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """各違反に対して Alert レコードを生成する。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            metadata にアラート生成結果を追記した CrawlContext
        """
        alerts_generated = []

        try:
            for violation in ctx.violations:
                alert = self._create_alert(violation, ctx)
                alerts_generated.append(alert)

            # Save to DB if session factory is available
            if self._session_factory is not None and alerts_generated:
                try:
                    session = self._session_factory()
                    for alert in alerts_generated:
                        session.add(alert)
                    session.commit()
                    # 審査キューへ自動投入 (要件 2.1, 2.2)
                    try:
                        from src.review.service import ReviewService
                        svc = ReviewService(session)
                        for alert in alerts_generated:
                            svc.enqueue_from_alert(alert)
                    except Exception as review_exc:
                        logger.warning("審査キュー投入に失敗しました: %s", review_exc)
                    session.close()
                except Exception as e:
                    logger.error("AlertPlugin DB save failed: %s", e)
                    ctx.errors.append({
                        "plugin": self.name,
                        "stage": "reporter",
                        "error": f"Alert DB save failed: {e}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            ctx.metadata["alertplugin_alerts_generated"] = len(alerts_generated)
            ctx.metadata["alertplugin_alerts"] = alerts_generated

        except Exception as e:
            logger.error("AlertPlugin failed: %s", e)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "reporter",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return ctx

    def _create_alert(self, violation: dict[str, Any], ctx: CrawlContext) -> dict[str, Any]:
        """Create an Alert record from a violation.

        Args:
            violation: The violation dict
            ctx: Pipeline context for site info

        Returns:
            Alert record dict
        """
        violation_type = violation.get("violation_type", "")
        severity = self._determine_severity(violation_type)

        message = self._build_message(violation)

        return {
            "alert_type": violation_type or "contract_violation",
            "severity": severity,
            "message": message,
            "site_id": ctx.site.id,
            "is_resolved": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "violation_data": violation,
        }

    def _determine_severity(self, violation_type: str) -> str:
        """Determine alert severity based on violation type.

        Args:
            violation_type: The type of violation

        Returns:
            "warning" for price_mismatch, "info" for structured_data_failure,
            "warning" as default
        """
        if violation_type == "structured_data_failure":
            return "info"
        # price_mismatch and all other types default to warning
        return "warning"

    def _build_message(self, violation: dict[str, Any]) -> str:
        """Build a human-readable alert message from a violation.

        Args:
            violation: The violation dict

        Returns:
            Alert message string
        """
        violation_type = violation.get("violation_type", "unknown")

        if violation_type == "price_mismatch":
            variant = violation.get("variant_name", "unknown")
            contract = violation.get("contract_price", "N/A")
            actual = violation.get("actual_price", "N/A")
            source = violation.get("data_source", "unknown")
            return (
                f"Price mismatch for variant '{variant}': "
                f"contract={contract}, actual={actual} (source: {source})"
            )

        if violation_type == "structured_data_failure":
            return f"Structured data extraction failure: {violation.get('error', 'unknown')}"

        return f"Contract violation detected: {violation_type}"

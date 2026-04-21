"""
DuplicateSuppressionChecker - 重複通知抑制チェッカー。

NotificationRecord テーブルを参照し、同一サイト・同一違反種別の通知が
指定時間窓内に送信済みかを判定する。

Requirements: 6.1, 6.2, 6.4, 6.5
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.models import NotificationRecord

logger = logging.getLogger(__name__)


class DuplicateSuppressionChecker:
    """NotificationRecord テーブルを参照し重複通知を判定する。"""

    def __init__(self, session_factory):
        """Initialize DuplicateSuppressionChecker.

        Args:
            session_factory: Callable that returns a DB session.
        """
        self._session_factory = session_factory

    def filter_new_violations(
        self,
        site_id: int,
        violation_types: list[str],
        window_hours: int,
    ) -> list[str]:
        """重複でない violation_type のリストを返す。

        指定時間窓内に status='sent' の NotificationRecord が存在する
        violation_type を除外し、新規の violation_type のみ返す。

        Args:
            site_id: 対象サイト ID
            violation_types: チェック対象の violation_type リスト
            window_hours: 重複判定の時間窓（時間）

        Returns:
            重複でない violation_type のリスト
        """
        if not violation_types:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        session = self._session_factory()
        try:
            existing = (
                session.query(NotificationRecord.violation_type)
                .filter(
                    NotificationRecord.site_id == site_id,
                    NotificationRecord.violation_type.in_(violation_types),
                    NotificationRecord.status == "sent",
                    NotificationRecord.sent_at >= cutoff,
                )
                .distinct()
                .all()
            )
            sent_types = {row[0] for row in existing}
            return [vt for vt in violation_types if vt not in sent_types]
        finally:
            session.close()

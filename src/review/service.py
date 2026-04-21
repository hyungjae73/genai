"""
ReviewService — 手動審査ワークフローのビジネスロジック層

要件: 2.1-2.5, 3.5-3.11, 4.3-4.6, 5.2-5.3, 6.1-6.4, 7.1-7.6, 8.2-8.4, 9.1-9.6
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models import Alert, MonitoringSite, ReviewDecision, ReviewItem, VerificationResult, Violation
from src.review.state_machine import validate_transition
from src.security.audit import AuditLogger

logger = logging.getLogger(__name__)

# Alert severity → ReviewItem priority マッピング
SEVERITY_TO_PRIORITY: dict[str, str] = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
}

# 審査キューに投入する severity
ENQUEUE_SEVERITIES = {"critical", "high", "medium"}


class ReviewService:
    """審査ワークフローのビジネスロジックを担当するサービス層。"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_logger = AuditLogger(db)

    # ------------------------------------------------------------------ #
    # 自動投入
    # ------------------------------------------------------------------ #

    def enqueue_from_alert(self, alert: Alert) -> Optional[ReviewItem]:
        """Alert から ReviewItem を作成してキューに投入する。

        severity が critical/high/medium の場合のみ投入。
        同一 alert_id の重複チェックを行う。
        fake_site タイプは priority を "critical" に上書き。

        要件: 2.1, 2.2, 2.4, 2.5
        """
        if alert.severity not in ENQUEUE_SEVERITIES:
            return None

        # 重複チェック (要件 2.5)
        existing = (
            self.db.query(ReviewItem)
            .filter(ReviewItem.alert_id == alert.id)
            .first()
        )
        if existing:
            return None

        priority = SEVERITY_TO_PRIORITY.get(alert.severity, "medium")

        # fake_site は priority を critical に上書き (要件 2.4)
        if alert.alert_type == "fake_site":
            priority = "critical"

        review_type = "fake_site" if alert.alert_type == "fake_site" else "violation"

        item = ReviewItem(
            alert_id=alert.id,
            site_id=alert.site_id,
            review_type=review_type,
            status="pending",
            priority=priority,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def enqueue_from_dark_pattern(
        self, site_id: int, alert: Alert, score: float
    ) -> Optional[ReviewItem]:
        """ダークパターン検出時に ReviewItem を作成する。

        dark_pattern_score >= 0.7 の場合のみ投入。

        要件: 2.3
        """
        if score < 0.7:
            return None

        # 重複チェック
        if alert is not None:
            existing = (
                self.db.query(ReviewItem)
                .filter(ReviewItem.alert_id == alert.id)
                .first()
            )
            if existing:
                return None

        priority = SEVERITY_TO_PRIORITY.get(
            alert.severity if alert else "medium", "medium"
        )

        item = ReviewItem(
            alert_id=alert.id if alert else None,
            site_id=site_id,
            review_type="dark_pattern",
            status="pending",
            priority=priority,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    # ------------------------------------------------------------------ #
    # 一次審査
    # ------------------------------------------------------------------ #

    def assign_reviewer(
        self, review_item_id: int, reviewer_id: int, username: str
    ) -> ReviewItem:
        """審査案件に担当者を割り当て、status を in_review に遷移する。

        要件: 3.5, 10.1
        """
        item = self._get_item_or_404(review_item_id)

        if not validate_transition(item.status, "in_review"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"ステータス '{item.status}' から 'in_review' への遷移は許可されていません",
            )

        item.status = "in_review"
        item.assigned_to = reviewer_id
        item.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(item)

        self.audit_logger.log(
            user=username,
            action="assign",
            resource_type="review_item",
            resource_id=review_item_id,
            details={"reviewer_id": reviewer_id},
        )
        return item

    def decide_primary(
        self,
        review_item_id: int,
        decision: str,
        comment: str,
        reviewer_id: int,
        username: str,
    ) -> ReviewDecision:
        """一次審査判定を実行する。approved/rejected/escalated。

        要件: 3.7-3.11, 5.2, 5.3
        """
        item = self._get_item_or_404(review_item_id)

        if not validate_transition(item.status, decision):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"ステータス '{item.status}' から '{decision}' への遷移は許可されていません",
            )

        item.status = decision
        item.updated_at = datetime.utcnow()

        record = ReviewDecision(
            review_item_id=review_item_id,
            reviewer_id=reviewer_id,
            decision=decision,
            comment=comment,
            review_stage="primary",
            decided_at=datetime.utcnow(),
        )
        self.db.add(record)

        # Alert 更新 (要件 6.1, 6.2)
        self._update_alert_resolution(item, decision)

        self.db.commit()
        self.db.refresh(record)

        self.audit_logger.log(
            user=username,
            action="decide" if decision != "escalated" else "escalate",
            resource_type="review_item",
            resource_id=review_item_id,
            details={"decision": decision, "review_stage": "primary"},
        )

        # 通知連携 (要件 6.3, 6.4)
        self._send_decision_notification(item, decision)

        return record

    def decide_secondary(
        self,
        review_item_id: int,
        decision: str,
        comment: str,
        reviewer_id: int,
        username: str,
    ) -> ReviewDecision:
        """二次審査判定を実行する。approved/rejected のみ。

        要件: 4.3-4.6, 5.2, 5.3
        """
        item = self._get_item_or_404(review_item_id)

        if not validate_transition(item.status, decision):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"ステータス '{item.status}' から '{decision}' への遷移は許可されていません",
            )

        item.status = decision
        item.updated_at = datetime.utcnow()

        record = ReviewDecision(
            review_item_id=review_item_id,
            reviewer_id=reviewer_id,
            decision=decision,
            comment=comment,
            review_stage="secondary",
            decided_at=datetime.utcnow(),
        )
        self.db.add(record)

        # Alert 更新 (要件 6.1, 6.2)
        self._update_alert_resolution(item, decision)

        self.db.commit()
        self.db.refresh(record)

        self.audit_logger.log(
            user=username,
            action="decide",
            resource_type="review_item",
            resource_id=review_item_id,
            details={"decision": decision, "review_stage": "secondary"},
        )

        # 通知連携 (要件 6.3)
        self._send_decision_notification(item, decision)

        return record

    # ------------------------------------------------------------------ #
    # クエリ
    # ------------------------------------------------------------------ #

    def list_reviews(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        review_type: Optional[str] = None,
        assigned_to: Optional[int] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ReviewItem], int]:
        """フィルタリング + ソート + ページネーション付き一覧取得。

        要件: 7.1-7.6
        """
        from src.models import ReviewItem as RI
        from sqlalchemy import case

        # priority の ORDER BY 用 CASE 式（SQLAlchemy 2.x 構文）
        priority_order = case(
            (RI.priority == "critical", 1),
            (RI.priority == "high", 2),
            (RI.priority == "medium", 3),
            (RI.priority == "low", 4),
            else_=5,
        )

        query = self.db.query(RI)

        if status is not None:
            query = query.filter(RI.status == status)
        if priority is not None:
            query = query.filter(RI.priority == priority)
        if review_type is not None:
            query = query.filter(RI.review_type == review_type)
        if assigned_to is not None:
            query = query.filter(RI.assigned_to == assigned_to)

        total = query.count()
        items = (
            query.order_by(priority_order, RI.created_at.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def get_review_detail(self, review_item_id: int) -> dict:
        """統合ビュー: Alert + Violation + VerificationResult + Site + Decisions。

        要件: 3.3, 9.1-9.6
        """
        item = self._get_item_or_404(review_item_id)

        alert: Optional[Alert] = None
        if item.alert_id:
            alert = self.db.query(Alert).filter(Alert.id == item.alert_id).first()

        site = self.db.query(MonitoringSite).filter(MonitoringSite.id == item.site_id).first()

        violation: Optional[Violation] = None
        verification: Optional[VerificationResult] = None

        if alert and alert.violation_id:
            violation = self.db.query(Violation).filter(Violation.id == alert.violation_id).first()

        if item.review_type in ("dark_pattern", "fake_site") and item.site_id:
            verification = (
                self.db.query(VerificationResult)
                .filter(VerificationResult.site_id == item.site_id)
                .order_by(VerificationResult.created_at.desc())
                .first()
            )

        decisions = (
            self.db.query(ReviewDecision)
            .filter(ReviewDecision.review_item_id == review_item_id)
            .order_by(ReviewDecision.decided_at.asc())
            .all()
        )

        return {
            "review_item": item,
            "alert": alert,
            "violation": violation,
            "verification": verification,
            "site": site,
            "decisions": decisions,
        }

    def get_stats(self) -> dict:
        """審査統計情報を返す。

        要件: 8.2-8.4
        """
        from src.models import ReviewItem as RI

        # by_status
        status_counts = (
            self.db.query(RI.status, func.count(RI.id))
            .group_by(RI.status)
            .all()
        )
        by_status = {s: c for s, c in status_counts}
        for s in ("pending", "in_review", "escalated", "approved", "rejected"):
            by_status.setdefault(s, 0)

        # by_priority (pending のみ)
        priority_counts = (
            self.db.query(RI.priority, func.count(RI.id))
            .filter(RI.status == "pending")
            .group_by(RI.priority)
            .all()
        )
        by_priority = {p: c for p, c in priority_counts}

        # by_review_type (pending のみ)
        type_counts = (
            self.db.query(RI.review_type, func.count(RI.id))
            .filter(RI.status == "pending")
            .group_by(RI.review_type)
            .all()
        )
        by_review_type = {t: c for t, c in type_counts}

        return {
            "by_status": by_status,
            "by_priority": by_priority,
            "by_review_type": by_review_type,
        }

    def get_escalated_reviews(
        self, limit: int = 20, offset: int = 0
    ) -> tuple[list[ReviewItem], int]:
        """エスカレーション案件一覧を返す。

        要件: 4.1
        """
        from src.models import ReviewItem as RI

        query = self.db.query(RI).filter(RI.status == "escalated")
        total = query.count()
        items = query.order_by(RI.created_at.asc()).offset(offset).limit(limit).all()
        return items, total

    def get_decisions(self, review_item_id: int) -> list[ReviewDecision]:
        """判定履歴を返す。要件: 5.4"""
        self._get_item_or_404(review_item_id)
        return (
            self.db.query(ReviewDecision)
            .filter(ReviewDecision.review_item_id == review_item_id)
            .order_by(ReviewDecision.decided_at.asc())
            .all()
        )

    # ------------------------------------------------------------------ #
    # 内部ヘルパー
    # ------------------------------------------------------------------ #

    def _get_item_or_404(self, review_item_id: int) -> ReviewItem:
        item = self.db.query(ReviewItem).filter(ReviewItem.id == review_item_id).first()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ReviewItem id={review_item_id} が見つかりません",
            )
        return item

    def _update_alert_resolution(self, item: ReviewItem, decision: str) -> None:
        """approved 時に Alert.is_resolved = True に更新する。要件: 6.1, 6.2"""
        if item.alert_id is None:
            return
        alert = self.db.query(Alert).filter(Alert.id == item.alert_id).first()
        if alert is None:
            return
        if decision == "approved":
            alert.is_resolved = True
        # rejected は False のまま維持

    def _send_decision_notification(self, item: ReviewItem, decision: str) -> None:
        """判定結果に応じた通知を非同期送信する。要件: 6.3, 6.4"""
        try:
            from src.celery_app import celery_app

            if decision == "rejected":
                # 違反確定通知
                celery_app.send_task(
                    "src.notification_tasks.send_notification",
                    args=[{
                        "site_id": item.site_id,
                        "violations": [{"type": item.review_type}],
                        "slack_enabled": True,
                        "email_enabled": True,
                        "email_recipients": [],
                        "notification_type": "violation_confirmed",
                        "review_item_id": item.id,
                    }],
                    queue="notification",
                )
            elif decision == "escalated":
                # admin へのエスカレーション通知
                celery_app.send_task(
                    "src.notification_tasks.send_notification",
                    args=[{
                        "site_id": item.site_id,
                        "violations": [],
                        "slack_enabled": True,
                        "email_enabled": True,
                        "email_recipients": [],
                        "notification_type": "escalation",
                        "review_item_id": item.id,
                    }],
                    queue="notification",
                )
        except Exception as exc:
            # 通知失敗は審査フローを止めない
            logger.warning("通知送信に失敗しました: %s", exc)

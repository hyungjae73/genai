"""
Reviews API — 手動審査ワークフローのエンドポイント

要件: 3.1, 3.2, 3.4, 3.6, 4.1, 4.2, 4.7, 5.4, 7.1-7.6, 8.1, 8.5
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import (
    AlertDetailInReview,
    AssignReviewerRequest,
    DarkPatternDetailInReview,
    FakeSiteDetailInReview,
    PaginatedReviewResponse,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewDetailResponse,
    ReviewItemResponse,
    ReviewStatsResponse,
    SiteBasicInfo,
    ViolationDetailInReview,
)
from src.auth.dependencies import require_role
from src.auth.rbac import Role
from src.database import get_async_db
from src.models import User
from src.review.service import ReviewService

router = APIRouter()


# ------------------------------------------------------------------ #
# 審査キュー一覧
# ------------------------------------------------------------------ #

@router.get("/", response_model=PaginatedReviewResponse)
async def list_reviews(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    review_type: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(Role.REVIEWER, Role.ADMIN)),
) -> PaginatedReviewResponse:
    """審査キュー一覧を取得する。reviewer/admin のみ。"""
    svc = ReviewService(db)
    items, total = await svc.list_reviews(
        status=status,
        priority=priority,
        review_type=review_type,
        assigned_to=assigned_to,
        limit=limit,
        offset=offset,
    )
    return PaginatedReviewResponse(
        items=[ReviewItemResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# ------------------------------------------------------------------ #
# 審査統計
# ------------------------------------------------------------------ #

@router.get("/stats", response_model=ReviewStatsResponse)
async def get_review_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(Role.VIEWER, Role.REVIEWER, Role.ADMIN)),
) -> ReviewStatsResponse:
    """審査統計を取得する。viewer/reviewer/admin。"""
    svc = ReviewService(db)
    stats = await svc.get_stats()
    return ReviewStatsResponse(**stats)


# ------------------------------------------------------------------ #
# エスカレーション案件一覧
# ------------------------------------------------------------------ #

@router.get("/escalated", response_model=PaginatedReviewResponse)
async def list_escalated_reviews(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
) -> PaginatedReviewResponse:
    """エスカレーション案件一覧を取得する。admin のみ。"""
    svc = ReviewService(db)
    items, total = await svc.get_escalated_reviews(limit=limit, offset=offset)
    return PaginatedReviewResponse(
        items=[ReviewItemResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# ------------------------------------------------------------------ #
# 審査案件詳細
# ------------------------------------------------------------------ #

@router.get("/{review_id}", response_model=ReviewDetailResponse)
async def get_review_detail(
    review_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(Role.REVIEWER, Role.ADMIN)),
) -> ReviewDetailResponse:
    """審査案件詳細を取得する。reviewer/admin のみ。"""
    svc = ReviewService(db)
    detail = await svc.get_review_detail(review_id)

    item = detail["review_item"]
    alert = detail["alert"]
    violation = detail["violation"]
    verification = detail["verification"]
    site = detail["site"]
    decisions = detail["decisions"]

    alert_resp = None
    if alert:
        alert_resp = AlertDetailInReview(
            id=alert.id,
            severity=alert.severity,
            message=alert.message,
            alert_type=alert.alert_type,
            created_at=alert.created_at,
            fake_domain=alert.fake_domain,
            domain_similarity_score=alert.domain_similarity_score,
            content_similarity_score=alert.content_similarity_score,
        )

    violation_resp = None
    if violation and item.review_type == "violation":
        violation_resp = ViolationDetailInReview(
            id=violation.id,
            violation_type=violation.violation_type,
            expected_value=violation.expected_value,
            actual_value=violation.actual_value,
        )

    dark_pattern_resp = None
    if verification and item.review_type == "dark_pattern":
        dark_pattern_resp = DarkPatternDetailInReview(
            dark_pattern_score=verification.dark_pattern_score,
            dark_pattern_types=verification.dark_pattern_types,
        )

    fake_site_resp = None
    if alert and item.review_type == "fake_site":
        fake_site_resp = FakeSiteDetailInReview(
            fake_domain=alert.fake_domain,
            domain_similarity_score=alert.domain_similarity_score,
            content_similarity_score=alert.content_similarity_score,
        )

    site_resp = None
    if site:
        site_resp = SiteBasicInfo(id=site.id, name=site.name, url=site.url)

    return ReviewDetailResponse(
        review_item=ReviewItemResponse.model_validate(item),
        alert=alert_resp,
        violation=violation_resp,
        dark_pattern=dark_pattern_resp,
        fake_site=fake_site_resp,
        site=site_resp,
        decisions=[ReviewDecisionResponse.model_validate(d) for d in decisions],
    )


# ------------------------------------------------------------------ #
# 担当者割り当て
# ------------------------------------------------------------------ #

@router.post("/{review_id}/assign", response_model=ReviewItemResponse)
async def assign_reviewer(
    review_id: int,
    body: AssignReviewerRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(Role.REVIEWER, Role.ADMIN)),
) -> ReviewItemResponse:
    """担当者を割り当てる。reviewer/admin のみ。"""
    svc = ReviewService(db)
    item = await svc.assign_reviewer(
        review_item_id=review_id,
        reviewer_id=body.reviewer_id,
        username=current_user.username,
    )
    return ReviewItemResponse.model_validate(item)


# ------------------------------------------------------------------ #
# 一次審査判定
# ------------------------------------------------------------------ #

@router.post("/{review_id}/decide", response_model=ReviewDecisionResponse)
async def decide_primary(
    review_id: int,
    body: ReviewDecisionRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(Role.REVIEWER, Role.ADMIN)),
) -> ReviewDecisionResponse:
    """一次審査判定を実行する。reviewer/admin のみ。"""
    svc = ReviewService(db)
    record = await svc.decide_primary(
        review_item_id=review_id,
        decision=body.decision,
        comment=body.comment,
        reviewer_id=current_user.id,
        username=current_user.username,
    )
    return ReviewDecisionResponse.model_validate(record)


# ------------------------------------------------------------------ #
# 二次審査判定
# ------------------------------------------------------------------ #

@router.post("/{review_id}/final-decide", response_model=ReviewDecisionResponse)
async def decide_secondary(
    review_id: int,
    body: ReviewDecisionRequest,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(Role.ADMIN)),
) -> ReviewDecisionResponse:
    """二次審査判定を実行する。admin のみ。"""
    svc = ReviewService(db)
    record = await svc.decide_secondary(
        review_item_id=review_id,
        decision=body.decision,
        comment=body.comment,
        reviewer_id=current_user.id,
        username=current_user.username,
    )
    return ReviewDecisionResponse.model_validate(record)


# ------------------------------------------------------------------ #
# 判定履歴
# ------------------------------------------------------------------ #

@router.get("/{review_id}/decisions", response_model=list[ReviewDecisionResponse])
async def get_decisions(
    review_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_role(Role.REVIEWER, Role.ADMIN)),
) -> list[ReviewDecisionResponse]:
    """判定履歴を取得する。reviewer/admin のみ。"""
    svc = ReviewService(db)
    decisions = await svc.get_decisions(review_id)
    return [ReviewDecisionResponse.model_validate(d) for d in decisions]

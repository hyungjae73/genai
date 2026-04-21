"""
Pydantic schemas for API request/response models.
"""

from datetime import datetime
from typing import Optional, Any, Literal
from pydantic import BaseModel, ConfigDict, Field


# Monitoring Site schemas
class MonitoringSiteBase(BaseModel):
    """Base schema for monitoring site."""
    customer_id: int
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1)


class MonitoringSiteCreate(MonitoringSiteBase):
    """Schema for creating a monitoring site."""
    monitoring_enabled: bool = True


class MonitoringSiteUpdate(BaseModel):
    """Schema for updating a monitoring site."""
    customer_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[str] = Field(None, min_length=1)
    monitoring_enabled: Optional[bool] = None
    pre_capture_script: Optional[Any] = None
    crawl_priority: Optional[str] = None
    plugin_config: Optional[Any] = None


class MonitoringSiteResponse(BaseModel):
    """Schema for monitoring site response."""
    id: int
    customer_id: int
    name: str
    url: str
    is_active: bool
    last_crawled_at: Optional[datetime] = None
    compliance_status: str = "pending"
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Customer schemas
class CustomerBase(BaseModel):
    """Base schema for customer."""
    name: str = Field(..., min_length=1, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    email: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    is_active: bool = True


class CustomerCreate(CustomerBase):
    """Schema for creating a customer."""
    pass


class CustomerUpdate(BaseModel):
    """Schema for updating a customer."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    company_name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    is_active: Optional[bool] = None


class CustomerResponse(CustomerBase):
    """Schema for customer response."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Contract Condition schemas
class ContractConditionBase(BaseModel):
    """Base schema for contract condition."""
    site_id: int
    prices: dict[str, Any]
    payment_methods: dict[str, Any]
    fees: dict[str, Any]
    subscription_terms: Optional[dict[str, Any]] = None


class ContractConditionCreate(ContractConditionBase):
    """Schema for creating a contract condition."""
    dynamic_fields: Optional[dict[str, Any]] = None
    category_id: Optional[int] = None


class ContractConditionUpdate(BaseModel):
    """Schema for updating a contract condition."""
    prices: Optional[dict[str, Any]] = None
    payment_methods: Optional[dict[str, Any]] = None
    fees: Optional[dict[str, Any]] = None
    subscription_terms: Optional[dict[str, Any]] = None
    dynamic_fields: Optional[dict[str, Any]] = None
    category_id: Optional[int] = None


class ContractConditionResponse(ContractConditionBase):
    """Schema for contract condition response."""
    id: int
    version: int
    is_current: bool
    created_at: datetime
    dynamic_fields: Optional[dict[str, Any]] = None
    category_id: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


# Alert schemas
class AlertResponse(BaseModel):
    """Schema for alert response."""
    id: int
    violation_id: Optional[int]
    alert_type: str
    severity: str
    message: str
    email_sent: bool
    slack_sent: bool
    created_at: datetime
    old_price: Optional[float] = None
    new_price: Optional[float] = None
    change_percentage: Optional[float] = None
    site_name: Optional[str] = None
    violation_type: Optional[str] = None
    is_resolved: bool
    site_id: Optional[int] = None
    fake_domain: Optional[str] = None
    legitimate_domain: Optional[str] = None
    domain_similarity_score: Optional[float] = None
    content_similarity_score: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)


# Monitoring History schemas
class MonitoringHistoryFilter(BaseModel):
    """Schema for filtering monitoring history."""
    site_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    violation_type: Optional[str] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class CrawlResultResponse(BaseModel):
    """Schema for crawl result response."""
    id: int
    site_id: int
    url: str
    status_code: int
    screenshot_path: Optional[str] = None
    crawled_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class CrawlJobResponse(BaseModel):
    """Schema for crawl job initiation response."""
    job_id: str
    status: str = "pending"


class CrawlStatusResponse(BaseModel):
    """Schema for crawl job status response."""
    job_id: str
    status: str  # "pending", "running", "completed", "failed"
    result: Optional[dict] = None  # Changed from CrawlResultResponse to dict for task results


class ViolationResponse(BaseModel):
    """Schema for violation response."""
    id: int
    validation_result_id: int
    violation_type: str
    severity: str
    field_name: str
    expected_value: Any
    actual_value: Any
    detected_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Statistics schemas
class MonitoringStatistics(BaseModel):
    """Schema for monitoring statistics."""
    total_sites: int
    active_sites: int
    total_violations: int
    high_severity_violations: int
    success_rate: float
    last_crawl: Optional[datetime]
    fake_site_alerts: int = 0
    unresolved_fake_site_alerts: int = 0


# Error response schema
class ErrorResponse(BaseModel):
    """Schema for error response."""
    detail: str
    error_code: Optional[str] = None


# Screenshot schemas
class ScreenshotResponse(BaseModel):
    """Schema for screenshot response."""
    id: int
    site_id: int
    site_name: str
    screenshot_type: str  # 'baseline' or 'violation'
    file_path: str
    file_format: str  # 'png' or 'pdf'
    crawled_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ScreenshotUpload(BaseModel):
    """Schema for screenshot upload."""
    site_id: int
    screenshot_type: str  # 'baseline' or 'violation'
    file_format: str  # 'png' or 'pdf'


# Category schemas
class CategoryCreate(BaseModel):
    """Schema for creating a category."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class CategoryResponse(BaseModel):
    """Schema for category response."""
    id: int
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)



# Field type literal for validation
FIELD_TYPE_LITERAL = Literal["text", "number", "currency", "percentage", "date", "boolean", "list"]


# FieldSchema schemas
class FieldSchemaCreate(BaseModel):
    """Schema for creating a field schema."""
    category_id: int
    field_name: str = Field(..., min_length=1, max_length=255)
    field_type: FIELD_TYPE_LITERAL
    is_required: bool = False
    validation_rules: Optional[dict[str, Any]] = None
    display_order: int = 0


class FieldSchemaUpdate(BaseModel):
    """Schema for updating a field schema."""
    field_name: Optional[str] = Field(None, min_length=1, max_length=255)
    field_type: Optional[FIELD_TYPE_LITERAL] = None
    is_required: Optional[bool] = None
    validation_rules: Optional[dict[str, Any]] = None
    display_order: Optional[int] = None


class FieldSchemaResponse(BaseModel):
    """Schema for field schema response."""
    id: int
    category_id: int
    field_name: str
    field_type: str
    is_required: bool
    validation_rules: Optional[dict[str, Any]] = None
    display_order: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FieldSuggestionResponse(BaseModel):
    """Schema for field suggestion response."""
    field_name: str
    field_type: str
    sample_value: Any
    confidence: float


# ExtractedData schemas
class ExtractedDataResponse(BaseModel):
    """Schema for extracted data response."""
    id: int
    screenshot_id: int
    site_id: int
    extracted_fields: dict[str, Any]
    confidence_scores: dict[str, Any]
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractedDataUpdate(BaseModel):
    """Schema for updating extracted data."""
    extracted_fields: Optional[dict[str, Any]] = None
    status: Optional[Literal["pending", "confirmed", "rejected"]] = None


# ------------------------------------------------------------------
# Extracted Payment Info schemas
# ------------------------------------------------------------------

class ExtractedPaymentInfoResponse(BaseModel):
    """Schema for extracted payment info response."""
    id: int
    crawl_result_id: int
    site_id: int
    source: str = "html"
    product_info: Optional[dict[str, Any]] = None
    price_info: Optional[Any] = None
    payment_methods: Optional[Any] = None
    fees: Optional[Any] = None
    metadata: Optional[dict[str, Any]] = None
    confidence_scores: Optional[dict[str, Any]] = None
    overall_confidence_score: Optional[float] = None
    status: str
    language: Optional[str] = None
    extracted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractedPaymentInfoUpdate(BaseModel):
    """Schema for updating extracted payment info fields."""
    product_info: Optional[dict[str, Any]] = None
    price_info: Optional[Any] = None
    payment_methods: Optional[Any] = None
    fees: Optional[Any] = None
    status: Optional[Literal["pending", "approved", "rejected"]] = None


class PaginatedExtractedPaymentInfoResponse(BaseModel):
    """Paginated response for extracted payment info list."""
    items: list[ExtractedPaymentInfoResponse]
    total: int
    page: int
    page_size: int


# ------------------------------------------------------------------
# Price History schemas
# ------------------------------------------------------------------

class PriceHistoryResponse(BaseModel):
    """Schema for a single price history record."""
    id: int
    site_id: int
    product_identifier: str
    price: float
    currency: str
    price_type: str
    previous_price: Optional[float] = None
    price_change_amount: Optional[float] = None
    price_change_percentage: Optional[float] = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PriceHistoryListResponse(BaseModel):
    """Schema for price history list response."""
    items: list[PriceHistoryResponse]
    total: int


# ------------------------------------------------------------------
# Storage management schemas
# ------------------------------------------------------------------

class StorageUsageResponse(BaseModel):
    """Schema for storage usage response."""
    total_files: int
    total_size_bytes: int
    total_size_mb: float


# ------------------------------------------------------------------
# Manual Extraction Input schema
# ------------------------------------------------------------------

class ManualExtractionInput(BaseModel):
    """Schema for manual extraction input from visual confirmation."""
    product_name: Optional[str] = None
    price: Optional[str] = None
    currency: Optional[str] = None
    payment_methods: Optional[list[str]] = None
    additional_fees: Optional[str] = None


# ------------------------------------------------------------------
# Scraping Task schemas (engineering_standards.md compliant)
# ------------------------------------------------------------------

from src.models import ScrapingTaskStatus


class CreateScrapingTaskRequest(BaseModel):
    """
    Request schema for creating a scraping task.

    Boundary defense: target_url is validated as HTTPS/HTTP with length limits.
    Pydantic rejects invalid data at the API boundary — no ValueError deeper in.
    """
    target_url: str = Field(
        ...,
        min_length=10,
        max_length=2048,
        pattern=r"^https?://",
        description="Target URL to scrape (must be http:// or https://)",
    )


class ScrapingTaskResponse(BaseModel):
    """Response schema for a scraping task."""
    id: int
    target_url: str
    status: ScrapingTaskStatus
    result_minio_key: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------
# Notification schemas (Requirements: 9.3, 10.2)
# ------------------------------------------------------------------

class NotificationConfigResponse(BaseModel):
    """Schema for notification config response. Webhook URL is masked."""
    slack_enabled: bool
    slack_webhook_url: Optional[str] = None
    slack_channel: str
    email_enabled: bool
    email_recipients: list[str]
    suppression_window_hours: int


class NotificationConfigUpdate(BaseModel):
    """Schema for updating notification config. All fields optional."""
    slack_enabled: Optional[bool] = None
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    email_enabled: Optional[bool] = None
    additional_email_recipients: Optional[list[str]] = None
    suppression_window_hours: Optional[int] = Field(None, ge=1, le=168)


class NotificationHistoryResponse(BaseModel):
    """Schema for a single notification history record."""
    id: int
    violation_type: str
    channel: str
    recipient: str
    status: str
    sent_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedNotificationHistoryResponse(BaseModel):
    """Paginated response for notification history."""
    items: list[NotificationHistoryResponse]
    total: int
    limit: int
    offset: int


# ------------------------------------------------------------------ #
# 審査ワークフロー スキーマ (manual-review-workflow)
# 要件: 5.5, 9.1-9.6
# ------------------------------------------------------------------ #

class ReviewItemResponse(BaseModel):
    """審査案件レスポンス。"""
    id: int
    alert_id: Optional[int]
    site_id: int
    review_type: str   # "violation" | "dark_pattern" | "fake_site"
    status: str        # "pending" | "in_review" | "approved" | "rejected" | "escalated"
    priority: str      # "critical" | "high" | "medium" | "low"
    assigned_to: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedReviewResponse(BaseModel):
    """ページネーション付き審査案件一覧レスポンス。"""
    items: list[ReviewItemResponse]
    total: int
    limit: int
    offset: int


class ReviewDecisionRequest(BaseModel):
    """審査判定リクエスト。"""
    decision: str
    comment: str = Field(..., min_length=1)


class AssignReviewerRequest(BaseModel):
    """担当者割り当てリクエスト。"""
    reviewer_id: int


class ReviewDecisionResponse(BaseModel):
    """審査判定レスポンス。"""
    id: int
    review_item_id: int
    reviewer_id: int
    decision: str
    comment: str
    review_stage: str  # "primary" | "secondary"
    decided_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertDetailInReview(BaseModel):
    """審査詳細内の Alert 情報。"""
    id: int
    severity: str
    message: str
    alert_type: str
    created_at: datetime
    fake_domain: Optional[str] = None
    domain_similarity_score: Optional[float] = None
    content_similarity_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ViolationDetailInReview(BaseModel):
    """審査詳細内の Violation 情報。"""
    id: int
    violation_type: str
    expected_value: dict
    actual_value: dict

    model_config = ConfigDict(from_attributes=True)


class DarkPatternDetailInReview(BaseModel):
    """審査詳細内のダークパターン情報。"""
    dark_pattern_score: Optional[float]
    dark_pattern_types: Optional[dict]


class FakeSiteDetailInReview(BaseModel):
    """審査詳細内の偽サイト情報。"""
    fake_domain: Optional[str]
    domain_similarity_score: Optional[float]
    content_similarity_score: Optional[float]


class SiteBasicInfo(BaseModel):
    """審査詳細内のサイト基本情報。"""
    id: int
    name: str
    url: str

    model_config = ConfigDict(from_attributes=True)


class ReviewDetailResponse(BaseModel):
    """審査案件詳細レスポンス（統合ビュー）。"""
    review_item: ReviewItemResponse
    alert: Optional[AlertDetailInReview]
    violation: Optional[ViolationDetailInReview]
    dark_pattern: Optional[DarkPatternDetailInReview]
    fake_site: Optional[FakeSiteDetailInReview]
    site: Optional[SiteBasicInfo]
    decisions: list[ReviewDecisionResponse]


class ReviewStatsResponse(BaseModel):
    """審査統計レスポンス。"""
    by_status: dict[str, int]       # {"pending": 5, "in_review": 3, ...}
    by_priority: dict[str, int]     # pending のみ
    by_review_type: dict[str, int]  # pending のみ


# ------------------------------------------------------------------ #
# 検証フロー再構築スキーマ (verification-flow-restructure)
# 要件: 11.1-11.5
# ------------------------------------------------------------------ #

class EvidenceRecordResponse(BaseModel):
    """証拠保全レコードレスポンス。"""
    id: int
    verification_result_id: int
    variant_name: str
    screenshot_path: str
    roi_image_path: Optional[str] = None
    ocr_text: str
    ocr_confidence: float
    evidence_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

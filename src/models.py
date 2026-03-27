"""
SQLAlchemy models for Payment Compliance Monitor.

This module defines the database models for monitoring sites, contract conditions,
crawl results, violations, and alerts.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Customer(Base):
    """
    Customer master model.
    
    Represents a customer/client who owns one or more monitoring sites.
    """
    __tablename__ = "customers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    sites: Mapped[List["MonitoringSite"]] = relationship(
        "MonitoringSite", back_populates="customer", cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_customers_email", "email"),
        Index("ix_customers_is_active", "is_active"),
    )
    
    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, name={self.name}, company={self.company_name})>"


class MonitoringSite(Base):
    """
    Monitoring target site model.
    
    Represents an e-commerce site that is being monitored for compliance.
    """
    __tablename__ = "monitoring_sites"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    compliance_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True
    )
    
    # Pipeline architecture columns (Req 21)
    pre_capture_script: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=None)
    crawl_priority: Mapped[str] = mapped_column(String(20), nullable=False, server_default='normal')
    etag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_modified_header: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    plugin_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=None)
    
    # Relationships
    customer: Mapped["Customer"] = relationship(
        "Customer", back_populates="sites"
    )
    category: Mapped[Optional["Category"]] = relationship(
        "Category", back_populates="sites"
    )
    contract_conditions: Mapped[List["ContractCondition"]] = relationship(
        "ContractCondition", back_populates="site", cascade="all, delete-orphan"
    )
    crawl_results: Mapped[List["CrawlResult"]] = relationship(
        "CrawlResult", back_populates="site", cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_monitoring_sites_customer_id", "customer_id"),
        Index("ix_monitoring_sites_is_active", "is_active"),
        Index("ix_monitoring_sites_compliance_status", "compliance_status"),
    )
    
    @property
    def domain(self) -> str:
        """URLからドメイン名を抽出する。www.プレフィックスを除去。"""
        if not self.url:
            return ""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.url)
            hostname = parsed.hostname or ""
            if hostname.startswith("www."):
                hostname = hostname[4:]
            return hostname
        except Exception:
            return ""

    def __repr__(self) -> str:
        return f"<MonitoringSite(id={self.id}, name={self.name})>"


class ContractCondition(Base):
    """
    Contract condition model.
    
    Stores the agreed-upon payment conditions for a monitoring site.
    Supports versioning to track changes over time.
    """
    __tablename__ = "contract_conditions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("monitoring_sites.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    prices: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payment_methods: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fees: Mapped[dict] = mapped_column(JSONB, nullable=False)
    subscription_terms: Mapped[dict] = mapped_column(JSONB, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=True
    )
    
    # Relationships
    site: Mapped["MonitoringSite"] = relationship(
        "MonitoringSite", back_populates="contract_conditions"
    )
    category: Mapped[Optional["Category"]] = relationship("Category")
    
    # Indexes
    __table_args__ = (
        Index("ix_contract_conditions_site_id", "site_id"),
        Index("ix_contract_conditions_is_current", "is_current"),
        Index("ix_contract_conditions_site_version", "site_id", "version"),
    )
    
    def __repr__(self) -> str:
        return f"<ContractCondition(id={self.id}, site_id={self.site_id}, version={self.version})>"


class CrawlResult(Base):
    """
    Crawl result model.
    
    Stores the raw HTML content and metadata from crawling operations.
    """
    __tablename__ = "crawl_results"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("monitoring_sites.id"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)
    screenshot_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    crawled_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    # Relationships
    site: Mapped["MonitoringSite"] = relationship(
        "MonitoringSite", back_populates="crawl_results"
    )
    extracted_payment_info: Mapped[List["ExtractedPaymentInfo"]] = relationship(
        "ExtractedPaymentInfo", back_populates="crawl_result", cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_crawl_results_site_id", "site_id"),
        Index("ix_crawl_results_crawled_at", "crawled_at"),
        Index("ix_crawl_results_site_crawled", "site_id", "crawled_at"),
    )
    
    def __repr__(self) -> str:
        return f"<CrawlResult(id={self.id}, site_id={self.site_id}, status_code={self.status_code})>"


class Violation(Base):
    """
    Violation model.
    
    Represents a detected violation of contract conditions.
    """
    __tablename__ = "violations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    validation_result_id: Mapped[int] = mapped_column(Integer, nullable=False)
    violation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    actual_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    # Relationships
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="violation", cascade="all, delete-orphan"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_violations_validation_result_id", "validation_result_id"),
        Index("ix_violations_detected_at", "detected_at"),
        Index("ix_violations_severity", "severity"),
        Index("ix_violations_type", "violation_type"),
    )
    
    def __repr__(self) -> str:
        return f"<Violation(id={self.id}, type={self.violation_type}, severity={self.severity})>"


class Alert(Base):
    """
    Alert model.
    
    Stores alert notifications sent for detected violations.
    """
    __tablename__ = "alerts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    violation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("violations.id"), nullable=True
    )
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    site_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("monitoring_sites.id"), nullable=True
    )
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    slack_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    # Price change related fields (for price anomaly alerts)
    old_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    new_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    change_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Fake site detection fields
    fake_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    legitimate_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    domain_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    content_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Relationships
    violation: Mapped["Violation"] = relationship(
        "Violation", back_populates="alerts"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_alerts_violation_id", "violation_id"),
        Index("ix_alerts_created_at", "created_at"),
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_alert_type", "alert_type"),
        Index("ix_alerts_fake_domain", "fake_domain"),
    )
    
    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, type={self.alert_type}, severity={self.severity})>"


class CrawlJob(Base):
    """
    Crawl job tracking model.

    Persists crawl job status in the database instead of relying on
    Redis / Celery result backend for status tracking.
    """
    __tablename__ = "crawl_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("monitoring_sites.id"), nullable=False
    )
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, running, completed, failed
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    site: Mapped["MonitoringSite"] = relationship("MonitoringSite")

    __table_args__ = (
        Index("ix_crawl_jobs_site_id", "site_id"),
        Index("ix_crawl_jobs_status", "status"),
        Index("ix_crawl_jobs_celery_task_id", "celery_task_id"),
    )

    def __repr__(self) -> str:
        return f"<CrawlJob(id={self.id}, site_id={self.site_id}, status={self.status})>"


class ExtractedPaymentInfo(Base):
    """
    Extracted payment information model.
    
    Stores structured payment information extracted from crawled pages,
    including product details, pricing, payment methods, and fees.
    Includes confidence scores for each extracted field.
    """
    __tablename__ = "extracted_payment_info"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crawl_result_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("crawl_results.id"), nullable=False
    )
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("monitoring_sites.id"), nullable=False
    )
    
    # Extraction source: "html" (structured extraction) or "ocr" (screenshot OCR)
    source: Mapped[str] = mapped_column(
        String(10), nullable=False, default="html"
    )
    
    # Extracted data (JSONB format)
    product_info: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    price_info: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    payment_methods: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    fees: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    extraction_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    
    # Confidence scores
    confidence_scores: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    overall_confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Status management
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    
    # Timestamps
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    # Relationships
    crawl_result: Mapped["CrawlResult"] = relationship(
        "CrawlResult", back_populates="extracted_payment_info"
    )
    site: Mapped["MonitoringSite"] = relationship("MonitoringSite")
    
    # Indexes
    __table_args__ = (
        Index("ix_extracted_payment_info_crawl_result_id", "crawl_result_id"),
        Index("ix_extracted_payment_info_site_id", "site_id"),
        Index("ix_extracted_payment_info_extracted_at", "extracted_at"),
        Index("ix_extracted_payment_info_status", "status"),
        Index("ix_extracted_payment_info_site_extracted", "site_id", "extracted_at"),
    )
    
    def get_product_name(self) -> Optional[str]:
        """Get product name from product_info JSONB field."""
        if self.product_info:
            return self.product_info.get("name")
        return None
    
    def get_product_description(self) -> Optional[str]:
        """Get product description from product_info JSONB field."""
        if self.product_info:
            return self.product_info.get("description")
        return None
    
    def get_product_sku(self) -> Optional[str]:
        """Get product SKU from product_info JSONB field."""
        if self.product_info:
            return self.product_info.get("sku")
        return None
    
    def get_base_price(self) -> Optional[dict]:
        """
        Get base price information from price_info JSONB field.
        
        Returns:
            Dictionary containing amount, currency, and price_type, or None if not found.
        """
        if self.price_info and isinstance(self.price_info, list):
            for price in self.price_info:
                if price.get("price_type") == "base_price":
                    return price
        return None
    
    def get_all_prices(self) -> list:
        """
        Get all price information from price_info JSONB field.
        
        Returns:
            List of price dictionaries.
        """
        if self.price_info and isinstance(self.price_info, list):
            return self.price_info
        return []
    
    def get_payment_method_names(self) -> list:
        """
        Get list of payment method names from payment_methods JSONB field.
        
        Returns:
            List of payment method names.
        """
        if self.payment_methods and isinstance(self.payment_methods, list):
            return [pm.get("method_name") for pm in self.payment_methods if pm.get("method_name")]
        return []
    
    def get_total_fees(self) -> float:
        """
        Calculate total fees from fees JSONB field.
        
        Returns:
            Sum of all fee amounts.
        """
        if self.fees and isinstance(self.fees, list):
            return sum(fee.get("amount", 0) for fee in self.fees if isinstance(fee.get("amount"), (int, float)))
        return 0.0
    
    def get_field_confidence(self, field_name: str) -> Optional[float]:
        """
        Get confidence score for a specific field.
        
        Args:
            field_name: Name of the field to get confidence for.
            
        Returns:
            Confidence score (0.0-1.0) or None if not found.
        """
        if self.confidence_scores:
            return self.confidence_scores.get(field_name)
        return None
    
    def __repr__(self) -> str:
        return (
            f"<ExtractedPaymentInfo(id={self.id}, site_id={self.site_id}, "
            f"status={self.status}, confidence={self.overall_confidence_score})>"
        )


class PriceHistory(Base):
    """
    Price history model.
    
    Tracks price changes over time for products on monitored sites.
    Records each price observation with change calculations for time-series analysis.
    """
    __tablename__ = "price_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("monitoring_sites.id"), nullable=False
    )
    product_identifier: Mapped[str] = mapped_column(String(500), nullable=False)
    
    # Price information
    price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    price_type: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Change information
    previous_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    price_change_percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Timestamp
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    # Related information
    extracted_payment_info_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("extracted_payment_info.id"), nullable=True
    )
    
    # Relationships
    site: Mapped["MonitoringSite"] = relationship("MonitoringSite")
    extracted_payment_info: Mapped[Optional["ExtractedPaymentInfo"]] = relationship(
        "ExtractedPaymentInfo"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_price_history_site_product", "site_id", "product_identifier"),
        Index("ix_price_history_recorded_at", "recorded_at"),
        Index("ix_price_history_site_recorded", "site_id", "recorded_at"),
    )
    
    def calculate_price_change(self, new_price: float) -> tuple[float, float]:
        """
        Calculate price change amount and percentage.
        
        Args:
            new_price: The new price to compare against current price.
            
        Returns:
            Tuple of (change_amount, change_percentage).
            change_amount: Absolute difference (new_price - current_price).
            change_percentage: Percentage change ((new_price - current_price) / current_price * 100).
        """
        change_amount = new_price - self.price
        
        if self.price == 0:
            # Avoid division by zero
            change_percentage = 0.0 if new_price == 0 else 100.0
        else:
            change_percentage = (change_amount / self.price) * 100.0
        
        return change_amount, change_percentage
    
    def is_significant_change(self, threshold_percentage: float = 20.0) -> bool:
        """
        Check if the price change is significant based on a threshold.
        
        Args:
            threshold_percentage: Percentage threshold for significant change (default: 20%).
            
        Returns:
            True if absolute price change percentage exceeds threshold, False otherwise.
        """
        if self.price_change_percentage is None:
            return False
        
        return abs(self.price_change_percentage) >= threshold_percentage
    
    def is_price_drop_to_zero(self) -> bool:
        """
        Check if the price dropped to zero.
        
        Returns:
            True if current price is zero and previous price was non-zero, False otherwise.
        """
        return self.price == 0 and self.previous_price is not None and self.previous_price > 0
    
    def get_price_trend(self) -> str:
        """
        Get the price trend direction.
        
        Returns:
            String indicating trend: 'increasing', 'decreasing', 'stable', or 'unknown'.
        """
        if self.price_change_amount is None:
            return "unknown"
        
        if self.price_change_amount > 0:
            return "increasing"
        elif self.price_change_amount < 0:
            return "decreasing"
        else:
            return "stable"
    
    def __repr__(self) -> str:
        return (
            f"<PriceHistory(id={self.id}, site_id={self.site_id}, "
            f"product={self.product_identifier}, price={self.price}, "
            f"change={self.price_change_percentage}%)>"
        )


class AuditLog(Base):
    """
    Audit log model for tracking administrative operations.
    
    Records all management operations for security and compliance purposes.
    """
    __tablename__ = "audit_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[int] = mapped_column(Integer, nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_audit_user', 'user'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_timestamp', 'timestamp'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, user='{self.user}', "
            f"action='{self.action}', resource='{self.resource_type}')>"
        )


class VerificationResult(Base):
    """
    Verification result model.
    
    Stores complete verification data including HTML extraction,
    OCR extraction, discrepancies, and violations.
    """
    __tablename__ = "verification_results"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("monitoring_sites.id"), nullable=False
    )
    
    # Extracted data
    html_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ocr_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Validation results
    html_violations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    ocr_violations: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Comparison results
    discrepancies: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Metadata
    screenshot_path: Mapped[str] = mapped_column(Text, nullable=False)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Pipeline architecture fields (Req 21.4)
    structured_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    structured_data_violations: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    data_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    structured_data_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    evidence_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    # Relationships
    site: Mapped["MonitoringSite"] = relationship("MonitoringSite")
    
    # Indexes
    __table_args__ = (
        Index("ix_verification_results_site_id", "site_id"),
        Index("ix_verification_results_created_at", "created_at"),
        Index("ix_verification_results_status", "status"),
        Index("ix_verification_results_site_created", "site_id", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<VerificationResult(id={self.id}, site_id={self.site_id}, status={self.status})>"


class EvidenceRecord(Base):
    """
    Evidence record model.

    Stores evidence data from crawl pipeline including screenshots,
    ROI images, OCR text, and confidence scores for verification results.
    evidence_type values: 'price_display', 'terms_notice', 'subscription_condition', 'general'
    """
    __tablename__ = "evidence_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    verification_result_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("verification_results.id"), nullable=False
    )
    variant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    screenshot_path: Mapped[str] = mapped_column(String(512), nullable=False)
    roi_image_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ocr_text: Mapped[str] = mapped_column(Text, nullable=False)
    ocr_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    verification_result: Mapped["VerificationResult"] = relationship(
        "VerificationResult", backref="evidence_records"
    )

    # Indexes
    __table_args__ = (
        Index("ix_evidence_records_verification_result_id", "verification_result_id"),
        Index("ix_evidence_records_evidence_type", "evidence_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<EvidenceRecord(id={self.id}, "
            f"verification_result_id={self.verification_result_id}, "
            f"evidence_type={self.evidence_type})>"
        )


class Category(Base):
    """
    Product/Service category model.

    Represents a dynamic category for classifying monitoring sites
    and contract conditions.
    """
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # HEXカラーコード
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    sites: Mapped[List["MonitoringSite"]] = relationship(
        "MonitoringSite", back_populates="category"
    )
    field_schemas: Mapped[List["FieldSchema"]] = relationship(
        "FieldSchema", back_populates="category", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name={self.name})>"


class FieldSchema(Base):
    """
    Field schema model.

    Defines dynamic field definitions per category for monitoring
    data items (name, type, constraints).
    """
    __tablename__ = "field_schemas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categories.id"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    validation_rules: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    category: Mapped["Category"] = relationship(
        "Category", back_populates="field_schemas"
    )

    __table_args__ = (
        Index("ix_field_schemas_category_id", "category_id"),
        UniqueConstraint("category_id", "field_name", name="uq_field_schema_category_field"),
    )

    def __repr__(self) -> str:
        return f"<FieldSchema(id={self.id}, category_id={self.category_id}, field_name={self.field_name})>"


class ExtractedData(Base):
    """
    Extracted data model.

    Stores structured data extracted from screenshots via OCR,
    along with confidence scores and review status.
    """
    __tablename__ = "extracted_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    screenshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("monitoring_sites.id"), nullable=False
    )
    extracted_fields: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence_scores: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_extracted_data_screenshot_id", "screenshot_id"),
        Index("ix_extracted_data_site_id", "site_id"),
    )

    def __repr__(self) -> str:
        return f"<ExtractedData(id={self.id}, screenshot_id={self.screenshot_id}, site_id={self.site_id})>"


class CrawlSchedule(Base):
    """
    Crawl schedule model.

    Stores per-site crawl scheduling configuration including priority,
    interval, and delta crawl headers (ETag/Last-Modified).
    One schedule per site (site_id is unique).
    priority values: 'high', 'normal', 'low'
    """
    __tablename__ = "crawl_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("monitoring_sites.id"), nullable=False, unique=True
    )
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default='normal')
    next_crawl_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    last_etag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_modified: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    site: Mapped["MonitoringSite"] = relationship(
        "MonitoringSite", backref="crawl_schedule"
    )

    # Indexes
    __table_args__ = (
        Index("ix_crawl_schedules_next_crawl_at", "next_crawl_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<CrawlSchedule(id={self.id}, site_id={self.site_id}, "
            f"priority={self.priority}, next_crawl_at={self.next_crawl_at})>"
        )


import enum


class ScrapingTaskStatus(str, enum.Enum):
    """Strict state machine for scraping task lifecycle."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ScrapingTask(Base):
    """
    Tracks Celery-driven web scraping tasks with strict state management.

    State transitions: PENDING → PROCESSING → SUCCESS | FAILED
    """
    __tablename__ = "scraping_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ScrapingTaskStatus.PENDING.value
    )
    result_minio_key: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_scraping_tasks_status", "status"),
        Index("ix_scraping_tasks_target_url_status", "target_url", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<ScrapingTask(id={self.id}, url={self.target_url!r}, "
            f"status={self.status})>"
        )

"""
SQLAlchemy models for Dynamic Compliance Rules and Content Fingerprints.

DynamicComplianceRuleModel: コンプライアンス担当者が自然言語で登録する
動的検出ルール。LLM as a Judge で実行時に判定される。

ContentFingerprintModel: 商品中核ページのコンテンツ特徴量。
Darksite検出の比較元データとして使用。

🚨 CTO Override:
- ルール追加は DB 登録のみ（Pythonファイル不要）
- TF-IDF 廃止 → Dense Vector（all-MiniLM-L6-v2, 384次元）
- Fingerprint は is_canonical_product=True のみ保存
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base

# pgvector 拡張: Vector 型のインポート
# pgvector がインストールされていない環境ではフォールバック
try:
    from pgvector.sqlalchemy import Vector

    PGVECTOR_AVAILABLE = True
except ImportError:
    # pgvector 未インストール時は ARRAY(Float) にフォールバック
    Vector = None
    PGVECTOR_AVAILABLE = False


# ---------------------------------------------------------------------------
# Dynamic Compliance Rule — LLM as a Judge 用ルール定義
# ---------------------------------------------------------------------------


class DynamicComplianceRuleModel(Base):
    """動的コンプライアンスルール。

    コンプライアンス担当者が自然言語プロンプトで登録する。
    DynamicLLMValidatorPlugin が実行時に読み込み、LLM に判定させる。

    🚨 CTO Override: ルール追加のたびに .py ファイルを作成する設計は却下。
    この DB テーブルにレコードを追加するだけで検出項目を拡張可能。
    """

    __tablename__ = "dynamic_compliance_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ルール識別
    rule_name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # LLM プロンプト
    # プレースホルダ: {page_text}, {contract_terms}, {site_url}
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)

    # 違反判定設定
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="warning"
    )  # critical, warning, info
    dark_pattern_category: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="other"
    )
    confidence_threshold: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.7"
    )

    # 適用範囲
    applicable_categories: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # ["subscription", "info_product"] or null (= all)
    applicable_site_ids: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # [1, 2, 3] or null (= all sites)

    # 状態管理
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    execution_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="100"
    )

    # 監査
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Indexes
    __table_args__ = (
        Index("ix_dcr_rule_name", "rule_name"),
        Index("ix_dcr_is_active", "is_active"),
        Index("ix_dcr_severity", "severity"),
        Index("ix_dcr_category", "dark_pattern_category"),
        Index("ix_dcr_execution_order", "execution_order"),
    )

    def __repr__(self) -> str:
        return (
            f"<DynamicComplianceRule(id={self.id}, "
            f"rule_name='{self.rule_name}', "
            f"active={self.is_active})>"
        )


# ---------------------------------------------------------------------------
# Content Fingerprint — Darksite 検出用コンテンツ特徴量
# ---------------------------------------------------------------------------


class ContentFingerprintModel(Base):
    """コンテンツフィンガープリント。

    商品中核ページのテキスト埋め込みベクトル（384次元）と
    画像 pHash を保存する。Darksite 検出の比較元データ。

    🚨 CTO Override:
    - TF-IDF 廃止 → all-MiniLM-L6-v2 Dense Vector（384次元）
    - is_canonical_product=True のみ保存（爆発防止）
    - max_fingerprints_per_site=50、TTL 90日自動削除
    """

    __tablename__ = "content_fingerprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("monitoring_sites.id"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)

    # テキスト特徴量
    # pgvector 利用可能時: Vector(384) 型（ANN検索対応）
    # pgvector 未インストール時: JSONB にフォールバック
    if PGVECTOR_AVAILABLE:
        text_embedding: Mapped[Optional[list]] = mapped_column(
            Vector(384), nullable=True
        )
    else:
        text_embedding: Mapped[Optional[dict]] = mapped_column(
            JSONB, nullable=True
        )  # {"vector": [0.1, 0.2, ...]} as fallback

    text_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256 of normalized text（重複排除用）

    # 画像特徴量
    image_phashes: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # ["abc123", "def456"] — pHash hex strings

    # 商品情報
    product_names: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # ["商品A", "商品B"]
    price_info: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )  # [{"amount": 1000, "currency": "JPY"}]

    # 🚨 CTO Override: 爆発防止フラグ
    is_canonical_product: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # タイムスタンプ
    captured_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Indexes
    __table_args__ = (
        Index("ix_cfp_site_id", "site_id"),
        Index("ix_cfp_text_hash", "text_hash"),
        Index("ix_cfp_is_canonical", "is_canonical_product"),
        Index("ix_cfp_captured_at", "captured_at"),
        Index("ix_cfp_site_canonical", "site_id", "is_canonical_product"),
    )

    def __repr__(self) -> str:
        return (
            f"<ContentFingerprint(id={self.id}, "
            f"site_id={self.site_id}, "
            f"canonical={self.is_canonical_product})>"
        )

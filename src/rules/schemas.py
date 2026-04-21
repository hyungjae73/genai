"""
Pydantic schemas for Dynamic Compliance Rules — LLM as a Judge.

API リクエスト/レスポンス用スキーマと、
LLM Structured Outputs 用の判定結果スキーマを定義する。

🚨 CTO Override 3件反映済み:
1. LLMJudgeVerdict: Chain of Thought 誘発のためフィールド順序を
   reasoning → evidence_text → confidence → compliant に変更
2. Strict Mode: default="" を排除し全フィールド必須化
3. DynamicRuleCreate: {page_text} の Fail-Fast バリデーション追加
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RuleSeverity(str, Enum):
    """違反の重大度。"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class DarkPatternCategory(str, Enum):
    """ダークパターン分類タクソノミー（Req 16）。"""
    VISUAL_DECEPTION = "visual_deception"
    HIDDEN_SUBSCRIPTION = "hidden_subscription"
    SNEAK_INTO_BASKET = "sneak_into_basket"
    DEFAULT_SUBSCRIPTION = "default_subscription"
    CONFIRMSHAMING = "confirmshaming"
    DISTANT_CANCELLATION = "distant_cancellation_terms"
    HIDDEN_FEES = "hidden_fees"
    URGENCY_PATTERN = "urgency_pattern"
    PRICE_MANIPULATION = "price_manipulation"
    MISLEADING_UI = "misleading_ui"
    OTHER = "other"


# ---------------------------------------------------------------------------
# LLM Structured Outputs — Judge の判定結果スキーマ
# ---------------------------------------------------------------------------


class LLMJudgeVerdict(BaseModel):
    """LLM Judge の判定結果（Structured Outputs 用）。

    🚨 CTO Override 1: Chain of Thought 誘発フィールド順序
    LLM は自己回帰モデルのため、結論を先に出力させると推論精度が低下する。
    reasoning（思考）→ evidence_text（証拠）→ confidence（確信度）→ compliant（結論）
    の順序で出力させることで、十分な思考プロセスを経た判定を引き出す。

    🚨 CTO Override 2: Strict Mode 完全必須化
    default="" を排除。全フィールドを Required にすることで、
    LLM がフィールドを欠落させるハルシネーションを防止する。
    """

    model_config = ConfigDict(strict=True)

    # 1. 最初に推論プロセス（思考）を書かせる
    reasoning: str = Field(
        description="判定に至った論理的な推論プロセスと理由を詳細に説明してください。"
    )

    # 2. 次に証拠を抽出させる
    evidence_text: str = Field(
        description="判定根拠となるページ内のテキスト引用。存在しない場合は '該当なし' と記述してください。"
    )

    # 3. 推論に基づき、最終的な確信度を出させる
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="この判定の確信度（0.0=不確実、1.0=確実）"
    )

    # 4. 最後に結論を出させる
    compliant: bool = Field(
        description="最終判定：契約条件に準拠しているか（True=準拠、False=違反）"
    )


# ---------------------------------------------------------------------------
# API Request / Response Schemas
# ---------------------------------------------------------------------------


class DynamicRuleCreate(BaseModel):
    """動的ルール作成リクエスト。"""

    model_config = ConfigDict(strict=True)

    rule_name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    prompt_template: str = Field(
        min_length=10,
        description="LLM に送信するプロンプト。必ず {page_text} を含めること。"
    )
    severity: RuleSeverity = RuleSeverity.WARNING
    dark_pattern_category: DarkPatternCategory = DarkPatternCategory.OTHER
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    applicable_categories: Optional[list[str]] = None
    applicable_site_ids: Optional[list[int]] = None
    execution_order: int = Field(default=100, ge=0)
    created_by: str = Field(min_length=1, max_length=255)

    # 🚨 CTO Override 3: Fail-Fast バリデーション
    @field_validator("prompt_template")
    @classmethod
    def validate_prompt_template_variables(cls, v: str) -> str:
        """プロンプトテンプレートに必須変数 {page_text} が含まれているか検査。"""
        if "{page_text}" not in v:
            raise ValueError(
                "プロンプトテンプレートには必ず '{page_text}' を含める必要があります。"
            )
        return v


class DynamicRuleUpdate(BaseModel):
    """動的ルール更新リクエスト。"""

    model_config = ConfigDict(strict=True)

    description: Optional[str] = None
    prompt_template: Optional[str] = None
    severity: Optional[RuleSeverity] = None
    dark_pattern_category: Optional[DarkPatternCategory] = None
    confidence_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    applicable_categories: Optional[list[str]] = None
    applicable_site_ids: Optional[list[int]] = None
    is_active: Optional[bool] = None
    execution_order: Optional[int] = Field(default=None, ge=0)

    @field_validator("prompt_template")
    @classmethod
    def validate_prompt_template_variables(cls, v: Optional[str]) -> Optional[str]:
        """更新時もプロンプトテンプレートの必須変数を検査。"""
        if v is not None and "{page_text}" not in v:
            raise ValueError(
                "プロンプトテンプレートには必ず '{page_text}' を含める必要があります。"
            )
        return v


class DynamicRuleResponse(BaseModel):
    """動的ルールレスポンス。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_name: str
    description: Optional[str]
    prompt_template: str
    severity: str
    dark_pattern_category: str
    confidence_threshold: float
    applicable_categories: Optional[list[str]]
    applicable_site_ids: Optional[list[int]]
    is_active: bool
    execution_order: int
    created_by: str
    created_at: datetime
    updated_at: datetime


class LLMJudgeResultResponse(BaseModel):
    """LLM Judge 実行結果レスポンス。"""

    model_config = ConfigDict(strict=True)

    rule_name: str
    passed: bool
    violation_type: Optional[str] = None
    severity: str
    llm_confidence: float
    evidence_text: str
    reasoning: str

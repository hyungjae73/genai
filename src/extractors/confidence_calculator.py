"""
Confidence Calculator - 抽出データの信頼度スコアを計算するコンポーネント。

抽出元（構造化データ、セマンティックHTML、正規表現）に基づいて
フィールドごとの信頼度スコアと全体信頼度スコアを計算します。

信頼度スコア範囲:
  - structured_data: 0.85 - 0.95
  - semantic_html:   0.65 - 0.80
  - regex:           0.40 - 0.60

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Base confidence ranges per extraction source
SOURCE_CONFIDENCE_RANGES: Dict[str, tuple] = {
    "structured_data": (0.85, 0.95),
    "semantic_html": (0.65, 0.80),
    "regex": (0.40, 0.60),
}

# Field-specific weight adjustments (higher = more reliable for that source)
FIELD_WEIGHTS: Dict[str, float] = {
    "product_name": 1.0,
    "product_description": 0.8,
    "sku": 1.0,
    "base_price": 1.0,
    "currency": 1.0,
    "price_type": 0.7,
    "availability": 0.6,
    "payment_methods": 0.8,
    "fees": 0.7,
    "metadata": 0.5,
}

# Default weight for fields not in the map
DEFAULT_FIELD_WEIGHT = 0.7


class ConfidenceCalculator:
    """抽出データの信頼度スコアを計算するクラス。"""

    def calculate_confidence_score(
        self,
        extraction_source: str,
        field_name: str,
        value: Any,
    ) -> float:
        """
        単一フィールドの信頼度スコアを計算する。

        Args:
            extraction_source: 抽出元 ("structured_data", "semantic_html", "regex")
            field_name: フィールド名
            value: 抽出された値

        Returns:
            0.0 - 1.0 の信頼度スコア
        """
        if value is None:
            return 0.0

        base_range = SOURCE_CONFIDENCE_RANGES.get(extraction_source)
        if base_range is None:
            logger.warning("Unknown extraction source: %s", extraction_source)
            return 0.0

        low, high = base_range
        field_weight = FIELD_WEIGHTS.get(field_name, DEFAULT_FIELD_WEIGHT)

        # Interpolate within the range based on field weight
        score = low + (high - low) * field_weight

        # Apply value quality adjustments
        score = self._adjust_for_value_quality(score, value)

        return round(min(max(score, 0.0), 1.0), 2)

    def calculate_field_scores(
        self,
        fields: Dict[str, Any],
        extraction_source: str,
    ) -> Dict[str, float]:
        """
        複数フィールドの信頼度スコアを一括計算する。

        Args:
            fields: フィールド名と値の辞書
            extraction_source: 抽出元

        Returns:
            フィールド名と信頼度スコアの辞書
        """
        scores = {}
        for field_name, value in fields.items():
            scores[field_name] = self.calculate_confidence_score(
                extraction_source, field_name, value
            )
        return scores

    def calculate_overall_score(
        self,
        field_scores: Dict[str, float],
    ) -> float:
        """
        フィールドごとの信頼度スコアから全体信頼度スコアを加重平均で計算する。

        Args:
            field_scores: フィールド名と信頼度スコアの辞書

        Returns:
            0.0 - 1.0 の全体信頼度スコア
        """
        if not field_scores:
            return 0.0

        total_weight = 0.0
        weighted_sum = 0.0

        for field_name, score in field_scores.items():
            weight = FIELD_WEIGHTS.get(field_name, DEFAULT_FIELD_WEIGHT)
            weighted_sum += score * weight
            total_weight += weight

        if total_weight == 0.0:
            return 0.0

        return round(weighted_sum / total_weight, 2)

    def _adjust_for_value_quality(self, base_score: float, value: Any) -> float:
        """値の品質に基づいてスコアを微調整する。"""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return 0.0
            # Very short strings are less reliable
            if len(stripped) < 2:
                return base_score * 0.8
        elif isinstance(value, (int, float)):
            # Negative prices are suspicious
            if value < 0:
                return base_score * 0.5
        elif isinstance(value, list):
            if not value:
                return 0.0

        return base_score

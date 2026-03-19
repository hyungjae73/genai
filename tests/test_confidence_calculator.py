"""
Unit tests for ConfidenceCalculator.

Tests cover:
- Confidence scores per extraction source (structured_data, semantic_html, regex)
- Weighted average overall score calculation
- Edge cases (None values, empty inputs, unknown sources, negative numbers)

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

import pytest

from src.extractors.confidence_calculator import (
    ConfidenceCalculator,
    DEFAULT_FIELD_WEIGHT,
    FIELD_WEIGHTS,
    SOURCE_CONFIDENCE_RANGES,
)


@pytest.fixture
def calculator():
    return ConfidenceCalculator()


# ---------------------------------------------------------------------------
# 各抽出元の信頼度スコアテスト (Req 6.1, 6.2, 6.3, 6.4)
# ---------------------------------------------------------------------------

class TestSourceConfidenceScores:
    """抽出元ごとの信頼度スコア範囲を検証する。"""

    def test_structured_data_score_in_range(self, calculator):
        """構造化データの信頼度は 0.85-0.95 の範囲内 (Req 6.2)"""
        score = calculator.calculate_confidence_score("structured_data", "base_price", 1000)
        assert 0.85 <= score <= 0.95

    def test_semantic_html_score_in_range(self, calculator):
        """セマンティックHTMLの信頼度は 0.65-0.80 の範囲内 (Req 6.3)"""
        score = calculator.calculate_confidence_score("semantic_html", "base_price", 1000)
        assert 0.65 <= score <= 0.80

    def test_regex_score_in_range(self, calculator):
        """正規表現の信頼度は 0.40-0.60 の範囲内 (Req 6.4)"""
        score = calculator.calculate_confidence_score("regex", "base_price", 1000)
        assert 0.40 <= score <= 0.60

    def test_structured_data_higher_than_semantic(self, calculator):
        """構造化データのスコアはセマンティックHTMLより高い"""
        sd = calculator.calculate_confidence_score("structured_data", "product_name", "Widget")
        sh = calculator.calculate_confidence_score("semantic_html", "product_name", "Widget")
        assert sd > sh

    def test_semantic_higher_than_regex(self, calculator):
        """セマンティックHTMLのスコアは正規表現より高い"""
        sh = calculator.calculate_confidence_score("semantic_html", "product_name", "Widget")
        rx = calculator.calculate_confidence_score("regex", "product_name", "Widget")
        assert sh > rx

    def test_field_weight_affects_score(self, calculator):
        """フィールド重みが高いほどスコアが高くなる"""
        # product_name weight=1.0, metadata weight=0.5
        high_w = calculator.calculate_confidence_score("structured_data", "product_name", "Widget Pro")
        low_w = calculator.calculate_confidence_score("structured_data", "metadata", {"k": "v"})
        assert high_w > low_w

    def test_unknown_field_uses_default_weight(self, calculator):
        """未知のフィールドはデフォルト重みを使用する"""
        score = calculator.calculate_confidence_score("structured_data", "unknown_field", "val")
        low, high = SOURCE_CONFIDENCE_RANGES["structured_data"]
        expected = round(low + (high - low) * DEFAULT_FIELD_WEIGHT, 2)
        assert score == expected

    def test_calculate_field_scores_returns_all_fields(self, calculator):
        """calculate_field_scores は全フィールドのスコアを返す"""
        fields = {"product_name": "Widget", "base_price": 500, "currency": "JPY"}
        scores = calculator.calculate_field_scores(fields, "structured_data")
        assert set(scores.keys()) == set(fields.keys())
        for v in scores.values():
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# 加重平均計算のテスト (Req 6.6)
# ---------------------------------------------------------------------------

class TestWeightedAverageCalculation:
    """全体信頼度スコアの加重平均計算を検証する。"""

    def test_overall_score_in_valid_range(self, calculator):
        """全体スコアは 0.0-1.0 の範囲内"""
        field_scores = {"product_name": 0.9, "base_price": 0.85, "fees": 0.6}
        overall = calculator.calculate_overall_score(field_scores)
        assert 0.0 <= overall <= 1.0

    def test_overall_score_weighted_by_field_weights(self, calculator):
        """加重平均が正しく計算される"""
        field_scores = {"product_name": 0.9, "fees": 0.7}
        overall = calculator.calculate_overall_score(field_scores)

        w_pn = FIELD_WEIGHTS["product_name"]  # 1.0
        w_fees = FIELD_WEIGHTS["fees"]  # 0.7
        expected = round((0.9 * w_pn + 0.7 * w_fees) / (w_pn + w_fees), 2)
        assert overall == expected

    def test_single_field_overall_equals_that_score(self, calculator):
        """フィールドが1つの場合、全体スコアはそのフィールドのスコアと等しい"""
        overall = calculator.calculate_overall_score({"base_price": 0.75})
        assert overall == 0.75

    def test_all_same_scores_returns_that_score(self, calculator):
        """全フィールドが同じスコアなら全体スコアもそのスコア"""
        field_scores = {"product_name": 0.8, "base_price": 0.8, "currency": 0.8}
        overall = calculator.calculate_overall_score(field_scores)
        assert overall == 0.8

    def test_unknown_fields_use_default_weight_in_overall(self, calculator):
        """未知のフィールドはデフォルト重みで加重平均に含まれる"""
        field_scores = {"product_name": 1.0, "custom_field": 0.5}
        overall = calculator.calculate_overall_score(field_scores)

        w_pn = FIELD_WEIGHTS["product_name"]
        w_custom = DEFAULT_FIELD_WEIGHT
        expected = round((1.0 * w_pn + 0.5 * w_custom) / (w_pn + w_custom), 2)
        assert overall == expected

    def test_end_to_end_field_scores_to_overall(self, calculator):
        """calculate_field_scores → calculate_overall_score の一連の流れ"""
        fields = {"product_name": "Widget", "base_price": 1000, "currency": "JPY"}
        field_scores = calculator.calculate_field_scores(fields, "structured_data")
        overall = calculator.calculate_overall_score(field_scores)
        assert 0.85 <= overall <= 0.95


# ---------------------------------------------------------------------------
# エッジケースのテスト
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """境界値・異常入力のテスト。"""

    def test_none_value_returns_zero(self, calculator):
        """値がNoneの場合スコアは0.0"""
        score = calculator.calculate_confidence_score("structured_data", "product_name", None)
        assert score == 0.0

    def test_empty_string_returns_zero(self, calculator):
        """空文字列の場合スコアは0.0"""
        score = calculator.calculate_confidence_score("structured_data", "product_name", "")
        assert score == 0.0

    def test_whitespace_only_string_returns_zero(self, calculator):
        """空白のみの文字列の場合スコアは0.0"""
        score = calculator.calculate_confidence_score("semantic_html", "product_name", "   ")
        assert score == 0.0

    def test_empty_list_returns_zero(self, calculator):
        """空リストの場合スコアは0.0"""
        score = calculator.calculate_confidence_score("regex", "payment_methods", [])
        assert score == 0.0

    def test_unknown_source_returns_zero(self, calculator):
        """未知の抽出元の場合スコアは0.0"""
        score = calculator.calculate_confidence_score("unknown_source", "product_name", "val")
        assert score == 0.0

    def test_negative_number_reduces_score(self, calculator):
        """負の数値はスコアが低下する"""
        normal = calculator.calculate_confidence_score("structured_data", "base_price", 100)
        negative = calculator.calculate_confidence_score("structured_data", "base_price", -100)
        assert negative < normal

    def test_short_string_reduces_score(self, calculator):
        """1文字の文字列はスコアが低下する"""
        normal = calculator.calculate_confidence_score("structured_data", "product_name", "Widget")
        short = calculator.calculate_confidence_score("structured_data", "product_name", "W")
        assert short < normal

    def test_empty_field_scores_returns_zero_overall(self, calculator):
        """空の辞書の場合、全体スコアは0.0"""
        assert calculator.calculate_overall_score({}) == 0.0

    def test_all_zero_scores_returns_zero_overall(self, calculator):
        """全フィールドが0.0の場合、全体スコアも0.0"""
        field_scores = {"product_name": 0.0, "base_price": 0.0}
        assert calculator.calculate_overall_score(field_scores) == 0.0

    def test_score_never_exceeds_one(self, calculator):
        """スコアは1.0を超えない"""
        for source in SOURCE_CONFIDENCE_RANGES:
            for field in FIELD_WEIGHTS:
                score = calculator.calculate_confidence_score(source, field, "valid_value")
                assert score <= 1.0

    def test_score_never_below_zero(self, calculator):
        """スコアは0.0を下回らない"""
        for source in SOURCE_CONFIDENCE_RANGES:
            score = calculator.calculate_confidence_score(source, "base_price", -9999)
            assert score >= 0.0

    def test_empty_fields_dict_returns_empty_scores(self, calculator):
        """空のフィールド辞書は空のスコア辞書を返す"""
        scores = calculator.calculate_field_scores({}, "structured_data")
        assert scores == {}

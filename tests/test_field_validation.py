"""
Unit tests for field validation module.

Tests validate_field_value against various field types and validation rules.
Requirements: 8.7
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from typing import Optional

from src.field_validation import validate_field_value, _is_empty, _convert_date_format


def _make_schema(
    field_type: str = "text",
    is_required: bool = False,
    validation_rules: Optional[dict] = None,
) -> MagicMock:
    """Create a mock FieldSchema for testing."""
    schema = MagicMock()
    schema.field_type = field_type
    schema.is_required = is_required
    schema.validation_rules = validation_rules
    return schema


# --- Required / Optional ---

class TestRequiredValidation:
    def test_required_field_with_none_value(self):
        schema = _make_schema(field_type="text", is_required=True)
        valid, error = validate_field_value(None, schema)
        assert not valid
        assert "必須" in error

    def test_required_field_with_empty_string(self):
        schema = _make_schema(field_type="text", is_required=True)
        valid, error = validate_field_value("", schema)
        assert not valid
        assert "必須" in error

    def test_required_field_with_whitespace_only(self):
        schema = _make_schema(field_type="text", is_required=True)
        valid, error = validate_field_value("   ", schema)
        assert not valid
        assert "必須" in error

    def test_required_field_with_valid_value(self):
        schema = _make_schema(field_type="text", is_required=True)
        valid, error = validate_field_value("hello", schema)
        assert valid
        assert error is None

    def test_optional_field_with_none_value(self):
        schema = _make_schema(field_type="text", is_required=False)
        valid, error = validate_field_value(None, schema)
        assert valid
        assert error is None

    def test_optional_field_with_empty_string(self):
        schema = _make_schema(field_type="text", is_required=False)
        valid, error = validate_field_value("", schema)
        assert valid
        assert error is None


# --- Type Checking ---

class TestTypeValidation:
    def test_text_type_with_string(self):
        schema = _make_schema(field_type="text")
        valid, _ = validate_field_value("hello", schema)
        assert valid

    def test_text_type_with_number(self):
        schema = _make_schema(field_type="text")
        valid, error = validate_field_value(123, schema)
        assert not valid
        assert "テキスト型" in error

    def test_number_type_with_int(self):
        schema = _make_schema(field_type="number")
        valid, _ = validate_field_value(42, schema)
        assert valid

    def test_number_type_with_float(self):
        schema = _make_schema(field_type="number")
        valid, _ = validate_field_value(3.14, schema)
        assert valid

    def test_number_type_with_string(self):
        schema = _make_schema(field_type="number")
        valid, error = validate_field_value("42", schema)
        assert not valid
        assert "数値型" in error

    def test_currency_type_with_number(self):
        schema = _make_schema(field_type="currency")
        valid, _ = validate_field_value(1000, schema)
        assert valid

    def test_currency_type_with_string(self):
        schema = _make_schema(field_type="currency")
        valid, error = validate_field_value("1000", schema)
        assert not valid
        assert "通貨型" in error

    def test_percentage_type_with_number(self):
        schema = _make_schema(field_type="percentage")
        valid, _ = validate_field_value(50.5, schema)
        assert valid

    def test_percentage_type_with_string(self):
        schema = _make_schema(field_type="percentage")
        valid, error = validate_field_value("50%", schema)
        assert not valid
        assert "パーセンテージ型" in error

    def test_date_type_with_string(self):
        schema = _make_schema(field_type="date", validation_rules={"format": "YYYY-MM-DD"})
        valid, _ = validate_field_value("2024-01-15", schema)
        assert valid

    def test_date_type_with_number(self):
        schema = _make_schema(field_type="date")
        valid, error = validate_field_value(20240115, schema)
        assert not valid
        assert "日付型" in error

    def test_boolean_type_with_bool(self):
        schema = _make_schema(field_type="boolean")
        valid, _ = validate_field_value(True, schema)
        assert valid

    def test_boolean_type_with_string(self):
        schema = _make_schema(field_type="boolean")
        valid, error = validate_field_value("true", schema)
        assert not valid
        assert "真偽値型" in error

    def test_list_type_with_string(self):
        schema = _make_schema(field_type="list", validation_rules={"options": ["a", "b"]})
        valid, _ = validate_field_value("a", schema)
        assert valid

    def test_list_type_with_number(self):
        schema = _make_schema(field_type="list")
        valid, error = validate_field_value(1, schema)
        assert not valid
        assert "リスト選択肢" in error

    def test_unsupported_field_type(self):
        schema = _make_schema(field_type="unknown")
        valid, error = validate_field_value("test", schema)
        assert not valid
        assert "サポートされていない" in error


# --- Text Validation Rules ---

class TestTextRules:
    def test_max_length_within_limit(self):
        schema = _make_schema(field_type="text", validation_rules={"max_length": 10})
        valid, _ = validate_field_value("hello", schema)
        assert valid

    def test_max_length_exceeded(self):
        schema = _make_schema(field_type="text", validation_rules={"max_length": 5})
        valid, error = validate_field_value("hello world", schema)
        assert not valid
        assert "最大文字数" in error

    def test_pattern_match(self):
        schema = _make_schema(field_type="text", validation_rules={"pattern": r"^[A-Z]"})
        valid, _ = validate_field_value("Hello", schema)
        assert valid

    def test_pattern_no_match(self):
        schema = _make_schema(field_type="text", validation_rules={"pattern": r"^[A-Z]"})
        valid, error = validate_field_value("hello", schema)
        assert not valid
        assert "パターン" in error

    def test_invalid_regex_pattern(self):
        schema = _make_schema(field_type="text", validation_rules={"pattern": r"[invalid"})
        valid, error = validate_field_value("test", schema)
        assert not valid
        assert "無効な正規表現" in error

    def test_both_rules_pass(self):
        schema = _make_schema(
            field_type="text",
            validation_rules={"max_length": 20, "pattern": r"^\d+$"},
        )
        valid, _ = validate_field_value("12345", schema)
        assert valid


# --- Number Validation Rules ---

class TestNumberRules:
    def test_within_range(self):
        schema = _make_schema(field_type="number", validation_rules={"min": 0, "max": 100})
        valid, _ = validate_field_value(50, schema)
        assert valid

    def test_below_min(self):
        schema = _make_schema(field_type="number", validation_rules={"min": 0})
        valid, error = validate_field_value(-1, schema)
        assert not valid
        assert "最小値" in error

    def test_above_max(self):
        schema = _make_schema(field_type="number", validation_rules={"max": 100})
        valid, error = validate_field_value(101, schema)
        assert not valid
        assert "最大値" in error

    def test_at_boundary_min(self):
        schema = _make_schema(field_type="number", validation_rules={"min": 0})
        valid, _ = validate_field_value(0, schema)
        assert valid

    def test_at_boundary_max(self):
        schema = _make_schema(field_type="number", validation_rules={"max": 100})
        valid, _ = validate_field_value(100, schema)
        assert valid

    def test_no_rules(self):
        schema = _make_schema(field_type="number")
        valid, _ = validate_field_value(999999, schema)
        assert valid


# --- Currency Validation Rules ---

class TestCurrencyRules:
    def test_valid_currency(self):
        schema = _make_schema(
            field_type="currency",
            validation_rules={"min": 0, "currency_code": "JPY"},
        )
        valid, _ = validate_field_value(1000, schema)
        assert valid

    def test_below_min(self):
        schema = _make_schema(
            field_type="currency",
            validation_rules={"min": 0, "currency_code": "JPY"},
        )
        valid, error = validate_field_value(-100, schema)
        assert not valid
        assert "最小値" in error


# --- Percentage Validation Rules ---

class TestPercentageRules:
    def test_valid_percentage(self):
        schema = _make_schema(
            field_type="percentage",
            validation_rules={"min": 0, "max": 100},
        )
        valid, _ = validate_field_value(50, schema)
        assert valid

    def test_above_max(self):
        schema = _make_schema(
            field_type="percentage",
            validation_rules={"min": 0, "max": 100},
        )
        valid, error = validate_field_value(101, schema)
        assert not valid
        assert "最大値" in error

    def test_below_min(self):
        schema = _make_schema(
            field_type="percentage",
            validation_rules={"min": 0, "max": 100},
        )
        valid, error = validate_field_value(-1, schema)
        assert not valid
        assert "最小値" in error


# --- Date Validation Rules ---

class TestDateRules:
    def test_valid_date_default_format(self):
        schema = _make_schema(field_type="date", validation_rules={"format": "YYYY-MM-DD"})
        valid, _ = validate_field_value("2024-01-15", schema)
        assert valid

    def test_invalid_date_format(self):
        schema = _make_schema(field_type="date", validation_rules={"format": "YYYY-MM-DD"})
        valid, error = validate_field_value("15/01/2024", schema)
        assert not valid
        assert "日付フォーマット" in error

    def test_invalid_date_value(self):
        schema = _make_schema(field_type="date", validation_rules={"format": "YYYY-MM-DD"})
        valid, error = validate_field_value("2024-13-45", schema)
        assert not valid
        assert "日付フォーマット" in error

    def test_no_format_rule_uses_default(self):
        schema = _make_schema(field_type="date")
        valid, _ = validate_field_value("2024-01-15", schema)
        assert valid


# --- Boolean Validation ---

class TestBooleanRules:
    def test_true_value(self):
        schema = _make_schema(field_type="boolean")
        valid, _ = validate_field_value(True, schema)
        assert valid

    def test_false_value(self):
        schema = _make_schema(field_type="boolean")
        valid, _ = validate_field_value(False, schema)
        assert valid


# --- List Validation Rules ---

class TestListRules:
    def test_valid_option(self):
        schema = _make_schema(
            field_type="list",
            validation_rules={"options": ["visa", "mastercard", "amex"]},
        )
        valid, _ = validate_field_value("visa", schema)
        assert valid

    def test_invalid_option(self):
        schema = _make_schema(
            field_type="list",
            validation_rules={"options": ["visa", "mastercard", "amex"]},
        )
        valid, error = validate_field_value("paypal", schema)
        assert not valid
        assert "選択肢" in error

    def test_no_options_rule(self):
        schema = _make_schema(field_type="list")
        valid, _ = validate_field_value("anything", schema)
        assert valid


# --- Helper Functions ---

class TestHelpers:
    def test_is_empty_none(self):
        assert _is_empty(None) is True

    def test_is_empty_empty_string(self):
        assert _is_empty("") is True

    def test_is_empty_whitespace(self):
        assert _is_empty("   ") is True

    def test_is_empty_valid_string(self):
        assert _is_empty("hello") is False

    def test_is_empty_zero(self):
        assert _is_empty(0) is False

    def test_is_empty_false(self):
        assert _is_empty(False) is False

    def test_convert_date_format(self):
        assert _convert_date_format("YYYY-MM-DD") == "%Y-%m-%d"

"""
Field validation module for validating field values against FieldSchema validation rules.

Supports validation for field types: text, number, currency, percentage, date, boolean, list.
Each type has specific validation_rules that can be defined in the FieldSchema's JSONB column.

Requirements: 8.7
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional, Tuple, Union

from src.models import FieldSchema


# Supported field types
VALID_FIELD_TYPES = {"text", "number", "currency", "percentage", "date", "boolean", "list"}


def validate_field_value(
    value: Any, field_schema: FieldSchema
) -> tuple[bool, Optional[str]]:
    """
    Validate a field value against its schema's validation rules.

    Args:
        value: The value to validate.
        field_schema: The FieldSchema instance containing field_type,
                      is_required, and validation_rules.

    Returns:
        A tuple of (is_valid, error_message).
        If valid, returns (True, None).
        If invalid, returns (False, "error description").
    """
    # 1. Required check
    if field_schema.is_required and _is_empty(value):
        return False, "この項目は必須です"

    # If not required and value is empty, skip further validation
    if _is_empty(value):
        return True, None

    # 2. Type check
    type_valid, type_error = _validate_type(value, field_schema.field_type)
    if not type_valid:
        return False, type_error

    # 3. Validation rules
    rules = field_schema.validation_rules or {}
    return _validate_rules(value, field_schema.field_type, rules)


def _is_empty(value: Any) -> bool:
    """Check if a value is considered empty (None, empty string, etc.)."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _validate_type(value: Any, field_type: str) -> tuple[bool, Optional[str]]:
    """Validate that the value matches the expected field type."""
    if field_type == "text":
        if not isinstance(value, str):
            return False, f"テキスト型が期待されますが、{type(value).__name__}型が指定されました"

    elif field_type == "number":
        if not isinstance(value, (int, float)):
            return False, f"数値型が期待されますが、{type(value).__name__}型が指定されました"

    elif field_type == "currency":
        if not isinstance(value, (int, float)):
            return False, f"通貨型（数値）が期待されますが、{type(value).__name__}型が指定されました"

    elif field_type == "percentage":
        if not isinstance(value, (int, float)):
            return False, f"パーセンテージ型（数値）が期待されますが、{type(value).__name__}型が指定されました"

    elif field_type == "date":
        if not isinstance(value, str):
            return False, f"日付型（文字列）が期待されますが、{type(value).__name__}型が指定されました"

    elif field_type == "boolean":
        if not isinstance(value, bool):
            return False, f"真偽値型が期待されますが、{type(value).__name__}型が指定されました"

    elif field_type == "list":
        if not isinstance(value, str):
            return False, f"リスト選択肢（文字列）が期待されますが、{type(value).__name__}型が指定されました"

    else:
        return False, f"サポートされていないフィールド型です: {field_type}"

    return True, None


def _validate_rules(
    value: Any, field_type: str, rules: dict[str, Any]
) -> tuple[bool, Optional[str]]:
    """Validate value against the validation_rules for the given field type."""
    if field_type == "text":
        return _validate_text_rules(value, rules)
    elif field_type == "number":
        return _validate_number_rules(value, rules)
    elif field_type == "currency":
        return _validate_currency_rules(value, rules)
    elif field_type == "percentage":
        return _validate_percentage_rules(value, rules)
    elif field_type == "date":
        return _validate_date_rules(value, rules)
    elif field_type == "boolean":
        # No validation rules for boolean
        return True, None
    elif field_type == "list":
        return _validate_list_rules(value, rules)
    else:
        return True, None


def _validate_text_rules(value: str, rules: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate text value against rules: pattern, max_length."""
    if "max_length" in rules:
        max_length = rules["max_length"]
        if isinstance(max_length, (int, float)) and len(value) > int(max_length):
            return False, f"最大文字数（{int(max_length)}）を超えています"

    if "pattern" in rules:
        pattern = rules["pattern"]
        if isinstance(pattern, str):
            try:
                if not re.search(pattern, value):
                    return False, f"パターン（{pattern}）に一致しません"
            except re.error:
                return False, f"無効な正規表現パターンです: {pattern}"

    return True, None


def _validate_number_rules(value: Union[float, int], rules: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate number value against rules: min, max."""
    if "min" in rules:
        min_val = rules["min"]
        if isinstance(min_val, (int, float)) and value < min_val:
            return False, f"最小値（{min_val}）未満です"

    if "max" in rules:
        max_val = rules["max"]
        if isinstance(max_val, (int, float)) and value > max_val:
            return False, f"最大値（{max_val}）を超えています"

    return True, None


def _validate_currency_rules(value: Union[float, int], rules: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate currency value against rules: min, currency_code."""
    if "min" in rules:
        min_val = rules["min"]
        if isinstance(min_val, (int, float)) and value < min_val:
            return False, f"最小値（{min_val}）未満です"

    # currency_code is metadata, not a value constraint — no validation needed on the value itself

    return True, None


def _validate_percentage_rules(value: Union[float, int], rules: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate percentage value against rules: min, max."""
    if "min" in rules:
        min_val = rules["min"]
        if isinstance(min_val, (int, float)) and value < min_val:
            return False, f"最小値（{min_val}）未満です"

    if "max" in rules:
        max_val = rules["max"]
        if isinstance(max_val, (int, float)) and value > max_val:
            return False, f"最大値（{max_val}）を超えています"

    return True, None


def _validate_date_rules(value: str, rules: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate date value against rules: format."""
    date_format = rules.get("format", "YYYY-MM-DD")

    if isinstance(date_format, str):
        # Convert common format tokens to Python strftime
        py_format = _convert_date_format(date_format)
        try:
            datetime.strptime(value, py_format)
        except ValueError:
            return False, f"日付フォーマット（{date_format}）に一致しません"

    return True, None


def _convert_date_format(fmt: str) -> str:
    """Convert a human-readable date format string to Python strftime format."""
    result = fmt
    result = result.replace("YYYY", "%Y")
    result = result.replace("MM", "%m")
    result = result.replace("DD", "%d")
    return result


def _validate_list_rules(value: str, rules: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate list value against rules: options."""
    if "options" in rules:
        options = rules["options"]
        if isinstance(options, list) and value not in options:
            return False, f"選択肢（{', '.join(str(o) for o in options)}）に含まれていません"

    return True, None

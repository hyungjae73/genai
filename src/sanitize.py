"""
Input sanitization utilities.

Provides helpers to strip HTML tags and sanitize user-supplied strings
to prevent XSS when values are later rendered in a browser.
"""

import re
from typing import Any

# Regex that matches HTML tags
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html_tags(value: str) -> str:
    """
    Remove HTML tags from a string.

    Args:
        value: Raw string that may contain HTML markup.

    Returns:
        String with all HTML tags removed.
    """
    return _HTML_TAG_RE.sub("", value)


def sanitize_value(value: Any) -> Any:
    """
    Sanitize a single value.

    - Strings: strip HTML tags.
    - Dicts / lists: recurse.
    - Other types: return as-is.
    """
    if isinstance(value, str):
        return strip_html_tags(value)
    if isinstance(value, dict):
        return sanitize_dict(value)
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    return value


def sanitize_dict(data: dict) -> dict:
    """
    Recursively sanitize all string values in a dictionary.

    Walks nested dicts and lists, stripping HTML tags from every
    string leaf.  Non-string values are left untouched.

    Args:
        data: Dictionary to sanitize.

    Returns:
        New dictionary with sanitized string values.
    """
    return {key: sanitize_value(val) for key, val in data.items()}

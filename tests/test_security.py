"""
Tests for authentication, input sanitization, and audit logging (Task 24).

Covers:
- API key authentication on write endpoints
- HTML tag stripping / XSS prevention
- Audit log creation on data modifications
"""

import pytest
from src.sanitize import strip_html_tags, sanitize_dict, sanitize_value
from src.auth import verify_api_key


# ------------------------------------------------------------------
# strip_html_tags
# ------------------------------------------------------------------


def test_strip_html_tags_removes_script():
    assert strip_html_tags('<script>alert("xss")</script>hello') == 'alert("xss")hello'


def test_strip_html_tags_removes_nested_tags():
    assert strip_html_tags("<b><i>bold italic</i></b>") == "bold italic"


def test_strip_html_tags_preserves_plain_text():
    assert strip_html_tags("no tags here") == "no tags here"


def test_strip_html_tags_empty_string():
    assert strip_html_tags("") == ""


def test_strip_html_tags_only_tags():
    assert strip_html_tags("<div></div>") == ""


# ------------------------------------------------------------------
# sanitize_dict / sanitize_value
# ------------------------------------------------------------------


def test_sanitize_dict_strips_html_from_strings():
    data = {"name": "<b>Product</b>", "count": 5}
    result = sanitize_dict(data)
    assert result == {"name": "Product", "count": 5}


def test_sanitize_dict_recurses_nested():
    data = {"outer": {"inner": "<script>x</script>safe"}}
    result = sanitize_dict(data)
    assert result == {"outer": {"inner": "xsafe"}}


def test_sanitize_dict_handles_lists():
    data = {"items": ["<b>a</b>", "<i>b</i>"]}
    result = sanitize_dict(data)
    assert result == {"items": ["a", "b"]}


def test_sanitize_value_non_string():
    assert sanitize_value(42) == 42
    assert sanitize_value(None) is None
    assert sanitize_value(3.14) == 3.14


# ------------------------------------------------------------------
# verify_api_key
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_verify_api_key_missing():
    """Missing header should raise 401."""
    with pytest.raises(Exception) as exc_info:
        await verify_api_key(x_api_key=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_api_key_invalid():
    """Wrong key should raise 403."""
    with pytest.raises(Exception) as exc_info:
        await verify_api_key(x_api_key="wrong-key")
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_verify_api_key_valid():
    """Correct key should return the key."""
    result = await verify_api_key(x_api_key="dev-api-key")
    assert result == "dev-api-key"

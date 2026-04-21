"""
Property-based tests for database URL derivation functions.

Feature: production-readiness-improvements
Property 1: データベースURL導出の往復一貫性

Validates that derive_async_url and derive_sync_url correctly transform
PostgreSQL connection URLs while preserving host, port, database name,
and credentials across all valid input prefixes.
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from urllib.parse import urlparse, urlunparse

from src.database import derive_async_url, derive_sync_url


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid PostgreSQL URL prefixes
PREFIXES = ["postgresql://", "postgresql+psycopg2://", "postgresql+asyncpg://"]

prefix_strategy = st.sampled_from(PREFIXES)

# Username: alphanumeric + underscore, non-empty
username_strategy = st.from_regex(r"[a-zA-Z][a-zA-Z0-9_]{0,29}", fullmatch=True)

# Password: printable ASCII excluding @, /, :, and whitespace to keep URL valid
password_strategy = st.from_regex(r"[a-zA-Z0-9!#$%^&*()_+\-=]{1,30}", fullmatch=True)

# Hostname: simple DNS-like names
hostname_strategy = st.from_regex(r"[a-z][a-z0-9\-]{0,19}(\.[a-z]{2,6})?", fullmatch=True)

# Port: valid TCP port range
port_strategy = st.integers(min_value=1, max_value=65535)

# Database name: alphanumeric + underscore
dbname_strategy = st.from_regex(r"[a-zA-Z][a-zA-Z0-9_]{0,29}", fullmatch=True)


@st.composite
def postgresql_url_strategy(draw):
    """Generate a valid PostgreSQL connection URL with a random prefix."""
    prefix = draw(prefix_strategy)
    username = draw(username_strategy)
    password = draw(password_strategy)
    host = draw(hostname_strategy)
    port = draw(port_strategy)
    dbname = draw(dbname_strategy)
    return f"{prefix}{username}:{password}@{host}:{port}/{dbname}"


def _strip_prefix(url: str) -> str:
    """Remove the driver prefix from a PostgreSQL URL, returning the rest."""
    for prefix in ["postgresql+asyncpg://", "postgresql+psycopg2://", "postgresql://"]:
        if url.startswith(prefix):
            return url[len(prefix):]
    raise ValueError(f"Unknown prefix in URL: {url}")


# ===========================================================================
# Property 1: データベースURL導出の往復一貫性
# ===========================================================================

class TestDatabaseURLDerivationRoundTrip:
    """
    Property 1: データベースURL導出の往復一貫性

    For ANY valid PostgreSQL URL with prefix postgresql://,
    postgresql+psycopg2://, or postgresql+asyncpg://:
    - derive_async_url ALWAYS produces a URL with postgresql+asyncpg:// prefix
    - derive_sync_url ALWAYS produces a URL with postgresql+psycopg2:// prefix
    - Host, port, database name, and credentials are preserved in ALL conversions

    Feature: production-readiness-improvements, Property 1: データベースURL導出の往復一貫性
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(url=postgresql_url_strategy())
    def test_derive_async_url_always_produces_asyncpg_prefix(self, url: str):
        """
        derive_async_url always produces a URL with postgresql+asyncpg:// prefix,
        regardless of the input prefix.

        **Validates: Requirements 1.1, 1.5, 1.6**
        """
        result = derive_async_url(url)
        assert result.startswith("postgresql+asyncpg://"), (
            f"Expected asyncpg prefix, got: {result}"
        )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(url=postgresql_url_strategy())
    def test_derive_sync_url_always_produces_psycopg2_prefix(self, url: str):
        """
        derive_sync_url always produces a URL with postgresql+psycopg2:// prefix,
        regardless of the input prefix.

        **Validates: Requirements 1.1, 1.5, 1.6**
        """
        result = derive_sync_url(url)
        assert result.startswith("postgresql+psycopg2://"), (
            f"Expected psycopg2 prefix, got: {result}"
        )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(url=postgresql_url_strategy())
    def test_derive_async_url_preserves_credentials_and_host(self, url: str):
        """
        derive_async_url preserves host, port, database name, and credentials.

        **Validates: Requirements 1.1, 1.5, 1.6**
        """
        result = derive_async_url(url)
        original_suffix = _strip_prefix(url)
        result_suffix = _strip_prefix(result)
        assert original_suffix == result_suffix, (
            f"Credentials/host/port/dbname changed.\n"
            f"  Original suffix: {original_suffix}\n"
            f"  Result suffix:   {result_suffix}"
        )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(url=postgresql_url_strategy())
    def test_derive_sync_url_preserves_credentials_and_host(self, url: str):
        """
        derive_sync_url preserves host, port, database name, and credentials.

        **Validates: Requirements 1.1, 1.5, 1.6**
        """
        result = derive_sync_url(url)
        original_suffix = _strip_prefix(url)
        result_suffix = _strip_prefix(result)
        assert original_suffix == result_suffix, (
            f"Credentials/host/port/dbname changed.\n"
            f"  Original suffix: {original_suffix}\n"
            f"  Result suffix:   {result_suffix}"
        )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(url=postgresql_url_strategy())
    def test_derive_async_then_sync_round_trip(self, url: str):
        """
        Applying derive_async_url then derive_sync_url produces a valid
        psycopg2 URL with the same credentials/host/port/dbname as the original.

        **Validates: Requirements 1.1, 1.5, 1.6**
        """
        async_url = derive_async_url(url)
        sync_url = derive_sync_url(async_url)

        assert sync_url.startswith("postgresql+psycopg2://"), (
            f"Round-trip result should have psycopg2 prefix, got: {sync_url}"
        )
        original_suffix = _strip_prefix(url)
        result_suffix = _strip_prefix(sync_url)
        assert original_suffix == result_suffix, (
            f"Round-trip changed credentials/host/port/dbname.\n"
            f"  Original suffix: {original_suffix}\n"
            f"  Result suffix:   {result_suffix}"
        )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(url=postgresql_url_strategy())
    def test_derive_sync_then_async_round_trip(self, url: str):
        """
        Applying derive_sync_url then derive_async_url produces a valid
        asyncpg URL with the same credentials/host/port/dbname as the original.

        **Validates: Requirements 1.1, 1.5, 1.6**
        """
        sync_url = derive_sync_url(url)
        async_url = derive_async_url(sync_url)

        assert async_url.startswith("postgresql+asyncpg://"), (
            f"Round-trip result should have asyncpg prefix, got: {async_url}"
        )
        original_suffix = _strip_prefix(url)
        result_suffix = _strip_prefix(async_url)
        assert original_suffix == result_suffix, (
            f"Round-trip changed credentials/host/port/dbname.\n"
            f"  Original suffix: {original_suffix}\n"
            f"  Result suffix:   {result_suffix}"
        )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(url=postgresql_url_strategy())
    def test_derive_async_url_is_idempotent(self, url: str):
        """
        Applying derive_async_url twice produces the same result as once.

        **Validates: Requirements 1.1, 1.5, 1.6**
        """
        once = derive_async_url(url)
        twice = derive_async_url(once)
        assert once == twice, (
            f"derive_async_url is not idempotent.\n"
            f"  Once:  {once}\n"
            f"  Twice: {twice}"
        )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(url=postgresql_url_strategy())
    def test_derive_sync_url_is_idempotent(self, url: str):
        """
        Applying derive_sync_url twice produces the same result as once.

        **Validates: Requirements 1.1, 1.5, 1.6**
        """
        once = derive_sync_url(url)
        twice = derive_sync_url(once)
        assert once == twice, (
            f"derive_sync_url is not idempotent.\n"
            f"  Once:  {once}\n"
            f"  Twice: {twice}"
        )

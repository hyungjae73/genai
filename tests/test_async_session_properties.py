"""
Property-based tests for the async database session dependency function.

Feature: production-readiness-improvements
Property 2: 非同期セッション依存関数のロールバック・クローズ保証

Validates that get_async_db guarantees:
- rollback is called when an exception occurs
- close is called in ALL cases
- commit is NOT called by the dependency (callers must commit explicitly)
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from unittest.mock import AsyncMock, MagicMock, patch

from src.database import get_async_db


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Various exception types that could occur during database operations
exception_type_strategy = st.sampled_from([
    ValueError,
    RuntimeError,
    TypeError,
    KeyError,
    IOError,
    AttributeError,
    ConnectionError,
    TimeoutError,
    PermissionError,
    OSError,
])

# Exception messages
exception_message_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=50,
)


def _make_mock_session() -> AsyncMock:
    """Create a mock AsyncSession with tracked rollback/close/commit calls."""
    session = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.commit = AsyncMock()
    return session


# ===========================================================================
# Property 2: 非同期セッション依存関数のロールバック・クローズ保証
# ===========================================================================

class TestAsyncSessionRollbackCloseGuarantee:
    """
    Property 2: 非同期セッション依存関数のロールバック・クローズ保証

    For ANY database operation sequence:
    - If an exception occurs: rollback is called
    - In ALL cases: close is called
    - Commit is NOT called by the dependency (callers must commit explicitly)

    Feature: production-readiness-improvements, Property 2: 非同期セッション依存関数のロールバック・クローズ保証
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(data=st.data())
    @pytest.mark.asyncio
    async def test_normal_flow_close_called_commit_not_called(self, data):
        """
        Normal flow (no exception): session is yielded, close is called,
        commit is NOT called by the dependency.

        **Validates: Requirements 1.3**
        """
        mock_session = _make_mock_session()

        mock_session_local = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_local.return_value = ctx

        with patch("src.database.AsyncSessionLocal", mock_session_local):
            gen = get_async_db()
            session = await gen.__anext__()

            assert session is mock_session

            # Simulate normal completion (no exception)
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass

        mock_session.close.assert_awaited_once()
        mock_session.commit.assert_not_awaited()
        mock_session.rollback.assert_not_awaited()

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        exc_type=exception_type_strategy,
        exc_msg=exception_message_strategy,
    )
    @pytest.mark.asyncio
    async def test_exception_flow_rollback_and_close_called(
        self, exc_type, exc_msg
    ):
        """
        Exception flow: for ANY exception type, rollback is called,
        close is called, and the original exception is re-raised.

        **Validates: Requirements 1.3**
        """
        mock_session = _make_mock_session()

        mock_session_local = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_local.return_value = ctx

        with patch("src.database.AsyncSessionLocal", mock_session_local):
            gen = get_async_db()
            session = await gen.__anext__()

            assert session is mock_session

            # Throw an exception into the generator
            with pytest.raises(exc_type):
                await gen.athrow(exc_type, exc_type(exc_msg), None)

        mock_session.rollback.assert_awaited_once()
        mock_session.close.assert_awaited_once()
        mock_session.commit.assert_not_awaited()

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(exc_type=exception_type_strategy)
    @pytest.mark.asyncio
    async def test_various_exception_types_all_trigger_rollback(self, exc_type):
        """
        Various exception types (ValueError, RuntimeError, etc.)
        all trigger rollback and close, never commit.

        **Validates: Requirements 1.3**
        """
        mock_session = _make_mock_session()

        mock_session_local = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_session)
        ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_local.return_value = ctx

        with patch("src.database.AsyncSessionLocal", mock_session_local):
            gen = get_async_db()
            session = await gen.__anext__()

            with pytest.raises(exc_type):
                await gen.athrow(exc_type, exc_type("test error"), None)

        # Rollback MUST be called for any exception type
        mock_session.rollback.assert_awaited_once()
        # Close MUST always be called
        mock_session.close.assert_awaited_once()
        # Commit MUST NOT be called by the dependency
        mock_session.commit.assert_not_awaited()

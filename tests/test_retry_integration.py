"""
Integration tests for retry decorator HTTP error handling.

Validates that:
- All retry attempts exhausted raises the original exception (via reraise=True)
- 4xx client errors are NOT retried
- 5xx server errors and 429 ARE retried

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
"""

from __future__ import annotations

import pytest
import httpx

from src.core.retry import with_retry


# ---------------------------------------------------------------------------
# Helper: retryable HTTP error filter (same pattern used in production code)
# ---------------------------------------------------------------------------

def _is_retryable_http_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


# ---------------------------------------------------------------------------
# Test: All retry attempts exhausted raises original exception
# Validates: Requirements 11.5
# ---------------------------------------------------------------------------

class TestRetryExhaustedRaisesOriginal:
    """When all retry attempts are exhausted, the original exception is re-raised."""

    def test_connection_error_exhausted(self):
        """ConnectionError is re-raised after max_attempts."""
        call_count = 0

        @with_retry(
            retry_on=(ConnectionError,),
            max_attempts=3,
            min_wait=0.0,
            max_wait=0.0,
            max_jitter=0.0,
        )
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("connection refused")

        with pytest.raises(ConnectionError, match="connection refused"):
            always_fail()

        assert call_count == 3

    def test_http_5xx_exhausted(self):
        """HTTP 500 error is re-raised after max_attempts when using retry_if."""
        call_count = 0

        @with_retry(
            retry_on=(httpx.HTTPStatusError,),
            retry_if=_is_retryable_http_error,
            max_attempts=3,
            min_wait=0.0,
            max_wait=0.0,
            max_jitter=0.0,
        )
        def always_500():
            nonlocal call_count
            call_count += 1
            response = httpx.Response(500, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError(
                "Server Error", request=response.request, response=response
            )

        with pytest.raises(httpx.HTTPStatusError):
            always_500()

        assert call_count == 3

    def test_http_429_exhausted(self):
        """HTTP 429 rate limit error is re-raised after max_attempts."""
        call_count = 0

        @with_retry(
            retry_on=(httpx.HTTPStatusError,),
            retry_if=_is_retryable_http_error,
            max_attempts=3,
            min_wait=0.0,
            max_wait=0.0,
            max_jitter=0.0,
        )
        def always_429():
            nonlocal call_count
            call_count += 1
            response = httpx.Response(429, request=httpx.Request("GET", "http://test"))
            raise httpx.HTTPStatusError(
                "Too Many Requests", request=response.request, response=response
            )

        with pytest.raises(httpx.HTTPStatusError):
            always_429()

        assert call_count == 3


# ---------------------------------------------------------------------------
# Test: 4xx client errors are NOT retried
# Validates: Requirements 11.1, 11.3
# ---------------------------------------------------------------------------

class TestClientErrorsNotRetried:
    """4xx HTTP errors should NOT be retried — function called exactly once."""

    @pytest.mark.parametrize("status_code,reason", [
        (400, "Bad Request"),
        (401, "Unauthorized"),
        (403, "Forbidden"),
        (404, "Not Found"),
    ])
    def test_4xx_not_retried(self, status_code, reason):
        call_count = 0

        @with_retry(
            retry_on=(httpx.HTTPStatusError,),
            retry_if=_is_retryable_http_error,
            max_attempts=3,
            min_wait=0.0,
            max_wait=0.0,
            max_jitter=0.0,
        )
        def raise_client_error():
            nonlocal call_count
            call_count += 1
            response = httpx.Response(
                status_code, request=httpx.Request("GET", "http://test")
            )
            raise httpx.HTTPStatusError(
                reason, request=response.request, response=response
            )

        with pytest.raises(httpx.HTTPStatusError):
            raise_client_error()

        assert call_count == 1, (
            f"Expected exactly 1 call for {status_code} {reason}, got {call_count}"
        )


# ---------------------------------------------------------------------------
# Test: 5xx and 429 ARE retried, then succeed
# Validates: Requirements 11.1, 11.3
# ---------------------------------------------------------------------------

class TestTransientErrorsRetried:
    """5xx and 429 errors should be retried, and succeed if transient."""

    def test_500_then_success(self):
        call_count = 0

        @with_retry(
            retry_on=(httpx.HTTPStatusError,),
            retry_if=_is_retryable_http_error,
            max_attempts=3,
            min_wait=0.0,
            max_wait=0.0,
            max_jitter=0.0,
        )
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                response = httpx.Response(
                    500, request=httpx.Request("GET", "http://test")
                )
                raise httpx.HTTPStatusError(
                    "Server Error", request=response.request, response=response
                )
            return "ok"

        result = fail_then_succeed()
        assert result == "ok"
        assert call_count == 2

    def test_429_then_success(self):
        call_count = 0

        @with_retry(
            retry_on=(httpx.HTTPStatusError,),
            retry_if=_is_retryable_http_error,
            max_attempts=3,
            min_wait=0.0,
            max_wait=0.0,
            max_jitter=0.0,
        )
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                response = httpx.Response(
                    429, request=httpx.Request("GET", "http://test")
                )
                raise httpx.HTTPStatusError(
                    "Too Many Requests", request=response.request, response=response
                )
            return "ok"

        result = fail_then_succeed()
        assert result == "ok"
        assert call_count == 2


# ---------------------------------------------------------------------------
# Test: Async retry works correctly
# Validates: Requirements 11.1, 11.4
# ---------------------------------------------------------------------------

class TestAsyncRetry:
    """Verify with_retry works with async functions."""

    @pytest.mark.asyncio
    async def test_async_retry_exhausted(self):
        call_count = 0

        @with_retry(
            retry_on=(ConnectionError,),
            max_attempts=3,
            min_wait=0.0,
            max_wait=0.0,
            max_jitter=0.0,
        )
        async def async_always_fail():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("async connection refused")

        with pytest.raises(ConnectionError, match="async connection refused"):
            await async_always_fail()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_retry_then_success(self):
        call_count = 0

        @with_retry(
            retry_on=(ConnectionError,),
            max_attempts=3,
            min_wait=0.0,
            max_wait=0.0,
            max_jitter=0.0,
        )
        async def async_fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("transient")
            return "async_ok"

        result = await async_fail_then_succeed()
        assert result == "async_ok"
        assert call_count == 2

"""Property-based tests for the with_retry decorator.

Feature: production-readiness-improvements
Properties 4, 5, 6: Retry decorator backoff bounds, max attempts, non-retryable exception propagation.
"""
import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import MagicMock

from src.core.retry import with_retry


# ---------------------------------------------------------------------------
# Property 4: Backoff time bounds
# **Validates: Requirements 10.1, 10.3**
#
# For any retry attempt n (1 <= n <= max_attempts), the actual wait time is
# within [min_wait * multiplier^(n-1), min(min_wait * multiplier^(n-1), max_wait) + max_jitter].
# ---------------------------------------------------------------------------

class TestProperty4BackoffTimeBounds:
    """Property 4: リトライデコレータのバックオフ時間境界"""

    @given(
        min_wait=st.floats(min_value=0.1, max_value=2.0),
        max_wait=st.floats(min_value=3.0, max_value=20.0),
        multiplier=st.floats(min_value=1.0, max_value=4.0),
        max_jitter=st.floats(min_value=0.0, max_value=2.0),
        max_attempts=st.integers(min_value=2, max_value=5),
    )
    @settings(max_examples=100)
    def test_wait_time_within_bounds(
        self, min_wait, max_wait, multiplier, max_jitter, max_attempts
    ):
        """**Validates: Requirements 10.1, 10.3**

        Wait time for each attempt n is within the expected exponential
        backoff range plus jitter.
        """
        decorator = with_retry(
            max_attempts=max_attempts,
            min_wait=min_wait,
            max_wait=max_wait,
            multiplier=multiplier,
            max_jitter=max_jitter,
            retry_on=(ValueError,),
        )

        # Apply decorator to a dummy function to access the Retrying object
        @decorator
        def _dummy():
            pass

        wait_strategy = _dummy.retry.wait

        for attempt_number in range(1, max_attempts):
            retry_state = MagicMock()
            retry_state.attempt_number = attempt_number

            # Sample the wait time multiple times to account for jitter randomness
            for _ in range(5):
                wait_time = wait_strategy(retry_state=retry_state)

                # Exponential component: multiplier * 2^(n-1), clamped to [min_wait, max_wait]
                exp_base_value = multiplier * (2 ** (attempt_number - 1))
                exp_component = min(max(exp_base_value, min_wait), max_wait)

                # Lower bound: exponential component + 0 jitter
                lower_bound = exp_component
                # Upper bound: exponential component + max_jitter
                upper_bound = exp_component + max_jitter

                assert wait_time >= lower_bound - 1e-9, (
                    f"attempt={attempt_number}, wait={wait_time}, "
                    f"lower_bound={lower_bound}"
                )
                assert wait_time <= upper_bound + 1e-9, (
                    f"attempt={attempt_number}, wait={wait_time}, "
                    f"upper_bound={upper_bound}"
                )


# ---------------------------------------------------------------------------
# Property 5: Max attempts — always-failing function called exactly max_attempts times
# **Validates: Requirements 10.2, 11.5**
# ---------------------------------------------------------------------------

class TestProperty5MaxAttempts:
    """Property 5: リトライデコレータの最大試行回数遵守"""

    @given(max_attempts=st.integers(min_value=1, max_value=8))
    @settings(max_examples=100)
    def test_always_failing_called_exactly_max_attempts(self, max_attempts):
        """**Validates: Requirements 10.2, 11.5**

        An always-failing function is called exactly max_attempts times,
        then the original exception is re-raised (reraise=True).
        """
        call_count = 0

        @with_retry(
            max_attempts=max_attempts,
            min_wait=0.0,
            max_wait=0.0,
            max_jitter=0.0,
            retry_on=(ValueError,),
        )
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fails")

        call_count = 0
        # With reraise=True, the original ValueError is re-raised after all attempts
        with pytest.raises(ValueError, match="always fails"):
            always_fail()

        assert call_count == max_attempts, (
            f"Expected {max_attempts} calls, got {call_count}"
        )


# ---------------------------------------------------------------------------
# Property 6: Non-retryable exceptions propagate immediately
# **Validates: Requirements 10.5**
# ---------------------------------------------------------------------------

class TestProperty6NonRetryableExceptionPropagation:
    """Property 6: 非リトライ対象例外の即時伝搬"""

    @given(
        max_attempts=st.integers(min_value=2, max_value=5),
    )
    @settings(max_examples=100)
    def test_non_retryable_exception_propagates_immediately(self, max_attempts):
        """**Validates: Requirements 10.5**

        When a function raises an exception NOT in retry_on, the decorator
        does not retry and the function is called exactly once.
        """
        call_count = 0

        @with_retry(
            max_attempts=max_attempts,
            min_wait=0.0,
            max_wait=0.0,
            max_jitter=0.0,
            retry_on=(ValueError,),  # Only retry on ValueError
        )
        def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("not retryable")

        call_count = 0
        with pytest.raises(TypeError, match="not retryable"):
            raises_type_error()

        assert call_count == 1, (
            f"Expected exactly 1 call for non-retryable exception, got {call_count}"
        )

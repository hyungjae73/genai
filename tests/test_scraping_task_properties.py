"""
Property-based tests for ScrapingTask model, schema, and service.

Tests boundary defense (Pydantic validation), idempotency (duplicate URL handling),
pessimistic state transitions, and edge-case resilience.
"""

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from pydantic import ValidationError

from src.api.schemas import CreateScrapingTaskRequest
from src.models import ScrapingTask, ScrapingTaskStatus
from src.scraping_task_service import ScrapingTaskService, InvalidStateTransition


# --- Strategies ---

def valid_url_strategy():
    """Generate valid HTTP/HTTPS URLs (no NUL bytes)."""
    protocol = st.sampled_from(["http://", "https://"])
    domain = st.from_regex(r"[a-z]{1,30}\.[a-z]{2,4}", fullmatch=True)
    path = st.from_regex(r"(/[a-z0-9]{1,20}){0,3}", fullmatch=True)
    return st.builds(lambda p, d, pa: f"{p}{d}{pa}", protocol, domain, path)


def invalid_url_strategy():
    """Generate URLs that should be rejected by the schema."""
    return st.one_of(
        # Empty / too short
        st.just(""),
        st.just("http://"),
        st.just("x"),
        # Wrong protocol
        st.builds(lambda d: f"ftp://{d}.com", st.from_regex(r"[a-z]{3,10}", fullmatch=True)),
        st.builds(lambda d: f"file:///{d}", st.from_regex(r"[a-z]{3,10}", fullmatch=True)),
        # No protocol
        st.builds(lambda d: f"{d}.com/page", st.from_regex(r"[a-z]{3,10}", fullmatch=True)),
        # Oversized URL (> 2048 chars)
        st.just("https://example.com/" + "a" * 2040),
    )


def error_message_strategy():
    """Generate error messages including edge cases."""
    return st.one_of(
        st.text(
            min_size=0,
            max_size=200,
            alphabet=st.characters(blacklist_characters="\x00"),
        ),
        # Huge error message
        st.just("E" * 15000),
        # Empty
        st.just(""),
    )


# ===================================================================
# Property 1: Boundary defense — Pydantic rejects invalid URLs
# ===================================================================


class TestBoundaryDefense:
    """
    Skill 1: Parse, don't validate.
    Valid URLs pass; invalid URLs raise ValidationError at the boundary.
    """

    @given(url=valid_url_strategy())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_urls_accepted(self, url):
        """Any well-formed HTTP/HTTPS URL is accepted by the schema."""
        req = CreateScrapingTaskRequest(target_url=url)
        assert req.target_url == url

    @given(url=invalid_url_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_urls_rejected(self, url):
        """Malformed URLs are rejected with ValidationError, not silently accepted."""
        with pytest.raises(ValidationError):
            CreateScrapingTaskRequest(target_url=url)


# ===================================================================
# Property 2: Idempotency — duplicate create_task returns existing
# ===================================================================


class TestIdempotency:
    """
    Skill 2: Idempotency guarantee.
    Calling create_task twice with the same URL returns the same task.
    """

    @given(url=valid_url_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_duplicate_create_returns_same_task(self, db_session, url):
        """Two create_task calls with the same URL return the same task (no duplicate)."""
        svc = ScrapingTaskService(db_session)

        task1 = svc.create_task(url)
        task2 = svc.create_task(url)

        assert task1.id == task2.id
        assert task1.status == ScrapingTaskStatus.PENDING.value

    @given(url=valid_url_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_new_task_after_previous_failed(self, db_session, url):
        """After a task FAILs, a new task can be created for the same URL."""
        svc = ScrapingTaskService(db_session)

        task1 = svc.create_task(url)
        svc.mark_as_failed(task1.id, "test failure")

        task2 = svc.create_task(url)
        assert task2.id != task1.id
        assert task2.status == ScrapingTaskStatus.PENDING.value


# ===================================================================
# Property 3: Pessimistic state transitions
# ===================================================================


class TestStateTransitions:
    """
    Skill 3 & 4: Pessimistic state management.
    Only valid transitions are allowed; invalid ones raise errors.
    """

    @given(url=valid_url_strategy(), error_msg=error_message_strategy())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_mark_as_failed_from_pending(self, db_session, url, error_msg):
        """PENDING → FAILED is a valid transition."""
        svc = ScrapingTaskService(db_session)
        task = svc.create_task(url)

        result = svc.mark_as_failed(task.id, error_msg)

        assert result.status == ScrapingTaskStatus.FAILED.value
        # Error message truncated to 10000 chars
        assert len(result.error_message or "") <= 10000

    @given(url=valid_url_strategy())
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_mark_as_failed_idempotent(self, db_session, url):
        """Calling mark_as_failed on an already-FAILED task is a no-op (idempotent)."""
        svc = ScrapingTaskService(db_session)
        task = svc.create_task(url)

        svc.mark_as_failed(task.id, "first failure")
        result = svc.mark_as_failed(task.id, "second failure")

        assert result.status == ScrapingTaskStatus.FAILED.value
        # Original error message preserved (not overwritten)
        assert result.error_message == "first failure"

    @given(url=valid_url_strategy())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cannot_fail_success_task(self, db_session, url):
        """SUCCESS → FAILED is an invalid transition."""
        svc = ScrapingTaskService(db_session)
        task = svc.create_task(url)

        # Manually set to SUCCESS
        task.status = ScrapingTaskStatus.SUCCESS.value
        db_session.flush()

        with pytest.raises(InvalidStateTransition):
            svc.mark_as_failed(task.id, "should not work")

    def test_mark_as_failed_nonexistent_task(self, db_session):
        """Attempting to fail a nonexistent task raises ValueError."""
        svc = ScrapingTaskService(db_session)
        with pytest.raises(ValueError, match="not found"):
            svc.mark_as_failed(999999, "no such task")

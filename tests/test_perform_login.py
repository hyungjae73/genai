"""
Unit tests for perform_login Celery task.

Feature: stealth-browser-hardening
Covers: perform_login task registration, retry config, distributed lock flow,
        lock verification before cookie save, login_failed marking after retries.

Requirements: 7.2, 7.3, 7.4, 8.1, 8.3
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline_tasks import perform_login


# ---------------------------------------------------------------------------
# Task registration and configuration
# ---------------------------------------------------------------------------


class TestPerformLoginTaskConfig:
    """Validates: Task registration, retry config, and queue routing."""

    def test_task_registered_with_correct_name(self):
        """perform_login is registered with the expected Celery task name."""
        assert perform_login.name == 'src.pipeline_tasks.perform_login'

    def test_max_retries_is_3(self):
        """perform_login has max_retries=3 (Req 7.4)."""
        assert perform_login.max_retries == 3

    def test_acks_late_enabled(self):
        """perform_login uses acks_late for reliability."""
        assert perform_login.acks_late is True

    def test_retry_backoff_enabled(self):
        """perform_login uses exponential backoff."""
        assert perform_login.retry_backoff is True

    def test_retry_backoff_max(self):
        """perform_login caps backoff at 300 seconds."""
        assert perform_login.retry_backoff_max == 300

    def test_autoretry_for_exception(self):
        """perform_login auto-retries on any Exception."""
        assert Exception in perform_login.autoretry_for

    def test_login_task_routed_to_crawl_queue(self):
        """perform_login is routed to the 'crawl' queue."""
        from src.celery_app import PIPELINE_TASK_ROUTES

        assert PIPELINE_TASK_ROUTES['src.pipeline_tasks.perform_login'] == {'queue': 'crawl'}


# ---------------------------------------------------------------------------
# Login flow — lock acquire, login, verify, save, release
# ---------------------------------------------------------------------------


class TestPerformLoginFlow:
    """Validates: Distributed lock flow (Req 8.1, 8.3) and cookie save (Req 7.3)."""

    @pytest.mark.asyncio
    async def test_successful_login_acquires_lock_saves_cookies_releases(self):
        """Full happy path: acquire lock → login → verify lock → save cookies → release lock."""
        from src.pipeline_tasks import _perform_login_async

        mock_session_mgr = AsyncMock()
        mock_session_mgr.acquire_login_lock.return_value = True
        mock_session_mgr.verify_lock_held.return_value = True
        mock_redis = AsyncMock()

        mock_task = MagicMock()

        with patch('src.pipeline_tasks.aioredis') as mock_aioredis, \
             patch('src.pipeline_tasks.SessionManager', return_value=mock_session_mgr):
            mock_aioredis.from_url.return_value = mock_redis

            result = await _perform_login_async(mock_task, site_id=42)

        assert result['site_id'] == 42
        assert result['status'] == 'login_success'
        assert result['cookies_saved'] is True

        mock_session_mgr.acquire_login_lock.assert_called_once_with(42)
        mock_session_mgr.verify_lock_held.assert_called_once_with(42)
        mock_session_mgr.save_cookies.assert_called_once()
        mock_session_mgr.release_login_lock.assert_called_once_with(42)
        mock_redis.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_already_held_skips_login(self):
        """When lock is already held, login is skipped (Req 8.1)."""
        from src.pipeline_tasks import _perform_login_async

        mock_session_mgr = AsyncMock()
        mock_session_mgr.acquire_login_lock.return_value = False
        mock_redis = AsyncMock()

        mock_task = MagicMock()

        with patch('src.pipeline_tasks.aioredis') as mock_aioredis, \
             patch('src.pipeline_tasks.SessionManager', return_value=mock_session_mgr):
            mock_aioredis.from_url.return_value = mock_redis

            result = await _perform_login_async(mock_task, site_id=7)

        assert result['site_id'] == 7
        assert result['status'] == 'lock_held'
        assert result['skipped'] is True

        mock_session_mgr.save_cookies.assert_not_called()
        mock_session_mgr.release_login_lock.assert_not_called()

    @pytest.mark.asyncio
    async def test_lock_expired_before_save_raises(self):
        """When lock expires before cookie save, RuntimeError is raised (CTO Review Fix)."""
        from src.pipeline_tasks import _perform_login_async

        mock_session_mgr = AsyncMock()
        mock_session_mgr.acquire_login_lock.return_value = True
        mock_session_mgr.verify_lock_held.return_value = False
        mock_redis = AsyncMock()

        mock_task = MagicMock()

        with patch('src.pipeline_tasks.aioredis') as mock_aioredis, \
             patch('src.pipeline_tasks.SessionManager', return_value=mock_session_mgr):
            mock_aioredis.from_url.return_value = mock_redis

            with pytest.raises(RuntimeError, match="Login lock expired"):
                await _perform_login_async(mock_task, site_id=99)

        # Lock should still be released in finally block
        mock_session_mgr.release_login_lock.assert_called_once_with(99)
        mock_session_mgr.save_cookies.assert_not_called()

    @pytest.mark.asyncio
    async def test_lock_released_even_on_login_failure(self):
        """Lock is always released, even when login raises an exception (Req 8.3)."""
        from src.pipeline_tasks import _perform_login_async

        mock_session_mgr = AsyncMock()
        mock_session_mgr.acquire_login_lock.return_value = True
        mock_redis = AsyncMock()

        mock_task = MagicMock()

        with patch('src.pipeline_tasks.aioredis') as mock_aioredis, \
             patch('src.pipeline_tasks.SessionManager', return_value=mock_session_mgr), \
             patch('src.pipeline_tasks._do_site_login', side_effect=ConnectionError("timeout")):
            mock_aioredis.from_url.return_value = mock_redis

            with pytest.raises(ConnectionError):
                await _perform_login_async(mock_task, site_id=5)

        mock_session_mgr.release_login_lock.assert_called_once_with(5)


# ---------------------------------------------------------------------------
# Retries exhausted — mark login_failed (Req 7.4)
# ---------------------------------------------------------------------------


class TestPerformLoginRetriesExhausted:
    """Validates: login_failed marking after 3 retries (Req 7.4)."""

    @pytest.mark.asyncio
    async def test_mark_login_failed_calls_session_manager(self):
        """_mark_login_failed sets session status via SessionManager."""
        from src.pipeline_tasks import _mark_login_failed

        mock_session_mgr = AsyncMock()
        mock_redis = AsyncMock()

        with patch('src.pipeline_tasks.aioredis') as mock_aioredis, \
             patch('src.pipeline_tasks.SessionManager', return_value=mock_session_mgr):
            mock_aioredis.from_url.return_value = mock_redis

            await _mark_login_failed(site_id=10)

        mock_session_mgr.mark_login_failed.assert_called_once_with(10)
        mock_redis.aclose.assert_called_once()


# ---------------------------------------------------------------------------
# Placeholder login logic
# ---------------------------------------------------------------------------


class TestDoSiteLogin:
    """Validates: Placeholder login returns valid cookie structure."""

    @pytest.mark.asyncio
    async def test_returns_cookie_list(self):
        """_do_site_login returns a list of cookie dicts."""
        from src.pipeline_tasks import _do_site_login

        cookies = await _do_site_login(site_id=1)

        assert isinstance(cookies, list)
        assert len(cookies) > 0
        cookie = cookies[0]
        assert 'name' in cookie
        assert 'value' in cookie
        assert 'domain' in cookie
        assert 'path' in cookie

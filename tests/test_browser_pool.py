"""
Unit tests for BrowserPool.

Feature: crawl-pipeline-architecture
Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6

All Playwright objects are mocked since Playwright may not be installed
in the test environment.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pipeline.browser_pool import BrowserPool


# --- Helpers ---


def _make_mock_browser(connected=True):
    """Create a mock Browser that reports the given connection state."""
    browser = MagicMock()
    browser.is_connected.return_value = connected
    browser.close = AsyncMock()

    page = MagicMock()
    page.is_closed.return_value = False
    page.close = AsyncMock()
    browser.new_page = AsyncMock(return_value=page)

    return browser


def _make_mock_playwright(browsers=None):
    """Create a mock Playwright instance that launches mock browsers."""
    pw = MagicMock()
    if browsers is None:
        browsers = [_make_mock_browser() for _ in range(10)]

    pw.chromium.launch = AsyncMock(side_effect=browsers)
    pw.stop = AsyncMock()
    return pw


def _make_launcher(mock_pw):
    """Create an async launcher function that returns the mock Playwright."""

    async def launcher():
        return mock_pw

    return launcher


# --- Tests ---


class TestBrowserPoolInit:
    """Test BrowserPool initialization."""

    def test_default_max_instances(self):
        pool = BrowserPool()
        assert pool._max_instances == 3

    def test_custom_max_instances(self):
        pool = BrowserPool(max_instances=5)
        assert pool._max_instances == 5

    def test_not_initialized_by_default(self):
        pool = BrowserPool()
        assert pool._initialized is False


class TestBrowserPoolInitialize:
    """Validates: Requirement 15.1 — pool holds configurable number of instances."""

    @pytest.mark.asyncio
    async def test_initialize_creates_browsers(self):
        mock_pw = _make_mock_playwright()
        pool = BrowserPool(max_instances=3, playwright_launcher=_make_launcher(mock_pw))

        await pool.initialize()

        assert pool._initialized is True
        assert len(pool._instances) == 3
        assert pool._pool.qsize() == 3
        assert mock_pw.chromium.launch.call_count == 3

    @pytest.mark.asyncio
    async def test_initialize_custom_count(self):
        mock_pw = _make_mock_playwright()
        pool = BrowserPool(max_instances=5, playwright_launcher=_make_launcher(mock_pw))

        await pool.initialize()

        assert len(pool._instances) == 5
        assert pool._pool.qsize() == 5


class TestBrowserPoolAcquire:
    """Validates: Requirements 15.2, 15.4 — acquire browser and page, wait when all in use."""

    @pytest.mark.asyncio
    async def test_acquire_returns_browser_and_page(self):
        mock_browsers = [_make_mock_browser(), _make_mock_browser()]
        mock_pw = _make_mock_playwright(mock_browsers)
        pool = BrowserPool(max_instances=2, playwright_launcher=_make_launcher(mock_pw))
        await pool.initialize()

        browser, page = await pool.acquire()

        assert browser in mock_browsers
        assert browser.new_page.called
        assert page is not None

    @pytest.mark.asyncio
    async def test_acquire_checks_is_connected(self):
        mock_browser = _make_mock_browser(connected=True)
        mock_pw = _make_mock_playwright([mock_browser])
        pool = BrowserPool(max_instances=1, playwright_launcher=_make_launcher(mock_pw))
        await pool.initialize()

        await pool.acquire()
        mock_browser.is_connected.assert_called()

    @pytest.mark.asyncio
    async def test_acquire_raises_when_not_initialized(self):
        pool = BrowserPool()
        with pytest.raises(RuntimeError, match="not initialized"):
            await pool.acquire()

    @pytest.mark.asyncio
    async def test_acquire_waits_when_all_in_use(self):
        """When all instances are in use, acquire() awaits for one to be returned."""
        mock_browser = _make_mock_browser()
        mock_pw = _make_mock_playwright([mock_browser])
        pool = BrowserPool(max_instances=1, playwright_launcher=_make_launcher(mock_pw))
        await pool.initialize()

        # Acquire the only instance
        browser, page = await pool.acquire()

        # Second acquire should block; use a timeout to verify
        acquired = asyncio.Event()

        async def try_acquire():
            await pool.acquire()
            acquired.set()

        task = asyncio.create_task(try_acquire())

        # Give the task a moment to start waiting
        await asyncio.sleep(0.05)
        assert not acquired.is_set(), "acquire() should be waiting"

        # Release the browser to unblock
        await pool.release(browser, page)
        await asyncio.sleep(0.05)
        assert acquired.is_set(), "acquire() should have completed after release"

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestBrowserPoolRelease:
    """Validates: Requirement 15.3 — close page and return browser to pool."""

    @pytest.mark.asyncio
    async def test_release_closes_page_and_returns_browser(self):
        mock_browser = _make_mock_browser()
        mock_pw = _make_mock_playwright([mock_browser])
        pool = BrowserPool(max_instances=1, playwright_launcher=_make_launcher(mock_pw))
        await pool.initialize()

        browser, page = await pool.acquire()
        assert pool._pool.qsize() == 0

        await pool.release(browser, page)

        page.close.assert_called_once()
        assert pool._pool.qsize() == 1

    @pytest.mark.asyncio
    async def test_release_handles_already_closed_page(self):
        mock_browser = _make_mock_browser()
        mock_pw = _make_mock_playwright([mock_browser])
        pool = BrowserPool(max_instances=1, playwright_launcher=_make_launcher(mock_pw))
        await pool.initialize()

        browser, page = await pool.acquire()
        page.is_closed.return_value = True

        # Should not raise
        await pool.release(browser, page)
        page.close.assert_not_called()
        assert pool._pool.qsize() == 1


class TestBrowserPoolCrashDetection:
    """Validates: Requirement 15.5 — crash detection and auto-regeneration."""

    @pytest.mark.asyncio
    async def test_acquire_replaces_crashed_browser(self):
        crashed_browser = _make_mock_browser(connected=False)
        replacement_browser = _make_mock_browser(connected=True)
        mock_pw = _make_mock_playwright([crashed_browser, replacement_browser])
        pool = BrowserPool(max_instances=1, playwright_launcher=_make_launcher(mock_pw))
        await pool.initialize()

        browser, page = await pool.acquire()

        # Should have gotten the replacement, not the crashed one
        assert browser is replacement_browser
        assert replacement_browser.new_page.called

        # Crashed browser should have been removed from instances
        assert crashed_browser not in pool._instances
        assert replacement_browser in pool._instances

    @pytest.mark.asyncio
    async def test_release_replaces_crashed_browser(self):
        mock_browser = _make_mock_browser(connected=True)
        replacement_browser = _make_mock_browser(connected=True)
        mock_pw = _make_mock_playwright([mock_browser, replacement_browser])
        pool = BrowserPool(max_instances=1, playwright_launcher=_make_launcher(mock_pw))
        await pool.initialize()

        browser, page = await pool.acquire()

        # Simulate crash during use
        mock_browser.is_connected.return_value = False

        await pool.release(browser, page)

        # Pool should contain the replacement
        assert pool._pool.qsize() == 1
        returned = pool._pool.get_nowait()
        assert returned is replacement_browser

    @pytest.mark.asyncio
    async def test_crash_maintains_pool_size(self):
        browsers = [
            _make_mock_browser(connected=False),  # will crash on acquire
            _make_mock_browser(connected=True),
            _make_mock_browser(connected=True),  # replacement for crashed
        ]
        mock_pw = _make_mock_playwright(browsers)
        pool = BrowserPool(max_instances=2, playwright_launcher=_make_launcher(mock_pw))
        await pool.initialize()

        # Acquire the crashed one (should be replaced)
        browser, page = await pool.acquire()
        assert browser.is_connected()

        # Pool should still have the right number of tracked instances
        assert len(pool._instances) == 2


class TestBrowserPoolShutdown:
    """Validates: Requirement 15.6 — graceful shutdown of all instances."""

    @pytest.mark.asyncio
    async def test_shutdown_closes_all_browsers(self):
        mock_browsers = [_make_mock_browser(), _make_mock_browser()]
        mock_pw = _make_mock_playwright(mock_browsers)
        pool = BrowserPool(max_instances=2, playwright_launcher=_make_launcher(mock_pw))
        await pool.initialize()

        await pool.shutdown()

        for browser in mock_browsers:
            browser.close.assert_called_once()

        assert pool._instances == []
        assert pool._initialized is False
        mock_pw.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_already_disconnected(self):
        mock_browser = _make_mock_browser(connected=False)
        mock_pw = _make_mock_playwright([mock_browser])
        pool = BrowserPool(max_instances=1, playwright_launcher=_make_launcher(mock_pw))
        await pool.initialize()

        # Should not raise even if browser is disconnected
        await pool.shutdown()
        mock_browser.close.assert_not_called()  # skipped because not connected

    @pytest.mark.asyncio
    async def test_shutdown_clears_pool(self):
        mock_pw = _make_mock_playwright()
        pool = BrowserPool(max_instances=2, playwright_launcher=_make_launcher(mock_pw))
        await pool.initialize()

        assert pool._pool.qsize() == 2
        await pool.shutdown()
        assert pool._pool.empty()
        assert pool._playwright is None

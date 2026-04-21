"""
StealthBrowserFactory — single entry point for all Playwright browser creation.

Applies playwright-stealth, consistent User-Agent, randomized viewport,
and optional proxy injection. All Playwright consumers in the codebase
MUST use this factory to avoid DRY violations and ensure uniform anti-bot posture.

Usage:
    async with StealthBrowserFactory() as factory:
        browser, context, page = await factory.create_page()
        # ... use page ...
        await page.close()
        await context.close()

Or for BrowserPool integration (browser lifecycle managed externally):
    factory = StealthBrowserFactory()
    browser = await factory.create_browser(playwright_instance)
    context = await factory.create_context(browser)
    page = await context.new_page()
    await factory.apply_stealth(page)
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Optional

from src.scraping_config import ScrapingConfig, scraping_config

logger = logging.getLogger(__name__)


class StealthBrowserFactory:
    """Factory for creating stealth-configured Playwright browsers and contexts.

    Centralizes:
    - playwright-stealth application (navigator.webdriver hiding)
    - Fixed User-Agent (consistent fingerprint)
    - Randomized viewport from pool
    - Proxy injection (when configured)
    - Delay jitter insertion
    """

    def __init__(self, config: Optional[ScrapingConfig] = None) -> None:
        self._config = config or scraping_config
        self._playwright: Optional[Any] = None
        self._owns_playwright = False

    async def __aenter__(self) -> "StealthBrowserFactory":
        """Start Playwright instance (context manager mode)."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._owns_playwright = True
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Stop Playwright instance if we own it."""
        if self._owns_playwright and self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def create_browser(self, playwright: Optional[Any] = None) -> Any:
        """Launch a Chromium browser with proxy support.

        Args:
            playwright: External Playwright instance. Uses internal if None.

        Returns:
            Playwright Browser instance.
        """
        pw = playwright or self._playwright
        if pw is None:
            raise RuntimeError(
                "No Playwright instance. Use 'async with StealthBrowserFactory()' "
                "or pass a playwright instance."
            )

        launch_kwargs: dict[str, Any] = {"headless": True}

        proxy = self._config.get_proxy_dict()
        if proxy:
            launch_kwargs["proxy"] = proxy
            logger.info("Launching browser with proxy: %s", proxy.get("server", ""))

        return await pw.chromium.launch(**launch_kwargs)

    async def create_context(
        self,
        browser: Any,
        viewport: Optional[dict[str, int]] = None,
        device_scale_factor: int = 1,
    ) -> Any:
        """Create a BrowserContext with stealth fingerprint.

        Args:
            browser: Playwright Browser instance.
            viewport: Override viewport. Random from pool if None.
            device_scale_factor: CSS pixel ratio (default 1).

        Returns:
            Playwright BrowserContext with stealth UA and viewport.
        """
        vp = viewport or self._config.get_random_viewport()

        context = await browser.new_context(
            user_agent=self._config.scraping_user_agent,
            viewport=vp,
            device_scale_factor=device_scale_factor,
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )
        return context

    async def create_page(
        self,
        browser: Optional[Any] = None,
        viewport: Optional[dict[str, int]] = None,
        device_scale_factor: int = 1,
    ) -> tuple[Any, Any, Any]:
        """Convenience: create browser (if needed) + context + page with stealth.

        Returns:
            (browser, context, page) tuple. Caller must close context and page.
        """
        own_browser = browser is None
        if own_browser:
            browser = await self.create_browser()

        context = await self.create_context(
            browser, viewport=viewport, device_scale_factor=device_scale_factor
        )
        page = await context.new_page()
        await self.apply_stealth(page)
        return browser, context, page

    async def apply_stealth(self, page: Any) -> None:
        """Apply playwright-stealth patches to a page.

        Hides navigator.webdriver, patches chrome.runtime, etc.
        Falls back gracefully if playwright-stealth is not installed.
        """
        if not self._config.scraping_stealth_enabled:
            return

        try:
            from playwright_stealth import stealth_async

            await stealth_async(page)
            logger.debug("Stealth patches applied to page")
        except ImportError:
            logger.warning(
                "playwright-stealth not installed — stealth patches skipped. "
                "Install with: pip install playwright-stealth"
            )
        except Exception as e:
            logger.warning("Failed to apply stealth patches: %s", e)

    async def jitter(self) -> None:
        """Insert a random delay to avoid mechanical timing detection."""
        delay = self._config.get_jitter()
        await asyncio.sleep(delay)

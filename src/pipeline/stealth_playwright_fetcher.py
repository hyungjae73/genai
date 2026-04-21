"""
StealthPlaywrightFetcher — Playwright-based PageFetcher implementation.

Uses BrowserPool for browser instance management and SessionManager
for Cookie injection/persistence across distributed workers.

Requirements: 10.2
"""

from __future__ import annotations

import logging
from typing import Optional

from src.models import MonitoringSite
from src.pipeline.browser_pool import BrowserPool
from src.pipeline.fetcher_protocol import FetchResult
from src.pipeline.session_manager import SessionManager

logger = logging.getLogger(__name__)


class StealthPlaywrightFetcher:
    """Playwright ベースの PageFetcher 実装。

    BrowserPool からブラウザを取得し、SessionManager で Cookie を注入する。
    """

    def __init__(
        self,
        browser_pool: BrowserPool,
        session_manager: Optional[SessionManager] = None,
    ) -> None:
        self._pool = browser_pool
        self._session_manager = session_manager

    async def fetch(self, url: str, site: MonitoringSite) -> FetchResult:
        """Playwright でページを取得する。"""
        browser, page = await self._pool.acquire()
        try:
            # Cookie injection
            if self._session_manager:
                cookies = await self._session_manager.get_cookies(site.id)
                if cookies:
                    await page.context.add_cookies(cookies)

            response = await page.goto(url, wait_until="networkidle", timeout=30000)
            status = response.status if response else 0
            html = await page.content()
            headers = dict(response.headers) if response else {}

            # Cookie persistence
            if self._session_manager and status == 200:
                new_cookies = await page.context.cookies()
                await self._session_manager.save_cookies(site.id, new_cookies)

            return FetchResult(html=html, status_code=status, headers=headers)
        finally:
            await self._pool.release(browser, page)

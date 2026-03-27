"""
BrowserPool — Playwright ブラウザインスタンスプール。

ワーカープロセス内で設定可能な数のブラウザインスタンスを保持し、
タスク間で再利用する。asyncio.Queue ベースのプール管理を行い、
全インスタンス使用中の場合は返却されるまで await で待機する。

クラッシュ検出は browser.is_connected() で行い、
クラッシュしたインスタンスは破棄して新規生成する。

Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from playwright.async_api import Browser, Page, Playwright

logger = logging.getLogger(__name__)


async def _default_playwright_launcher() -> Any:
    """デフォルトの Playwright 起動関数。

    Returns:
        Playwright インスタンス
    """
    from playwright.async_api import async_playwright

    pw_context_manager = async_playwright()
    return await pw_context_manager.start()


class BrowserPool:
    """Playwright ブラウザインスタンスプール。

    asyncio.Queue ベースでブラウザインスタンスを管理する。
    acquire() で貸し出し、release() で返却する。
    全インスタンス使用中の場合は await で待機する。

    Attributes:
        _max_instances: プール内の最大ブラウザインスタンス数
        _pool: 利用可能なブラウザインスタンスのキュー
        _instances: 全ブラウザインスタンスのリスト（追跡用）
        _playwright: Playwright インスタンス
        _initialized: 初期化済みフラグ
    """

    def __init__(
        self,
        max_instances: int = 3,
        playwright_launcher: Optional[Callable] = None,
    ) -> None:
        """BrowserPool を初期化する。

        Args:
            max_instances: プール内の最大ブラウザインスタンス数（デフォルト: 3）
            playwright_launcher: Playwright 起動関数（テスト用にオーバーライド可能）
        """
        self._max_instances = max_instances
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_instances)
        self._instances: list = []
        self._playwright: Optional[Any] = None
        self._initialized = False
        self._playwright_launcher = playwright_launcher or _default_playwright_launcher

    async def _create_browser(self) -> Any:
        """新しいブラウザインスタンスを生成する。

        Returns:
            Playwright Browser インスタンス
        """
        if self._playwright is None:
            raise RuntimeError(
                "BrowserPool is not initialized. Call initialize() first."
            )

        browser = await self._playwright.chromium.launch(headless=True)
        return browser

    async def initialize(self) -> None:
        """プールを初期化し、max_instances 個のブラウザを起動する。

        Playwright を起動し、設定された数のブラウザインスタンスを生成して
        プールに追加する。
        """
        self._playwright = await self._playwright_launcher()

        for _ in range(self._max_instances):
            browser = await self._create_browser()
            self._instances.append(browser)
            await self._pool.put(browser)

        self._initialized = True
        logger.info(
            "BrowserPool initialized with %d instances", self._max_instances
        )

    async def acquire(self) -> tuple:
        """プールからブラウザを取得し、新しいページを生成して返却する。

        全インスタンスが使用中の場合は、いずれかが返却されるまで await で待機する。
        取得したブラウザが切断されている（クラッシュ）場合は、
        破棄して新しいインスタンスを生成する。

        Returns:
            (browser, page) のタプル
        """
        if not self._initialized:
            raise RuntimeError(
                "BrowserPool is not initialized. Call initialize() first."
            )

        browser = await self._pool.get()

        # クラッシュ検出: is_connected() で接続状態を確認
        if not browser.is_connected():
            logger.warning("Browser instance crashed, creating replacement")
            browser = await self._handle_crash(browser)

        page = await browser.new_page()
        return browser, page

    async def release(self, browser: Any, page: Any) -> None:
        """ページを閉じてブラウザをプールに返却する。

        Args:
            browser: 返却するブラウザインスタンス
            page: 閉じるページインスタンス
        """
        try:
            if not page.is_closed():
                await page.close()
        except Exception as e:
            logger.warning("Error closing page: %s", e)

        # ブラウザがまだ接続中ならプールに返却
        if browser.is_connected():
            await self._pool.put(browser)
        else:
            # クラッシュしていた場合は新しいインスタンスで置換
            logger.warning("Browser crashed during use, replacing instance")
            new_browser = await self._handle_crash(browser)
            await self._pool.put(new_browser)

    async def _handle_crash(self, browser: Any) -> Any:
        """クラッシュしたインスタンスを破棄し、新規生成する。

        クラッシュしたブラウザを _instances リストから除去し、
        新しいブラウザインスタンスを生成して _instances に追加する。

        Args:
            browser: クラッシュしたブラウザインスタンス

        Returns:
            新しいブラウザインスタンス
        """
        # クラッシュしたインスタンスを追跡リストから除去
        if browser in self._instances:
            self._instances.remove(browser)

        # 安全にクローズを試みる
        try:
            await browser.close()
        except Exception:
            pass  # クラッシュ済みなので無視

        # 新しいインスタンスを生成
        new_browser = await self._create_browser()
        self._instances.append(new_browser)

        logger.info("Replaced crashed browser instance")
        return new_browser

    async def shutdown(self) -> None:
        """全ブラウザインスタンスを正常に終了する。

        プール内の全インスタンスと追跡リスト内の全インスタンスを閉じる。
        """
        # プールから全インスタンスを取り出す（ノンブロッキング）
        while not self._pool.empty():
            try:
                self._pool.get_nowait()
            except asyncio.QueueEmpty:
                break

        # 全インスタンスを閉じる
        for browser in self._instances:
            try:
                if browser.is_connected():
                    await browser.close()
            except Exception as e:
                logger.warning(
                    "Error closing browser during shutdown: %s", e
                )

        self._instances.clear()

        # Playwright を終了
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning("Error stopping Playwright: %s", e)
            self._playwright = None

        self._initialized = False
        logger.info("BrowserPool shut down")

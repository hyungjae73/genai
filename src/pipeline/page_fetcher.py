"""
PageFetcherStage — PageFetcher ステージの実行順序制御。

PageFetcher は特殊なステージで、ブラウザページのライフサイクルを管理し、
プラグインを固定順序で実行する:

  1. LocalePlugin — ロケール設定を ctx.metadata に格納
  2. ページ取得 — page.goto() + networkidle 待機 + DOM 安定化
     - デルタクロール: ETag/Last-Modified 条件付きリクエストヘッダー付与
     - 304 Not Modified → pagefetcher_not_modified フラグ設定、残りスキップ
     - 200 → 新しい ETag/Last-Modified を metadata に記録
  3. PreCaptureScriptPlugin — should_run() が True の場合のみ実行
  4. ModalDismissPlugin — モーダル検出・閉じ
  5. スクリーンショット撮影 — ctx.screenshots に追加

Requirements: 23.1, 23.2, 23.3, 18.2, 18.3, 18.4, 18.5
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

from src.pipeline.context import CrawlContext, VariantCapture
from src.pipeline.plugins.locale_plugin import LocalePlugin
from src.pipeline.plugins.modal_dismiss_plugin import ModalDismissPlugin
from src.pipeline.plugins.pre_capture_script_plugin import PreCaptureScriptPlugin

if TYPE_CHECKING:
    from src.pipeline.browser_pool import BrowserPool

logger = logging.getLogger(__name__)

# DOM stabilization wait time in ms
DOM_STABILIZATION_WAIT_MS = 1000


class PageFetcherStage:
    """PageFetcher ステージの実行順序制御。

    固定順序でプラグインとページ取得ロジックを実行する。
    BrowserPool からブラウザを取得し、ページのライフサイクルを管理する。

    Attributes:
        _browser_pool: BrowserPool インスタンス（None の場合はテスト用）
        _locale_plugin: LocalePlugin インスタンス
        _pre_capture_plugin: PreCaptureScriptPlugin インスタンス
        _modal_dismiss_plugin: ModalDismissPlugin インスタンス
    """

    def __init__(self, browser_pool: Optional[BrowserPool] = None) -> None:
        """PageFetcherStage を初期化する。

        Args:
            browser_pool: BrowserPool インスタンス。None の場合はテスト用。
        """
        self._browser_pool = browser_pool
        self._locale_plugin = LocalePlugin()
        self._pre_capture_plugin = PreCaptureScriptPlugin()
        self._modal_dismiss_plugin = ModalDismissPlugin()

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """PageFetcher ステージを固定順序で実行する。

        実行順序:
          1. LocalePlugin
          2. ページ取得 (page.goto + networkidle + DOM安定化)
          3. PreCaptureScriptPlugin (should_run が True の場合のみ)
          4. ModalDismissPlugin
          5. スクリーンショット撮影

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            処理結果を追記した CrawlContext
        """
        browser = None
        page = None

        try:
            # Step 1: LocalePlugin
            ctx = await self._run_plugin(self._locale_plugin, ctx, "locale")

            # Acquire browser and page
            if self._browser_pool is not None:
                browser, page = await self._browser_pool.acquire()

                # Apply locale config from LocalePlugin
                locale_config = ctx.metadata.get("locale_config", {})
                if locale_config:
                    await self._apply_locale_config(page, locale_config)

                # Store page reference for plugins
                ctx.metadata["page"] = page

                # Step 2: Page fetch with delta crawl support
                ctx = await self._fetch_page(ctx, page)

                # If 304 Not Modified, skip remaining steps
                if ctx.metadata.get("pagefetcher_not_modified"):
                    return ctx

                # Step 3: PreCaptureScriptPlugin (conditional)
                if self._pre_capture_plugin.should_run(ctx):
                    ctx = await self._run_plugin(
                        self._pre_capture_plugin, ctx, "pre_capture_script"
                    )

                # Step 4: ModalDismissPlugin
                ctx = await self._run_plugin(
                    self._modal_dismiss_plugin, ctx, "modal_dismiss"
                )

                # Step 5: Screenshot capture
                ctx = await self._capture_screenshot(ctx, page)

                # Set html_content from page
                try:
                    ctx.html_content = await page.content()
                except Exception as e:
                    logger.error("Failed to get page content: %s", e)
                    ctx.errors.append({
                        "plugin": "PageFetcherStage",
                        "error": f"Failed to get page content: {e}",
                        "type": "content_error",
                    })

        except Exception as e:
            logger.error("PageFetcherStage error: %s", e)
            ctx.errors.append({
                "plugin": "PageFetcherStage",
                "error": str(e),
                "type": "stage_error",
            })
        finally:
            # Clean up page reference from metadata
            ctx.metadata.pop("page", None)

            # Release browser back to pool
            if self._browser_pool is not None and browser is not None and page is not None:
                await self._browser_pool.release(browser, page)

        return ctx

    async def _apply_locale_config(self, page: Any, locale_config: dict) -> None:
        """LocalePlugin の設定をページに適用する。

        Args:
            page: Playwright Page オブジェクト
            locale_config: LocalePlugin が生成した設定 dict
        """
        try:
            context = page.context
            extra_headers = locale_config.get("extra_http_headers", {})
            if extra_headers:
                await context.set_extra_http_headers(extra_headers)
        except Exception as e:
            logger.warning("Failed to apply locale config: %s", e)

    async def _fetch_page(self, ctx: CrawlContext, page: Any) -> CrawlContext:
        """ページを取得する。デルタクロール対応。

        ETag/Last-Modified の条件付きリクエストヘッダーを付与し、
        304 Not Modified の場合はフルクロールをスキップする。

        Args:
            ctx: パイプライン共有コンテキスト
            page: Playwright Page オブジェクト

        Returns:
            処理結果を追記した CrawlContext
        """
        # Build conditional request headers for delta crawl
        extra_headers = _build_conditional_headers(ctx.site)

        if extra_headers:
            try:
                await page.set_extra_http_headers(extra_headers)
            except Exception as e:
                logger.warning("Failed to set conditional headers: %s", e)

        # Navigate to URL
        try:
            response = await page.goto(
                ctx.url, wait_until="networkidle", timeout=30000
            )
        except Exception as e:
            ctx.errors.append({
                "plugin": "PageFetcherStage",
                "error": f"page.goto failed: {e}",
                "type": "navigation_error",
            })
            return ctx

        if response is None:
            ctx.errors.append({
                "plugin": "PageFetcherStage",
                "error": "page.goto returned None response",
                "type": "navigation_error",
            })
            return ctx

        status = response.status

        # Handle 304 Not Modified
        if status == 304:
            ctx.metadata["pagefetcher_not_modified"] = True
            logger.info("304 Not Modified for %s — skipping full crawl", ctx.url)
            return ctx

        # Handle 200 OK — save new ETag/Last-Modified
        if status == 200:
            headers = response.headers
            new_etag = headers.get("etag")
            new_last_modified = headers.get("last-modified")

            if new_etag:
                ctx.metadata["pagefetcher_etag"] = new_etag
            if new_last_modified:
                ctx.metadata["pagefetcher_last_modified"] = new_last_modified

        # DOM stabilization wait
        try:
            await page.wait_for_timeout(DOM_STABILIZATION_WAIT_MS)
        except Exception as e:
            logger.debug("DOM stabilization wait failed (non-critical): %s", e)

        return ctx

    async def _capture_screenshot(self, ctx: CrawlContext, page: Any) -> CrawlContext:
        """スクリーンショットを撮影して ctx.screenshots に追加する。

        Args:
            ctx: パイプライン共有コンテキスト
            page: Playwright Page オブジェクト

        Returns:
            スクリーンショットを追加した CrawlContext
        """
        try:
            screenshot_bytes = await page.screenshot(full_page=True)
            timestamp = datetime.now(timezone.utc)
            image_path = (
                f"screenshots/{ctx.site.id}_default_"
                f"{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
            )

            ctx.screenshots.append(
                VariantCapture(
                    variant_name="default",
                    image_path=image_path,
                    captured_at=timestamp,
                    metadata={
                        "pagefetcher_source": "page_fetcher_stage",
                    },
                )
            )
            # Store raw bytes for downstream processing
            ctx.metadata["pagefetcher_screenshot_bytes"] = screenshot_bytes
        except Exception as e:
            ctx.errors.append({
                "plugin": "PageFetcherStage",
                "error": f"Screenshot capture failed: {e}",
                "type": "screenshot_error",
            })

        return ctx

    async def _run_plugin(
        self, plugin: Any, ctx: CrawlContext, step_name: str
    ) -> CrawlContext:
        """プラグインを実行し、エラーを ctx.errors に記録する。

        Args:
            plugin: CrawlPlugin インスタンス
            ctx: パイプライン共有コンテキスト
            step_name: ステップ名（ログ用）

        Returns:
            処理結果を追記した CrawlContext
        """
        try:
            ctx = await plugin.execute(ctx)
        except Exception as e:
            ctx.errors.append({
                "plugin": plugin.name,
                "stage": "page_fetcher",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            logger.error(
                "Plugin %s failed in PageFetcherStage: %s", plugin.name, e
            )
        return ctx


def _build_conditional_headers(site: Any) -> dict[str, str]:
    """デルタクロール用の条件付きリクエストヘッダーを構築する。

    MonitoringSite の etag / last_modified_header フィールドに基づいて
    If-None-Match / If-Modified-Since ヘッダーを生成する。

    Args:
        site: MonitoringSite インスタンス

    Returns:
        条件付きヘッダーの dict。ヘッダーが不要な場合は空 dict。

    Requirements: 18.2, 18.5
    """
    headers: dict[str, str] = {}

    etag = getattr(site, "etag", None)
    if etag:
        headers["If-None-Match"] = etag

    last_modified = getattr(site, "last_modified_header", None)
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    return headers

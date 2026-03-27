"""
ModalDismissPlugin — PageFetcher ステージ プラグイン。

ページ上のモーダルやオーバーレイを自動的に検出・閉じるプラグイン。
ctx.metadata["page"] に格納された Playwright Page オブジェクトを操作する。

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin

if TYPE_CHECKING:
    from playwright.async_api import Page


# Modal detection selectors
MODAL_SELECTORS = [
    '[role="dialog"]',
    '[role="alertdialog"]',
    ".modal",
    ".overlay",
    '[class*="cookie"]',
    '[class*="consent"]',
    '[id*="cookie"]',
    '[id*="consent"]',
]

# Close button selectors (tried in order)
CLOSE_BUTTON_SELECTORS = [
    'button[aria-label*="close"]',
    ".close",
    'button[class*="close"]',
    'button[class*="dismiss"]',
    'button[class*="accept"]',
]

POST_DISMISS_WAIT_MS = 500


class ModalDismissPlugin(CrawlPlugin):
    """モーダル/オーバーレイを自動検出・閉じるプラグイン。

    検出フロー:
      1. MODAL_SELECTORS でモーダル要素を検出
      2. 各モーダルに対して CLOSE_BUTTON_SELECTORS で閉じるボタンを探してクリック
      3. 閉じるボタンが見つからない場合は Escape キーを送信
      4. 処理完了後 500ms 待機

    エラーが発生した場合は ctx.errors に記録し、パイプラインを中断しない。
    """

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """ページ上のモーダルを検出して閉じる。

        Args:
            ctx: パイプライン共有コンテキスト。
                 ctx.metadata["page"] に Playwright Page が格納されていること。

        Returns:
            処理結果を追記した CrawlContext
        """
        page: Page = ctx.metadata.get("page")
        if page is None:
            ctx.errors.append({
                "plugin": self.name,
                "error": "No page found in ctx.metadata",
                "type": "missing_page",
            })
            return ctx

        try:
            await self._dismiss_modals(page, ctx)
        except Exception as e:
            ctx.errors.append({
                "plugin": self.name,
                "error": str(e),
                "type": "modal_dismiss_error",
            })

        return ctx

    async def _dismiss_modals(self, page: Page, ctx: CrawlContext) -> None:
        """全モーダルセレクタを走査し、検出されたモーダルを閉じる。"""
        for selector in MODAL_SELECTORS:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    try:
                        visible = await element.is_visible()
                        if not visible:
                            continue
                        await self._close_modal(page, element, ctx)
                    except Exception as e:
                        ctx.errors.append({
                            "plugin": self.name,
                            "error": f"Error closing modal ({selector}): {e}",
                            "type": "modal_close_error",
                        })
            except Exception as e:
                ctx.errors.append({
                    "plugin": self.name,
                    "error": f"Error querying selector ({selector}): {e}",
                    "type": "modal_query_error",
                })

    async def _close_modal(
        self, page: Page, modal_element: object, ctx: CrawlContext
    ) -> None:
        """単一モーダルを閉じる。ボタンクリック → Escape フォールバック。"""
        # Try close button selectors
        closed = False
        for btn_selector in CLOSE_BUTTON_SELECTORS:
            try:
                button = await modal_element.query_selector(btn_selector)
                if button:
                    await button.click()
                    closed = True
                    break
            except Exception:
                continue

        # Fallback: Escape key
        if not closed:
            try:
                await page.keyboard.press("Escape")
            except Exception as e:
                ctx.errors.append({
                    "plugin": self.name,
                    "error": f"Escape key fallback failed: {e}",
                    "type": "escape_fallback_error",
                })

        # Wait after dismiss
        await asyncio.sleep(POST_DISMISS_WAIT_MS / 1000)

    def should_run(self, ctx: CrawlContext) -> bool:
        """常に True を返す。"""
        return True

"""
PreCaptureScriptPlugin — PageFetcher ステージ プラグイン。

サイトごとに登録されたカスタム Playwright アクション（JSON 定義）を逐次実行する。
ctx.metadata["page"] に格納された Playwright Page オブジェクトを操作する。

サポートするアクション型:
  - click: セレクタ指定の要素クリック
  - wait: ミリ秒指定の待機
  - select: セレクタと value 指定のセレクト操作
  - type: セレクタと text 指定のテキスト入力

label フィールドが設定されたアクションは実行後にスクリーンショットを取得し、
ctx.screenshots に VariantCapture として追加する。

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.pipeline.context import CrawlContext, VariantCapture
from src.pipeline.plugin import CrawlPlugin

if TYPE_CHECKING:
    from playwright.async_api import Page

SUPPORTED_ACTIONS = {"click", "wait", "select", "type"}


def parse_script(raw: Any) -> list[dict[str, Any]]:
    """PreCaptureScript JSON をパースしてアクションリストに変換する。

    Args:
        raw: JSON 文字列またはパース済みリスト

    Returns:
        アクション dict のリスト

    Raises:
        ValueError: JSON 形式が不正、またはアクション定義が無効な場合
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"Invalid JSON: {e}")

    if not isinstance(raw, list):
        raise ValueError("PreCaptureScript must be a JSON array")

    actions = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Action {i} must be an object")
        action_type = item.get("action")
        if action_type not in SUPPORTED_ACTIONS:
            raise ValueError(
                f"Action {i}: unsupported action type '{action_type}'. "
                f"Supported: {SUPPORTED_ACTIONS}"
            )
        actions.append(item)

    return actions


def serialize_script(actions: list[dict[str, Any]]) -> str:
    """アクションリストを JSON 文字列にシリアライズする。"""
    return json.dumps(actions, ensure_ascii=False)


class PreCaptureScriptPlugin(CrawlPlugin):
    """サイト固有のカスタム Playwright アクションを実行するプラグイン。

    site.pre_capture_script が設定されている場合のみ実行される。
    JSON 定義のアクションを定義順に逐次実行する。
    """

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """PreCaptureScript を解析・実行する。

        Args:
            ctx: パイプライン共有コンテキスト。
                 ctx.metadata["page"] に Playwright Page が格納されていること。
                 ctx.site.pre_capture_script に JSON アクション定義があること。

        Returns:
            処理結果を追記した CrawlContext
        """
        page: Page | None = ctx.metadata.get("page")
        if page is None:
            ctx.errors.append({
                "plugin": self.name,
                "error": "No page found in ctx.metadata",
                "type": "missing_page",
            })
            return ctx

        # Parse script
        raw_script = ctx.site.pre_capture_script
        try:
            actions = parse_script(raw_script)
        except ValueError as e:
            ctx.errors.append({
                "plugin": self.name,
                "error": str(e),
                "type": "validation_error",
            })
            return ctx

        # Execute actions sequentially
        for i, action in enumerate(actions):
            try:
                await self._execute_action(page, action, ctx)
            except Exception as e:
                ctx.errors.append({
                    "plugin": self.name,
                    "error": f"Action {i} ({action.get('action')}): {e}",
                    "type": "action_error",
                })
                # Skip remaining actions on error
                break

        return ctx

    async def _execute_action(
        self, page: Page, action: dict[str, Any], ctx: CrawlContext
    ) -> None:
        """単一アクションを実行する。label 付きの場合はスクリーンショットを取得。"""
        action_type = action["action"]

        if action_type == "click":
            await page.click(action["selector"])
        elif action_type == "wait":
            await asyncio.sleep(action["ms"] / 1000)
        elif action_type == "select":
            await page.select_option(action["selector"], action["value"])
        elif action_type == "type":
            await page.fill(action["selector"], action["text"])

        # Take screenshot if label is set
        label = action.get("label")
        if label:
            screenshot_bytes = await page.screenshot()
            # Store screenshot path — in real usage, the bytes would be saved to disk
            # and the path recorded. For the plugin, we store the bytes in metadata
            # and create a VariantCapture with a placeholder path.
            timestamp = datetime.now(timezone.utc)
            image_path = f"screenshots/{ctx.site.id}_{label}_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"

            ctx.screenshots.append(
                VariantCapture(
                    variant_name=label,
                    image_path=image_path,
                    captured_at=timestamp,
                    metadata={
                        "precapturescript_source": "pre_capture_script",
                        "precapturescript_action": action_type,
                    },
                )
            )
            # Store raw bytes in metadata for downstream processing
            screenshot_key = f"precapturescript_screenshot_{label}"
            ctx.metadata[screenshot_key] = screenshot_bytes

    def should_run(self, ctx: CrawlContext) -> bool:
        """site.pre_capture_script が設定されている場合のみ True を返す。"""
        return ctx.site.pre_capture_script is not None

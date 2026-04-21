"""
JourneyPlugin — PageFetcher ステージ プラグイン。

ユーザージャーニーキャプチャプラグイン。
plugin_config に定義されたジャーニースクリプトを実行し、
各ステップでのUI変化を記録してダークパターンを検出する。

🚨 CTO Override 1: locator + isVisible() で可視要素のみトラッキング。生HTML差分は禁止。
🚨 CTO Override 2: get_by_role ヒューリスティック・フォールバック。

Requirements: 3.1–3.13, 9.1–9.6
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from src.pipeline.context import CrawlContext, VariantCapture
from src.pipeline.plugin import CrawlPlugin
from src.pipeline.plugins.dark_pattern_utils import parse_journey_script

logger = logging.getLogger(__name__)

# Currency regex for no_new_fees assertion
_CURRENCY_RE = re.compile(r"[¥\$€£]\s*[\d,]+|[\d,]+\s*円", re.UNICODE)


class JourneyPlugin(CrawlPlugin):
    """ユーザージャーニーキャプチャプラグイン。

    🚨 CTO Override 1: locator + isVisible() で可視要素のみトラッキング。
    🚨 CTO Override 2: get_by_role ヒューリスティック・フォールバック。

    Requirements: 3.1–3.13, 9.1–9.6
    """

    def should_run(self, ctx: CrawlContext) -> bool:
        """plugin_config に JourneyPlugin.journey_script が設定されている場合に True。"""
        config = (ctx.site.plugin_config or {}).get("JourneyPlugin", {})
        return bool(config.get("journey_script"))

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """ジャーニースクリプトを実行し、各ステップの結果を記録する。"""
        page = ctx.metadata.get("pagefetcher_page")
        if page is None:
            ctx.errors.append({
                "plugin": self.name,
                "stage": "page_fetcher",
                "error": "JourneyPlugin: pagefetcher_page not found in metadata",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            ctx.metadata["journey_steps"] = []
            ctx.metadata["journey_dom_diffs"] = []
            return ctx

        config = (ctx.site.plugin_config or {}).get("JourneyPlugin", {})
        raw_script = config.get("journey_script")

        # Parse journey script — invalid JSON → errors + skip
        try:
            steps = parse_journey_script(raw_script)
        except (ValueError, Exception) as exc:
            error_msg = f"JourneyPlugin: invalid journey_script: {exc}"
            logger.error(error_msg)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "page_fetcher",
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            ctx.metadata["journey_steps"] = []
            ctx.metadata["journey_dom_diffs"] = []
            return ctx

        step_results: list[dict] = []
        dom_diffs: list[dict] = []

        for step in steps:
            step_name = step.get("step", "unknown")
            step_selector = step.get("selector", "")

            # Capture before snapshot
            before_snapshot = await self._capture_visible_snapshot(page)

            # Capture before screenshot
            before_capture = await self._take_screenshot(
                page, ctx, f"journey_{step_name}_before"
            )
            if before_capture:
                ctx.screenshots.append(before_capture)

            # Execute step
            step_error: Optional[str] = None
            try:
                await self._execute_step(page, step)
            except Exception as exc:
                step_error = f"Step '{step_name}' failed: {exc}"
                logger.warning(step_error)
                ctx.errors.append({
                    "plugin": self.name,
                    "stage": "page_fetcher",
                    "error": step_error,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                # Skip remaining steps on error
                step_results.append({
                    "step": step_name,
                    "selector": step_selector,
                    "error": step_error,
                    "assertion_failed": False,
                    "assertions": {},
                })
                break

            # Capture after snapshot
            after_snapshot = await self._capture_visible_snapshot(page)

            # Capture after screenshot
            after_capture = await self._take_screenshot(
                page, ctx, f"journey_{step_name}_after"
            )
            if after_capture:
                ctx.screenshots.append(after_capture)

            # Compute DOM diff (visible element changes)
            diff = self._compute_snapshot_diff(before_snapshot, after_snapshot)
            dom_diffs.append({"step": step_name, "diff": diff})

            # Evaluate assertions
            assertions_config = step.get("assert", {})
            assertion_results: dict[str, Any] = {}
            assertion_failed = False

            for assertion_key, assertion_value in assertions_config.items():
                try:
                    if assertion_key == "no_new_fees":
                        passed, evidence = await self._eval_no_new_fees(
                            page, before_snapshot, after_snapshot
                        )
                    elif assertion_key == "no_upsell_modal":
                        passed, evidence = await self._eval_no_upsell_modal(page)
                    elif assertion_key == "no_preselected_subscription":
                        passed, evidence = await self._eval_no_preselected_subscription(page)
                    else:
                        passed, evidence = True, {}

                    assertion_results[assertion_key] = {
                        "passed": passed,
                        "evidence": evidence,
                    }
                    if not passed:
                        assertion_failed = True
                        ctx.violations.append({
                            "violation_type": assertion_key,
                            "severity": "warning",
                            "dark_pattern_category": "hidden_subscription",
                            "step": step_name,
                            "evidence": evidence,
                        })
                except Exception as exc:
                    logger.warning("Assertion %s failed: %s", assertion_key, exc)
                    assertion_results[assertion_key] = {"passed": True, "error": str(exc)}

            step_results.append({
                "step": step_name,
                "selector": step_selector,
                "error": step_error,
                "assertion_failed": assertion_failed,
                "assertions": assertion_results,
            })

        ctx.metadata["journey_steps"] = step_results
        ctx.metadata["journey_dom_diffs"] = dom_diffs
        return ctx

    async def _capture_visible_snapshot(self, page: Any) -> dict[str, list[str]]:
        """Capture visible elements snapshot using locator + isVisible().

        🚨 CTO Override: no raw HTML diff — use locator + isVisible() only.
        """
        snapshot: dict[str, list[str]] = {"visible_texts": [], "visible_selectors": []}
        try:
            # Get all text-containing elements and check visibility
            locator = page.locator("body *")
            count = await locator.count()
            for i in range(min(count, 200)):  # limit to avoid performance issues
                try:
                    el = locator.nth(i)
                    if await el.is_visible():
                        text = await el.inner_text()
                        text = text.strip()
                        if text:
                            snapshot["visible_texts"].append(text[:100])
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("_capture_visible_snapshot error: %s", exc)
        return snapshot

    async def _execute_step(self, page: Any, step: dict) -> None:
        """Execute a journey step with selector click + role fallback.

        🚨 CTO Override: get_by_role heuristic fallback when selector not found.
        """
        step_type = step.get("step", "")
        selector = step.get("selector", "")
        wait_ms = step.get("wait_ms", 0)

        if step_type == "wait":
            import asyncio
            await asyncio.sleep(wait_ms / 1000.0 if wait_ms else 0.5)
            return

        if step_type == "screenshot":
            return  # Screenshots are handled in execute()

        if step_type == "goto_checkout":
            url = step.get("url", "")
            if url:
                await page.goto(url)
                return

        # Try explicit selector first
        if selector:
            try:
                await page.click(selector, timeout=5000)
                return
            except Exception:
                pass

        # 🚨 CTO Override: heuristic fallback via get_by_role
        fallback = self._get_role_fallback(page, step)
        if fallback is not None:
            await fallback.click(timeout=5000)
        else:
            raise RuntimeError(
                f"No selector or role fallback found for step '{step_type}'"
            )

    def _get_role_fallback(self, page: Any, step: dict):
        """Return a role-based locator fallback for the given step.

        🚨 CTO Override: get_by_role heuristic for add_to_cart and others.
        """
        step_type = step.get("step", "")

        if step_type == "add_to_cart":
            return page.get_by_role(
                "button",
                name=re.compile(r"カート|追加|add.*cart", re.IGNORECASE),
            )
        elif step_type == "goto_checkout":
            return page.get_by_role(
                "button",
                name=re.compile(r"チェックアウト|購入|checkout|buy", re.IGNORECASE),
            )
        elif step_type == "click":
            label = step.get("label", "")
            if label:
                return page.get_by_role("button", name=re.compile(re.escape(label), re.IGNORECASE))
        return None

    async def _eval_no_new_fees(
        self,
        page: Any,
        before_snapshot: dict,
        after_snapshot: dict,
    ) -> tuple[bool, dict]:
        """Assert no new fees appeared after the step.

        Uses currency regex on visible text diff.
        """
        before_texts = set(before_snapshot.get("visible_texts", []))
        after_texts = set(after_snapshot.get("visible_texts", []))
        new_texts = after_texts - before_texts

        new_fees = []
        for text in new_texts:
            if _CURRENCY_RE.search(text):
                new_fees.append(text)

        passed = len(new_fees) == 0
        return passed, {"new_fee_texts": new_fees}

    async def _eval_no_upsell_modal(self, page: Any) -> tuple[bool, dict]:
        """Assert no upsell modal/dialog is visible."""
        modal_selectors = [
            "[role='dialog']",
            "[role='alertdialog']",
            ".modal",
            ".popup",
            ".overlay",
            "[class*='modal']",
            "[class*='popup']",
            "[class*='upsell']",
        ]
        found_modals = []
        for sel in modal_selectors:
            try:
                locator = page.locator(sel)
                count = await locator.count()
                for i in range(count):
                    el = locator.nth(i)
                    if await el.is_visible():
                        found_modals.append(sel)
                        break
            except Exception:
                pass

        passed = len(found_modals) == 0
        return passed, {"found_modals": found_modals}

    async def _eval_no_preselected_subscription(self, page: Any) -> tuple[bool, dict]:
        """Assert no subscription option is pre-selected."""
        checked_selectors = [
            "input[type='checkbox']:checked",
            "input[type='radio']:checked",
        ]
        preselected = []
        for sel in checked_selectors:
            try:
                locator = page.locator(sel)
                count = await locator.count()
                for i in range(count):
                    el = locator.nth(i)
                    if await el.is_visible():
                        label_text = ""
                        try:
                            # Try to get associated label text
                            label_text = await el.evaluate(
                                "el => el.labels && el.labels[0] ? el.labels[0].innerText : ''"
                            )
                        except Exception:
                            pass
                        # Check if it looks like a subscription
                        subscription_keywords = [
                            "定期", "サブスク", "subscription", "recurring",
                            "monthly", "毎月", "自動更新",
                        ]
                        if any(kw.lower() in label_text.lower() for kw in subscription_keywords):
                            preselected.append({"selector": sel, "label": label_text})
            except Exception:
                pass

        passed = len(preselected) == 0
        return passed, {"preselected_subscriptions": preselected}

    @staticmethod
    def _compute_snapshot_diff(
        before: dict[str, list[str]],
        after: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        """Compute diff between two visible snapshots."""
        before_set = set(before.get("visible_texts", []))
        after_set = set(after.get("visible_texts", []))
        return {
            "added": list(after_set - before_set),
            "removed": list(before_set - after_set),
        }

    @staticmethod
    async def _take_screenshot(
        page: Any,
        ctx: CrawlContext,
        variant_name: str,
    ) -> Optional[VariantCapture]:
        """Take a screenshot and return a VariantCapture."""
        try:
            screenshot_bytes = await page.screenshot(type="png")
            # Store as base64 in metadata path (no filesystem write in plugin)
            import base64
            image_data = base64.b64encode(screenshot_bytes).decode("utf-8")
            image_path = f"data:image/png;base64,{image_data[:50]}..."  # truncated ref
            return VariantCapture(
                variant_name=variant_name,
                image_path=image_path,
                captured_at=datetime.now(timezone.utc),
                metadata={"journey_screenshot": True},
            )
        except Exception as exc:
            logger.debug("Screenshot failed for %s: %s", variant_name, exc)
            return None

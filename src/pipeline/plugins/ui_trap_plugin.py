"""
UITrapPlugin — Validator ステージ プラグイン。

UI/UXトラップ検出プラグイン。
事前チェック済みチェックボックス、デフォルト定期購入ラジオボタン、
解約条件DOM距離、コンファームシェイミングを検出する。

Requirements: 4.1–4.11, 14.3, 14.5
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin
from src.pipeline.plugins.dark_pattern_utils import detect_confirmshaming

logger = logging.getLogger(__name__)

# Keywords indicating paid/subscription services
_PAID_SERVICE_KEYWORDS = [
    "定期", "サブスク", "subscription", "recurring", "monthly", "毎月",
    "自動更新", "有料", "プレミアム", "premium", "保険", "insurance",
    "保証", "warranty", "会員", "membership",
]

# Keywords indicating cancellation terms
_CANCELLATION_KEYWORDS = [
    "解約", "キャンセル", "cancel", "退会", "解除", "停止",
    "termination", "unsubscribe",
]

# Default DOM distance threshold
_DEFAULT_DOM_DISTANCE_THRESHOLD = 20


class UITrapPlugin(CrawlPlugin):
    """UI/UXトラップ検出プラグイン。

    Requirements: 4.1–4.11, 14.3, 14.5
    """

    def should_run(self, ctx: CrawlContext) -> bool:
        """html_content があり、pagefetcher_page が metadata に存在する場合に True。"""
        return (
            ctx.html_content is not None
            and ctx.metadata.get("pagefetcher_page") is not None
        )

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """4つの検出器を実行し、結果を ctx.metadata に書き込む。"""
        page = ctx.metadata["pagefetcher_page"]
        detections: list[dict] = []

        # 1. Pre-selected checkboxes (sneak_into_basket)
        try:
            checkbox_detections = await self._detect_preselected_checkboxes(page)
            detections.extend(checkbox_detections)
            for d in checkbox_detections:
                ctx.violations.append({
                    "violation_type": "sneak_into_basket",
                    "severity": "warning",
                    "dark_pattern_category": "sneak_into_basket",
                    "evidence": d,
                })
        except Exception as exc:
            error_msg = f"UITrapPlugin: checkbox detection error: {exc}"
            logger.warning(error_msg)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "validator",
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # 2. Default subscription radios (default_subscription)
        try:
            radio_detections = await self._detect_default_subscription_radios(page)
            detections.extend(radio_detections)
            for d in radio_detections:
                ctx.violations.append({
                    "violation_type": "default_subscription",
                    "severity": "warning",
                    "dark_pattern_category": "default_subscription",
                    "evidence": d,
                })
        except Exception as exc:
            error_msg = f"UITrapPlugin: radio detection error: {exc}"
            logger.warning(error_msg)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "validator",
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # 3. Distant cancellation terms (distant_cancellation_terms)
        try:
            cancellation_detections = await self._detect_distant_cancellation(page)
            detections.extend(cancellation_detections)
            for d in cancellation_detections:
                ctx.violations.append({
                    "violation_type": "distant_cancellation_terms",
                    "severity": "info",
                    "dark_pattern_category": "distant_cancellation_terms",
                    "evidence": d,
                })
        except Exception as exc:
            error_msg = f"UITrapPlugin: cancellation detection error: {exc}"
            logger.warning(error_msg)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "validator",
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # 4. Confirmshaming (confirmshaming)
        try:
            confirmshaming_detections = await self._detect_confirmshaming(page)
            detections.extend(confirmshaming_detections)
            for d in confirmshaming_detections:
                ctx.violations.append({
                    "violation_type": "confirmshaming",
                    "severity": "warning",
                    "dark_pattern_category": "confirmshaming",
                    "evidence": d,
                })
        except Exception as exc:
            error_msg = f"UITrapPlugin: confirmshaming detection error: {exc}"
            logger.warning(error_msg)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "validator",
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        ctx.metadata["uitrap_detections"] = detections
        return ctx

    async def _detect_preselected_checkboxes(self, page: Any) -> list[dict]:
        """Find checked checkboxes with paid service labels.

        Returns list of detection dicts for sneak_into_basket violations.
        """
        detections: list[dict] = []
        try:
            locator = page.locator("input[type='checkbox']:checked")
            count = await locator.count()
            for i in range(count):
                el = locator.nth(i)
                try:
                    if not await el.is_visible():
                        continue
                    # Get associated label text
                    label_text = await el.evaluate(
                        "el => {"
                        "  if (el.labels && el.labels.length > 0) return el.labels[0].innerText;"
                        "  const parent = el.closest('label');"
                        "  if (parent) return parent.innerText;"
                        "  const next = el.nextElementSibling;"
                        "  if (next) return next.innerText;"
                        "  return '';"
                        "}"
                    )
                    label_text = (label_text or "").strip()
                    # Check if label indicates a paid service
                    if any(kw.lower() in label_text.lower() for kw in _PAID_SERVICE_KEYWORDS):
                        detections.append({
                            "type": "preselected_checkbox",
                            "label": label_text,
                            "index": i,
                        })
                except Exception as exc:
                    logger.debug("Checkbox element %d error: %s", i, exc)
        except Exception as exc:
            logger.debug("_detect_preselected_checkboxes error: %s", exc)
        return detections

    async def _detect_default_subscription_radios(self, page: Any) -> list[dict]:
        """Find radio groups where subscription is the default selection.

        Returns list of detection dicts for default_subscription violations.
        """
        detections: list[dict] = []
        try:
            # Find all checked radio buttons
            locator = page.locator("input[type='radio']:checked")
            count = await locator.count()
            for i in range(count):
                el = locator.nth(i)
                try:
                    if not await el.is_visible():
                        continue
                    label_text = await el.evaluate(
                        "el => {"
                        "  if (el.labels && el.labels.length > 0) return el.labels[0].innerText;"
                        "  const parent = el.closest('label');"
                        "  if (parent) return parent.innerText;"
                        "  const next = el.nextElementSibling;"
                        "  if (next) return next.innerText;"
                        "  return '';"
                        "}"
                    )
                    label_text = (label_text or "").strip()
                    # Check if the default-selected radio is a subscription option
                    if any(kw.lower() in label_text.lower() for kw in _PAID_SERVICE_KEYWORDS):
                        detections.append({
                            "type": "default_subscription_radio",
                            "label": label_text,
                            "index": i,
                        })
                except Exception as exc:
                    logger.debug("Radio element %d error: %s", i, exc)
        except Exception as exc:
            logger.debug("_detect_default_subscription_radios error: %s", exc)
        return detections

    async def _detect_distant_cancellation(
        self,
        page: Any,
        threshold: int = _DEFAULT_DOM_DISTANCE_THRESHOLD,
    ) -> list[dict]:
        """Detect when cancellation terms are far from subscription selector.

        DOM distance > threshold triggers a distant_cancellation_terms violation.
        """
        detections: list[dict] = []
        try:
            # Find subscription-related inputs
            sub_locator = page.locator(
                "input[type='checkbox'], input[type='radio'], select"
            )
            sub_count = await sub_locator.count()

            for i in range(sub_count):
                el = sub_locator.nth(i)
                try:
                    if not await el.is_visible():
                        continue
                    label_text = await el.evaluate(
                        "el => {"
                        "  if (el.labels && el.labels.length > 0) return el.labels[0].innerText;"
                        "  const parent = el.closest('label');"
                        "  if (parent) return parent.innerText;"
                        "  return '';"
                        "}"
                    )
                    label_text = (label_text or "").strip()
                    if not any(kw.lower() in label_text.lower() for kw in _PAID_SERVICE_KEYWORDS):
                        continue

                    # Measure DOM distance to cancellation terms
                    distance = await el.evaluate(
                        """el => {
                            const cancelKeywords = ['解約', 'キャンセル', 'cancel', '退会', '解除'];
                            let node = el;
                            let depth = 0;
                            // Walk up to find a common ancestor, then search for cancel text
                            while (node && depth < 50) {
                                const text = node.innerText || '';
                                if (cancelKeywords.some(kw => text.toLowerCase().includes(kw.toLowerCase()))) {
                                    return depth;
                                }
                                node = node.parentElement;
                                depth++;
                            }
                            return depth;
                        }"""
                    )

                    if isinstance(distance, (int, float)) and distance >= threshold:
                        detections.append({
                            "type": "distant_cancellation",
                            "subscription_label": label_text,
                            "dom_distance": distance,
                            "threshold": threshold,
                        })
                except Exception as exc:
                    logger.debug("Cancellation distance element %d error: %s", i, exc)
        except Exception as exc:
            logger.debug("_detect_distant_cancellation error: %s", exc)
        return detections

    async def _detect_confirmshaming(self, page: Any) -> list[dict]:
        """Detect confirmshaming patterns in button texts.

        Uses detect_confirmshaming() from dark_pattern_utils.
        """
        detections: list[dict] = []
        try:
            # Check all buttons and links
            locator = page.locator("button, a, input[type='button'], input[type='submit']")
            count = await locator.count()
            for i in range(count):
                el = locator.nth(i)
                try:
                    if not await el.is_visible():
                        continue
                    text = await el.inner_text()
                    text = (text or "").strip()
                    if not text:
                        # Try value attribute for input buttons
                        text = await el.get_attribute("value") or ""
                        text = text.strip()
                    if not text:
                        continue

                    pattern_type = detect_confirmshaming(text)
                    if pattern_type:
                        detections.append({
                            "type": "confirmshaming",
                            "pattern_type": pattern_type,
                            "text": text,
                            "index": i,
                        })
                except Exception as exc:
                    logger.debug("Confirmshaming element %d error: %s", i, exc)
        except Exception as exc:
            logger.debug("_detect_confirmshaming error: %s", exc)
        return detections

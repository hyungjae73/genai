"""
LLMClassifierPlugin — DataExtractor ステージ プラグイン。

LLMセマンティック分類によるダークパターン検出プラグイン。

🚨 CTO Override: Middle-Out Truncation — 上部20% + 下部30% を保持。
🚨 CTO Override: CoT フィールド順序 — reasoning → evidence → confidence → compliant。
🚨 CTO Override: 指数バックオフ3回リトライ必須（tenacity）。
🚨 CTO Override: 二重挿入（Double Injection）禁止。

Requirements: 2.1–2.14, 8.1–8.7, 13.1–13.7, 14.3
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin
from src.pipeline.plugins.dark_pattern_utils import (
    clamp_confidence,
    extract_json_block,
    middle_out_truncate,
    strip_html_tags,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt template
# 🚨 CTO Override: CoT field order — reasoning → evidence → confidence → compliant
# 🚨 CTO Override: {page_text} replace only, no append at end
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """\
あなたはECサイトのダークパターン検出の専門家です。
以下のページテキストを分析し、以下のいずれかのダークパターンが含まれているかどうかを判定してください。

【検出対象ダークパターン】
1. 隠れた定期購入・自動更新（hidden_subscription）: 定期購入や自動更新の条件が不明瞭に記載されている
2. 小フォント重要文言（misleading_font_size）: 定期購入・解約・手数料・返金・縛り期間等の重要な購入条件が、
   ページ全体のフォントサイズと比較して著しく小さく表示されており、ユーザーの視認性が意図的に低下している

ページテキスト:
{page_text}

以下のJSON形式で回答してください（フィールド順序を厳守）:
```json
{
  "reasoning": "推論プロセスの説明",
  "evidence_text": "証拠となるテキスト（なければ '該当なし'）",
  "confidence": 0.0,
  "is_subscription": false,
  "dark_pattern_type": "hidden_subscription"
}
```

フィールド説明:
- reasoning: 判断の根拠となる推論プロセス（必須）
- evidence_text: ページ内の証拠テキスト（なければ '該当なし'）
- confidence: 確信度 0.0〜1.0（必須）
- is_subscription: 隠れた定期購入または小フォント重要文言が存在するか（必須）
- dark_pattern_type: 検出されたダークパターンの種類。以下のいずれか:
  "hidden_subscription"（隠れた定期購入）または "misleading_font_size"（小フォント重要文言）
"""


class LLMClassifierPlugin(CrawlPlugin):
    """LLMセマンティック分類プラグイン。

    🚨 CTO Override: Middle-Out Truncation — 上部20% + 下部30% を保持。
    🚨 CTO Override: CoT フィールド順序（reasoning → evidence → confidence → compliant）。
    🚨 CTO Override: 指数バックオフ3回リトライ必須。
    🚨 CTO Override: 二重挿入（Double Injection）禁止。

    Requirements: 2.1–2.14, 8.1–8.7, 13.1–13.7, 14.3
    """

    def should_run(self, ctx: CrawlContext) -> bool:
        """evidence_records または html_content があり、LLM_API_KEY が設定されている場合に True。"""
        has_content = bool(ctx.evidence_records or ctx.html_content)
        has_api_key = bool(os.environ.get("LLM_API_KEY"))
        return has_content and has_api_key

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """テキスト抽出 → Middle-Out Truncation → LLM分類。"""
        max_input_tokens = int(os.environ.get("LLM_MAX_INPUT_TOKENS", "4000"))
        max_calls = int(os.environ.get("LLM_MAX_CALLS_PER_CRAWL", "5"))

        text = self._extract_text(ctx)
        truncated = middle_out_truncate(text, max_input_tokens)

        results: list[dict] = []
        token_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        call_count = 0

        try:
            if call_count >= max_calls:
                ctx.metadata["llmclassifier_calls_limited"] = True
            else:
                result = await self._call_llm_with_retry(truncated, ctx.screenshots)
                call_count += 1
                if result:
                    results.append(result)
                    # Accumulate token usage if present
                    usage = result.get("token_usage", {})
                    for k in token_usage:
                        token_usage[k] += usage.get(k, 0)

                if call_count >= max_calls and len(truncated) > max_input_tokens:
                    ctx.metadata["llmclassifier_calls_limited"] = True

        except Exception as exc:
            error_msg = f"LLMClassifierPlugin: unexpected error: {exc}"
            logger.error(error_msg)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "data_extractor",
                "error": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        ctx.metadata["llmclassifier_results"] = results
        ctx.metadata["llmclassifier_token_usage"] = token_usage
        self._add_violations(ctx, results)
        return ctx

    def _extract_text(self, ctx: CrawlContext) -> str:
        """Extract plain text from html_content and evidence_records."""
        parts: list[str] = []

        if ctx.html_content:
            parts.append(strip_html_tags(ctx.html_content))

        for record in ctx.evidence_records:
            if isinstance(record, dict):
                # OCR text or other text evidence
                text = record.get("text") or record.get("ocr_text") or ""
                if text:
                    parts.append(str(text))

        return "\n".join(parts)

    async def _call_llm_with_retry(
        self,
        text: str,
        screenshots: list,
    ) -> Optional[dict]:
        """Call LLM with exponential backoff retry (tenacity, 3 retries).

        🚨 CTO Override: tenacity exponential backoff 3 retries.
        """
        try:
            from tenacity import retry, stop_after_attempt, wait_exponential

            @retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
            )
            async def _call():
                return await self._call_llm(text, screenshots)

            return await _call()
        except ImportError:
            # tenacity not available — call directly
            logger.warning("tenacity not available, calling LLM without retry")
            return await self._call_llm(text, screenshots)
        except Exception as exc:
            error_msg = f"LLMClassifierPlugin: LLM call failed after retries: {exc}"
            logger.error(error_msg)
            return None

    async def _call_llm(self, text: str, screenshots: list) -> Optional[dict]:
        """Call the configured LLM provider.

        🚨 CTO Override: {page_text} replace only, no append at end.
        """
        provider = os.environ.get("LLM_PROVIDER", "openai").lower()
        api_key = os.environ.get("LLM_API_KEY", "")
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

        # Build prompt — 🚨 CTO Override: {page_text} replace only
        prompt = _PROMPT_TEMPLATE.replace("{page_text}", text)

        try:
            if provider == "openai":
                return await self._call_openai(prompt, api_key, model)
            elif provider == "gemini":
                return await self._call_gemini(prompt, api_key, model)
            elif provider == "claude":
                return await self._call_claude(prompt, api_key, model)
            else:
                logger.warning("Unknown LLM provider: %s", provider)
                return None
        except Exception as exc:
            logger.error("LLM API call failed (%s): %s", provider, exc)
            raise

    async def _call_openai(self, prompt: str, api_key: str, model: str) -> Optional[dict]:
        """Call OpenAI API."""
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=api_key)
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
            )
            content = response.choices[0].message.content or ""
            usage = response.usage
            parsed = extract_json_block(content)
            if parsed:
                parsed["confidence"] = clamp_confidence(float(parsed.get("confidence", 0.0)))
                parsed["token_usage"] = {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                }
            return parsed
        except Exception as exc:
            logger.error("OpenAI API error: %s", exc)
            raise

    async def _call_gemini(self, prompt: str, api_key: str, model: str) -> Optional[dict]:
        """Call Google Gemini API."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            gemini_model = genai.GenerativeModel(model or "gemini-pro")
            response = await gemini_model.generate_content_async(prompt)
            content = response.text or ""
            parsed = extract_json_block(content)
            if parsed:
                parsed["confidence"] = clamp_confidence(float(parsed.get("confidence", 0.0)))
                parsed["token_usage"] = {}
            return parsed
        except Exception as exc:
            logger.error("Gemini API error: %s", exc)
            raise

    async def _call_claude(self, prompt: str, api_key: str, model: str) -> Optional[dict]:
        """Call Anthropic Claude API."""
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            response = await client.messages.create(
                model=model or "claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text if response.content else ""
            usage = response.usage
            parsed = extract_json_block(content)
            if parsed:
                parsed["confidence"] = clamp_confidence(float(parsed.get("confidence", 0.0)))
                parsed["token_usage"] = {
                    "prompt_tokens": usage.input_tokens if usage else 0,
                    "completion_tokens": usage.output_tokens if usage else 0,
                    "total_tokens": (usage.input_tokens + usage.output_tokens) if usage else 0,
                }
            return parsed
        except Exception as exc:
            logger.error("Claude API error: %s", exc)
            raise

    @staticmethod
    def _add_violations(ctx: CrawlContext, results: list[dict]) -> None:
        """Add violations for results with confidence >= 0.7 and is_subscription == True."""
        for result in results:
            if not isinstance(result, dict):
                continue
            confidence = result.get("confidence", 0.0)
            is_subscription = result.get("is_subscription", False)
            if confidence >= 0.7 and is_subscription:
                ctx.violations.append({
                    "violation_type": "hidden_subscription",
                    "severity": "warning",
                    "dark_pattern_category": "hidden_subscription",
                    "confidence": confidence,
                    "evidence_text": result.get("evidence_text", ""),
                    "dark_pattern_type": result.get("dark_pattern_type", "hidden_subscription"),
                    "reasoning": result.get("reasoning", ""),
                })

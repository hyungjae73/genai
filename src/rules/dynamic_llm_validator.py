"""
DynamicLLMValidatorPlugin — LLM as a Judge アーキテクチャ。

CrawlPipeline の Validator ステージで実行される CrawlPlugin。
DB に登録された自然言語ルール（DynamicComplianceRuleModel）を
実行時にロードし、LLM に「Judge」として判定させる。

🚨 CTO Override: ルール追加のたびに .py ファイルを作成する設計は却下。
コード変更ゼロでルール追加可能。

実行フロー:
1. DB から is_active=True のルールを取得（merchant_category でフィルタ）
2. 各ルールの prompt_template にページテキスト・契約条件を埋め込み
3. LLM に判定を依頼（Structured Outputs で LLMJudgeVerdict を取得）
4. confidence >= threshold かつ non-compliant で違反を CrawlContext に追加
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional, Protocol, runtime_checkable

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin
from src.rules.base import RuleResult

try:
    import tenacity
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# テキスト抽出・圧縮ユーティリティ
# 🚨 CTO Override: 単純な前方切り捨ては厳禁。
# ---------------------------------------------------------------------------

def _strip_html_to_text(html: str) -> str:
    """HTMLタグをパージして純粋テキストノードを抽出する。

    <script>, <style>, <noscript> タグとその内容を除外し、
    全HTMLタグを除去してテキストノードのみを返す。
    """
    import re

    # script, style, noscript タグとその内容を除去
    text = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 全HTMLタグを除去
    text = re.sub(r"<[^>]+>", " ", text)
    # 連続空白を正規化
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _middle_out_truncate(text: str, max_chars: int) -> str:
    """Middle-Out Truncation アルゴリズム。

    🚨 CTO Override: 単純な先頭切り捨ては厳禁。
    フッターに隠された解約条件の証拠隠滅を防止する。

    上部20%（ヘッダー・価格表示）+ 下部30%（フッター・解約条件）を
    優先保持し、中間50%を切り捨てる。
    切り詰め箇所には '[...中略...]' マーカーを挿入する。

    Args:
        text: 入力テキスト
        max_chars: 最大文字数

    Returns:
        切り詰め後のテキスト（max_chars 以下）
    """
    if len(text) <= max_chars:
        return text

    marker = "\n[...中略...]\n"
    marker_len = len(marker)
    available = max_chars - marker_len

    if available <= 0:
        return text[:max_chars]

    top_len = int(available * 0.20)  # 上部20%
    bottom_len = int(available * 0.30)  # 下部30%
    middle_len = available - top_len - bottom_len  # 残り50%から中間サンプリング

    top_part = text[:top_len]
    bottom_part = text[-bottom_len:] if bottom_len > 0 else ""

    # 中間部分から均等サンプリング（完全に捨てるのではなく一部保持）
    if middle_len > 0:
        middle_start = top_len
        middle_end = len(text) - bottom_len
        middle_text = text[middle_start:middle_end]
        if len(middle_text) > middle_len:
            # 中間テキストの先頭と末尾から均等に取得
            half = middle_len // 2
            middle_sample = middle_text[:half] + middle_text[-half:]
        else:
            middle_sample = middle_text
        return top_part + marker + middle_sample + marker + bottom_part

    return top_part + marker + bottom_part

# LLM Judge のシステムプロンプト
JUDGE_SYSTEM_PROMPT = """あなたは決済コンプライアンスの専門家です。
ECサイトのコンテンツを分析し、指定された契約条件への準拠を判定してください。

判定結果は必ず以下のJSON形式で出力してください:
{
    "compliant": true/false,
    "confidence": 0.0-1.0,
    "evidence_text": "判定根拠となるページ内のテキスト",
    "reasoning": "判定理由の説明"
}"""


@runtime_checkable
class LLMJudgeClient(Protocol):
    """LLM Judge のクライアントインターフェース。

    Gemini/Claude/OpenAI の Structured Outputs を使用して
    LLMJudgeVerdict 形式のレスポンスを返す。
    """

    async def judge(
        self, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        """LLM に判定を依頼し、JSON レスポンスを返す。"""
        ...


@runtime_checkable
class DynamicRuleProvider(Protocol):
    """動的ルールの取得インターフェース。DB からルールを取得する。"""

    async def get_active_rules(
        self, site_id: int, merchant_category: str
    ) -> list[Any]:  # list[DynamicComplianceRuleModel]
        """指定サイト・カテゴリに適用可能なアクティブルールを取得する。"""
        ...


class DynamicLLMValidatorPlugin(CrawlPlugin):
    """LLM as a Judge — 動的コンプライアンスバリデーター。

    CrawlPipeline の Validator ステージで実行される。
    DB に登録された自然言語ルールを LLM に判定させる。
    """

    def __init__(
        self,
        llm_client: Optional[LLMJudgeClient] = None,
        rule_provider: Optional[DynamicRuleProvider] = None,
        max_calls_per_crawl: int = 10,
    ) -> None:
        self._llm_client = llm_client
        self._rule_provider = rule_provider
        self._max_calls = int(
            os.environ.get("LLM_JUDGE_MAX_CALLS_PER_CRAWL", str(max_calls_per_crawl))
        )
        self._call_count = 0

    def should_run(self, ctx: CrawlContext) -> bool:
        """LLM クライアントとルールプロバイダーが設定されている場合に True。"""
        if self._llm_client is None or self._rule_provider is None:
            return False
        has_content = bool(ctx.html_content) or bool(ctx.evidence_records)
        has_key = bool(os.environ.get("LLM_API_KEY"))
        return has_content and has_key

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """DB からルールをロードし、LLM Judge で順次評価する。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            violations と metadata を追記した CrawlContext
        """
        self._call_count = 0
        results: list[dict[str, Any]] = []

        try:
            # 1. DB からアクティブルールを取得
            merchant_category = getattr(ctx.site, "merchant_category", "general") or "general"
            rules = await self._rule_provider.get_active_rules(
                site_id=ctx.site.id,
                merchant_category=merchant_category,
            )

            if not rules:
                ctx.metadata["llmjudge_no_rules"] = True
                return ctx

            # 2. 各ルールを LLM で評価
            for rule in rules:
                if self._call_count >= self._max_calls:
                    ctx.metadata["llmjudge_calls_limited"] = True
                    break

                result = await self._evaluate_single_rule(ctx, rule)
                results.append(result.evidence)

                # 違反があれば violations に追加
                if not result.passed:
                    ctx.violations.append({
                        "violation_type": result.violation_type or "llm_judge_violation",
                        "severity": result.severity,
                        "dark_pattern_category": result.violation_type or "other",
                        "rule_name": result.rule_id,
                        "llm_confidence": result.evidence.get("llm_confidence", 0.0),
                        "evidence_text": result.evidence.get("evidence_text", ""),
                        "reasoning": result.evidence.get("reasoning", ""),
                        "plugin": self.name,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

        except Exception as e:
            logger.error("DynamicLLMValidatorPlugin failed: %s", e)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "validator",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        ctx.metadata["llmjudge_results"] = results
        ctx.metadata["llmjudge_call_count"] = self._call_count
        return ctx

    async def _evaluate_single_rule(
        self, ctx: CrawlContext, rule: Any
    ) -> RuleResult:
        """単一の動的ルールを LLM で評価する。"""
        rule_name = getattr(rule, "rule_name", "unknown")
        prompt_template = getattr(rule, "prompt_template", "")
        severity = getattr(rule, "severity", "warning")
        category = getattr(rule, "dark_pattern_category", "other")
        threshold = getattr(rule, "confidence_threshold", 0.7)

        # プロンプト構築
        page_text = self._extract_page_text(ctx)
        contract = self._get_contract_dict(ctx)
        user_prompt = self._build_prompt(
            prompt_template, page_text, contract, ctx.url
        )

        # LLM 判定（指数バックオフリトライ付き）
        # 🚨 CTO Bugfix: LLM APIは429/502/503が日常茶飯事。
        # 1回のエラーで passed=True を返すのは致命的な偽陰性。
        # 最低3回リトライする。
        try:
            self._call_count += 1

            if TENACITY_AVAILABLE:
                @tenacity.retry(
                    wait=tenacity.wait_exponential(multiplier=1, min=2, max=10),
                    stop=tenacity.stop_after_attempt(3),
                    retry=tenacity.retry_if_exception_type(Exception),
                    reraise=True,
                )
                async def _call_with_retry() -> dict[str, Any]:
                    return await self._llm_client.judge(
                        system_prompt=JUDGE_SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                    )

                response = await _call_with_retry()
            else:
                # tenacity 未インストール時: 手動3回リトライ
                import asyncio
                last_err: Optional[Exception] = None
                for attempt in range(3):
                    try:
                        response = await self._llm_client.judge(
                            system_prompt=JUDGE_SYSTEM_PROMPT,
                            user_prompt=user_prompt,
                        )
                        last_err = None
                        break
                    except Exception as retry_err:
                        last_err = retry_err
                        if attempt < 2:
                            delay = 2 * (2 ** attempt)  # 2s, 4s
                            logger.warning(
                                "LLM Judge retry %d/3 for rule '%s': %s (delay=%ds)",
                                attempt + 1, rule_name, retry_err, delay,
                            )
                            await asyncio.sleep(delay)
                if last_err is not None:
                    raise last_err

        except Exception as e:
            logger.error(
                "LLM Judge failed after retries for rule '%s': %s",
                rule_name, e,
            )
            return RuleResult(
                rule_id=rule_name, passed=True,
                message=f"LLM Judge error (retries exhausted): {e}",
            )

        # レスポンスパース
        compliant = response.get("compliant", True)
        confidence = min(max(float(response.get("confidence", 0.0)), 0.0), 1.0)
        evidence_text = response.get("evidence_text", "")
        reasoning = response.get("reasoning", "")

        is_violation = not compliant and confidence >= threshold

        return RuleResult(
            rule_id=rule_name,
            passed=not is_violation,
            violation_type=category if is_violation else None,
            severity=severity if is_violation else "info",
            evidence={
                "llm_confidence": confidence,
                "evidence_text": evidence_text,
                "reasoning": reasoning,
                "compliant": compliant,
                "rule_name": rule_name,
            },
            message=reasoning if is_violation else "",
        )

    def _extract_page_text(self, ctx: CrawlContext) -> str:
        """CrawlContext からページテキストを抽出する。

        🚨 CTO Override: 生HTMLをそのまま返すのは禁止。
        HTMLタグをパージして純粋テキストノードのみを抽出する。
        <script>, <style>, <noscript> は除外。
        """
        # OCR テキストを優先（既にクリーンテキスト）
        ocr_texts = [
            r.get("ocr_text", "")
            for r in ctx.evidence_records
            if r.get("ocr_text")
        ]
        if ocr_texts:
            return "\n".join(ocr_texts)

        # HTML からタグをパージして純粋テキストを抽出
        raw_html = ctx.html_content or ""
        if not raw_html:
            return ""
        return _strip_html_to_text(raw_html)

    def _get_contract_dict(self, ctx: CrawlContext) -> dict[str, Any]:
        """CrawlContext から契約条件を取得する。"""
        try:
            conditions = getattr(ctx.site, "contract_conditions", None)
            if conditions:
                for c in conditions:
                    if getattr(c, "is_current", False):
                        return {"prices": c.prices, "fees": c.fees,
                                "payment_methods": c.payment_methods,
                                "subscription_terms": c.subscription_terms}
        except Exception:
            pass
        return {}

    def _build_prompt(
        self, template: str, page_text: str,
        contract: dict[str, Any], url: str,
    ) -> str:
        """プロンプトテンプレートを展開する。

        🚨 CTO Override: 単純な前方切り捨て（[:N]）は厳禁。
        Middle-Out Truncation で上部20%+下部30%を保持し、
        フッターに隠された解約条件の見逃しを防止する。

        🚨 CTO Bugfix: 二重挿入（Double Injection）を排除。
        {page_text} プレースホルダがある場合は replace のみ。
        ない場合のみフォールバックとして末尾に追加。
        """
        max_text = int(os.environ.get("LLM_JUDGE_MAX_TEXT_CHARS", "8000"))
        truncated = _middle_out_truncate(page_text, max_text)

        prompt = template

        # プレースホルダがある場合は置換、ない場合は警告+末尾追加
        if "{page_text}" in prompt:
            prompt = prompt.replace("{page_text}", truncated)
        else:
            logger.warning(
                "Prompt template missing '{page_text}' placeholder. "
                "Appending page text to end."
            )
            prompt = f"{prompt}\n\n--- ページコンテンツ ---\n{truncated}"

        prompt = prompt.replace("{contract_terms}",
                                json.dumps(contract, ensure_ascii=False, default=str))
        prompt = prompt.replace("{site_url}", url)

        # 🚨 修正: 二重挿入を排除。return prompt のみ。
        return prompt

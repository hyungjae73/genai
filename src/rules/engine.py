"""
RuleEngine — Hybrid Rule Engine（Built-in + Dynamic LLM）。

2種類のルールを統合実行する:
1. Built-in Rules: エンジニアが書く Python コード（BaseContractRule 継承）
2. Dynamic LLM Rules: コンプライアンス担当者が DB に自然言語プロンプトで登録

🚨 CTO Override: ルール追加のたびに .py ファイルを作成する設計は却下。
Dynamic LLM Rules はコード変更ゼロで追加可能（LLM as a Judge）。
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Optional

from src.rules.base import BaseContractRule, RuleResult

logger = logging.getLogger(__name__)

# Global rule registry: rule_id → BaseContractRule instance
_RULE_REGISTRY: dict[str, BaseContractRule] = {}


def register_rule(rule: BaseContractRule) -> None:
    """ルールをグローバルレジストリに登録する。"""
    if rule.rule_id in _RULE_REGISTRY:
        raise ValueError(f"Rule '{rule.rule_id}' is already registered.")
    _RULE_REGISTRY[rule.rule_id] = rule
    logger.info("Registered built-in rule: %s", rule.rule_id)


def get_rule(rule_id: str) -> Optional[BaseContractRule]:
    """レジストリからルールを取得する。"""
    return _RULE_REGISTRY.get(rule_id)


def list_rules() -> list[str]:
    """登録済みルールIDのリストを返す。"""
    return list(_RULE_REGISTRY.keys())


def clear_registry() -> None:
    """レジストリをクリアする（テスト用）。"""
    _RULE_REGISTRY.clear()


class RuleEngine:
    """Hybrid Rule Engine — Built-in + Dynamic LLM ルールの統合実行。

    実行順序:
    1. Built-in Rules（Python コード、高速・決定論的）
    2. Dynamic LLM Rules（DB 登録の自然言語プロンプト、LLM as a Judge）

    Usage:
        engine = RuleEngine(llm_validator=dynamic_llm_plugin)
        results = await engine.evaluate_all(
            ctx=crawl_context,
            contract=contract_dict,
            merchant_category="subscription",
            builtin_rules=[{"rule_id": "price_match", "params": {}}],
            dynamic_rules=[DynamicComplianceRule(...)],
        )
    """

    def __init__(
        self,
        llm_validator: Optional[Any] = None,  # DynamicLLMValidatorPlugin
    ) -> None:
        self._llm_validator = llm_validator

    async def evaluate_all(
        self,
        ctx: Any,  # CrawlContext
        contract: dict[str, Any],
        merchant_category: str,
        builtin_rules: list[dict[str, Any]],
        dynamic_rules: Optional[list[Any]] = None,  # list[DynamicComplianceRule]
    ) -> list[RuleResult]:
        """Built-in + Dynamic LLM ルールを統合実行する。

        Args:
            ctx: パイプライン共有コンテキスト
            contract: ContractCondition の dict 表現
            merchant_category: 加盟店の商材カテゴリ
            builtin_rules: Built-in ルール仕様リスト
            dynamic_rules: DB 登録の Dynamic LLM ルールリスト

        Returns:
            全ルールの RuleResult リスト
        """
        results: list[RuleResult] = []

        # Phase 1: Built-in Rules（高速・決定論的）
        for rule_spec in builtin_rules:
            rule_id = rule_spec.get("rule_id", "")
            params = rule_spec.get("params", {})

            rule = get_rule(rule_id) or self._try_dynamic_load(rule_id)
            if rule is None:
                logger.warning("Built-in rule '%s' not found, skipping", rule_id)
                continue

            if not rule.applies_to(merchant_category):
                continue

            try:
                result = rule.evaluate(ctx, contract, params)
                results.append(result)
            except Exception as e:
                logger.error("Built-in rule '%s' failed: %s", rule_id, e)
                results.append(RuleResult(
                    rule_id=rule_id, passed=True,
                    message=f"Rule evaluation error: {e}",
                ))

        # Phase 2: Dynamic LLM Rules（LLM as a Judge）
        if dynamic_rules and self._llm_validator:
            for dyn_rule in dynamic_rules:
                if not getattr(dyn_rule, "is_active", True):
                    continue
                # カテゴリフィルタ
                applicable = getattr(dyn_rule, "applicable_categories", None)
                if applicable and merchant_category not in applicable:
                    continue

                try:
                    result = await self._llm_validator.evaluate_dynamic_rule(
                        ctx, contract, dyn_rule
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(
                        "Dynamic LLM rule '%s' failed: %s",
                        getattr(dyn_rule, "rule_name", "unknown"), e,
                    )
                    results.append(RuleResult(
                        rule_id=getattr(dyn_rule, "rule_name", "unknown"),
                        passed=True,
                        message=f"LLM rule evaluation error: {e}",
                    ))

        return results

    def _try_dynamic_load(self, rule_id: str) -> Optional[BaseContractRule]:
        """ルールIDからモジュールを動的にロードする。"""
        module_path = f"src.rules.{rule_id}"
        try:
            module = importlib.import_module(module_path)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseContractRule)
                    and attr is not BaseContractRule
                ):
                    instance = attr()
                    register_rule(instance)
                    return instance
        except (ImportError, ModuleNotFoundError):
            pass
        return None

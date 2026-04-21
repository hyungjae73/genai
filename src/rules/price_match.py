"""
PriceMatchRule — 価格一致チェックルール。

既存の ContractComparisonPlugin の価格比較ロジックを
BaseContractRule として再実装したもの。全商材カテゴリに適用。
"""

from __future__ import annotations

from typing import Any

from src.rules.base import BaseContractRule, RuleResult


class PriceMatchRule(BaseContractRule):
    """契約価格と実際の表示価格の一致を検証するルール。"""

    @property
    def rule_id(self) -> str:
        return "price_match"

    def evaluate(
        self,
        ctx: Any,
        contract: dict[str, Any],
        params: dict[str, Any],
    ) -> RuleResult:
        """価格一致チェック。

        ctx.extracted_data["structured_price_data"]["variants"] の各価格を
        contract["prices"] と比較する。
        """
        price_data = ctx.extracted_data.get("structured_price_data", {})
        variants = price_data.get("variants", [])
        contract_prices = contract.get("prices", {})

        mismatches = []
        for variant in variants:
            actual = variant.get("price")
            expected = self._find_contract_price(
                contract_prices, variant.get("variant_name", "")
            )
            if expected is not None and actual != expected:
                mismatches.append({
                    "variant_name": variant.get("variant_name"),
                    "expected": expected,
                    "actual": actual,
                })

        if mismatches:
            return RuleResult(
                rule_id=self.rule_id,
                passed=False,
                violation_type="price_mismatch",
                severity="warning",
                evidence={"mismatches": mismatches},
                message=f"{len(mismatches)} price mismatch(es) detected",
            )

        return RuleResult(rule_id=self.rule_id, passed=True)

    def _find_contract_price(
        self, prices: dict[str, Any], variant_name: str
    ) -> float | None:
        if variant_name in prices:
            return self._to_float(prices[variant_name])
        variants_list = prices.get("variants", [])
        if isinstance(variants_list, list):
            for v in variants_list:
                if isinstance(v, dict) and v.get("name") == variant_name:
                    return self._to_float(v.get("price"))
        base = prices.get("base_price")
        return self._to_float(base) if base is not None else None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

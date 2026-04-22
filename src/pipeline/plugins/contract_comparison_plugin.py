"""
ContractComparisonPlugin — Validator ステージ プラグイン。

extracted_data 内の各バリアント価格を ContractCondition の prices と比較し、
不一致を violations に追加する。全一致時は metadata に "match" インジケータを記録。

Requirements: 10.1, 10.2, 10.3, 10.4
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin

logger = logging.getLogger(__name__)


class ContractComparisonPlugin(CrawlPlugin):
    """全バリアント価格を ContractCondition と比較するプラグイン。

    extracted_data["structured_price_data"]["variants"] の各バリアント価格を
    ContractCondition.prices と比較し、不一致があれば violations に追加する。

    Requirements: 10.1, 10.2, 10.3, 10.4
    """

    def __init__(self, contract_provider=None):
        """Initialize ContractComparisonPlugin.

        Args:
            contract_provider: Optional callable(site_id) -> ContractCondition.
                               Defaults to None (uses ctx.site.contract_conditions).
                               Useful for dependency injection in tests.
        """
        self._contract_provider = contract_provider

    def should_run(self, ctx: CrawlContext) -> bool:
        """extracted_data に価格情報が存在する場合に True を返す。"""
        price_data = ctx.extracted_data.get("structured_price_data")
        if not price_data:
            return False
        variants = price_data.get("variants", [])
        return len(variants) > 0

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """各バリアント価格を ContractCondition と比較する。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            violations に差異レコードを追記した CrawlContext
        """
        try:
            contract = self._get_contract(ctx)
            if contract is None:
                ctx.errors.append({
                    "plugin": self.name,
                    "stage": "validator",
                    "error": "No contract condition found for site",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return ctx

            contract_prices = contract.get("prices", {})
            price_data = ctx.extracted_data.get("structured_price_data", {})
            variants = price_data.get("variants", [])

            all_match = True
            for variant in variants:
                variant_name = variant.get("variant_name", "")
                actual_price = variant.get("price")
                data_source = variant.get("data_source", "unknown")

                # Look up contract price for this variant
                contract_price = self._find_contract_price(
                    contract_prices, variant_name, actual_price
                )

                if contract_price is not None and actual_price != contract_price:
                    all_match = False
                    ctx.violations.append({
                        "variant_name": variant_name,
                        "contract_price": contract_price,
                        "actual_price": actual_price,
                        "data_source": data_source,
                        "violation_type": "price_mismatch",
                        "plugin": self.name,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            if all_match:
                ctx.metadata["contractcomparison_match"] = True
            else:
                ctx.metadata["contractcomparison_match"] = False

        except Exception as e:
            logger.error("ContractComparisonPlugin failed: %s", e)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "validator",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return ctx

    def _get_contract(self, ctx: CrawlContext) -> dict[str, Any] | None:
        """Get the current contract condition for the site.

        Uses the injected contract_provider if available, otherwise
        attempts to get from ctx.site.contract_conditions.
        """
        if self._contract_provider is not None:
            return self._contract_provider(ctx.site.id)

        # Try to get from site's contract_conditions relationship
        try:
            conditions = getattr(ctx.site, "contract_conditions", None)
            if conditions:
                # Find the current (active) contract condition
                for condition in conditions:
                    if getattr(condition, "is_current", False):
                        return {
                            "prices": condition.prices if hasattr(condition, "prices") else {},
                        }
                # If no current condition, use the first one
                first = conditions[0]
                return {
                    "prices": first.prices if hasattr(first, "prices") else {},
                }
        except Exception as e:
            logger.warning("Failed to get contract conditions: %s", e)

        return None

    def _find_contract_price(
        self,
        contract_prices: dict[str, Any],
        variant_name: str,
        actual_price: float | None,
    ) -> float | None:
        """Find the contract price for a given variant.

        Contract prices can be structured as:
        - {"variant_name": price} — direct mapping
        - {"variants": [{"name": ..., "price": ...}]} — list format
        - {"base_price": price} — single price for all variants

        Returns the contract price if found, None otherwise.
        """
        if not contract_prices:
            return None

        # Direct variant name mapping
        if variant_name in contract_prices:
            return self._parse_price(contract_prices[variant_name])

        # Check variants list
        variants_list = contract_prices.get("variants", [])
        if isinstance(variants_list, list):
            for v in variants_list:
                if isinstance(v, dict) and v.get("name") == variant_name:
                    return self._parse_price(v.get("price"))

        # Fallback to base_price
        base_price = contract_prices.get("base_price")
        if base_price is not None:
            return self._parse_price(base_price)

        return None

    def _parse_price(self, value: Any) -> float | None:
        """Parse a price value to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

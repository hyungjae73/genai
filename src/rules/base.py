"""
BaseContractRule — 契約違反検出ルールの抽象基底クラス。

全ての契約バリデーションルールはこのクラスを継承する。
新しい検出項目を追加する場合、このクラスを継承した新ルールを
1ファイル作成するだけでよい（Open-Closed Principle）。

RuleEngine が rule_id をキーにルールを自動ロードする。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RuleResult:
    """ルール評価結果。

    Attributes:
        rule_id: 評価したルールの識別子
        passed: ルールに合格したか（True=違反なし、False=違反あり）
        violation_type: 違反種別（passed=False の場合のみ）
        severity: 違反の重大度（critical, warning, info）
        evidence: 違反の証拠データ
        message: 人間可読な違反メッセージ
    """

    rule_id: str
    passed: bool
    violation_type: Optional[str] = None
    severity: str = "warning"
    evidence: dict[str, Any] = field(default_factory=dict)
    message: str = ""


class BaseContractRule(ABC):
    """契約違反検出ルールの抽象基底クラス。

    全ルールは以下を実装する:
    - rule_id: ルールの一意識別子（レジストリキー）
    - evaluate(): CrawlContext と ContractCondition を受け取り RuleResult を返す
    - applies_to(): 商材カテゴリに基づく適用可否判定

    Usage:
        class RefundGuaranteeRule(BaseContractRule):
            rule_id = "refund_guarantee"

            def evaluate(self, ctx, contract, params) -> RuleResult:
                # 返金保証テキストの存在チェック
                ...

            def applies_to(self, merchant_category: str) -> bool:
                return merchant_category in ("subscription", "info_product")
    """

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """ルールの一意識別子。RuleEngine のレジストリキーとして使用。"""
        ...

    @abstractmethod
    def evaluate(
        self,
        ctx: Any,  # CrawlContext — 循環インポート回避のため Any
        contract: dict[str, Any],
        params: dict[str, Any],
    ) -> RuleResult:
        """ルールを評価し、結果を返す。

        Args:
            ctx: パイプライン共有コンテキスト（CrawlContext）
            contract: ContractCondition の dict 表現
            params: ルール固有のパラメータ（validation_rules から取得）

        Returns:
            RuleResult（passed=True で違反なし、False で違反あり）
        """
        ...

    def applies_to(self, merchant_category: str) -> bool:
        """このルールが指定された商材カテゴリに適用されるか。

        デフォルトは全カテゴリに適用。サブクラスでオーバーライドして
        特定カテゴリのみに限定可能。

        Args:
            merchant_category: 加盟店の商材カテゴリ

        Returns:
            True の場合このルールを適用する
        """
        return True

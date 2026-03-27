"""
CrawlContext and VariantCapture dataclasses.

パイプライン全体で共有されるコンテキストオブジェクト。
各プラグインは受け取った CrawlContext に処理結果を追記して返却する。

metadata のプラグイン名プレフィックスルール:
    metadata フィールドはプラグイン間のデータ受け渡しに使用される。
    各プラグインは自身のプラグイン名（小文字、アンダースコア区切り）を
    プレフィックスとしたキーでデータを格納すること。

    例:
        - structureddata_empty: True  (StructuredDataPlugin)
        - pagefetcher_etag: "abc123"  (PageFetcher)
        - ocr_confidence_avg: 0.85    (OCRPlugin)

    これにより、プラグイン間のキー衝突を防止し、
    どのプラグインがどのメタデータを書き込んだかを明確にする。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.models import MonitoringSite


@dataclass
class VariantCapture:
    """バリアント別スクリーンショットとメタデータ。

    各バリアント（商品オプション等）ごとに取得されたスクリーンショットと
    そのメタデータを保持する。

    Attributes:
        variant_name: バリアント名（例: "デフォルト", "オプションA"）
        image_path: スクリーンショット画像のファイルパス
        captured_at: キャプチャ日時
        metadata: 追加メタデータ。プラグイン名プレフィックス付きキーで格納する。
    """

    variant_name: str
    image_path: str
    captured_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """dict にシリアライズする。

        captured_at は ISO 8601 形式の文字列に変換される。
        """
        return {
            "variant_name": self.variant_name,
            "image_path": self.image_path,
            "captured_at": self.captured_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VariantCapture":
        """dict からデシリアライズする。

        captured_at は ISO 8601 形式の文字列から datetime に変換される。
        """
        captured_at = data["captured_at"]
        if isinstance(captured_at, str):
            captured_at = datetime.fromisoformat(captured_at)
        return cls(
            variant_name=data["variant_name"],
            image_path=data["image_path"],
            captured_at=captured_at,
            metadata=data.get("metadata", {}),
        )


@dataclass
class CrawlContext:
    """パイプライン全体で共有されるコンテキスト。

    各プラグインは受け取った CrawlContext に処理結果を追記して返却する。
    他プラグインが書き込んだフィールドを破壊してはならない。

    Attributes:
        site: 監視対象サイトの MonitoringSite インスタンス
        url: クロール対象 URL
        html_content: 取得した HTML コンテンツ（nullable）
        screenshots: バリアント別スクリーンショットのリスト
        extracted_data: 抽出されたデータ（価格情報等）
        violations: 検出された違反のリスト
        evidence_records: 証拠保全レコードのリスト
        errors: パイプライン実行中に発生したエラーのリスト
        metadata: プラグイン間データ受け渡し用メタデータ。
            各プラグインはプラグイン名をプレフィックスとしたキーで格納する。
            例: structureddata_empty, pagefetcher_etag, ocr_confidence_avg
    """

    site: MonitoringSite
    url: str
    html_content: Optional[str] = None
    screenshots: list[VariantCapture] = field(default_factory=list)
    extracted_data: dict[str, Any] = field(default_factory=dict)
    violations: list[dict[str, Any]] = field(default_factory=list)
    evidence_records: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """dict にシリアライズする（ラウンドトリップ対応）。

        MonitoringSite は site.id でシリアライズされる。
        VariantCapture リストは各要素の to_dict() でシリアライズされる。
        """
        return {
            "site_id": self.site.id,
            "url": self.url,
            "html_content": self.html_content,
            "screenshots": [s.to_dict() for s in self.screenshots],
            "extracted_data": self.extracted_data,
            "violations": self.violations,
            "evidence_records": self.evidence_records,
            "errors": self.errors,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], site: Optional[MonitoringSite] = None
    ) -> "CrawlContext":
        """dict からデシリアライズする。

        site は以下のいずれかの方法で復元される:
          1. site 引数として直接渡す（推奨）
          2. data 内の site_id から別途取得する（呼び出し側で事前に取得）

        Args:
            data: to_dict() で生成された dict
            site: MonitoringSite インスタンス。None の場合は data["site_id"] から
                  最小限の MonitoringSite を生成する（テスト用途）。

        Returns:
            復元された CrawlContext インスタンス
        """
        if site is None:
            # テスト・デシリアライズ用: site_id のみ持つ最小限の MonitoringSite を生成
            site = MonitoringSite(id=data["site_id"])

        screenshots = [
            VariantCapture.from_dict(s) for s in data.get("screenshots", [])
        ]

        return cls(
            site=site,
            url=data["url"],
            html_content=data.get("html_content"),
            screenshots=screenshots,
            extracted_data=data.get("extracted_data", {}),
            violations=data.get("violations", []),
            evidence_records=data.get("evidence_records", []),
            errors=data.get("errors", []),
            metadata=data.get("metadata", {}),
        )

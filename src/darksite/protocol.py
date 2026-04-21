"""
DarksiteDetectorProtocol — Darksite検出の抽象インターフェース。

契約違反検出（In-site CrawlPipeline）とは完全に分離された
Off-site 検出サービスのプロトコル定義。

2層の検出メカニズム:
1. Dense Vector セマンティック検索（all-MiniLM-L6-v2, 384次元）
   🚨 CTO Override: TF-IDF は廃止。テキスト Spinning に無力なため。
2. 画像 pHash（perceptual hash）比較

🚨 CTO Override: ContentFingerprint は商品の中核ページのみに限定
（is_canonical_product フラグ + max_fingerprints_per_site 上限）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Protocol, runtime_checkable


# Dense Vector 設定
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 384次元、ローカル推論、~50ms/文
EMBEDDING_DIM = 384
SIMILARITY_THRESHOLD = 0.85  # コサイン類似度の「高類似」閾値
IMAGE_PHASH_THRESHOLD = 10  # ハミング距離の「同一画像」閾値

# Fingerprint 制限
DEFAULT_MAX_FINGERPRINTS_PER_SITE = 50
DEFAULT_FINGERPRINT_TTL_DAYS = 90


@dataclass
class DomainMatch:
    """ドメイン類似度マッチ結果。"""

    candidate_domain: str
    legitimate_domain: str
    similarity_score: float  # 0.0–1.0
    match_type: str  # "typosquat", "subdomain", "homoglyph", "tld_swap"
    is_reachable: bool
    http_status: Optional[int] = None


@dataclass
class ContentMatch:
    """コンテンツ類似度マッチ結果。

    🚨 CTO Override: TF-IDF 廃止。Dense Vector（all-MiniLM-L6-v2）で
    セマンティック類似度を計算。Spinning されたテキストも検出可能。
    """

    source_url: str
    target_url: str
    text_similarity: float  # Dense Vector コサイン類似度 (0.0–1.0)
    image_similarity: float  # pHash ハミング距離ベース (0.0–1.0)
    overall_similarity: float  # 加重平均: text(0.6) + image(0.4)
    matched_products: list[dict[str, Any]] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentFingerprint:
    """コンテンツフィンガープリント — 比較元データ。

    🚨 CTO Override: 全ページではなく商品の中核ページのみに限定。
    is_canonical_product=True のページのみ Fingerprint を生成する。
    max_fingerprints_per_site でサイトあたりの上限を制御。
    captured_at ベースで TTL 自動削除（デフォルト 90 日）。
    """

    site_id: int
    url: str
    text_embedding: list[float]  # 384次元 Dense Vector (all-MiniLM-L6-v2)
    image_phashes: list[str]  # pHash hex strings of product images
    product_names: list[str]
    price_info: list[dict[str, Any]]
    is_canonical_product: bool = False  # True = 商品中核ページ（Fingerprint対象）
    text_hash: str = ""  # SHA-256 of normalized text（重複排除用）
    captured_at: Optional[datetime] = None


@dataclass
class DarksiteReport:
    """Darksite検出レポート。"""

    site_id: int
    legitimate_domain: str
    scan_timestamp: datetime
    domain_matches: list[DomainMatch] = field(default_factory=list)
    content_matches: list[ContentMatch] = field(default_factory=list)
    contract_discrepancies: list[dict[str, Any]] = field(default_factory=list)
    risk_score: float = 0.0


@runtime_checkable
class ContentEmbedder(Protocol):
    """テキスト埋め込みモデルのインターフェース。

    🚨 CTO Override: TF-IDF 廃止。all-MiniLM-L6-v2 等の
    軽量ローカル埋め込みモデルを使用する。
    """

    def embed_text(self, text: str) -> list[float]:
        """テキストを Dense Vector に変換する。

        Args:
            text: 入力テキスト

        Returns:
            384次元の埋め込みベクトル
        """
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """複数テキストをバッチで Dense Vector に変換する。"""
        ...

    def cosine_similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """2つのベクトルのコサイン類似度を計算する。"""
        ...


@runtime_checkable
class FingerprintStore(Protocol):
    """ContentFingerprint の永続化インターフェース。

    🚨 CTO Override: is_canonical_product=True のみ保存。
    max_fingerprints_per_site で上限制御。TTL で自動削除。
    """

    async def save(self, fingerprint: ContentFingerprint) -> None:
        """Fingerprint を保存する。is_canonical_product=True のみ受け付ける。"""
        ...

    async def find_similar(
        self, embedding: list[float], threshold: float = SIMILARITY_THRESHOLD
    ) -> list[ContentFingerprint]:
        """類似する Fingerprint を検索する（ANN検索）。"""
        ...

    async def cleanup_expired(self, ttl_days: int = DEFAULT_FINGERPRINT_TTL_DAYS) -> int:
        """TTL 超過の Fingerprint を削除する。削除件数を返す。"""
        ...

    async def count_by_site(self, site_id: int) -> int:
        """サイトあたりの Fingerprint 件数を返す。"""
        ...


@runtime_checkable
class DarksiteDetectorProtocol(Protocol):
    """Darksite検出サービスのプロトコルインターフェース。

    CrawlPipeline とは独立したサービスとして動作する。
    """

    async def scan_domains(
        self, legitimate_domain: str, known_products: list[dict[str, Any]]
    ) -> list[DomainMatch]:
        """類似ドメインをスキャンする。"""
        ...

    async def compare_content(
        self,
        source_fingerprint: ContentFingerprint,
        target_url: str,
    ) -> ContentMatch:
        """正規サイトと対象URLのコンテンツを比較する。

        🚨 CTO Override: Dense Vector（all-MiniLM-L6-v2）で
        セマンティック類似度を計算。TF-IDF は使用しない。
        """
        ...

    async def detect_contract_discrepancies(
        self,
        legitimate_contract: dict[str, Any],
        target_content: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """正規の契約内容と対象コンテンツの乖離を検出する。"""
        ...

    async def full_scan(
        self, site_id: int, legitimate_domain: str
    ) -> DarksiteReport:
        """フルスキャンを実行する。"""
        ...

# Topic: Architecture — アーキテクチャ関連

## Timeline

### 2026-03-26
- CrawlPipeline 4ステージ構成（PageFetcher → DataExtractor → Validator → Reporter）のコアフレームワーク実装完了
- CrawlPlugin 抽象基底クラス: execute(ctx) + should_run(ctx) + name プロパティ
- CrawlContext: パイプライン共有コンテキスト、to_dict/from_dict ラウンドトリップ対応
- resolve_plugin_config: 3層マージ（グローバル → サイト → 環境変数）の純粋関数
- BrowserPool: asyncio.Queue ベース、クラッシュ検出・自動再生成、playwright_launcher 注入
- PageFetcher プラグイン群: LocalePlugin, ModalDismissPlugin, PreCaptureScriptPlugin
- FigJamにアーキテクチャ図7枚生成（パイプライン全体、Celeryキュー分離、BrowserPool、設定マージ、状態遷移、DBスキーマ、フロントエンド構成）
  - 関連: sessions/2026-03-26-initial.md, sessions/2026-03-26-figma.md

### 2026-03-31
- **ドメイン分離アーキテクチャ**: 契約違反検出（In-site）とDarksite検出（Off-site）を完全に別ドメインとして分離
- **In-site: Rule Engine パターン**
  - `BaseContractRule` ABC（rule_id, evaluate, applies_to）+ `RuleResult` dataclass
  - `RuleEngine`（グローバルレジストリ + 動的モジュールロード + カテゴリフィルタ）
  - OCP準拠: 新ルール追加は `src/rules/{rule_id}.py` を1ファイル作成するだけ
  - `PriceMatchRule` を参考実装として作成（既存ContractComparisonPluginのルール化）
- **Off-site: DarksiteDetectorProtocol**
  - `@runtime_checkable Protocol` で CrawlPipeline とは完全独立
  - 4つの dataclass: DomainMatch, ContentMatch, ContentFingerprint, DarksiteReport
  - 3層同定: TF-IDF → pHash → ベクトル埋め込み（初期はLayer 1+2）
  - 関連: sessions/2026-03-31-domain-separation-architecture.md

### 2026-03-31 (CTO Review)
- **🚨 CTO修正指令3件を反映**:
  1. Hybrid Rule Engine: Built-in Rules（Python）+ Dynamic LLM Rules（DB自然言語プロンプト、LLM as a Judge）
  2. TF-IDF全廃 → all-MiniLM-L6-v2 Dense Vector（384次元、ローカル推論）をLayer 1に
  3. ContentFingerprint爆発防止: is_canonical_product フラグ、max_fingerprints_per_site=50、TTL 90日
- DynamicLLMValidatorPlugin: JUDGE_SYSTEM_PROMPT でJSON出力強制、confidence_threshold=0.7
- ContentEmbedder / FingerprintStore Protocol 追加（pgvector ANN検索対応）
  - 関連: sessions/2026-03-31-cto-architecture-review.md

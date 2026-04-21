# Requirements Document

## Introduction

Stealth Browser Hardening は、Payment Compliance Monitor のクローリング基盤をボット検出対策で段階的に強化する機能である。Phase 1（実装済み）では playwright-stealth 統合と StealthBrowserFactory による一元化を完了。Phase 2 では Redis ベースの分散 Cookie/Session 管理を導入し、ステートレスワーカーでのセッション共有を実現する。Phase 2.5 では Page Validation Engine による Soft Block 検知と Vision-LLM フォールバックラベリングを導入し、HTTP 200 の裏に隠れたブロックを正確に識別して AI 学習用の高品質な教師データを蓄積する。Phase 3 では Anti-Bot SaaS ルーティングを追加し、高難度ターゲットを外部スクレイピングサービスへ委譲する。Phase 4 では Multi-Armed Bandit アルゴリズムによる適応型回避エンジンを導入し、ボット対策の変更を自動検知して最適なフェッチ戦略に自律的に切り替える。

## Dependencies

- crawl-pipeline-architecture（BrowserPool, PageFetcherStage, CrawlPlugin）
- 既存 Redis インフラ（docker-compose.yml で定義済み）
- playwright-stealth パッケージ（requirements.txt に追加済み）

## Glossary

- **StealthBrowserFactory**: 全 Playwright ブラウザ生成の単一エントリポイント。stealth パッチ、UA、viewport、proxy、jitter を一元管理するファクトリクラス
- **ScrapingConfig**: pydantic-settings ベースのスクレイピング設定クラス。環境変数から proxy、UA、jitter 等を読み込む
- **BrowserPool**: Playwright ブラウザインスタンスプール。asyncio.Queue ベースで貸出・返却を管理する
- **CrawlerEngine**: robots.txt 遵守・レート制限付きの Web クローラーエンジン
- **PageFetcherStage**: パイプラインの PageFetcher ステージ。BrowserPool からブラウザを取得しプラグインを固定順序で実行する
- **ScreenshotManager**: スクリーンショット撮影・圧縮・保存を管理するクラス
- **ScreenshotCapture**: 単発スクリーンショット撮影ユーティリティ
- **SessionManager**: Redis を中央 Cookie ストレージとして使用するセッション管理クラス
- **FetcherRouter**: ターゲット難易度に基づきリクエストを Playwright または SaaS API にルーティングするルーター
- **PageFetcher**: Playwright ステルスと SaaS API の両方を抽象化するプロトコルインターフェース
- **ValidationStage**: クロールパイプライン内でフェッチ結果の DOM を分析し、Soft Block（CAPTCHA、アクセス拒否等）を検知するステージ
- **Soft Block**: HTTP 200 を返すがページ内容がボット対策のチャレンジページ（CAPTCHA、JavaScript チャレンジ等）である状態
- **VLM (Vision-Language Model)**: スクリーンショット画像を入力として受け取り、画面の内容を分類するマルチモーダル AI モデル（Gemini Vision、Claude Vision 等）
- **MonitoringSite**: 監視対象サイトの DB モデル。is_hard_target フラグで SaaS ルーティング対象を識別する
- **Viewport_Pool**: ランダム選択用の viewport サイズリスト [1920x1080, 1366x768, 1440x900, 1536x864]
- **Delay_Jitter**: リクエスト間に挿入するランダム遅延（0.8〜2.5 秒）
- **AdaptiveEvasionEngine**: Phase 4 の適応型回避エンジン。テレメトリ収集 → 異常検知 → バンディットアルゴリズムによる探索 → 動的適応のループを自律的に実行する
- **Multi-Armed Bandit**: 複数の戦略（Arm）の中から最適なものを探索と搾取のバランスで選択する強化学習アルゴリズム
- **Epsilon-Greedy**: バンディットアルゴリズムの一種。確率 ε でランダムな Arm を探索し、確率 1-ε で現在最良の Arm を搾取する
- **Exploration Mode**: サイトの成功率が閾値を下回った際に FetcherRouter が切り替わるモード。複数の Arm を試行して最適戦略を発見する
- **Arm**: バンディットアルゴリズムにおける個々のフェッチ戦略。例: Playwright+ProxyA、SaaS(ZenRows)、SaaS(ScraperAPI) 等
- **Telemetry**: 各フェッチ試行の結果（HTTP ステータス、応答時間、ボット対策ヘッダー）を記録したデータ

## Requirements

### Requirement 1: StealthBrowserFactory による Playwright 一元化（Phase 1 — 実装済み）

**User Story:** クロールワーカーとして、全ての Playwright ブラウザ生成がステルス設定済みの単一ファクトリを経由することで、システム全体のボット対策姿勢を統一したい。

#### Acceptance Criteria

1. THE StealthBrowserFactory SHALL serve as the single entry point for all Playwright browser, context, and page creation in the codebase
2. WHEN StealthBrowserFactory creates a BrowserContext, THE StealthBrowserFactory SHALL set the User-Agent to the fixed latest Windows Chrome string "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
3. WHEN StealthBrowserFactory creates a BrowserContext, THE StealthBrowserFactory SHALL select a viewport randomly from the Viewport_Pool [1920x1080, 1366x768, 1440x900, 1536x864]
4. WHEN StealthBrowserFactory creates a page, THE StealthBrowserFactory SHALL apply playwright-stealth patches (navigator.webdriver hiding, chrome.runtime patching)
5. IF playwright-stealth is not installed, THEN THE StealthBrowserFactory SHALL log a warning and continue without stealth patches
6. WHEN scraping_stealth_enabled is set to false, THE StealthBrowserFactory SHALL skip stealth patch application

### Requirement 2: Delay Jitter（Phase 1 — 実装済み）

**User Story:** クロールワーカーとして、リクエスト間にランダムな遅延を挿入することで、ボット検出システムに機械的なタイミングと判断されないようにしたい。

#### Acceptance Criteria

1. WHEN StealthBrowserFactory.jitter() is called, THE StealthBrowserFactory SHALL insert a random delay between scraping_jitter_min (default 0.8) and scraping_jitter_max (default 2.5) seconds
2. THE ScrapingConfig SHALL expose scraping_jitter_min and scraping_jitter_max as configurable environment variables

### Requirement 3: Proxy-Ready Architecture（Phase 1 — 実装済み）

**User Story:** 運用者として、環境変数でレジデンシャルプロキシを設定できることで、コード変更なしにクロールトラフィックをプロキシ経由にルーティングしたい。

#### Acceptance Criteria

1. THE ScrapingConfig SHALL load SCRAPING_PROXY_URL, SCRAPING_PROXY_USERNAME, and SCRAPING_PROXY_PASSWORD from environment variables via pydantic-settings
2. THE ScrapingConfig SHALL use SecretStr for SCRAPING_PROXY_PASSWORD to prevent accidental log exposure
3. WHEN SCRAPING_PROXY_URL is configured, THE StealthBrowserFactory SHALL pass the proxy configuration to Playwright's browser launch
4. WHEN SCRAPING_PROXY_URL is not configured, THE StealthBrowserFactory SHALL launch the browser with a direct connection

### Requirement 4: ScrapingConfig 集中設定（Phase 1 — 実装済み）

**User Story:** 開発者として、全てのスクレイピング関連設定が単一の pydantic-settings クラスに集約されていることで、設定の一貫性と発見容易性を確保したい。

#### Acceptance Criteria

1. THE ScrapingConfig SHALL centralize scraping_user_agent, proxy settings, jitter range, and scraping_stealth_enabled in a single BaseSettings class
2. THE ScrapingConfig SHALL provide a module-level singleton instance for direct import
3. THE ScrapingConfig SHALL load configuration from environment variables and .env files with extra="ignore"

### Requirement 5: 全 Playwright 消費者の StealthBrowserFactory 移行（Phase 1 — 実装済み）

**User Story:** 開発者として、全ての Playwright 消費者が StealthBrowserFactory を使用するようリファクタリングされていることで、ブラウザ生成における DRY 違反を排除したい。

#### Acceptance Criteria

1. THE BrowserPool SHALL use StealthBrowserFactory for browser creation, context creation, and stealth application
2. THE CrawlerEngine SHALL use StealthBrowserFactory for browser creation, context creation, stealth application, and jitter insertion
3. THE ScreenshotManager SHALL use StealthBrowserFactory for browser creation, context creation, and stealth application
4. THE ScreenshotCapture SHALL use StealthBrowserFactory for browser creation, context creation, stealth application, and jitter insertion
5. THE PageFetcherStage SHALL acquire stealth-configured pages via BrowserPool (which delegates to StealthBrowserFactory)


### Requirement 6: Redis 分散 Cookie/Session 管理（Phase 2）

**User Story:** クロールワーカーとして、認証済み Cookie を Redis 経由で分散ワーカー間で共有することで、ローカルファイルベースの Cookie 保存なしにログインセッションを再利用したい。

#### Acceptance Criteria

1. THE SessionManager SHALL store cookies in Redis keyed by site_id using a structured key format (e.g., "session:{site_id}:cookies")
2. WHEN a crawl task starts, THE SessionManager SHALL fetch cookies from Redis and inject them into the Playwright BrowserContext
3. WHEN cookies are updated after a successful page load, THE SessionManager SHALL persist the updated cookies back to Redis
4. THE SessionManager SHALL set a configurable TTL on stored cookies (default: 3600 seconds) and remove expired entries automatically via Redis expiry
5. THE SessionManager SHALL use the existing Redis infrastructure defined in docker-compose.yml (redis://redis:6379/0)

### Requirement 7: 認証リフレッシュとログインタスク（Phase 2）

**User Story:** クロールワーカーとして、セッション期限切れ時に別のログインタスクが Redis 上の Cookie を更新することで、手動介入なしにクロールを再開したい。

#### Acceptance Criteria

1. WHEN a crawl request receives a 401 or 403 HTTP status, THE SessionManager SHALL detect the response as an expired session
2. WHEN an expired session is detected, THE SessionManager SHALL enqueue a Celery login task to refresh cookies for the affected site_id
3. WHEN the login task completes successfully, THE SessionManager SHALL store the refreshed cookies in Redis with a new TTL
4. IF the login task fails after 3 retries, THEN THE SessionManager SHALL log the failure and mark the site session as "login_failed"

### Requirement 8: 分散ロックによるログイン排他制御（Phase 2）

**User Story:** 運用者として、同一サイトに対するログインタスクの多重実行を分散ロックで防止することで、ログインスタンピードを回避したい。

#### Acceptance Criteria

1. WHEN a login task is enqueued, THE SessionManager SHALL acquire a Redis distributed lock with key format "login_lock:{site_id}" and TTL of 120 seconds
2. IF the lock is already held by another worker, THEN THE SessionManager SHALL skip the login task and wait for the existing login to complete
3. WHEN the login task completes (success or failure), THE SessionManager SHALL release the distributed lock
4. IF the lock TTL expires before the login task completes, THEN THE SessionManager SHALL allow a new login attempt (preventing deadlock)

### Requirement 9: ステートレスワーカー原則（Phase 2）

**User Story:** プラットフォームエンジニアとして、クロールワーカーがローカルファイルベースの Cookie 保存を持たない完全ステートレスであることで、セッションアフィニティなしに水平スケールしたい。

#### Acceptance Criteria

1. THE SessionManager SHALL store all session data exclusively in Redis, with no local filesystem cookie storage
2. WHEN a worker process starts, THE SessionManager SHALL have no dependency on local state from previous runs
3. THE SessionManager SHALL allow any worker to resume a crawl session for any site_id by fetching cookies from Redis

### Requirement 10: PageFetcher プロトコルインターフェース（Phase 3）

**User Story:** 開発者として、Playwright と SaaS のどちらがページ取得に使われているかを隠蔽する抽象インターフェースにより、消費者をフェッチ実装から分離したい。

#### Acceptance Criteria

1. THE PageFetcher protocol SHALL define a fetch(url, site) method that returns page content (HTML string) and HTTP status code
2. THE StealthPlaywrightFetcher SHALL implement the PageFetcher protocol using StealthBrowserFactory and Playwright
3. THE SaaSFetcher SHALL implement the PageFetcher protocol using httpx API calls to the configured SaaS provider
4. THE PageFetcher protocol SHALL be a Python Protocol class (structural subtyping) to avoid inheritance coupling

### Requirement 11: FetcherRouter によるターゲット難易度ルーティング（Phase 3）

**User Story:** クロールワーカーとして、ターゲット難易度に基づきリクエストが適切なフェッチャーに自動ルーティングされることで、高難度ターゲットは SaaS API を、通常ターゲットは Playwright を使用したい。

#### Acceptance Criteria

1. WHEN a MonitoringSite has is_hard_target set to true, THE FetcherRouter SHALL route the request to the SaaSFetcher
2. WHEN a MonitoringSite has is_hard_target set to false or unset, THE FetcherRouter SHALL route the request to the StealthPlaywrightFetcher
3. THE FetcherRouter SHALL select the fetcher implementation based solely on the MonitoringSite.is_hard_target flag
4. THE MonitoringSite model SHALL include an is_hard_target Boolean column (default: false)

### Requirement 12: Anti-Bot SaaS API 統合（Phase 3）

**User Story:** クロールワーカーとして、高難度ターゲットのページを外部スクレイピング SaaS API（ZenRows、ScraperAPI）経由で取得することで、複雑な回避技術を自前実装せずに高度なボット検出を突破したい。

#### Acceptance Criteria

1. THE SaaSFetcher SHALL send HTTP GET requests to the configured SaaS provider API endpoint via httpx
2. THE SaaSFetcher SHALL include the SaaS API key in each request as required by the provider's authentication scheme
3. THE ScrapingConfig SHALL load SAAS_API_KEY and SAAS_PROVIDER from environment variables via pydantic-settings
4. THE SaaSFetcher SHALL return the HTML content and HTTP status code from the SaaS API response
5. THE SaaSFetcher SHALL support ZenRows and ScraperAPI as provider options

### Requirement 13: SaaS API 障害時の Celery リトライとフェイルセーフ停止（Phase 3）

**User Story:** クロールワーカーとして、SaaS API が利用不可の場合に指数バックオフで自動リトライし、全リトライ失敗時はリクエストを即座に停止してアラートを発報することで、IP BAN のリスクなくクロール障害を運用チームに通知したい。

#### Acceptance Criteria

1. WHEN the SaaS API returns a 429 (rate limited) or 5xx error, THE FetcherRouter SHALL retry the request with exponential backoff (base_delay=30 seconds, max_retries=5)
2. WHEN all SaaS API retries are exhausted for a hard target request, THE FetcherRouter SHALL fail the request, mark the site's crawl status as "SAAS_BLOCKED", and trigger a critical alert to the operations team. THE FetcherRouter SHALL NOT fall back to StealthPlaywrightFetcher for hard targets (自殺的フォールバック禁止: SaaS でブロックされた高難度ターゲットに自前 Playwright で突撃すると IP BAN のリスクがある)
3. THE FetcherRouter SHALL log each retry attempt and the final failure with the site_id, error details, and "SAAS_BLOCKED" status
4. IF the SaaS API returns a non-retryable error (4xx except 429), THEN THE FetcherRouter SHALL fail the request immediately without retry

### Requirement 14: 自己実装禁止の制約（Phase 3）

**User Story:** テックリードとして、マウス移動シミュレーションや TLS フィンガープリント偽装の自前実装を明示的に禁止することで、チームが実績のある SaaS ソリューションに集中するようにしたい。

#### Acceptance Criteria

1. THE System SHALL delegate advanced bot evasion (CAPTCHA solving, TLS JA3 fingerprint rotation, human-like mouse movement) exclusively to external SaaS providers
2. THE System SHALL limit self-implemented stealth measures to playwright-stealth patches, User-Agent setting, viewport randomization, delay jitter, and proxy routing


### Requirement 15: Page Validation Engine による真の成否判定（Phase 2.5 — Soft Block 検知）

**User Story:** データエンジニアとして、HTTP 200 OK の裏に隠れた Soft Block（CAPTCHA 等）を正確に検知し、AI 学習用のノイズのない教師データを蓄積したい。

#### Acceptance Criteria

1. THE System SHALL NOT rely solely on HTTP status codes to determine the success of a fetch operation
2. THE System SHALL implement a ValidationStage in the crawl pipeline that analyzes the DOM for known anti-bot signatures (e.g., Cloudflare challenge page tokens, PerimeterX `_px` cookies, Datadome `datadome` cookies, Akamai Bot Manager markers)
3. IF a page returns HTTP 200 BUT triggers an anti-bot signature OR exhibits a drastic DOM structure anomaly (e.g., page body < 1KB, no expected product/price elements), THEN THE System SHALL label the fetch as `SOFT_BLOCKED` rather than `SUCCESS`
4. THE System SHALL log the complete execution context alongside the binary success/failure outcome into the telemetry store: Proxy ASN (if available), User-Agent, Viewport size, JS execution time, anti-bot response headers, and the `SOFT_BLOCKED` / `SUCCESS` / `HARD_BLOCKED` label
5. THE ValidationStage SHALL maintain a configurable registry of anti-bot signature patterns (environment variable `ANTIBOT_SIGNATURES_JSON` or default built-in list) that can be updated without code deployment

### Requirement 16: Vision-LLM フォールバックラベリング（Phase 2.5 — 未知ブロック画面の自動分類）

**User Story:** MLOps エンジニアとして、未知のブロック画面に遭遇した際、VLM（Vision-Language Model）を用いて自動的に画面を分類し、人間による手動ラベリングのボトルネックを排除したい。

#### Acceptance Criteria

1. WHEN the ValidationStage detects a significant DOM anomaly but cannot match a known anti-bot signature, THE ScreenshotManager SHALL capture a full-page screenshot of the blocked page
2. THE System SHALL asynchronously send the screenshot to a configured VLM API (e.g., Gemini Vision, Claude Vision) with a zero-shot classification prompt asking: "この画面は (a) CAPTCHA チャレンジ、(b) アクセス拒否、(c) コンテンツ変更、(d) 正常なページ のいずれですか？"
3. THE System SHALL update the fetch outcome record based on the VLM's classification: `CAPTCHA_CHALLENGE`, `ACCESS_DENIED`, `CONTENT_CHANGED`, or `NORMAL`
4. THE VLM API key and provider SHALL be configured via pydantic-settings (environment variables `VLM_API_KEY`, `VLM_PROVIDER`)
5. IF the VLM API is unavailable or returns an error, THEN THE System SHALL label the fetch as `UNKNOWN_BLOCK` and log the error without blocking the pipeline
6. THE System SHALL rate-limit VLM API calls per site_id (configurable, default: 5 calls per hour per site, environment variable `VLM_RATE_LIMIT_PER_SITE_HOUR`) to control costs

### Requirement 17: テレメトリと成功率の継続的モニタリング（Phase 4 — 適応型回避エンジン）

**User Story:** AI モデルとして、各サイトのスクレイピング成功率とブロック率（403/429/CAPTCHA）をリアルタイムに把握し、相手のボット対策の変更を検知したい。

#### Acceptance Criteria

1. THE System SHALL log the outcome of every fetch attempt, including HTTP status code, response time in milliseconds, and specific anti-bot response headers (e.g., `cf-ray`, `x-datadome`, `server: cloudflare`)
2. THE System SHALL store fetch telemetry in Redis using a time-series structure keyed by site_id (e.g., `telemetry:{site_id}:results`) with automatic expiry (default: 24 hours)
3. THE System SHALL calculate the trailing 1-hour success rate (HTTP 200 count / total attempt count) for each site_id
4. WHEN a site's trailing 1-hour success rate drops below a configurable threshold (default: 80%, environment variable `ADAPTIVE_SUCCESS_THRESHOLD`), THE System SHALL emit an "anomaly_detected" event for that site_id
5. THE System SHALL expose a `GET /api/sites/{site_id}/fetch-telemetry` endpoint returning the current success rate, total attempts, and block breakdown (403/429/CAPTCHA counts) for the trailing 1-hour window

### Requirement 18: バンディットアルゴリズムによる動的ルーティング（Phase 4 — 適応型回避エンジン）

**User Story:** 運用者として、サイトのボット対策が強化された際、システムが自動的に複数のフェッチ戦略をテストし、最も効果的な手段（SaaS への切り替えなど）へ自律的にルーティングを変更させたい。

#### Acceptance Criteria

1. WHEN a site's "anomaly_detected" event is emitted (success rate below threshold), THE FetcherRouter SHALL enter "Exploration Mode" for that site_id
2. IN Exploration Mode, THE FetcherRouter SHALL distribute requests across available strategies (Arms) using an Epsilon-Greedy algorithm with configurable epsilon (default: 0.2, environment variable `ADAPTIVE_EPSILON`). 利用可能な Arms: (A) Playwright + 現在のプロキシプール + Jitter(大), (B) Playwright + 代替プロキシプール + UA変更, (C) SaaS API (ZenRows), (D) SaaS API (ScraperAPI)
3. THE FetcherRouter SHALL track the success rate of each Arm per site_id in Redis (e.g., `bandit:{site_id}:arm:{arm_id}:successes` / `bandit:{site_id}:arm:{arm_id}:trials`)
4. WHEN Exploration Mode has accumulated sufficient trials (configurable minimum: 20 trials per Arm, environment variable `ADAPTIVE_MIN_TRIALS`), THE FetcherRouter SHALL select the Arm with the highest observed success rate as the "winning strategy"
5. THE FetcherRouter SHALL automatically update the MonitoringSite record: set `is_hard_target=True` if the winning strategy is a SaaS Arm, and persist the preferred fetcher configuration in `plugin_config`
6. WHEN the winning strategy is selected, THE FetcherRouter SHALL exit Exploration Mode and route all subsequent requests for that site_id to the winning Arm
7. THE FetcherRouter SHALL re-enter Exploration Mode if the winning strategy's success rate drops below the threshold again (continuous adaptation loop)
8. THE FetcherRouter SHALL NOT select an Arm that would violate Requirement 13 (自殺的フォールバック禁止: 高難度ターゲットに対して SaaS Arm が全滅した場合、Playwright Arm への切り替えは禁止。代わりに SAAS_BLOCKED として停止)

### Requirement 19: スケジュール設定フロントエンド拡張（is_hard_target / plugin_config）

**User Story:** As a 運用者, I want サイトのスケジュール設定画面から is_hard_target フラグとフェッチャー設定（SaaS/ローカル選択）を管理したい, so that ボット対策が強いサイトの設定をUIから変更できる。

#### Acceptance Criteria

1. THE ScheduleTab SHALL 「高難度ターゲット」トグル（is_hard_target）を表示する
2. WHEN is_hard_target が有効の場合、THE ScheduleTab SHALL フェッチャー選択セクションを表示し、利用するフェッチャー（Playwright / ZenRows / ScraperAPI）を選択可能にする
3. WHEN ユーザーが設定を変更して保存した場合、THE ScheduleTab SHALL `PUT /api/sites/{site_id}` APIに `is_hard_target` と `plugin_config` パラメータを含めて送信する
4. THE ScheduleTab SHALL 現在のフェッチテレメトリ（成功率、ブロック率）を `GET /api/sites/{site_id}/fetch-telemetry` APIから取得して表示する
5. IF is_hard_target が false の場合、THEN THE ScheduleTab SHALL フェッチャー選択セクションを非表示にする
6. THE ApiService SHALL `Site` 型に `is_hard_target?: boolean` と `plugin_config?: Record<string, any>` フィールドを追加する
7. THE ApiService SHALL `FetchTelemetry` 型定義と `getFetchTelemetry(siteId: number)` 関数を提供する

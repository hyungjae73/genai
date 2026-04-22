# 要件定義書: 本番環境対応改善 (production-readiness-improvements)

## はじめに

決済条件監視システム（Payment Compliance Monitor）の本番環境対応に向けた6領域の技術改善を定義する。現在のシステムは10個のDockerコンテナ、4段階のCeleryパイプライン、同期型データベースアクセスのFastAPIバックエンド、手動状態管理のReactフロントエンドで構成されている。本改善では、非同期DBパフォーマンス、分散オブザーバビリティ、コンテナ最適化、フロントエンドデータ管理、リトライ耐障害性、E2Eテストカバレッジを対象とする。

## 用語集

- **API_Server**: FastAPIアプリケーション（`src/main.py`）。ポート8000でRESTエンドポイントを提供する
- **Database_Module**: SQLAlchemyセッション管理モジュール（`src/database.py`）。エンジンとセッションファクトリを提供する
- **Async_Engine**: `asyncpg` ドライバを使用する SQLAlchemy `create_async_engine` インスタンス
- **Async_Session**: Async_Engine にバインドされた `async_sessionmaker` から取得する SQLAlchemy `AsyncSession`
- **Sync_Engine**: `psycopg2` ドライバを使用する SQLAlchemy `create_engine` インスタンス。Alembicマイグレーション用に保持する
- **Celery_Pipeline**: 4段階のCeleryタスクチェーン（crawl → extract → validate → report）＋ notification キュー
- **Crawl_Worker**: `crawl` キューを消費するCeleryワーカーのDockerコンテナ。Playwrightブラウザインスタンスを保持する
- **Trace_Context**: OpenTelemetryのスパンコンテキスト。トレースID、スパンID、伝搬ヘッダーを含む
- **Trace_Middleware**: ルートスパンを作成し、Trace_Context をリクエスト状態に注入するFastAPIミドルウェア
- **Celery_Instrumentation**: Celeryシグナルに接続するOpenTelemetryフック。タスク境界を越えてTrace_Contextを伝搬する
- **Playwright_Image**: Microsoft公式の `mcr.microsoft.com/playwright/python` Dockerベースイメージ。ブラウザ依存関係がプリインストールされている
- **Query_Client**: TanStack Query の `QueryClient` インスタンス。フロントエンドのキャッシュ、再取得、ポーリング設定を管理する
- **Retry_Decorator**: Tenacityベースのデコレータ。指数バックオフ、ジッター、最大リトライ回数を適用する
- **E2E_Test_Suite**: Playwright Testプロジェクト。ブラウザベースのE2Eテストを含む
- **RBAC**: ロールベースアクセス制御。admin、reviewer、viewer の3ロール

## 要件

### 要件 1: 非同期データベースエンジンのセットアップ

**ユーザストーリー:** バックエンド開発者として、Database_Module が asyncpg を使用した Async_Engine を提供するようにしたい。FastAPIエンドポイントがノンブロッキングなデータベース操作を実行できるようにするため。

#### 受入条件

1. WHEN API_Server が起動した場合、THE Database_Module SHALL DATABASE_URL 環境変数から導出した `postgresql+asyncpg://` 接続文字列を使用して Async_Engine を作成する
2. THE Database_Module SHALL Async_Engine にバインドされた `async_sessionmaker` ファクトリを提供し、Async_Session インスタンスを生成する
3. THE Database_Module SHALL 非同期の `get_async_db` 依存関数を公開する。この関数は Async_Session を yield し、成功時にコミット、例外時にロールバック、finally ブロックでセッションをクローズする
4. THE Database_Module SHALL 既存の Sync_Engine と `SessionLocal` ファクトリ（`psycopg2-binary` 使用）を Alembicマイグレーション用に保持する
5. WHEN DATABASE_URL が `postgresql+psycopg2://` を含む場合、THE Database_Module SHALL `postgresql+psycopg2://` を `postgresql+asyncpg://` に置換して非同期URLを導出する
6. WHEN DATABASE_URL がドライバサフィックスなしの `postgresql://` を含む場合、THE Database_Module SHALL 非同期URLを `postgresql+asyncpg://`、同期URLを `postgresql+psycopg2://` として構築する

### 要件 2: FastAPIエンドポイントの非同期移行

**ユーザストーリー:** バックエンド開発者として、全てのFastAPIルートハンドラが async def と Async_Session を使用するようにしたい。API_Server がイベントループをブロックせずに並行リクエストを処理できるようにするため。

#### 受入条件

1. THE API_Server SHALL 全てのルートハンドラ関数を `def` から `async def` に変換する
2. THE API_Server SHALL 全ての `Depends(get_db)` 依存を `Depends(get_async_db)` に置換し、Async_Session を返すようにする
3. THE API_Server SHALL 全ての同期的な SQLAlchemy `session.query()` 呼び出しを、2.0スタイルクエリAPIの `await session.execute(select(...))` に置換する
4. THE API_Server SHALL 全ての同期的な `session.commit()` 呼び出しを `await session.commit()` に置換する
5. THE API_Server SHALL 全ての同期的な `session.refresh()` 呼び出しを `await session.refresh()` に置換する
6. WHEN `_create_initial_admin` 関数がライフスパン起動時に実行される場合、THE API_Server SHALL Alembicマイグレーションが同期ドライバを必要とするため、Sync_Engine セッションを使用する

### 要件 3: Alembicマイグレーションの後方互換性

**ユーザストーリー:** バックエンド開発者として、Alembicが引き続き同期型の psycopg2 ドライバを使用するようにしたい。既存および将来のマイグレーションが変更なしで実行できるようにするため。

#### 受入条件

1. THE Database_Module SHALL Alembicの `env.py` を `psycopg2` ドライバの Sync_Engine を排他的に使用するよう設定する
2. WHEN 開発者が `alembic upgrade head` を実行した場合、THE Database_Module SHALL DATABASE_URL のドライバプレフィックスに関係なく同期接続URLを使用する
3. THE Database_Module SHALL `requirements.txt` に `psycopg2-binary` パッケージを `asyncpg` と並行して保持する

### 要件 4: OpenTelemetryトレース初期化

**ユーザストーリー:** プラットフォームエンジニアとして、API_Server が設定済みのトレーサープロバイダーで OpenTelemetry を初期化するようにしたい。全サービスが相関トレースを出力できるようにするため。

#### 受入条件

1. WHEN API_Server が起動した場合、THE API_Server SHALL `BatchSpanProcessor` を持つ OpenTelemetry `TracerProvider` を初期化する
2. THE API_Server SHALL `OTEL_EXPORTER_OTLP_ENDPOINT` 環境変数でOTLPエクスポーターエンドポイントを設定する（デフォルト: `http://localhost:4317`）
3. THE API_Server SHALL `OTEL_SERVICE_NAME` 環境変数でサービス名リソース属性を `payment-compliance-api` に設定する
4. WHEN `OTEL_ENABLED` 環境変数が `false` に設定されている場合、THE API_Server SHALL OpenTelemetry初期化をスキップし、トレーシングオーバーヘッドなしで動作する

### 要件 5: FastAPI・SQLAlchemyトレース計装

**ユーザストーリー:** プラットフォームエンジニアとして、HTTPリクエストとデータベースクエリが自動的にトレースされるようにしたい。レイテンシのボトルネックがトレーシングバックエンドで可視化されるようにするため。

#### 受入条件

1. THE Trace_Middleware SHALL 各受信HTTPリクエストに対してHTTPメソッド、URLパス、レスポンスステータスコードを含むルートスパンを作成する
2. THE API_Server SHALL `SQLAlchemyInstrumentor` を使用してSQLAlchemyを計装し、データベースクエリスパンをリクエストスパンの子として記録する
3. THE API_Server SHALL `HTTPXClientInstrumentor` を使用して `httpx` 経由の外部HTTPコールを計装し、Trace_Context を下流サービスに伝搬する
4. THE API_Server SHALL アクティブなOpenTelemetryスパンコンテキストから Sentry の `trace_id` を設定し、OpenTelemetry と Sentry を統合する

### 要件 6: Celery分散トレース伝搬

**ユーザストーリー:** プラットフォームエンジニアとして、Celeryタスクがトレースコンテキストを運搬・伝搬するようにしたい。APIリクエストからパイプライン全体を通じて単一のトレースが形成されるようにするため。

#### 受入条件

1. THE Celery_Pipeline SHALL `CeleryInstrumentor` を使用してCeleryを計装し、各タスク実行に対してスパンを作成する
2. WHEN API_Server がCeleryタスクをディスパッチした場合、THE API_Server SHALL 現在の Trace_Context をタスクヘッダーに注入する
3. WHEN Celeryワーカーがタスクを受信した場合、THE Celery_Instrumentation SHALL タスクヘッダーから Trace_Context を抽出し、親トレースにリンクされた子スパンを作成する
4. WHEN Celeryタスクが次のパイプラインステージにチェーンする場合、THE Celery_Instrumentation SHALL チェーンを通じて Trace_Context を伝搬し、crawl → extract → validate → report の各ステージが1つのトレースIDを共有するようにする
5. THE Celery_Pipeline SHALL 各ワーカーの `TracerProvider` にキュー名に一致するサービス名を設定する（例: `payment-compliance-crawl-worker`）

### 要件 7: Crawl Worker Playwright公式ベースイメージ

**ユーザストーリー:** DevOpsエンジニアとして、Crawl_Worker が公式のPlaywright Dockerイメージを使用するようにしたい。ブラウザ依存関係がプリインストールされ、アップストリームで保守されるようにするため。

#### 受入条件

1. THE Crawl_Worker の Dockerfile SHALL ランタイムステージのベースイメージとして `mcr.microsoft.com/playwright/python:v1.40.0-jammy` を使用する
2. THE Crawl_Worker の Dockerfile SHALL Playwright_Image の上に Tesseract OCR（`tesseract-ocr`、`tesseract-ocr-jpn`）と CJKフォント（`fonts-noto-cjk`）をインストールする
3. THE Crawl_Worker の Dockerfile SHALL マルチステージビルドを使用する。ビルダーステージは `python:3.11-slim` でpip依存関係をインストールし、ランタイムステージは Playwright_Image を使用する
4. THE Crawl_Worker の Dockerfile SHALL Playwright_Image にプリインストールされている Playwright システム依存関係（libnss3、libatk、libcups等）の手動 `apt-get` インストールを削除する
5. THE Crawl_Worker の Dockerfile SHALL Playwright_Image にプリインストールされたブラウザが含まれるため、`playwright install chromium` コマンドを削除する
6. THE API_Server および crawl 以外の Celeryワーカー SHALL 既存の `python:3.11-slim` ベースの Dockerfile を変更せずに継続使用する

### 要件 8: TanStack Query クライアントセットアップ

**ユーザストーリー:** フロントエンド開発者として、一元化された Query_Client 設定を持ちたい。全てのデータ取得が一貫したキャッシュと再取得ポリシーを使用するようにするため。

#### 受入条件

1. THE フロントエンドアプリケーション SHALL デフォルト `staleTime` 30秒、デフォルト `gcTime`（ガベージコレクション時間）5分の Query_Client を作成する
2. THE フロントエンドアプリケーション SHALL Reactコンポーネントツリーを Query_Client を提供する `QueryClientProvider` でラップする
3. THE フロントエンドアプリケーション SHALL `@tanstack/react-query` バージョン5.x と `@tanstack/react-query-devtools` を依存関係としてインストールする

### 要件 9: APIレイヤーの TanStack Query フック移行

**ユーザストーリー:** フロントエンド開発者として、各APIエンドポイントをラップするカスタムクエリフックを持ちたい。コンポーネントが自動キャッシュ付きの宣言的データ取得を使用するようにするため。

#### 受入条件

1. THE フロントエンドアプリケーション SHALL 全ての読み取りエンドポイントに対して `useQuery` ベースのフックを提供する（例: `useSites`、`useAlerts`、`useStatistics`、`useReviews`、`useCategories`）
2. THE フロントエンドアプリケーション SHALL 全ての書き込みエンドポイントに対して `useMutation` ベースのフックを提供する（例: `useCreateSite`、`useUpdateSite`、`useDeleteSite`）
3. WHEN ミューテーションが成功した場合、THE ミューテーションフック SHALL 関連するクエリキャッシュを無効化し、古いデータが自動的に再取得されるようにする
4. THE フロントエンドアプリケーション SHALL 既存の `setInterval` ベースの30秒ダッシュボードポーリングを TanStack Query の `refetchInterval` オプション（30000ミリ秒）に置換する
5. THE フロントエンドアプリケーション SHALL クロール進捗と審査キュー更新のCeleryタスクステータスポーリングに TanStack Query の `refetchInterval` を使用する（タスクステータスが `PENDING` または `STARTED` の間は2000ミリ秒間隔）

### 要件 10: Tenacity リトライデコレータ定義

**ユーザストーリー:** バックエンド開発者として、Tenacityを使用した標準化された Retry_Decorator を持ちたい。全てのリトライ可能な操作が一貫したバックオフとジッター設定を使用するようにするため。

#### 受入条件

1. THE Retry_Decorator SHALL 1秒から開始し倍率2の指数バックオフを使用する
2. THE Retry_Decorator SHALL 最終例外を発生させる前に最大3回のリトライを適用する
3. THE Retry_Decorator SHALL サンダリングハード防止のため、各バックオフ間隔に最大1秒のランダムジッターを追加する
4. THE Retry_Decorator SHALL 各リトライ試行をWARNINGレベルでログ出力する（試行回数、待機時間、例外メッセージを含む）
5. THE Retry_Decorator SHALL リトライ対象の例外型の設定可能なリストを受け付ける（デフォルト: `(Exception,)`）
6. THE Retry_Decorator SHALL 例外型マッチング以外のカスタムリトライ条件用のオプショナルな `retry_if` コーラブルを受け付ける

### 要件 11: リトライデコレータの外部呼び出しへの適用

**ユーザストーリー:** バックエンド開発者として、Retry_Decorator が全ての外部サービス呼び出しに適用されるようにしたい。一時的な障害が統一的に処理されるようにするため。

#### 受入条件

1. THE Celery_Pipeline SHALL LLM API呼び出し（OpenAI、Anthropic）に Retry_Decorator を適用し、HTTP 429（レートリミット）と HTTP 5xx（サーバーエラー）レスポンスでリトライする
2. THE notification ワーカー SHALL Slack webhook とメール送信操作に Retry_Decorator を適用し、接続エラーと HTTP 5xx レスポンスでリトライする
3. THE Celery_Pipeline SHALL `httpx` 経由の外部HTTPリクエストに Retry_Decorator を適用し、`httpx.ConnectError`、`httpx.TimeoutException`、HTTP 5xx レスポンスでリトライする
4. THE Crawl_Worker SHALL Playwrightスクリーンショットキャプチャ操作に Retry_Decorator を適用し、`playwright.async_api.TimeoutError` でリトライする
5. WHEN 全てのリトライ試行が尽きた場合、THE Retry_Decorator SHALL `tenacity.RetryError` 経由で完全なリトライ履歴を利用可能にした上で元の例外を発生させる

### 要件 12: Playwright E2Eテストプロジェクトセットアップ

**ユーザストーリー:** QAエンジニアとして、ブラウザベースのE2Eテスト用に設定された Playwright Test プロジェクトを持ちたい。重要なユーザーワークフローが自動的に検証されるようにするため。

#### 受入条件

1. THE E2E_Test_Suite SHALL `@playwright/test` をテストランナーとして使用し、`playwright.config.ts` 設定ファイルを持つ
2. THE E2E_Test_Suite SHALL Chromium をデフォルトブラウザとして設定し、ビューポートを 1280x720 ピクセルとする
3. THE E2E_Test_Suite SHALL `E2E_BASE_URL` 環境変数から `baseURL` を設定する（デフォルト: `http://localhost:5173`）
4. THE E2E_Test_Suite SHALL テストアーティファクト（スクリーンショット、トレース、動画）を `test-results/` ディレクトリに保存する
5. THE E2E_Test_Suite SHALL admin ユーザーとして認証し、テスト間で再利用するためにセッション状態を保存するグローバルセットアップスクリプトを設定する

### 要件 13: E2E 重要ワークフローテスト

**ユーザストーリー:** QAエンジニアとして、主要なユーザージャーニーをカバーするE2Eテストを持ちたい。コアワークフローのリグレッションがデプロイ前に検出されるようにするため。

#### 受入条件

1. THE E2E_Test_Suite SHALL ログインフローをテストする: ログインページに遷移、認証情報を入力、送信、ダッシュボードへのリダイレクトを検証
2. THE E2E_Test_Suite SHALL サイト管理をテストする: 新規サイトを作成、サイト一覧に表示されることを検証、サイト名を更新、サイトを削除
3. THE E2E_Test_Suite SHALL アラートワークフローをテストする: アラートページに遷移、アラート一覧の読み込みを検証、アラート詳細の重要度とメッセージの表示を検証
4. THE E2E_Test_Suite SHALL 審査ワークフローをテストする: 審査ダッシュボードに遷移、審査案件を開く、審査判定を送信、判定が記録されたことを検証
5. THE E2E_Test_Suite SHALL クロールトリガーフローをテストする: サイトのクロールをトリガー、ステータスエンドポイントでクロール完了をポーリング、クロール結果の表示を検証

### 要件 14: E2E RBAC検証テスト

**ユーザストーリー:** QAエンジニアとして、ロールベースのアクセス制限を検証するE2Eテストを持ちたい。UIレベルで不正アクセスが防止されることを確認するため。

#### 受入条件

1. WHEN viewer として認証されている場合、THE E2E_Test_Suite SHALL ユーザー管理ページにアクセスできず、禁止レスポンスまたはリダイレクトが返されることを検証する
2. WHEN reviewer として認証されている場合、THE E2E_Test_Suite SHALL reviewer が審査ダッシュボードにアクセスし判定を送信できることを検証する
3. WHEN reviewer として認証されている場合、THE E2E_Test_Suite SHALL reviewer が admin 専用ページ（ユーザー管理、システム設定）にアクセスできないことを検証する
4. WHEN admin として認証されている場合、THE E2E_Test_Suite SHALL ユーザー管理とシステム設定を含む全ページにアクセスできることを検証する
5. THE E2E_Test_Suite SHALL グローバルセットアップ時に作成された各ロール（admin、reviewer、viewer）用の個別認証状態ファイルを使用する

### 要件 15: E2E CI/CD統合

**ユーザストーリー:** DevOpsエンジニアとして、E2EテストをGitHub Actions CIパイプラインに統合したい。ワークフローのリグレッションがデプロイをブロックするようにするため。

#### 受入条件

1. THE E2E_Test_Suite SHALL `main` ブランチを対象とするプルリクエストで Playwright テストを実行する GitHub Actions ワークフローファイルを提供する
2. THE GitHub Actions ワークフロー SHALL E2Eテスト実行前に `docker-compose up` でアプリケーションスタックを起動する
3. THE GitHub Actions ワークフロー SHALL テスト失敗時にテストアーティファクト（スクリーンショット、トレース）を GitHub Actions アーティファクトとしてアップロードする
4. THE GitHub Actions ワークフロー SHALL テストランナージョブに公式の `mcr.microsoft.com/playwright` Dockerイメージを使用し、CIでのブラウザインストールを回避する
5. IF いずれかのE2Eテストが失敗した場合、THEN THE GitHub Actions ワークフロー SHALL チェックを失敗としてマークし、プルリクエストのマージをブロックする

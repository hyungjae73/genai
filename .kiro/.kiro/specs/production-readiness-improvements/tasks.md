# 実装計画: 本番環境対応改善 (production-readiness-improvements)

## 概要

設計書のマイグレーション戦略に従い、3フェーズで段階的に実装する。Phase 1（HIGH優先度: AsyncSession + OpenTelemetry）→ Phase 2（MEDIUM優先度: Playwright公式イメージ + TanStack Query + Tenacityリトライ）→ Phase 3（LOW優先度: E2Eテスト）。各フェーズは独立してデプロイ可能であり、既存機能への破壊的変更を回避する。

## タスク

### Phase 1: APIサバイバビリティ（HIGH優先度）

- [x] 1. AsyncSession移行 — database.py の非同期エンジン追加
  - [x] 1.1 `src/database.py` に `derive_async_url` / `derive_sync_url` ヘルパー関数を追加する
    - `postgresql://`、`postgresql+psycopg2://`、`postgresql+asyncpg://` の3パターンを処理
    - 既存の `engine` / `SessionLocal` / `get_db` は削除せず保持する
    - _要件: 1.1, 1.5, 1.6_
  - [x]* 1.2 `derive_async_url` / `derive_sync_url` のプロパティベーステストを作成する
    - **Property 1: データベースURL導出の往復一貫性**
    - **検証対象: 要件 1.1, 1.5, 1.6**
  - [x] 1.3 `src/database.py` に `async_engine` + `AsyncSessionLocal` + `get_async_db` を追加する
    - `create_async_engine` で `ASYNC_DATABASE_URL` を使用
    - `async_sessionmaker(bind=async_engine, expire_on_commit=False)` を設定
    - `get_async_db` は自動コミットしない（設計判断: 明示的コミットパターン）
    - 例外時は `rollback`、finally で `close` を保証
    - _要件: 1.1, 1.2, 1.3_
  - [x]* 1.4 `get_async_db` のプロパティベーステストを作成する
    - **Property 2: 非同期セッション依存関数のロールバック・クローズ保証**
    - **検証対象: 要件 1.3**
  - [x] 1.5 `requirements.txt` に `asyncpg` が既に含まれていることを確認し、不足パッケージがあれば追加する
    - _要件: 3.3_

- [x] 2. FastAPIエンドポイントの非同期移行
  - [x] 2.1 `src/api/sites.py` を `async def` + `Depends(get_async_db)` + 2.0スタイルクエリに移行する
    - `session.query()` → `await session.execute(select(...))` に変換
    - POST/PUT/DELETE では `await session.commit()` を明示的に呼び出す
    - GET では commit を呼ばない（設計判断: 参照系の無駄なコミット回避）
    - _要件: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 2.2 `src/api/customers.py` を非同期に移行する
    - _要件: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 2.3 `src/api/contracts.py` を非同期に移行する
    - _要件: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 2.4 `src/api/alerts.py` を非同期に移行する
    - _要件: 2.1, 2.2, 2.3, 2.4_
  - [x] 2.5 `src/api/monitoring.py` を非同期に移行する
    - _要件: 2.1, 2.2, 2.3, 2.4_
  - [x] 2.6 `src/api/categories.py`、`src/api/field_schemas.py`、`src/api/extraction.py` を非同期に移行する
    - _要件: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 2.7 `src/api/screenshots.py`、`src/api/verification.py`、`src/api/crawl.py` を非同期に移行する
    - _要件: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 2.8 `src/api/reviews.py` と `src/review/service.py` を AsyncSession 対応に移行する
    - ReviewService のコンストラクタを `AsyncSession` 受け取りに変更
    - 全クエリを 2.0スタイル (`await db.execute(select(...))`) に変換
    - `db.commit()` → `await db.commit()` に変換
    - _要件: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 2.9 `src/api/auth.py`、`src/api/users.py`、`src/api/audit_logs.py` を非同期に移行する
    - _要件: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 2.10 `src/api/schedules.py`、`src/api/notifications.py`、`src/api/dark_patterns.py`、`src/api/extracted_data.py` を非同期に移行する
    - _要件: 2.1, 2.2, 2.3, 2.4, 2.5_
  - [x] 2.11 `src/main.py` の `_create_initial_admin` が `SessionLocal`（同期）を継続使用することを確認する
    - Celeryワーカーも同期セッションを継続使用（設計判断: Celeryは同期のまま維持）
    - _要件: 2.6_

- [x] 3. Alembic後方互換性の確認
  - [x] 3.1 `alembic/env.py` が `Sync_Engine`（psycopg2）を排他的に使用するよう設定する
    - `derive_sync_url` を使用して常に psycopg2 URL を保証
    - _要件: 3.1, 3.2_
  - [x]* 3.2 `alembic upgrade head` が正常に動作することを検証するテストを作成する
    - _要件: 3.1, 3.2_

- [x] 4. チェックポイント — Phase 1 AsyncSession移行の検証
  - 全テストが通ることを確認し、不明点があればユーザーに質問する。

- [x] 5. OpenTelemetry計装 — TracerProvider初期化
  - [x] 5.1 `src/core/telemetry.py` を新規作成し、`init_telemetry` 関数を実装する
    - `TracerProvider` + `BatchSpanProcessor` + OTLPエクスポーター設定
    - `OTEL_ENABLED` 環境変数による有効/無効切り替え（デフォルト: `true`）
    - `OTEL_EXPORTER_OTLP_ENDPOINT`（デフォルト: `http://localhost:4317`）
    - `OTEL_SERVICE_NAME`（デフォルト: `payment-compliance-api`）
    - _要件: 4.1, 4.2, 4.3, 4.4_
  - [x] 5.2 `instrument_fastapi` 関数を実装する
    - `FastAPIInstrumentor` + `SQLAlchemyInstrumentor` + `HTTPXClientInstrumentor` を計装
    - _要件: 5.1, 5.2, 5.3_
  - [x] 5.3 `src/main.py` のライフスパンで `init_telemetry()` と `instrument_fastapi(app)` を呼び出す
    - _要件: 4.1, 5.1_
  - [x] 5.4 `requirements.txt` に OpenTelemetry 関連パッケージを追加する
    - `opentelemetry-api`、`opentelemetry-sdk`、`opentelemetry-exporter-otlp`
    - `opentelemetry-instrumentation-fastapi`、`opentelemetry-instrumentation-sqlalchemy`
    - `opentelemetry-instrumentation-httpx`、`opentelemetry-instrumentation-celery`
    - _要件: 4.1, 5.1, 5.2, 5.3_

- [x] 6. OpenTelemetry計装 — Celery分散トレース伝搬
  - [x] 6.1 `src/core/telemetry.py` に `instrument_celery`、`inject_trace_context`、`extract_trace_context` を追加する
    - `CeleryInstrumentor` によるタスクスパン自動作成
    - タスクヘッダーへの traceparent 注入・抽出
    - _要件: 6.1, 6.2, 6.3, 6.4_
  - [x]* 6.2 `inject_trace_context` / `extract_trace_context` のプロパティベーステストを作成する
    - **Property 3: OpenTelemetryトレースコンテキストの注入・抽出往復**
    - **検証対象: 要件 6.2, 6.3**
  - [x] 6.3 `src/celery_app.py` の `worker_init` シグナルで `instrument_celery` を呼び出す
    - 各ワーカーに `OTEL_SERVICE_NAME` を設定（例: `payment-compliance-crawl-worker`）
    - _要件: 6.1, 6.5_
  - [x] 6.4 `docker-compose.yml` の全ワーカーサービスに `OTEL_SERVICE_NAME` 環境変数を追加する
    - _要件: 6.5_
  - [x]* 6.5 Celeryパイプライン全体のトレース伝搬を検証する統合テストを作成する
    - _要件: 6.2, 6.3, 6.4_

- [x] 7. チェックポイント — Phase 1 完了確認
  - 全テストが通ることを確認し、不明点があればユーザーに質問する。

### Phase 2: 信頼性・効率性（MEDIUM優先度）

- [x] 8. Crawl Worker ベースイメージ最適化
  - [x] 8.1 `docker/Dockerfile.crawl` を新規作成する
    - ビルダーステージ: `python:3.11-slim` で pip 依存関係インストール
    - ランタイムステージ: `mcr.microsoft.com/playwright/python:v1.40.0-jammy`
    - Tesseract OCR + CJKフォント + postgresql-client を追加インストール
    - `playwright install chromium` と libnss3 等の手動 apt-get を削除
    - _要件: 7.1, 7.2, 7.3, 7.4, 7.5_
  - [x] 8.2 `docker-compose.yml` の `crawl-worker` サービスの `dockerfile` を `docker/Dockerfile.crawl` に変更する
    - 他のワーカー（extract, validate, report, notification）は既存 `docker/Dockerfile` を継続使用
    - _要件: 7.6_

- [x] 9. TanStack Query導入 — クライアントセットアップ
  - [x] 9.1 `@tanstack/react-query` と `@tanstack/react-query-devtools` を `package.json` に追加する
    - _要件: 8.3_
  - [x] 9.2 `frontend/src/lib/queryClient.ts` を新規作成する
    - `staleTime: 30_000`、`gcTime: 300_000`、`retry: 1`、`refetchOnWindowFocus: false`
    - _要件: 8.1_
  - [x] 9.3 `frontend/src/main.tsx` または `App.tsx` で `QueryClientProvider` をラップする
    - 開発環境では `ReactQueryDevtools` も追加
    - _要件: 8.2_

- [x] 10. TanStack Query導入 — クエリフック実装
  - [x] 10.1 `frontend/src/hooks/queries/useSites.ts` を作成する
    - `useSites`、`useSite`、`useCreateSite`、`useUpdateSite`、`useDeleteSite`
    - ミューテーション `onSuccess` で `['sites']` キャッシュを無効化
    - _要件: 9.1, 9.2, 9.3_
  - [x] 10.2 `frontend/src/hooks/queries/useAlerts.ts` を作成する
    - `useAlerts`、`useSiteAlerts`
    - _要件: 9.1_
  - [x] 10.3 `frontend/src/hooks/queries/useStatistics.ts` を作成する
    - `useStatistics` に `refetchInterval: 30_000` を設定
    - 既存の `setInterval` ベースのダッシュボードポーリングを置換
    - _要件: 9.1, 9.4_
  - [x] 10.4 `frontend/src/hooks/queries/useReviews.ts` を作成する
    - `useReviews`、`useReviewDetail`、`useReviewStats`、`useAssignReviewer`、`useDecidePrimary`、`useDecideSecondary`
    - ミューテーション `onSuccess` で `['reviews']`、`['review-stats']` を無効化
    - _要件: 9.1, 9.2, 9.3_
  - [x] 10.5 `frontend/src/hooks/queries/useCategories.ts` を作成する
    - _要件: 9.1, 9.2, 9.3_
  - [x] 10.6 Celeryタスクステータスポーリングフックを実装する
    - `useCrawlStatus(jobId)`: PENDING/STARTED 時は `refetchInterval: 2000`、SUCCESS 時に `invalidateQueries` 発火
    - キャッシュ無効化は `onSuccess`（202受信時）ではなく、ポーリングが SUCCESS を返したタイミングで実行（設計判断）
    - _要件: 9.5_
  - [x]* 10.7 ポーリング間隔の条件分岐ロジックのプロパティベーステスト（fast-check）を作成する
    - **Property 7: タスクステータスポーリング間隔の条件分岐**
    - **検証対象: 要件 9.5**

- [x] 11. TanStack Query導入 — 既存コンポーネントの移行
  - [x] 11.1 ダッシュボード系ページ（`Dashboard.tsx` 等）の `setInterval` + `useState` を `useQuery` フックに置換する
    - _要件: 9.4_
  - [x] 11.2 サイト管理ページ（`Sites.tsx` 等）を `useSites` / `useCreateSite` 等のフックに移行する
    - _要件: 9.1, 9.2, 9.3_
  - [x] 11.3 審査ワークフローページ（`ReviewDashboard.tsx`、`ReviewDetail.tsx`、`Reviews.tsx`）を `useReviews` 等のフックに移行する
    - _要件: 9.1, 9.2, 9.3_
  - [x] 11.4 アラート、カテゴリ、その他のページを対応するクエリフックに移行する
    - _要件: 9.1, 9.2, 9.3_

- [x] 12. チェックポイント — TanStack Query移行の検証
  - 全テストが通ることを確認し、不明点があればユーザーに質問する。

- [x] 13. Tenacityリトライデコレータの実装
  - [x] 13.1 `src/core/retry.py` を新規作成し、`with_retry` デコレータを実装する
    - 指数バックオフ（min=1s, max=10s, multiplier=2）+ ランダムジッター（max=1s）
    - `max_attempts=3`、`retry_on` で例外型指定、`retry_if` でカスタム条件
    - `before_sleep_log` で WARNING レベルログ出力
    - `reraise=True` で元の例外を再送出
    - _要件: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_
  - [x]* 13.2 `with_retry` のプロパティベーステストを作成する
    - **Property 4: リトライデコレータのバックオフ時間境界**
    - **Property 5: リトライデコレータの最大試行回数遵守**
    - **Property 6: 非リトライ対象例外の即時伝搬**
    - **検証対象: 要件 10.1, 10.2, 10.3, 10.5**
  - [x] 13.3 `requirements.txt` に `tenacity` パッケージを追加する
    - _要件: 10.1_

- [x] 14. Tenacityリトライの外部呼び出しへの適用
  - [x] 14.1 LLM API呼び出し（OpenAI/Anthropic）に `with_retry` を適用する
    - `retry_on=(HTTPStatusError,)` で HTTP 429 と 5xx をリトライ対象に設定
    - 4xx クライアントエラーはリトライしない
    - _要件: 11.1_
  - [x] 14.2 notification-worker の Slack webhook / メール送信に `with_retry` を適用する
    - `retry_on=(ConnectionError, SMTPException)` + HTTP 5xx
    - _要件: 11.2_
  - [x] 14.3 `httpx` 経由の外部HTTPリクエストに `with_retry` を適用する
    - `retry_on=(httpx.ConnectError, httpx.TimeoutException)` + HTTP 5xx
    - _要件: 11.3_
  - [x] 14.4 crawl-worker の Playwright スクリーンショットキャプチャに `with_retry` を適用する
    - `retry_on=(playwright.async_api.TimeoutError,)`
    - _要件: 11.4_
  - [x]* 14.5 リトライデコレータの実際のHTTPエラーハンドリングを検証する統合テストを作成する
    - 全リトライ試行失敗時に `RetryError` 経由で元の例外が発生することを検証
    - _要件: 11.5_

- [x] 15. チェックポイント — Phase 2 完了確認
  - 全テストが通ることを確認し、不明点があればユーザーに質問する。

### Phase 3: 品質保証（LOW優先度）

- [x] 16. E2Eテストプロジェクトセットアップ
  - [x] 16.1 `genai/e2e/` ディレクトリを作成し、`@playwright/test` をインストールする
    - `package.json` に Playwright Test 依存関係を追加
    - _要件: 12.1_
  - [x] 16.2 `genai/e2e/playwright.config.ts` を作成する
    - Chromium デフォルト、ビューポート 1280x720、`E2E_BASE_URL` 環境変数対応
    - `screenshot: 'only-on-failure'`、`trace: 'on-first-retry'`、`video: 'on-first-retry'`
    - `outputDir: 'test-results/'`
    - _要件: 12.1, 12.2, 12.3, 12.4_
  - [x] 16.3 `genai/e2e/global-setup.ts` を作成する
    - admin / reviewer / viewer の3ロールで認証し、セッション状態を `auth/*.json` に保存
    - _要件: 12.5, 14.5_

- [x] 17. E2E 重要ワークフローテスト
  - [x] 17.1 `genai/e2e/tests/login.spec.ts` を作成する
    - ログインページ遷移 → 認証情報入力 → 送信 → ダッシュボードリダイレクト検証
    - _要件: 13.1_
  - [x] 17.2 `genai/e2e/tests/site-management.spec.ts` を作成する
    - 固有テストデータ生成（`e2e-site-${Date.now()}-...`）でサイト作成 → 一覧表示検証 → 更新 → 削除
    - `afterEach` でテストデータクリーンアップ
    - _要件: 13.2_
  - [x] 17.3 `genai/e2e/tests/alerts.spec.ts` を作成する
    - アラートページ遷移 → 一覧読み込み検証 → 詳細の重要度・メッセージ表示検証
    - _要件: 13.3_
  - [x] 17.4 `genai/e2e/tests/review-workflow.spec.ts` を作成する
    - `test.describe.configure({ mode: 'serial' })` で直列実行を保証（設計判断: 状態遷移テスト）
    - 審査ダッシュボード遷移 → 案件オープン → 判定送信 → 記録検証
    - _要件: 13.4_
  - [x] 17.5 `genai/e2e/tests/crawl-trigger.spec.ts` を作成する
    - クロールトリガー → ステータスポーリング → 結果表示検証
    - _要件: 13.5_

- [x] 18. E2E RBAC検証テスト
  - [x] 18.1 `genai/e2e/tests/rbac.spec.ts` を作成する
    - viewer: ユーザー管理ページアクセス不可を検証
    - reviewer: 審査ダッシュボードアクセス可 + admin専用ページアクセス不可を検証
    - admin: 全ページアクセス可を検証
    - 各ロール用の個別認証状態ファイルを使用
    - _要件: 14.1, 14.2, 14.3, 14.4, 14.5_

- [x] 19. E2E CI/CD統合
  - [x] 19.1 `genai/e2e/.github/workflows/e2e.yml` を作成する
    - `main` ブランチ対象のPRで Playwright テストを実行
    - `docker-compose up` でアプリケーションスタック起動
    - テスト失敗時にアーティファクト（スクリーンショット、トレース）をアップロード
    - 公式 `mcr.microsoft.com/playwright` Docker イメージを使用
    - テスト失敗時にチェックを失敗としてマーク
    - _要件: 15.1, 15.2, 15.3, 15.4, 15.5_

- [x] 20. 最終チェックポイント — 全フェーズ完了確認
  - 全テストが通ることを確認し、不明点があればユーザーに質問する。

## 備考

- `*` マーク付きのタスクはオプションであり、MVP優先時にスキップ可能
- 各タスクは特定の要件を参照しており、トレーサビリティを確保
- チェックポイントで段階的な検証を実施
- プロパティベーステストは設計書の正当性プロパティに基づく（Hypothesis / fast-check）
- ユニットテストは特定の例外ケースとエッジケースを検証
- **設計判断の反映**: `get_async_db` は自動コミットしない / Celeryワーカーは同期維持 / Celeryタスクキャッシュ無効化はポーリングSUCCESS時 / E2Eテストは固有データ生成+serialモード

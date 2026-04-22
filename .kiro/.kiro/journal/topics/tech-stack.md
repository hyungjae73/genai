# Topic: Tech Stack — 技術スタック一覧

## Last Updated: 2026-03-26

## Backend

| カテゴリ | 技術 | バージョン | 用途 |
|---------|------|-----------|------|
| 言語 | Python | 3.11 | バックエンド全体 |
| Webフレームワーク | FastAPI | 0.104.1 | REST API |
| ASGIサーバー | Uvicorn | 0.24.0 | FastAPI実行 |
| バリデーション | Pydantic | 2.5.0 | リクエスト/レスポンススキーマ |
| ORM | SQLAlchemy | 2.0.23 | DBアクセス（mapped_column構文） |
| マイグレーション | Alembic | 1.13.0 | DBスキーマ管理 |
| DB | PostgreSQL | 15 (Alpine) | メインデータストア |
| DBドライバ | psycopg2-binary | 2.9.9 | PostgreSQL接続 |
| タスクキュー | Celery | 5.3.4 | 非同期タスク処理（4キュー分離） |
| メッセージブローカー | Redis | 7.2 (Alpine) | Celeryブローカー + 結果バックエンド + レートリミッター |
| ブラウザ自動化 | Playwright | 1.40.0 | サイトクロール + スクリーンショット |
| HTML解析 | BeautifulSoup4 | 4.12.2 | 構造化データ抽出（JSON-LD, Microdata, OG） |
| XMLパーサー | lxml | 4.9.3 | HTML/XMLパース高速化 |
| OCR | Tesseract (pytesseract) | 0.3.10 | スクリーンショットからテキスト抽出 |
| 画像処理 | Pillow | 10.1.0 | ROI切り出し、画像操作 |
| HTTP クライアント | httpx | 0.25.2 | 外部API呼び出し |
| テンプレート | Jinja2 | 3.1.2 | 通知テンプレート |
| 機械学習 | scikit-learn | 1.3.2 | テキスト分類・類似度計算 |
| 通知（メール） | SendGrid | 6.11.0 | メール通知送信 |
| 通知（Slack） | slack-sdk | 3.26.1 | Slack Webhook通知 |
| 暗号化 | cryptography | 41.0.7 | データ暗号化 |
| 認証 | PyJWT + bcrypt | 2.8.0 / 4.1.2 | JWT認証、パスワードハッシュ |
| オブジェクトストレージ | MinIO SDK (S3互換) | — | スクリーンショット/証拠画像保存 |

## Frontend

| カテゴリ | 技術 | バージョン | 用途 |
|---------|------|-----------|------|
| 言語 | TypeScript | 5.9.3 | フロントエンド全体 |
| UIフレームワーク | React | 19.2.0 | SPA |
| ルーティング | React Router | 7.13.1 | ページ遷移 |
| HTTPクライアント | Axios | 1.13.6 | API通信 |
| チャート | Chart.js + react-chartjs-2 | 4.5.1 / 5.3.1 | 価格履歴グラフ |
| チャート（追加） | Recharts | 3.8.0 | ダッシュボードチャート |
| 画像ビューア | react-zoom-pan-pinch | 3.7.0 | スクリーンショット拡大表示 |
| ビルドツール | Vite | 7.3.1 | 開発サーバー + ビルド |
| リンター | ESLint | 9.39.1 | コード品質 |
| 本番サーバー | Nginx | Alpine | 静的ファイル配信 |

## テスト

| カテゴリ | 技術 | バージョン | 用途 |
|---------|------|-----------|------|
| テストDB | testcontainers-python | >=4.0.0 | テスト用PostgreSQLコンテナ自動管理 |
| バックエンドテスト | pytest | 7.4.3 | ユニット/統合テスト |
| 非同期テスト | pytest-asyncio | 0.21.1 | async関数テスト |
| カバレッジ | pytest-cov | 4.1.0 | コードカバレッジ |
| PBT（バックエンド） | Hypothesis | 6.92.1 | プロパティベーステスト（27プロパティ） |
| フロントエンドテスト | Vitest | 4.0.18 | コンポーネントテスト |
| DOM テスト | Testing Library | 16.3.2 | React コンポーネントテスト |
| PBT（フロントエンド） | fast-check | 4.6.0 | フロントエンドプロパティテスト |
| テストデータ | Faker | 20.1.0 | テストデータ生成 |

## Infrastructure / DevOps

| カテゴリ | 技術 | バージョン | 用途 |
|---------|------|-----------|------|
| コンテナ | Docker | マルチステージビルド | アプリケーションコンテナ化 |
| オーケストレーション | docker-compose | — | ローカル開発環境（10サービス） |
| CI/CD | GitHub Actions | — | PR検証、デプロイ、ロールバック |
| オブジェクトストレージ | MinIO | latest | ローカルS3互換ストレージ |
| Node.js | Node 20 (Alpine) | — | フロントエンドビルド |

## docker-compose サービス構成（10サービス）

| サービス | イメージ | concurrency | キュー |
|---------|---------|-------------|-------|
| postgres | postgres:15-alpine | — | — |
| redis | redis:7.2-alpine | — | — |
| api | python:3.11-slim | — | — |
| celery-worker | python:3.11-slim | — | default |
| crawl-worker | python:3.11-slim | 2 | crawl（Playwright + BrowserPool） |
| extract-worker | python:3.11-slim | 8 | extract（CPU最適化） |
| validate-worker | python:3.11-slim | 8 | validate（CPU最適化） |
| report-worker | python:3.11-slim | 4 | report（DB/Storage I/O） |
| minio | minio/minio:latest | — | — |
| frontend | nginx:alpine | — | — |

## パイプラインアーキテクチャ

```
CrawlPipeline (4ステージ)
├── Stage 1: PageFetcher    → LocalePlugin, PreCaptureScriptPlugin, ModalDismissPlugin
├── Stage 2: DataExtractor  → StructuredDataPlugin, ShopifyPlugin, HTMLParserPlugin, OCRPlugin
├── Stage 3: Validator      → ContractComparisonPlugin, EvidencePreservationPlugin
└── Stage 4: Reporter       → DBStoragePlugin, ObjectStoragePlugin, AlertPlugin
```

## 関連ファイル
- Backend依存: `genai/requirements.txt`
- Frontend依存: `genai/frontend/package.json`
- Docker: `genai/docker/Dockerfile`, `genai/frontend/Dockerfile.prod`
- Compose: `genai/docker-compose.yml`

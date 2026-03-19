# 実装計画: Docker CI/CD パイプライン

## 概要

Payment Compliance Monitorの全サービスをDockerベースで統一管理し、GitHub Actions CI/CDパイプラインを構築する。既存コードのDocker互換性修正、マルチステージDockerfile、環境別Docker Compose構成、エントリポイントスクリプト、ヘルスチェック拡張、GitHub Actionsワークフローを段階的に実装する。

## Tasks

- [x] 1. 既存コードのDocker互換性修正
  - [x] 1.1 `src/tasks.py`のSQLiteフォールバックを削除し、`database.py`の`SessionLocal`を使用するようリファクタリング
    - `cleanup_old_data`, `crawl_all_sites`, `scan_all_fake_sites`の3タスクで`DATABASE_URL`未設定時のSQLiteフォールバックを削除
    - `src/database.py`の`SessionLocal`をインポートして使用
    - _Requirements: 1.1, 3.5_
  - [x] 1.2 `src/main.py`のCORS設定を環境変数`CORS_ORIGINS`から読み込むよう修正
    - `allow_origins=["*"]`を`os.getenv("CORS_ORIGINS", "*").split(",")`に変更
    - 本番環境ではフロントエンドのオリジンのみ許可
    - _Requirements: 9.2_

- [ ] 2. バックエンド マルチステージDockerfile
  - [x] 2.1 `genai/docker/Dockerfile`をマルチステージ構成に書き換え
    - builderステージ: python:3.11-slim + gcc + requirements.txtインストール
    - productionステージ: python:3.11-slim + Playwright/Chromium依存関係
    - 非rootユーザー`appuser`でプロセス実行
    - レイヤーキャッシュ最適化（requirements.txtを先にCOPY）
    - _Requirements: 2.1, 2.3, 2.4, 2.5, 9.1_

  - [x] 2.2 Property 3のプロパティベーステスト: Dockerfileのセキュリティ準拠
    - **Property 3: Dockerfileのセキュリティ準拠**
    - テストファイル: `genai/tests/test_docker_cicd_properties.py`
    - 全本番用Dockerfileに対し、(a) ベースイメージがalpine/slimバリアント、(b) 非rootユーザーのUSERディレクティブが含まれることを検証
    - Hypothesisで複数のDockerfileパスをストラテジーとして生成
    - **Validates: Requirements 2.3, 9.1**

- [x] 3. フロントエンド本番用Dockerfile・Nginx設定
  - [x] 3.1 `genai/frontend/Dockerfile.prod`を新規作成
    - buildステージ: node:20-alpine + npm ci + npm run build
    - productionステージ: nginx:alpine + ビルド済み静的ファイル配信
    - _Requirements: 2.2, 2.4, 9.1_
  - [x] 3.2 `genai/frontend/nginx.conf`を新規作成
    - SPAルーティング対応（`try_files $uri $uri/ /index.html`）
    - gzip圧縮、キャッシュヘッダー設定
    - _Requirements: 2.2_
  - [x] 3.3 `genai/frontend/.dockerignore`を更新
    - `node_modules`, `.env*`, `.git`, `dist`等を除外
    - _Requirements: 9.3_

- [x] 4. エントリポイントスクリプトとマイグレーション自動化
  - [x] 4.1 `genai/docker/entrypoint.sh`を新規作成
    - 必須環境変数チェック（DATABASE_URL, REDIS_URL, SECRET_KEY）
    - 本番環境でDEBUG=false, ENABLE_DOCS=false強制
    - DATABASE_URLからDB接続情報をパース
    - pg_isreadyによるDB接続待機（最大30回リトライ、2秒間隔）
    - RUN_MIGRATIONS=true時のみAlembicマイグレーション実行
    - マイグレーション失敗時にexit 1でアプリケーション起動中止
    - _Requirements: 3.3, 3.5, 6.1, 6.2, 6.3, 6.4, 9.5_
  - [x] 4.2 Property 5のプロパティベーステスト: 本番環境でのDEBUGモード強制無効化
    - **Property 5: 本番環境でのDEBUGモード強制無効化**
    - テストファイル: `genai/tests/test_docker_cicd_properties.py`
    - ENVIRONMENT=production時にDEBUG=falseが強制されることをランダムなDEBUG値で検証
    - **Validates: Requirements 3.3, 9.5**
  - [x] 4.3 Property 6のプロパティベーステスト: 必須環境変数の起動前検証
    - **Property 6: 必須環境変数の起動前検証**
    - テストファイル: `genai/tests/test_docker_cicd_properties.py`
    - ランダムな必須変数の欠落パターンに対し、エントリポイントが非ゼロ終了コードを返すことを検証
    - **Validates: Requirements 3.5**
  - [x] 4.4 Property 7のプロパティベーステスト: マイグレーション失敗時のデプロイ中止
    - **Property 7: マイグレーション失敗時のデプロイ中止**
    - テストファイル: `genai/tests/test_docker_cicd_properties.py`
    - ランダムな非ゼロ終了コードに対し、エントリポイントがアプリケーション起動せずに終了することを検証
    - **Validates: Requirements 6.2**

- [x] 5. チェックポイント - Dockerfileとエントリポイントの検証
  - 全テストが通ることを確認し、ユーザーに質問があれば確認する。

- [x] 6. Docker Compose環境別構成
  - [x] 6.1 `genai/docker-compose.yml`（ベース）を修正
    - 全サービスにhealthcheck設定を追加
    - ポート公開をベースから削除（オーバーライドで設定）
    - `screenshots_data`ボリュームを追加し、APIとCelery Workerにマウント
    - `depends_on`に`condition: service_healthy`を設定
    - _Requirements: 1.1, 1.2, 1.5, 8.2, 8.3_
  - [x] 6.2 `genai/docker-compose.override.yml`を新規作成（開発用）
    - 設定可能なポートマッピング（POSTGRES_PORT, REDIS_PORT, API_PORT環境変数）
    - ホットリロード用ボリュームマウント（src, tests, alembic, frontend/src）
    - API: `--reload`フラグ付きuvicorn、RUN_MIGRATIONS=true
    - Celery Worker/Beat: RUN_MIGRATIONS=false
    - Frontend: Vite dev server、VITE_API_BASE_URL設定
    - _Requirements: 1.1, 1.3, 1.4, 3.4_
  - [x] 6.3 `genai/docker-compose.prod.yml`を新規作成（本番用）
    - GHCRイメージ参照（ghcr.io/${GITHUB_REPOSITORY}/api, frontend）
    - リソース制限（memory limits）
    - restart: unless-stopped
    - ENVIRONMENT=production設定
    - _Requirements: 3.4_
  - [x] 6.4 Property 1のプロパティベーステスト: 全サービス定義の完全性
    - **Property 1: 全サービス定義の完全性**
    - テストファイル: `genai/tests/test_docker_cicd_properties.py`
    - docker-compose.ymlに全6サービス（postgres, redis, api, celery-worker, celery-beat, frontend）が定義されていることを検証
    - **Validates: Requirements 1.1**
  - [x] 6.5 Property 2のプロパティベーステスト: 全サービスのヘルスチェック設定
    - **Property 2: 全サービスのヘルスチェック設定**
    - テストファイル: `genai/tests/test_docker_cicd_properties.py`
    - docker-compose.yml内の全サービスにhealthcheck設定が存在することを検証
    - **Validates: Requirements 1.2, 8.2**

- [ ] 7. 環境別設定テンプレート
  - [ ] 7.1 `genai/.env.development`を新規作成
    - 開発用デフォルト値（DEBUG=true, LOG_LEVEL=DEBUG, POSTGRES_PORT=15432等）
    - シークレット変数に開発用デフォルト値を設定
    - _Requirements: 3.1_
  - [ ] 7.2 `genai/.env.staging`を新規作成
    - ステージング用設定（DEBUG=false, LOG_LEVEL=INFO）
    - シークレット変数はCHANGE_ME_IN_SECRETSプレースホルダー
    - _Requirements: 3.1, 3.2_
  - [ ] 7.3 `genai/.env.production`を新規作成
    - 本番用設定（DEBUG=false, LOG_LEVEL=WARNING, ENABLE_DOCS=false）
    - シークレット変数はCHANGE_ME_IN_SECRETSプレースホルダー
    - _Requirements: 3.1, 3.2, 3.3_
  - [ ] 7.4 `genai/.dockerignore`を更新
    - `.env*`, `.git`, `tests/`, `venv/`, `__pycache__/`等を除外
    - _Requirements: 9.3_
  - [ ] 7.5 Property 4のプロパティベーステスト: シークレット情報の非ハードコード
    - **Property 4: シークレット情報の非ハードコード**
    - テストファイル: `genai/tests/test_docker_cicd_properties.py`
    - .env.staging, .env.productionのシークレット変数がプレースホルダーであること、.dockerignoreが.envファイルを除外することを検証
    - **Validates: Requirements 3.2, 9.2**

- [ ] 8. チェックポイント - Docker Compose構成と環境設定の検証
  - 全テストが通ることを確認し、ユーザーに質問があれば確認する。

- [ ] 9. ヘルスチェックエンドポイント拡張
  - [ ] 9.1 `genai/src/main.py`の`/health`エンドポイントを拡張
    - PostgreSQL接続チェック（SessionLocalを使用）
    - Redis接続チェック（redis.from_urlを使用）
    - レスポンスにversion（IMAGE_TAG環境変数）、timestamp、servicesフィールドを追加
    - 異常時はHTTP 503を返す
    - _Requirements: 8.1, 8.4_
  - [ ] 9.2 Property 9のプロパティベーステスト: ヘルスチェックレスポンスの完全性
    - **Property 9: ヘルスチェックレスポンスの完全性**
    - テストファイル: `genai/tests/test_docker_cicd_properties.py`
    - DB/Redisの全状態組み合わせに対し、レスポンスに(a)全体ステータス、(b)DB接続状態、(c)Redis接続状態、(d)バージョン情報が含まれ、異常時はunhealthy+503を返すことを検証
    - Hypothesisで接続状態の組み合わせを生成
    - **Validates: Requirements 8.1, 8.4**

- [ ] 10. GitHub Actions PRワークフロー
  - [ ] 10.1 `.github/workflows/pr.yml`を新規作成
    - PR作成時にトリガー（on: pull_request, branches: [main]）
    - test-backendジョブ: PostgreSQL/Redisサービスコンテナ、pip cache、pytest --cov実行
    - test-frontendジョブ: node_modules cache、npm ci、lint、test --coverage実行
    - テストカバレッジレポートをアーティファクトとして保存
    - _Requirements: 4.2, 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 11. GitHub Actions デプロイワークフロー
  - [ ] 11.1 `.github/workflows/deploy.yml`を新規作成
    - main push/タグ（v*）でトリガー
    - test-backend, test-frontendジョブ（PRワークフローと同様）
    - build-and-pushジョブ: docker/metadata-actionでタグ生成、buildx + GHAキャッシュ
    - バックエンド・フロントエンド両方のイメージをビルド・プッシュ
    - タグ戦略: commit-sha, latest, stable（mainのみ）, semver（v*タグ時）
    - security-scanジョブ: Trivyでバックエンド・フロントエンドイメージをスキャン（CRITICAL/HIGH検出時に失敗）
    - ジョブ間のneeds依存でパイプライン失敗時に後続ステージをスキップ
    - _Requirements: 4.1, 4.3, 4.4, 4.5, 4.6, 7.1, 7.2, 7.3, 7.4, 9.4_
  - [ ] 11.2 Property 8のプロパティベーステスト: イメージタグの一貫性
    - **Property 8: イメージタグの一貫性**
    - テストファイル: `genai/tests/test_docker_cicd_properties.py`
    - ランダムなコミットハッシュに対し、deploy.ymlのmetadata-action設定がsha/latestタグを生成することを検証
    - **Validates: Requirements 4.4, 7.2**
  - [ ] 11.3 `deploy.yml`にECS Fargateデプロイジョブを追加
    - deploy-stagingジョブ: security-scan後、mainブランチ時に自動実行
    - deploy-productionジョブ: deploy-staging後、v*タグ時に手動承認ゲート付きで実行
    - AWS OIDC認証（aws-actions/configure-aws-credentials@v4 + role-to-assume）
    - 4サービス（api, celery-worker, celery-beat, frontend）のタスク定義取得→イメージ更新→デプロイ
    - wait-for-service-stabilityで安定性確認
    - GitHub Repository Secrets/Variablesの設定ドキュメント
    - _Requirements: 4.1, 4.5, 7.4_

- [ ] 12. エラーコード体系と構造化ログ
  - [ ] 12.1 `genai/src/error_codes.py`を新規作成
    - PCM-E1xx〜E7xxのエラーコード定数定義
    - StructuredLoggerクラス（JSON構造化ログ出力）
    - エラーコードごとの重大度・ロールバック要否のメタデータ
    - _Requirements: 10.1, 10.2_
  - [ ] 12.2 `genai/docker/entrypoint.sh`にlog_error関数と構造化ログ出力を追加
    - JSON形式のエラーログ出力関数
    - 既存のechoをlog_error呼び出しに置換（PCM-E101, E201, E202）
    - _Requirements: 10.3_
  - [ ] 12.3 `genai/src/main.py`のヘルスチェックにエラーコードを追加
    - DB接続失敗時にPCM-E201、Redis接続失敗時にPCM-E301をレスポンスに含める
    - _Requirements: 10.4_

- [ ] 13. ロールバック・切り戻し機構
  - [ ] 13.1 `genai/docker/entrypoint.sh`にマイグレーションロールバック機能を追加
    - マイグレーション実行前に現在のリビジョンを記録
    - 失敗時にalembic downgradeで前リビジョンに自動ダウングレード
    - _Requirements: 11.3_
  - [ ] 13.2 `.github/workflows/rollback.yml`を新規作成
    - workflow_dispatchトリガー（手動実行）
    - 入力: 対象サービス（api/celery-worker/celery-beat/frontend/all）、イメージタグ、環境
    - ECSタスク定義のイメージ差し替え→デプロイ→安定性待機
    - _Requirements: 11.2, 11.5_
  - [ ] 13.3 deploy.ymlのECSデプロイ設定にCircuit Breaker・ローリングアップデート設定を追記
    - deploymentCircuitBreaker.rollback: true
    - minimumHealthyPercent: 100, maximumPercent: 200
    - _Requirements: 11.1, 11.4_

- [ ] 14. 最終チェックポイント - 全体統合検証
  - 全テストが通ることを確認し、ユーザーに質問があれば確認する。

## Notes

- `*`マーク付きタスクはオプションで、MVP実装時にスキップ可能
- 各タスクは具体的な要件番号を参照し、トレーサビリティを確保
- チェックポイントで段階的な検証を実施
- プロパティベーステストは設計書の9つの正当性プロパティすべてをカバー
- テストファイルは`genai/tests/test_docker_cicd_properties.py`に集約
- Python PBTにはHypothesis、TypeScript PBTにはfast-checkを使用

# 技術設計書: Docker CI/CD パイプライン

## 概要

Payment Compliance Monitorの全サービス（PostgreSQL、Redis、FastAPI API、Celery Worker、Celery Beat、React Frontend）をDockerベースで統一管理し、GitHub Actions CI/CDパイプラインを通じて自動テスト・ビルド・デプロイを実現する。

現状の課題:
- バックエンドDockerfile（`genai/docker/Dockerfile`）はシングルステージで、ビルドツール（gcc等）が最終イメージに残る
- フロントエンドDockerfile（`genai/frontend/Dockerfile`）は開発用Viteサーバーのみで本番ビルドに対応していない
- 環境別設定管理（dev/staging/prod）が未実装
- CI/CDパイプラインが存在しない
- ヘルスチェックエンドポイント（`/health`）がDB/Redis接続状態を返さない
- マイグレーション自動実行の仕組みがない

本設計では、既存の`docker-compose.yml`を開発用ベースとして維持しつつ、環境別オーバーライドファイル、マルチステージDockerfile、GitHub Actionsワークフロー、マイグレーション自動化スクリプトを追加する。

### 既存コードのDocker互換性に関する課題

既存のAPI実装にはローカル環境前提のコードが含まれており、Docker化に際して以下の修正が必要:

| 課題 | ファイル | 内容 | 対応 |
|------|---------|------|------|
| SQLiteフォールバック | `src/tasks.py` | `cleanup_old_data`, `crawl_all_sites`, `scan_all_fake_sites`の3タスクで`DATABASE_URL`未設定時に`sqlite:///./payment_monitor.db`にフォールバック | `database.py`の`SessionLocal`を使用するようリファクタリング。または`src/database.py`と同じPostgreSQLデフォルトURLに統一 |
| localhostデフォルト | `src/database.py`, `src/celery_app.py`, `src/crawler.py` | 環境変数未設定時に`localhost`に接続しようとする | エントリポイントの必須環境変数チェック（`DATABASE_URL`, `REDIS_URL`）で防止。Docker Compose内ではサービス名（`postgres`, `redis`）で接続 |
| スクリーンショット保存先 | `src/screenshot_manager.py` | ローカルファイルシステム（`screenshots/`）に保存。コンテナ再起動でデータ消失 | Docker Composeで名前付きボリューム（`screenshots_data`）をマウント |
| フロントエンドAPI URL | `frontend/src/services/api.ts` | デフォルト`http://localhost:8080`。Docker環境ではポートが異なる可能性 | `docker-compose.override.yml`で`VITE_API_BASE_URL`環境変数を設定 |
| CORS設定 | `src/main.py` | `allow_origins=["*"]`（全許可）。本番環境ではフロントエンドのオリジンのみ許可すべき | 環境変数`CORS_ORIGINS`から読み込むよう修正（既に`.env`に定義済み） |

### 主要な設計判断

| 判断事項 | 選択 | 理由 |
|---------|------|------|
| CI/CDプラットフォーム | GitHub Actions | GitHubリポジトリとの統合が容易、無料枠が十分 |
| コンテナレジストリ | GitHub Container Registry (ghcr.io) | GitHub Actionsとのシームレスな認証連携 |
| フロントエンド本番配信 | Nginx (alpine) | 軽量・高速な静的ファイル配信 |
| セキュリティスキャン | Trivy | OSSで高精度、GitHub Actions統合が容易 |
| PBTライブラリ | Hypothesis (Python) / fast-check (TypeScript) | 既にプロジェクトに導入済み |

## アーキテクチャ

### システム全体構成

```mermaid
graph TB
    subgraph "開発者ワークフロー"
        DEV[開発者] -->|git push| GH[GitHub Repository]
        DEV -->|docker compose up| LOCAL[ローカル開発環境]
    end

    subgraph "CI/CD パイプライン (GitHub Actions)"
        GH -->|PR作成| PR_WF[PR Workflow]
        GH -->|main push| DEPLOY_WF[Deploy Workflow]
        
        PR_WF --> LINT[Lint & Type Check]
        PR_WF --> TEST_BE[Backend Tests]
        PR_WF --> TEST_FE[Frontend Tests]
        
        DEPLOY_WF --> BUILD[Docker Build]
        BUILD --> SCAN[Security Scan - Trivy]
        SCAN --> PUSH[Push to GHCR]
        PUSH --> DEPLOY[Deploy]
    end

    subgraph "コンテナレジストリ"
        PUSH --> GHCR[GitHub Container Registry]
    end

    subgraph "デプロイ先環境"
        DEPLOY --> STG[Staging]
        DEPLOY --> PROD[Production]
    end
```

### Docker Compose 環境構成

```mermaid
graph LR
    subgraph "ベース (docker-compose.yml)"
        PG[PostgreSQL]
        RD[Redis]
        API[FastAPI API]
        CW[Celery Worker]
        CB[Celery Beat]
        FE[Frontend]
    end

    subgraph "開発オーバーライド"
        OV_DEV[docker-compose.override.yml]
        OV_DEV -.->|ホットリロード<br>ポート公開<br>ボリュームマウント| API
        OV_DEV -.->|Vite dev server| FE
    end

    subgraph "本番オーバーライド"
        OV_PROD[docker-compose.prod.yml]
        OV_PROD -.->|本番イメージ<br>リソース制限<br>再起動ポリシー| API
        OV_PROD -.->|Nginx配信| FE
    end
```


## コンポーネントとインターフェース

### 1. マルチステージDockerfile（バックエンド）

ファイル: `genai/docker/Dockerfile`（既存ファイルを置換）

```dockerfile
# ---- Builder Stage ----
FROM python:3.11-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y gcc postgresql-client && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Production Stage ----
FROM python:3.11-slim AS production
WORKDIR /app

# Playwright + Chromiumに必要なシステム依存関係（クローラー機能で必須）
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libatspi2.0-0 libxshmfence1 fonts-liberation \
    xdg-utils wget \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

# Playwright Chromiumブラウザのインストール
RUN playwright install chromium

COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

ポイント:
- `builder`ステージでgcc等のビルドツールを使い依存関係をインストール
- `production`ステージにはビルドツール（gcc）を含めない（要件2.1, 2.4）
- Playwright + Chromiumのシステム依存関係を明示的にインストール（クローラー機能に必須）
- 非rootユーザー`appuser`で実行（要件2.3）
- `requirements.txt`を先にCOPYしてレイヤーキャッシュを活用（要件2.5）
- `entrypoint.sh`に実行権限を付与

### 2. マルチステージDockerfile（フロントエンド）

ファイル: `genai/frontend/Dockerfile.prod`（新規作成）

```dockerfile
# ---- Build Stage ----
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- Production Stage ----
FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
RUN adduser -D -u 1000 appuser
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

ポイント:
- ビルド済み静的ファイルをNginxで配信（要件2.2）
- node_modules等のビルド依存関係を最終イメージに含めない（要件2.4）

### 3. Docker Compose 環境別構成

#### ベースファイル: `docker-compose.yml`（既存を修正）

全環境共通のサービス定義。ヘルスチェック設定を全サービスに追加（要件8.2）。
スクリーンショット保存用の名前付きボリューム（`screenshots_data`）を追加し、APIコンテナとCelery Workerにマウント。

ベースファイルの変更点:
- 全サービスにhealthcheck設定を追加
- ポート公開をベースから削除（オーバーライドファイルで環境ごとに設定）
- `screenshots_data`ボリュームを追加（`/app/screenshots`にマウント）
- `volumes`セクションに`screenshots_data`を追加

#### 開発用オーバーライド: `docker-compose.override.yml`（新規）

```yaml
# docker compose up で自動的に読み込まれる
services:
  postgres:
    ports:
      - "${POSTGRES_PORT:-15432}:5432"  # ローカルhomebrew PostgreSQLとの競合回避
  redis:
    ports:
      - "${REDIS_PORT:-16379}:6379"    # ローカルhomebrew Redisとの競合回避
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile
    command: uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      - RUN_MIGRATIONS=true  # 開発時はAPI起動時にマイグレーション自動実行
    volumes:
      - ./src:/app/src
      - ./tests:/app/tests
      - ./alembic:/app/alembic
    ports:
      - "${API_PORT:-8000}:8000"
  celery-worker:
    build:
      context: .
      dockerfile: docker/Dockerfile
    environment:
      - RUN_MIGRATIONS=false  # Worker/Beatではマイグレーション実行しない
    volumes:
      - ./src:/app/src
  celery-beat:
    build:
      context: .
      dockerfile: docker/Dockerfile
    environment:
      - RUN_MIGRATIONS=false
    volumes:
      - ./src:/app/src
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile  # 開発用Dockerfile（Vite dev server）
    environment:
      - VITE_API_BASE_URL=http://localhost:8000  # 開発時はホストのAPIポートを指定
    volumes:
      - ./frontend/src:/app/src
      - ./frontend/public:/app/public
    ports:
      - "5173:5173"
```

ホットリロード対応（要件1.3）、設定可能なポートマッピング（要件1.4）。
Celery Worker/Beatでは`RUN_MIGRATIONS=false`を設定し、マイグレーションはAPIコンテナのみで実行する。

#### 本番用オーバーライド: `docker-compose.prod.yml`（新規）

```yaml
# docker compose -f docker-compose.yml -f docker-compose.prod.yml up
services:
  postgres:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G
  redis:
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M
  api:
    image: ghcr.io/${GITHUB_REPOSITORY}/api:${IMAGE_TAG:-latest}
    environment:
      - RUN_MIGRATIONS=true
      - ENVIRONMENT=production
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
  celery-worker:
    image: ghcr.io/${GITHUB_REPOSITORY}/api:${IMAGE_TAG:-latest}
    environment:
      - RUN_MIGRATIONS=false
      - ENVIRONMENT=production
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
  celery-beat:
    image: ghcr.io/${GITHUB_REPOSITORY}/api:${IMAGE_TAG:-latest}
    environment:
      - RUN_MIGRATIONS=false
      - ENVIRONMENT=production
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M
  frontend:
    image: ghcr.io/${GITHUB_REPOSITORY}/frontend:${IMAGE_TAG:-latest}
    ports:
      - "80:80"
    restart: unless-stopped
```

ポイント:
- 全環境でDockerコンテナ内のPostgreSQL/Redisを使用（開発・ステージング・本番で統一）
- 将来的にRDS/ElastiCacheへ移行する場合は、`DATABASE_URL`/`REDIS_URL`環境変数の差し替えとdocker-compose.prod.ymlの修正のみで対応可能（アプリコード変更不要）
- 本番用イメージはGHCRから取得
- リソース制限とrestart policyを設定

### 4. エントリポイントスクリプト

ファイル: `genai/docker/entrypoint.sh`（新規）

```bash
#!/bin/bash
set -e

# 必須環境変数チェック（要件3.5）
REQUIRED_VARS="DATABASE_URL REDIS_URL SECRET_KEY"
for var in $REQUIRED_VARS; do
  if [ -z "${!var}" ]; then
    echo "ERROR: Required environment variable $var is not set"
    exit 1
  fi
done

# 本番環境でDEBUGモード無効化を強制（要件3.3, 9.5）
if [ "$ENVIRONMENT" = "production" ]; then
  export DEBUG=false
  export ENABLE_DOCS=false
fi

# DATABASE_URLからホスト・ポート・ユーザーをパース
# 形式: postgresql+psycopg2://user:pass@host:port/dbname
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:]*\):.*|\1|p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_USER=$(echo "$DATABASE_URL" | sed -n 's|.*://\([^:]*\):.*|\1|p')

# マイグレーション実行（要件6.1）
# RUN_MIGRATIONS=true の場合のみ実行（APIコンテナのみ、Worker/Beatでは実行しない）
if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "Waiting for database connection..."
  # DB接続確認（要件6.3）
  MAX_RETRIES=30
  RETRY_COUNT=0
  until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" 2>/dev/null; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
      echo "ERROR: Database connection timeout after $MAX_RETRIES retries"
      exit 1
    fi
    echo "Database not ready, retrying in 2s... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
  done
  echo "Running Alembic migrations..."
  alembic upgrade head
  MIGRATION_STATUS=$?
  if [ $MIGRATION_STATUS -ne 0 ]; then
    echo "ERROR: Migration failed with status $MIGRATION_STATUS"
    exit 1  # デプロイ中止（要件6.2）
  fi
  echo "Migrations completed successfully"
fi

exec "$@"
```

ポイント:
- `DATABASE_URL`からDB接続情報をパースするため、`DB_HOST`/`DB_PORT`/`DB_USER`の別途設定が不要
- `RUN_MIGRATIONS`フラグにより、APIコンテナのみでマイグレーション実行（Celery Worker/Beatでは`false`を設定）
- DB接続待機にタイムアウト（最大30回リトライ）を設定し、無限ループを防止
- 本番環境では`ENABLE_DOCS=false`も強制（APIドキュメント非公開）

### 5. ヘルスチェックエンドポイント

ファイル: `genai/src/main.py`（既存の`/health`エンドポイントを拡張）

```python
@app.get("/health")
async def health_check():
    """拡張ヘルスチェック（要件8.1, 8.4）"""
    import os
    from datetime import datetime, timezone
    from sqlalchemy import text
    from fastapi.responses import JSONResponse
    
    health = {
        "status": "healthy",
        "version": os.getenv("IMAGE_TAG", "dev"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": "unknown",
            "redis": "unknown"
        }
    }
    
    # PostgreSQL接続チェック（同期セッションを使用 — 既存のdatabase.pyに合わせる）
    try:
        from src.database import SessionLocal
        session = SessionLocal()
        try:
            session.execute(text("SELECT 1"))
            health["services"]["database"] = "healthy"
        finally:
            session.close()
    except Exception as e:
        health["status"] = "unhealthy"
        health["services"]["database"] = f"unhealthy: {str(e)}"
    
    # Redis接続チェック
    try:
        import redis as redis_lib
        redis_client = redis_lib.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        redis_client.ping()
        health["services"]["redis"] = "healthy"
        redis_client.close()
    except Exception as e:
        health["status"] = "unhealthy"
        health["services"]["redis"] = f"unhealthy: {str(e)}"
    
    status_code = 200 if health["status"] == "healthy" else 503
    return JSONResponse(content=health, status_code=status_code)
```

ポイント:
- 既存の`database.py`が同期的な`SessionLocal`を使用しているため、ヘルスチェックも同期セッションで実装
- `timestamp`フィールドを追加（データモデルのレスポンス定義と一致）
- Redisクライアントは同期版の`redis.from_url()`を使用（`redis`パッケージの同期API）
- Redisクライアントの接続を明示的にクローズ

### 6. GitHub Actions ワークフロー

#### PR ワークフロー: `.github/workflows/pr.yml`

```yaml
name: PR Check
on:
  pull_request:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env: { POSTGRES_USER: test, POSTGRES_PASSWORD: test, POSTGRES_DB: test }
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 10s
      redis:
        image: redis:7.2-alpine
        ports: ["6379:6379"]
        options: --health-cmd "redis-cli ping" --health-interval 10s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ hashFiles('requirements.txt') }}
      - run: pip install -r requirements.txt
      - run: pytest --cov=src --cov-report=xml tests/
        env:
          DATABASE_URL: postgresql+psycopg2://test:test@localhost:5432/test
          REDIS_URL: redis://localhost:6379/0
          SECRET_KEY: test-secret-key-for-ci
      - uses: actions/upload-artifact@v4
        with: { name: coverage-backend, path: coverage.xml }

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - uses: actions/cache@v4
        with:
          path: frontend/node_modules
          key: node-${{ hashFiles('frontend/package-lock.json') }}
      - run: npm ci
        working-directory: frontend
      - run: npm run lint
        working-directory: frontend
      - run: npm run test -- --coverage
        working-directory: frontend
      - uses: actions/upload-artifact@v4
        with: { name: coverage-frontend, path: frontend/coverage/ }
```

#### デプロイワークフロー: `.github/workflows/deploy.yml`

```yaml
name: Build & Deploy
on:
  push:
    branches: [main]
    tags: ['v*']  # セマンティックバージョンタグにも対応

env:
  REGISTRY: ghcr.io

jobs:
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env: { POSTGRES_USER: test, POSTGRES_PASSWORD: test, POSTGRES_DB: test }
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 10s
      redis:
        image: redis:7.2-alpine
        ports: ["6379:6379"]
        options: --health-cmd "redis-cli ping" --health-interval 10s
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: pip-${{ hashFiles('requirements.txt') }}
      - run: pip install -r requirements.txt
        working-directory: .
      - run: pytest --cov=src --cov-report=xml tests/
        working-directory: .
        env:
          DATABASE_URL: postgresql+psycopg2://test:test@localhost:5432/test
          REDIS_URL: redis://localhost:6379/0

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - uses: actions/cache@v4
        with:
          path: frontend/node_modules
          key: node-${{ hashFiles('frontend/package-lock.json') }}
      - run: npm ci
        working-directory: frontend
      - run: npm run lint
        working-directory: frontend
      - run: npm run test -- --coverage
        working-directory: frontend

  build-and-push:
    needs: [test-backend, test-frontend]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      # バックエンドイメージのビルド・プッシュ
      - uses: docker/metadata-action@v5
        id: meta-api
        with:
          images: ${{ env.REGISTRY }}/${{ github.repository }}/api
          tags: |
            type=sha
            type=raw,value=latest
            type=raw,value=stable,enable=${{ github.ref == 'refs/heads/main' }}
            type=semver,pattern={{version}},enable=${{ startsWith(github.ref, 'refs/tags/v') }}
      - uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/Dockerfile
          push: true
          tags: ${{ steps.meta-api.outputs.tags }}
          labels: ${{ steps.meta-api.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      # フロントエンドイメージのビルド・プッシュ
      - uses: docker/metadata-action@v5
        id: meta-frontend
        with:
          images: ${{ env.REGISTRY }}/${{ github.repository }}/frontend
          tags: |
            type=sha
            type=raw,value=latest
            type=raw,value=stable,enable=${{ github.ref == 'refs/heads/main' }}
            type=semver,pattern={{version}},enable=${{ startsWith(github.ref, 'refs/tags/v') }}
      - uses: docker/build-push-action@v5
        with:
          context: ./frontend
          file: frontend/Dockerfile.prod
          push: true
          tags: ${{ steps.meta-frontend.outputs.tags }}
          labels: ${{ steps.meta-frontend.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
  security-scan:
    needs: build-and-push
    runs-on: ubuntu-latest
    steps:
      - uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ github.repository }}/api:sha-${{ github.sha }}
          severity: CRITICAL,HIGH
          exit-code: '1'  # CRITICAL/HIGH検出時にジョブ失敗
      - uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ github.repository }}/frontend:sha-${{ github.sha }}
          severity: CRITICAL,HIGH
          exit-code: '1'

  deploy-staging:
    needs: security-scan
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN_STAGING }}
          aws-region: ${{ vars.AWS_REGION }}
      - name: Download task definition
        run: |
          aws ecs describe-task-definition \
            --task-definition ${{ vars.ECS_TASK_FAMILY_API }} \
            --query taskDefinition > task-def-api.json
      - uses: aws-actions/amazon-ecs-render-task-definition@v1
        id: render-api
        with:
          task-definition: task-def-api.json
          container-name: api
          image: ${{ env.REGISTRY }}/${{ github.repository }}/api:sha-${{ github.sha }}
      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.render-api.outputs.task-definition }}
          service: ${{ vars.ECS_SERVICE_API }}
          cluster: ${{ vars.ECS_CLUSTER }}
          wait-for-service-stability: true
      # Celery Worker デプロイ
      - name: Download worker task definition
        run: |
          aws ecs describe-task-definition \
            --task-definition ${{ vars.ECS_TASK_FAMILY_WORKER }} \
            --query taskDefinition > task-def-worker.json
      - uses: aws-actions/amazon-ecs-render-task-definition@v1
        id: render-worker
        with:
          task-definition: task-def-worker.json
          container-name: celery-worker
          image: ${{ env.REGISTRY }}/${{ github.repository }}/api:sha-${{ github.sha }}
      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.render-worker.outputs.task-definition }}
          service: ${{ vars.ECS_SERVICE_WORKER }}
          cluster: ${{ vars.ECS_CLUSTER }}
          wait-for-service-stability: true
      # Celery Beat デプロイ
      - name: Download beat task definition
        run: |
          aws ecs describe-task-definition \
            --task-definition ${{ vars.ECS_TASK_FAMILY_BEAT }} \
            --query taskDefinition > task-def-beat.json
      - uses: aws-actions/amazon-ecs-render-task-definition@v1
        id: render-beat
        with:
          task-definition: task-def-beat.json
          container-name: celery-beat
          image: ${{ env.REGISTRY }}/${{ github.repository }}/api:sha-${{ github.sha }}
      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.render-beat.outputs.task-definition }}
          service: ${{ vars.ECS_SERVICE_BEAT }}
          cluster: ${{ vars.ECS_CLUSTER }}
          wait-for-service-stability: true
      # Frontend デプロイ
      - name: Download frontend task definition
        run: |
          aws ecs describe-task-definition \
            --task-definition ${{ vars.ECS_TASK_FAMILY_FRONTEND }} \
            --query taskDefinition > task-def-frontend.json
      - uses: aws-actions/amazon-ecs-render-task-definition@v1
        id: render-frontend
        with:
          task-definition: task-def-frontend.json
          container-name: frontend
          image: ${{ env.REGISTRY }}/${{ github.repository }}/frontend:sha-${{ github.sha }}
      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.render-frontend.outputs.task-definition }}
          service: ${{ vars.ECS_SERVICE_FRONTEND }}
          cluster: ${{ vars.ECS_CLUSTER }}
          wait-for-service-stability: true

  deploy-production:
    needs: deploy-staging
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    environment: production  # 手動承認ゲート
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN_PRODUCTION }}
          aws-region: ${{ vars.AWS_REGION }}
      - name: Download task definition
        run: |
          aws ecs describe-task-definition \
            --task-definition ${{ vars.ECS_TASK_FAMILY_API }} \
            --query taskDefinition > task-def-api.json
      - uses: aws-actions/amazon-ecs-render-task-definition@v1
        id: render-api
        with:
          task-definition: task-def-api.json
          container-name: api
          image: ${{ env.REGISTRY }}/${{ github.repository }}/api:sha-${{ github.sha }}
      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.render-api.outputs.task-definition }}
          service: ${{ vars.ECS_SERVICE_API }}
          cluster: ${{ vars.ECS_CLUSTER }}
          wait-for-service-stability: true
      - name: Download worker task definition
        run: |
          aws ecs describe-task-definition \
            --task-definition ${{ vars.ECS_TASK_FAMILY_WORKER }} \
            --query taskDefinition > task-def-worker.json
      - uses: aws-actions/amazon-ecs-render-task-definition@v1
        id: render-worker
        with:
          task-definition: task-def-worker.json
          container-name: celery-worker
          image: ${{ env.REGISTRY }}/${{ github.repository }}/api:sha-${{ github.sha }}
      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.render-worker.outputs.task-definition }}
          service: ${{ vars.ECS_SERVICE_WORKER }}
          cluster: ${{ vars.ECS_CLUSTER }}
          wait-for-service-stability: true
      - name: Download beat task definition
        run: |
          aws ecs describe-task-definition \
            --task-definition ${{ vars.ECS_TASK_FAMILY_BEAT }} \
            --query taskDefinition > task-def-beat.json
      - uses: aws-actions/amazon-ecs-render-task-definition@v1
        id: render-beat
        with:
          task-definition: task-def-beat.json
          container-name: celery-beat
          image: ${{ env.REGISTRY }}/${{ github.repository }}/api:sha-${{ github.sha }}
      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.render-beat.outputs.task-definition }}
          service: ${{ vars.ECS_SERVICE_BEAT }}
          cluster: ${{ vars.ECS_CLUSTER }}
          wait-for-service-stability: true
      - name: Download frontend task definition
        run: |
          aws ecs describe-task-definition \
            --task-definition ${{ vars.ECS_TASK_FAMILY_FRONTEND }} \
            --query taskDefinition > task-def-frontend.json
      - uses: aws-actions/amazon-ecs-render-task-definition@v1
        id: render-frontend
        with:
          task-definition: task-def-frontend.json
          container-name: frontend
          image: ${{ env.REGISTRY }}/${{ github.repository }}/frontend:sha-${{ github.sha }}
      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.render-frontend.outputs.task-definition }}
          service: ${{ vars.ECS_SERVICE_FRONTEND }}
          cluster: ${{ vars.ECS_CLUSTER }}
          wait-for-service-stability: true
```

ポイント:
- `docker/metadata-action`を使用してタグ生成を自動化（コミットSHA、latest、stable、セマンティックバージョン）
- gitタグ（`v*`）作成時にもワークフローがトリガーされ、セマンティックバージョンタグが付与される
- フロントエンドイメージのビルド・プッシュも明示的に記載
- セキュリティスキャンでCRITICAL/HIGH検出時は`exit-code: '1'`でジョブ失敗
- `permissions`でGHCRへのプッシュに必要な`packages: write`を明示

#### AWS ECS Fargate デプロイ構成

デプロイ先としてAWS ECS Fargateを採用。各サービスを個別のECSサービスとして管理する。

##### ECSサービス構成

| ECSサービス | コンテナイメージ | タスク数 | 備考 |
|------------|----------------|---------|------|
| api | ghcr.io/.../api | 1-N (Auto Scaling) | ALB経由でHTTPリクエスト受付。RUN_MIGRATIONS=true |
| celery-worker | ghcr.io/.../api | 1-N | バックグラウンドタスク実行。RUN_MIGRATIONS=false |
| celery-beat | ghcr.io/.../api | 1 | スケジューラー（1インスタンスのみ）。RUN_MIGRATIONS=false |
| frontend | ghcr.io/.../frontend | 1-N | Nginx静的ファイル配信。ALB経由 |

注意: 現時点では全環境でDockerコンテナ内のPostgreSQL/Redisを使用。将来的にRDS/ElastiCacheへ移行する場合は、`DATABASE_URL`/`REDIS_URL`環境変数の差し替えとECSタスク定義の更新のみで対応可能。

##### 将来のRDS/ElastiCache移行時の対応

アプリケーションは`DATABASE_URL`/`REDIS_URL`環境変数で接続先を決定するため、マネージドサービスへの移行時にコード変更は不要。以下の対応のみ必要:
- ECSタスク定義の環境変数をRDS/ElastiCacheエンドポイントに変更
- RDS SSL接続が必要な場合は`DATABASE_URL`に`?sslmode=require`を付与
- ElastiCache AUTH有効時は`REDIS_URL`にパスワードを含める（`redis://:password@endpoint:6379/0`）

##### AWS認証方式

GitHub Actions OIDC（OpenID Connect）を使用し、長期的なアクセスキーを不要にする:
- GitHub ActionsのOIDCプロバイダーをAWS IAMに登録
- 環境ごと（staging/production）にIAMロールを作成
- `aws-actions/configure-aws-credentials@v4`の`role-to-assume`で認証

##### 必要なGitHub設定

**Repository Secrets:**

| シークレット名 | 説明 |
|--------------|------|
| `AWS_ROLE_ARN_STAGING` | ステージング環境用IAMロールARN |
| `AWS_ROLE_ARN_PRODUCTION` | 本番環境用IAMロールARN |

**Repository Variables (vars):**

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `AWS_REGION` | AWSリージョン | `ap-northeast-1` |
| `ECS_CLUSTER` | ECSクラスター名 | `payment-monitor` |
| `ECS_SERVICE_API` | APIサービス名 | `api` |
| `ECS_SERVICE_WORKER` | Workerサービス名 | `celery-worker` |
| `ECS_SERVICE_BEAT` | Beatサービス名 | `celery-beat` |
| `ECS_SERVICE_FRONTEND` | Frontendサービス名 | `frontend` |
| `ECS_TASK_FAMILY_API` | APIタスク定義ファミリー | `payment-monitor-api` |
| `ECS_TASK_FAMILY_WORKER` | Workerタスク定義ファミリー | `payment-monitor-worker` |
| `ECS_TASK_FAMILY_BEAT` | Beatタスク定義ファミリー | `payment-monitor-beat` |
| `ECS_TASK_FAMILY_FRONTEND` | Frontendタスク定義ファミリー | `payment-monitor-frontend` |

##### デプロイフロー

```mermaid
graph LR
    SEC[Security Scan] --> STG[Deploy Staging]
    STG -->|v* タグ時のみ| APPROVE[手動承認]
    APPROVE --> PROD[Deploy Production]
    
    STG --> |各サービス| API_S[API]
    STG --> WORKER_S[Worker]
    STG --> BEAT_S[Beat]
    STG --> FE_S[Frontend]
```

- main pushでステージングに自動デプロイ
- `v*`タグ作成時に本番デプロイ（`environment: production`による手動承認ゲート付き）
- 各サービスのタスク定義を取得→イメージ更新→デプロイ→安定性待機の順で実行
- `wait-for-service-stability: true`により、新タスクが正常起動するまで待機

### 7. 環境別設定テンプレート

ファイル構成:
- `genai/.env.example` — 既存（全変数のテンプレート）
- `genai/.env.development` — 開発用デフォルト値（新規）
- `genai/.env.staging` — ステージング用テンプレート（新規）
- `genai/.env.production` — 本番用テンプレート（新規）

#### シークレット変数の分類と注入方式（要件3.2）

シークレット変数（ソースコードやイメージに含めてはならない値）を明確に分類し、環境ごとの注入方式を定義する。

| シークレット変数 | 説明 | 開発環境 | ステージング/本番 |
|----------------|------|---------|-----------------|
| `POSTGRES_PASSWORD` | DB接続パスワード | `.env.development`にデフォルト値 | GitHub Secrets → 環境変数注入 |
| `SECRET_KEY` | アプリケーション秘密鍵 | `.env.development`にデフォルト値 | GitHub Secrets → 環境変数注入 |
| `ENCRYPTION_KEY` | データ暗号化キー | `.env.development`にデフォルト値 | GitHub Secrets → 環境変数注入 |
| `JWT_SECRET_KEY` | JWT署名キー | `.env.development`にデフォルト値 | GitHub Secrets → 環境変数注入 |
| `SENDGRID_API_KEY` | メール送信APIキー | プレースホルダー | GitHub Secrets → 環境変数注入 |
| `SLACK_BOT_TOKEN` | Slack通知トークン | プレースホルダー | GitHub Secrets → 環境変数注入 |
| `SLACK_WEBHOOK_URL` | Slack Webhook URL | プレースホルダー | GitHub Secrets → 環境変数注入 |

#### 注入方式の詳細

1. **ローカル開発環境**: `.env.development`ファイルに開発用のデフォルト値を記載。`docker-compose.override.yml`の`env_file`で読み込む。
2. **CI/CDパイプライン（テスト）**: GitHub Actionsの`env`セクションでテスト用の値を直接設定。
3. **ステージング/本番デプロイ**: GitHub Actionsの`secrets`コンテキストから環境変数として注入。デプロイ先のクラウドサービス（ECS Task Definition、Cloud Run環境変数等）に設定。

```yaml
# deploy.ymlでのシークレット注入例
deploy-staging:
  environment: staging
  steps:
    - name: Deploy
      env:
        DATABASE_URL: ${{ secrets.STAGING_DATABASE_URL }}
        SECRET_KEY: ${{ secrets.STAGING_SECRET_KEY }}
        ENCRYPTION_KEY: ${{ secrets.STAGING_ENCRYPTION_KEY }}
        REDIS_URL: ${{ secrets.STAGING_REDIS_URL }}
```

#### テンプレートファイルのルール

- `.env.staging` / `.env.production` にはシークレット変数の値として `CHANGE_ME_IN_SECRETS` プレースホルダーのみ記載
- 実際のシークレット値はGitHub Repository Secrets（またはEnvironment Secrets）に保存
- `.dockerignore`で全`.env*`ファイルをDockerイメージから除外（要件9.2, 9.3）


## データモデル

本機能は新規データベーステーブルを追加しない。既存のデータモデルに変更はない。

ただし、以下の設定データ構造を定義する:

### ヘルスチェックレスポンス

```json
{
  "status": "healthy | unhealthy",
  "version": "abc1234",
  "timestamp": "2024-01-01T00:00:00Z",
  "services": {
    "database": "healthy | unhealthy: <error>",
    "redis": "healthy | unhealthy: <error>"
  }
}
```

### 環境設定構造

| 変数カテゴリ | 開発 | ステージング | 本番 |
|------------|------|------------|------|
| DEBUG | true | false | false |
| LOG_LEVEL | DEBUG | INFO | WARNING |
| ENVIRONMENT | development | staging | production |
| ENABLE_DOCS | true | true | false |
| POSTGRES_PORT (ホスト側) | 15432 | - | - |
| REDIS_PORT (ホスト側) | 16379 | - | - |
| API_PORT (ホスト側) | 8000 | - | 80 |

開発環境ではホスト側ポートをデフォルトポートからずらし（15432, 16379）、ローカルのhomebrew PostgreSQL/Redisとの競合を回避する（要件1.4）。

### Dockerイメージタグ戦略

| タグ | 付与条件 | 用途 |
|-----|---------|------|
| `<commit-sha>` | 全ビルド | 特定バージョンの追跡 |
| `latest` | 全ビルド | 最新ビルドの参照 |
| `stable` | mainブランチからのビルド | 本番デプロイ用 |
| `v1.2.3` | gitタグ作成時 | セマンティックバージョン |

### ファイル構成（新規・変更ファイル一覧）

```
genai/
├── .github/
│   └── workflows/
│       ├── pr.yml                    # PR時のテスト・リントワークフロー
│       └── deploy.yml                # main push/タグ時のビルド・デプロイワークフロー
├── docker/
│   ├── Dockerfile                    # バックエンド マルチステージ（変更）
│   └── entrypoint.sh                 # エントリポイントスクリプト（新規）
├── frontend/
│   ├── Dockerfile                    # フロントエンド開発用（既存維持）
│   ├── Dockerfile.prod               # フロントエンド本番用マルチステージ（新規）
│   ├── nginx.conf                    # フロントエンド本番用Nginx設定（新規）
│   └── .dockerignore                 # フロントエンド用dockerignore（新規）
├── docker-compose.yml                # ベース設定（変更: ポート公開削除、ヘルスチェック統一）
├── docker-compose.override.yml       # 開発用オーバーライド（新規）
├── docker-compose.prod.yml           # 本番用オーバーライド（新規）
├── .env.development                  # 開発環境設定（新規）
├── .env.staging                      # ステージング環境設定（新規）
├── .env.production                   # 本番環境設定テンプレート（新規）
├── .dockerignore                     # 更新（変更）
└── src/
    └── main.py                       # ヘルスチェック拡張（変更）
```

注意事項:
- `nginx.conf`は`frontend/`ディレクトリに配置（Dockerfile.prodのCOPYコンテキストに合わせる）
- `docker-compose.yml`（ベース）からはポート公開を削除し、オーバーライドファイルで環境ごとに設定
- `frontend/.dockerignore`を新規作成し、node_modules等を本番ビルドコンテキストから除外


## 正当性プロパティ (Correctness Properties)

*プロパティとは、システムの全ての有効な実行において真であるべき特性や振る舞いのことです。プロパティは人間が読める仕様と機械的に検証可能な正当性保証の橋渡しをします。*

### Property 1: 全サービス定義の完全性

*For any* docker-compose.ymlファイルにおいて、PostgreSQL、Redis、API、Celery Worker、Celery Beat、Frontendの全6サービスが定義されていること。

**Validates: Requirements 1.1**

### Property 2: 全サービスのヘルスチェック設定

*For any* docker-compose.ymlに定義されたサービスにおいて、そのサービスにはhealthcheck設定が含まれていること。

**Validates: Requirements 1.2, 8.2**

### Property 3: Dockerfileのセキュリティ準拠

*For any* 本番用Dockerfileにおいて、(a) ベースイメージがalpineまたはslimバリアントであり、(b) 非rootユーザーでプロセスを実行するUSERディレクティブが含まれていること。

**Validates: Requirements 2.3, 9.1**

### Property 4: シークレット情報の非ハードコード

*For any* 環境設定テンプレートファイル（.env.staging, .env.production）において、シークレット変数（パスワード、APIキー、暗号化キー）の値がプレースホルダーであり、実際の秘密情報が含まれていないこと。また、.dockerignoreが.envファイルを除外していること。

**Validates: Requirements 3.2, 9.2**

### Property 5: 本番環境でのDEBUGモード強制無効化

*For any* ENVIRONMENT=productionの設定において、エントリポイントスクリプトがDEBUG=falseを強制すること。

**Validates: Requirements 3.3, 9.5**

### Property 6: 必須環境変数の起動前検証

*For any* 必須環境変数のセットにおいて、いずれかの変数が未設定の場合、エントリポイントスクリプトが非ゼロの終了コードで終了すること。

**Validates: Requirements 3.5**

### Property 7: マイグレーション失敗時のデプロイ中止

*For any* Alembicマイグレーションの実行において、マイグレーションが非ゼロの終了コードを返した場合、エントリポイントスクリプトがアプリケーションを起動せずに終了すること。

**Validates: Requirements 6.2**

### Property 8: イメージタグの一貫性

*For any* CIビルドにおいて、生成されるDockerイメージにはgitコミットハッシュベースのタグとlatestタグの両方が付与されること。

**Validates: Requirements 4.4, 7.2**

### Property 9: ヘルスチェックレスポンスの完全性

*For any* DB接続状態とRedis接続状態の組み合わせにおいて、`/health`エンドポイントのレスポンスには(a) 全体ステータス、(b) データベース接続状態、(c) Redis接続状態、(d) サービスバージョン情報が含まれ、いずれかのサービスが異常な場合は全体ステータスが"unhealthy"となりHTTP 503を返すこと。

**Validates: Requirements 8.1, 8.4**

## エラーハンドリング

### エラーコード体系

全エラーをカテゴリ別にコード化し、ログ出力・アラート・ロールバック判定に使用する。

#### コード体系: `PCM-{カテゴリ}{番号}`

| カテゴリ | プレフィックス | 説明 |
|---------|-------------|------|
| インフラ・起動 | `PCM-E1xx` | コンテナ起動、環境変数、ポート競合 |
| データベース | `PCM-E2xx` | DB接続、マイグレーション、クエリ |
| Redis・Celery | `PCM-E3xx` | Redis接続、Celeryタスク、ブローカー |
| ネットワーク・通信 | `PCM-E4xx` | DNS解決、タイムアウト、TLS、外部API |
| CI/CDパイプライン | `PCM-E5xx` | ビルド、テスト、プッシュ、デプロイ |
| アプリケーション | `PCM-E6xx` | API、クローラー、データ処理 |
| セキュリティ | `PCM-E7xx` | 認証、認可、脆弱性 |

#### エラーコード一覧

##### インフラ・起動エラー (PCM-E1xx)

| コード | エラー | 重大度 | ロールバック | 対応 |
|--------|-------|--------|------------|------|
| PCM-E101 | 必須環境変数未設定 | CRITICAL | 不要（起動前） | entrypoint.shで検出、exit 1。デプロイ中止 |
| PCM-E102 | ポート競合 | HIGH | 不要（起動前） | 環境変数でポート変更。ログにポート番号出力 |
| PCM-E103 | Dockerイメージビルド失敗 | CRITICAL | 不要（ビルド前） | CI/CDパイプラインで後続ジョブスキップ |
| PCM-E104 | コンテナOOMKill | CRITICAL | 自動（再起動） | Docker Composeのrestart policyで再起動。memory limits調整 |
| PCM-E105 | ディスク容量不足 | CRITICAL | 手動 | Dockerボリューム・ログのクリーンアップ |
| PCM-E106 | 依存サービス起動タイムアウト | HIGH | 不要 | depends_on + service_healthyで待機。タイムアウト後にログ出力 |
| PCM-E107 | entrypoint.shの本番DEBUG強制失敗 | CRITICAL | 自動ロールバック | ENVIRONMENT=productionでDEBUG=false強制に失敗した場合、起動中止 |

##### データベースエラー (PCM-E2xx)

| コード | エラー | 重大度 | ロールバック | 対応 |
|--------|-------|--------|------------|------|
| PCM-E201 | DB接続タイムアウト | CRITICAL | 自動ロールバック | pg_isreadyで30回リトライ後にexit 1。デプロイ時は前バージョンに切り戻し |
| PCM-E202 | マイグレーション失敗 | CRITICAL | 自動ロールバック | exit 1でアプリ起動中止。`alembic downgrade`で前リビジョンに戻す |
| PCM-E203 | DB接続プール枯渇 | HIGH | 不要 | NullPool使用中のため発生しにくい。ログ監視で検知 |
| PCM-E204 | クエリタイムアウト | MEDIUM | 不要 | SQLAlchemy statement_timeoutで制御。Celeryタスクはtask_time_limitで保護 |
| PCM-E205 | DB認証失敗 | CRITICAL | 自動ロールバック | 環境変数の設定ミス。デプロイ時は前バージョンに切り戻し |
| PCM-E206 | テーブル/スキーマ不整合 | CRITICAL | 自動ロールバック | マイグレーション漏れ。`alembic downgrade`後に前バージョンデプロイ |

##### Redis・Celeryエラー (PCM-E3xx)

| コード | エラー | 重大度 | ロールバック | 対応 |
|--------|-------|--------|------------|------|
| PCM-E301 | Redis接続失敗 | HIGH | 不要（再起動） | ヘルスチェックで検知→コンテナ再起動。Celeryはブローカー復旧まで自動リトライ |
| PCM-E302 | Celeryタスクタイムアウト | MEDIUM | 不要 | task_time_limit(300s)で強制終了。task_soft_time_limit(240s)で警告 |
| PCM-E303 | Celeryブローカー接続断 | HIGH | 不要（再接続） | Celeryの自動再接続機能で復旧。broker_connection_retry_on_startup=True |
| PCM-E304 | Redisメモリ上限到達 | HIGH | 不要 | maxmemory-policy設定で古いキーを自動削除。アラート通知 |
| PCM-E305 | Celery Beatスケジュール重複実行 | MEDIUM | 不要 | Beatインスタンスを1つに制限（ECSタスク数=1） |

##### ネットワーク・通信エラー (PCM-E4xx)

| コード | エラー | 重大度 | ロールバック | 対応 |
|--------|-------|--------|------------|------|
| PCM-E401 | DNS解決失敗 | CRITICAL | 自動ロールバック | Docker内部DNS（サービス名解決）失敗。コンテナ再起動で復旧しない場合はネットワーク再作成 |
| PCM-E402 | サービス間通信タイムアウト | HIGH | 不要（リトライ） | API→DB/Redis間のタイムアウト。接続プールのタイムアウト設定で制御 |
| PCM-E403 | TLS/SSL証明書エラー | CRITICAL | 自動ロールバック | 将来のRDS SSL接続時に発生しうる。証明書の有効期限・設定を確認 |
| PCM-E404 | 外部API通信失敗（SendGrid/Slack） | LOW | 不要 | アラート送信失敗。リトライ（ALERT_RETRY_MAX_ATTEMPTS=3）後にログ記録 |
| PCM-E405 | GHCRレジストリ接続失敗 | HIGH | 不要（リトライ） | CI/CDでのイメージプッシュ/プル失敗。GitHub Actionsの自動リトライで対応 |
| PCM-E406 | クローラーターゲットサイト接続失敗 | LOW | 不要 | Playwright timeout。max_retries(3)で指数バックオフリトライ |
| PCM-E407 | Docker Networkパーティション | CRITICAL | 自動（再起動） | コンテナ間通信不能。Docker Composeの再起動で復旧 |

##### CI/CDパイプラインエラー (PCM-E5xx)

| コード | エラー | 重大度 | ロールバック | 対応 |
|--------|-------|--------|------------|------|
| PCM-E501 | バックエンドテスト失敗 | HIGH | 不要（デプロイ前） | 後続ジョブスキップ。PR上に失敗レポート |
| PCM-E502 | フロントエンドテスト失敗 | HIGH | 不要（デプロイ前） | 同上 |
| PCM-E503 | Dockerイメージプッシュ失敗 | HIGH | 不要（デプロイ前） | GHCR認証確認。リトライ後も失敗ならジョブ失敗 |
| PCM-E504 | セキュリティスキャンCRITICAL検出 | CRITICAL | 不要（デプロイ前） | デプロイ中止。スキャン結果をアーティファクト保存 |
| PCM-E505 | ECSデプロイ失敗 | CRITICAL | 自動ロールバック | ECSサービス安定性待機失敗。前バージョンのタスク定義に自動切り戻し |
| PCM-E506 | ECSタスク起動失敗 | CRITICAL | 自動ロールバック | ヘルスチェック失敗でECSが旧タスクを維持（ローリングアップデート） |
| PCM-E507 | GitHub Actions OIDC認証失敗 | CRITICAL | 不要（デプロイ前） | IAMロール設定確認。シークレット設定確認 |

##### アプリケーションエラー (PCM-E6xx)

| コード | エラー | 重大度 | ロールバック | 対応 |
|--------|-------|--------|------------|------|
| PCM-E601 | APIレスポンスエラー率急増 | HIGH | 自動ロールバック | ヘルスチェック失敗→コンテナ再起動。改善しない場合は前バージョンに切り戻し |
| PCM-E602 | クローラーの連続失敗 | MEDIUM | 不要 | crawl_all_sitesのresult['failed']を監視。閾値超過でアラート |
| PCM-E603 | データ処理パイプライン異常 | MEDIUM | 不要 | Celeryタスクのstatus='error'を監視 |

##### セキュリティエラー (PCM-E7xx)

| コード | エラー | 重大度 | ロールバック | 対応 |
|--------|-------|--------|------------|------|
| PCM-E701 | 本番環境でDEBUGモード有効 | CRITICAL | 自動ロールバック | entrypoint.shで強制無効化。検出時は即座にコンテナ停止 |
| PCM-E702 | シークレット漏洩検出 | CRITICAL | 手動 | .dockerignoreで.env除外。CI/CDでシークレットスキャン |
| PCM-E703 | 不正なCORSオリジン | HIGH | 自動ロールバック | CORS_ORIGINS環境変数の設定ミス。前バージョンに切り戻し |

### ログ出力フォーマット

全エラーは以下の構造化ログフォーマットで出力する:

```python
import logging
import json
from datetime import datetime, timezone

class StructuredLogger:
    """構造化ログ出力。エラーコードとメタデータを含む。"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def error(self, code: str, message: str, **kwargs):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "error_code": code,
            "message": message,
            "service": os.getenv("SERVICE_NAME", "unknown"),
            "version": os.getenv("IMAGE_TAG", "dev"),
            "environment": os.getenv("ENVIRONMENT", "development"),
            **kwargs
        }
        self.logger.error(json.dumps(log_entry))
```

使用例:
```python
logger = StructuredLogger("api")
logger.error("PCM-E201", "Database connection timeout", host="postgres", retries=30)
logger.error("PCM-E301", "Redis connection failed", url="redis://redis:6379/0")
```

entrypoint.shでのログ出力:
```bash
log_error() {
  local code=$1
  local message=$2
  echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"level\":\"ERROR\",\"error_code\":\"$code\",\"message\":\"$message\",\"service\":\"entrypoint\",\"environment\":\"$ENVIRONMENT\"}"
}

# 使用例
log_error "PCM-E101" "Required environment variable $var is not set"
log_error "PCM-E201" "Database connection timeout after $MAX_RETRIES retries"
log_error "PCM-E202" "Migration failed with status $MIGRATION_STATUS"
```

### ロールバック・切り戻し機構

#### 1. ECSデプロイのローリングアップデートによる自動ロールバック

ECS Fargateのデプロイはローリングアップデート方式を採用。新タスクがヘルスチェックに失敗した場合、ECSが自動的に旧タスクを維持する。

```mermaid
graph TD
    DEPLOY[新バージョンデプロイ] --> NEW_TASK[新タスク起動]
    NEW_TASK --> HC{ヘルスチェック}
    HC -->|成功| DRAIN[旧タスクドレイン]
    DRAIN --> COMPLETE[デプロイ完了]
    HC -->|失敗| ROLLBACK[新タスク停止]
    ROLLBACK --> KEEP_OLD[旧タスク維持]
    KEEP_OLD --> ALERT[PCM-E506 アラート送信]
```

ECSサービス設定:
```json
{
  "deploymentConfiguration": {
    "minimumHealthyPercent": 100,
    "maximumPercent": 200,
    "deploymentCircuitBreaker": {
      "enable": true,
      "rollback": true
    }
  }
}
```

- `deploymentCircuitBreaker.rollback: true` により、新タスクの起動失敗が連続した場合にECSが自動的に前のタスク定義にロールバック
- `minimumHealthyPercent: 100` により、旧タスクは新タスクが正常になるまで停止されない

#### 2. GitHub Actionsからの手動ロールバック

deploy.ymlにロールバック用のワークフローディスパッチを追加:

```yaml
# .github/workflows/rollback.yml
name: Rollback
on:
  workflow_dispatch:
    inputs:
      service:
        description: 'ロールバック対象サービス'
        required: true
        type: choice
        options: [api, celery-worker, celery-beat, frontend, all]
      image_tag:
        description: '切り戻し先のイメージタグ（例: sha-abc1234）'
        required: true
        type: string
      environment:
        description: 'デプロイ先環境'
        required: true
        type: choice
        options: [staging, production]

jobs:
  rollback:
    runs-on: ubuntu-latest
    environment: ${{ inputs.environment }}
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ inputs.environment == 'production' && secrets.AWS_ROLE_ARN_PRODUCTION || secrets.AWS_ROLE_ARN_STAGING }}
          aws-region: ${{ vars.AWS_REGION }}
      
      - name: Rollback services
        run: |
          SERVICES="${{ inputs.service }}"
          TAG="${{ inputs.image_tag }}"
          
          if [ "$SERVICES" = "all" ]; then
            SERVICES="api celery-worker celery-beat frontend"
          fi
          
          for svc in $SERVICES; do
            echo "Rolling back $svc to $TAG..."
            
            # サービスに応じたタスク定義ファミリーとイメージを決定
            case $svc in
              api)
                FAMILY="${{ vars.ECS_TASK_FAMILY_API }}"
                IMAGE="${{ env.REGISTRY }}/${{ github.repository }}/api:$TAG"
                ECS_SERVICE="${{ vars.ECS_SERVICE_API }}"
                ;;
              celery-worker)
                FAMILY="${{ vars.ECS_TASK_FAMILY_WORKER }}"
                IMAGE="${{ env.REGISTRY }}/${{ github.repository }}/api:$TAG"
                ECS_SERVICE="${{ vars.ECS_SERVICE_WORKER }}"
                ;;
              celery-beat)
                FAMILY="${{ vars.ECS_TASK_FAMILY_BEAT }}"
                IMAGE="${{ env.REGISTRY }}/${{ github.repository }}/api:$TAG"
                ECS_SERVICE="${{ vars.ECS_SERVICE_BEAT }}"
                ;;
              frontend)
                FAMILY="${{ vars.ECS_TASK_FAMILY_FRONTEND }}"
                IMAGE="${{ env.REGISTRY }}/${{ github.repository }}/frontend:$TAG"
                ECS_SERVICE="${{ vars.ECS_SERVICE_FRONTEND }}"
                ;;
            esac
            
            # 現在のタスク定義を取得してイメージを差し替え
            TASK_DEF=$(aws ecs describe-task-definition --task-definition $FAMILY --query taskDefinition)
            NEW_TASK_DEF=$(echo $TASK_DEF | jq --arg IMG "$IMAGE" '.containerDefinitions[0].image = $IMG')
            
            # 新しいタスク定義を登録してデプロイ
            echo "$NEW_TASK_DEF" | jq '{containerDefinitions, family, taskRoleArn, executionRoleArn, networkMode, requiresCompatibilities, cpu, memory}' > /tmp/task-def.json
            NEW_ARN=$(aws ecs register-task-definition --cli-input-json file:///tmp/task-def.json --query taskDefinition.taskDefinitionArn --output text)
            
            aws ecs update-service \
              --cluster ${{ vars.ECS_CLUSTER }} \
              --service $ECS_SERVICE \
              --task-definition $NEW_ARN \
              --force-new-deployment
            
            echo "Waiting for $svc to stabilize..."
            aws ecs wait services-stable \
              --cluster ${{ vars.ECS_CLUSTER }} \
              --services $ECS_SERVICE
            
            echo "✓ $svc rolled back to $TAG"
          done
        env:
          REGISTRY: ghcr.io
```

#### 3. Alembicマイグレーションのロールバック

entrypoint.shにマイグレーション失敗時の自動ダウングレード機能を追加:

```bash
# マイグレーション実行（ロールバック対応版）
if [ "$RUN_MIGRATIONS" = "true" ]; then
  # 現在のリビジョンを記録
  CURRENT_REV=$(alembic current 2>/dev/null | grep -oP '[a-f0-9]+' | head -1)
  
  echo "Running Alembic migrations..."
  alembic upgrade head
  MIGRATION_STATUS=$?
  
  if [ $MIGRATION_STATUS -ne 0 ]; then
    log_error "PCM-E202" "Migration failed with status $MIGRATION_STATUS"
    
    # 前のリビジョンにダウングレード
    if [ -n "$CURRENT_REV" ]; then
      echo "Attempting rollback to revision $CURRENT_REV..."
      alembic downgrade "$CURRENT_REV"
      DOWNGRADE_STATUS=$?
      if [ $DOWNGRADE_STATUS -eq 0 ]; then
        log_error "PCM-E202" "Migration rolled back to $CURRENT_REV successfully"
      else
        log_error "PCM-E202" "Migration rollback also failed with status $DOWNGRADE_STATUS"
      fi
    fi
    
    exit 1  # デプロイ中止
  fi
  echo "Migrations completed successfully"
fi
```

#### 4. ロールバック判定マトリクス

| エラーコード | 検出方法 | 自動ロールバック | 手動ロールバック |
|------------|---------|----------------|----------------|
| PCM-E201 | entrypoint.sh exit 1 | ECS Circuit Breaker | rollback.yml |
| PCM-E202 | entrypoint.sh exit 1 | alembic downgrade + ECS Circuit Breaker | rollback.yml |
| PCM-E205 | entrypoint.sh exit 1 | ECS Circuit Breaker | rollback.yml |
| PCM-E206 | entrypoint.sh exit 1 | alembic downgrade + ECS Circuit Breaker | rollback.yml |
| PCM-E401 | ヘルスチェック失敗 | コンテナ再起動 | rollback.yml |
| PCM-E505 | ECS wait-for-stability失敗 | ECS Circuit Breaker | rollback.yml |
| PCM-E506 | ECSヘルスチェック失敗 | ECS Circuit Breaker（旧タスク維持） | rollback.yml |
| PCM-E601 | /healthエンドポイント503 | コンテナ再起動→ECS Circuit Breaker | rollback.yml |
| PCM-E701 | entrypoint.sh検出 | 起動中止→ECS Circuit Breaker | rollback.yml |
| PCM-E703 | アプリ起動後のCORS検証 | — | rollback.yml |

### Docker Compose起動時のエラー

| エラー状況 | エラーコード | 対応 |
|-----------|-----------|------|
| サービスの依存先が起動失敗 | PCM-E106 | `depends_on` + `condition: service_healthy`により待機。タイムアウト時はログ出力 |
| ポート競合 | PCM-E102 | 環境変数によるポート設定で回避 |
| イメージビルド失敗 | PCM-E103 | docker composeの標準エラー出力に表示 |
| コンテナOOMKill | PCM-E104 | restart policyで再起動。memory limits調整 |

### エントリポイントスクリプトのエラー

| エラー状況 | エラーコード | 対応 |
|-----------|-----------|------|
| 必須環境変数未設定 | PCM-E101 | エラーメッセージ出力後、exit 1でコンテナ停止 |
| DB接続不可 | PCM-E201 | pg_isreadyで最大30回リトライ。タイムアウト後にexit 1 |
| マイグレーション失敗 | PCM-E202 | alembic downgradeで前リビジョンに戻した後、exit 1 |
| DB認証失敗 | PCM-E205 | 環境変数確認のログ出力後、exit 1 |

### CI/CDパイプラインのエラー

| エラー状況 | エラーコード | 対応 |
|-----------|-----------|------|
| テスト失敗 | PCM-E501/E502 | 後続ジョブスキップ。PR上に失敗レポート |
| Dockerビルド失敗 | PCM-E103 | デプロイジョブスキップ |
| セキュリティスキャンCRITICAL | PCM-E504 | デプロイ中止。スキャン結果をアーティファクト保存 |
| レジストリプッシュ失敗 | PCM-E503 | リトライ後も失敗ならジョブ失敗 |
| ECSデプロイ失敗 | PCM-E505 | ECS Circuit Breakerで自動ロールバック |
| OIDC認証失敗 | PCM-E507 | IAMロール・シークレット設定確認 |

### ヘルスチェックのエラー

| エラー状況 | エラーコード | 対応 |
|-----------|-----------|------|
| DB接続失敗 | PCM-E201 | `/health`がHTTP 503。再起動ポリシーでコンテナ再起動 |
| Redis接続失敗 | PCM-E301 | `/health`がHTTP 503。同上 |
| ヘルスチェックタイムアウト | PCM-E402 | retries回数後にunhealthy判定 |

### ネットワーク・通信エラー

| エラー状況 | エラーコード | 対応 |
|-----------|-----------|------|
| DNS解決失敗 | PCM-E401 | コンテナ再起動。復旧しない場合はDocker Network再作成 |
| サービス間通信タイムアウト | PCM-E402 | 接続プールのタイムアウト設定で制御 |
| 外部API通信失敗 | PCM-E404 | リトライ（3回）後にログ記録。アラート送信は非クリティカル |
| クローラーターゲット接続失敗 | PCM-E406 | 指数バックオフリトライ（3回）。結果をDB記録 |

## テスト戦略

### テストアプローチ

ユニットテストとプロパティベーステストの二重アプローチを採用する。

- **ユニットテスト**: 特定の例、エッジケース、エラー条件の検証
- **プロパティベーステスト**: 全入力に対する普遍的プロパティの検証

### プロパティベーステスト設定

- **バックエンド**: Hypothesis（Python） — 既にプロジェクトに導入済み（`requirements.txt`に`hypothesis==6.92.1`）
- **フロントエンド**: fast-check（TypeScript） — 既にプロジェクトに導入済み（`package.json`に`fast-check`）
- 各テストは最低100イテレーション実行
- 各テストにはデザインドキュメントのプロパティ番号をコメントで参照
- タグ形式: **Feature: docker-cicd-pipeline, Property {number}: {property_text}**
- 各正当性プロパティは1つのプロパティベーステストで実装する

### ユニットテスト

| テスト対象 | テスト内容 | ツール |
|-----------|----------|-------|
| ヘルスチェックエンドポイント | DB/Redis正常時のレスポンス確認 | pytest + httpx |
| ヘルスチェックエンドポイント | DB障害時のHTTP 503レスポンス確認 | pytest + httpx |
| エントリポイントスクリプト | 必須変数未設定時のexit 1確認 | bash test / pytest |
| エントリポイントスクリプト | マイグレーション失敗時のexit 1確認 | bash test / pytest |
| Docker Compose設定 | YAML構文の妥当性確認 | pytest + pyyaml |
| Dockerfile | マルチステージ構成の確認 | pytest |
| .dockerignore | 必須除外パターンの確認 | pytest |
| 環境設定テンプレート | 全必須変数の存在確認 | pytest |
| GitHub Actionsワークフロー | YAML構文とジョブ依存関係の確認 | pytest + pyyaml |

### プロパティベーステスト

| プロパティ | テスト内容 | ツール |
|-----------|----------|-------|
| Property 1 | ランダムなサービス名セットに対し、全6サービスが含まれることを検証 | Hypothesis |
| Property 2 | docker-compose内の全サービスに対し、healthcheck設定の存在を検証 | Hypothesis |
| Property 3 | 全Dockerfileに対し、セキュリティ要件（alpine/slim + non-root）を検証 | Hypothesis |
| Property 4 | ランダムなシークレット変数名に対し、テンプレートにハードコード値がないことを検証 | Hypothesis |
| Property 5 | ランダムなDEBUG値に対し、ENVIRONMENT=production時にDEBUG=falseが強制されることを検証 | Hypothesis |
| Property 6 | ランダムな必須変数の欠落パターンに対し、検証スクリプトが失敗することを検証 | Hypothesis |
| Property 7 | ランダムなマイグレーション終了コードに対し、非ゼロ時にスクリプトが終了することを検証 | Hypothesis |
| Property 8 | ランダムなコミットハッシュに対し、生成されるタグにハッシュとlatestが含まれることを検証 | Hypothesis |
| Property 9 | DB/Redisの全状態組み合わせに対し、ヘルスレスポンスの完全性と正確性を検証 | Hypothesis |

### 統合テスト

| テスト対象 | テスト内容 |
|-----------|----------|
| Docker Compose起動 | `docker compose config`による設定検証 |
| Dockerイメージビルド | バックエンド・フロントエンドイメージのビルド成功確認 |
| ヘルスチェック | 起動後の`/health`エンドポイントレスポンス確認 |
| マイグレーション | コンテナ内でのAlembicマイグレーション実行確認 |


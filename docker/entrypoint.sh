#!/bin/bash
set -e

# ---------------------------------------------------------------------------
# screenshotsディレクトリの権限修正（ボリュームマウント時にrootで作成される対策）
# ---------------------------------------------------------------------------
if [ "$(id -u)" = "0" ]; then
  chown -R appuser:appuser /app/screenshots 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# Structured log helper (Requirements 10.3)
# ---------------------------------------------------------------------------
log_error() {
  local error_code="$1"
  local message="$2"
  local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "{\"timestamp\":\"$timestamp\",\"level\":\"ERROR\",\"error_code\":\"$error_code\",\"service\":\"entrypoint\",\"version\":\"${IMAGE_TAG:-dev}\",\"environment\":\"${ENVIRONMENT:-development}\",\"message\":\"$message\"}"
}

# 必須環境変数チェック（要件3.5）
REQUIRED_VARS="DATABASE_URL REDIS_URL SECRET_KEY"
for var in $REQUIRED_VARS; do
  if [ -z "${!var}" ]; then
    log_error "PCM-E101" "Required environment variable $var is not set"
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
      log_error "PCM-E201" "Database connection timeout after $MAX_RETRIES retries"
      exit 1
    fi
    echo "Database not ready, retrying in 2s... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
  done
  # Record current revision before migration for rollback (Requirements 11.3)
  CURRENT_REVISION=$(alembic current 2>/dev/null | grep -oP '[a-f0-9]+' | head -1 || echo "")

  echo "Running Alembic migrations..."
  alembic upgrade head
  MIGRATION_STATUS=$?
  if [ $MIGRATION_STATUS -ne 0 ]; then
    log_error "PCM-E202" "Migration failed with status $MIGRATION_STATUS"
    if [ -n "$CURRENT_REVISION" ]; then
      echo "Attempting rollback to revision $CURRENT_REVISION..."
      alembic downgrade "$CURRENT_REVISION" || log_error "PCM-E202" "Rollback also failed"
    fi
    exit 1
  fi
  echo "Migrations completed successfully"
fi

# appuserに切り替えてアプリケーション起動
if [ "$(id -u)" = "0" ]; then
  exec gosu appuser "$@"
else
  exec "$@"
fi

# Deployment Guide - Payment Compliance Monitor

本ドキュメントは、Payment Compliance Monitorシステムを本番環境にデプロイする手順を説明します。

## 目次

1. [前提条件](#前提条件)
2. [環境準備](#環境準備)
3. [Docker Composeデプロイ](#docker-composeデプロイ)
4. [本番環境設定](#本番環境設定)
5. [セキュリティ設定](#セキュリティ設定)
6. [監視とログ](#監視とログ)
7. [バックアップとリカバリ](#バックアップとリカバリ)
8. [トラブルシューティング](#トラブルシューティング)

---

## 前提条件

### ハードウェア要件

**最小構成:**
- CPU: 2コア
- メモリ: 4GB RAM
- ストレージ: 50GB SSD

**推奨構成:**
- CPU: 4コア以上
- メモリ: 8GB RAM以上
- ストレージ: 100GB SSD以上

### ソフトウェア要件

- **OS**: Ubuntu 22.04 LTS / CentOS 8+ / Amazon Linux 2
- **Docker**: 24.0+
- **Docker Compose**: 2.20+
- **Git**: 2.30+

### ネットワーク要件

- **インバウンド**:
  - ポート 80 (HTTP) - オプション
  - ポート 443 (HTTPS) - 推奨
  - ポート 8000 (API) - ファイアウォールで保護

- **アウトバウンド**:
  - ポート 443 (HTTPS) - 外部API通信用
  - ポート 25/587 (SMTP) - メール送信用

---

## 環境準備

### 1. サーバーセットアップ

```bash
# システムアップデート
sudo apt update && sudo apt upgrade -y

# 必要なパッケージのインストール
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git
```

### 2. Dockerインストール

```bash
# Docker公式GPGキーの追加
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Dockerリポジトリの追加
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Dockerのインストール
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Dockerサービスの起動と自動起動設定
sudo systemctl start docker
sudo systemctl enable docker

# 現在のユーザーをdockerグループに追加
sudo usermod -aG docker $USER
newgrp docker

# インストール確認
docker --version
docker compose version
```

### 3. アプリケーションのクローン

```bash
# プロジェクトディレクトリの作成
sudo mkdir -p /opt/payment-monitor
sudo chown $USER:$USER /opt/payment-monitor
cd /opt/payment-monitor

# リポジトリのクローン
git clone <repository-url> .
cd genai
```

---

## Docker Composeデプロイ

### 1. 環境変数の設定

```bash
# .envファイルの作成
cp .env.example .env

# エディタで.envを編集
nano .env
```

**重要な設定項目:**

```bash
# データベース（強力なパスワードに変更）
POSTGRES_PASSWORD=<strong-password-here>

# セキュリティキー（必ず変更）
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# 外部サービス
SENDGRID_API_KEY=<your-sendgrid-key>
SLACK_BOT_TOKEN=<your-slack-token>

# 環境設定
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
```

### 2. データベースの初期化

```bash
# PostgreSQLとRedisの起動
docker compose up -d postgres redis

# データベースの準備完了を待つ
sleep 10

# マイグレーションの実行
docker compose run --rm api alembic upgrade head
```

### 3. 全サービスの起動

```bash
# すべてのサービスを起動
docker compose up -d

# サービスの状態確認
docker compose ps

# ログの確認
docker compose logs -f
```

### 4. 動作確認

```bash
# ヘルスチェック
curl http://localhost:8000/health

# API ドキュメント（開発環境のみ）
curl http://localhost:8000/docs
```

---

## 本番環境設定

### 1. リバースプロキシ（Nginx）の設定

```bash
# Nginxのインストール
sudo apt install -y nginx

# 設定ファイルの作成
sudo nano /etc/nginx/sites-available/payment-monitor
```

**Nginx設定例:**

```nginx
upstream payment_monitor_api {
    server localhost:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    # HTTPSへリダイレクト
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL証明書（Let's Encryptなど）
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # SSL設定
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # セキュリティヘッダー
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # ログ設定
    access_log /var/log/nginx/payment-monitor-access.log;
    error_log /var/log/nginx/payment-monitor-error.log;

    # API プロキシ
    location /api/ {
        proxy_pass http://payment_monitor_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # タイムアウト設定
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # 静的ファイル（フロントエンド）
    location / {
        root /opt/payment-monitor/genai/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 最大アップロードサイズ
    client_max_body_size 10M;
}
```

```bash
# 設定の有効化
sudo ln -s /etc/nginx/sites-available/payment-monitor /etc/nginx/sites-enabled/

# 設定のテスト
sudo nginx -t

# Nginxの再起動
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 2. SSL証明書の取得（Let's Encrypt）

```bash
# Certbotのインストール
sudo apt install -y certbot python3-certbot-nginx

# SSL証明書の取得
sudo certbot --nginx -d your-domain.com

# 自動更新の設定
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

### 3. ファイアウォール設定

```bash
# UFWのインストールと設定
sudo apt install -y ufw

# デフォルトポリシー
sudo ufw default deny incoming
sudo ufw default allow outgoing

# 必要なポートを開放
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# ファイアウォールの有効化
sudo ufw enable

# 状態確認
sudo ufw status
```

---

## セキュリティ設定

### 1. データベースセキュリティ

```bash
# PostgreSQLコンテナに接続
docker compose exec postgres psql -U payment_monitor

# パスワードポリシーの設定
ALTER ROLE payment_monitor WITH PASSWORD '<strong-password>';

# 不要な権限の削除
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO payment_monitor;
```

### 2. Redisセキュリティ

docker-compose.ymlに追加:

```yaml
redis:
  image: redis:7.2-alpine
  command: redis-server --requirepass <redis-password>
  environment:
    - REDIS_PASSWORD=<redis-password>
```

.envファイルを更新:

```bash
REDIS_URL=redis://:<redis-password>@redis:6379/0
```

### 3. アプリケーションセキュリティ

```bash
# 本番環境では必ずfalseに設定
DEBUG=false
ENABLE_DOCS=false

# CORS設定を厳格に
CORS_ORIGINS=https://your-domain.com

# セキュリティヘッダーの有効化（Nginxで設定済み）
```

---

## 監視とログ

### 1. ログ管理

```bash
# ログローテーション設定
sudo nano /etc/logrotate.d/payment-monitor
```

```
/var/log/nginx/payment-monitor-*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data adm
    sharedscripts
    postrotate
        [ -f /var/run/nginx.pid ] && kill -USR1 `cat /var/run/nginx.pid`
    endscript
}
```

### 2. Dockerログの管理

docker-compose.ymlに追加:

```yaml
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 3. ヘルスチェック監視

```bash
# cronジョブでヘルスチェック
crontab -e
```

```cron
# 5分ごとにヘルスチェック
*/5 * * * * curl -f http://localhost:8000/health || echo "Health check failed" | mail -s "Payment Monitor Alert" admin@example.com
```

### 4. リソース監視

```bash
# Docker統計情報の確認
docker stats

# システムリソースの確認
htop
df -h
free -h
```

---

## バックアップとリカバリ

### 1. データベースバックアップ

```bash
# バックアップスクリプトの作成
sudo nano /opt/payment-monitor/scripts/backup-db.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/payment-monitor/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/payment_monitor_$DATE.sql.gz"

mkdir -p $BACKUP_DIR

docker compose exec -T postgres pg_dump -U payment_monitor payment_monitor | gzip > $BACKUP_FILE

# 30日以上古いバックアップを削除
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_FILE"
```

```bash
# 実行権限の付与
chmod +x /opt/payment-monitor/scripts/backup-db.sh

# cronで毎日実行
crontab -e
```

```cron
# 毎日午前3時にバックアップ
0 3 * * * /opt/payment-monitor/scripts/backup-db.sh
```

### 2. データベースリストア

```bash
# バックアップからリストア
gunzip < /opt/payment-monitor/backups/payment_monitor_YYYYMMDD_HHMMSS.sql.gz | \
docker compose exec -T postgres psql -U payment_monitor payment_monitor
```

### 3. ボリュームバックアップ

```bash
# Dockerボリュームのバックアップ
docker run --rm \
  -v payment-monitor_postgres_data:/data \
  -v /opt/payment-monitor/backups:/backup \
  alpine tar czf /backup/postgres_volume_$(date +%Y%m%d).tar.gz -C /data .
```

---

## トラブルシューティング

### 問題: コンテナが起動しない

```bash
# ログの確認
docker compose logs api

# コンテナの状態確認
docker compose ps

# コンテナの再起動
docker compose restart api
```

### 問題: データベース接続エラー

```bash
# PostgreSQLの状態確認
docker compose exec postgres pg_isready -U payment_monitor

# 接続テスト
docker compose exec postgres psql -U payment_monitor -d payment_monitor -c "SELECT 1;"

# ネットワークの確認
docker network inspect payment-monitor-network
```

### 問題: Celeryタスクが実行されない

```bash
# Celery Workerのログ確認
docker compose logs celery-worker

# Redisの接続確認
docker compose exec redis redis-cli ping

# タスクキューの確認
docker compose exec celery-worker celery -A src.celery_app inspect active
```

### 問題: メモリ不足

```bash
# メモリ使用状況の確認
free -h
docker stats

# 不要なコンテナの削除
docker system prune -a

# スワップの追加（一時的な対処）
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## アップデート手順

### 1. アプリケーションのアップデート

```bash
cd /opt/payment-monitor/genai

# 最新コードの取得
git pull origin main

# コンテナの再ビルドと再起動
docker compose build
docker compose up -d

# マイグレーションの実行
docker compose exec api alembic upgrade head
```

### 2. ゼロダウンタイムデプロイ

```bash
# Blue-Greenデプロイメント用のスクリプト
# （詳細は別途ドキュメント参照）
```

---

## パフォーマンスチューニング

### 1. PostgreSQL最適化

```sql
-- 接続数の調整
ALTER SYSTEM SET max_connections = 200;

-- 共有バッファの調整（メモリの25%）
ALTER SYSTEM SET shared_buffers = '2GB';

-- ワークメモリの調整
ALTER SYSTEM SET work_mem = '16MB';

-- 設定の再読み込み
SELECT pg_reload_conf();
```

### 2. Celery最適化

docker-compose.ymlで調整:

```yaml
celery-worker:
  command: celery -A src.celery_app worker --loglevel=info --concurrency=8 --max-tasks-per-child=1000
```

### 3. Redis最適化

```bash
# Redisの設定調整
docker compose exec redis redis-cli CONFIG SET maxmemory 1gb
docker compose exec redis redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

---

## 本番環境チェックリスト

- [ ] 環境変数が本番用に設定されている
- [ ] すべてのセキュリティキーが変更されている
- [ ] DEBUG=false に設定されている
- [ ] SSL証明書が設定されている
- [ ] ファイアウォールが設定されている
- [ ] データベースバックアップが設定されている
- [ ] ログローテーションが設定されている
- [ ] 監視・アラートが設定されている
- [ ] ドキュメントが最新である
- [ ] 緊急連絡先が明確である

---

## サポート

問題が発生した場合:

1. ログを確認: `docker compose logs`
2. ドキュメントを参照
3. 開発チームに連絡

---

**最終更新**: 2024年
**バージョン**: 1.0

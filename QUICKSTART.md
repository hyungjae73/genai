# Payment Compliance Monitor - クイックスタートガイド

このガイドでは、ローカル環境でPayment Compliance Monitorを起動する手順を説明します。

## 前提条件

以下がインストール済みであることを確認してください：

- ✅ PostgreSQL 15 (Homebrewでインストール済み)
- ✅ Redis (Homebrewでインストール済み)
- ✅ Python 3.9+ (システムにインストール済み)
- ✅ Node.js 18+ (フロントエンド用)

## セットアップ状況

以下のセットアップが完了しています：

1. ✅ PostgreSQL データベース作成済み
   - データベース名: `payment_monitor`
   - ユーザー: `payment_monitor`
   
2. ✅ Python仮想環境作成済み (`venv/`)

3. ✅ 依存パッケージインストール済み

4. ✅ データベースマイグレーション実行済み

5. ✅ 環境変数設定済み (`.env`)
   - ポート: 8080
   - セキュリティキー生成済み

## 起動方法

### オプション1: すべてのサービスを一度に起動

```bash
cd genai
./start_all.sh
```

このスクリプトは以下を自動的に起動します：
- PostgreSQL (未起動の場合)
- Redis (未起動の場合)
- FastAPI APIサーバー (ポート 8080)
- Celery Worker (バックグラウンドタスク処理)
- Celery Beat (スケジューラー)
- React フロントエンド (ポート 5173)

### オプション2: 個別にサービスを起動

#### 1. FastAPI APIサーバー

```bash
cd genai
./start_api.sh
```

#### 2. Celery Worker (別ターミナル)

```bash
cd genai
./start_celery_worker.sh
```

#### 3. Celery Beat (別ターミナル)

```bash
cd genai
./start_celery_beat.sh
```

#### 4. React フロントエンド (別ターミナル)

```bash
cd genai/frontend
./start_frontend.sh
```

## アクセスURL

サービスが起動したら、以下のURLにアクセスできます：

- **API ドキュメント (Swagger UI)**: http://localhost:8080/docs
- **API ヘルスチェック**: http://localhost:8080/health
- **フロントエンド ダッシュボード**: http://localhost:5173

## サービスの停止

### すべてのサービスを停止

```bash
cd genai
./stop_all.sh
```

### 個別に停止

```bash
# FastAPI
pkill -f "uvicorn src.main:app"

# Celery Worker
pkill -f "celery.*worker"

# Celery Beat
pkill -f "celery.*beat"

# Frontend
pkill -f "vite"
```

## ログの確認

ログは `genai/logs/` ディレクトリに保存されます：

```bash
# APIログ
tail -f logs/api.log

# Celery Workerログ
tail -f logs/celery_worker.log

# Celery Beatログ
tail -f logs/celery_beat.log

# Frontendログ
tail -f logs/frontend.log
```

## トラブルシューティング

### PostgreSQLが起動しない

```bash
brew services start postgresql@15
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"
```

### Redisが起動しない

```bash
brew services start redis
redis-cli ping  # PONGが返ってくればOK
```

### ポート8080が使用中

別のポートに変更する場合：

1. `.env` ファイルの `API_PORT` を変更
2. `start_api.sh` のポート番号を変更
3. `frontend/.env` の `VITE_API_BASE_URL` を変更

### データベース接続エラー

```bash
# データベースが存在するか確認
psql -U payment_monitor -d payment_monitor -c "SELECT 1;"

# マイグレーションを再実行
source venv/bin/activate
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"
alembic upgrade head
```

## 基本的な使い方

### 1. サイトの登録

```bash
curl -X POST "http://localhost:8080/api/sites/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example Payment Site",
    "url": "https://example.com",
    "monitoring_enabled": true
  }'
```

### 2. 契約条件の登録

```bash
curl -X POST "http://localhost:8080/api/contracts/" \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": 1,
    "content": "利用規約の内容...",
    "version": "1.0"
  }'
```

### 3. クローリングの実行

```bash
curl -X POST "http://localhost:8080/api/monitoring/crawl/1"
```

### 4. アラートの確認

```bash
curl "http://localhost:8080/api/alerts/"
```

## 次のステップ

- フロントエンドダッシュボードでサイトを登録
- 定期クローリングのスケジュール設定
- アラート通知の設定 (SendGrid/Slack)
- フェイクサイト検出の設定

## 詳細ドキュメント

- [README.md](README.md) - 完全なドキュメント
- [docs/deployment.md](docs/deployment.md) - デプロイメントガイド
- API ドキュメント: http://localhost:8080/docs

## サポート

問題が発生した場合は、ログファイルを確認してください：

```bash
ls -la logs/
```

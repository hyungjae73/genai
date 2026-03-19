# ローカル環境セットアップ完了 ✅

Payment Compliance Monitorのローカル環境が正常にセットアップされ、起動しました。

## セットアップ完了項目

### インフラストラクチャ
- ✅ PostgreSQL 15 インストール・起動済み
- ✅ Redis インストール・起動済み
- ✅ データベース `payment_monitor` 作成済み
- ✅ データベースユーザー `payment_monitor` 作成済み

### アプリケーション
- ✅ Python 仮想環境作成済み (`venv/`)
- ✅ 全依存パッケージインストール済み
- ✅ Playwright Chromiumブラウザインストール済み
- ✅ Alembicマイグレーション実行済み

### 設定
- ✅ 環境変数ファイル (`.env`) 設定済み
  - APIポート: 8080
  - データベース接続: localhost
  - Redis接続: localhost
  - セキュリティキー生成済み
- ✅ フロントエンド環境変数設定済み
  - API URL: http://localhost:8080

### サービス起動
- ✅ FastAPI APIサーバー起動 (PID: 23071)
- ✅ Celery Worker起動 (PID: 23084)
- ✅ Celery Beat起動 (PID: 23100)
- ✅ React フロントエンド起動 (PID: 23109)

## アクセスURL

### API
- **Swagger UI (APIドキュメント)**: http://localhost:8080/docs
- **ReDoc (APIドキュメント)**: http://localhost:8080/redoc
- **ヘルスチェック**: http://localhost:8080/health

### フロントエンド
- **ダッシュボード**: http://localhost:5173

## 起動スクリプト

以下のスクリプトが作成されています：

```bash
# すべてのサービスを起動
./start_all.sh

# 個別起動
./start_api.sh              # FastAPI
./start_celery_worker.sh    # Celery Worker
./start_celery_beat.sh      # Celery Beat
./frontend/start_frontend.sh # React Frontend

# すべてのサービスを停止
./stop_all.sh
```

## ログファイル

ログは `logs/` ディレクトリに保存されています：

```bash
logs/api.log              # FastAPI
logs/celery_worker.log    # Celery Worker
logs/celery_beat.log      # Celery Beat
logs/frontend.log         # React Frontend
```

## 動作確認

### APIヘルスチェック
```bash
curl http://localhost:8080/health
# 出力: {"status":"healthy"}
```

### サイト一覧取得
```bash
curl http://localhost:8080/api/sites/
```

### Swagger UIでAPIテスト
ブラウザで http://localhost:8080/docs を開いて、各エンドポイントをテストできます。

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

## フロントエンドの使い方

1. ブラウザで http://localhost:5173 を開く
2. ダッシュボードでシステムの状態を確認
3. サイト管理画面でサイトを登録・管理
4. アラート画面でアラートを確認

## 機能一覧

### 実装済み機能

1. **サイト管理**
   - サイトの登録・更新・削除
   - 監視の有効化/無効化

2. **契約条件管理**
   - 契約条件の登録・更新
   - バージョン管理

3. **Webクローリング**
   - Playwright使用の高度なクローリング
   - JavaScript実行対応
   - レート制限

4. **コンテンツ分析**
   - 契約条件の変更検出
   - 差分計算
   - 類似度計算

5. **バリデーション**
   - 必須項目チェック
   - 禁止用語チェック
   - カスタムルール

6. **アラートシステム**
   - 優先度別アラート
   - Email通知 (SendGrid)
   - Slack通知

7. **フェイクサイト検出**
   - ドメイン類似度チェック
   - コンテンツ類似度チェック
   - 機械学習ベースの検出

8. **セキュリティ**
   - AES-256-GCM暗号化
   - JWT認証
   - bcryptパスワードハッシュ
   - 監査ログ

9. **スケジューリング**
   - 日次クローリング
   - 週次フェイクサイトスキャン
   - 月次データクリーンアップ

10. **React ダッシュボード**
    - リアルタイム監視
    - サイト管理UI
    - アラート管理UI

## テスト

### 全テスト実行
```bash
source venv/bin/activate
pytest
```

### カバレッジレポート
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### テスト結果
- 合計: 123テスト
- 成功: 123
- スキップ: 5
- カバレッジ: 74%

## トラブルシューティング

### サービスが起動しない

```bash
# PostgreSQL確認
brew services list | grep postgresql
pg_isready -h localhost -p 5432

# Redis確認
brew services list | grep redis
redis-cli ping

# ログ確認
tail -f logs/api.log
tail -f logs/celery_worker.log
```

### ポート競合

ポート8080が使用中の場合：

1. `.env` の `API_PORT` を変更
2. `start_api.sh` のポート番号を変更
3. `frontend/.env` の `VITE_API_BASE_URL` を変更

### データベースリセット

```bash
# データベース削除・再作成
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"
dropdb payment_monitor
createdb payment_monitor -O payment_monitor

# マイグレーション再実行
source venv/bin/activate
alembic upgrade head
```

## 次のステップ

1. **通知設定**
   - SendGrid APIキーを `.env` に設定
   - Slack Webhook URLを `.env` に設定

2. **本番デプロイ**
   - `docs/deployment.md` を参照
   - Docker Composeでのデプロイ
   - Nginx リバースプロキシ設定

3. **カスタマイズ**
   - バリデーションルールの追加
   - アラート条件のカスタマイズ
   - スケジュール設定の調整

## ドキュメント

- [QUICKSTART.md](QUICKSTART.md) - クイックスタートガイド
- [README.md](README.md) - 完全なドキュメント
- [docs/deployment.md](docs/deployment.md) - デプロイメントガイド
- API ドキュメント: http://localhost:8080/docs

## サポート

問題が発生した場合：

1. ログファイルを確認
2. サービスの状態を確認
3. データベース接続を確認
4. Redis接続を確認

---

**セットアップ完了日時**: 2026-03-07 02:33 JST

すべてのサービスが正常に起動しています。開発を開始できます！ 🚀

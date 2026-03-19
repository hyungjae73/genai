# Alembic Database Migrations

このディレクトリには、Payment Compliance Monitor システムのデータベーススキーママイグレーションが含まれています。

## セットアップ

Alembic は既に初期化されており、`alembic.ini` と `env.py` が設定されています。

## マイグレーションの実行

### データベースを最新バージョンにアップグレード

```bash
alembic upgrade head
```

### 特定のリビジョンにアップグレード

```bash
alembic upgrade <revision_id>
```

### 1つ前のバージョンにダウングレード

```bash
alembic downgrade -1
```

### 特定のリビジョンにダウングレード

```bash
alembic downgrade <revision_id>
```

### すべてのマイグレーションをロールバック

```bash
alembic downgrade base
```

## 新しいマイグレーションの作成

### 自動生成（モデルの変更を検出）

```bash
alembic revision --autogenerate -m "Description of changes"
```

### 手動作成

```bash
alembic revision -m "Description of changes"
```

## マイグレーション履歴の確認

### 現在のリビジョンを表示

```bash
alembic current
```

### マイグレーション履歴を表示

```bash
alembic history
```

### 詳細な履歴を表示

```bash
alembic history --verbose
```

## 環境変数

Alembic は `.env` ファイルから以下の環境変数を読み込みます：

- `DATABASE_URL`: PostgreSQL データベース接続文字列

例：
```
DATABASE_URL=postgresql+asyncpg://payment_monitor:payment_monitor_pass@postgres:5432/payment_monitor
```

**注意**: Alembic は `asyncpg` ではなく `psycopg2` を使用するため、`env.py` で自動的に URL を変換します。

## 初期マイグレーション

初期マイグレーション (`2a7009ae03db_initial_schema_creation.py`) には以下のテーブルが含まれています：

1. **monitoring_sites**: 監視対象サイト
2. **contract_conditions**: 契約条件（バージョン管理対応）
3. **crawl_results**: クローリング結果
4. **violations**: 違反検知結果
5. **alerts**: アラート通知

すべてのテーブルには適切なインデックスと外部キー制約が設定されています。

## トラブルシューティング

### データベースに接続できない

- Docker Compose でデータベースが起動していることを確認してください
- `.env` ファイルの `DATABASE_URL` が正しいことを確認してください
- ローカル開発の場合、ホスト名を `postgres` から `localhost` に変更する必要があるかもしれません

### マイグレーションが失敗する

- データベースの状態を確認してください: `alembic current`
- 必要に応じて、手動でデータベースをクリーンアップしてください
- 最初からやり直す場合: `alembic downgrade base` → `alembic upgrade head`

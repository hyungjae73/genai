# テストセットアップガイド

このドキュメントでは、Payment Compliance Monitor のテスト環境のセットアップ方法を説明します。

## 修正内容

### 1. Redis接続エラーの修正

**問題**: `redis.exceptions.ConnectionError: Error connecting to localhost:6379`

**解決策**: Docker ComposeでRedisコンテナを起動

```bash
docker-compose up -d redis
```

### 2. SQLite + JSONB型の非互換性の修正

**問題**: `sqlalchemy.exc.CompileError: Compiler can't render element of type JSONB`

**原因**: テストでSQLiteを使用していたが、modelsでPostgreSQL専用のJSONB型を使用

**解決策**: テスト用にPostgreSQLコンテナを使用

- `tests/test_crawler.py` を修正: SQLite → PostgreSQL
- `tests/test_models_properties.py` を修正: SQLite → PostgreSQL
- `tests/conftest.py` を作成: 共通のテスト設定
- `.env` にテスト用データベースURLを追加

### 3. 非推奨警告の修正

**問題**: `DeprecationWarning: Call to deprecated close. (Use aclose() instead)`

**解決策**: `src/crawler.py` の `close()` メソッドを修正

```python
# 修正前
await self._redis_client.close()

# 修正後
await self._redis_client.aclose()
```

## テスト環境のセットアップ

### 前提条件

- Docker と Docker Compose がインストールされていること
- Python 3.9+ がインストールされていること
- 仮想環境が有効化されていること

### セットアップ手順

#### 1. Docker コンテナを起動

```bash
# PostgreSQL と Redis を起動
docker-compose up -d postgres redis

# コンテナが起動したことを確認
docker-compose ps
```

#### 2. テスト用データベースをセットアップ

```bash
# セットアップスクリプトを実行
./setup_test_db.sh
```

または、手動でセットアップ:

```bash
# テストデータベースを作成
docker-compose exec postgres psql -U payment_monitor -d payment_monitor -c "CREATE DATABASE payment_monitor_test;"

# マイグレーションを実行
export DATABASE_URL="postgresql+asyncpg://payment_monitor:payment_monitor_pass@localhost:5432/payment_monitor_test"
alembic upgrade head
```

#### 3. テストを実行

```bash
# すべてのテストを実行
pytest tests/ -v

# 特定のテストファイルを実行
pytest tests/test_crawler.py -v
pytest tests/test_models_properties.py -v

# カバレッジレポート付きで実行
pytest tests/ -v --cov=src --cov-report=html
```

## テスト用データベース設定

### 環境変数

テストは以下の環境変数を使用します:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://payment_monitor:payment_monitor_pass@localhost:5432/payment_monitor_test
```

この設定は以下の場所で定義されています:
- `.env` ファイル
- `tests/conftest.py`

### データベース接続

テストは各テストファイルで以下のフィクスチャを使用します:

```python
@pytest.fixture
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
    )
    # テーブルを作成
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # テーブルを削除
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()
```

## トラブルシューティング

### PostgreSQL に接続できない

**症状**: `could not translate host name "postgres" to address`

**解決策**:
1. PostgreSQL コンテナが起動していることを確認
   ```bash
   docker-compose ps postgres
   ```

2. コンテナを再起動
   ```bash
   docker-compose restart postgres
   ```

3. ローカルから接続する場合は、ホスト名を `localhost` に変更
   ```bash
   export TEST_DATABASE_URL="postgresql+asyncpg://payment_monitor:payment_monitor_pass@localhost:5432/payment_monitor_test"
   ```

### Redis に接続できない

**症状**: `Error connecting to localhost:6379`

**解決策**:
1. Redis コンテナが起動していることを確認
   ```bash
   docker-compose ps redis
   ```

2. コンテナを再起動
   ```bash
   docker-compose restart redis
   ```

### テストデータベースが存在しない

**症状**: `database "payment_monitor_test" does not exist`

**解決策**:
```bash
docker-compose exec postgres psql -U payment_monitor -d payment_monitor -c "CREATE DATABASE payment_monitor_test;"
```

### マイグレーションエラー

**症状**: `Target database is not up to date`

**解決策**:
```bash
# テストデータベースにマイグレーションを適用
export DATABASE_URL="postgresql+asyncpg://payment_monitor:payment_monitor_pass@localhost:5432/payment_monitor_test"
alembic upgrade head
```

## CI/CD での実行

GitHub Actions や他の CI/CD 環境でテストを実行する場合:

```yaml
# .github/workflows/test.yml の例
services:
  postgres:
    image: postgres:15
    env:
      POSTGRES_USER: payment_monitor
      POSTGRES_PASSWORD: payment_monitor_pass
      POSTGRES_DB: payment_monitor
    ports:
      - 5432:5432
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
  
  redis:
    image: redis:7
    ports:
      - 6379:6379
    options: >-
      --health-cmd "redis-cli ping"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5

steps:
  - name: Run tests
    env:
      TEST_DATABASE_URL: postgresql+asyncpg://payment_monitor:payment_monitor_pass@localhost:5432/payment_monitor
    run: |
      pytest tests/ -v --cov=src
```

## 参考資料

- [pytest-asyncio ドキュメント](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy Async ドキュメント](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Hypothesis ドキュメント](https://hypothesis.readthedocs.io/)

# Database Migration Guide

このドキュメントは、Payment Compliance Monitor システムのデータベースマイグレーション管理について説明します。

## 概要

このプロジェクトでは、データベーススキーマのバージョン管理に **Alembic** を使用しています。Alembic は SQLAlchemy のマイグレーションツールで、データベーススキーマの変更を追跡し、適用・ロールバックすることができます。

## ディレクトリ構造

```
genai/
├── alembic/                    # Alembic マイグレーションディレクトリ
│   ├── versions/              # マイグレーションスクリプト
│   │   └── 2a7009ae03db_initial_schema_creation.py
│   ├── env.py                 # Alembic 環境設定
│   ├── script.py.mako         # マイグレーションテンプレート
│   └── README.md              # Alembic 使用方法
├── alembic.ini                # Alembic 設定ファイル
└── src/
    └── models.py              # SQLAlchemy モデル定義
```

## 初期セットアップ

### 1. Alembic の初期化（完了済み）

Alembic は既に初期化されており、以下の設定が完了しています：

- ✅ `alembic/` ディレクトリの作成
- ✅ `alembic.ini` 設定ファイルの作成
- ✅ `alembic/env.py` の設定（環境変数からのDB URL読み込み、モデルのインポート）
- ✅ 初期マイグレーションスクリプトの作成

### 2. 初期マイグレーションの内容

初期マイグレーション (`2a7009ae03db_initial_schema_creation.py`) には以下のテーブルが含まれています：

#### テーブル一覧

1. **monitoring_sites** - 監視対象サイト
   - id (PK)
   - company_name
   - domain (UNIQUE)
   - target_url
   - is_active
   - created_at

2. **contract_conditions** - 契約条件
   - id (PK)
   - site_id (FK → monitoring_sites)
   - version
   - prices (JSONB)
   - payment_methods (JSONB)
   - fees (JSONB)
   - subscription_terms (JSONB)
   - is_current
   - created_at

3. **crawl_results** - クローリング結果
   - id (PK)
   - site_id (FK → monitoring_sites)
   - url
   - html_content
   - status_code
   - crawled_at

4. **violations** - 違反検知結果
   - id (PK)
   - validation_result_id
   - violation_type
   - severity
   - field_name
   - expected_value (JSONB)
   - actual_value (JSONB)
   - detected_at

5. **alerts** - アラート通知
   - id (PK)
   - violation_id (FK → violations)
   - alert_type
   - severity
   - message
   - email_sent
   - slack_sent
   - created_at

#### インデックス

各テーブルには、パフォーマンス最適化のための適切なインデックスが設定されています：

- 外部キー列
- 検索頻度の高い列（domain, is_active, severity など）
- 複合インデックス（site_id + version, site_id + crawled_at など）

## マイグレーションの実行

### Docker 環境での実行

1. **データベースを起動**
   ```bash
   docker-compose up -d postgres
   ```

2. **マイグレーションを実行**
   ```bash
   # Docker コンテナ内で実行
   docker-compose exec api alembic upgrade head
   
   # または、ローカルから実行（データベースが起動している場合）
   alembic upgrade head
   ```

3. **マイグレーション状態を確認**
   ```bash
   docker-compose exec api alembic current
   ```

4. **データベースのテーブルを確認**
   ```bash
   docker-compose exec postgres psql -U payment_monitor -d payment_monitor -c '\dt'
   ```

### ローカル開発環境での実行

1. **データベースを起動**
   ```bash
   docker-compose up -d postgres
   ```

2. **環境変数を設定**
   ```bash
   # .env ファイルが正しく設定されていることを確認
   cat .env | grep DATABASE_URL
   ```

3. **マイグレーションを実行**
   ```bash
   alembic upgrade head
   ```

## マイグレーションの検証

マイグレーションが正しく設定されているか検証するには：

```bash
python verify_migration.py
```

このスクリプトは以下をチェックします：
- マイグレーションファイルの存在
- upgrade/downgrade 関数の存在
- 期待されるテーブルの定義
- 必要なインデックスの定義

## 新しいマイグレーションの作成

### モデルを変更した場合

1. **src/models.py でモデルを変更**

2. **自動生成でマイグレーションを作成**
   ```bash
   alembic revision --autogenerate -m "Add new column to monitoring_sites"
   ```

3. **生成されたマイグレーションを確認**
   ```bash
   # alembic/versions/ 内の新しいファイルを確認
   cat alembic/versions/<revision_id>_*.py
   ```

4. **必要に応じて手動で調整**
   - Alembic の自動生成は完璧ではないため、生成されたコードを確認
   - データ移行が必要な場合は手動で追加

5. **マイグレーションを適用**
   ```bash
   alembic upgrade head
   ```

### 手動でマイグレーションを作成する場合

```bash
alembic revision -m "Custom migration description"
```

生成されたファイルの `upgrade()` と `downgrade()` 関数を実装します。

## マイグレーションのロールバック

### 1つ前のバージョンに戻す

```bash
alembic downgrade -1
```

### 特定のリビジョンに戻す

```bash
alembic downgrade <revision_id>
```

### すべてのマイグレーションをロールバック

```bash
alembic downgrade base
```

## トラブルシューティング

### データベースに接続できない

**症状**: `could not translate host name "postgres" to address`

**解決方法**:
1. Docker Compose でデータベースが起動していることを確認
   ```bash
   docker-compose ps postgres
   ```

2. ローカル開発の場合、`.env` の `DATABASE_URL` を調整
   ```bash
   # Docker の場合
   DATABASE_URL=postgresql+asyncpg://payment_monitor:payment_monitor_pass@postgres:5432/payment_monitor
   
   # ローカルの場合
   DATABASE_URL=postgresql+asyncpg://payment_monitor:payment_monitor_pass@localhost:5432/payment_monitor
   ```

### マイグレーションの状態が不整合

**症状**: `Target database is not up to date`

**解決方法**:
1. 現在の状態を確認
   ```bash
   alembic current
   alembic history
   ```

2. データベースをリセット（開発環境のみ）
   ```bash
   alembic downgrade base
   alembic upgrade head
   ```

3. 本番環境では、手動で状態を修正
   ```bash
   alembic stamp <revision_id>
   ```

### 自動生成が期待通りに動作しない

**症状**: `alembic revision --autogenerate` が変更を検出しない

**解決方法**:
1. `alembic/env.py` で `target_metadata` が正しく設定されているか確認
2. モデルが正しくインポートされているか確認
3. 手動でマイグレーションを作成

## ベストプラクティス

### 1. マイグレーションは小さく保つ

- 1つのマイグレーションで1つの論理的な変更を行う
- 複数の変更がある場合は、複数のマイグレーションに分割

### 2. マイグレーションをテストする

```bash
# アップグレードをテスト
alembic upgrade head

# ダウングレードをテスト
alembic downgrade -1

# 再度アップグレード
alembic upgrade head
```

### 3. データ移行を含める

スキーマ変更だけでなく、必要なデータ移行も含める：

```python
def upgrade() -> None:
    # スキーマ変更
    op.add_column('monitoring_sites', sa.Column('status', sa.String(20)))
    
    # データ移行
    op.execute("UPDATE monitoring_sites SET status = 'active' WHERE is_active = true")
    op.execute("UPDATE monitoring_sites SET status = 'inactive' WHERE is_active = false")
```

### 4. 本番環境での注意事項

- マイグレーション前にデータベースをバックアップ
- ダウンタイムが必要な場合は、メンテナンスウィンドウを設定
- 大規模なテーブルの変更は、段階的に実行
- ロールバック計画を準備

## 参考資料

- [Alembic 公式ドキュメント](https://alembic.sqlalchemy.org/)
- [SQLAlchemy ドキュメント](https://docs.sqlalchemy.org/)
- プロジェクトの `alembic/README.md` - 基本的な使用方法
- プロジェクトの `src/models.py` - データモデル定義

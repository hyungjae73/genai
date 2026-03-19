# Alembic セットアップ完了サマリー

## 実施内容

タスク 2.3「Alembic マイグレーションスクリプトを作成」を完了しました。

### 1. Alembic の初期化

```bash
alembic init alembic
```

以下のディレクトリとファイルが作成されました：
- `alembic/` - マイグレーションディレクトリ
- `alembic/versions/` - マイグレーションスクリプト格納ディレクトリ
- `alembic/env.py` - Alembic 環境設定
- `alembic/script.py.mako` - マイグレーションテンプレート
- `alembic.ini` - Alembic 設定ファイル

### 2. Alembic の設定

#### alembic.ini の変更
- データベース URL を環境変数から読み込むように設定
- コメントアウト: `# sqlalchemy.url = driver://user:pass@localhost/dbname`

#### alembic/env.py の変更
- 環境変数の読み込み（`python-dotenv` 使用）
- SQLAlchemy モデルのインポート（`from src.models import Base`）
- `target_metadata = Base.metadata` の設定（autogenerate サポート）
- データベース URL の変換（`postgresql+asyncpg://` → `postgresql://`）

### 3. 初期マイグレーションスクリプトの作成

ファイル: `alembic/versions/2a7009ae03db_initial_schema_creation.py`

#### 作成されるテーブル

1. **monitoring_sites** - 監視対象サイト
   - 主キー、ユニーク制約（domain）
   - インデックス: domain, is_active

2. **contract_conditions** - 契約条件
   - 外部キー: site_id → monitoring_sites.id
   - JSONB カラム: prices, payment_methods, fees, subscription_terms
   - インデックス: site_id, is_current, (site_id, version)

3. **crawl_results** - クローリング結果
   - 外部キー: site_id → monitoring_sites.id
   - インデックス: site_id, crawled_at, (site_id, crawled_at)

4. **violations** - 違反検知結果
   - JSONB カラム: expected_value, actual_value
   - インデックス: validation_result_id, detected_at, severity, violation_type

5. **alerts** - アラート通知
   - 外部キー: violation_id → violations.id
   - インデックス: violation_id, created_at, severity, alert_type

#### 特徴
- すべてのテーブルに適切なインデックスを設定
- 外部キー制約を設定
- デフォルト値とサーバーサイドデフォルトを設定
- 完全な `upgrade()` と `downgrade()` 関数を実装

### 4. ドキュメントの作成

以下のドキュメントを作成しました：

1. **alembic/README.md**
   - Alembic の基本的な使用方法
   - マイグレーションコマンドのリファレンス
   - トラブルシューティング

2. **MIGRATION_GUIDE.md**
   - 包括的なマイグレーションガイド
   - 初期セットアップの説明
   - マイグレーションの実行方法
   - 新しいマイグレーションの作成方法
   - ベストプラクティス

3. **verify_migration.py**
   - マイグレーション検証スクリプト
   - テーブルとインデックスの存在確認
   - 次のステップの表示

### 5. 検証結果

```bash
python verify_migration.py
```

✅ すべての検証チェックに合格：
- マイグレーションファイルの存在
- upgrade/downgrade 関数の存在
- 5つのテーブルすべての定義
- 必要なインデックスの定義

## 使用方法

### マイグレーションの実行

```bash
# データベースを起動
docker-compose up -d postgres

# マイグレーションを適用
alembic upgrade head

# 状態を確認
alembic current
```

### マイグレーション履歴の確認

```bash
alembic history
```

出力:
```
<base> -> 2a7009ae03db (head), Initial schema creation
```

### データベースの確認

```bash
docker-compose exec postgres psql -U payment_monitor -d payment_monitor -c '\dt'
```

## 次のステップ

1. Docker Compose でデータベースを起動
2. マイグレーションを実行して、スキーマを作成
3. 次のタスク（クローリングエンジンの実装）に進む

## 関連ファイル

- `alembic.ini` - Alembic 設定
- `alembic/env.py` - 環境設定
- `alembic/versions/2a7009ae03db_initial_schema_creation.py` - 初期マイグレーション
- `alembic/README.md` - 基本的な使用方法
- `MIGRATION_GUIDE.md` - 包括的なガイド
- `verify_migration.py` - 検証スクリプト
- `src/models.py` - SQLAlchemy モデル定義

## 要件の充足

このタスクは以下の要件を満たしています：

- **Requirements 6.1**: データベースにクローリング結果をタイムスタンプ付きで保存
- データベーススキーマのバージョン管理
- マイグレーションの適用とロールバック機能
- 開発・本番環境での使用に対応

## 完了確認

✅ Alembic の初期化完了
✅ 環境設定の完了
✅ 初期マイグレーションスクリプトの作成完了
✅ ドキュメントの作成完了
✅ 検証スクリプトの作成と実行完了

タスク 2.3 は正常に完了しました。

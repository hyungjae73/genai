# 要件定義書: testcontainers-migration

## はじめに

バックエンドテストのデータベースをSQLiteインメモリDBからtestcontainers-python（PostgreSQL）へ移行する。現在446件のバックエンドテストがSQLiteで実行されているが、本番環境のPostgreSQLとの差異（JSONB→JSON型の妥協、server_defaultの動作差異、インデックス動作差異、タイムスタンプ精度差異）により、テストの信頼性が低下している。testcontainers-pythonを導入し、本番同等のPostgreSQL 15上で全テストを実行可能にする。

## 用語集

- **TestRunner**: pytestベースのテスト実行システム（conftest.py、フィクスチャ、テストファイル群を含む）
- **PostgresContainer**: testcontainers-pythonが提供するPostgreSQLコンテナ管理クラス（postgres:15-alpineイメージを使用）
- **TestSession**: pytestのセッションスコープで管理されるテスト実行単位（全テストスイートの1回の実行）
- **TestCase**: 個別のテスト関数（pytest関数単位）
- **ModelDefinition**: genai/src/models.pyに定義されたSQLAlchemyモデル群
- **CIWorkflow**: GitHub Actionsで実行されるCI/CDパイプライン（genai/.github/workflows/pr.yml）
- **AlembicMigration**: Alembicによるデータベーススキーママイグレーション
- **TransactionRollback**: テスト間のデータ分離を実現するトランザクションロールバック機構

## 要件

### 要件1: PostgreSQLテストコンテナの導入

**ユーザーストーリー:** 開発者として、テスト実行時にtestcontainers-pythonで自動的にPostgreSQLコンテナが起動されるようにしたい。本番同等のデータベースでテストを実行し、SQLiteとの動作差異に起因するバグを防止するため。

#### 受入基準

1. WHEN TestSessionが開始された時、THE TestRunnerはPostgresContainer（postgres:15-alpineイメージ）を起動しなければならない（SHALL）
2. WHEN PostgresContainerが起動完了した時、THE TestRunnerはSQLAlchemyエンジンをPostgreSQLの接続URLで構成しなければならない（SHALL）
3. WHEN TestSessionが終了した時、THE TestRunnerはPostgresContainerを停止・削除しなければならない（SHALL）
4. THE PostgresContainerはセッションスコープ（1回のテストスイート実行につき1コンテナ）で管理されなければならない（SHALL）
5. WHEN PostgresContainerの起動が完了した時、THE TestRunnerはBase.metadata.create_all()を実行してスキーマを作成しなければならない（SHALL）

### 要件2: テスト間のデータ分離

**ユーザーストーリー:** 開発者として、各テストが独立して実行され、他のテストのデータに影響されないようにしたい。テスト結果の再現性と信頼性を確保するため。

#### 受入基準

1. WHEN 各TestCaseが開始された時、THE TestRunnerは新しいデータベーストランザクションを開始しなければならない（SHALL）
2. WHEN 各TestCaseが終了した時、THE TestRunnerはTransactionRollbackを実行してデータベースを元の状態に戻さなければならない（SHALL）
3. THE TestRunnerは全446件のTestCase間でデータ漏洩が発生しないことを保証しなければならない（SHALL）
4. WHILE TransactionRollbackが有効な間、THE TestRunnerはネストされたトランザクション（SAVEPOINT）をサポートしなければならない（SHALL）

### 要件3: JSONB型の復元

**ユーザーストーリー:** 開発者として、SQLite互換のために妥協していたJSON型をPostgreSQLネイティブのJSONB型に復元したい。JSONB固有のクエリ機能（インデックス、演算子）を活用できるようにするため。

#### 受入基準

1. THE ModelDefinitionはMonitoringSiteモデルのpre_capture_scriptフィールドをJSONBに変更しなければならない（SHALL）
2. THE ModelDefinitionはMonitoringSiteモデルのplugin_configフィールドをJSONBに変更しなければならない（SHALL）
3. THE ModelDefinitionはVerificationResultモデルのstructured_dataフィールドをJSONBに変更しなければならない（SHALL）
4. THE ModelDefinitionはVerificationResultモデルのstructured_data_violationsフィールドをJSONBに変更しなければならない（SHALL）
5. WHEN JSONB型に変更された後、THE TestRunnerは全446件のテストがPostgreSQL上で正常に動作することを検証しなければならない（SHALL）
6. THE ModelDefinitionはJSONB型を使用するフィールドでPostgreSQL固有のJSONBインポート（sqlalchemy.dialects.postgresql.JSONB）を使用しなければならない（SHALL）

### 要件4: conftest.pyの移行

**ユーザーストーリー:** 開発者として、テスト設定ファイル（conftest.py）をtestcontainers-python対応に更新したい。全テストファイルが統一されたPostgreSQLフィクスチャを使用できるようにするため。

#### 受入基準

1. THE TestRunnerはgenai/tests/conftest.pyにセッションスコープのPostgresContainerフィクスチャを定義しなければならない（SHALL）
2. THE TestRunnerはgenai/tests/conftest.pyに関数スコープのdb_sessionフィクスチャ（TransactionRollback付き）を定義しなければならない（SHALL）
3. THE TestRunnerはgenai/tests/conftest.pyにFastAPI依存関係のオーバーライド用clientフィクスチャを定義しなければならない（SHALL）
4. WHEN 個別テストファイルがローカルにdb_sessionフィクスチャを定義している場合、THE TestRunnerは共通のconftest.pyフィクスチャを使用するように統一しなければならない（SHALL）
5. THE TestRunnerはSQLiteインメモリDBへの参照をconftest.pyから削除しなければならない（SHALL）

### 要件5: CI/CDパイプラインの更新

**ユーザーストーリー:** 開発者として、GitHub ActionsのCIワークフローがtestcontainersベースのテストを正しく実行できるようにしたい。PRごとに自動テストが本番同等のPostgreSQLで実行されるようにするため。

#### 受入基準

1. THE CIWorkflowはGitHub Actionsランナー上でDockerが利用可能であることを前提としなければならない（SHALL）
2. WHEN testcontainersがPostgresContainerを起動する時、THE CIWorkflowはservicesセクションのpostgresサービス定義を削除しなければならない（SHALL）
3. THE CIWorkflowはtestcontainersが自動的にPostgreSQLコンテナを管理するため、DATABASE_URL環境変数の手動設定を削除しなければならない（SHALL）
4. THE CIWorkflowはpip install時にtestcontainers[postgres]パッケージをインストールしなければならない（SHALL）

### 要件6: 依存パッケージの更新

**ユーザーストーリー:** 開発者として、testcontainers-pythonとその依存パッケージがrequirements.txtに追加されるようにしたい。開発環境とCI環境で一貫した依存関係を維持するため。

#### 受入基準

1. THE TestRunnerはgenai/requirements.txtにtestcontainers[postgres]パッケージを追加しなければならない（SHALL）
2. THE TestRunnerはgenai/requirements.txtにaiosqliteパッケージへの依存がある場合、テスト用途としての参照を削除しなければならない（SHALL）
3. THE TestRunnerはpsycopg2-binary（既存インストール済み）がrequirements.txtに含まれていることを確認しなければならない（SHALL）

### 要件7: Alembicマイグレーションの検証

**ユーザーストーリー:** 開発者として、AlembicマイグレーションがPostgreSQLコンテナ上で正しく動作することを検証したい。本番デプロイ前にマイグレーションの問題を検出するため。

#### 受入基準

1. WHEN テストスイートが実行される時、THE TestRunnerはAlembicMigrationをPostgresContainer上で実行して検証するオプションを提供しなければならない（SHALL）
2. IF AlembicMigrationが失敗した場合、THEN THE TestRunnerは明確なエラーメッセージとともにテストを中断しなければならない（SHALL）
3. THE TestRunnerはAlembicのupgrade headコマンドがPostgresContainer上で正常に完了することを検証しなければならない（SHALL）

### 要件8: テスト実行パフォーマンス

**ユーザーストーリー:** 開発者として、testcontainersへの移行後もテスト実行時間が許容範囲内に収まるようにしたい。開発サイクルの速度を維持するため。

#### 受入基準

1. THE TestRunnerは全446件のバックエンドテストを120秒以内に完了しなければならない（SHALL）（現在SQLiteで約80秒）
2. THE PostgresContainerはセッションスコープで1回のみ起動され、全テスト間で再利用されなければならない（SHALL）
3. THE TestRunnerはTransactionRollbackによるテスト間クリーンアップを使用し、テーブルの再作成を回避しなければならない（SHALL）

### 要件9: Docker未利用環境でのフォールバック

**ユーザーストーリー:** 開発者として、Dockerが利用できない軽量CI環境やローカル環境でもテストが適切にスキップされるようにしたい。環境に依存しないテスト実行を可能にするため。

#### 受入基準

1. IF Dockerが利用できない環境でテストが実行された場合、THEN THE TestRunnerはDB依存テストをpytest.mark.skipifでスキップしなければならない（SHALL）
2. WHEN DB依存テストがスキップされた時、THE TestRunnerはスキップ理由として「Docker is not available」を表示しなければならない（SHALL）
3. THE TestRunnerはDockerの利用可否をテストセッション開始時に1回だけ判定しなければならない（SHALL）

### 要件10: 既存テストの互換性保証

**ユーザーストーリー:** 開発者として、移行後に全446件の既存テストが変更なしまたは最小限の変更で動作することを確認したい。移行によるリグレッションを防止するため。

#### 受入基準

1. THE TestRunnerは移行後に全446件のバックエンドテストがパスすることを検証しなければならない（SHALL）
2. WHEN テストがSQLite固有の動作に依存している場合、THE TestRunnerはPostgreSQL互換の動作に修正しなければならない（SHALL）
3. THE TestRunnerはserver_defaultの動作差異（SQLiteではPython側default、PostgreSQLではDB側default）を正しく処理しなければならない（SHALL）
4. THE TestRunnerはタイムスタンプ精度の差異（SQLiteの秒精度 vs PostgreSQLのマイクロ秒精度）を正しく処理しなければならない（SHALL）
5. THE TestRunnerはインデックス動作の差異（SQLiteの部分インデックス制限）を正しく処理しなければならない（SHALL）

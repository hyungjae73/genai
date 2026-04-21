# 要件定義書

## はじめに

Payment Compliance Monitorの全サービス（PostgreSQL、Redis、FastAPI API、Celery Worker、Celery Beat、React Frontend）をDockerベースで統一的に管理し、CI/CDパイプラインを通じてパブリッククラウド（AWS、GCPなど）へ自動デプロイできるようにする。現在のローカル開発環境はhomebrewベースのPostgreSQLとRedisに依存しているが、Docker Composeによる完全コンテナ化された開発環境へ移行し、本番環境との一貫性を確保する。

## 用語集

- **Pipeline**: GitHub ActionsなどのCI/CDサービス上で実行される自動化されたビルド・テスト・デプロイのワークフロー
- **Container_Registry**: Dockerイメージを保存・配布するためのレジストリサービス（例: Amazon ECR、Google Artifact Registry、GitHub Container Registry）
- **Build_System**: Dockerイメージのビルド、タグ付け、プッシュを行うシステム
- **Orchestrator**: Docker Composeまたはクラウド上のコンテナオーケストレーションサービス（ECS、Cloud Runなど）
- **Health_Check**: サービスの正常稼働を確認するためのエンドポイントまたはコマンド
- **Environment_Manager**: 環境変数と設定ファイルを環境ごと（開発・ステージング・本番）に管理するシステム
- **Migration_Runner**: Alembicを使用してデータベースマイグレーションを実行するプロセス
- **Test_Runner**: 自動テスト（ユニットテスト、統合テスト）を実行するプロセス
- **Image_Tag**: Dockerイメージに付与されるバージョン識別子（gitコミットハッシュ、セマンティックバージョンなど）

## 要件

### 要件 1: Docker化された開発環境の統一

**ユーザーストーリー:** 開発者として、全サービスをDockerベースで起動したい。それにより、homebrewのローカルサービスとの競合を排除し、チーム全体で一貫した開発環境を実現できる。

#### 受け入れ基準

1. WHEN `docker compose up` コマンドが実行された場合、THE Orchestrator SHALL PostgreSQL、Redis、API、Celery Worker、Celery Beat、Frontendの全6サービスを起動する
2. WHILE 全サービスが起動中の状態で、THE Health_Check SHALL 各サービスの正常稼働を確認可能にする
3. WHEN 開発者がソースコードを変更した場合、THE Orchestrator SHALL ホットリロードにより変更をコンテナ内に即座に反映する
4. THE Orchestrator SHALL ローカルのhomebrew PostgreSQL（ポート5432）およびRedis（ポート6379）と競合しないよう、設定可能なポートマッピングを提供する
5. IF Docker Composeの起動中にサービスが異常終了した場合、THEN THE Orchestrator SHALL エラーログを出力し、依存サービスの起動順序を維持する

### 要件 2: 本番用Dockerイメージのビルド

**ユーザーストーリー:** DevOpsエンジニアとして、本番環境向けに最適化されたDockerイメージをビルドしたい。それにより、セキュリティとパフォーマンスを確保した状態でデプロイできる。

#### 受け入れ基準

1. THE Build_System SHALL バックエンド（API/Celery）用のマルチステージDockerfileを使用して、最終イメージにビルドツールを含めない
2. THE Build_System SHALL フロントエンド用のマルチステージDockerfileを使用して、ビルド済み静的ファイルをNginxで配信する本番イメージを生成する
3. THE Build_System SHALL 非rootユーザーでアプリケーションプロセスを実行する
4. WHEN 本番イメージがビルドされた場合、THE Build_System SHALL 開発用の依存関係（テストライブラリ、デバッグツール）を最終イメージに含めない
5. THE Build_System SHALL Dockerレイヤーキャッシュを活用して、依存関係に変更がない場合のビルド時間を短縮する

### 要件 3: 環境別設定管理

**ユーザーストーリー:** DevOpsエンジニアとして、開発・ステージング・本番の各環境に応じた設定を管理したい。それにより、環境ごとに適切な設定でサービスを動作させることができる。

#### 受け入れ基準

1. THE Environment_Manager SHALL 開発（development）、ステージング（staging）、本番（production）の3環境向けの設定テンプレートを提供する
2. THE Environment_Manager SHALL シークレット情報（データベースパスワード、APIキー、暗号化キー）を環境変数として外部から注入可能にする
3. WHEN 本番環境で起動した場合、THE Environment_Manager SHALL DEBUG=falseを強制し、デバッグ用エンドポイントを無効化する
4. THE Environment_Manager SHALL 各環境のDocker Compose設定をオーバーライドファイル（docker-compose.override.yml、docker-compose.prod.yml）で管理する
5. IF 必須の環境変数が未設定の場合、THEN THE Environment_Manager SHALL サービス起動前にエラーメッセージを出力して起動を中止する

### 要件 4: CI/CDパイプラインの構築

**ユーザーストーリー:** 開発チームとして、コードの変更がプッシュされた際に自動でテスト・ビルド・デプロイが実行されるCI/CDパイプラインを構築したい。それにより、手動デプロイのリスクと工数を削減できる。

#### 受け入れ基準

1. WHEN コードがmainブランチにプッシュされた場合、THE Pipeline SHALL 自動的にテスト、ビルド、デプロイのワークフローを実行する
2. WHEN プルリクエストが作成された場合、THE Pipeline SHALL 自動テスト（ユニットテスト、リンター）を実行し、結果をプルリクエストに報告する
3. THE Pipeline SHALL バックエンドとフロントエンドのDockerイメージをビルドし、Container_Registryにプッシュする
4. THE Pipeline SHALL Image_Tagとしてgitコミットハッシュとセマンティックバージョンの両方をサポートする
5. IF パイプラインのいずれかのステージが失敗した場合、THEN THE Pipeline SHALL 後続のステージを実行せず、失敗通知を送信する
6. THE Pipeline SHALL パイプラインの実行時間を最小化するため、依存関係のキャッシュとDockerレイヤーキャッシュを活用する

### 要件 5: 自動テストの統合

**ユーザーストーリー:** 開発者として、CI/CDパイプライン内で自動テストが実行されることを保証したい。それにより、品質を維持しながら迅速にデプロイできる。

#### 受け入れ基準

1. THE Test_Runner SHALL パイプライン内でPythonバックエンドのユニットテストをpytestで実行する
2. THE Test_Runner SHALL パイプライン内でReactフロントエンドのテストを実行する
3. THE Test_Runner SHALL テスト実行時にPostgreSQLとRedisのサービスコンテナを自動的に起動する
4. WHEN テストが失敗した場合、THE Test_Runner SHALL 失敗したテストの詳細とログをパイプラインの出力に含める
5. THE Test_Runner SHALL テストカバレッジレポートを生成し、パイプラインのアーティファクトとして保存する

### 要件 6: データベースマイグレーションの自動化

**ユーザーストーリー:** DevOpsエンジニアとして、デプロイ時にデータベースマイグレーションが自動的に実行されるようにしたい。それにより、スキーマ変更の適用漏れを防止できる。

#### 受け入れ基準

1. WHEN デプロイが実行された場合、THE Migration_Runner SHALL アプリケーション起動前にAlembicマイグレーションを自動実行する
2. IF マイグレーションが失敗した場合、THEN THE Migration_Runner SHALL デプロイを中止し、エラー詳細をログに出力する
3. THE Migration_Runner SHALL マイグレーション実行前にデータベース接続の確認を行う
4. THE Migration_Runner SHALL マイグレーションの実行状態（成功・失敗・スキップ）をログに記録する

### 要件 7: コンテナレジストリ管理

**ユーザーストーリー:** DevOpsエンジニアとして、ビルドされたDockerイメージをコンテナレジストリに安全に保存・管理したい。それにより、デプロイ時に信頼性の高いイメージを取得できる。

#### 受け入れ基準

1. THE Build_System SHALL ビルドされたイメージをContainer_Registryにプッシュする
2. THE Build_System SHALL 各イメージにgitコミットハッシュベースのタグとlatestタグを付与する
3. WHEN mainブランチからビルドされた場合、THE Build_System SHALL イメージにstableタグを追加で付与する
4. THE Container_Registry SHALL 認証情報をCI/CDパイプラインのシークレットとして安全に管理する

### 要件 8: ヘルスチェックとモニタリング対応

**ユーザーストーリー:** 運用担当者として、デプロイされたサービスの稼働状態を監視したい。それにより、障害を早期に検知し対応できる。

#### 受け入れ基準

1. THE Health_Check SHALL FastAPI APIに `/health` エンドポイントを提供し、データベースとRedisの接続状態を含むヘルスステータスを返す
2. THE Health_Check SHALL Docker Composeの各サービスにヘルスチェック設定を含める
3. WHEN ヘルスチェックが失敗した場合、THE Orchestrator SHALL コンテナの再起動ポリシーに従ってサービスを再起動する
4. THE Health_Check SHALL ヘルスチェックレスポンスにサービスバージョン情報（Image_Tag）を含める

### 要件 9: セキュリティ対策

**ユーザーストーリー:** セキュリティ担当者として、コンテナとCI/CDパイプラインのセキュリティを確保したい。それにより、脆弱性やシークレット漏洩のリスクを最小化できる。

#### 受け入れ基準

1. THE Build_System SHALL Dockerイメージのベースイメージとして公式の最小イメージ（alpine、slim）を使用する
2. THE Pipeline SHALL シークレット情報をソースコードやDockerイメージに含めない
3. THE Build_System SHALL `.dockerignore` ファイルにより、`.env`ファイル、`.git`ディレクトリ、テストファイルを本番イメージから除外する
4. WHEN Dockerイメージがビルドされた場合、THE Build_System SHALL 既知の脆弱性がないことを確認するためのセキュリティスキャンステップをパイプラインに含める
5. THE Environment_Manager SHALL 本番環境でDEBUGモードが有効にならないよう制御する

### 要件 10: エラーコード体系と構造化ログ

**ユーザーストーリー:** 運用担当者として、エラー発生時に原因を迅速に特定したい。それにより、障害対応時間を短縮し、適切なロールバック判断ができる。

#### 受け入れ基準

1. THE Environment_Manager SHALL 全エラーをカテゴリ別のエラーコード（PCM-E{カテゴリ}{番号}）で分類し、ログに出力する
2. THE Environment_Manager SHALL エラーログにタイムスタンプ、エラーコード、サービス名、バージョン、環境名を含む構造化JSON形式で出力する
3. WHEN エントリポイントスクリプトでエラーが発生した場合、THE Environment_Manager SHALL 対応するエラーコードを構造化ログとして出力する
4. THE Health_Check SHALL ヘルスチェック失敗時に対応するエラーコードをレスポンスに含める

### 要件 11: デプロイのロールバック・切り戻し

**ユーザーストーリー:** DevOpsエンジニアとして、デプロイ後に問題が発生した場合に前のバージョンに迅速に切り戻したい。それにより、障害の影響範囲と時間を最小化できる。

#### 受け入れ基準

1. THE Orchestrator SHALL ECSデプロイ時にCircuit Breakerを有効にし、新タスクのヘルスチェック失敗時に自動的に前バージョンにロールバックする
2. THE Pipeline SHALL GitHub Actionsのworkflow_dispatchにより、任意のサービスを指定したイメージタグに手動で切り戻せるロールバックワークフローを提供する
3. WHEN マイグレーションが失敗した場合、THE Migration_Runner SHALL 前のAlembicリビジョンへの自動ダウングレードを試行する
4. THE Orchestrator SHALL ローリングアップデート方式を採用し、新タスクが正常になるまで旧タスクを停止しない（minimumHealthyPercent: 100）
5. THE Pipeline SHALL ロールバックワークフローで対象サービス（api, celery-worker, celery-beat, frontend, all）と切り戻し先イメージタグを選択可能にする

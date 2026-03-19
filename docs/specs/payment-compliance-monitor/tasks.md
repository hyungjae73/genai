# Implementation Plan: Payment Compliance Monitor

## Overview

このタスクリストは、決済条件監視・検証システムを段階的に実装するためのものです。各タスクは前のタスクの成果物を基に構築され、最終的に完全に統合されたシステムを形成します。

## Current Status

プロジェクトは初期段階です。`genai/` ディレクトリが存在し、`.env` ファイルが作成されていますが、実装コードはまだありません。以下のタスクリストは、要件と設計に基づいて完全なシステムを構築するためのものです。

## Tasks

- [x] 1. プロジェクト構造とDocker環境のセットアップ
  - プロジェクトディレクトリ構造を作成（genai/src/, genai/tests/, genai/docker/）
  - Docker Compose設定ファイルを作成（FastAPI, PostgreSQL, Redis, Celery Worker, Celery Beat）
  - requirements.txtに依存パッケージを定義（FastAPI, Playwright, SQLAlchemy, Celery, pytest, Hypothesis）
  - 環境変数設定ファイル（.env.example）を作成し、既存の.envを更新
  - _Requirements: 10.1, 10.2_

- [ ] 2. データベーススキーマとモデルの実装
  - [x] 2.1 SQLAlchemy モデルクラスを実装
    - genai/src/models.py を作成
    - MonitoringSite, ContractCondition, CrawlResult, Violation, Alert モデルを作成
    - リレーションシップとインデックスを定義
    - _Requirements: 6.1, 6.2, 6.3, 7.1_
  
  - [x] 2.2 データモデルのプロパティテストを実装
    - genai/tests/test_models_properties.py を作成
    - **Property: Contract versioning**
    - **Validates: Requirements 7.2**
  
  - [x] 2.3 Alembic マイグレーションスクリプトを作成
    - Alembic を初期化（genai/alembic/）
    - 初期スキーマ作成マイグレーション
    - _Requirements: 6.1_

- [ ] 3. クローリングエンジンの実装
  - [x] 3.1 CrawlerEngine クラスを実装
    - genai/src/crawler.py を作成
    - Playwright を使用した非同期クローリング機能
    - robots.txt チェック機能
    - レート制限機能（Redis使用）
    - リトライロジック（exponential backoff）
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  
  - [x] 3.2 クローリングエンジンのプロパティテストを実装
    - genai/tests/test_crawler_properties.py を作成
    - **Property 2: Rate limit compliance**
    - **Validates: Requirements 1.3, 9.3**
  
  - [x] 3.3 クローリングエンジンのプロパティテストを実装
    - **Property 3: Robots.txt compliance**
    - **Validates: Requirements 1.4, 9.4**
  
  - [x] 3.4 クローリングエンジンのプロパティテストを実装
    - **Property 4: Retry with exponential backoff**
    - **Validates: Requirements 1.5**
  
  - [x] 3.5 クローリングエンジンのプロパティテストを実装
    - **Property 5: Crawl result persistence**
    - **Validates: Requirements 1.6**

- [ ] 4. コンテンツ解析エンジンの実装
  - [x] 4.1 ContentAnalyzer クラスを実装
    - genai/src/analyzer.py を作成
    - BeautifulSoup4 を使用したHTML解析
    - 価格抽出機能（正規表現パターンマッチング）
    - 決済方法抽出機能（キーワードマッチング）
    - 手数料抽出機能
    - 定期縛り条件抽出機能
    - PaymentInfo データクラスへの構造化
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_
  
  - [x] 4.2 コンテンツ解析エンジンのユニットテストを実装
    - genai/tests/test_analyzer.py を作成
    - 価格抽出のテスト
    - 決済方法抽出のテスト
    - エッジケースのテスト
    - _Requirements: 2.1, 2.2_

- [ ] 5. 検証エンジンの実装
  - [x] 5.1 ValidationEngine クラスを実装
    - genai/src/validator.py を作成
    - 価格検証機能（許容誤差範囲対応）
    - 決済方法検証機能
    - 手数料検証機能
    - 定期縛り条件検証機能
    - Violation オブジェクト生成機能
    - ValidationResult データクラスへの構造化
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_
  
  - [x] 5.2 検証エンジンのプロパティテストを実装
    - genai/tests/test_validator_properties.py を作成
    - **Property 6: Contract condition violation detection**
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.5**
  
  - [x] 5.3 検証エンジンのプロパティテストを実装
    - **Property 7: Validation result persistence**
    - **Validates: Requirements 3.6**
  
  - [x] 5.4 検証エンジンのプロパティテストを実装
    - **Property 8: Alert triggering on violation**
    - **Validates: Requirements 3.7**

- [x] 6. Checkpoint - コア機能の統合テスト
  - クローリング → 解析 → 検証のワークフローが正常に動作することを確認
  - すべてのテストがパスすることを確認
  - ユーザーに質問があれば確認

- [x] 7. 擬似サイト検出エンジンの実装
  - [x] 7.1 FakeSiteDetector クラスを実装
    - genai/src/fake_detector.py を作成
    - Levenshtein距離によるドメイン類似度計算
    - TF-IDFによるコンテンツ類似度計算
    - 類似ドメインスキャン機能
    - 擬似サイト検証機能
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_
  
  - [x] 7.2 擬似サイト検出エンジンのプロパティテストを実装
    - genai/tests/test_fake_detector_properties.py を作成
    - **Property 9: Domain similarity calculation**
    - **Validates: Requirements 4.2**

- [x] 8. アラートシステムの実装
  - [x] 8.1 AlertSystem クラスを実装
    - genai/src/alert_system.py を作成
    - SendGrid API統合（メール送信）
    - Slack SDK統合（Slack通知）
    - Jinja2テンプレートエンジン統合
    - リトライロジック（exponential backoff）
    - アラート優先度処理
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_
  
  - [x] 8.2 アラートシステムのユニットテストを実装
    - genai/tests/test_alert_system.py を作成
    - メール送信のテスト（モック使用）
    - Slack通知のテスト（モック使用）
    - リトライロジックのテスト
    - _Requirements: 5.1, 5.2, 5.6_

- [x] 9. Celeryタスクとスケジューラの実装
  - [x] 9.1 Celeryタスクを実装
    - genai/src/tasks.py を作成
    - genai/src/celery_app.py を作成（Celery設定）
    - crawl_and_validate_site タスク（クローリング → 解析 → 検証 → アラート）
    - scan_fake_sites タスク（擬似サイトスキャン）
    - cleanup_old_data タスク（古いデータのクリーンアップ）
    - _Requirements: 1.1, 4.1, 6.5_
  
  - [x] 9.2 Celery Beat スケジュール設定
    - 日次クローリングスケジュール（毎日午前2時）
    - 週次擬似サイトスキャン（毎週月曜午前3時）
    - 月次データクリーンアップ（毎月1日午前4時）
    - _Requirements: 1.1, 4.1_
  
  - [x] 9.3 スケジューラのプロパティテストを実装
    - genai/tests/test_scheduler_properties.py を作成
    - **Property 1: Daily crawling execution**
    - **Validates: Requirements 1.1**

- [x] 10. Management API の実装
  - [x] 10.1 FastAPI アプリケーションとルーターを作成
    - genai/src/main.py を作成（FastAPIアプリケーション）
    - genai/src/api/ ディレクトリを作成
    - JWT認証ミドルウェア
    - Pydantic スキーマ定義（リクエスト/レスポンス）
    - エラーハンドリングミドルウェア
    - _Requirements: 7.6, 9.5_
  
  - [x] 10.2 契約条件管理エンドポイントを実装
    - genai/src/api/contracts.py を作成
    - POST /contracts（契約作成）
    - PUT /contracts/{id}（契約更新）
    - GET /contracts/{id}（契約取得）
    - DELETE /contracts/{id}（契約削除）
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [x] 10.3 契約条件管理のプロパティテストを実装
    - genai/tests/test_contracts_properties.py を作成
    - **Property 10: Encryption round-trip**
    - **Validates: Requirements 7.4**
  
  - [x] 10.4 監視履歴エンドポイントを実装
    - genai/src/api/monitoring.py を作成
    - GET /monitoring-history（履歴取得、フィルタリング対応）
    - GET /monitoring-history/statistics（統計情報取得）
    - _Requirements: 6.4, 6.6_
  
  - [x] 10.5 アラートエンドポイントを実装
    - genai/src/api/alerts.py を作成
    - GET /alerts（アラート一覧取得）
    - GET /alerts/{id}（アラート詳細取得）
    - _Requirements: 5.5_
  
  - [x] 10.6 監視対象サイト管理エンドポイントを実装
    - genai/src/api/sites.py を作成
    - POST /sites（サイト登録）
    - PUT /sites/{id}（サイト更新）
    - GET /sites（サイト一覧取得）
    - DELETE /sites/{id}（サイト削除）
    - _Requirements: 1.1_

- [x] 11. Checkpoint - API統合テスト
  - すべてのAPIエンドポイントが正常に動作することを確認
  - 認証・認可が正しく機能することを確認
  - すべてのテストがパスすることを確認
  - ユーザーに質問があれば確認

- [x] 12. セキュリティ機能の実装
  - [x] 12.1 暗号化ユーティリティを実装
    - genai/src/security/encryption.py を作成
    - AES-256-GCM暗号化/復号化関数
    - 環境変数からの暗号化キー読み込み
    - _Requirements: 7.4, 9.2_
  
  - [x] 12.2 認証・認可機能を実装
    - genai/src/security/auth.py を作成
    - JWT トークン生成/検証
    - パスワードハッシュ化（bcrypt）
    - ユーザー登録/ログイン機能
    - _Requirements: 9.5_
  
  - [x] 12.3 監査ログ機能を実装
    - genai/src/security/audit.py を作成
    - 管理操作の自動ログ記録
    - AuditLog モデルへの保存
    - _Requirements: 9.6_

- [x] 13. ダッシュボード（React）の実装
  - [x] 13.1 React プロジェクトのセットアップ
    - genai/frontend/ ディレクトリを作成
    - Vite でプロジェクト作成
    - TypeScript設定
    - 必要なライブラリのインストール（React Router, Axios, Chart.js）
    - _Requirements: 8.1_
  
  - [x] 13.2 監視対象サイト一覧ページを実装
    - genai/frontend/src/pages/Sites.tsx を作成
    - サイト一覧表示
    - コンプライアンスステータス表示
    - _Requirements: 8.1_
  
  - [x] 13.3 アラート一覧ページを実装
    - genai/frontend/src/pages/Alerts.tsx を作成
    - アラート一覧表示
    - 重要度レベル表示
    - タイムスタンプ表示
    - _Requirements: 8.2_
  
  - [x] 13.4 統計ダッシュボードページを実装
    - genai/frontend/src/pages/Dashboard.tsx を作成
    - 監視サイト数、違反数、成功率の表示
    - グラフ表示（Chart.js使用）
    - _Requirements: 8.3_
  
  - [x] 13.5 自動リフレッシュ機能を実装
    - 30秒ごとのデータ更新
    - polling実装
    - _Requirements: 8.6_

- [x] 14. エンドツーエンド統合とテスト
  - [x] 14.1 Docker Compose で全サービスを起動
    - すべてのコンテナが正常に起動することを確認
    - サービス間の通信が正常に機能することを確認
    - _Requirements: 10.1, 10.4_
  
  - [x] 14.2 エンドツーエンドテストを実装
    - genai/tests/test_e2e.py を作成
    - サイト登録 → クローリング → 解析 → 検証 → アラートの完全なワークフロー
    - 契約更新 → 即時検証のワークフロー
    - 擬似サイト検出 → 高優先度アラートのワークフロー
    - _Requirements: 1.1, 2.1, 3.1, 5.1_

- [x] 15. ドキュメントとデプロイ準備
  - [x] 15.1 README.md を作成
    - genai/README.md を作成
    - プロジェクト概要
    - セットアップ手順
    - 使用方法
    - API ドキュメント
  
  - [x] 15.2 環境変数ドキュメントを作成
    - 必要な環境変数の一覧と説明
    - .env.example の更新
  
  - [x] 15.3 デプロイ手順書を作成
    - genai/docs/deployment.md を作成
    - Docker Compose でのデプロイ手順
    - 本番環境での設定推奨事項

- [x] 16. Final Checkpoint - 全体テストと検証
  - すべての機能が正常に動作することを確認
  - すべてのプロパティテストがパスすることを確認
  - パフォーマンス要件を満たしていることを確認
  - セキュリティ要件を満たしていることを確認
  - ユーザーに最終確認

## Notes

- タスクに `*` マークが付いているものはオプションで、コア機能の実装を優先する場合はスキップ可能です
- 各タスクは具体的な要件番号と紐付けられており、トレーサビリティを確保しています
- Checkpointタスクで段階的に検証を行い、問題を早期発見します
- プロパティテストは設計書の正確性プロパティを検証し、システムの正確性を保証します
- ユニットテストは具体的な例やエッジケースを検証します
- すべてのファイルパスは `genai/` ディレクトリを基準としています
- 現在の実装状況: プロジェクトは初期段階で、実装コードはまだありません

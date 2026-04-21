# Implementation Plan: Dark Pattern Notification

## Overview

NotificationPlugin を CrawlPipeline の Reporter ステージに追加し、ダークパターン違反検出時に Slack/メール通知を非同期送信する。実装は DB モデル → 純粋関数 → プラグイン → Celery タスク → API → インフラの順で段階的に進める。

## Tasks

- [x] 1. NotificationRecord DB モデルと Alembic マイグレーション
  - [x] 1.1 NotificationRecord モデルを `genai/src/models.py` に追加する
    - `id`, `site_id` (FK → monitoring_sites.id), `alert_id` (FK → alerts.id, nullable), `violation_type` (String), `channel` (String: slack/email), `recipient` (String), `status` (String: sent/failed/skipped), `sent_at` (DateTime) フィールドを定義
    - 複合インデックス `(site_id, violation_type, sent_at)` と `alert_id` インデックスを追加
    - MonitoringSite, Alert へのリレーションシップを定義
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 1.2 Alembic マイグレーションファイルを作成する
    - `notification_records` テーブルの作成マイグレーション
    - ダウングレードで `notification_records` テーブルを削除
    - _Requirements: 7.5_

  - [ ]* 1.3 Write property test for NotificationRecord model
    - **Property 12: Duplicate suppression within time window**
    - **Validates: Requirements 6.2, 6.4, 6.5**

- [x] 2. NotificationConfig データクラスと merge_notification_config 純粋関数
  - [x] 2.1 `genai/src/pipeline/plugins/notification_config.py` を作成する
    - `NotificationConfig` dataclass を定義 (slack_enabled, slack_webhook_url, slack_channel, email_enabled, email_recipients, suppression_window_hours)
    - `merge_notification_config(customer_email, site_config)` 純粋関数を実装
    - 3層マージ: 環境変数 → site plugin_config → NOTIFICATION_OVERRIDE_DISABLED オーバーライド
    - Customer.email をベース受信者として email_recipients の先頭に配置、additional_email_recipients を追加、重複除去
    - `mask_webhook_url(url)` ヘルパー関数を実装（末尾8文字以外をマスク）
    - _Requirements: 3.2, 4.1, 4.2, 4.3, 4.4, 4.5, 9.4_

  - [ ]* 2.2 Write property test for merge_notification_config
    - **Property 8: 3-layer config merge priority**
    - **Validates: Requirements 3.2, 4.1, 4.2, 4.3, 4.4, 4.5**

  - [ ]* 2.3 Write property test for mask_webhook_url
    - **Property 14: Webhook URL masking**
    - **Validates: Requirements 9.4**

- [x] 3. NotificationTemplateRenderer
  - [x] 3.1 `genai/src/pipeline/plugins/notification_template.py` を作成する
    - `NotificationTemplateRenderer` クラスを実装
    - `render_slack_payload(violations, config, site)`: Slack Block Kit 形式ペイロード生成、severity 色分け (warning→#FFA500, critical→#FF0000, info→#0000FF)
    - `render_email(violations, config, site)`: (subject, body) タプル返却、件名形式 `[決済条件監視] {severity}: {site_name} でダークパターン違反を検出`
    - `render_violation_fields(violation, site)`: 違反 dict からテンプレートフィールド値を抽出、欠損値は 'N/A'
    - 複数違反を1通にまとめる
    - _Requirements: 2.2, 2.3, 3.3, 3.4, 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 3.2 Write property test for Slack payload fields and severity colors
    - **Property 4: Slack payload contains all required violation fields**
    - **Property 5: Slack severity color mapping**
    - **Validates: Requirements 2.2, 2.3**

  - [ ]* 3.3 Write property test for email subject and body
    - **Property 6: Email subject format**
    - **Property 7: Email body contains all required violation fields**
    - **Validates: Requirements 3.3, 3.4**

  - [ ]* 3.4 Write property test for missing fields and round-trip
    - **Property 10: Missing template fields default to N/A**
    - **Property 11: Template field round-trip**
    - **Validates: Requirements 5.4, 5.5**

  - [ ]* 3.5 Write property test for multiple violations single notification
    - **Property 9: Multiple violations produce single notification**
    - **Validates: Requirements 5.3**

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. DuplicateSuppressionChecker と NotificationPlugin
  - [x] 5.1 `genai/src/pipeline/plugins/duplicate_suppression.py` を作成する
    - `DuplicateSuppressionChecker` クラスを実装
    - `filter_new_violations(site_id, violation_types, window_hours)`: NotificationRecord テーブルを参照し、重複でない violation_type のリストを返す
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

  - [x] 5.2 `genai/src/pipeline/plugins/notification_plugin.py` を作成する
    - `NotificationPlugin(CrawlPlugin)` を実装
    - `should_run(ctx)`: violations >= 1 かつ通知チャネルが1つ以上有効
    - `execute(ctx)`: 設定マージ → 重複判定 → テンプレート生成 → Celery タスク投入 → metadata 記録
    - Celery ワーカー不可時の同期フォールバック
    - エラー時は ctx.errors に記録しパイプラインを中断しない
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.5, 3.1, 3.6, 5.2, 6.1, 6.2, 6.3, 8.1, 8.5_

  - [ ]* 5.3 Write property test for should_run
    - **Property 1: should_run reflects violations and channel availability**
    - **Validates: Requirements 1.2**

  - [ ]* 5.4 Write property test for execute error handling
    - **Property 2: execute records metadata with notification_ prefix**
    - **Property 3: execute never raises exceptions**
    - **Validates: Requirements 1.4, 1.5**

- [x] 6. Celery send_notification タスクとキュー設定
  - [x] 6.1 `genai/src/notification_tasks.py` を作成する
    - `send_notification` Celery タスクを実装 (queue='notification', max_retries=3, default_retry_delay=60)
    - `_send_slack(webhook_url, payload)`: HTTP POST + 最大3回リトライ (1s, 2s, 4s 指数バックオフ)
    - `_send_email(recipients, subject, body)`: SMTP 送信 + 最大3回リトライ (1s, 2s, 4s 指数バックオフ)
    - 送信完了後に NotificationRecord を保存し、Alert の slack_sent/email_sent フラグを更新
    - _Requirements: 2.4, 2.5, 3.5, 3.6, 6.3, 8.1, 8.2, 8.3, 8.4_

  - [x] 6.2 `genai/src/celery_app.py` に notification キューとルーティングを追加する
    - `Queue('notification', routing_key='notification')` を PIPELINE_QUEUES に追加
    - `'src.notification_tasks.send_notification': {'queue': 'notification'}` をルーティングに追加
    - `include` リストに `'src.notification_tasks'` を追加
    - _Requirements: 8.2_

  - [ ]* 6.3 Write property test for successful send creates NotificationRecord
    - **Property 13: Successful send creates NotificationRecord and updates Alert flags**
    - **Validates: Requirements 2.5, 3.6, 6.3, 8.4**

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. パイプライン統合と docker-compose 設定
  - [x] 8.1 CrawlPipeline の Reporter ステージに NotificationPlugin を登録する
    - `genai/src/pipeline/pipeline.py` または該当するパイプライン構築コードで、Reporter ステージの実行順序を DBStoragePlugin → AlertPlugin → NotificationPlugin に設定
    - _Requirements: 1.3_

  - [x] 8.2 `genai/docker-compose.yml` に notification-worker サービスを追加する
    - `celery -A src.celery_app worker -Q notification --loglevel=info --concurrency=4`
    - NOTIFICATION_SLACK_WEBHOOK_URL, NOTIFICATION_SLACK_ENABLED, NOTIFICATION_EMAIL_ENABLED, SMTP_HOST, SMTP_PORT 環境変数を設定
    - postgres, redis への depends_on を設定
    - _Requirements: 8.2_

- [x] 9. 通知設定管理 API と通知履歴 API
  - [x] 9.1 Pydantic スキーマを `genai/src/api/schemas.py` に追加する
    - `NotificationConfigResponse`, `NotificationConfigUpdate`, `NotificationHistoryResponse`, `PaginatedNotificationHistoryResponse` を定義
    - _Requirements: 9.3, 10.2_

  - [x] 9.2 `genai/src/api/notifications.py` を作成する
    - `GET /api/sites/{site_id}/notification-config`: マージ済み通知設定を返却、webhook URL マスク済み
    - `PUT /api/sites/{site_id}/notification-config`: plugin_config 内の NotificationPlugin 設定を更新
    - `GET /api/sites/{site_id}/notifications`: 通知履歴を返却、channel/status フィルタ、ページネーション (limit/offset, デフォルト limit=50)
    - 存在しない site_id → 404、不正な設定値 → 422
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 9.3 `genai/src/main.py` に notifications ルーターを登録する
    - `app.include_router(notifications_router, prefix="/api", tags=["notifications"])`
    - _Requirements: 9.1, 10.1_

  - [ ]* 9.4 Write property test for notification config API round-trip
    - **Property 15: Notification config API round-trip**
    - **Validates: Requirements 9.1, 9.2**

  - [ ]* 9.5 Write property test for notification history filtering and pagination
    - **Property 16: Notification history filtering**
    - **Property 17: Notification history pagination**
    - **Validates: Requirements 10.3, 10.4, 10.5**

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The design uses Python throughout, so all implementation tasks use Python

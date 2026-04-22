# Requirements Document

## Introduction

ダークパターン（消費者を誤認させるUIデザインパターン）を含む契約違反が検出された際に、担当者へSlackおよびメールで通知する機能を実装する。現在のReporterステージにはAlertPluginが存在し、違反検出時にAlertレコードをDBに保存しているが、外部通知（Slack/メール）はパイプライン外の旧フロー（`AlertSystem`クラス）でのみ実装されている。

本機能では、CrawlPipelineのReporterステージにNotificationPluginを新規追加し、AlertPlugin実行後に動作させる。通知チャネル（Slack webhook / メール）はグローバル設定＋サイト単位の`plugin_config`による3層マージ（グローバル → サイト → 環境変数オーバーライド）で制御する。通知テンプレートには違反詳細（サイト名、違反種別、検出価格、証拠スクリーンショットURL）を含め、同一違反に対する重複通知を抑制する仕組みを導入する。

## Glossary

- **NotificationPlugin**: CrawlPipelineのReporterステージで動作する通知プラグイン。AlertPlugin実行後にSlack/メール通知を送信する
- **NotificationChannel**: 通知の送信先チャネル。`slack`（Slack Incoming Webhook）と`email`（SMTPメール）の2種類をサポートする
- **NotificationTemplate**: 通知メッセージのテンプレート。違反詳細（サイト名、違反種別、検出価格、証拠スクリーンショットURL等）を埋め込む
- **NotificationRecord**: 通知送信履歴を記録するDBモデル。重複通知抑制の判定に使用する
- **DuplicateSuppressionWindow**: 同一違反に対する重複通知を抑制する時間窓（デフォルト: 24時間）
- **NotificationConfig**: 通知チャネルの設定情報。Slack webhook URL、メール送信先、有効/無効フラグ等を含む
- **CrawlPipeline**: サイト単位のクロール処理を4ステージで実行するパイプラインオーケストレータ
- **AlertPlugin**: Reporterステージで違反検出時にAlertレコードをDBに生成するプラグイン
- **CrawlContext**: パイプライン全体で共有されるコンテキストオブジェクト
- **Customer**: 顧客マスタモデル。`email`フィールド（String, NOT NULL）を持つ
- **MonitoringSite**: 監視対象サイトモデル。`plugin_config`（JSON, nullable）でサイト単位のプラグイン設定を保持する
- **Alert**: アラートモデル。`email_sent`および`slack_sent`フラグを持つ

## Requirements

### Requirement 1: NotificationPlugin のパイプライン統合

**User Story:** As a 開発者, I want ダークパターン違反の通知がCrawlPipelineのReporterステージ内でプラグインとして実行されること, so that 通知処理がパイプラインのライフサイクルに統合され、エラーハンドリングやメタデータ記録が一元管理される。

#### Acceptance Criteria

1. THE NotificationPlugin SHALL CrawlPlugin 抽象基底クラスを継承し、`execute(ctx: CrawlContext) -> CrawlContext` および `should_run(ctx: CrawlContext) -> bool` を実装する
2. THE NotificationPlugin の `should_run()` SHALL CrawlContext の `violations` が1件以上存在し、かつ通知チャネル（Slack または メール）が1つ以上有効に設定されている場合に `True` を返す
3. THE CrawlPipeline の Reporter ステージ SHALL NotificationPlugin を AlertPlugin の後に実行する（実行順序: DBStoragePlugin → AlertPlugin → NotificationPlugin）
4. WHEN NotificationPlugin が実行完了した場合, THE NotificationPlugin SHALL 送信結果（成功/失敗、送信チャネル、送信先）を CrawlContext の `metadata` に `notification_` プレフィックス付きキーで記録する
5. IF NotificationPlugin の実行中にエラーが発生した場合, THEN THE NotificationPlugin SHALL エラーを CrawlContext の `errors` リストに記録し、パイプラインの実行を中断しない

### Requirement 2: Slack 通知送信

**User Story:** As a コンプライアンス担当者, I want ダークパターン違反が検出された際にSlackチャネルへ通知が送信されること, so that チーム全体で違反を即座に把握し対応を開始できる。

#### Acceptance Criteria

1. WHEN NotificationPlugin が実行され Slack 通知が有効な場合, THE NotificationPlugin SHALL Slack Incoming Webhook URL に HTTP POST リクエストを送信する
2. THE Slack 通知メッセージ SHALL 以下の情報を含む: サイト名、違反種別、検出価格（該当する場合）、証拠スクリーンショットURL（該当する場合）、違反の severity、検出日時
3. THE Slack 通知メッセージ SHALL Slack Block Kit 形式でフォーマットし、severity に応じた色分け（warning: 黄色、critical: 赤色、info: 青色）を適用する
4. WHEN Slack Webhook への送信が HTTP ステータス 200 以外を返した場合, THE NotificationPlugin SHALL 最大3回までリトライし（指数バックオフ: 1秒、2秒、4秒）、全リトライ失敗後にエラーを CrawlContext の `errors` に記録する
5. WHEN Slack 通知の送信に成功した場合, THE NotificationPlugin SHALL 対応する Alert レコードの `slack_sent` フラグを `True` に更新する

### Requirement 3: メール通知送信

**User Story:** As a コンプライアンス担当者, I want ダークパターン違反が検出された際に担当者のメールアドレスへ通知が送信されること, so that Slackを使用していない担当者にも違反情報が確実に届く。

#### Acceptance Criteria

1. WHEN NotificationPlugin が実行されメール通知が有効な場合, THE NotificationPlugin SHALL 設定されたメールアドレスに通知メールを送信する
2. THE メール通知 SHALL 送信先として MonitoringSite に紐づく Customer の `email` フィールドを使用する
3. THE メール通知の件名 SHALL 「[決済条件監視] {severity}: {サイト名} でダークパターン違反を検出」の形式とする
4. THE メール通知の本文 SHALL 以下の情報を含む: サイト名、サイトURL、違反種別、検出価格（該当する場合）、証拠スクリーンショットURL（該当する場合）、違反の severity、検出日時
5. WHEN メール送信が失敗した場合, THE NotificationPlugin SHALL 最大3回までリトライし（指数バックオフ: 1秒、2秒、4秒）、全リトライ失敗後にエラーを CrawlContext の `errors` に記録する
6. WHEN メール通知の送信に成功した場合, THE NotificationPlugin SHALL 対応する Alert レコードの `email_sent` フラグを `True` に更新する

### Requirement 4: 通知チャネル設定の3層マージ

**User Story:** As a 運用者, I want 通知チャネルの設定をグローバル・サイト単位・環境変数の3層で柔軟に制御できること, so that 全体のデフォルト設定を維持しつつ、特定サイトだけ通知先を変更したり、環境変数で緊急オーバーライドできる。

#### Acceptance Criteria

1. THE NotificationPlugin SHALL グローバル設定として以下の環境変数を参照する: `NOTIFICATION_SLACK_WEBHOOK_URL`（Slack Webhook URL）、`NOTIFICATION_SLACK_CHANNEL`（Slackチャネル名、デフォルト: `#alerts`）、`NOTIFICATION_EMAIL_ENABLED`（メール通知有効フラグ、デフォルト: `true`）、`NOTIFICATION_SLACK_ENABLED`（Slack通知有効フラグ、デフォルト: `false`）
2. WHEN MonitoringSite の `plugin_config` に `NotificationPlugin` の設定が含まれる場合, THE NotificationPlugin SHALL グローバル設定をベースにサイト単位の設定でマージ（上書き）する
3. THE サイト単位の `plugin_config` SHALL 以下の形式をサポートする: `{"params": {"NotificationPlugin": {"slack_webhook_url": "https://...", "slack_channel": "#site-alerts", "email_enabled": true, "slack_enabled": true, "additional_email_recipients": ["extra@example.com"]}}}`
4. WHEN 環境変数 `NOTIFICATION_OVERRIDE_DISABLED` が `true` に設定されている場合, THE NotificationPlugin SHALL 全通知チャネルを無効化する（緊急停止用）
5. THE NotificationPlugin SHALL 設定マージの優先順位を「環境変数オーバーライド > サイト単位 plugin_config > グローバル環境変数」の順で適用する

### Requirement 5: 通知テンプレート

**User Story:** As a コンプライアンス担当者, I want 通知メッセージに違反の詳細情報が構造化して含まれること, so that 通知を受け取った時点で違反の内容と影響範囲を把握できる。

#### Acceptance Criteria

1. THE NotificationTemplate SHALL 以下のフィールドをプレースホルダーとして定義する: `{site_name}`（サイト名）、`{site_url}`（サイトURL）、`{violation_type}`（違反種別）、`{severity}`（重要度）、`{detected_price}`（検出価格、該当する場合）、`{expected_price}`（契約価格、該当する場合）、`{evidence_url}`（証拠スクリーンショットURL、該当する場合）、`{detected_at}`（検出日時）
2. THE NotificationPlugin SHALL CrawlContext の `violations` リスト内の各違反から上記フィールドの値を抽出してテンプレートに埋め込む
3. WHEN 1回のパイプライン実行で複数の違反が検出された場合, THE NotificationPlugin SHALL 全違反を1通の通知メッセージにまとめて送信する（違反ごとに個別通知を送信しない）
4. WHEN テンプレートフィールドに対応するデータが CrawlContext に存在しない場合, THE NotificationPlugin SHALL 該当フィールドを「N/A」として表示する
5. FOR ALL 有効な CrawlContext の violations, THE NotificationTemplate SHALL テンプレートにフィールド値を埋め込んだ後、再度パースして元のフィールド値を復元できる（ラウンドトリップ特性）

### Requirement 6: 重複通知抑制

**User Story:** As a コンプライアンス担当者, I want 同一の違反に対して短期間に繰り返し通知が送信されないこと, so that 通知疲れを防ぎ、重要な新規違反の通知を見逃さない。

#### Acceptance Criteria

1. THE NotificationPlugin SHALL 通知送信前に NotificationRecord テーブルを参照し、同一サイト・同一違反種別の通知が DuplicateSuppressionWindow 内に送信済みかを判定する
2. WHEN 同一サイト・同一違反種別の通知が DuplicateSuppressionWindow（デフォルト: 24時間）内に送信済みの場合, THE NotificationPlugin SHALL 通知送信をスキップし、スキップ理由を CrawlContext の `metadata` に記録する
3. WHEN 通知送信に成功した場合, THE NotificationPlugin SHALL NotificationRecord テーブルに送信履歴（site_id、violation_type、channel、sent_at）を記録する
4. THE DuplicateSuppressionWindow SHALL 環境変数 `NOTIFICATION_SUPPRESSION_WINDOW_HOURS`（デフォルト: 24）で設定可能とする
5. WHEN 同一サイトで異なる違反種別が検出された場合, THE NotificationPlugin SHALL 各違反種別を独立して重複判定し、新規の違反種別のみ通知する

### Requirement 7: NotificationRecord DBモデル

**User Story:** As a 開発者, I want 通知送信履歴がDBに永続化されること, so that 重複通知抑制の判定と通知履歴の監査が可能になる。

#### Acceptance Criteria

1. THE NotificationRecord テーブル SHALL `id`（Integer, 主キー）、`site_id`（Integer, 外部キー → monitoring_sites.id）、`alert_id`（Integer, 外部キー → alerts.id, nullable）、`violation_type`（String）、`channel`（String: `slack` または `email`）、`recipient`（String: Slack チャネル名またはメールアドレス）、`status`（String: `sent`, `failed`, `skipped`）、`sent_at`（DateTime）フィールドを持つ
2. THE NotificationRecord テーブル SHALL `site_id` と `violation_type` と `sent_at` の複合インデックスを持つ（重複通知判定の高速化）
3. THE NotificationRecord テーブル SHALL `alert_id` にインデックスを持つ
4. THE 全新規カラム SHALL nullable として定義され、既存レコードに影響を与えない（alert_id は nullable）
5. THE Alembic マイグレーション SHALL ダウングレード時に NotificationRecord テーブルを削除する

### Requirement 8: Celery 非同期通知タスク

**User Story:** As a 開発者, I want 通知送信処理がCeleryタスクとして非同期実行されること, so that 通知送信の遅延やリトライがパイプラインの実行時間に影響しない。

#### Acceptance Criteria

1. THE NotificationPlugin SHALL 通知送信処理を Celery タスク `send_notification` としてキューに投入し、パイプライン内では同期的に待機しない
2. THE `send_notification` Celery タスク SHALL `notification` キューで実行される
3. WHEN `send_notification` タスクが失敗した場合, THE Celery タスク SHALL Celery のリトライ機構（`max_retries=3`, `default_retry_delay=60`）で自動リトライする
4. THE `send_notification` タスク SHALL 送信完了後に NotificationRecord を更新し、Alert レコードの `email_sent` / `slack_sent` フラグを更新する
5. WHEN Celery ワーカーが利用不可の場合, THE NotificationPlugin SHALL フォールバックとして同期的に通知送信を試み、失敗時はエラーを CrawlContext の `errors` に記録する

### Requirement 9: 通知設定管理API

**User Story:** As a フロントエンド開発者, I want API経由でサイトの通知設定を取得・更新できること, so that UIから通知チャネルの有効/無効や送信先を管理できる。

#### Acceptance Criteria

1. THE API SHALL `GET /api/sites/{site_id}/notification-config` エンドポイントで対象サイトの通知設定（マージ済み）を返却する
2. THE API SHALL `PUT /api/sites/{site_id}/notification-config` エンドポイントで対象サイトの `plugin_config` 内の NotificationPlugin 設定を更新する
3. THE API レスポンス SHALL 以下のフィールドを含む: `slack_enabled`（bool）、`slack_webhook_url`（string, マスク済み）、`slack_channel`（string）、`email_enabled`（bool）、`email_recipients`（list[string]）、`suppression_window_hours`（int）
4. WHEN Slack Webhook URL を API レスポンスで返す場合, THE API SHALL URL の末尾8文字以外をマスクする（セキュリティ対策）
5. WHEN 存在しない site_id が指定された場合, THE API SHALL 404 エラーを返す
6. WHEN 不正な設定値が指定された場合, THE API SHALL 422 バリデーションエラーを返す

### Requirement 10: 通知履歴API

**User Story:** As a 運用者, I want サイトごとの通知送信履歴を確認できること, so that 通知が正しく送信されているか、重複抑制が適切に機能しているかを監査できる。

#### Acceptance Criteria

1. THE API SHALL `GET /api/sites/{site_id}/notifications` エンドポイントで対象サイトの通知履歴を返却する
2. THE API レスポンス SHALL 各通知レコードに `id`、`violation_type`、`channel`、`recipient`、`status`、`sent_at` を含む
3. THE API SHALL `channel` パラメータ（`slack` / `email`）でフィルタリング可能とする
4. THE API SHALL `status` パラメータ（`sent` / `failed` / `skipped`）でフィルタリング可能とする
5. THE API SHALL ページネーション（`limit`、`offset`）をサポートし、デフォルト `limit=50` とする
6. WHEN 存在しない site_id が指定された場合, THE API SHALL 404 エラーを返す

### Requirement 11: 通知設定管理フロントエンドUI

**User Story:** As a 管理者, I want フロントエンドから通知設定（Slack webhook URL、メールアドレス、しきい値、有効/無効）を管理したい, so that 環境変数を直接編集せずにUIから通知チャネルを設定できる。

#### Acceptance Criteria

1. THE System SHALL サイト詳細パネル内に「通知設定」タブまたはセクションを提供する
2. THE 通知設定UI SHALL 以下の設定項目を表示・編集可能にする: Slack通知の有効/無効トグル、Slack Webhook URL入力、Slackチャンネル名入力、Email通知の有効/無効トグル、Email送信先アドレスリスト（複数入力）、重複抑制ウィンドウ（時間単位）
3. WHEN ユーザーが設定を変更して保存した場合、THE 通知設定UI SHALL `PUT /api/sites/{site_id}/notification-config` APIを呼び出して設定を更新する
4. THE 通知設定UI SHALL Slack Webhook URLをマスク表示する（末尾8文字以外を `***` で表示）
5. THE 通知設定UI SHALL 通知履歴セクションを提供し、`GET /api/sites/{site_id}/notifications` APIから直近の通知送信履歴を表示する
6. THE 通知履歴セクション SHALL チャンネル（Slack/Email）とステータス（sent/failed/skipped）でフィルタリング可能にする
7. IF API呼び出しが失敗した場合、THEN THE 通知設定UI SHALL エラーメッセージを表示する
8. THE ApiService SHALL `NotificationConfig` 型定義と `getNotificationConfig`、`updateNotificationConfig`、`getNotificationHistory` 関数を提供する

# Session: 2026-03-27 Notification Tasks Execution

## Summary
dark-pattern-notification タスク実行開始。Tasks 1-5 完了（DB モデル、設定マージ、テンプレート、重複抑制、NotificationPlugin）。ステータスバッジのインラインツールチップ復元も実施。

## Tasks Completed
- Task 1.1: NotificationRecord モデルを models.py に追加
- Task 1.2: Alembic マイグレーション m8n9o0p1q2r3 作成・適用
- Task 2.1: notification_config.py（NotificationConfig dataclass + merge_notification_config + mask_webhook_url）
- Task 3.1: notification_template.py（NotificationTemplateRenderer: Slack Block Kit + メール）
- Task 5.1: duplicate_suppression.py（DuplicateSuppressionChecker）
- Task 5.2: notification_plugin.py（NotificationPlugin with should_run/execute）
- テスト: test_notification_config.py (15), test_notification_template.py (18), test_notification_plugin.py (23) — 全パス
- UX修正: ステータスバッジに title ツールチップ復元（Badge, Sites, SiteRow, CrawlResultReview, AlertTab, ScreenshotTab）

## Decisions Made
- Badge コンポーネントに title prop を追加してネイティブツールチップ対応（HelpButton モーダルとは別にインラインヘルプを維持）

## Open Items
- Task 6: Celery send_notification タスク + キュー設定
- Task 8: パイプライン統合 + docker-compose notification-worker
- Task 9: 通知設定/履歴 API + main.py ルーター登録
- Task 10: 最終チェックポイント

## Related Specs
- dark-pattern-notification (Tasks 1-5 完了、6-10 残)

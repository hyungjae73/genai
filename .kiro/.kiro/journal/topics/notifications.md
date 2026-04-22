# Topic: Notifications — 通知機能

## Timeline

### 2026-03-26
- Customer.emailの現状用途を調査: CRM表示・検索・重複チェックのみ、通知未使用
- ユーザー要件: ダークパターン検出時にSlack/メールで担当者通知が必要
- dark-pattern-notification spec の requirements.md を作成（10要件）:
  - Req 1: NotificationPlugin パイプライン統合（AlertPlugin の後）
  - Req 2: Slack通知（Webhook, Block Kit, severity色分け, リトライ）
  - Req 3: メール通知（Customer.email宛, SMTP, リトライ）
  - Req 4: 通知チャネル設定の3層マージ
  - Req 5: 通知テンプレート（違反詳細の構造化）
  - Req 6: 重複通知抑制（24時間窓, サイト×違反種別単位）
  - Req 7: NotificationRecord DBモデル
  - Req 8: Celery非同期通知タスク
  - Req 9: 通知設定管理API
  - Req 10: 通知履歴API
- 次ステップ: design.md → tasks.md 作成（crawl-pipeline-architecture完了後に実装）
  - 関連: sessions/2026-03-26-review.md

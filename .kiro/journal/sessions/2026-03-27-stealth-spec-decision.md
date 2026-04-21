# Session: 2026-03-27 Stealth Spec Decision

## Summary
stealth browser リファクタリングのspec管理方針を決定。既存specに含めず、新規spec `stealth-browser-hardening` として切り出す。

## Decisions Made
- 新規spec `stealth-browser-hardening` を作成する（既存 crawl-pipeline-architecture に追加しない）
- 理由: crawl-pipeline-architecture は全タスク完了済み、関心事が独立、テスト対象が明確

## Open Items
- stealth-browser-hardening spec の requirements/design/tasks 作成
- 実装済みコードの文書化 + テスト作成 + 既存テスト修正

## Related Specs
- stealth-browser-hardening（新規作成予定）
- crawl-pipeline-architecture（完了済み、変更しない）

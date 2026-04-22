# Session: 2026-04-08 (remaining-ui-specs)

## Summary
フロントエンド未カバー要件の残り3件を各親specまたは新規specに配置完了。通知設定UIをdark-pattern-notificationに、スケジュール設定拡張をstealth-browser-hardeningに追記し、契約条件動的フォームを新規spec dynamic-contract-form として作成。

## Tasks Completed
- dark-pattern-notification requirements.md に Requirement 11（通知設定管理フロントエンドUI）追記
- stealth-browser-hardening requirements.md に Requirement 19（スケジュール設定フロントエンド拡張）追記
- 新規spec dynamic-contract-form 作成（.config.kiro + requirements.md 4要件）

## Decisions Made
- **通知設定UI → dark-pattern-notification**: バックエンドAPI（Req 9, 10）が既に同specに定義済みのため、フロントエンドUIも同specに追加
- **スケジュール設定拡張 → stealth-browser-hardening**: is_hard_target/plugin_config/fetch-telemetry は同specで定義済みの概念
- **契約条件動的フォーム → 新規spec**: Category/FieldSchema は汎用的な契約管理機能であり、既存specのスコープに収まらないため独立spec化

## Open Items
- dynamic-contract-form の design.md / tasks.md 未作成
- dark-pattern-notification / stealth-browser-hardening の追加要件に対応する design.md / tasks.md の更新が必要
- フロントエンド未カバー要件6件すべてがspec配置完了

## Related Specs
- `.kiro/specs/dark-pattern-notification/` — Requirement 11 追記
- `.kiro/specs/stealth-browser-hardening/` — Requirement 19 追記
- `.kiro/specs/dynamic-contract-form/` — 新規作成（requirements.md 4要件）

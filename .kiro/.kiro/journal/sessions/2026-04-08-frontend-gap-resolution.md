# Session: 2026-04-08 (frontend-gap-resolution)

## Summary
フロントエンド未カバー要件6件の所属先を確定。パスワード変更UI・エラーページ・監査ログ閲覧UIの3件をuser-auth-rbac requirements.mdに要件11-13として追記。残り3件（通知設定UI、契約条件動的フォーム、スケジュール設定拡張）はdark-pattern-frontendには入れず、各親specまたは新規specとして扱う方針を決定。

## Tasks Completed
- user-auth-rbac requirements.md に要件11（パスワード変更）追記
- user-auth-rbac requirements.md に要件12（エラーページ 403/404/500）追記
- user-auth-rbac requirements.md に要件13（監査ログ閲覧UI）追記

## Decisions Made
- **dark-pattern-frontendのスコープ維持**: 「ダークパターン検出UI」に限定。通知設定・契約フォーム・スケジュール設定は別の関心事のため追加しない
- **未カバー要件の所属先確定**:
  - パスワード変更UI → user-auth-rbac 要件11（認証の関心事）
  - エラーページ → user-auth-rbac 要件12（認証・認可のエラーハンドリング）
  - 監査ログ閲覧UI → user-auth-rbac 要件13（監査の関心事、admin専用）
  - 通知設定管理UI → dark-pattern-notification に追加 or 新規spec（通知インフラの関心事）
  - 契約条件動的フォーム → 新規spec dynamic-contract-form（Category/FieldSchemaの汎用契約管理）
  - スケジュール設定拡張 → stealth-browser-hardening に追加（is_hard_target/plugin_configの設定UI）

## Open Items
- 通知設定管理UI、契約条件動的フォーム、スケジュール設定拡張の3件は必要時にspec化
- user-auth-rbac の design.md と tasks.md に要件11-13の設計・タスクを追加する必要あり

## Related Specs
- `.kiro/specs/user-auth-rbac/` — requirements.md に要件11-13追記
- `.kiro/specs/dark-pattern-frontend/` — スコープ変更なし（確認済み）

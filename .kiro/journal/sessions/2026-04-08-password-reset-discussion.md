# Session: 2026-04-08 (password-reset-discussion)

## Summary
パスワードリセット機能の必要性を議論。要件11（パスワード変更）は定義済みだが未実装。パスワードを忘れた場合のadmin強制リセット機能（要件14）の追加を提案。

## Decisions Made
- **パスワード変更（要件11）とパスワードリセット（要件14）は別機能**: 要件11はログイン中ユーザの自己変更、要件14はadminによる強制リセット
- **メールベースリセットは不要**: 社内ツールのためadminに依頼する運用で十分

## Open Items
- 要件14（admin強制リセット `POST /api/users/{id}/reset-password`）をuser-auth-rbac requirements.mdに追記するか確認待ち
- 要件11（パスワード変更）+ 要件14（強制リセット）の実装が未着手

## Related Specs
- `.kiro/specs/user-auth-rbac/`

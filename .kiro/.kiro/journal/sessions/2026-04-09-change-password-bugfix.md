# Session: 2026-04-09 (change-password-bugfix)

## Summary
初期パスワード設定画面のバグ修正。「現在のパスワード」入力欄が非表示で、新パスワードをcurrent_passwordとして送信していたため401エラーが発生していた。常に現在のパスワード入力欄を表示するよう修正。

## Tasks Completed
- ChangePassword.tsx: 初期セットアップ時も「現在のパスワード（自動生成されたパスワード）」入力欄を表示するよう修正
- 不要な条件分岐（isInitialSetup時のcurrentPassword || newPasswordフォールバック）を削除
- フロントエンドリビルド→再デプロイ完了

## Related Specs
- `.kiro/specs/user-auth-rbac/`

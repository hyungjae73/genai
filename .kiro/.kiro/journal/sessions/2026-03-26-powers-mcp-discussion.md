# Session: 2026-03-26 (Powers/MCP Skill Enhancement Discussion)

## Summary
Powers/MCPによるスキル強化案3つ（キーワード駆動ドメイン知識、インフラ操作統合、DB直接操作）を評価・優先度付け。

## Tasks Completed
- なし（議論のみ）

## Decisions Made
- **DB直接操作MCPを最優先**: テストデータ投入・スキーマ確認の頻度が高く、開発テンポへのインパクト最大。PostgreSQL MCP Server導入を検討
- **キーワード駆動ドメイン知識も高優先**: ダークパターン検知specで法規制知識（特定商取引法、景品表示法）が必要。steering fileMatchパターンで今すぐ実現可能
- **インフラ操作統合は中優先**: docker-compose変更頻度は低く、Alembicは既にhookで管理済み。将来的にAWS MCP検討

## Topics Discussed
- Context Rot問題: 全ツール常時ロードによるコンテキスト長圧迫の回避策
- Figma Powerのactivateパターンが既にキーワード駆動の実証例
- SQLiteテストDB + PostgreSQL本番DBの二重管理の摩擦
- 法規制ドメイン知識（特定商取引法、景品表示法）のMCP/steering化
- 開発環境限定でのIaC生成→レビュー→適用フロー

## Open Items
- PostgreSQL MCP Server の `.kiro/settings/mcp.json` 設定
- 法規制ドメイン知識用 steering file（fileMatch: ダークパターン関連ファイル）作成
- dark-pattern-notification / advanced-dark-pattern-detection の design.md → tasks.md

## Related Specs
- .kiro/specs/advanced-dark-pattern-detection/
- .kiro/specs/dark-pattern-notification/

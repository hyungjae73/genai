# Session: 2026-03-26 (SQLite Test DB Evaluation)

## Summary
SQLiteテスト用DBの適切性を評価。JSONB→JSON妥協、インデックス動作差異、タイムスタンプ精度問題を特定。testcontainers-pythonへの移行を推奨。

## Tasks Completed
- なし（技術評価のみ）

## Decisions Made
- **SQLiteテストDBは限界に近づいている**: JSONB非対応、server_default差異、複合インデックス動作差異が既に問題化
- **testcontainers-pythonへの移行を推奨**: 本番同等PostgreSQL、conftest.py変更のみ、既存446テストはそのまま動作、JSONB復元可能
- **移行タイミングは次のDB変更時**: advanced-dark-pattern-detectionのDBモデル拡張時に合わせて実施が効率的

## Topics Discussed
- SQLite vs PostgreSQLの型・機能差異（JSONB、部分インデックス、タイムスタンプ精度）
- testcontainers-python vs docker-compose test profile vs 現状維持の比較
- 移行の影響範囲（conftest.py変更、JSON→JSONB復元、CI設定）
- GitHub ActionsでのDocker service対応

## Open Items
- testcontainers-python移行のspec作成（次のDB変更時に実施）
- dark-pattern-notification / advanced-dark-pattern-detection の design.md → tasks.md
- PostgreSQL MCP Server設定
- 法規制ドメイン知識steering file作成

## Related Specs
- .kiro/specs/crawl-pipeline-architecture/ (JSONB→JSON妥協の発生源)
- .kiro/specs/advanced-dark-pattern-detection/ (次のDB変更予定)

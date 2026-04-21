# Session: 2026-03-27 (testcontainers-migration Design)

## Summary
testcontainers-migration specの設計ドキュメントを作成。conftest.py新設計、JSONB復元、CI統一、5つの正当性プロパティを定義。

## Tasks Completed
- testcontainers-migration design.md 作成

## Decisions Made
- **CI servicesセクション削除→testcontainersに統一**: ローカルとCIで同一コンテナ管理ロジック
- **同期ドライバpsycopg2に統一**: asyncpg/aiosqlite依存を排除
- **Base.metadata.create_all()でスキーマ作成**: Alembic検証は別途オプションフィクスチャ
- **session scopeコンテナ + function scopeトランザクションrollback**: パフォーマンスとテスト分離の両立
- **SAVEPOINTサポート**: event.listens_for(session, "after_transaction_end")でネストトランザクション対応

## Topics Discussed
- 現状conftest.pyのasyncpg URLパターンとpsycopg2の不整合
- 6つ以上のテストファイルがローカルにSQLiteインメモリDBを定義している問題
- CI PostgreSQL servicesとtestcontainersの二重管理回避

## Open Items
- testcontainers-migration tasks.md 作成・実装
- dark-pattern-notification design.md → tasks.md
- advanced-dark-pattern-detection design.md → tasks.md

## Related Specs
- .kiro/specs/testcontainers-migration/

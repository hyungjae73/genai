# Session: 2026-03-27 (testcontainers-python Decision)

## Summary
testcontainers-python vs docker-compose test profileを比較評価。testcontainers-pythonを理想の選択として決定。2層テスト構成（ユニット/PBT→testcontainers、E2E→docker-compose profile）を方針化。

## Tasks Completed
- なし（技術評価のみ）

## Decisions Made
- **testcontainers-pythonが理想**: テストライフサイクル自動管理、テスト分離、CI統合の容易さ、並列テスト対応で優位
- **2層テスト構成を採用**: ユニットテスト/PBT→testcontainers-python（PostgreSQL 15-alpine）、E2Eテスト→docker-compose test profile（将来追加）
- **移行の影響範囲はconftest.pyのみ**: 既存446テストはそのまま動作。JSON→JSONB復元が可能に
- **scope="session"でコンテナ再利用**: テストスイート全体で1つのPostgreSQLコンテナを共有、各テストはrollbackで分離

## Topics Discussed
- testcontainers vs docker-compose profileの6観点比較（コンテナ管理、テスト分離、CI統合、ローカル開発、並列テスト、Alembic検証）
- conftest.pyの具体的な実装パターン（PostgresContainer + session scope + rollback）
- docker-compose profileが向いているケース（複数サービス間E2Eテスト）

## Open Items
- testcontainers-python移行spec作成（advanced-dark-pattern-detectionのDB変更時に合わせて実施）
- requirements.txtへの `testcontainers[postgres]` 追加
- GitHub Actions CI設定の確認（Docker service不要、testcontainersが自動管理）

## Related Specs
- .kiro/specs/crawl-pipeline-architecture/ (JSONB→JSON妥協の解消)
- .kiro/specs/advanced-dark-pattern-detection/ (次のDB変更タイミング)

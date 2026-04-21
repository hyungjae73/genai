# Session: 2026-03-27 (ScrapingTask実装 — engineering_standards検証)

## Summary
engineering_standards.mdの4つの防衛スキルを実証するため、ScrapingTaskのDBモデル・Pydanticスキーマ・サービスクラス・PBTテストを実装。事前設計レポート→コード→テスト実行→チェックリストの全フローを完遂。8 PBTテスト全PASS。

## Tasks Completed
- ScrapingTaskモデル（models.py追加）: ScrapingTaskStatus Enum、状態遷移インデックス
- CreateScrapingTaskRequest/ScrapingTaskResponse（schemas.py追加）: URL pattern検証、Enum型status
- ScrapingTaskService（新規ファイル）: create_task（べき等性）、mark_as_failed（悲観的状態遷移）
- test_scraping_task_properties.py: 8 PBTテスト（境界防御、べき等性、状態遷移、エッジケース）
- Alembicマイグレーション: l7m8n9o0p1q2_add_scraping_tasks_table.py
- spec-dependencies.md: マイグレーションチェーン更新

## Decisions Made
- **同一URL重複タスクの扱い**: PENDING/PROCESSINGの既存タスクがあれば再利用（べき等性）。FAILED/SUCCESS後は新規作成を許可
- **SUCCESS→FAILEDの遷移を禁止**: 完了済みタスクの状態を巻き戻すのは不正。InvalidStateTransitionで拒否
- **error_messageは10000文字に切り詰め**: 巨大スタックトレースによるDB肥大化を防止

## Related Specs
- .kiro/steering/engineering_standards.md

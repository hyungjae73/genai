# Session: 2026-03-27 Spec Prioritization

## Summary
requirements.mdのみ存在するspec 2件を特定し、実装順序を決定。dark-pattern-notification → advanced-dark-pattern-detection の順で進める方針。ユーザーが一時中断を要求したため、実装は次セッションに持ち越し。

## Tasks Completed
- 全specディレクトリを走査し、design.md/tasks.md未作成のspecを特定
- advanced-dark-pattern-detection（14要件）と dark-pattern-notification（10要件）の2件を確認
- 依存関係分析: notification が detection の前提（Req 14 連携）

## Decisions Made
- dark-pattern-notification を先に実装する（advanced-dark-pattern-detection の前提依存）
- 両specとも requirements-first ワークフロー

## Open Items
- dark-pattern-notification の design.md 作成から開始（次セッション）
- その後 tasks.md 作成 → 実装
- advanced-dark-pattern-detection は notification 完了後に着手

## Related Specs
- dark-pattern-notification
- advanced-dark-pattern-detection

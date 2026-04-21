# Session: 2026-03-26 (Product Constitution)

## Summary
プロダクト憲法（product.md）をsteeringファイルとして作成。非同期UX、証拠保全、グローバルエラーハンドリングの3原則を定義。

## Tasks Completed
- `.kiro/steering/product.md` 作成（auto inclusion）

## Decisions Made
- **プロダクト憲法をsteering auto inclusionで管理**: 全セッションで自動適用される不可侵の原則として定義
- **3つの不可侵原則**: (1) 非同期タスクUX — ローディングスピナー禁止、task_id + ポーリング必須 (2) 証拠保全 — MinIO保存必須、react-zoom-pan-pinchビューア必須 (3) グローバルエラーハンドリング — 画面クラッシュ禁止、Error Boundary 2層、4xx/5xx分離

## Topics Discussed
- 非同期タスク（crawl/extract/validate/report）のフロントエンドUX設計方針
- 証拠保全のトレーサビリティ要件
- エラーハンドリングの階層設計

## Open Items
- product.md の原則に基づくフロントエンド実装（Error Boundary、非同期進捗UI）は未実装
- dark-pattern-notification / advanced-dark-pattern-detection の design.md → tasks.md 作成

## Related Specs
- .kiro/steering/product.md

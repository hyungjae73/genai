# Session: 2026-03-27 Spec Merge Analysis

## Summary
dark-pattern-notification と advanced-dark-pattern-detection を統合すべきか別specで進めるべきかを分析。別specのまま進める方針を決定。

## Decisions Made
- 2つのspecは統合せず別specのまま進める
  - 関心事が明確に分離: detection=「何を検出するか」、notification=「どう通知するか」
  - DBモデル変更が完全に独立（別テーブル/別カラム）
  - 唯一の接点は detection Req 14（violations形式の互換性）のみ
  - notification は既存違反にも使える汎用機能
  - 統合すると24要件の巨大specになりレビュー・管理が困難
- 実装順序: notification → detection（notification が汎用基盤として先に必要）

## Topics Discussed
- spec統合 vs 分離の判断基準（関心事分離、DBモデル独立性、接点の少なさ）

## Open Items
- dark-pattern-notification の design.md 作成から開始（次セッション）

## Related Specs
- dark-pattern-notification
- advanced-dark-pattern-detection

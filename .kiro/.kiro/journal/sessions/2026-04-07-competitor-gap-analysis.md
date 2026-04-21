# Session: 2026-04-07 (competitor-gap-analysis)

## Summary
セカンドサイトアナリティカ社の加盟店審査システム提案資料（PDF）を分析し、現状システムとの機能差分を11項目洗い出した。dark-pattern-frontend spec の requirements.md 作成をサブエージェントに委譲完了。

## Tasks Completed
- dark-pattern-frontend spec の requirements.md 作成（9要件、サブエージェント委譲）
- 競合提案資料（SecondXight Analytica 加盟店審査システム）との機能差分分析
- 11項目の差分を特定し、Spec化推奨優先度テーブルを作成

## Decisions Made
- **dark-pattern-frontend spec**: requirements-first ワークフローで作成開始。FR-1〜FR-9の全9要件をEARSパターン準拠で定義
- **競合差分分析の結果**: 以下の11項目が現状システムに欠落していることを確認:
  1. ユーザ管理・権限管理（🔴P0）— 認証・RBAC完全欠落
  2. 手動審査ワークフロー（🔴P0）— 二次判定・承認フロー欠落
  3. 外部データ連携I/F（🔴P1）— 申込受付システムWebAPI連携なし
  4. 反社・ネガ情報チェック（🔴P1）— JDM照会・独自ネガDB連携なし
  5. 風評検索（🟡P2）
  6. 住所・法人情報収集（🟡P2）
  7. シミュレーション（🟡P2）
  8. 類似度チェック/重複検出（🟡P2）
  9. URL自動判定（🟢P3）
  10. CSV/BI連携（🟢P3）
  11. 商材資料自動チェック（🟢P3）

## Topics Discussed
- 競合システムの全体構成: 初期審査フロー（申込→情報収集→AI判定→ルール判定→手動審査→判定結果）
- 途上審査フロー: 定期タイミング自動実行、加盟店マスタ更新連携
- 概算見積り: イニシャル2,400万円、ランニング月額60万円、9ヶ月スケジュール
- 現状システムのカバー範囲: クローリング、ルール判定、AI判定（LLM）、偽サイト検知、ダークパターン検出、通知は実装済み

## Open Items
- ユーザーがどの差分Specから着手するか未決定（P0のuser-auth-rbacまたはmanual-review-workflowを推奨）
- dark-pattern-frontend spec の design.md → tasks.md 作成が次ステップ
- 競合差分の各項目について詳細なSpec作成が必要

## Related Specs
- `.kiro/specs/dark-pattern-frontend/` — requirements.md 作成完了
- `.kiro/specs/advanced-dark-pattern-detection/` — 既存バックエンド実装

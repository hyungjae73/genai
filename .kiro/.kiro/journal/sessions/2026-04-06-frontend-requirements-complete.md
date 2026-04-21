# Session: 2026-04-06 (frontend-requirements-complete)

## Summary
前セッションで途中だったフロントエンド実装要件シート（`frontend-requirements.md`）のFR-2〜FR-8を完成させた。全8カテゴリ、Before/After ASCIIワイヤーフレーム付き、api.ts型定義・関数シグネチャまとめ、実装優先度テーブルを含む616行のドキュメント。

## Tasks Completed
- FR-2: ダークパターンスコア履歴チャート（時系列折れ線グラフ、Chart.js Line）
- FR-3: 加盟店カテゴリ（merchant_category）設定UI（サイト編集フォーム拡張）
- FR-4: 動的LLMルール管理CRUD画面（Rules.tsx拡張、ビルトイン/LLMタブ切替、モーダル設計）
- FR-5: サイト別検出ルールセット表示（DarkPatternTab内サブタブ、読み取り専用）
- FR-6: 違反カテゴリバッジ（Alerts.tsx拡張、dark_pattern_category Badge追加）
- FR-7: ジャーニースクリプトGUIエディタ（Phase 2、textareaベース）
- FR-8: ダッシュボード統合（統計カード2枚追加、スコア分布・カテゴリトレンドグラフ）
- api.ts追加型定義・関数シグネチャまとめセクション作成
- 実装優先度テーブル作成

## Decisions Made
- **Rules.tsxはタブ切替で拡張**: 新規ページ追加ではなく、既存Rules.tsx内に「ビルトイン」「LLMルール」タブを追加。サイドバー変更不要。
- **FR-4にバックエンドCRUD API新規必要**: `GET/POST/PUT/DELETE /api/dark-patterns/rules` — 現在未実装。
- **FR-7はPhase 2**: ジャーニースクリプトエディタは低優先度、textareaベースで最小実装。
- **FR-5は読み取り専用**: サイト詳細からルール適用状況を確認のみ、編集はRulesページへ誘導。

## Topics Discussed
- フロントエンドギャップ分析の完了: バックエンドで追加された全概念（dark_pattern_score, subscores, types, dynamic_compliance_rules, merchant_category, journey_script, dark_pattern_category）のUI反映要件を網羅

## Open Items
- FR-4のバックエンドCRUD API（`/api/dark-patterns/rules`）が未実装 — フロント実装前に必要
- FR-3のmerchant_categoryフィールドがSiteモデル/APIに未追加
- FR-6のAlert APIレスポンスにdark_pattern_category未含有
- FR-8のStatistics APIレスポンス拡張が必要
- 要件シートに基づくspec作成 → tasks.md → 実装の流れが次ステップ

## Related Specs
- `.kiro/specs/advanced-dark-pattern-detection/`

## End-of-Session Checklist
- [x] models.py変更なし → Alembicマイグレーション不要
- [x] schemas.py変更なし
- [x] API追加なし → main.py変更不要
- [x] DB/API変更なし → spec-dependencies.md更新不要

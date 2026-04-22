# Session: 2026-03-27 Status Help Standalone Restoration

## Summary
ステータスヘルプモーダルをページヘルプから分離し、ステータスフィルター横の独立?ボタンとして復元。ページヘルプとステータスヘルプの情報粒度を分離。

## Tasks Completed
- Sites.tsx: ページヘルプからステータス説明を削除、ステータスフィルター横に独立HelpButton復元
- SiteManagement.tsx: ページヘルプからステータス説明を削除、不要なBadge import削除
- Vite dev server 起動（port 5174）

## Decisions Made
- ページヘルプ（タイトル横?）: ページ操作の説明に集中（検索、クロール、結果確認）
- ステータスヘルプ（フィルター横?）: ステータスの意味に特化（準拠/違反/保留/エラー）
- SiteRow のバッジ: title ツールチップを維持（行クリックとの競合回避のためモーダルは不使用）
- 情報粒度の原則: 異なる粒度の情報は異なるヘルプボタンに分離する

## Open Items
- dark-pattern-notification Tasks 6-10 の実行継続

## Related Specs
- figma-ux-improvement（HelpButton コンポーネント）
- screenshot-integration-rename（UI変更の影響範囲）

# Session: 2026-03-27 Help Content Rewrite

## Summary
全7ページのヘルプモーダル内容を書き直し。ユーザーストーリーベースの冗長な説明から、操作ガイド形式の簡潔な内容に変更。help-content CSS を追加しフォントサイズ・見出し・余白を改善。

## Tasks Completed
- HelpButton.css に help-content スタイル追加（0.85rem、見出し下線、💡ヒントボックス）
- Sites.tsx: 「できること」箇条書き + クロール/結果確認の操作説明 + ステータスヘルプへの誘導
- SiteManagement.tsx: 階層構造 + 詳細タブの簡潔な説明
- Customers.tsx: 登録・編集・削除 + 無効化の注意点
- Contracts.tsx: 設定項目一覧 + 「現在」バッジの説明
- Alerts.tsx: 重要度の目安を1行ずつ簡潔に
- FakeSites.tsx: スコアの見方 + 自動更新の説明
- CrawlResultReview.tsx（2箇所）: 操作方法 + 信頼度スコアのヒント

## Decisions Made
- ヘルプモーダルのタイトルを「このページの使い方」に統一
- 「ユーザーストーリー」見出しは全ページから削除（ユーザー向けではない）
- 構成パターン: 「できること」箇条書き → 操作説明 → 💡ヒント
- 重要な補足は help-tip ボックスで視覚的に区別

## Open Items
- dark-pattern-notification Tasks 6-10 の実行継続

## Related Specs
- figma-ux-improvement（HelpButton コンポーネント）

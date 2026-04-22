# Session: 2026-03-27 Help Content Catalog

## Summary
SaaS他社事例（Slack, Loom, Spotify）を調査し、ヘルプUXのベストプラクティスを把握。全ページのヘルプコンテンツを一覧確認できるMDファイル（help-content.md）を作成。

## Tasks Completed
- SaaS他社のヘルプUI/UX事例調査（Slack, Loom, Spotify, Stripe, Notion等）
- genai/frontend/src/help-content.md 作成（7ページヘルプ + 1インラインヘルプ + ツールチップ一覧 + デザイン方針）

## Decisions Made
- ヘルプコンテンツはspecとして切り出さず、MDファイルで内容を管理し直接コードに反映する方針
- デザイン方針: 最大3セクション、「できること」箇条書き→操作説明→💡ヒント

## Topics Discussed
- 他社事例の共通パターン: 検索バー最上部、アイコン付きカテゴリ、よくある質問を先に、エスカレーションパス
- 現在のモーダル構造（HelpButton→Modal）の制約内でできる改善と、将来的な再設計の分離

## Open Items
- help-content.md の内容レビュー後、コードに反映
- dark-pattern-notification Tasks 6-10 の実行継続

## Related Specs
- figma-ux-improvement（HelpButton コンポーネント）

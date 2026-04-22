# Session: 2026-04-06 (ui-bugfix-screenshot-toast)

## Summary
フロントエンドUI2件のバグ修正。スクリーンショット表示不具合（相対パスにAPI_BASE_URL未付加）とToast通知の文字色コントラスト不足（白文字on緑背景）を修正。

## Tasks Completed
- Sites.tsx: screenshot_path にVITE_API_BASE_URLプレフィックスを付加（CrawlResultReview.tsxと同じパターン）
- Sites.css: Toast通知スタイルをApp.cssパターンに統一（success-subtle背景+success-text文字色+左ボーダー）

## Decisions Made
- **Toast統一**: Sites.css独自のtoastスタイル（color-text-inverse白文字+color-success緑背景）を廃止し、App.cssの薄い背景+濃い文字+左ボーダーパターンに統一

## Related Specs
- .kiro/specs/figma-ux-improvement/（デザインシステム）

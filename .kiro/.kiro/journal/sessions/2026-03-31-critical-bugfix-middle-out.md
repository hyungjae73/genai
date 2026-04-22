# Session: 2026-03-31 (critical-bugfix-middle-out)

## Summary
CTOレビューで発見された致命的バグ2件を即時修正。DynamicLLMValidatorPluginの生HTML返却と単純前方切り捨てを、HTMLタグパージ+Middle-Out Truncationに置換。

## Tasks Completed
- `_extract_page_text()`: 生HTML返却 → `_strip_html_to_text()` でscript/style/noscript除去+全タグパージに修正
- `_build_prompt()`: `page_text[:max_text]` → `_middle_out_truncate()` に置換（上部20%+下部30%保持）
- `_strip_html_to_text()` ユーティリティ関数を追加
- `_middle_out_truncate()` ユーティリティ関数を追加（中間部分の均等サンプリング付き）

## Decisions Made
- **Middle-Out中間サンプリング**: 中間50%を完全に捨てるのではなく、残り枠で中間テキストの先頭・末尾から均等取得する方式を採用

## Related Specs
- .kiro/specs/advanced-dark-pattern-detection/

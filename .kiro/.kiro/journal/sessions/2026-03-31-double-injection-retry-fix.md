# Session: 2026-03-31 (double-injection-retry-fix)

## Summary
CTOレッドフラグ2件を即時修正。_build_promptの二重挿入バグ排除、LLM API呼び出しに指数バックオフ3回リトライ追加。

## Tasks Completed
- `_build_prompt`: {page_text}プレースホルダ有無で条件分岐、二重挿入を排除。return promptのみに修正
- `_evaluate_single_rule`: tenacity指数バックオフ3回リトライ追加（tenacity未インストール時は手動リトライにフォールバック）

## Decisions Made
- **二重挿入修正**: {page_text}がテンプレートにある場合はreplaceのみ、ない場合のみ末尾追加（フォールバック+警告ログ）
- **リトライ戦略**: tenacity優先、未インストール時は手動3回（2s→4sの指数バックオフ）。全リトライ失敗後のみpassed=True

## Related Specs
- .kiro/specs/advanced-dark-pattern-detection/

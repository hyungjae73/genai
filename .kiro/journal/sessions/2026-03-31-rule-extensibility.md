# Session: 2026-03-31 (rule-extensibility)

## Summary
advanced-dark-pattern-detection specに検出ルール動的拡張性（Req 15）とdark_pattern_type分類体系（Req 16）を追加。DetectionRuleSetエンジン設計、6組み込みルール型、10種の分類タクソノミー、4新規Correctness Properties（P23-P26）を定義。

## Tasks Completed
- requirements.md: Req 15（DetectionRuleSet、10 AC）+ Req 16（分類体系、5 AC）追加
- design.md: DetectionRuleSetエンジン設計（load_detection_rules, evaluate_rule, normalize_dark_pattern_type）+ JSON形式例 + P23-P26追加
- tasks.md: Task 1.13（DetectionRuleSet実装）+ Task 1.14（PBT P23-P26）追加
- Glossary: DetectionRuleSet, VALID_DARK_PATTERN_TYPES 追加

## Decisions Made
- **6組み込みルール型**: css_selector_exists, text_pattern_match, price_threshold, element_attribute_check, dom_distance, custom_evaluator
- **custom_evaluator**: Python callableパスを指定して任意ロジック実行可能（加盟店固有の検出ルール対応）
- **ルールマージ戦略**: グローバル + サイト固有、rule_idによる上書き
- **分類タクソノミー**: 10種 + other フォールバック。LLM出力の自由テキストを正規化

## Open Items
- タスク実行開始

## Related Specs
- .kiro/specs/advanced-dark-pattern-detection/

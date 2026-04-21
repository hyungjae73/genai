# Session: 2026-04-06 (contract-ui-gap-analysis)

## Summary
契約条件登録UIのギャップ分析。現在のContracts.tsxフォームには価格/決済方法/手数料/サブスク条件の基本フィールドは存在するが、advanced-dark-pattern-detectionで追加されたmerchant_category、validation_rules、Dynamic LLMルール管理のUIが未実装であることを確認。

## Topics Discussed
- 現在の契約条件フォーム: サイト選択、JPY価格、許可/必須決済方法、手数料（%/固定）、サブスク条件（契約期間/解約ポリシー）
- 不足UI候補4件: (1) merchant_category選択、(2) validation_rules設定、(3) Dynamic LLMルール管理画面、(4) 新規契約項目フィールド追加
- ユーザーに具体的な要件を確認中（判断待ち）

## Open Items
- 契約条件UIの追加要件の具体化（ユーザー回答待ち）

## Related Specs
- .kiro/specs/advanced-dark-pattern-detection/（merchant_category、validation_rules）

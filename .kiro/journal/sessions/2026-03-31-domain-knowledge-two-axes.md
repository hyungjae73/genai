# Session: 2026-03-31 (domain-knowledge-two-axes)

## Summary
ドメイン知識の共有: システムの検出には「契約違反検出」と「Darksite検出」の2つの独立した軸があることを確認。契約違反検出は加盟店の商品特性により検出項目が異なり、動的拡張が必要。Darksite検出は類似ドメイン・契約外コンテンツ・契約偽りの3要素。

## Decisions Made
- （判断待ち）検出ルール拡張性の設計を現specに組み込むか、別specとして切り出すか

## Topics Discussed
- **軸1: 契約違反検出**: 共通項目+加盟店固有項目、契約条件追加時の検出ロジック動的拡張の必要性
- **軸2: Darksite検出**: 類似ドメイン検出、同一商品の契約外ドメイン存在確認、契約内容の偽り検出
- **現状のカバー範囲**: 軸1はContractComparisonPlugin+advanced-dark-pattern-detection、軸2はfake-site-detection-alert
- **拡張性の課題**: plugin_config(JSONB)+ContractConditionで加盟店別ルール定義は可能だが、新検出項目タイプのコード変更なし追加は未対応

## Open Items
- 検出ルール拡張性の設計方針決定（現spec組み込み vs 別spec）
- advanced-dark-pattern-detection タスク実行開始

## Related Specs
- .kiro/specs/advanced-dark-pattern-detection/（契約違反検出の高度化）
- .kiro/specs/fake-site-detection-alert/（Darksite検出）

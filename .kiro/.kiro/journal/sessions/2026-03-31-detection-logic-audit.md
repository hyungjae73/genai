# Session: 2026-03-31 (detection-logic-audit)

## Summary
advanced-dark-pattern-detection の検出ロジックを既存コードベースから包括的に調査。現状の検出能力のギャップ分析を実施し、specに含まれていない6つの強化ポイントを特定。

## Tasks Completed
- 既存パイプラインの違反検出フロー全体を調査（StructuredDataPlugin → HTMLParserPlugin → SemanticParser → ContractComparisonPlugin → AlertPlugin → NotificationPlugin）
- SemanticParser の価格/手数料/支払方法パターンマッチングの詳細確認
- PriceHistory/Violation/VerificationResult モデルの検出結果永続化構造を確認
- specカバー範囲外の6つの検出ギャップを特定

## Topics Discussed
- **Price Bait-and-Switch**: PriceHistoryテーブルは存在するがクロール前後の価格操作パターン検出なし
- **解約導線の機能検証**: DOM距離は検出するがリンク先の有効性検証なし
- **税込/税抜表示の欺瞞**: 価格抽出はするが税表示コンテキストの判定なし
- **偽の緊急性パターン**: カウントダウンタイマー/残数表示の検出なし
- **dark_pattern_type分類体系**: LLMの自由テキスト返却で下流集計が困難になるリスク
- **クロスプラグイン相関**: 複合パターン（低コントラスト+定期購入条件）の重み付けなし

## Open Items
- dark_pattern_type の有効値リスト定義をspecに追加するか判断待ち
- 偽の緊急性パターン（Urgency Pattern）をUITrapPluginに追加するか判断待ち
- 現状スコープで実装に進むか、spec拡張するか

## Related Specs
- .kiro/specs/advanced-dark-pattern-detection/
- .kiro/specs/dark-pattern-notification/

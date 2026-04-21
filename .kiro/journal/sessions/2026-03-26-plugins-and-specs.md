# Session: 2026-03-26 (Plugins Implementation & Advanced Detection Spec)

## Summary
crawl-pipeline-architecture Tasks 4.7-5.4を完了（PageFetcherステージ実行順序制御、DataExtractorプラグイン4つ実装）。advanced-dark-pattern-detection specのrequirements.mdを作成（14要件）。

## Tasks Completed
- 4.7: PageFetcherStage 実行順序制御（前セッションで実装済み、テスト25件通過確認）
- 4.8: Property test — Delta crawl conditional headers（Property 20）
- 5.1: StructuredDataPlugin（JSON-LD, Microdata, Open Graph抽出、優先順位マージ）
- 5.2: ShopifyPlugin（/products/{handle}.json API、バリアント価格抽出）
- 5.3: HTMLParserPlugin（PaymentInfoExtractorフォールバック）
- 5.4: OCRPlugin（ROI検出、価格パターンマッチング、証拠レコード生成）
- 5.5: Property tests — DataExtractor プラグイン（in_progress、次回継続）
- advanced-dark-pattern-detection requirements.md 作成（14要件）

## Decisions Made
- **advanced-dark-pattern-detectionは別specで管理**: crawl-pipeline-architectureはインフラ層、検知ロジックはアプリケーション層で関心が異なる。LLM連携は外部API依存があり独立イテレーションが必要。4アプローチを段階的リリース可能。
- **4つの検知プラグインのステージ配置**: CSSVisualPlugin→DataExtractor、LLMClassifierPlugin→DataExtractor（OCR後）、JourneyPlugin→PageFetcher（PreCaptureScript後）、UITrapPlugin→Validator（ContractComparison後）
- **DarkPatternScoreの加重配分**: CSS Visual 0.25、LLM 0.30、Journey 0.25、UI Trap 0.20

## Topics Discussed
- CSS視覚的隠蔽検知（コントラスト比WCAG 2.0、フォントサイズ異常、オフスクリーン配置）
- LLMセマンティック分類（Gemini/Claude/GPT-4o、Vision API、レート制限）
- ユーザージャーニーベースの動的状態キャプチャ（カート追加後、チェックアウト時）
- UI/UXトラップ検知（Sneak into Basket、コンファームシェイミング日英辞書）

## Open Items
- crawl-pipeline-architecture Task 5.5（DataExtractor property tests）から再開
- advanced-dark-pattern-detection design.md / tasks.md 作成
- dark-pattern-notification design.md / tasks.md 作成

## Related Specs
- .kiro/specs/crawl-pipeline-architecture/
- .kiro/specs/advanced-dark-pattern-detection/
- .kiro/specs/dark-pattern-notification/

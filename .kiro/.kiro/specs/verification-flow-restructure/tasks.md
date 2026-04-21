# 実装計画: 検証フロー再構築 (verification-flow-restructure)

## 概要

`verification_service.py` の `run_verification()` を2パス構造に再構築する。
(1) 構造化データ価格比較パス（JSON-LD / Shopify API / Microdata / Open Graph → 契約条件比較）
(2) 視覚的証拠保全パス（バリアント別キャプチャ → ROI抽出 → OCR → EvidenceRecord保存）

**前提**: 以下は crawl-pipeline-architecture spec で実装済み:
- `StructuredDataPlugin`, `ShopifyPlugin`, `OCRPlugin`, `EvidencePreservationPlugin`, `DBStoragePlugin`
- `EvidenceRecord` モデル（`genai/src/models.py`）
- `VerificationResult` の新規フィールド（`structured_data`, `structured_data_violations`, `data_source`, `structured_data_status`, `evidence_status`）
- Alembic マイグレーション（`j5k6l7m8n9o0`）

**未実装**: `verification_service.py` の2パス再構築のみ。

## タスク

- [x] 1. StructuredDataParser の拡張
  - [x] 1.1 `genai/src/extractors/structured_data_parser.py` に Open Graph 解析メソッドを追加
    - `parse_open_graph(html: str) -> dict`: `og:price:amount`, `og:price:currency`, `product:price:amount` 等のメタタグを解析
    - _要件: 2.3_

  - [x] 1.2 Shopify 検出・取得メソッドを追加
    - `_detect_shopify(html: str) -> bool`: `Shopify.shop` または `cdn.shopify.com` の存在を検出
    - `fetch_shopify_product(url: str, html: str) -> dict | None`: Shopify 判定後 `/products/{handle}.json` を取得。404/403 時は None を返却
    - _要件: 3.1, 3.2, 3.3, 3.4_

  - [x] 1.3 全ソース統合メソッドを追加
    - `extract_all_variant_prices(html: str, url: str) -> StructuredPriceData`: JSON-LD > Shopify API > Microdata > Open Graph の優先順位で統合
    - `_resolve_priority(sources: dict) -> StructuredPriceData`: 優先順位に基づく価格統合
    - `VariantPrice` / `StructuredPriceData` dataclass を定義
    - _要件: 2.1, 2.2, 2.4, 2.5, 2.6_

  - [ ]* 1.4 プロパティテスト（Hypothesis）
    - **Property 3**: JSON-LD N件 Offer → N件バリアント抽出、data_source="json_ld"
    - **Property 4**: Shopify product.json N件バリアント → N件 VariantPrice 抽出
    - **Property 5**: `_detect_shopify` — Shopify.shop/cdn.shopify.com 含む ↔ True
    - **Property 6**: 複数ソース → 優先順位に従った data_source が採用される
    - テストファイル: `genai/tests/test_verification_structured_data.py`
    - _要件: 2.1, 2.2, 2.4, 2.5, 3.4_

- [x] 2. VerificationService の2パス再構築
  - [x] 2.1 `StructuredPathResult` / `EvidencePathResult` dataclass を定義
    - `genai/src/verification_service.py` に追加
    - `StructuredPathResult`: structured_price_data, violations, data_source, status, error_message
    - `EvidencePathResult`: evidence_records, status, error_message
    - _要件: 1.1, 1.5_

  - [x] 2.2 `_run_structured_data_path()` メソッドを実装
    - `extract_all_variant_prices()` で構造化データ抽出
    - 空の場合は `PaymentInfoExtractor` にフォールバック（`data_source = "html_fallback"`）
    - `_compare_variants()` で全バリアント価格を契約条件と比較
    - _要件: 2.1-2.6, 4.1-4.3, 5.1-5.4_

  - [x] 2.3 `_run_evidence_path()` メソッドを実装
    - バリアント別キャプチャ（PreCaptureScript 設定時）または単一キャプチャ
    - ROI検出 → 切り出し → OCR → EvidenceRecord 生成
    - 途中エラー時は取得済みレコードを返却
    - _要件: 6.1-6.5, 7.1-7.5, 8.1-8.4_

  - [x] 2.4 `_compare_variants()` メソッドを実装
    - 全バリアント価格を ContractCondition.prices と個別比較
    - 違反レコード（variant_name, field, contract_value, actual_value, severity, data_source）を生成
    - 違反数 + 一致数 = 全バリアント数の不変条件を維持
    - _要件: 5.1-5.4_

  - [x] 2.5 `run_verification()` を2パス並行実行に変更
    - `asyncio.gather(..., return_exceptions=True)` で両パスを並行実行
    - `_merge_results()` で両パスの結果を統合
    - 一方のパス失敗時は `status = "partial_failure"`、両方失敗時は `status = "failure"`
    - _要件: 1.1-1.5_

  - [ ]* 2.6 プロパティテスト（Hypothesis）
    - **Property 1**: 一方のパスが例外送出 → 他方は正常完了し status フィールドが設定される
    - **Property 7**: 構造化データなし → PaymentInfoExtractor 呼び出し、data_source="html_fallback"
    - **Property 8**: N件バリアント → 違反数 + 一致数 = N
    - **Property 13**: K件 EvidenceRecord → 全て同一 verification_result_id、有効な evidence_type
    - テストファイル: `genai/tests/test_verification_service_restructure.py`
    - _要件: 1.2, 1.3, 4.1, 4.2, 5.1-5.3, 8.2, 8.3_

- [x] 3. チェックポイント - 2パス実装の検証
  - 全テストが通ることを確認し、不明点があればユーザに質問する。

- [x] 4. API スキーマ拡張と検証結果 API 更新
  - [x] 4.1 `genai/src/api/schemas.py` に `EvidenceRecordResponse` スキーマを追加
    - id, verification_result_id, variant_name, screenshot_path, roi_image_path, ocr_text, ocr_confidence, evidence_type, created_at
    - _要件: 11.1-11.5_

  - [x] 4.2 `genai/src/api/verification.py` の検証結果レスポンスに新規フィールドを追加
    - `structured_data`, `structured_data_violations`, `data_source`, `structured_data_status`, `evidence_status`, `evidence_records` を `_format_verification_result()` に追加
    - 新規フィールドが NULL の場合は `null` として返却（後方互換性）
    - _要件: 11.1-11.5, 10.1, 10.2_

  - [ ]* 4.3 プロパティテスト（Hypothesis）
    - **Property 14**: 新規フィールドが NULL の VerificationResult → 既存フィールドが変更なし、新規フィールドは null
    - **Property 15**: 新規フィールドが非 NULL → API レスポンスに全フィールドが含まれる
    - テストファイル: `genai/tests/test_verification_api_restructure.py`
    - _要件: 10.1, 10.2, 11.1-11.5_

- [x] 5. PreCaptureScript ラベル拡張の確認
  - [x] 5.1 `genai/src/pipeline/plugins/pre_capture_script_plugin.py` の `label` フィールド対応を確認
    - label 付きアクション → variant_name = label
    - label なし → variant_name = `step_{index+1}`
    - ラウンドトリップシリアライズの確認
    - _要件: 12.1-12.4_

  - [ ]* 5.2 プロパティテスト（Hypothesis）
    - **Property 11**: label あり → variant_name = label、label なし → variant_name = step_{N}
    - **Property 12**: PreCaptureScript JSON ラウンドトリップ（label フィールド付き）
    - テストファイル: `genai/tests/test_verification_pre_capture.py`
    - _要件: 12.2, 12.3, 12.4_

- [x] 6. 最終チェックポイント - 全体検証
  - 全テストが通ることを確認し、不明点があればユーザに質問する。

## 備考

- `*` マーク付きのタスクはオプション（MVP では省略可能）
- crawl-pipeline-architecture spec で実装済みのコンポーネント（StructuredDataPlugin, ShopifyPlugin, EvidenceRecord モデル等）は再実装不要
- `verification_service.py` は旧来の単一パス実装のままのため、2パス再構築が主要作業
- 後方互換性: 新規フィールドは全て nullable、既存フィールドは変更なし

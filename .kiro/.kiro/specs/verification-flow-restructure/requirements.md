# Requirements Document

## Introduction

決済条件監視システムの検証フロー（`verification_service.py` の `run_verification()`）を再構築する。現在のフローはスクリーンショット（OCR）ベースで価格比較を行っているが、オプション選択で価格が変動するサイト（Shopify等）では差分が出てしまう問題がある。

本改修では検証フローの役割を明確に分離する:
- **価格・決済条件比較**: HTML構造化データ（JSON-LD, microdata, Shopify product.json等）から全バリアント価格を抽出し、契約条件と比較する（主手段）
- **視覚的不正検出・証拠保全**: キャプチャ + OCR により、DOMからは見えない画像埋め込み文言や小さい文字の縛り条件など、視覚的な不正の証拠を保全する（補助手段）

2つの検証パスを独立して実行し、結果を統合することで、バリアント価格変動による誤検知を排除しつつ、視覚的不正の検出能力を維持する。

## Glossary

- **VerificationService**: 検証フロー全体を制御するサービスクラス（`genai/src/verification_service.py`）
- **StructuredDataParser**: JSON-LD および Microdata 形式の構造化データを解析するコンポーネント（`genai/src/extractors/structured_data_parser.py`）
- **PaymentInfoExtractor**: HTML要素から決済情報を抽出するコンポーネント（`genai/src/extractors/payment_info_extractor.py`）
- **ScreenshotManager**: Playwright を使用してサイトのスクリーンショットを撮影するコンポーネント（`genai/src/screenshot_manager.py`）
- **OCREngine**: スクリーンショット画像からテキストを抽出するコンポーネント（`genai/src/ocr_engine.py`）
- **VerificationResult**: 検証結果を格納するDBモデル（`genai/src/models.py`）
- **ContractCondition**: サイトの契約条件を格納するDBモデル（`genai/src/models.py`）
- **MonitoringSite**: 監視対象サイトを表すDBモデル（`genai/src/models.py`）
- **StructuredPriceData**: 構造化データから抽出された全バリアント価格情報を表すデータ構造
- **EvidenceRecord**: 証拠保全データ（キャプチャ画像、切り出し画像、OCRテキスト等）を格納するデータ構造
- **ROI**: Region of Interest（関心領域）。キャプチャ画像から切り出す特定の矩形領域
- **PreCaptureScript**: サイトごとに登録可能なカスタムPlaywrightアクションのJSON定義（crawl-modal-automation specで追加予定）
- **VariantCapture**: バリアント別に取得されたスクリーンショットとそのメタデータの組み合わせ

## Requirements

### Requirement 1: 検証フローの2パス分離

**User Story:** As a 検証運用者, I want 価格比較と視覚的不正検出が独立した検証パスとして実行されること, so that 各検証の役割が明確になり、バリアント価格変動による誤検知が排除される。

#### Acceptance Criteria

1. THE VerificationService SHALL `run_verification()` メソッド内で「構造化データ価格比較パス」と「視覚的証拠保全パス」の2つの検証パスを独立して実行する
2. WHEN 構造化データ価格比較パスが失敗した場合, THE VerificationService SHALL 視覚的証拠保全パスを中断せずに実行する
3. WHEN 視覚的証拠保全パスが失敗した場合, THE VerificationService SHALL 構造化データ価格比較パスの結果を有効な検証結果として保持する
4. WHEN 両方の検証パスが完了した場合, THE VerificationService SHALL 両パスの結果を統合した VerificationResult を生成する
5. THE VerificationResult SHALL 各検証パスの成否を個別に記録するフィールドを持つ（`structured_data_status`, `evidence_status`）

### Requirement 2: 構造化データ優先の価格抽出

**User Story:** As a 検証運用者, I want 価格情報がHTML構造化データから優先的に抽出されること, so that オプション選択による価格変動に影響されない正確な価格比較ができる。

#### Acceptance Criteria

1. THE StructuredDataParser SHALL JSON-LD（`<script type="application/ld+json">`）から schema.org Product/Offer の全バリアント価格を抽出する
2. THE StructuredDataParser SHALL Shopify product.json（`/products/{handle}.json`）エンドポイントから全バリアントの価格情報を抽出する
3. THE StructuredDataParser SHALL Open Graph メタタグおよび Microdata 属性から補助的な価格情報を抽出する
4. THE StructuredDataParser SHALL 抽出した価格情報を StructuredPriceData として返却し、各価格にデータソース（`json_ld`, `shopify_api`, `microdata`, `open_graph`）を付与する
5. WHEN 複数のデータソースから同一商品の価格が取得された場合, THE StructuredDataParser SHALL JSON-LD > Shopify API > Microdata > Open Graph の優先順位で価格を採用する
6. WHEN 構造化データから価格が取得できない場合, THE StructuredDataParser SHALL 空の StructuredPriceData を返却する

### Requirement 3: Shopify product.json からのバリアント価格抽出

**User Story:** As a 検証運用者, I want Shopifyサイトの全バリアント価格が自動的に取得されること, so that オプション選択による価格差分が正確に把握できる。

#### Acceptance Criteria

1. WHEN 対象サイトのURLがShopifyサイトである場合, THE StructuredDataParser SHALL `/products/{handle}.json` エンドポイントにHTTPリクエストを送信する
2. WHEN Shopify product.json が正常に取得できた場合, THE StructuredDataParser SHALL `variants` 配列から各バリアントの `title`, `price`, `compare_at_price`, `sku`, `option1`, `option2`, `option3` を抽出する
3. WHEN Shopify product.json のレスポンスが404またはアクセス拒否の場合, THE StructuredDataParser SHALL エラーをログに記録し、他のデータソースにフォールバックする
4. THE StructuredDataParser SHALL Shopifyサイトの判定を、HTMLソース内の `Shopify.shop` 変数の存在、または `cdn.shopify.com` へのリソース参照の有無で行う

### Requirement 4: 構造化データ不在時のフォールバック

**User Story:** As a 検証運用者, I want 構造化データが取得できないサイトでも価格比較が行われること, so that 全サイトで検証が継続される。

#### Acceptance Criteria

1. WHEN StructuredDataParser が空の StructuredPriceData を返却した場合, THE VerificationService SHALL PaymentInfoExtractor による従来のHTML解析で価格情報を抽出する
2. WHEN フォールバックが発生した場合, THE VerificationService SHALL 検証結果のデータソースフィールドに `"html_fallback"` を記録する
3. THE VerificationService SHALL フォールバック時も構造化データ抽出時と同一の契約条件比較ロジックを適用する

### Requirement 5: 構造化データと契約条件の比較

**User Story:** As a 検証運用者, I want 構造化データから抽出した全バリアント価格が契約条件と比較されること, so that いずれかのバリアントが契約違反している場合に検出できる。

#### Acceptance Criteria

1. WHEN StructuredPriceData に複数のバリアント価格が含まれる場合, THE VerificationService SHALL 各バリアント価格を ContractCondition の prices と個別に比較する
2. WHEN いずれかのバリアント価格が契約条件と一致しない場合, THE VerificationService SHALL 不一致のバリアント名、契約価格、実際の価格を含む差異レコードを生成する
3. WHEN 全バリアント価格が契約条件の範囲内である場合, THE VerificationService SHALL 価格比較結果を「一致」として記録する
4. THE VerificationService SHALL 比較結果に使用したデータソース（`json_ld`, `shopify_api`, `microdata`, `html_fallback`）を記録する

### Requirement 6: バリアント別キャプチャ

**User Story:** As a 検証運用者, I want 各バリアントのスクリーンショットが個別に取得されること, so that バリアントごとの視覚的な証拠が保全される。

#### Acceptance Criteria

1. WHEN MonitoringSite に PreCaptureScript が設定されている場合, THE ScreenshotManager SHALL PreCaptureScript の各ステップ実行後にスクリーンショットを取得する
2. THE ScreenshotManager SHALL 各キャプチャにバリアント名（PreCaptureScript のステップラベル）をメタデータとして付与する
3. WHEN 1回のクロールで複数のキャプチャが取得された場合, THE ScreenshotManager SHALL 全キャプチャのファイルパスとメタデータをリストとして返却する
4. WHEN MonitoringSite に PreCaptureScript が設定されていない場合, THE ScreenshotManager SHALL デフォルト状態での1回のキャプチャのみを取得する
5. IF バリアント別キャプチャの途中でエラーが発生した場合, THEN THE ScreenshotManager SHALL エラーをログに記録し、取得済みのキャプチャを有効な結果として返却する

### Requirement 7: 関心領域（ROI）の抽出

**User Story:** As a 検証運用者, I want キャプチャ画像から価格表示エリアや注意書きエリアが自動的に切り出されること, so that 証拠保全に必要な部分のみが効率的に保存される。

#### Acceptance Criteria

1. THE OCREngine SHALL キャプチャ画像から価格表示領域、注意書き領域、定期購入条件領域を関心領域（ROI）として検出する
2. WHEN ROI が検出された場合, THE OCREngine SHALL 各 ROI を個別の画像ファイルとして切り出して保存する
3. THE OCREngine SHALL 各 ROI 画像に対して OCR を実行し、抽出テキストと信頼度スコアを返却する
4. WHEN ROI が検出されない場合, THE OCREngine SHALL キャプチャ画像全体に対して従来の OCR 処理を実行する
5. THE OCREngine SHALL ROI の検出に、テキストブロックの位置情報（bbox）と価格パターン（通貨記号 + 数値）のマッチングを使用する

### Requirement 8: 証拠保全データの保存

**User Story:** As a 検証運用者, I want 視覚的不正検出の証拠データがDBに構造化して保存されること, so that 後から証拠を参照・検索できる。

#### Acceptance Criteria

1. THE EvidenceRecord SHALL 以下のフィールドを持つ: `verification_result_id`（外部キー）, `variant_name`（バリアント名）, `screenshot_path`（元キャプチャ画像パス）, `roi_image_path`（切り出し画像パス、nullable）, `ocr_text`（OCR抽出テキスト）, `ocr_confidence`（OCR信頼度）, `evidence_type`（証拠種別: `price_display`, `terms_notice`, `subscription_condition`, `general`）, `created_at`（タイムスタンプ）
2. THE VerificationService SHALL 各バリアントキャプチャおよび各 ROI に対して EvidenceRecord を生成し、DBに保存する
3. WHEN 1回の検証で複数の EvidenceRecord が生成された場合, THE VerificationService SHALL 全レコードを同一の VerificationResult に関連付ける
4. THE EvidenceRecord テーブル SHALL `verification_result_id` および `evidence_type` にインデックスを持つ

### Requirement 9: VerificationResult モデルの拡張

**User Story:** As a 開発者, I want VerificationResult モデルが新しい検証フローの結果を格納できること, so that 構造化データ比較と証拠保全の両方の結果が記録される。

#### Acceptance Criteria

1. THE VerificationResult SHALL `structured_data` フィールド（JSONB型、nullable）を持ち、構造化データから抽出した価格情報を格納する
2. THE VerificationResult SHALL `structured_data_violations` フィールド（JSONB型、nullable）を持ち、構造化データベースの契約違反情報を格納する
3. THE VerificationResult SHALL `data_source` フィールド（String型）を持ち、価格比較に使用したデータソース（`json_ld`, `shopify_api`, `microdata`, `html_fallback`）を記録する
4. THE VerificationResult SHALL `structured_data_status` フィールド（String型、nullable）を持ち、構造化データ検証パスの成否を記録する
5. THE VerificationResult SHALL `evidence_status` フィールド（String型、nullable）を持ち、証拠保全パスの成否を記録する
6. THE VerificationResult SHALL 既存の `html_data`, `ocr_data`, `html_violations`, `ocr_violations`, `discrepancies` フィールドを維持し、後方互換性を保つ

### Requirement 10: 後方互換性の維持

**User Story:** As a 検証運用者, I want 既存の検証結果データが新しいフローでも正常に参照できること, so that 過去の検証履歴が失われない。

#### Acceptance Criteria

1. THE VerificationResult の新規フィールド SHALL 全て nullable として定義され、既存レコードに影響を与えない
2. WHEN 新規フィールドが NULL の VerificationResult が参照された場合, THE API SHALL 従来のレスポンス形式と互換性のあるレスポンスを返却する
3. THE Alembic マイグレーション SHALL 既存の `verification_results` テーブルに新規カラムを追加し、既存データを保持する
4. THE Alembic マイグレーション SHALL ダウングレード時に追加カラムを削除し、既存カラムのデータを保持する

### Requirement 11: 検証結果APIの拡張

**User Story:** As a フロントエンド開発者, I want 検証結果APIが構造化データ比較結果と証拠保全データを返却すること, so that フロントエンドで新しい検証結果を表示できる。

#### Acceptance Criteria

1. THE 検証結果APIレスポンス SHALL `structured_data` フィールドに構造化データから抽出した価格情報を含む
2. THE 検証結果APIレスポンス SHALL `structured_data_violations` フィールドに構造化データベースの契約違反情報を含む
3. THE 検証結果APIレスポンス SHALL `data_source` フィールドに使用したデータソースを含む
4. THE 検証結果APIレスポンス SHALL `evidence_records` フィールドに関連する証拠保全データのリストを含む
5. WHEN 検証結果に新規フィールドが存在しない場合（既存データ）, THE API SHALL 新規フィールドを `null` として返却する

### Requirement 12: PreCaptureScript ステップラベルの拡張

**User Story:** As a 検証運用者, I want PreCaptureScript の各ステップにラベルを付与できること, so that バリアント別キャプチャのメタデータとして使用できる。

#### Acceptance Criteria

1. THE PreCaptureScript のアクションオブジェクト SHALL オプショナルな `label` フィールド（文字列）を持つ
2. WHEN `label` フィールドが設定されたアクションの実行後にキャプチャが取得された場合, THE ScreenshotManager SHALL `label` の値をキャプチャのバリアント名メタデータとして使用する
3. WHEN `label` フィールドが設定されていない場合, THE ScreenshotManager SHALL アクションのインデックス番号（`step_1`, `step_2` 等）をバリアント名として使用する
4. FOR ALL 有効な PreCaptureScript JSON（`label` フィールド付き）, THE ScreenshotManager SHALL JSON をパースしてアクションリストに変換し、再度JSONにシリアライズした場合に同等のアクションリストが得られる（ラウンドトリップ特性）


### Requirement 13: OCR スマート・リトライ

**User Story:** As a 検証運用者, I want OCR信頼度が0%だった場合にスクリーンショットを再取得してOCRをリトライすること, so that JSレンダリング遅延による一時的なOCR失敗を自動回復できる。

#### Acceptance Criteria

1. WHEN 視覚的証拠保全パスのOCR結果の信頼度が0%の場合, THE VerificationService SHALL スマート・リトライを1回だけ実行する
2. WHEN スマート・リトライが発動した場合, THE VerificationService SHALL 5秒間待機してからスクリーンショットを再取得する
3. WHEN スクリーンショットの再取得に成功した場合, THE VerificationService SHALL 再取得した画像に対してOCRを実行する
4. WHEN リトライOCRの信頼度が0%より大きい場合, THE VerificationService SHALL リトライ結果で元の結果を上書きする
5. WHEN リトライOCRの信頼度が0%のままの場合, THE VerificationService SHALL 元の結果を維持する（2回目のリトライは行わない）
6. IF スマート・リトライ中にエラーが発生した場合, THEN THE VerificationService SHALL エラーを無視し、元の結果を維持する


### Requirement 14: OCR 失敗時の審査キュー自動投入

**User Story:** As a 検証運用者, I want スマート・リトライ後もOCR信頼度が0%のままの案件が自動的に審査キューに投入されること, so that 人間による目視確認が漏れなく行われる。

#### Acceptance Criteria

1. WHEN スマート・リトライ後もOCR信頼度が0%の場合, THE VerificationService SHALL alert_type="ocr_failure"、severity="medium" のアラートを生成する
2. WHEN OCR失敗アラートが生成された場合, THE VerificationService SHALL ReviewService.enqueue_from_alert() を呼び出して審査キューに pending 状態で投入する
3. THE 審査キューに投入される ReviewItem SHALL review_type="violation"、priority="medium" で作成される
4. IF 審査キュー投入中にエラーが発生した場合, THEN THE VerificationService SHALL エラーを無視し、検証結果の保存には影響させない
5. THE OCR失敗アラートのメッセージ SHALL サイト名とURLを含み、目視確認が必要であることを明示する

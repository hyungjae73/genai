# Requirements Document

## Introduction

決済条件監視システムのクロールフロー全体を、パイプライン＋プラグインアーキテクチャに再設計する。現在の `tasks.py` 内のモノリシックな `_crawl_and_validate_site_async()`（250行超）を、4ステージ構成の `CrawlPipeline` に分解し、各ステージをプラグインで構成する。

本specは以下の2つの既存specを統合・上位互換する上位specである:
- `crawl-modal-automation`: ロケール設定、モーダル自動閉じ、プレキャプチャスクリプト → PageFetcherステージのプラグインとして統合
- `verification-flow-restructure`: 構造化データ抽出、2パス検証、証拠保全 → DataExtractor / Validator / Reporterステージのプラグインとして統合

数万〜数十万サイト規模のスケーラビリティに対応するため、Playwrightブラウザプール、Celeryキュー分離、優先度キュー、デルタクロール、ベンダー非依存オブジェクトストレージ（S3互換API経由でAWS S3/GCS/MinIO対応）、バッチスケジューリング、バルクDB操作の7つのスケーラビリティ施策を導入する。

## Glossary

- **CrawlPipeline**: サイト単位のクロール処理を4ステージで実行するパイプラインオーケストレータ
- **CrawlPlugin**: 各ステージ内で実行されるプラグインの抽象基底クラス。`execute(ctx)` と `should_run(ctx)` を持つ
- **CrawlContext**: パイプライン全体で共有されるコンテキストオブジェクト。サイト情報、HTML、スクリーンショット、抽出データ、違反情報、証拠レコード、エラー、メタデータを保持する
- **CrawlScheduler**: Celery Beat によるスケジュール管理コンポーネント。バッチ分割と時間分散を制御する
- **BatchDispatcher**: サイト群をバッチに分割し、優先度に基づいてCeleryキューにディスパッチするコンポーネント
- **BrowserPool**: Playwright ブラウザインスタンスをワーカー内でプールし、タスク間で再利用するコンポーネント
- **MonitoringSite**: 監視対象サイトを表すDBモデル（`genai/src/models.py`）
- **VerificationResult**: 検証結果を格納するDBモデル（`genai/src/models.py`）
- **ContractCondition**: サイトの契約条件を格納するDBモデル（`genai/src/models.py`）
- **EvidenceRecord**: 証拠保全データ（キャプチャ画像、切り出し画像、OCRテキスト等）を格納する新規DBモデル
- **CrawlSchedule**: サイトごとのクロールスケジュール・優先度・デルタクロール情報を格納する新規DBモデル
- **StructuredPriceData**: 構造化データから抽出された全バリアント価格情報を表すデータ構造
- **VariantCapture**: バリアント別に取得されたスクリーンショットとそのメタデータの組み合わせ
- **ROI**: Region of Interest（関心領域）。キャプチャ画像から切り出す特定の矩形領域
- **PreCaptureScript**: サイトごとに登録可能なカスタムPlaywrightアクションのJSON定義
- **ScheduleTab**: SiteDetailPanel 内のクロールスケジュール管理タブ。優先度、クロール間隔、プレキャプチャスクリプトの表示・編集を行う

## Requirements

### Requirement 1: CrawlPlugin 抽象インターフェースとCrawlContext

**User Story:** As a 開発者, I want パイプラインのプラグインが統一されたインターフェースで実装されること, so that 新しいプラグインの追加や既存プラグインの差し替えが容易になる。

#### Acceptance Criteria

1. THE CrawlPlugin SHALL `execute(ctx: CrawlContext) -> CrawlContext` 非同期メソッドを抽象メソッドとして定義する
2. THE CrawlPlugin SHALL `should_run(ctx: CrawlContext) -> bool` メソッドを抽象メソッドとして定義し、プラグインの実行条件を判定する
3. THE CrawlContext SHALL `site`（MonitoringSite）, `url`（str）, `html_content`（str, nullable）, `screenshots`（list[VariantCapture]）, `extracted_data`（dict）, `violations`（list）, `evidence_records`（list）, `errors`（list）, `metadata`（dict）フィールドを持つ
4. WHEN CrawlPlugin の `execute()` が CrawlContext を受け取った場合, THE CrawlPlugin SHALL 処理結果を CrawlContext に追記して返却し、他プラグインが書き込んだフィールドを破壊しない
5. THE CrawlContext の `metadata` フィールド SHALL プラグイン間のデータ受け渡しに使用され、各プラグインはプラグイン名をプレフィックスとしたキーでデータを格納する
6. FOR ALL 有効な CrawlContext オブジェクト, THE CrawlContext SHALL dict にシリアライズし再度 CrawlContext に復元した場合に同等のオブジェクトが得られる（ラウンドトリップ特性）

### Requirement 2: CrawlPipeline オーケストレータ

**User Story:** As a 開発者, I want サイト単位のクロール処理が4ステージのパイプラインとして実行されること, so that 各ステージを独立してスケール・テスト・デバッグできる。

#### Acceptance Criteria

1. THE CrawlPipeline SHALL 4つのステージを以下の順序で実行する: (1) PageFetcher → (2) DataExtractor → (3) Validator → (4) Reporter
2. WHEN 各ステージが実行される場合, THE CrawlPipeline SHALL ステージに登録された全プラグインの `should_run()` を評価し、`True` を返したプラグインのみ `execute()` を呼び出す
3. WHEN あるステージ内のプラグインがエラーを発生させた場合, THE CrawlPipeline SHALL エラーを CrawlContext の `errors` リストに記録し、同一ステージ内の残りのプラグインの実行を継続する
4. IF PageFetcher ステージで HTML 取得に失敗した場合, THEN THE CrawlPipeline SHALL DataExtractor ステージをスキップし、エラー情報を Reporter ステージに渡す
5. THE CrawlPipeline SHALL 各ステージの開始時刻・終了時刻・実行プラグイン名を CrawlContext の `metadata` に記録する
6. WHEN パイプライン全体の実行が完了した場合, THE CrawlPipeline SHALL 最終的な CrawlContext を返却する
7. THE CrawlPipeline SHALL 全プラグインを常に登録した状態で動作し、各プラグインの `should_run()` が実行条件（サイト設定、データ有無、規模閾値等）に基づいて段階的に有効化される設計とする。スケール対応プラグイン（ObjectStoragePlugin, バルクDB等）は小規模時には `should_run()` が `False` を返し、規模が閾値を超えた時点で自動的に有効化される

### Requirement 3: PageFetcher ステージ — LocalePlugin

**User Story:** As a クロール運用者, I want クロール時にブラウザのロケールとAccept-Languageヘッダーが日本語に設定されること, so that 言語選択モーダルの表示を事前に抑制できる。

#### Acceptance Criteria

1. WHEN LocalePlugin が実行される場合, THE LocalePlugin SHALL Playwright ページの `locale` を `"ja-JP"` に設定する
2. WHEN LocalePlugin が実行される場合, THE LocalePlugin SHALL `extra_http_headers` に `{"Accept-Language": "ja-JP,ja;q=0.9"}` を設定する
3. WHILE ロケール設定が適用された状態で, THE LocalePlugin SHALL 従来と同じビューポートサイズ（1920x1080）とデバイススケールファクター（2）を維持する
4. THE LocalePlugin の `should_run()` SHALL 常に `True` を返す

### Requirement 4: PageFetcher ステージ — ModalDismissPlugin

**User Story:** As a クロール運用者, I want クロール時にページ上のモーダルやオーバーレイが自動的に閉じられること, so that スクリーンショットにモーダルが写り込まない。

#### Acceptance Criteria

1. WHEN ページの読み込みが完了した後, THE ModalDismissPlugin SHALL ページ上のモーダル要素を検出する
2. THE ModalDismissPlugin SHALL 以下のセレクタパターンでモーダル要素を検出する: `[role="dialog"]`, `[role="alertdialog"]`, `.modal`, `.overlay`, `[class*="cookie"]`, `[class*="consent"]`, `[id*="cookie"]`, `[id*="consent"]`
3. WHEN モーダル要素が検出された場合, THE ModalDismissPlugin SHALL モーダル内の閉じるボタン（`button[aria-label*="close"]`, `.close`, `button[class*="close"]`, `button[class*="dismiss"]`, `button[class*="accept"]`）をクリックして閉じる
4. WHEN 閉じるボタンが見つからない場合, THE ModalDismissPlugin SHALL Escapeキーの送信を試みてモーダルを閉じる
5. WHEN モーダルの閉じ処理が完了した後, THE ModalDismissPlugin SHALL 500ミリ秒待機してから次の処理に進む
6. IF モーダルの検出または閉じ処理中にエラーが発生した場合, THEN THE ModalDismissPlugin SHALL エラーを CrawlContext の `errors` リストに記録し、パイプラインの実行を中断しない
7. THE ModalDismissPlugin の `should_run()` SHALL 常に `True` を返す

### Requirement 5: PageFetcher ステージ — PreCaptureScriptPlugin

**User Story:** As a クロール運用者, I want サイトごとにカスタムのPlaywrightアクションをプラグインとして実行できること, so that 汎用ロジックでは対応できないサイト固有の操作を自動化できる。

#### Acceptance Criteria

1. THE PreCaptureScriptPlugin の `should_run()` SHALL CrawlContext の `site` に `pre_capture_script` が設定されている場合のみ `True` を返す
2. WHEN PreCaptureScriptPlugin が実行される場合, THE PreCaptureScriptPlugin SHALL `pre_capture_script` JSON を解析し、アクションを定義順に逐次実行する
3. THE PreCaptureScriptPlugin SHALL 以下のアクション型をサポートする: `click`（セレクタ指定の要素クリック）, `wait`（ミリ秒指定の待機）, `select`（セレクタとvalue指定のセレクト操作）, `type`（セレクタとtext指定のテキスト入力）
4. WHEN アクションにオプショナルな `label` フィールドが設定されている場合, THE PreCaptureScriptPlugin SHALL アクション実行後にスクリーンショットを取得し、`label` の値をバリアント名メタデータとして CrawlContext の `screenshots` に追加する
5. IF PreCaptureScript のアクション実行中にエラーが発生した場合, THEN THE PreCaptureScriptPlugin SHALL エラーを CrawlContext の `errors` リストに記録し、残りのアクションをスキップする
6. IF PreCaptureScript のJSON形式が不正な場合, THEN THE PreCaptureScriptPlugin SHALL バリデーションエラーを CrawlContext の `errors` リストに記録し、実行をスキップする
7. FOR ALL 有効な PreCaptureScript JSON, THE PreCaptureScriptPlugin SHALL JSON をパースしてアクションリストに変換し、再度JSONにシリアライズした場合に同等のアクションリストが得られる（ラウンドトリップ特性）

### Requirement 6: DataExtractor ステージ — StructuredDataPlugin

**User Story:** As a 検証運用者, I want 価格情報がHTML構造化データから優先的に抽出されること, so that オプション選択による価格変動に影響されない正確な価格比較ができる。

#### Acceptance Criteria

1. THE StructuredDataPlugin SHALL JSON-LD（`<script type="application/ld+json">`）から schema.org Product/Offer の全バリアント価格を抽出する
2. THE StructuredDataPlugin SHALL Open Graph メタタグおよび Microdata 属性から補助的な価格情報を抽出する
3. THE StructuredDataPlugin SHALL 抽出した価格情報を CrawlContext の `extracted_data` に StructuredPriceData として格納し、各価格にデータソース（`json_ld`, `shopify_api`, `microdata`, `open_graph`）を付与する
4. WHEN 複数のデータソースから同一商品の価格が取得された場合, THE StructuredDataPlugin SHALL JSON-LD > Shopify API > Microdata > Open Graph の優先順位で価格を採用する
5. WHEN 構造化データから価格が取得できない場合, THE StructuredDataPlugin SHALL CrawlContext の `metadata` に `structured_data_empty: True` を設定する
6. THE StructuredDataPlugin の `should_run()` SHALL CrawlContext の `html_content` が存在する場合に `True` を返す

### Requirement 7: DataExtractor ステージ — ShopifyPlugin

**User Story:** As a 検証運用者, I want Shopifyサイトの全バリアント価格が自動的に取得されること, so that オプション選択による価格差分が正確に把握できる。

#### Acceptance Criteria

1. THE ShopifyPlugin の `should_run()` SHALL CrawlContext の `html_content` 内に `Shopify.shop` 変数または `cdn.shopify.com` へのリソース参照が存在する場合に `True` を返す
2. WHEN ShopifyPlugin が実行される場合, THE ShopifyPlugin SHALL `/products/{handle}.json` エンドポイントにHTTPリクエストを送信する
3. WHEN Shopify product.json が正常に取得できた場合, THE ShopifyPlugin SHALL `variants` 配列から各バリアントの `title`, `price`, `compare_at_price`, `sku`, `option1`, `option2`, `option3` を抽出し、CrawlContext の `extracted_data` に追加する
4. IF Shopify product.json のレスポンスが404またはアクセス拒否の場合, THEN THE ShopifyPlugin SHALL エラーを CrawlContext の `errors` リストに記録し、パイプラインの実行を中断しない

### Requirement 8: DataExtractor ステージ — HTMLParserPlugin

**User Story:** As a 検証運用者, I want 構造化データが取得できないサイトでも価格比較が行われること, so that 全サイトで検証が継続される。

#### Acceptance Criteria

1. THE HTMLParserPlugin の `should_run()` SHALL CrawlContext の `metadata` に `structured_data_empty: True` が設定されている場合に `True` を返す
2. WHEN HTMLParserPlugin が実行される場合, THE HTMLParserPlugin SHALL 従来の PaymentInfoExtractor によるHTML解析で価格情報を抽出する
3. WHEN フォールバック抽出が完了した場合, THE HTMLParserPlugin SHALL CrawlContext の `extracted_data` にデータソース `"html_fallback"` を付与して格納する

### Requirement 9: DataExtractor ステージ — OCRPlugin

**User Story:** As a 検証運用者, I want スクリーンショットからOCRで視覚的証拠が抽出されること, so that DOMからは見えない画像埋め込み文言や小さい文字の縛り条件を検出できる。

#### Acceptance Criteria

1. THE OCRPlugin の `should_run()` SHALL CrawlContext の `screenshots` が1件以上存在する場合に `True` を返す
2. WHEN OCRPlugin が実行される場合, THE OCRPlugin SHALL 各スクリーンショットから価格表示領域、注意書き領域、定期購入条件領域を関心領域（ROI）として検出する
3. WHEN ROI が検出された場合, THE OCRPlugin SHALL 各 ROI を個別の画像ファイルとして切り出し、OCR を実行して抽出テキストと信頼度スコアを CrawlContext の `evidence_records` に追加する
4. WHEN ROI が検出されない場合, THE OCRPlugin SHALL スクリーンショット全体に対して OCR を実行し、結果を CrawlContext の `evidence_records` に追加する
5. THE OCRPlugin SHALL ROI の検出に、テキストブロックの位置情報（bbox）と価格パターン（通貨記号 + 数値）のマッチングを使用する

### Requirement 10: Validator ステージ — ContractComparisonPlugin

**User Story:** As a 検証運用者, I want 構造化データから抽出した全バリアント価格が契約条件と比較されること, so that いずれかのバリアントが契約違反している場合に検出できる。

#### Acceptance Criteria

1. THE ContractComparisonPlugin の `should_run()` SHALL CrawlContext の `extracted_data` に価格情報が存在する場合に `True` を返す
2. WHEN ContractComparisonPlugin が実行される場合, THE ContractComparisonPlugin SHALL CrawlContext の `extracted_data` 内の各バリアント価格を ContractCondition の prices と個別に比較する
3. WHEN いずれかのバリアント価格が契約条件と一致しない場合, THE ContractComparisonPlugin SHALL 不一致のバリアント名、契約価格、実際の価格、データソースを含む差異レコードを CrawlContext の `violations` に追加する
4. WHEN 全バリアント価格が契約条件の範囲内である場合, THE ContractComparisonPlugin SHALL 価格比較結果を「一致」として CrawlContext の `metadata` に記録する

### Requirement 11: Validator ステージ — EvidencePreservationPlugin

**User Story:** As a 検証運用者, I want 視覚的不正検出の証拠データが構造化して保全されること, so that 後から証拠を参照・検索できる。

#### Acceptance Criteria

1. THE EvidencePreservationPlugin の `should_run()` SHALL CrawlContext の `evidence_records` が1件以上存在する場合に `True` を返す
2. WHEN EvidencePreservationPlugin が実行される場合, THE EvidencePreservationPlugin SHALL 各 evidence_record に `evidence_type`（`price_display`, `terms_notice`, `subscription_condition`, `general`）を分類して付与する
3. THE EvidencePreservationPlugin SHALL 各 evidence_record に `verification_result_id`, `variant_name`, `screenshot_path`, `roi_image_path`（nullable）, `ocr_text`, `ocr_confidence`, `evidence_type`, `created_at` フィールドを設定する
4. WHEN 1回のパイプライン実行で複数の evidence_record が生成された場合, THE EvidencePreservationPlugin SHALL 全レコードを同一の VerificationResult に関連付ける

### Requirement 12: Reporter ステージ — DBStoragePlugin

**User Story:** As a 開発者, I want パイプラインの実行結果がDBに効率的に保存されること, so that 大量サイトのクロール結果を高速に永続化できる。

#### Acceptance Criteria

1. THE DBStoragePlugin SHALL CrawlContext の検証結果を VerificationResult としてDBに保存する
2. THE DBStoragePlugin SHALL CrawlContext の evidence_records を EvidenceRecord テーブルにバルクINSERTで保存する
3. THE DBStoragePlugin SHALL CrawlContext の violations を Violation テーブルにバルクINSERTで保存する
4. WHEN バルクINSERT中にエラーが発生した場合, THE DBStoragePlugin SHALL トランザクションをロールバックし、エラーを CrawlContext の `errors` リストに記録する
5. THE DBStoragePlugin の `should_run()` SHALL 常に `True` を返す

### Requirement 13: Reporter ステージ — ObjectStoragePlugin

**User Story:** As a 運用者, I want スクリーンショットと証拠画像がベンダー非依存のオブジェクトストレージに保存されること, so that AWS S3, Google Cloud Storage, MinIO 等のバックエンドを環境設定で切り替えられ、ワーカーを分散配置しても共有ファイルシステムが不要になる。

#### Acceptance Criteria

1. THE ObjectStoragePlugin の `should_run()` SHALL CrawlContext の `screenshots` または `evidence_records` に画像ファイルパスが存在する場合に `True` を返す
2. WHEN ObjectStoragePlugin が実行される場合, THE ObjectStoragePlugin SHALL S3互換API（MinIO SDK）を使用して全スクリーンショットと ROI 画像をオブジェクトストレージにアップロードする
3. THE ObjectStoragePlugin SHALL 環境変数（`STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET`, `STORAGE_REGION`）でバックエンドを設定可能とする
4. THE ObjectStoragePlugin SHALL 以下のバックエンドをエンドポイント設定のみで切り替え可能とする: AWS S3（`s3.amazonaws.com`）, Google Cloud Storage（`storage.googleapis.com`）, MinIO（`localhost:9000` 等）
5. WHEN アップロードが完了した場合, THE ObjectStoragePlugin SHALL CrawlContext 内のローカルファイルパスをオブジェクトストレージ URL に置換する
6. IF オブジェクトストレージへのアップロードに失敗した場合, THEN THE ObjectStoragePlugin SHALL エラーを CrawlContext の `errors` リストに記録し、ローカルファイルパスを維持する（フォールバック）
7. THE ObjectStoragePlugin SHALL アップロード先パスを `{bucket}/{site_id}/{date}/{filename}` 形式で構成する
8. THE docker-compose.yml SHALL ローカル開発用に MinIO サービスを含み、本番環境では AWS S3 または GCS に切り替え可能とする

### Requirement 14: Reporter ステージ — AlertPlugin

**User Story:** As a 運用者, I want 契約違反が検出された場合にアラートが自動生成されること, so that 違反を迅速に把握できる。

#### Acceptance Criteria

1. THE AlertPlugin の `should_run()` SHALL CrawlContext の `violations` が1件以上存在する場合に `True` を返す
2. WHEN AlertPlugin が実行される場合, THE AlertPlugin SHALL 各違反に対して Alert レコードを生成しDBに保存する
3. THE AlertPlugin SHALL アラートの severity を違反の種類に基づいて設定する（価格不一致: `warning`, 構造化データ取得失敗: `info`）

### Requirement 15: Playwright ブラウザプール

**User Story:** As a 運用者, I want Playwrightブラウザインスタンスがワーカー内で再利用されること, so that ブラウザ起動のオーバーヘッドが削減され、大量サイトのクロールが高速化される。

#### Acceptance Criteria

1. THE BrowserPool SHALL ワーカープロセス内で設定可能な数（デフォルト: 3）のブラウザインスタンスを保持する
2. WHEN CrawlPipeline の PageFetcher ステージがブラウザページを必要とする場合, THE BrowserPool SHALL プールからブラウザインスタンスを貸し出し、新しいページ（タブ）を生成して返却する
3. WHEN PageFetcher ステージが完了した場合, THE BrowserPool SHALL ページを閉じ、ブラウザインスタンスをプールに返却する
4. WHILE プール内の全ブラウザインスタンスが使用中の場合, THE BrowserPool SHALL インスタンスが返却されるまで待機する
5. IF ブラウザインスタンスがクラッシュした場合, THEN THE BrowserPool SHALL クラッシュしたインスタンスを破棄し、新しいインスタンスを生成してプールに追加する
6. WHEN ワーカープロセスが終了する場合, THE BrowserPool SHALL 全ブラウザインスタンスを正常に終了する

### Requirement 16: Celery キュー分離と水平スケーリング

**User Story:** As a 運用者, I want パイプラインの各ステージが独立したCeleryキューで実行されること, so that ステージごとに独立してワーカー数をスケールできる。

#### Acceptance Criteria

1. THE CrawlPipeline SHALL 4つの Celery キューを使用する: `crawl`（PageFetcher）, `extract`（DataExtractor）, `validate`（Validator）, `report`（Reporter）
2. THE celery_app の設定 SHALL 各キューのルーティングルールを定義し、タスクを適切なキューに振り分ける
3. THE docker-compose.yml SHALL 各キュー専用のワーカーサービスを定義し、独立してスケール可能とする
4. WHEN `crawl` キューのワーカーが起動する場合, THE ワーカー SHALL Playwright と BrowserPool を初期化する
5. WHEN `extract` または `validate` キューのワーカーが起動する場合, THE ワーカー SHALL Playwright を初期化せず、CPU処理に最適化された設定で起動する

### Requirement 17: 優先度キューとレートリミティング

**User Story:** As a 運用者, I want サイトの優先度に基づいてクロール順序が制御されること, so that 重要なサイトが優先的にクロールされ、対象サイトへの過負荷が防止される。

#### Acceptance Criteria

1. THE MonitoringSite SHALL `crawl_priority` カラム（String型、デフォルト `'normal'`、値: `'high'`, `'normal'`, `'low'`）を持つ
2. WHEN BatchDispatcher がタスクをキューに投入する場合, THE BatchDispatcher SHALL `crawl_priority` に基づいて Celery タスクの priority を設定する（high=0, normal=5, low=9）
3. THE CrawlPipeline SHALL ドメイン単位のレートリミティングを実装し、同一ドメインへのリクエスト間隔を設定可能な最小値（デフォルト: 2秒）以上に制御する
4. WHEN レートリミットに達した場合, THE CrawlPipeline SHALL タスクの実行を遅延させ、制限解除後に再開する

### Requirement 18: デルタクロール（変更検出）

**User Story:** As a 運用者, I want 変更のないサイトのフルクロールをスキップできること, so that 10万サイト以上の規模でもクロール負荷を大幅に削減できる。

#### Acceptance Criteria

1. THE MonitoringSite SHALL `etag` カラム（String型、nullable）と `last_modified_header` カラム（String型、nullable）を持つ
2. WHEN PageFetcher ステージが HTTP リクエストを送信する場合, THE PageFetcher SHALL `If-None-Match`（ETag）および `If-Modified-Since`（Last-Modified）ヘッダーを付与する
3. WHEN HTTP レスポンスが 304 Not Modified の場合, THE CrawlPipeline SHALL フルクロールをスキップし、前回の検証結果を有効として維持する
4. WHEN HTTP レスポンスが 200 の場合, THE PageFetcher SHALL レスポンスの `ETag` および `Last-Modified` ヘッダーを CrawlContext の `metadata` に記録し、クロール完了後に MonitoringSite に保存する
5. WHEN MonitoringSite に `etag` および `last_modified_header` が未設定の場合, THE PageFetcher SHALL 条件付きリクエストヘッダーを付与せず、通常のフルクロールを実行する

### Requirement 19: バッチスケジューリング

**User Story:** As a 運用者, I want 大量のサイトが時間分散してクロールされること, so that システムリソースの瞬間的な過負荷を防止できる。

#### Acceptance Criteria

1. THE CrawlSchedule テーブル SHALL `site_id`（外部キー）, `priority`（String）, `next_crawl_at`（DateTime）, `interval_minutes`（Integer）, `last_etag`（String, nullable）, `last_modified`（String, nullable）フィールドを持つ
2. WHEN CrawlScheduler が起動する場合, THE CrawlScheduler SHALL `next_crawl_at` が現在時刻以前の CrawlSchedule レコードをバッチサイズ（設定可能、デフォルト: 100）ごとに取得する
3. WHEN バッチが取得された場合, THE BatchDispatcher SHALL バッチ内のサイトを `priority` 順にソートし、Celery タスクとしてキューに投入する
4. WHEN タスク投入が完了した場合, THE CrawlScheduler SHALL 対象 CrawlSchedule の `next_crawl_at` を `interval_minutes` 分後に更新する
5. THE CrawlScheduler SHALL 1回のスケジュール実行で投入するタスク数の上限（設定可能、デフォルト: 500）を持ち、上限を超えた場合は次回のスケジュール実行に持ち越す

### Requirement 20: バルクDB操作（閾値ベース自動切替）

**User Story:** As a 開発者, I want クロール結果のDB保存が規模に応じて個別INSERTとバルクINSERTを自動切替すること, so that 少量時は即時書き込みの即応性を維持し、大量時はバルク操作で効率的に永続化できる。

#### Acceptance Criteria

1. THE DBStoragePlugin SHALL 1回のパイプライン実行で保存するレコード数が閾値（設定可能、デフォルト: 10レコード）以下の場合、個別INSERTで即時書き込みを実行する
2. THE DBStoragePlugin SHALL 1回のパイプライン実行で保存するレコード数が閾値を超える場合、バルクINSERT（`session.bulk_save_objects()` または `session.execute(insert().values([...]))` ）で実行する
3. WHEN バルクINSERTのバッチサイズが設定可能な上限（デフォルト: 100レコード）を超える場合, THE DBStoragePlugin SHALL 複数回のバルクINSERTに分割して実行する
4. THE DBStoragePlugin SHALL 個別INSERT・バルクINSERTいずれの場合も単一トランザクションで実行し、部分的な書き込みを防止する
5. THE 閾値は環境変数（`DB_BULK_THRESHOLD`）で設定可能とし、運用規模に応じて調整できる

### Requirement 21: DBモデル拡張

**User Story:** As a 開発者, I want パイプラインアーキテクチャに必要なDBスキーマ変更が安全に適用されること, so that 既存データとの後方互換性を維持しながら新機能を導入できる。

#### Acceptance Criteria

1. THE MonitoringSite SHALL `pre_capture_script` カラム（JSON型、nullable、デフォルト NULL）を持つ
2. THE MonitoringSite SHALL `crawl_priority` カラム（String型、デフォルト `'normal'`）を持つ
3. THE MonitoringSite SHALL `etag` カラム（String型、nullable）と `last_modified_header` カラム（String型、nullable）を持つ
4. THE MonitoringSite SHALL `plugin_config` カラム（JSON型、nullable、デフォルト NULL）を持ち、サイト単位のプラグイン有効/無効・パラメータオーバーライドを格納する
4. THE VerificationResult SHALL `structured_data` フィールド（JSONB型、nullable）, `structured_data_violations` フィールド（JSONB型、nullable）, `data_source` フィールド（String型、nullable）, `structured_data_status` フィールド（String型、nullable）, `evidence_status` フィールド（String型、nullable）を持つ
5. THE EvidenceRecord テーブル SHALL `verification_result_id`（外部キー）, `variant_name`（String）, `screenshot_path`（String）, `roi_image_path`（String, nullable）, `ocr_text`（Text）, `ocr_confidence`（Float）, `evidence_type`（String）, `created_at`（DateTime）フィールドを持つ
6. THE EvidenceRecord テーブル SHALL `verification_result_id` および `evidence_type` にインデックスを持つ
7. THE CrawlSchedule テーブル SHALL `site_id`（外部キー）, `priority`（String）, `next_crawl_at`（DateTime）, `interval_minutes`（Integer）, `last_etag`（String, nullable）, `last_modified`（String, nullable）フィールドを持つ
8. THE CrawlSchedule テーブル SHALL `next_crawl_at` にインデックスを持つ
9. THE 全新規カラム SHALL nullable として定義され、既存レコードに影響を与えない
10. THE Alembic マイグレーション SHALL ダウングレード時に追加カラムおよびテーブルを削除し、既存データを保持する

### Requirement 22: 後方互換性・移行パス・パイプライン設定の柔軟性

**User Story:** As a 運用者, I want 新パイプラインへの移行を段階的に行え、切り替え後もプラグインの有効/無効をグローバルおよびサイト単位で柔軟に制御できること, so that 安全に移行でき、運用中の要件変化にも対応できる。

#### Acceptance Criteria

1. THE 既存の `crawl_and_validate_site` Celery タスク SHALL 移行期間中も動作を維持し、新パイプラインと並行して実行可能とする
2. THE 環境変数 `USE_PIPELINE`（`true`/`false`、デフォルト `false`）SHALL 新旧フローの切り替えを制御する
3. WHEN `USE_PIPELINE=true` の場合, THE CrawlScheduler SHALL 新パイプライン経由でタスクをディスパッチする
4. WHEN `USE_PIPELINE=false` の場合, THE CrawlScheduler SHALL 従来の `crawl_all_sites` タスク経由でクロールを実行する
5. THE 既存の API エンドポイント SHALL 新旧両方のクロール結果を同一のレスポンス形式で返却する
6. THE VerificationResult の新規フィールドが NULL の場合, THE API SHALL 従来のレスポンス形式と互換性のあるレスポンスを返却する
7. THE CrawlPipeline SHALL グローバルプラグイン設定（環境変数 `PIPELINE_PLUGINS` または設定ファイル）を持ち、デフォルトで有効なプラグイン一覧を定義する
8. THE MonitoringSite SHALL `plugin_config` カラム（JSON型、nullable）を持ち、サイト単位でプラグインの有効/無効およびパラメータをオーバーライドできる
9. WHEN サイトの `plugin_config` が設定されている場合, THE CrawlPipeline SHALL グローバル設定をベースにサイト単位の設定でマージ（上書き）してプラグイン構成を決定する
10. WHEN サイトの `plugin_config` が NULL の場合, THE CrawlPipeline SHALL グローバル設定のデフォルトプラグイン構成をそのまま使用する
11. THE `plugin_config` JSON SHALL 以下の形式をサポートする: `{"disabled": ["ShopifyPlugin"], "enabled": ["CustomPlugin"], "params": {"OCRPlugin": {"confidence_threshold": 0.8}}}` — disabled でプラグイン無効化、enabled で追加有効化、params でプラグイン固有パラメータを上書き
12. WHEN 運用中に特定プラグインで障害が発生した場合, THE 運用者 SHALL 環境変数 `PIPELINE_DISABLED_PLUGINS` にプラグイン名を追加することで、再デプロイなしに即座にグローバル無効化できる

### Requirement 23: PageFetcher ステージの実行順序

**User Story:** As a 開発者, I want PageFetcherステージ内のプラグイン実行順序が明確に定義されていること, so that ロケール設定→ページ取得→プレキャプチャスクリプト→モーダル閉じ→スクリーンショットの順序が保証される。

#### Acceptance Criteria

1. THE PageFetcher ステージ SHALL プラグインを以下の順序で実行する: (1) LocalePlugin → (2) ページ取得（`page.goto()` + networkidle待機 + DOM安定化） → (3) PreCaptureScriptPlugin → (4) ModalDismissPlugin → (5) スクリーンショット撮影
2. WHEN PreCaptureScriptPlugin が実行されない場合（`should_run()` が `False`）, THE PageFetcher ステージ SHALL ステップ(3)をスキップし、残りのステップを同じ順序で実行する
3. WHEN 全ステップが完了した場合, THE PageFetcher ステージ SHALL HTML コンテンツを CrawlContext の `html_content` に、スクリーンショットを `screenshots` に格納する

### Requirement 24: クロールスケジュール管理UI — ScheduleTab

**User Story:** As a クロール運用者, I want サイト詳細パネルからクロールスケジュール・優先度・プレキャプチャスクリプトを管理できること, so that サイトごとのクロール設定をUI上で確認・変更できる。

#### Acceptance Criteria

1. THE SiteDetailPanel SHALL 既存の4タブ（契約条件、スクリーンショット、検証・比較、アラート）に加えて「スケジュール」タブを持つ
2. WHEN ユーザーが「スケジュール」タブを選択した場合, THE ScheduleTab SHALL 対象サイトの CrawlSchedule 情報（優先度、クロール間隔、次回クロール予定日時）を表示する
3. THE ScheduleTab SHALL クロール優先度（高/通常/低）をセレクトボックスで変更可能とする
4. THE ScheduleTab SHALL クロール間隔（分単位）を数値入力フィールドで変更可能とする
5. THE ScheduleTab SHALL 次回クロール予定日時を表示し、「今すぐ実行」ボタンで即時クロールをトリガーできる
6. THE ScheduleTab SHALL デルタクロール情報（最終ETag、最終Last-Modified）を読み取り専用で表示する
7. WHEN ユーザーが設定を変更して「保存」ボタンをクリックした場合, THE ScheduleTab SHALL API経由で CrawlSchedule を更新する
8. WHEN 対象サイトに CrawlSchedule レコードが存在しない場合, THE ScheduleTab SHALL デフォルト値（優先度: normal、間隔: 1440分）で新規作成フォームを表示する

### Requirement 24a: クロールスケジュール管理UI — プラグイン設定セクション

**User Story:** As a クロール運用者, I want サイト詳細パネルからプラグインの有効/無効をUI上で切り替えられること, so that JSON を直接編集せずにサイト固有のプラグイン構成を管理できる。

#### Acceptance Criteria

1. THE ScheduleTab SHALL 「プラグイン設定（上級）」セクションを折りたたみ表示（デフォルト閉じ）で持つ
2. WHEN ユーザーが「プラグイン設定（上級）」セクションを展開した場合, THE ScheduleTab SHALL 全登録プラグインの一覧をトグルスイッチ付きで表示する
3. THE 各プラグインのトグルスイッチ SHALL グローバル設定でのデフォルト状態（有効/無効）を初期値として表示し、サイト単位でオーバーライドされている場合はオーバーライド値を表示する
4. WHEN ユーザーがプラグインのトグルを変更した場合, THE ScheduleTab SHALL 変更内容を `plugin_config` JSON 形式に変換し、保存時に API 経由で MonitoringSite に反映する
5. THE プラグイン一覧 SHALL 各プラグインの簡易説明（1行）を表示し、運用者がプラグインの役割を理解できるようにする
6. WHEN サイトの `plugin_config` が NULL（デフォルト設定）の場合, THE ScheduleTab SHALL 全プラグインを「グローバル設定に従う」状態で表示する
7. THE ScheduleTab SHALL 「デフォルトに戻す」ボタンを持ち、クリックで `plugin_config` を NULL にリセットする

### Requirement 25: クロールスケジュール管理UI — PreCaptureScript エディタ

**User Story:** As a クロール運用者, I want サイト詳細パネルからプレキャプチャスクリプトを編集できること, so that サイト固有のモーダル操作やバリアント選択をUI上で設定できる。

#### Acceptance Criteria

1. THE ScheduleTab SHALL PreCaptureScript 入力用のテキストエリアフィールドを持つ
2. THE PreCaptureScript テキストエリア SHALL 既存のスクリプトを JSON 形式で表示し、編集可能とする
3. WHEN PreCaptureScript フィールドが空の場合, THE ScheduleTab SHALL `null` として API に送信する
4. WHEN PreCaptureScript フィールドにJSON形式でない文字列が入力された場合, THE ScheduleTab SHALL バリデーションエラーメッセージを表示し送信を阻止する
5. THE PreCaptureScript テキストエリア SHALL プレースホルダーテキストとして JSON 形式の例を表示する（例: `[{"action": "click", "selector": ".lang-ja", "label": "日本語選択"}]`）

### Requirement 26: クロールスケジュール管理API

**User Story:** As a フロントエンド開発者, I want API経由でサイトのクロールスケジュールを取得・更新・作成できること, so that ScheduleTab からスケジュール管理ができる。

#### Acceptance Criteria

1. THE API SHALL `GET /api/sites/{site_id}/schedule` エンドポイントで対象サイトの CrawlSchedule を返却する
2. THE API SHALL `PUT /api/sites/{site_id}/schedule` エンドポイントで CrawlSchedule の priority, interval_minutes を更新する
3. THE API SHALL `POST /api/sites/{site_id}/schedule` エンドポイントで CrawlSchedule が存在しない場合に新規作成する
4. THE API SHALL `PUT /api/sites/{site_id}` エンドポイントで MonitoringSite の `pre_capture_script`, `crawl_priority` を更新可能とする
5. WHEN `pre_capture_script` に不正なJSON形式が指定された場合, THE API SHALL 422 バリデーションエラーを返す
6. WHEN 存在しない site_id が指定された場合, THE API SHALL 404 エラーを返す

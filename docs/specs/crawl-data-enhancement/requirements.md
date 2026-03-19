# Requirements Document

## Introduction

本ドキュメントは、クロールデータ取得・抽出機能の改善に関する要件を定義します。現在のシステムでは、HTML全体を保存しているものの、抽出した支払い情報（価格、支払い方法、手数料など）がメモリ上のみで保存されず、正規表現ベースの抽出のため精度が低く、視覚的な証拠となるスクリーンショットも取得されていません。本機能では、スクリーンショット自動取得、構造化データ抽出、抽出データの永続化、レビューUIの提供、時系列分析機能を実装し、データ品質と検証可能性を向上させます。

## Glossary

- **Crawler**: Webサイトにアクセスし、HTMLコンテンツとスクリーンショットを取得するシステムコンポーネント
- **Extractor**: HTMLから支払い情報を抽出し、構造化データに変換するシステムコンポーネント
- **Screenshot_Manager**: スクリーンショットの取得、保存、管理を行うシステムコンポーネント
- **Payment_Info_Store**: 抽出された支払い情報を永続化するデータベーステーブル
- **Review_UI**: クロール結果と抽出データを人が確認・修正するためのユーザーインターフェース
- **Confidence_Score**: 抽出されたデータの信頼度を示す0.0から1.0の数値
- **Price_History_Tracker**: 価格の時系列変化を記録・分析するシステムコンポーネント
- **Semantic_Parser**: セマンティックHTML（article、section、priceタグなど）を解析するパーサー
- **Structured_Data_Parser**: JSON-LD、Microdataなどの構造化データを解析するパーサー
- **Metadata_Extractor**: ページメタデータ（タイトル、説明文、OGタグ）を抽出するコンポーネント


## Requirements

### Requirement 1: スクリーンショット自動取得

**User Story:** 管理者として、クロール実行時に自動的にスクリーンショットが取得されることを期待する。これにより、抽出データの視覚的な証拠を保持し、後から検証できるようにする。

#### Acceptance Criteria

1. WHEN a crawl operation is initiated, THE Screenshot_Manager SHALL capture a full-page screenshot in PNG format
2. THE Screenshot_Manager SHALL save the screenshot file with a unique filename containing the site_id and timestamp
3. THE Screenshot_Manager SHALL store the screenshot file path in the crawl_results table
4. WHEN the screenshot capture fails, THE Screenshot_Manager SHALL log the error and continue the crawl operation
5. THE Screenshot_Manager SHALL compress screenshots to reduce storage size while maintaining readability
6. THE Screenshot_Manager SHALL set a maximum screenshot file size of 5MB per image

### Requirement 2: ページメタデータ取得

**User Story:** 管理者として、クロール時にページのメタデータ（タイトル、説明文、OGタグ）が自動的に取得されることを期待する。これにより、ページの基本情報を構造化して保存できる。

#### Acceptance Criteria

1. WHEN a page is crawled, THE Metadata_Extractor SHALL extract the page title from the HTML title tag
2. WHEN a page is crawled, THE Metadata_Extractor SHALL extract the meta description from the meta description tag
3. WHEN a page is crawled, THE Metadata_Extractor SHALL extract Open Graph tags including og:title, og:description, og:image, og:url
4. THE Metadata_Extractor SHALL store extracted metadata in JSONB format in the crawl_results table
5. WHEN metadata extraction fails for any field, THE Metadata_Extractor SHALL store null for that field and continue extraction


### Requirement 3: 構造化データ解析

**User Story:** 管理者として、JSON-LDやMicrodataなどの構造化データが自動的に解析されることを期待する。これにより、正確な商品情報と価格情報を取得できる。

#### Acceptance Criteria

1. WHEN a page contains JSON-LD structured data, THE Structured_Data_Parser SHALL parse and extract product and price information
2. WHEN a page contains Microdata markup, THE Structured_Data_Parser SHALL parse and extract product and price information
3. THE Structured_Data_Parser SHALL prioritize structured data over HTML parsing when both are available
4. THE Structured_Data_Parser SHALL extract schema.org Product properties including name, description, sku, offers
5. THE Structured_Data_Parser SHALL extract schema.org Offer properties including price, priceCurrency, availability
6. WHEN structured data parsing fails, THE Structured_Data_Parser SHALL log the error and fall back to HTML parsing

### Requirement 4: セマンティックHTML解析

**User Story:** 管理者として、セマンティックHTML要素（article、section、priceタグなど）が解析されることを期待する。これにより、構造化データがない場合でも精度の高い抽出ができる。

#### Acceptance Criteria

1. WHEN a page uses semantic HTML, THE Semantic_Parser SHALL identify article elements containing product information
2. THE Semantic_Parser SHALL identify section elements containing pricing information
3. THE Semantic_Parser SHALL extract price values from elements with data-price, itemprop="price", or class="price" attributes
4. THE Semantic_Parser SHALL identify payment method information from form elements and input types
5. THE Semantic_Parser SHALL extract fee information from table elements with pricing-related headers
6. THE Semantic_Parser SHALL assign higher confidence scores to data extracted from semantic elements


### Requirement 5: 商品と価格の関連付け

**User Story:** 管理者として、抽出された商品情報と価格情報が正しく関連付けられることを期待する。これにより、どの商品にどの価格が適用されるかを明確に把握できる。

#### Acceptance Criteria

1. THE Extractor SHALL associate each extracted price with its corresponding product name
2. THE Extractor SHALL associate each extracted price with its corresponding product SKU when available
3. WHEN multiple prices exist for a single product, THE Extractor SHALL store all price variants with their conditions
4. THE Extractor SHALL identify and store the relationship between base prices and additional fees
5. THE Extractor SHALL store product-price associations in the extracted_payment_info table with foreign key relationships

### Requirement 6: 信頼度スコア計算

**User Story:** 管理者として、抽出された各データ項目に信頼度スコアが付与されることを期待する。これにより、レビュー時に優先的に確認すべき項目を判断できる。

#### Acceptance Criteria

1. THE Extractor SHALL calculate a confidence score between 0.0 and 1.0 for each extracted field
2. THE Extractor SHALL assign higher confidence scores to data extracted from structured data formats
3. THE Extractor SHALL assign medium confidence scores to data extracted from semantic HTML elements
4. THE Extractor SHALL assign lower confidence scores to data extracted from regular expression patterns
5. THE Extractor SHALL store confidence scores in JSONB format in the extracted_payment_info table
6. THE Extractor SHALL calculate an overall confidence score as the weighted average of individual field scores


### Requirement 7: 抽出データの永続化

**User Story:** 管理者として、抽出された支払い情報がデータベースに永続化されることを期待する。これにより、後から参照・分析できるようにする。

#### Acceptance Criteria

1. THE Payment_Info_Store SHALL store extracted product information including name, description, sku
2. THE Payment_Info_Store SHALL store extracted price information including amount, currency, price_type
3. THE Payment_Info_Store SHALL store extracted payment method information including method_name, provider, processing_fee
4. THE Payment_Info_Store SHALL store extracted fee information including fee_type, amount, description
5. THE Payment_Info_Store SHALL store confidence scores for each extracted field
6. THE Payment_Info_Store SHALL store the extraction timestamp and crawl_result_id for traceability
7. THE Payment_Info_Store SHALL use JSONB columns for flexible schema to accommodate different site structures

### Requirement 8: 多言語対応の強化

**User Story:** 管理者として、日本語、英語、その他の言語で記載された支払い情報が正しく抽出されることを期待する。これにより、多様なサイトに対応できる。

#### Acceptance Criteria

1. THE Extractor SHALL detect the page language from the html lang attribute or meta tags
2. THE Extractor SHALL use language-specific patterns for price extraction in Japanese, English, and Chinese
3. THE Extractor SHALL recognize currency symbols and codes in multiple languages
4. THE Extractor SHALL recognize payment method names in multiple languages
5. THE Extractor SHALL store the detected language in the extracted_payment_info table


### Requirement 9: クロール結果レビューUI - 基本表示

**User Story:** レビュアーとして、クロール結果画面でスクリーンショットと抽出データを並べて確認できることを期待する。これにより、抽出結果の正確性を視覚的に検証できる。

#### Acceptance Criteria

1. THE Review_UI SHALL display the screenshot on the left side of the screen
2. THE Review_UI SHALL display the extracted payment information on the right side of the screen
3. THE Review_UI SHALL display the crawl timestamp and site URL at the top of the screen
4. THE Review_UI SHALL display the overall confidence score prominently
5. WHEN a user clicks on an extracted data field, THE Review_UI SHALL highlight the corresponding area on the screenshot
6. THE Review_UI SHALL support zooming and panning of the screenshot

### Requirement 10: クロール結果レビューUI - 信頼度表示

**User Story:** レビュアーとして、抽出された各データ項目の信頼度を確認できることを期待する。これにより、優先的に確認すべき項目を判断できる。

#### Acceptance Criteria

1. THE Review_UI SHALL display a confidence score indicator for each extracted field
2. THE Review_UI SHALL use color coding to indicate confidence levels: green for high, yellow for medium, red for low
3. THE Review_UI SHALL define high confidence as scores greater than or equal to 0.8
4. THE Review_UI SHALL define medium confidence as scores between 0.5 and 0.8
5. THE Review_UI SHALL define low confidence as scores less than 0.5
6. THE Review_UI SHALL sort extracted fields by confidence score in ascending order by default


### Requirement 11: クロール結果レビューUI - 手動修正機能

**User Story:** レビュアーとして、抽出ミスを発見した場合、その場で修正できることを期待する。これにより、データ品質を向上させることができる。

#### Acceptance Criteria

1. WHEN a user clicks an edit button for a field, THE Review_UI SHALL display an inline edit form
2. THE Review_UI SHALL validate user input according to the field type before saving
3. WHEN a user saves a correction, THE Review_UI SHALL update the extracted_payment_info table
4. WHEN a user saves a correction, THE Review_UI SHALL set the confidence score to 1.0 for manually verified fields
5. THE Review_UI SHALL display a visual indicator for manually corrected fields
6. THE Review_UI SHALL allow users to add new fields that were not automatically extracted

### Requirement 12: クロール結果レビューUI - 変更履歴記録

**User Story:** レビュアーとして、修正内容が履歴として記録されることを期待する。これにより、誰がいつ何を変更したかを追跡できる。

#### Acceptance Criteria

1. WHEN a user modifies an extracted field, THE Review_UI SHALL record the change in the audit_logs table
2. THE Review_UI SHALL record the user identifier, timestamp, field name, old value, and new value
3. THE Review_UI SHALL display a change history panel showing all modifications for the current crawl result
4. THE Review_UI SHALL allow users to view the change history for each individual field
5. THE Review_UI SHALL display the username and timestamp for each change


### Requirement 13: クロール結果レビューUI - 承認ワークフロー

**User Story:** レビュアーとして、レビュー完了後に結果を承認または却下できることを期待する。これにより、データの品質管理プロセスを確立できる。

#### Acceptance Criteria

1. THE Review_UI SHALL provide an approve button to mark the extraction as verified
2. THE Review_UI SHALL provide a reject button to mark the extraction as requiring re-crawl
3. WHEN a user approves a result, THE Review_UI SHALL update the status field to approved in extracted_payment_info
4. WHEN a user rejects a result, THE Review_UI SHALL update the status field to rejected in extracted_payment_info
5. WHEN a user rejects a result, THE Review_UI SHALL require a rejection reason comment
6. THE Review_UI SHALL display the approval status and approver information on the review screen

### Requirement 14: 価格履歴の記録

**User Story:** 分析者として、価格の時系列変化を記録できることを期待する。これにより、価格変動を追跡し、異常を検出できる。

#### Acceptance Criteria

1. THE Price_History_Tracker SHALL store each extracted price with its crawl timestamp
2. THE Price_History_Tracker SHALL maintain a complete history of price changes for each product
3. THE Price_History_Tracker SHALL calculate the price change amount between consecutive crawls
4. THE Price_History_Tracker SHALL calculate the price change percentage between consecutive crawls
5. THE Price_History_Tracker SHALL identify the product using a combination of site_id, product_name, and sku


### Requirement 15: 時系列グラフ表示

**User Story:** 分析者として、価格の時系列変化をグラフで確認できることを期待する。これにより、価格トレンドを視覚的に把握できる。

#### Acceptance Criteria

1. THE Review_UI SHALL display a line chart showing price changes over time for each product
2. THE Review_UI SHALL display the x-axis as crawl timestamps and the y-axis as price amounts
3. THE Review_UI SHALL allow users to select a date range for the chart display
4. THE Review_UI SHALL display multiple products on the same chart when comparing prices
5. THE Review_UI SHALL display data points with tooltips showing exact price and timestamp
6. THE Review_UI SHALL highlight significant price changes with visual markers

### Requirement 16: 異常値検出

**User Story:** 分析者として、急激な価格変動を自動検知してアラートを受け取ることを期待する。これにより、重要な変更を見逃さないようにする。

#### Acceptance Criteria

1. WHEN a price change exceeds 20 percent between consecutive crawls, THE Price_History_Tracker SHALL create an alert
2. WHEN a price drops to zero, THE Price_History_Tracker SHALL create a high-severity alert
3. WHEN a new product appears, THE Price_History_Tracker SHALL create an informational alert
4. WHEN a product disappears, THE Price_History_Tracker SHALL create a warning alert
5. THE Price_History_Tracker SHALL store alerts in the alerts table with appropriate severity levels
6. THE Price_History_Tracker SHALL include the old price, new price, and change percentage in the alert message


### Requirement 17: 過去クロール結果の比較

**User Story:** 分析者として、過去のクロール結果を比較できることを期待する。これにより、変更内容を詳細に確認できる。

#### Acceptance Criteria

1. THE Review_UI SHALL provide a comparison view showing two crawl results side by side
2. THE Review_UI SHALL highlight fields that have changed between the two selected crawl results
3. THE Review_UI SHALL display both screenshots side by side in comparison mode
4. THE Review_UI SHALL calculate and display the difference for numeric fields
5. THE Review_UI SHALL allow users to select any two crawl results from the history for comparison

### Requirement 18: データベーススキーマ拡張

**User Story:** 開発者として、抽出データを保存するための新しいテーブルが追加されることを期待する。これにより、既存のスキーマとの互換性を保ちながら新機能を実装できる。

#### Acceptance Criteria

1. THE Payment_Info_Store SHALL create an extracted_payment_info table with columns for id, crawl_result_id, site_id, extracted_at
2. THE Payment_Info_Store SHALL include JSONB columns for product_info, price_info, payment_methods, fees, metadata
3. THE Payment_Info_Store SHALL include a JSONB column for confidence_scores
4. THE Payment_Info_Store SHALL include columns for status, language, overall_confidence_score
5. THE Payment_Info_Store SHALL create a foreign key constraint to crawl_results table
6. THE Payment_Info_Store SHALL create indexes on site_id, crawl_result_id, extracted_at, and status columns


### Requirement 19: パフォーマンス最適化

**User Story:** 管理者として、スクリーンショット取得による遅延が最小限に抑えられることを期待する。これにより、クロール処理全体のパフォーマンスへの影響を軽減できる。

#### Acceptance Criteria

1. THE Screenshot_Manager SHALL complete screenshot capture within 5 seconds per page
2. THE Crawler SHALL execute screenshot capture asynchronously to avoid blocking HTML extraction
3. THE Crawler SHALL implement a timeout of 10 seconds for screenshot operations
4. WHEN the screenshot timeout is exceeded, THE Crawler SHALL log a warning and continue without the screenshot
5. THE Extractor SHALL complete data extraction within 3 seconds per page
6. THE Crawler SHALL maintain overall crawl performance within 20 percent of the baseline without screenshots

### Requirement 20: ストレージ管理

**User Story:** 管理者として、スクリーンショットのストレージ容量が管理されることを期待する。これにより、ディスク容量の枯渇を防ぐことができる。

#### Acceptance Criteria

1. THE Screenshot_Manager SHALL store screenshots in a dedicated directory structure organized by year, month, and site_id
2. THE Screenshot_Manager SHALL implement automatic cleanup of screenshots older than 90 days
3. THE Screenshot_Manager SHALL provide a configuration option to adjust the retention period
4. THE Screenshot_Manager SHALL log storage usage statistics daily
5. WHEN storage usage exceeds 80 percent of the allocated quota, THE Screenshot_Manager SHALL create a warning alert
6. THE Screenshot_Manager SHALL support manual deletion of screenshots through an admin API endpoint


### Requirement 21: API エンドポイント

**User Story:** 開発者として、抽出データにアクセスするためのRESTful APIエンドポイントが提供されることを期待する。これにより、フロントエンドやサードパーティシステムからデータを取得できる。

#### Acceptance Criteria

1. THE API SHALL provide a GET endpoint at /api/extracted-data/{crawl_result_id} to retrieve extracted payment information
2. THE API SHALL provide a GET endpoint at /api/extracted-data/site/{site_id} to retrieve all extracted data for a site
3. THE API SHALL provide a PUT endpoint at /api/extracted-data/{id} to update extracted data fields
4. THE API SHALL provide a GET endpoint at /api/price-history/{site_id}/{product_id} to retrieve price history
5. THE API SHALL return responses in JSON format with appropriate HTTP status codes
6. THE API SHALL implement pagination for endpoints returning multiple records with a default page size of 50

### Requirement 22: エラーハンドリング

**User Story:** 開発者として、抽出処理中のエラーが適切に処理されることを期待する。これにより、システムの安定性と信頼性を確保できる。

#### Acceptance Criteria

1. WHEN HTML parsing fails, THE Extractor SHALL log the error with the site_id and crawl_result_id
2. WHEN screenshot capture fails, THE Screenshot_Manager SHALL store null in the screenshot_path field
3. WHEN data extraction fails completely, THE Extractor SHALL create an extracted_payment_info record with status set to failed
4. THE Extractor SHALL include error details in the metadata JSONB field when extraction fails
5. WHEN a database write fails, THE System SHALL retry up to 3 times with exponential backoff
6. THE System SHALL send an alert to administrators when critical errors occur


### Requirement 23: 既存機能との互換性

**User Story:** 開発者として、既存のクロール機能が壊れないことを期待する。これにより、現在動作している機能を維持しながら新機能を追加できる。

#### Acceptance Criteria

1. THE Crawler SHALL continue to store HTML content in the crawl_results table as before
2. THE Crawler SHALL continue to update the last_crawled_at field in monitoring_sites table
3. THE Crawler SHALL continue to trigger validation and alert creation as before
4. THE Extractor SHALL operate as an additional step after HTML storage, not replacing existing logic
5. WHEN the extraction feature is disabled via configuration, THE Crawler SHALL function exactly as before
6. THE System SHALL maintain backward compatibility with existing API endpoints

### Requirement 24: 設定管理

**User Story:** 管理者として、機能の有効化・無効化や動作パラメータを設定できることを期待する。これにより、環境に応じた柔軟な運用ができる。

#### Acceptance Criteria

1. THE System SHALL provide a configuration option to enable or disable screenshot capture
2. THE System SHALL provide a configuration option to enable or disable structured data extraction
3. THE System SHALL provide a configuration option to set the screenshot quality level
4. THE System SHALL provide a configuration option to set the confidence score thresholds
5. THE System SHALL provide a configuration option to set the price change alert threshold percentage
6. THE System SHALL load configuration from environment variables or a configuration file


### Requirement 25: テストデータ生成

**User Story:** 開発者として、レビューUIのテストに使用できるサンプルデータが生成されることを期待する。これにより、開発とテストを効率的に進めることができる。

#### Acceptance Criteria

1. THE System SHALL provide a script to generate sample extracted_payment_info records
2. THE System SHALL provide a script to generate sample screenshots for testing
3. THE System SHALL provide a script to generate sample price history data
4. THE System SHALL generate test data with varying confidence scores to test UI behavior
5. THE System SHALL generate test data with different languages to test multilingual support

## Non-Functional Requirements

### Performance

1. THE System SHALL process and store extracted data for 100 concurrent crawl operations
2. THE Review_UI SHALL load and display a crawl result with screenshot within 2 seconds
3. THE API SHALL respond to data retrieval requests within 500 milliseconds for 95 percent of requests

### Security

1. THE Review_UI SHALL require authentication before allowing access to crawl results
2. THE API SHALL validate and sanitize all user input to prevent injection attacks
3. THE System SHALL log all data modifications in the audit_logs table

### Scalability

1. THE System SHALL support storage of up to 1 million extracted_payment_info records
2. THE System SHALL support storage of up to 100,000 screenshots
3. THE Price_History_Tracker SHALL efficiently query price history for products with up to 1,000 data points


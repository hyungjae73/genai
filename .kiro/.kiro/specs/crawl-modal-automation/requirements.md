# Requirements Document

## Introduction

クロール対象サイトが言語選択モーダルやCookie同意バナーなどのオーバーレイを表示する場合、スクリーンショットにモーダルが写り込み、正確なページ内容の取得を妨げる。本機能は3層のアプローチ（Accept-Language ヘッダー設定、汎用モーダル自動閉じ、サイト固有プレキャプチャスクリプト）でこの問題を解決し、モーダルのないクリーンなスクリーンショットとHTML取得を実現する。

## Glossary

- **ScreenshotManager**: Playwright を使用してサイトのスクリーンショットを撮影するコンポーネント（`genai/src/screenshot_manager.py`）
- **MonitoringSite**: 監視対象サイトを表すDBモデル（`genai/src/models.py`）
- **CrawlTask**: サイトのクロールとバリデーションを実行する非同期タスク（`genai/src/tasks.py`）
- **PreCaptureScript**: サイトごとに登録可能なカスタムPlaywrightアクションのJSON定義。`page.goto()` 後、スクリーンショット撮影前に実行される
- **ModalDetector**: ページ上のモーダル・オーバーレイ要素を検出し自動的に閉じるコンポーネント
- **LocaleConfig**: Playwright ブラウザページに設定する `locale` と `Accept-Language` ヘッダーの組み合わせ

## Requirements

### Requirement 1: Accept-Language ヘッダーとロケール設定

**User Story:** As a クロール運用者, I want クロール時にブラウザのロケールとAccept-Languageヘッダーが日本語に設定されること, so that 言語選択モーダルの表示を事前に抑制できる。

#### Acceptance Criteria

1. WHEN ScreenshotManager がブラウザページを生成する場合, THE ScreenshotManager SHALL `locale` を `"ja-JP"` に設定してページを作成する
2. WHEN ScreenshotManager がブラウザページを生成する場合, THE ScreenshotManager SHALL `extra_http_headers` に `{"Accept-Language": "ja-JP,ja;q=0.9"}` を設定してページを作成する
3. WHILE ロケール設定が適用された状態で, THE ScreenshotManager SHALL 従来と同じビューポートサイズ（1920x1080）とデバイススケールファクター（2）を維持する
4. WHEN ロケール設定が適用された状態でページを取得した場合, THE ScreenshotManager SHALL 従来と同一のスクリーンショット撮影フロー（networkidle待機、DOM安定化、フルページキャプチャ）を実行する

### Requirement 2: 汎用モーダル自動閉じ

**User Story:** As a クロール運用者, I want クロール時にページ上のモーダルやオーバーレイが自動的に閉じられること, so that スクリーンショットにモーダルが写り込まない。

#### Acceptance Criteria

1. WHEN ページの読み込みが完了した後かつスクリーンショット撮影前に, THE ModalDetector SHALL ページ上のモーダル要素を検出する
2. THE ModalDetector SHALL 以下のセレクタパターンでモーダル要素を検出する: `[role="dialog"]`, `[role="alertdialog"]`, `.modal`, `.overlay`, `[class*="cookie"]`, `[class*="consent"]`, `[id*="cookie"]`, `[id*="consent"]`
3. WHEN モーダル要素が検出された場合, THE ModalDetector SHALL モーダル内の閉じるボタン（`button[aria-label*="close"]`, `.close`, `button[class*="close"]`, `button[class*="dismiss"]`, `button[class*="accept"]`）をクリックして閉じる
4. WHEN 閉じるボタンが見つからない場合, THE ModalDetector SHALL Escapeキーの送信を試みてモーダルを閉じる
5. WHEN モーダルの閉じ処理が完了した後, THE ModalDetector SHALL 500ミリ秒待機してからスクリーンショット撮影に進む
6. IF モーダルの検出または閉じ処理中にエラーが発生した場合, THEN THE ModalDetector SHALL エラーをログに記録し、スクリーンショット撮影を中断せずに続行する
7. WHEN ページ上にモーダル要素が存在しない場合, THE ModalDetector SHALL 追加の待機なしでスクリーンショット撮影に進む

### Requirement 3: サイト固有プレキャプチャスクリプト

**User Story:** As a クロール運用者, I want サイトごとにカスタムのPlaywrightアクションを登録できること, so that 汎用ロジックでは対応できないサイト固有のモーダルや操作を自動化できる。

#### Acceptance Criteria

1. THE MonitoringSite SHALL `pre_capture_script` カラム（JSON型、nullable）を持つ
2. WHEN PreCaptureScript が MonitoringSite に設定されている場合, THE ScreenshotManager SHALL `page.goto()` 後かつスクリーンショット撮影前に PreCaptureScript を実行する
3. THE PreCaptureScript SHALL 以下のアクション型をサポートする: `click`（セレクタ指定の要素クリック）, `wait`（ミリ秒指定の待機）, `select`（セレクタとvalue指定のセレクト操作）, `type`（セレクタとtext指定のテキスト入力）
4. WHEN PreCaptureScript に複数のアクションが定義されている場合, THE ScreenshotManager SHALL アクションを定義順に逐次実行する
5. IF PreCaptureScript のアクション実行中にエラーが発生した場合, THEN THE ScreenshotManager SHALL エラーをログに記録し、残りのアクションをスキップしてスクリーンショット撮影に進む
6. WHEN MonitoringSite に PreCaptureScript が設定されていない場合, THE ScreenshotManager SHALL PreCaptureScript の実行をスキップする

### Requirement 4: PreCaptureScript の JSON スキーマ

**User Story:** As a クロール運用者, I want PreCaptureScript のJSON形式が明確に定義されていること, so that 正しい形式でスクリプトを登録できる。

#### Acceptance Criteria

1. THE PreCaptureScript SHALL JSON配列形式で定義され、各要素はアクションオブジェクトとする
2. THE アクションオブジェクト SHALL `action` フィールド（文字列、必須）を持ち、値は `"click"`, `"wait"`, `"select"`, `"type"` のいずれかとする
3. WHEN アクション型が `"click"` の場合, THE アクションオブジェクト SHALL `selector` フィールド（文字列、必須）を持つ
4. WHEN アクション型が `"wait"` の場合, THE アクションオブジェクト SHALL `duration` フィールド（整数、ミリ秒単位、必須）を持つ
5. WHEN アクション型が `"select"` の場合, THE アクションオブジェクト SHALL `selector` フィールド（文字列、必須）と `value` フィールド（文字列、必須）を持つ
6. WHEN アクション型が `"type"` の場合, THE アクションオブジェクト SHALL `selector` フィールド（文字列、必須）と `text` フィールド（文字列、必須）を持つ
7. IF PreCaptureScript のJSON形式が不正な場合, THEN THE ScreenshotManager SHALL バリデーションエラーをログに記録し、スクリプト実行をスキップする
8. FOR ALL 有効な PreCaptureScript JSON, THE ScreenshotManager SHALL JSON をパースしてアクションリストに変換し、再度JSONにシリアライズした場合に同等のアクションリストが得られる（ラウンドトリップ特性）

### Requirement 5: 実行順序の制御

**User Story:** As a クロール運用者, I want 3層の処理が正しい順序で実行されること, so that 各層が期待通りに機能する。

#### Acceptance Criteria

1. THE ScreenshotManager SHALL 以下の順序でキャプチャ処理を実行する: (1) ロケール・Accept-Language設定付きページ生成 → (2) `page.goto()` → (3) DOM安定化待機 → (4) PreCaptureScript実行 → (5) 汎用モーダル自動閉じ → (6) スクリーンショット撮影
2. WHEN PreCaptureScript が設定されていない場合, THE ScreenshotManager SHALL ステップ(4)をスキップし、残りのステップを同じ順序で実行する
3. WHEN 全ステップが完了した後, THE ScreenshotManager SHALL 従来と同じ後処理（OCRコピー保存、圧縮）を実行する

### Requirement 6: API スキーマ拡張

**User Story:** As a フロントエンド開発者, I want API経由でサイトの PreCaptureScript を登録・更新・取得できること, so that フロントエンドからスクリプトを管理できる。

#### Acceptance Criteria

1. THE MonitoringSiteCreate スキーマ SHALL `pre_capture_script` フィールド（Optional、JSON配列、デフォルト None）を持つ
2. THE MonitoringSiteUpdate スキーマ SHALL `pre_capture_script` フィールド（Optional、JSON配列、デフォルト None）を持つ
3. THE MonitoringSiteResponse スキーマ SHALL `pre_capture_script` フィールドを含む
4. WHEN `pre_capture_script` に不正なJSON形式が指定された場合, THE API SHALL 422 バリデーションエラーを返す

### Requirement 7: フロントエンド サイト編集UI拡張

**User Story:** As a クロール運用者, I want サイト登録・編集画面からPreCaptureScriptを入力できること, so that ブラウザ上でスクリプトを管理できる。

#### Acceptance Criteria

1. THE サイト登録モーダル SHALL PreCaptureScript 入力用のテキストエリアフィールドを持つ
2. THE サイト編集モーダル SHALL 既存の PreCaptureScript を表示し編集可能とする
3. WHEN PreCaptureScript フィールドが空の場合, THE フロントエンド SHALL `null` として API に送信する
4. WHEN PreCaptureScript フィールドにJSON形式でない文字列が入力された場合, THE フロントエンド SHALL バリデーションエラーメッセージを表示し送信を阻止する
5. THE PreCaptureScript 入力フィールド SHALL プレースホルダーテキストとしてJSON形式の例を表示する

### Requirement 8: データベースマイグレーション

**User Story:** As a 開発者, I want MonitoringSite テーブルへの新カラム追加が Alembic マイグレーションで管理されること, so that 安全にスキーマ変更をデプロイできる。

#### Acceptance Criteria

1. THE Alembic マイグレーション SHALL `monitoring_sites` テーブルに `pre_capture_script` カラム（JSON型、nullable、デフォルト NULL）を追加する
2. THE Alembic マイグレーション SHALL ダウングレード時に `pre_capture_script` カラムを削除する
3. WHEN マイグレーションが実行された場合, THE 既存の MonitoringSite レコード SHALL `pre_capture_script` が NULL の状態で保持される

### Requirement 9: 後方互換性

**User Story:** As a クロール運用者, I want 既存のサイト設定が変更なしで従来通り動作すること, so that 新機能の導入で既存のクロールが壊れない。

#### Acceptance Criteria

1. WHEN MonitoringSite に PreCaptureScript が設定されていない場合, THE ScreenshotManager SHALL ロケール設定と汎用モーダル閉じのみを適用し、従来と同等のスクリーンショットを撮影する
2. WHEN 汎用モーダル閉じ処理でモーダルが検出されない場合, THE ScreenshotManager SHALL 追加の遅延なしで従来と同じタイミングでスクリーンショットを撮影する
3. THE ScreenshotManager SHALL 既存の `capture_screenshot()` メソッドのインターフェース（引数: url, site_id, timeout）を変更しない

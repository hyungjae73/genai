# Requirements Document

## Introduction

決済条件監視システムのクロールパイプラインに、4つの高度なダークパターン検出アプローチを導入する。現在のパイプラインは構造化データ抽出・OCR・契約比較による基本的な違反検出を行っているが、視覚的欺瞞（極小フォント、低コントラスト、CSS隠蔽）、LLMによるセマンティック分類、動的状態変化（カート追加後の隠し料金、チェックアウト時のアップセル）、UI/UXトラップ（事前チェック済みオプション、コンファームシェイミング）といった高度なダークパターンには対応できていない。

本specでは以下の4つのプラグインを新規実装し、CrawlPipelineの各ステージに統合する:
1. **CSSVisualPlugin**（DataExtractorステージ）: CSS/視覚階層分析による視覚的欺瞞検出
2. **LLMClassifierPlugin**（DataExtractorステージ）: 外部LLM APIによるセマンティック分類
3. **JourneyPlugin**（PageFetcherステージ）: 動的状態変化・ユーザージャーニーキャプチャ
4. **UITrapPlugin**（Validatorステージ）: UI/UXトラップ検出

4プラグインの検出結果を統合した **DarkPatternScore**（0-1のMax Poolingスコア）を算出し、CrawlContext の violations および metadata に記録する。dark-pattern-notification specと連携してアラート通知を行う。

### 🚨 CTO Overrides（アーキテクチャ安全設計）

本specには以下のCTOレビューによるアーキテクチャ修正が適用されている。元の要件よりもこちらのルールが優先される。

1. **[CSSVisualPlugin] RPC爆発の禁止**: Python側で要素ごとに `getComputedStyle` をループ呼び出しすることは厳禁。`await page.evaluate(...)` で全テキスト要素のスタイルをブラウザJS内で一括計算し、1回のRPCでJSON配列として返す設計とする。
2. **[LLMClassifierPlugin] Middle-Out Truncation**: HTMLタグをパージして純粋テキストノードを抽出。上限超過時は上部20%+下部30%（フッター）を優先保持し、中間部分を切り捨てる。フッターに隠された解約条件の見逃しを防止する。
3. **[JourneyPlugin] DOM差分ノイズ排除**: 生HTML文字列の差分比較は禁止。Playwrightの `locator` + `isVisible()` で可視要素のみをトラッキングし、React/Vue等の仮想DOM再レンダリングノイズを排除する。
4. **[JourneyPlugin] セレクタのヒューリスティック・フォールバック**: 明示セレクタが見つからない場合、`get_by_role` 等でヒューリスティック探索を行い、サイトUI変更への耐性を確保する。
5. **[DarkPatternScore] Max Pooling + ペナルティベースライン**: 加重平均による未実行プラグイン除外は禁止（インセンティブの歪み防止）。実行済みサブスコアの最大値をスコアとし、未実行プラグインにはペナルティベースライン（0.15）を加算する。
6. **[Hybrid Rule Engine] 脱・Pythonファイル依存**: ルール追加のたびに `.py` ファイルを作成する設計は却下。Built-in Rules（エンジニアがコードで書く価格比較等）とは別に、コンプライアンス担当者がDBに自然言語プロンプトを登録するだけで `DynamicLLMValidatorPlugin` が LLM に判定させる「LLM as a Judge」アーキテクチャを採用する。
7. **[Darksite検出] TF-IDF廃止 → Dense Vector**: テキストSpinning（リライト）に無力なTF-IDFを廃止し、`all-MiniLM-L6-v2`（384次元、ローカル推論）によるセマンティック検索を Layer 1 とする。画像 pHash と組み合わせた2層検出。
8. **[ContentFingerprint] 爆発防止**: 全ページのFingerprintを保存してDBをパンクさせないよう、`is_canonical_product` フラグで商品中核ページのみに限定。`max_fingerprints_per_site=50`、TTL 90日自動削除。
9. **[LLM Structured Outputs] CoTフィールド順序**: LLMの自己回帰特性を活用し、reasoning → evidence_text → confidence → compliant の順序で出力させる。全フィールド必須（default値禁止、Strict Mode対応）。
10. **[プロンプト構築] 二重挿入禁止**: `{page_text}` プレースホルダ replace 後の末尾追加を禁止。トークン制限突破とAPIコスト2倍を防止。
11. **[LLM API呼び出し] 指数バックオフリトライ**: 最低3回リトライ（tenacity）。1回のエラーで passed=True を返す偽陰性を防止。
12. **[DynamicRuleCreate] Fail-Fastバリデーション**: `{page_text}` 必須チェック。プロンプト登録時に欠落を即座に検出。

## Dependencies

- crawl-pipeline-architecture: CrawlPlugin基底クラス、CrawlContext、CrawlPipeline、BrowserPool（必須・完了前提）
- dark-pattern-notification: NotificationPlugin によるアラート配信（通知連携用）

## Glossary

- **CSSVisualPlugin**: DataExtractorステージで動作するプラグイン。単一の `page.evaluate()` でブラウザJS内の全テキスト要素のスタイルを一括計算し、1回のRPCでPython側に返す設計でCSS/視覚階層の欺瞞技法を検出する（🚨 要素ごとのgetComputedStyleループは禁止）
- **LLMClassifierPlugin**: DataExtractorステージで動作するプラグイン。外部LLM APIを使用してテキスト・画像のセマンティック分類を行う
- **JourneyPlugin**: PageFetcherステージで動作するプラグイン。カート追加・チェックアウト等のユーザージャーニーを再現し、動的に出現するダークパターンを検出する
- **UITrapPlugin**: Validatorステージで動作するプラグイン。事前チェック済みオプション、コンファームシェイミング等のUI/UXトラップを検出する
- **DarkPatternScore**: 4プラグインの検出結果をMax Poolingで統合した総合スコア（0-1）。実行済みサブスコアの最大値を採用し、未実行プラグインにはペナルティベースライン（0.15）を加算する。0はダークパターン未検出、1は最大リスクを示す
- **Middle-Out Truncation**: LLMClassifierPluginで使用するテキスト切り詰めアルゴリズム。上部20%+下部30%を優先保持し、中間部分を切り捨てることでフッターに隠された解約条件の見逃しを防止する
- **VisualDeceptionScore**: CSSVisualPluginが算出する視覚的欺瞞スコア（0-1）
- **ContrastRatio**: WCAG基準に基づくテキストと背景のコントラスト比。4.5:1未満を低コントラストとして検出する
- **JourneyScript**: ユーザージャーニーを定義するJSON形式のスクリプト。各ステップにアクションとアサーションを含む
- **ConfirmShaming**: ユーザーにオファーを断らせにくくする操作的なボタンテキストパターン（例: 「いいえ、節約したくありません」）
- **SneakIntoBasket**: ユーザーが明示的に選択していない有料オプションや定期購入プランがチェックアウトDOMに事前追加されている手法
- **CrawlPlugin**: 各ステージ内で実行されるプラグインの抽象基底クラス。`execute(ctx)` と `should_run(ctx)` を持つ
- **CrawlContext**: パイプライン全体で共有されるコンテキストオブジェクト。violations, evidence_records, metadata, errors を保持する
- **CrawlPipeline**: サイト単位のクロール処理を4ステージで実行するパイプラインオーケストレータ
- **BrowserPool**: Playwrightブラウザインスタンスをワーカー内でプールし再利用するコンポーネント
- **MonitoringSite**: 監視対象サイトを表すDBモデル。`plugin_config`（JSON型）でサイト単位のプラグイン設定を保持する
- **PreCaptureScriptPlugin**: サイトごとのカスタムPlaywrightアクションを実行する既存プラグイン。JourneyPluginはこの概念を拡張する
- **OCRPlugin**: スクリーンショットからOCRでテキストを抽出する既存プラグイン。LLMClassifierPluginはOCR結果を入力として使用する
- **StructuredDataPlugin**: HTML構造化データから価格情報を抽出する既存プラグイン。CSSVisualPluginはこの後に実行される
- **ContractComparisonPlugin**: 契約条件との価格比較を行う既存プラグイン。UITrapPluginはこの後に実行される
- **DetectionRuleSet**: 検出ルールの動的拡張を可能にするJSON形式のルール定義。グローバルルール + サイト固有ルールのマージをサポートし、コード変更なしに検出項目を追加できる
- **VALID_DARK_PATTERN_TYPES**: ダークパターン分類の有効値リスト。visual_deception, hidden_subscription, sneak_into_basket, default_subscription, confirmshaming, distant_cancellation_terms, hidden_fees, urgency_pattern, price_manipulation, misleading_ui, misleading_font_size, other の12種

## Requirements

### Requirement 1: CSSVisualPlugin — CSS/視覚階層による欺瞞検出

**User Story:** As a コンプライアンス担当者, I want ページ上の視覚的欺瞞技法（極小フォント、低コントラスト、CSS隠蔽）が自動検出されること, so that 消費者が見落としやすい隠された条件や料金表示を特定できる。

#### Acceptance Criteria

1. THE CSSVisualPlugin SHALL CrawlPlugin 抽象基底クラスを継承し、`execute(ctx: CrawlContext) -> CrawlContext` および `should_run(ctx: CrawlContext) -> bool` を実装する
2. THE CSSVisualPlugin の `should_run()` SHALL CrawlContext の `metadata` に `pagefetcher_page` （Playwrightページ参照）が存在する場合に `True` を返す
3. WHEN CSSVisualPlugin が実行される場合, THE CSSVisualPlugin SHALL 単一の `await page.evaluate(...)` 呼び出しでブラウザJSコンテキスト内の全テキスト要素（`innerText.trim().length > 0`）のCSSプロパティ（color, backgroundColor, fontSize, display, visibility, opacity, overflow, position, left, top）を一括計算し、結果をJSON配列として1回のRPCでPython側に返す（🚨 CTO Override: 要素ごとの `getComputedStyle` ループ呼び出しは厳禁。背景色は単色rgbaのみ対応）
4. WHEN テキスト要素の前景色と背景色のコントラスト比が 2.0:1 未満の場合, THE CSSVisualPlugin SHALL 該当要素を低コントラスト欺瞞として検出し、要素のセレクタ、前景色、背景色、算出コントラスト比を証拠として記録する
5. WHEN 条件テキスト（注意書き、定期購入条件等）のフォントサイズが同一ページ内の主要価格表示のフォントサイズの 25% 未満の場合, THE CSSVisualPlugin SHALL 該当要素をフォントサイズ異常として検出し、条件テキストのフォントサイズ、主要価格表示のフォントサイズ、比率を証拠として記録する
6. THE CSSVisualPlugin SHALL 以下のCSS隠蔽技法を検出する: `margin-left: -9999px` 等のオフスクリーン配置、`opacity: 0`、`font-size: 0`、親要素の `overflow: hidden` によるテキストクリッピング、`display: none` / `visibility: hidden` が適用された重要条件テキスト
7. WHEN CSS隠蔽技法が検出された場合, THE CSSVisualPlugin SHALL 該当要素のセレクタ、適用されたCSSプロパティ、隠蔽されたテキスト内容を証拠として CrawlContext の `evidence_records` に追加する
8. THE CSSVisualPlugin SHALL 検出された全欺瞞技法から visual_deception_score（0-1）を算出し、CrawlContext の `metadata` に `cssvisual_deception_score` キーで格納する
9. THE CSSVisualPlugin SHALL 検出された各欺瞞技法を `{technique: str, selector: str, evidence: dict, severity: float}` 形式で CrawlContext の `metadata` に `cssvisual_techniques` キーでリストとして格納する
10. IF CSSVisualPlugin の実行中にエラーが発生した場合, THEN THE CSSVisualPlugin SHALL エラーを CrawlContext の `errors` リストに記録し、パイプラインの実行を中断しない

### Requirement 2: LLMClassifierPlugin — LLMセマンティック分類

**User Story:** As a コンプライアンス担当者, I want ページ上のテキストや画像がLLMによってセマンティック分析され、隠された定期購入条件やダークパターンが分類されること, so that ルールベースでは検出困難な巧妙なダークパターンを特定できる。

#### Acceptance Criteria

1. THE LLMClassifierPlugin SHALL CrawlPlugin 抽象基底クラスを継承し、`execute(ctx: CrawlContext) -> CrawlContext` および `should_run(ctx: CrawlContext) -> bool` を実装する
2. THE LLMClassifierPlugin の `should_run()` SHALL CrawlContext の `evidence_records`（OCR結果）または `html_content` が存在し、かつ環境変数 `LLM_API_KEY` が設定されている場合に `True` を返す
3. WHEN LLMClassifierPlugin が実行される場合, THE LLMClassifierPlugin SHALL OCR抽出テキストまたはHTMLからタグをパージした純粋テキストノードをLLM APIに送信し、ダークパターン分類を要求する（🚨 CTO Override: HTMLタグをパージして純粋テキストノードのみを抽出。`<script>`, `<style>`, `<noscript>` は除外）
4. THE LLMClassifierPlugin SHALL LLM APIからのレスポンスを以下のJSON形式でパースする: `{is_subscription: bool, evidence_text: str, confidence: float, dark_pattern_type: str}`
5. THE LLMClassifierPlugin SHALL 環境変数 `LLM_PROVIDER`（`gemini`, `claude`, `openai`）、`LLM_API_KEY`、`LLM_MODEL` でLLMプロバイダーを設定可能とする
6. WHEN LLM_PROVIDER が `gemini` の場合, THE LLMClassifierPlugin SHALL Gemini 1.5 Pro API を使用する
7. WHEN LLM_PROVIDER が `claude` の場合, THE LLMClassifierPlugin SHALL Claude 3 API を使用する
8. WHEN LLM_PROVIDER が `openai` の場合, THE LLMClassifierPlugin SHALL GPT-4o API を使用する
9. WHEN CrawlContext の `screenshots` が存在する場合, THE LLMClassifierPlugin SHALL マルチモーダルLLM（Vision API）にスクリーンショットを送信し、視覚的コンテキストを含めた分類を行う
10. THE LLMClassifierPlugin SHALL 1回のクロール実行あたりのLLM API呼び出し回数を環境変数 `LLM_MAX_CALLS_PER_CRAWL`（デフォルト: 5）で制限する
11. WHEN LLM API呼び出し回数が上限に達した場合, THE LLMClassifierPlugin SHALL 残りの分析をスキップし、スキップ理由を CrawlContext の `metadata` に `llmclassifier_calls_limited: True` として記録する
12. IF LLM APIが利用不可（タイムアウト、認証エラー、レート制限等）の場合, THEN THE LLMClassifierPlugin SHALL エラーを CrawlContext の `errors` リストに記録し、パイプラインの実行を中断しない
13. THE LLMClassifierPlugin SHALL LLM分類結果を CrawlContext の `metadata` に `llmclassifier_results` キーでリストとして格納する
14. WHEN LLM分類結果の `confidence` が 0.7 以上かつ `is_subscription` が `True` の場合, THE LLMClassifierPlugin SHALL 該当結果を CrawlContext の `violations` に追加する

### Requirement 3: JourneyPlugin — 動的状態・ユーザージャーニーキャプチャ

**User Story:** As a コンプライアンス担当者, I want カート追加やチェックアウト遷移時に動的に出現するダークパターン（隠し料金、アップセルモーダル）が検出されること, so that 静的ページ分析では発見できない動的ダークパターンを特定できる。

#### Acceptance Criteria

1. THE JourneyPlugin SHALL CrawlPlugin 抽象基底クラスを継承し、`execute(ctx: CrawlContext) -> CrawlContext` および `should_run(ctx: CrawlContext) -> bool` を実装する
2. THE JourneyPlugin の `should_run()` SHALL CrawlContext の `site` の `plugin_config` に `JourneyPlugin` のジャーニースクリプトが設定されている場合に `True` を返す
3. WHEN JourneyPlugin が実行される場合, THE JourneyPlugin SHALL ジャーニースクリプトJSONを解析し、各ステップを定義順に逐次実行する
4. THE JourneyPlugin SHALL 以下のステップ型をサポートする: `add_to_cart`（セレクタ指定の「カートに追加」ボタンクリック）、`goto_checkout`（チェックアウトページへの遷移）、`click`（任意セレクタのクリック）、`wait`（ミリ秒指定の待機）、`screenshot`（現在状態のスクリーンショット取得）
5. THE JourneyPlugin SHALL 各ステップにアサーション定義をサポートする: `no_new_fees`（新規料金要素の非出現）、`no_upsell_modal`（アップセルモーダルの非出現）、`no_preselected_subscription`（事前選択された定期購入オプションの非存在）
6. WHEN ステップ実行前後で可視要素の差分を比較し、アサーション違反が検出された場合, THE JourneyPlugin SHALL 違反内容（ステップ名、アサーション種別、検出された要素のセレクタとテキスト）を CrawlContext の `violations` に追加する
7. THE JourneyPlugin SHALL 各ステップ実行前後のスクリーンショットを取得し、CrawlContext の `screenshots` に `journey_{step_name}_before` / `journey_{step_name}_after` のバリアント名で追加する
8. THE JourneyPlugin SHALL ジャーニースクリプトを以下のJSON形式でサポートする: `[{"step": "add_to_cart", "selector": ".add-cart-btn", "assert": {"no_new_fees": true}}, {"step": "goto_checkout", "assert": {"no_upsell_modal": true}}]`
9. IF ジャーニースクリプトのJSON形式が不正な場合, THEN THE JourneyPlugin SHALL バリデーションエラーを CrawlContext の `errors` リストに記録し、実行をスキップする
10. IF ステップ実行中にエラーが発生した場合（要素未検出、タイムアウト等）, THEN THE JourneyPlugin SHALL エラーを CrawlContext の `errors` リストに記録し、残りのステップをスキップする
11. WHEN 明示的なセレクタで要素が見つからない場合, THE JourneyPlugin SHALL Playwright の `get_by_role` 等を用いたヒューリスティック・フォールバック探索を実行する。例: `add_to_cart` ステップでは `page.get_by_role("button", name=re.compile("カート|追加|add.*cart", re.IGNORECASE))` でボタンを探索する（🚨 CTO Override: サイトUI変更でJSONスクリプトが壊れるのを防ぐフォールバック機構）
12. FOR ALL 有効な JourneyScript JSON, THE JourneyPlugin SHALL JSON をパースしてステップリストに変換し、再度JSONにシリアライズした場合に同等のステップリストが得られる（ラウンドトリップ特性）
13. THE JourneyPlugin SHALL 各ステップの実行結果（成功/失敗、アサーション結果、検出された要素数、フォールバック使用有無）を CrawlContext の `metadata` に `journey_steps` キーでリストとして格納する

### Requirement 4: UITrapPlugin — UI/UXトラップ検出

**User Story:** As a コンプライアンス担当者, I want チェックアウトフロー内の事前チェック済み有料オプション、デフォルト選択された定期購入、コンファームシェイミング等のUI/UXトラップが自動検出されること, so that 消費者が意図せず有料サービスに加入するリスクを特定できる。

#### Acceptance Criteria

1. THE UITrapPlugin SHALL CrawlPlugin 抽象基底クラスを継承し、`execute(ctx: CrawlContext) -> CrawlContext` および `should_run(ctx: CrawlContext) -> bool` を実装する
2. THE UITrapPlugin の `should_run()` SHALL CrawlContext の `html_content` が存在し、かつ CrawlContext の `metadata` に `pagefetcher_page`（Playwrightページ参照）が存在する場合に `True` を返す
3. WHEN UITrapPlugin が実行される場合, THE UITrapPlugin SHALL チェックアウトDOM内の全チェックボックス要素を走査し、デフォルトでチェック済み（`checked` 属性）かつ有料サービス・定期購入に関連するチェックボックスを検出する
4. WHEN デフォルトチェック済みの有料チェックボックスが検出された場合, THE UITrapPlugin SHALL 該当要素のセレクタ、ラベルテキスト、関連する料金情報を CrawlContext の `violations` に `sneak_into_basket` 違反種別で追加する
5. THE UITrapPlugin SHALL ラジオボタングループを走査し、「定期購入」オプションが「単品購入」オプションよりも先にデフォルト選択されているケースを検出する
6. WHEN デフォルト選択された定期購入ラジオボタンが検出された場合, THE UITrapPlugin SHALL 該当要素のセレクタ、選択肢テキスト、デフォルト選択値を CrawlContext の `violations` に `default_subscription` 違反種別で追加する
7. THE UITrapPlugin SHALL 定期購入選択要素とその解約条件テキストのDOM距離（要素数）を測定し、解約条件が選択要素から設定可能な閾値（デフォルト: 20要素）以上離れている場合に `distant_cancellation_terms` 違反として検出する
8. THE UITrapPlugin SHALL ボタンテキストのコンファームシェイミングパターンを検出する。検出対象パターン: 否定的な自己言及（「いいえ、節約したくありません」「割引は不要です」等）、感情的操作（「チャンスを逃す」「後悔する」等）
9. WHEN コンファームシェイミングパターンが検出された場合, THE UITrapPlugin SHALL 該当ボタンのセレクタ、テキスト内容、マッチしたパターン種別を CrawlContext の `violations` に `confirmshaming` 違反種別で追加する
10. THE UITrapPlugin SHALL 検出された全UI/UXトラップを CrawlContext の `metadata` に `uitrap_detections` キーでリストとして格納する
11. IF UITrapPlugin の実行中にエラーが発生した場合, THEN THE UITrapPlugin SHALL エラーを CrawlContext の `errors` リストに記録し、パイプラインの実行を中断しない

### Requirement 5: DarkPatternScore — 統合スコア算出

**User Story:** As a コンプライアンス担当者, I want 4つの検出アプローチの結果が統合された単一のダークパターンリスクスコアで評価されること, so that サイトのダークパターンリスクを一目で把握し、優先度に基づいた対応ができる。

#### Acceptance Criteria

1. THE CrawlPipeline SHALL 全プラグイン実行完了後に DarkPatternScore を算出するポストプロセスを実行する
2. THE DarkPatternScore SHALL 以下の4つのサブスコアに対し Max Pooling（最大値選択）を適用して算出する: CSSVisualPlugin の `cssvisual_deception_score`、LLMClassifierPlugin の分類結果から算出したスコア、JourneyPlugin のアサーション違反率、UITrapPlugin の検出数から算出したスコア。総合スコアは実行済みサブスコアと未実行ペナルティの最大値とする（🚨 CTO Override: 加重平均は禁止）
3. WHEN サブスコアを提供するプラグインが実行されなかった場合（`should_run()` が `False`）, THE DarkPatternScore SHALL 該当プラグインに未知リスクペナルティベースライン（デフォルト: 0.15、環境変数 `DARK_PATTERN_PENALTY_BASELINE`）を割り当て、Max Pooling の候補に含める（🚨 CTO Override: 未実行プラグインの除外・再計算は禁止。Journeyスキップでスコアが下がるインセンティブの歪みを防止）
4. THE DarkPatternScore SHALL 0（ダークパターン未検出）から 1（最大リスク）の範囲で算出される
5. THE DarkPatternScore SHALL CrawlContext の `metadata` に `darkpattern_score` キーで格納する
6. THE DarkPatternScore SHALL 各サブスコアの内訳を CrawlContext の `metadata` に `darkpattern_subscores` キーで `{css_visual: float, llm_classifier: float, journey: float, ui_trap: float}` 形式で格納する
7. WHEN DarkPatternScore が設定可能な閾値（デフォルト: 0.6、環境変数 `DARK_PATTERN_SCORE_THRESHOLD`）以上の場合, THE CrawlPipeline SHALL CrawlContext の `violations` に `high_dark_pattern_risk` 違反を追加する

### Requirement 6: パイプラインステージ統合と実行順序

**User Story:** As a 開発者, I want 4つの新規プラグインがCrawlPipelineの適切なステージに統合され、既存プラグインとの実行順序が明確に定義されていること, so that プラグイン間のデータ依存関係が正しく解決される。

#### Acceptance Criteria

1. THE CrawlPipeline の PageFetcher ステージ SHALL JourneyPlugin を PreCaptureScriptPlugin の後、ModalDismissPlugin の前に実行する（実行順序: LocalePlugin → ページ取得 → PreCaptureScriptPlugin → JourneyPlugin → ModalDismissPlugin → スクリーンショット撮影）
2. THE CrawlPipeline の DataExtractor ステージ SHALL CSSVisualPlugin を StructuredDataPlugin の後に実行する（実行順序: StructuredDataPlugin → ShopifyPlugin → HTMLParserPlugin → OCRPlugin → CSSVisualPlugin → LLMClassifierPlugin）
3. THE CrawlPipeline の DataExtractor ステージ SHALL LLMClassifierPlugin を OCRPlugin の後に実行する（OCR結果とスクリーンショットを入力として使用するため）
4. THE CrawlPipeline の Validator ステージ SHALL UITrapPlugin を ContractComparisonPlugin の後に実行する
5. THE CrawlPipeline SHALL 全4プラグインをデフォルトで登録し、各プラグインの `should_run()` が実行条件に基づいて有効化/無効化を制御する
6. THE 全4プラグイン SHALL MonitoringSite の `plugin_config` によるサイト単位の有効/無効オーバーライドをサポートする
7. THE 全4プラグイン SHALL 環境変数 `PIPELINE_DISABLED_PLUGINS` によるグローバル無効化をサポートする

### Requirement 7: CSSVisualPlugin — コントラスト比算出

**User Story:** As a 開発者, I want コントラスト比の算出がWCAG 2.0の相対輝度計算式に基づいていること, so that 業界標準に準拠した正確なコントラスト比判定ができる。

#### Acceptance Criteria

1. THE CSSVisualPlugin SHALL WCAG 2.0 の相対輝度（Relative Luminance）計算式を使用してコントラスト比を算出する
2. THE CSSVisualPlugin SHALL RGB値から相対輝度を算出する際、sRGBガンマ補正（線形化）を適用する
3. THE CSSVisualPlugin SHALL コントラスト比を `(L1 + 0.05) / (L2 + 0.05)` の式で算出する（L1は明るい方の相対輝度、L2は暗い方の相対輝度）
4. FOR ALL 有効なRGBカラーペア, THE CSSVisualPlugin SHALL 算出したコントラスト比が 1:1（同色）から 21:1（白黒）の範囲内であることを保証する
5. THE CSSVisualPlugin SHALL `rgba()` 形式の色値に対応し、アルファチャネルを考慮した実効色を算出する

### Requirement 8: LLMClassifierPlugin — プロンプトエンジニアリングとレスポンスパース

**User Story:** As a 開発者, I want LLM APIへのプロンプトが構造化され、レスポンスが確実にパースされること, so that LLM分類結果の品質と信頼性が確保される。

#### Acceptance Criteria

1. THE LLMClassifierPlugin SHALL LLM APIに送信するプロンプトに以下の指示を含める: 分析対象テキストの提示、定期購入/ダークパターン条件の判定要求、JSON形式での出力指定
2. THE LLMClassifierPlugin SHALL プロンプトテンプレートを以下の形式で定義する: 「以下のECサイトテキストを分析し、隠された定期購入条件やダークパターンが含まれているか判定してください。出力はJSON形式: {reasoning: str, evidence_text: str, confidence: float, is_subscription: bool, dark_pattern_type: str}」（🚨 CTO Override: LLMの自己回帰特性を活用するため、reasoning→evidence_text→confidence→結論の順序でフィールドを定義し、Chain of Thought を誘発する）
3. WHEN LLM APIレスポンスがJSON形式でない場合, THE LLMClassifierPlugin SHALL レスポンス内のJSONブロック（```json ... ``` またはJSON文字列）を抽出してパースを試みる
4. IF LLM APIレスポンスからJSONをパースできない場合, THEN THE LLMClassifierPlugin SHALL パースエラーを CrawlContext の `errors` に記録し、該当分析結果をスキップする
5. THE LLMClassifierPlugin SHALL LLM APIレスポンスの `confidence` 値が 0.0 から 1.0 の範囲外の場合、0.0-1.0 にクランプする
6. FOR ALL 有効な LLM分類結果JSON, THE LLMClassifierPlugin SHALL JSONをパースして分類結果オブジェクトに変換し、再度JSONにシリアライズした場合に同等のオブジェクトが得られる（ラウンドトリップ特性）
7. THE LLM Structured Outputs スキーマ SHALL 全フィールドを必須（Required）として定義し、default 値を設定しない（🚨 CTO Override: Strict Mode 対応。default="" はLLMがフィールドを欠落させるハルシネーションの原因となるため禁止。証拠がない場合はLLMに「該当なし」と明記させる）

### Requirement 9: JourneyPlugin — 可視要素差分比較とアサーション評価

**User Story:** As a 開発者, I want ジャーニーステップ前後の可視要素差分が正確に比較され、アサーション違反が確実に検出されること, so that 動的に出現するダークパターンの見逃しを防止できる。

#### Acceptance Criteria

1. THE JourneyPlugin SHALL 各ステップ実行前に、Playwright の `page.locator()` + `isVisible()` を使用して画面上で可視な料金関連要素・モーダル要素・チェックボックス要素のスナップショット（テキスト内容とセレクタのセット）を取得する（🚨 CTO Override: 生HTML文字列のDOMスナップショットは禁止。React/Vue等の仮想DOM再レンダリングノイズを排除するため、可視要素のみをトラッキングする）
2. THE JourneyPlugin SHALL 各ステップ実行後に可視要素スナップショットを再取得し、ステップ前のスナップショットと比較する
3. WHEN `no_new_fees` アサーションが設定されている場合, THE JourneyPlugin SHALL ステップ前後で可視（`isVisible()` == true）な要素の中から、金額正規表現（`/[¥$€£]\s*[\d,]+/` 等）にマッチするテキスト要素の増減のみをトラッキングし、新規出現した金額要素を検出する（🚨 CTO Override: DOM構造の差分ではなく、可視テキストの金額パターンマッチで判定）
4. WHEN `no_upsell_modal` アサーションが設定されている場合, THE JourneyPlugin SHALL ステップ後に `page.locator('[role="dialog"]:visible, .modal:visible, .popup:visible, [class*="upsell"]:visible')` で可視モーダルの新規出現を検出する
5. WHEN `no_preselected_subscription` アサーションが設定されている場合, THE JourneyPlugin SHALL `page.locator('input[type="checkbox"]:checked:visible, input[type="radio"]:checked:visible')` で可視のチェック済み要素を検出し、定期購入キーワードとの関連を評価する
6. THE JourneyPlugin SHALL 可視要素スナップショット差分の結果を CrawlContext の `metadata` に `journey_dom_diffs` キーで各ステップごとに格納する

### Requirement 10: UITrapPlugin — コンファームシェイミングパターン辞書

**User Story:** As a 開発者, I want コンファームシェイミングの検出パターンが拡張可能な辞書形式で管理されること, so that 新しいパターンの追加が容易で、日本語・英語の両方に対応できる。

#### Acceptance Criteria

1. THE UITrapPlugin SHALL コンファームシェイミングパターンを日本語と英語の両方で定義する
2. THE UITrapPlugin SHALL 以下の日本語パターンを検出する: 「いいえ」で始まり否定的な自己言及を含むテキスト（例: 「いいえ、節約したくありません」）、「不要です」「必要ありません」を含む利益放棄表現、「チャンスを逃す」「後悔」「損」を含む感情的操作表現
3. THE UITrapPlugin SHALL 以下の英語パターンを検出する: "No" で始まり否定的な自己言及を含むテキスト（例: "No thanks, I don't want to save money"）、"miss out"、"regret"、"lose" を含む感情的操作表現
4. THE UITrapPlugin SHALL パターン辞書を設定ファイルまたは環境変数で拡張可能とする
5. THE UITrapPlugin SHALL パターンマッチング時に大文字小文字を区別しない

### Requirement 11: DBモデル拡張 — ダークパターン検出結果の永続化

**User Story:** As a 開発者, I want ダークパターン検出結果がDBに構造化して保存されること, so that 検出履歴の分析とダッシュボード表示が可能になる。

#### Acceptance Criteria

1. THE VerificationResult SHALL `dark_pattern_score` カラム（Float型、nullable）を持つ
2. THE VerificationResult SHALL `dark_pattern_subscores` カラム（JSON型、nullable）を持ち、各サブスコアの内訳を格納する
3. THE VerificationResult SHALL `dark_pattern_types` カラム（JSON型、nullable）を持ち、検出されたダークパターン種別のリストを格納する
4. THE Violation テーブル SHALL `dark_pattern_category` カラム（String型、nullable）を持ち、ダークパターンのカテゴリ（`visual_deception`, `hidden_subscription`, `sneak_into_basket`, `default_subscription`, `confirmshaming`, `distant_cancellation_terms`, `high_dark_pattern_risk`）を格納する
5. THE 全新規カラム SHALL nullable として定義され、既存レコードに影響を与えない
6. THE Alembic マイグレーション SHALL ダウングレード時に追加カラムを削除し、既存データを保持する

### Requirement 12: ダークパターン検出API

**User Story:** As a フロントエンド開発者, I want API経由でサイトのダークパターン検出結果を取得できること, so that ダッシュボードにダークパターンリスクスコアと検出詳細を表示できる。

#### Acceptance Criteria

1. THE API SHALL `GET /api/sites/{site_id}/dark-patterns` エンドポイントで対象サイトの最新ダークパターン検出結果を返却する
2. THE API レスポンス SHALL 以下のフィールドを含む: `dark_pattern_score`（float）、`subscores`（dict: css_visual, llm_classifier, journey, ui_trap）、`detected_patterns`（list: 各パターンの種別、証拠、severity）、`detected_at`（datetime）
3. THE API SHALL `GET /api/sites/{site_id}/dark-patterns/history` エンドポイントでダークパターンスコアの履歴を返却する
4. THE 履歴API SHALL ページネーション（`limit`、`offset`）をサポートし、デフォルト `limit=50` とする
5. WHEN 存在しない site_id が指定された場合, THE API SHALL 404 エラーを返す
6. WHEN ダークパターン検出結果が存在しない場合, THE API SHALL `dark_pattern_score: null` を含む空の結果を返却する

### Requirement 13: LLMClassifierPlugin — レート制限とコスト制御

**User Story:** As a 運用者, I want LLM API呼び出しのレート制限とコスト制御が適切に行われること, so that 大量サイトクロール時のAPI費用が予算内に収まる。

#### Acceptance Criteria

1. THE LLMClassifierPlugin SHALL 環境変数 `LLM_MAX_CALLS_PER_CRAWL`（デフォルト: 5）で1回のクロール実行あたりのAPI呼び出し上限を制御する
2. THE LLMClassifierPlugin SHALL 環境変数 `LLM_RATE_LIMIT_RPM`（デフォルト: 60）でLLM APIへのリクエスト/分の上限を制御する
3. WHEN レート制限に達した場合, THE LLMClassifierPlugin SHALL リクエストを遅延させ、制限解除後に再開する
4. THE LLMClassifierPlugin SHALL 各API呼び出しの入力トークン数と出力トークン数を CrawlContext の `metadata` に `llmclassifier_token_usage` キーで記録する
5. THE LLMClassifierPlugin SHALL 環境変数 `LLM_MAX_INPUT_TOKENS`（デフォルト: 4000）で1回のAPI呼び出しあたりの入力テキスト長を制限する。テキスト抽出時はHTMLタグをパージして純粋テキストノードのみを抽出し（`<script>`, `<style>`, `<noscript>` は除外）、上限超過時は Middle-Out Truncation アルゴリズムを適用する: 上部20%（ヘッダー・価格表示）+ 下部30%（フッター・解約条件）を優先保持し、中間50%を切り捨てる。切り詰め箇所には `[...中略...]` マーカーを挿入する（🚨 CTO Override: 単純な先頭切り捨ては厳禁。フッターに隠された解約条件の証拠隠滅を防止）
6. THE LLMClassifierPlugin および DynamicLLMValidatorPlugin SHALL 外部LLM API呼び出しに指数バックオフ（Exponential Backoff）による最低3回のリトライを実装する。HTTP 429（Rate Limit）、502/503（Server Overloaded）等の一時的エラーに対応し、全リトライ失敗後のみエラーを記録する（🚨 CTO Override: 1回のAPIエラーで即座に passed=True を返す実装は致命的な偽陰性を生むため禁止）
7. THE DynamicLLMValidatorPlugin のプロンプト構築 SHALL `{page_text}` プレースホルダが prompt_template に含まれている場合は replace のみを行い、末尾にページテキストを二重挿入しない。プレースホルダがない場合のみフォールバックとして末尾に追加する（🚨 CTO Override: 二重挿入はトークン制限突破とAPIコスト2倍の原因となるため禁止）

### Requirement 14: dark-pattern-notification 連携

**User Story:** As a コンプライアンス担当者, I want ダークパターン検出結果がdark-pattern-notification specの通知フローと連携すること, so that 高リスクのダークパターンが検出された際に自動通知が送信される。

#### Acceptance Criteria

1. THE 4つの新規プラグイン SHALL 検出結果を CrawlContext の `violations` に追加する際、既存の NotificationPlugin が認識可能な形式（`violation_type`, `severity`, `site_name`, `evidence_url` フィールドを含む dict）で格納する
2. WHEN DarkPatternScore が閾値以上の場合に追加される `high_dark_pattern_risk` 違反 SHALL severity を `critical` に設定する
3. THE `sneak_into_basket`, `default_subscription`, `confirmshaming` 違反 SHALL severity を `warning` に設定する
4. THE `visual_deception`（低コントラスト、CSS隠蔽）違反 SHALL severity を `warning` に設定する
5. THE `distant_cancellation_terms` 違反 SHALL severity を `info` に設定する
6. THE 全違反 SHALL `dark_pattern_category` フィールドを含み、NotificationPlugin の通知テンプレートで違反カテゴリとして表示可能とする

### Requirement 15: 検出ルールの動的拡張性（Detection Rule Extensibility）

**User Story:** As a プロダクトオーナー, I want 決済加盟店の商品特性や契約条件の変更に応じて、コード変更なしに検出項目と摘発ロジックを追加・変更できること, so that 新しい契約要件が発生した際に迅速に対応できる。

#### Acceptance Criteria

1. THE System SHALL 検出ルールを JSON 形式の `DetectionRuleSet` として定義し、`ContractCondition` または `MonitoringSite.plugin_config` に格納可能とする
2. THE DetectionRuleSet SHALL 以下の構造をサポートする: `{"rules": [{"rule_id": str, "rule_type": str, "target": str, "condition": dict, "severity": str, "dark_pattern_category": str}]}`
3. THE `rule_type` SHALL 以下の組み込み型をサポートする: `css_selector_exists`（CSSセレクタの存在チェック）、`text_pattern_match`（正規表現テキストマッチ）、`price_threshold`（価格閾値チェック）、`element_attribute_check`（要素属性値チェック）、`dom_distance`（要素間DOM距離チェック）
4. THE System SHALL `rule_type: custom_evaluator` をサポートし、Python の callable パス（例: `src.rules.my_custom_rule.evaluate`）を指定して任意の検出ロジックを実行可能とする
5. THE 各プラグイン（CSSVisualPlugin, LLMClassifierPlugin, JourneyPlugin, UITrapPlugin）SHALL 実行時に `DetectionRuleSet` から自身のステージに該当するルールを読み込み、組み込みロジックに加えてルールベースの検出を実行する
6. WHEN DetectionRuleSet のルールが違反を検出した場合, THE System SHALL ルール定義の `severity` と `dark_pattern_category` を使用して CrawlContext の `violations` に追加する
7. THE DetectionRuleSet SHALL 加盟店（MonitoringSite）単位でオーバーライド可能とし、グローバルルール + サイト固有ルールのマージをサポートする
8. THE System SHALL 環境変数 `DETECTION_RULES_PATH` でグローバルルールセットのJSONファイルパスを指定可能とする
9. IF DetectionRuleSet のJSON形式が不正な場合, THEN THE System SHALL バリデーションエラーをログに記録し、組み込みロジックのみで実行を継続する
10. THE DetectionRuleSet SHALL `enabled: bool`（デフォルト: true）フィールドをサポートし、個別ルールの有効/無効を切り替え可能とする
11. THE DynamicComplianceRule の `prompt_template` フィールド SHALL 登録時に必須変数 `{page_text}` の存在を Fail-Fast バリデーションで検査する。`{page_text}` が含まれていない場合はバリデーションエラーを返し、登録を拒否する（🚨 CTO Override: 後段の replace 実行時の KeyError/ValueError によるシステムクラッシュを防止）

### Requirement 16: dark_pattern_type 分類体系（Classification Taxonomy）

**User Story:** As a データアナリスト, I want ダークパターンの検出結果が標準化された分類体系で記録されること, so that 検出結果の集計・フィルタリング・トレンド分析が正確に行える。

#### Acceptance Criteria

1. THE System SHALL 以下の `dark_pattern_type` 有効値リストを定義する: `visual_deception`（視覚的欺瞞）、`hidden_subscription`（隠れた定期購入）、`sneak_into_basket`（カートへの忍び込み）、`default_subscription`（デフォルト定期購入選択）、`confirmshaming`（コンファームシェイミング）、`distant_cancellation_terms`（遠隔解約条件）、`hidden_fees`（隠し料金）、`urgency_pattern`（偽の緊急性）、`price_manipulation`（価格操作）、`misleading_ui`（誤解を招くUI）
2. THE LLMClassifierPlugin SHALL LLM APIレスポンスの `dark_pattern_type` を有効値リストに正規化する。有効値リストに含まれない値は `other` にフォールバックする
3. THE 全プラグイン SHALL 違反レコードの `dark_pattern_category` フィールドに有効値リストの値のみを使用する
4. THE API レスポンス SHALL `detected_patterns` の各パターンに `dark_pattern_type` フィールドを含み、有効値リストの値のみを返却する
5. THE DetectionRuleSet の `dark_pattern_category` フィールド SHALL 有効値リストの値のみを受け付け、不正な値はバリデーションエラーとする

### Requirement 17: CSSVisualPlugin — 重要文言の小フォント表示検出（misleading_font_size）

**User Story:** As a コンプライアンス担当者, I want 購入手続きに必要な重要な文言（定期購入・自動更新・解約・手数料等）がページ全体のフォントサイズと比較して著しく小さく表示されているケースを全て検出したい, so that 消費者の視認性を意図的に低下させた表示を特定し、コンプライアンス違反として記録できる。

#### Acceptance Criteria

1. WHEN CSSVisualPlugin が実行される場合, THE CSSVisualPlugin SHALL ページ全体のテキスト要素のフォントサイズ中央値（median）を算出する
2. WHEN テキスト要素のフォントサイズがページ中央値の 75% 未満（設定可能、環境変数 `MISLEADING_FONT_SIZE_RATIO`、デフォルト: 0.75）の場合, THE CSSVisualPlugin SHALL そのテキストが重要キーワードを含むか判定する
3. THE CSSVisualPlugin SHALL 以下の日本語重要キーワードを検出対象とする: 「定期」「自動更新」「自動継続」「解約」「キャンセル」「返金」「返品」「手数料」「縛り」「最低利用期間」「違約金」「特定商取引」「重要事項」「注意事項」「同意」「承諾」
4. THE CSSVisualPlugin SHALL 以下の英語重要キーワードを検出対象とする: "subscription", "auto-renew", "auto renewal", "cancel", "cancellation", "refund", "fee", "charge", "terms", "important", "notice", "agree", "consent", "binding"
5. WHEN 重要キーワードを含むテキスト要素のフォントサイズがページ中央値の 75% 未満の場合, THE CSSVisualPlugin SHALL 該当要素を `misleading_font_size` 違反として検出し、要素のセレクタ・テキスト・フォントサイズ・ページ中央値・比率を証拠として記録する
6. THE `misleading_font_size` 違反 SHALL severity を `warning` に設定し、`dark_pattern_category` を `misleading_font_size` に設定する
7. WHEN LLMClassifierPlugin が実行される場合, THE LLMClassifierPlugin SHALL プロンプトに「フォントサイズが小さく視認性が低下した状態で表示されている重要な購入条件テキスト（定期購入・解約・手数料等）が存在するか」の判定指示を含める
8. WHEN LLM が小フォント重要文言を検出した場合, THE LLMClassifierPlugin SHALL `dark_pattern_type: "misleading_font_size"` として違反を記録する
9. THE System SHALL `misleading_font_size` を `VALID_DARK_PATTERN_TYPES` の有効値リストに追加する
10. THE `misleading_font_size` 違反 SHALL dark-pattern-notification の通知フローと連携し、severity `warning` として通知される

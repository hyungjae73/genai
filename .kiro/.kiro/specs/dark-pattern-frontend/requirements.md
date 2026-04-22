# 要件定義書

## はじめに

ダークパターン検出機能のフロントエンドUI実装要件。バックエンドで実装済みのダークパターン検出・スコアリング・LLMルール・ダークサイト候補検出の各機能を、React + TypeScript フロントエンドに統合する。対象は9カテゴリ（FR-1〜FR-9）のUI変更・新規コンポーネント作成であり、既存の SiteDetailPanel、Rules、Dashboard、Alerts の各ページを拡張する。

## 用語集

- **DarkPatternTab**: サイト詳細パネル内に新設するダークパターン専用タブコンポーネント
- **SiteDetailPanel**: サイト詳細情報を表示する既存タブパネルコンポーネント（`SiteDetailPanel.tsx`）
- **DarkPatternScore**: ダークパターン検出の総合リスクスコア（0.0〜1.0）
- **SubScore**: CSS視覚欺瞞・LLM分類・ジャーニー・UIトラップの4種サブスコア
- **DynamicRule**: LLMベースの動的検出ルール（DB管理、CRUD可能）
- **BuiltinRule**: ハードコードされた静的コンプライアンスチェックルール（5件）
- **RulesPage**: チェックルール一覧ページ（`Rules.tsx`）
- **DarksiteCandidate**: ダークサイト（偽サイト）候補のドメイン・コンテンツ情報
- **DarksitePreviewPanel**: ダークサイト候補のコンテンツ比較を表示するコンポーネント
- **DashboardPage**: 統計ダッシュボードページ（`Dashboard.tsx`）
- **AlertsPage**: アラート一覧ページ（`Alerts.tsx`）
- **ApiService**: フロントエンドAPI通信サービス（`api.ts`）
- **MerchantCategory**: 加盟店カテゴリ（subscription, ec_general, digital_content, travel, other）
- **ScoreGauge**: スコアを色分けプログレスバーで表示するUI要素
- **HistoryChart**: Chart.js による時系列折れ線グラフコンポーネント

## 要件

### 要件 1: ダークパターンスコア表示タブ（FR-1）

**ユーザーストーリー:** 監視担当者として、サイト詳細画面でダークパターンの総合リスクスコアとサブスコア内訳を確認したい。早期にリスクの高いサイトを特定するためである。

#### 受入条件

1. WHEN ユーザーがサイト詳細画面を開いた時、THE SiteDetailPanel SHALL 6番目のタブとして「ダークパターン」タブボタンを表示する
2. WHEN ユーザーが「ダークパターン」タブを選択した時、THE DarkPatternTab SHALL `GET /api/sites/{site_id}/dark-patterns` APIを呼び出し、最新のダークパターン検出結果を取得する
3. WHEN 検出結果が存在する時、THE DarkPatternTab SHALL 総合リスクスコアをプログレスバー形式で表示し、スコア値に応じて色分けする（0〜0.3: 緑、0.3〜0.6: 黄、0.6〜1.0: 赤）
4. WHEN 検出結果が存在する時、THE DarkPatternTab SHALL CSS視覚欺瞞・LLM分類・ジャーニー・UIトラップの4種サブスコアを横棒グラフで表示する
5. WHEN 検出結果が存在する時、THE DarkPatternTab SHALL 検出されたダークパターンタイプをBadgeコンポーネントで severity 別に色分け表示する（critical: 赤、warning: 黄、info: 青）
6. WHEN 検出結果が存在する時、THE DarkPatternTab SHALL 最終検出日時を表示する
7. IF 検出結果が存在しない時（APIがnullを返した時）、THEN THE DarkPatternTab SHALL 「ダークパターン検出データがありません」というメッセージを表示する
8. IF API呼び出しが失敗した時、THEN THE DarkPatternTab SHALL エラーメッセージを表示し、コンソールにエラーを記録する
9. THE ApiService SHALL `getDarkPatterns(siteId: number)` 関数と `DarkPatternResult` 型定義を提供する

### 要件 2: ダークパターンスコア履歴チャート（FR-2）

**ユーザーストーリー:** 監視担当者として、サイトのダークパターンスコアの時系列推移を確認したい。リスクの増減トレンドを把握するためである。

#### 受入条件

1. WHEN ユーザーがDarkPatternTab内で「スコア推移」サブタブを選択した時、THE HistoryChart SHALL `GET /api/sites/{site_id}/dark-patterns/history` APIを呼び出し、スコア履歴データを取得する
2. WHEN 履歴データが存在する時、THE HistoryChart SHALL Chart.js Line コンポーネントで総合スコアと4種サブスコアの計5本の折れ線グラフを表示する
3. WHEN 履歴データが存在する時、THE HistoryChart SHALL X軸に検出日時、Y軸にスコア値（0.0〜1.0）を表示する
4. THE HistoryChart SHALL 各折れ線を色分けし、凡例（総合スコア、CSS視覚欺瞞、LLM分類、ジャーニー、UIトラップ）を表示する
5. IF 履歴データが空の時、THEN THE HistoryChart SHALL 「スコア履歴データがありません」というメッセージを表示する
6. THE ApiService SHALL `getDarkPatternHistory(siteId: number, limit?: number, offset?: number)` 関数と `DarkPatternHistoryResponse` 型定義を提供する

### 要件 3: 加盟店カテゴリ設定（FR-3）

**ユーザーストーリー:** 管理者として、サイトに加盟店カテゴリを設定したい。カテゴリに応じた適切な検出ルールが適用されるようにするためである。

#### 受入条件

1. WHEN ユーザーがサイト編集フォームを開いた時、THE サイト編集フォーム SHALL 「加盟店カテゴリ」Selectコンポーネントを表示する
2. THE サイト編集フォーム SHALL 以下の選択肢を提供する: subscription（定期購入）、ec_general（EC一般）、digital_content（デジタル）、travel（旅行）、other（その他）
3. WHEN ユーザーがカテゴリを選択して保存した時、THE サイト編集フォーム SHALL `PUT /api/sites/{site_id}` APIに `merchant_category` パラメータを含めて送信する
4. THE サイト編集フォーム SHALL カテゴリ選択欄の下に「カテゴリに応じて適用される検出ルールが変わります」という説明テキストを表示する
5. THE ApiService SHALL `Site` 型に `merchant_category?: string` フィールドを追加し、`updateSite` 関数のパラメータに `merchant_category` を含める


### 要件 4: 動的LLMルール管理CRUD画面（FR-4）

**ユーザーストーリー:** 管理者として、LLMベースのダークパターン検出ルールを作成・編集・削除したい。新たな検出パターンに柔軟に対応するためである。

#### 受入条件

1. WHEN ユーザーがRulesPageを開いた時、THE RulesPage SHALL 「ビルトイン」と「LLMルール」の2つのタブを表示する
2. WHEN ユーザーが「ビルトイン」タブを選択した時、THE RulesPage SHALL 既存の静的コンプライアンスルール5件を従来通り表示する
3. WHEN ユーザーが「LLMルール」タブを選択した時、THE RulesPage SHALL `GET /api/dark-patterns/rules` APIを呼び出し、動的LLMルール一覧を取得して表示する
4. WHEN ユーザーが「LLMルール」タブを表示している時、THE RulesPage SHALL カテゴリフィルターと重要度フィルターのSelectコンポーネントを表示する
5. WHEN ユーザーが「新規LLMルール登録」ボタンをクリックした時、THE RulesPage SHALL ルール登録モーダルを表示する
6. THE ルール登録モーダル SHALL 以下の入力フィールドを提供する: ルール名（必須）、説明、重要度Select（critical/warning/info）、カテゴリSelect、確信度閾値（数値）、実行順序（数値）、作成者（必須）、プロンプトテンプレート（複数行textarea、必須）、対象カテゴリ（複数選択）、対象サイトID（複数入力）
7. WHEN ユーザーがプロンプトテンプレートを入力した時、THE ルール登録モーダル SHALL テンプレート内に `{page_text}` プレースホルダーが含まれているかバリデーションし、含まれていない場合は警告メッセージを表示する
8. WHEN ユーザーが登録ボタンをクリックし、バリデーションが通過した時、THE ルール登録モーダル SHALL `POST /api/dark-patterns/rules` APIを呼び出してルールを作成し、一覧を再取得する
9. WHEN ユーザーがルールカードの「編集」ボタンをクリックした時、THE RulesPage SHALL 編集モーダルを表示し、既存のルール情報をフォームに事前入力する
10. WHEN ユーザーが編集モーダルで保存した時、THE RulesPage SHALL `PUT /api/dark-patterns/rules/{id}` APIを呼び出してルールを更新する
11. WHEN ユーザーがルールカードの「削除」ボタンをクリックした時、THE RulesPage SHALL 確認ダイアログを表示し、確認後に `DELETE /api/dark-patterns/rules/{id}` APIを呼び出してルールを削除する
12. WHEN ユーザーがルールカードの「無効化」ボタンをクリックした時、THE RulesPage SHALL `PUT /api/dark-patterns/rules/{id}` APIで `is_active: false` を送信してルールを無効化する
13. THE ApiService SHALL `DynamicRule`、`DynamicRuleCreate`、`DynamicRuleUpdate` 型定義と、`getDynamicRules`、`createDynamicRule`、`updateDynamicRule`、`deleteDynamicRule` 関数を提供する
14. IF API呼び出しが失敗した時、THEN THE RulesPage SHALL エラーメッセージをユーザーに表示する

### 要件 5: サイト別検出ルールセット表示（FR-5）

**ユーザーストーリー:** 監視担当者として、特定のサイトにどの検出ルールが適用されているかを確認したい。検出結果の根拠を理解するためである。

#### 受入条件

1. WHEN ユーザーがDarkPatternTab内で「適用ルール」サブタブを選択した時、THE DarkPatternTab SHALL ビルトインルール5件とサイトに適用されるLLMルールの一覧を表示する
2. THE DarkPatternTab SHALL LLMルールについて、`applicable_site_ids` に当該サイトIDが含まれるルール、または `applicable_site_ids` がnull（全サイト対象）のルールを「適用中」として表示する
3. THE DarkPatternTab SHALL 適用対象外のLLMルールをグレーアウトして「対象外」ラベル付きで表示する
4. THE DarkPatternTab SHALL 各ルールの重要度Badgeを表示する
5. THE DarkPatternTab SHALL 「LLMルールの追加・編集は『チェックルール』ページから行えます」という案内テキストを表示する

### 要件 6: 違反カテゴリバッジ表示（FR-6）

**ユーザーストーリー:** 監視担当者として、アラート一覧でダークパターンの違反カテゴリを視覚的に確認したい。違反の種類を素早く把握するためである。

#### 受入条件

1. WHEN アラートに `dark_pattern_category` が設定されている時、THE AlertsPage SHALL アラートカードのヘッダーバッジ列にダークパターンカテゴリBadgeを追加表示する
2. THE AlertsPage SHALL カテゴリ別に以下の色分けを適用する: visual_deception=紫、hidden_subscription=赤、confirmshaming=オレンジ、hidden_fees=赤、urgency_pattern=黄、その他=グレー
3. WHEN アラートに `dark_pattern_confidence` が設定されている時、THE AlertsPage SHALL アラートカード内に「確信度: {値}」を表示する
4. THE AlertsPage SHALL アラートフィルターに「ダークパターンカテゴリ」Selectを追加し、カテゴリ別の絞り込みを可能にする
5. THE ApiService SHALL `Alert` 型に `dark_pattern_category?: string` と `dark_pattern_confidence?: number` フィールドを追加する

### 要件 7: ジャーニースクリプトGUIエディタ（FR-7）

**ユーザーストーリー:** 管理者として、サイトのユーザージャーニースクリプトをGUIから編集・保存したい。購入フローの検証シナリオを設定するためである。

#### 受入条件

1. WHEN ユーザーがDarkPatternTab内で「ジャーニー設定」サブタブを選択した時、THE DarkPatternTab SHALL ジャーニースクリプトエディタを表示する
2. THE ジャーニースクリプトエディタ SHALL textareaベースの複数行入力フィールドを提供する
3. THE ジャーニースクリプトエディタ SHALL 利用可能なコマンド一覧（navigate, click, wait, assert_visible, assert_not_visible, fill, scroll）をリファレンスとして表示する
4. WHEN ユーザーが「バリデーション」ボタンをクリックした時、THE ジャーニースクリプトエディタ SHALL 各行が有効なコマンド形式であるかクライアントサイドでバリデーションし、結果を表示する
5. WHEN ユーザーが「保存」ボタンをクリックし、バリデーションが通過した時、THE ジャーニースクリプトエディタ SHALL `PUT /api/sites/{site_id}` APIに `journey_script` パラメータを含めて送信する
6. IF バリデーションエラーがある時、THEN THE ジャーニースクリプトエディタ SHALL エラー行番号とエラー内容を表示する

### 要件 8: ダッシュボード統合（FR-8）

**ユーザーストーリー:** 監視担当者として、ダッシュボードでダークパターン検出の全体統計を確認したい。組織全体のリスク状況を俯瞰するためである。

#### 受入条件

1. THE DashboardPage SHALL 既存の統計カード群に加えて「高リスクサイト数」と「DP検出数」の2枚の統計カードを表示する
2. WHEN 統計データが取得された時、THE DashboardPage SHALL ダークパターンスコア分布（低リスク: 0〜0.3、中リスク: 0.3〜0.6、高リスク: 0.6〜1.0）を横棒グラフで表示する
3. WHEN 統計データが取得された時、THE DashboardPage SHALL カテゴリ別検出数（hidden_subscription、visual_deception、confirmshaming、hidden_fees 等）を横棒グラフで表示する
4. THE ApiService SHALL `Statistics` 型に `dark_pattern_high_risk_count`、`dark_pattern_detection_count`、`dark_pattern_score_distribution`、`dark_pattern_category_counts` フィールドを追加する
5. IF ダークパターン統計データが存在しない時（値がundefinedまたは0の時）、THEN THE DashboardPage SHALL ダークパターン関連セクションを非表示にする


### 要件 9: ダークサイト候補確認UI（FR-9）

**ユーザーストーリー:** 監視担当者として、サイトに関連するダークサイト（偽サイト）候補の詳細情報とコンテンツ比較を確認したい。偽サイトの脅威を正確に評価し、対応判断を行うためである。

#### 受入条件

1. WHEN ユーザーがDarkPatternTab内で「ダークサイト候補」サブタブを選択した時、THE DarkPatternTab SHALL `GET /api/sites/{site_id}/darksites` APIを呼び出し、ダークサイト候補一覧を取得して表示する
2. THE DarkPatternTab SHALL 各候補について以下の情報を表示する: 候補ドメイン、マッチ種別（typosquat/subdomain/homoglyph/tld_swap）、ドメイン類似度、コンテンツ類似度、HTTP到達可能性、リスクスコア、検出日時
3. THE DarkPatternTab SHALL リスクスコアに応じて候補カードの色分けを行う（0〜0.3: グレー、0.3〜0.6: 黄、0.6〜1.0: 赤）
4. WHEN ユーザーが候補カードの「コンテンツ確認」ボタンをクリックした時、THE DarksitePreviewPanel SHALL `GET /api/darksites/{id}/content` APIを呼び出し、コンテンツ比較データを取得してアコーディオン展開で表示する
5. WHEN コンテンツ比較データが取得された時、THE DarksitePreviewPanel SHALL 正規サイトと候補サイトのテキストを左右並列で表示し、テキスト類似度を表示する
6. WHEN コンテンツ比較データが取得された時、THE DarksitePreviewPanel SHALL 正規サイトと候補サイトの商品画像をサムネイルで並列表示し、pHash一致度を表示する
7. WHEN コンテンツ比較データに契約条件の乖離がある時、THE DarksitePreviewPanel SHALL 乖離リスト（フィールド名、正規値、候補値、重要度）を表示する
8. WHEN コンテンツ比較データに一致商品がある時、THE DarksitePreviewPanel SHALL 一致商品リスト（商品名、テキスト類似度、画像類似度）を表示する
9. IF ダークサイト候補が存在しない時、THEN THE DarkPatternTab SHALL 「ダークサイト候補は検出されていません」というメッセージを表示する
10. IF コンテンツ比較API呼び出しが失敗した時、THEN THE DarksitePreviewPanel SHALL エラーメッセージを表示する
11. THE ApiService SHALL `DarksiteCandidate`、`DarksiteContentComparison` 型定義と、`getDarksiteCandidates`、`getDarksiteContent` 関数を提供する

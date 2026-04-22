# Requirements Document

## Introduction

決済条件監視システム（Payment Compliance Monitoring System）のフロントエンドUIを再構築する。現在、スクリーンショット管理と検証・比較が独立ページとして存在するが、これらをサイト管理ページ（旧：階層型ビュー）のサイト詳細パネル内に統合する。また、サイドバーのナロービューポートでのUXを改善し、ヘルプモーダルを追加する。

## Glossary

- **Site_Management_Page**: 旧「階層型ビュー」ページ。顧客→サイトの階層構造を表示し、サイト詳細パネルを含むメインページ。ルートは `/site-management`
- **SiteDetailPanel**: サイト行を展開した際に表示される詳細パネルコンポーネント。タブ（契約条件、スクリーンショット、検証・比較、アラート）を持つ
- **Sidebar**: アプリケーション左側のナビゲーションコンポーネント。グループ化されたナビゲーションリンクを表示する
- **Baseline_Screenshot**: サイトの基準となるスクリーンショット。1サイトにつき1枚のみ保持し、上書き可能
- **Monitoring_Capture**: クロール時に取得されるスクリーンショット。旧「violation」タイプを含む通常のキャプチャ
- **Verification_Tab**: SiteDetailPanel内の検証・比較タブ。検証実行、結果表示、履歴表示を行う
- **Screenshot_Tab**: SiteDetailPanel内のスクリーンショットタブ。ベースライン画像と最新クロールスクリーンショットを表示する
- **Help_Modal**: 各ページのヘッダーに配置される「?」ボタンから開くモーダル。そのページの使い方とユーザーストーリーを説明する
- **Collapsed_Sidebar**: タブレット幅（768px〜1023px）でアイコンのみ表示されるサイドバー状態
- **Navigation_Items**: AppLayout.tsxで定義されるサイドバーのナビゲーション項目配列

## Requirements

### Requirement 1: 階層型ビューからサイト管理へのリネーム

**User Story:** As a 監視オペレーター, I want ページ名が「サイト管理」に変更されること, so that ページの目的が直感的に理解できる

#### Acceptance Criteria

1. WHEN the Site_Management_Page is rendered, THE Site_Management_Page SHALL display "サイト管理" as the page title in the `<h1>` element
2. THE Navigation_Items SHALL display "サイト管理" as the label for the Site_Management_Page link in the Sidebar
3. WHEN a user navigates to `/site-management`, THE application SHALL render the Site_Management_Page
4. WHEN a user navigates to `/hierarchy`, THE application SHALL redirect to `/site-management`
5. THE Navigation_Items SHALL use `/site-management` as the path for the Site_Management_Page link

### Requirement 2: スクリーンショットページのサイト詳細パネルへの統合

**User Story:** As a 監視オペレーター, I want サイト詳細パネル内でスクリーンショットを管理できること, so that サイトのコンテキストを離れずにスクリーンショット操作ができる

#### Acceptance Criteria

1. WHEN a user selects the "スクリーンショット" tab in the SiteDetailPanel, THE Screenshot_Tab SHALL display the Baseline_Screenshot for the selected site
2. WHEN a user selects the "スクリーンショット" tab in the SiteDetailPanel, THE Screenshot_Tab SHALL display the latest Monitoring_Capture for the selected site
3. THE Screenshot_Tab SHALL provide a re-capture button that overwrites the existing Baseline_Screenshot for the site
4. THE Screenshot_Tab SHALL provide a re-upload button that overwrites the existing Baseline_Screenshot for the site
5. THE Screenshot_Tab SHALL store exactly one Baseline_Screenshot per site, replacing the previous one on re-capture or re-upload
6. THE capture and upload modals in the Screenshot_Tab SHALL omit the screenshot type selector (baseline/violation), treating all captures as monitoring captures and all uploads as baseline overwrites
7. WHEN the `/screenshots` route is accessed, THE application SHALL redirect to `/site-management`
8. THE Navigation_Items SHALL exclude the "スクリーンショット" entry from the Sidebar

### Requirement 3: 検証・比較ページのサイト詳細パネルへの統合

**User Story:** As a 監視オペレーター, I want サイト詳細パネル内で検証・比較を実行できること, so that サイト選択の手間なく検証操作ができる

#### Acceptance Criteria

1. WHEN a user selects the "検証・比較" tab in the SiteDetailPanel, THE Verification_Tab SHALL use the currently expanded site's ID as the verification target without displaying a site selector
2. THE Verification_Tab SHALL provide a "検証実行" button that triggers verification for the selected site
3. WHEN verification completes, THE Verification_Tab SHALL display the comparison table with HTML values, OCR values, and status indicators
4. WHEN verification completes with discrepancies, THE Verification_Tab SHALL display the list of detected discrepancies with severity badges
5. THE Verification_Tab SHALL display a list of historical verification results for the selected site
6. THE Verification_Tab SHALL provide a CSV export button for the current verification result
7. WHEN the `/verification` route is accessed, THE application SHALL redirect to `/site-management`
8. THE Navigation_Items SHALL exclude the "検証・比較" entry from the Sidebar

### Requirement 4: ナビゲーション構造の更新

**User Story:** As a 監視オペレーター, I want サイドバーのナビゲーションが再構築後のページ構造を正確に反映すること, so that 存在しないページへのリンクが表示されない

#### Acceptance Criteria

1. THE Navigation_Items SHALL contain the "サイト管理" item with path `/site-management` in the navigation group
2. THE Navigation_Items SHALL exclude the "スクリーンショット" item (path `/screenshots`)
3. THE Navigation_Items SHALL exclude the "検証・比較" item (path `/verification`)
4. IF the "分析" navigation group contains zero items after removal, THEN THE AppLayout SHALL either remove the empty group or reassign "サイト管理" to the "分析" group
5. THE App.tsx route configuration SHALL include redirect routes from `/screenshots` and `/verification` to `/site-management`

### Requirement 5: サイドバーのホバー展開（タブレット幅）

**User Story:** As a 監視オペレーター, I want タブレット幅でサイドバーにホバーすると全ラベルが表示されること, so that 狭い画面でもナビゲーション項目を確認できる

#### Acceptance Criteria

1. WHILE the viewport width is between 768px and 1023px, THE Sidebar SHALL render in collapsed mode displaying icons only
2. WHEN the user hovers (mouseenter) over the Collapsed_Sidebar, THE Sidebar SHALL temporarily expand to display full navigation labels alongside icons
3. WHEN the user moves the cursor away (mouseleave) from the expanded Sidebar, THE Sidebar SHALL return to collapsed mode displaying icons only
4. WHILE the viewport width is less than 768px, THE Sidebar SHALL remain hidden and accessible only through the hamburger menu drawer
5. WHILE the viewport width is 1024px or greater, THE Sidebar SHALL remain fully expanded with labels visible at all times
6. WHEN the Collapsed_Sidebar expands on hover, THE Sidebar SHALL expand with a CSS transition of 200ms or less to provide smooth visual feedback
7. WHEN the Collapsed_Sidebar expands on hover, THE main content area SHALL remain in its current position without layout shift

### Requirement 6: 全ページへのヘルプモーダル追加

**User Story:** As a 新規ユーザー, I want 各ページに「?」ヘルプボタンがあること, so that 初めて使うページでも操作方法をすぐに理解できる

#### Acceptance Criteria

1. THE following pages SHALL each display a "?" help button in the page header area: ダッシュボード, 監視サイト一覧, アラート一覧, 偽サイト検知, サイト管理, クロール結果レビュー, 契約条件管理, チェックルール, 顧客マスター
2. WHEN the user clicks the "?" help button on any page, THE Help_Modal SHALL open and display that page's usage instructions
3. WHEN the user clicks the close button or presses Escape, THE Help_Modal SHALL close
4. THE "?" help button SHALL have an accessible label "ヘルプを表示" for screen readers
5. THE "?" help button SHALL use consistent styling across all pages (same size, position, and hover behavior)

#### Page-Specific Help Content

**ダッシュボード（Dashboard）:**
- ユーザーストーリー: 監視状況の全体像を把握したい
- 説明内容: 監視サイト数・違反数・成功率・偽サイト検知数の統計カード、違反数推移グラフの見方、データは30秒ごとに自動更新される

**監視サイト一覧（Sites）:**
- ユーザーストーリー: 監視対象サイトの状態を確認し、クロールを実行したい
- 説明内容: サイト名・URL検索とステータス・顧客フィルターの使い方、「今すぐクロール」ボタンでサイトの最新情報を取得、最終クロール日時をクリックするとクロール結果の詳細を確認可能、ステータス（準拠/違反/保留/エラー）の意味

**アラート一覧（Alerts）:**
- ユーザーストーリー: 検出された問題を重要度別に確認し、対応の優先順位を判断したい
- 説明内容: 重要度フィルター（緊急/高/中/低）と種別フィルター（契約違反/偽サイト）の使い方、カードの左ボーダー色が重要度を示す、偽サイトアラートにはTakeDown対応バナーが表示される、解決済みアラートは半透明で表示

**偽サイト検知（FakeSites）:**
- ユーザーストーリー: 偽サイトの検知状況を一覧で確認し、対応状況を追跡したい
- 説明内容: 偽ドメイン・正規ドメイン・類似度スコアの見方、ドメイン類似度とコンテンツ類似度の違い、ステータス（未解決/解決済み）の意味、データは30秒ごとに自動更新

**サイト管理（Site Management、旧：階層型ビュー）:**
- ユーザーストーリー: 顧客ごとのサイト構造を把握し、各サイトの詳細操作を行いたい
- 説明内容: 顧客→サイトの階層構造、サイトを展開すると詳細タブ（契約条件/スクリーンショット/検証・比較/アラート）が表示、ベースラインスクリーンショットは1サイト1枚で上書き可能、検証・比較はサイトのコンテキスト内で実行

**クロール結果レビュー（CrawlResultReview）:**
- ユーザーストーリー: クロールで取得したデータを確認・編集し、抽出精度を検証したい
- 説明内容: スクリーンショットとデータ抽出結果の並列表示、フィールドをクリックするとスクリーンショット上の該当箇所がハイライト、データの手動編集と承認/却下ワークフロー、HTML解析とOCR解析の比較

**契約条件管理（Contracts）:**
- ユーザーストーリー: サイトごとの契約条件を登録・管理し、監視の基準を設定したい
- 説明内容: サイトフィルターで特定サイトの契約を絞り込み、契約条件には価格・決済方法・手数料・サブスクリプション条件を設定、バージョン管理で契約変更の履歴を追跡、「現在」バッジが付いた契約が監視の基準として使用される

**チェックルール（Rules）:**
- ユーザーストーリー: 監視システムがどのような項目をチェックしているか確認したい
- 説明内容: カテゴリフィルターでルールを絞り込み、各ルールの重要度（高/中/低）と有効/無効の状態、ルールを展開するとチェックポイントの詳細が表示、ルールは価格・決済方法・手数料・サブスクリプション・透明性の5カテゴリ

**顧客マスター（Customers）:**
- ユーザーストーリー: 顧客情報を登録・管理し、サイトとの紐付けの基盤を整備したい
- 説明内容: 顧客名・会社名・メールアドレスで検索、ステータスフィルターで有効/無効を切り替え、新規登録・編集・削除の操作方法、顧客を無効にしても関連サイトの監視は継続される

# Implementation Plan: screenshot-integration-rename

## Overview

フロントエンドUIの再構築を段階的に実装する。共通コンポーネント（HelpButton）を先に作成し、リネーム・ルート変更 → ナビゲーション更新 → ページ統合 → サイドバーホバー → ヘルプモーダル追加の順で進める。TypeScript + React + Vitest で実装。

## Tasks

- [x] 1. HelpButton 共通コンポーネントの作成
  - [x] 1.1 `genai/frontend/src/components/ui/HelpButton/HelpButton.tsx` と `HelpButton.css` を作成
    - `HelpButtonProps` インターフェース（`title: string`, `children: ReactNode`）を定義
    - 「?」ボタンをレンダリングし、クリックで既存の `Modal` コンポーネントを開く
    - `aria-label="ヘルプを表示"` を設定
    - 閉じるボタンと Escape キーで閉じる（Modal 既存機能を利用）
    - 全ページで統一されたサイズ・位置・ホバー動作のスタイリング
    - _Requirements: 6.2, 6.3, 6.4, 6.5_

  - [x] 1.2 HelpButton のユニットテストを作成
    - `genai/frontend/src/components/ui/HelpButton/HelpButton.test.tsx` を作成
    - 「?」ボタンの表示、クリックでモーダル表示、aria-label の検証
    - _Requirements: 6.2, 6.3, 6.4_

- [x] 2. 階層型ビューからサイト管理へのリネームとルート変更
  - [x] 2.1 `HierarchyView.tsx` を `SiteManagement.tsx` にリネームし、ページタイトルを変更
    - `genai/frontend/src/pages/HierarchyView.tsx` → `genai/frontend/src/pages/SiteManagement.tsx`
    - `genai/frontend/src/pages/HierarchyView.css` → `genai/frontend/src/pages/SiteManagement.css`
    - コンポーネント名を `HierarchyView` → `SiteManagement` に変更
    - `<h1>` を「階層型ビュー」→「サイト管理」に変更
    - CSS クラス名 `.hierarchy-view` → `.site-management` に変更
    - _Requirements: 1.1_

  - [x] 2.2 `App.tsx` のルート定義を更新
    - `HierarchyView` インポートを `SiteManagement` に変更
    - `/hierarchy` ルートを `/site-management` に変更
    - `/hierarchy` → `/site-management` のリダイレクト（`<Navigate to="/site-management" replace />`）を追加
    - `/screenshots` → `/site-management` のリダイレクトを追加
    - `/verification` → `/site-management` のリダイレクトを追加
    - _Requirements: 1.3, 1.4, 2.7, 3.7, 4.5_

  - [x] 2.3 リネームとルーティングのユニットテストを作成
    - `genai/frontend/src/pages/__tests__/SiteManagement.test.tsx` を作成
    - SiteManagement ページの `<h1>` が「サイト管理」であることを検証
    - `/site-management` でページが表示されることを検証
    - `/hierarchy`, `/screenshots`, `/verification` からのリダイレクトを検証
    - _Requirements: 1.1, 1.3, 1.4, 2.7, 3.7_

- [x] 3. ナビゲーション構造の更新
  - [x] 3.1 `AppLayout.tsx` の `navigationItems` を更新
    - `{ path: '/hierarchy', label: '階層型ビュー', group: 'analysis' }` → `{ path: '/site-management', label: 'サイト管理', group: 'analysis' }` に変更
    - `{ path: '/screenshots', label: 'スクリーンショット', group: 'analysis' }` を削除
    - `{ path: '/verification', label: '検証・比較', group: 'analysis' }` を削除
    - 「分析」グループに「サイト管理」のみ残る（空グループにはならない）
    - _Requirements: 1.2, 1.5, 2.8, 3.8, 4.1, 4.2, 4.3, 4.4_

  - [x] 3.2 ナビゲーション項目のユニットテストを更新
    - `genai/frontend/src/layouts/AppLayout.test.tsx` を更新
    - 「サイト管理」が `/site-management` パスで存在することを検証
    - 「スクリーンショット」「検証・比較」が存在しないことを検証
    - 「分析」グループが空でないことを検証
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 4. Checkpoint - リネーム・ルート・ナビゲーション確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. ScreenshotTab の機能拡充
  - [x] 5.1 `genai/frontend/src/components/hierarchy/tabs/ScreenshotTab.tsx` を拡充
    - ベースラインスクリーンショット（`screenshot_type === 'baseline'`）と最新モニタリングキャプチャを分離表示
    - 再キャプチャボタン（ベースライン上書き）を追加
    - 再アップロードボタン（ベースライン上書き）を追加
    - キャプチャ/アップロードモーダルからスクリーンショットタイプセレクターを除外（キャプチャは常にモニタリング、アップロードは常にベースライン上書き）
    - 1サイトにつきベースラインは1枚のみ保持し、上書きで置換
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 5.2 ScreenshotTab のユニットテストを作成
    - ベースラインと最新キャプチャの表示を検証
    - 再キャプチャ/再アップロードボタンの存在を検証
    - タイプセレクターが非表示であることを検証
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6_

- [x] 6. VerificationTab の機能拡充
  - [x] 6.1 `genai/frontend/src/components/hierarchy/tabs/VerificationTab.tsx` を拡充
    - サイトセレクターを非表示にする（siteId は props から受け取り済み）
    - 「検証実行」ボタンを追加
    - 比較テーブル（HTML値、OCR値、ステータスインジケーター）の表示を確認・拡充
    - 差異リスト（重要度バッジ付き）の表示を確認・拡充
    - 履歴一覧の表示を確認
    - CSV エクスポートボタンを追加
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 6.2 VerificationTab のユニットテストを作成
    - 検証実行ボタンの存在を検証
    - 比較テーブル表示を検証
    - 差異リスト・重要度バッジ表示を検証
    - CSV エクスポートボタンの存在を検証
    - サイトセレクターが非表示であることを検証
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 7. Checkpoint - ページ統合確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. サイドバーのホバー展開（タブレット幅）
  - [x] 8.1 `Sidebar.tsx` に `hoverExpanded` prop を追加
    - `SidebarProps` に `hoverExpanded?: boolean` を追加
    - `hoverExpanded` が `true` の場合、`collapsed` が `true` でもラベルを表示
    - CSS クラス `sidebar--hover-expanded` を追加
    - _Requirements: 5.2, 5.3_

  - [x] 8.2 `Sidebar.css` にホバー展開スタイルを追加
    - `sidebar--collapsed.sidebar--hover-expanded` で `position: absolute` + `z-index` を設定（メインコンテンツの上に重ねてレイアウトシフトを防ぐ）
    - CSS transition を 200ms 以下に設定
    - _Requirements: 5.6, 5.7_

  - [x] 8.3 `AppLayout.tsx` にホバー状態管理を追加
    - `isHoverExpanded` state を追加
    - タブレット幅の sidebar wrapper に `onMouseEnter`/`onMouseLeave` ハンドラを設定
    - `Sidebar` コンポーネントに `hoverExpanded={isHoverExpanded}` を渡す
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 8.4 サイドバーホバーのユニットテストを作成
    - `genai/frontend/src/components/ui/Sidebar/Sidebar.test.tsx` を更新
    - `hoverExpanded` prop で `sidebar--hover-expanded` クラスが付与されることを検証
    - collapsed + hoverExpanded でラベルが表示されることを検証
    - _Requirements: 5.2, 5.3, 5.7_

- [x] 9. 全ページへのヘルプモーダル追加
  - [x] 9.1 Dashboard ページにヘルプモーダルを追加
    - `genai/frontend/src/pages/Dashboard.tsx` のヘッダーに HelpButton を配置
    - ヘルプコンテンツ: 統計カード・違反数推移グラフの見方・30秒自動更新の説明
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 9.2 FakeSites ページにヘルプモーダルを追加
    - `genai/frontend/src/pages/FakeSites.tsx` のヘッダーに HelpButton を配置
    - ヘルプコンテンツ: 偽ドメイン・類似度スコア・ステータスの説明
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 9.3 SiteManagement ページにヘルプモーダルを追加
    - `genai/frontend/src/pages/SiteManagement.tsx` のヘッダーに HelpButton を配置
    - ヘルプコンテンツ: 階層構造・詳細タブ・ベースラインスクリーンショット・検証の説明
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 9.4 CrawlResultReview ページにヘルプモーダルを追加
    - `genai/frontend/src/pages/CrawlResultReview.tsx` のヘッダーに HelpButton を配置
    - ヘルプコンテンツ: スクリーンショット並列表示・ハイライト・承認ワークフロー・HTML/OCR比較の説明
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 9.5 Contracts ページにヘルプモーダルを追加
    - `genai/frontend/src/pages/Contracts.tsx` のヘッダーに HelpButton を配置
    - ヘルプコンテンツ: サイトフィルター・契約条件設定・バージョン管理・「現在」バッジの説明
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 9.6 Rules ページにヘルプモーダルを追加
    - `genai/frontend/src/pages/Rules.tsx` のヘッダーに HelpButton を配置
    - ヘルプコンテンツ: カテゴリフィルター・重要度・有効/無効・5カテゴリの説明
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 9.7 Customers ページにヘルプモーダルを追加
    - `genai/frontend/src/pages/Customers.tsx` のヘッダーに HelpButton を配置
    - ヘルプコンテンツ: 検索・ステータスフィルター・CRUD操作・無効化時の監視継続の説明
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 9.8 Alerts ページのヘルプモーダルを HelpButton パターンに統一
    - `genai/frontend/src/pages/Alerts.tsx` の既存 `severity-help-btn` を HelpButton に置き換え
    - ヘルプコンテンツ: 重要度フィルター・種別フィルター・ボーダー色・TakeDownバナー・解決済み表示の説明
    - 既存の重要度説明モーダルの内容はヘルプモーダル内に統合
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

  - [x] 9.9 Sites ページのヘルプモーダルを HelpButton パターンに統一
    - `genai/frontend/src/pages/Sites.tsx` の既存ヘルプボタンを HelpButton に置き換え
    - ヘルプコンテンツ: 検索・フィルター・クロール実行・ステータスの説明
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

- [x] 10. Checkpoint - ヘルプモーダル確認
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. プロパティベーステスト
  - [x] 11.1 Property 1: Breakpoint classification is consistent
    - `genai/frontend/src/tests/screenshot-rename.property.test.ts` を作成
    - ランダムな正の整数幅を生成し、`classifyBreakpoint` の戻り値が正しいブレークポイントカテゴリであることを検証
    - 3つの範囲が網羅的かつ排他的であることを検証
    - **Property 1: Breakpoint classification is consistent**
    - **Validates: Requirements 5.1, 5.4, 5.5**

  - [x] 11.2 Property 2: No empty navigation groups are rendered
    - ランダムなナビゲーション項目とグループを生成し、Sidebar レンダリング後に空グループの DOM 要素が存在しないことを検証
    - **Property 2: No empty navigation groups are rendered**
    - **Validates: Requirements 4.4**

  - [x] 11.3 Property 3: Verification results display all required fields
    - ランダムな検証結果データを生成し、VerificationTab レンダリング後に HTML値・OCR値・ステータスが表示されていることを検証
    - **Property 3: Verification results display all required fields**
    - **Validates: Requirements 3.3**

  - [x] 11.4 Property 4: Discrepancies are displayed with severity badges
    - ランダムな差異データ（1件以上）を含む検証結果を生成し、各差異の重要度バッジが表示されていることを検証
    - **Property 4: Discrepancies are displayed with severity badges**
    - **Validates: Requirements 3.4**

  - [x] 11.5 Property 5: Help button presence, accessibility, and modal behavior
    - 9ページのリストからランダムにページを選択し、ヘルプボタンの存在・`aria-label="ヘルプを表示"`・モーダル表示を検証
    - **Property 5: Help button presence, accessibility, and modal behavior**
    - **Validates: Requirements 6.1, 6.2, 6.4**

  - [x] 11.6 Property 6: Baseline screenshot invariant (one per site)
    - ランダムなサイトIDとスクリーンショットデータを生成し、ベースラインが常に1枚であることを検証
    - **Property 6: Baseline screenshot invariant (one per site)**
    - **Validates: Requirements 2.5**

- [x] 12. Final checkpoint - 全テスト通過確認
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Alerts ページと Sites ページには既存のヘルプモーダルパターンがあるため、HelpButton への統一が必要
- `classifyBreakpoint` 関数は `genai/frontend/src/hooks/useMediaQuery.ts` に既に存在する
- テスト実行: `npx vitest run`（`genai/frontend` ディレクトリ）

# 要件定義書

## はじめに

本ドキュメントは、決済条件監視システムのWEB UIをFigmaデザインと連携し、継続的にUXを改善するための要件を定義する。既存のReact/TypeScriptフロントエンド（CSSベースのスタイリング）に対して、Figmaデザインからの一貫したデザイントークン適用、コンポーネントライブラリの整備、およびデザイン・コード間の同期ワークフローを確立する。

### 採用デザインシステム

**Figma SDS (Simple Design System)** を基盤として採用する。
- リポジトリ: https://github.com/figma/sds
- Figma公式のリファレンス実装（Variables、Styles、Components、Code Connect対応）
- React + CSSベースの既存構成に段階的に導入可能
- Kiro Figma Powerとの連携によりデザイン→コード変換を効率化

## 用語集

- **Design_Token_System**: Figmaで定義された色、タイポグラフィ、スペーシング、シャドウなどのデザイン値をCSS変数として管理するシステム
- **Component_Library**: Figmaデザインに基づいて構築された再利用可能なReactコンポーネント群
- **Figma_Sync_Workflow**: Figmaデザインの変更をフロントエンドコードに反映するための手順とツール群
- **Design_Spec**: Figmaから出力されるコンポーネントの仕様情報（サイズ、色、間隔、フォントなど）
- **UI_Page**: Dashboard、Alerts、FakeSites、CrawlResultReview等の既存ページ
- **Navigation_System**: アプリケーション全体のナビゲーションバーおよびルーティング構造
- **Responsive_Layout**: 画面サイズに応じてレイアウトが適応する仕組み

## 要件

### 要件1: デザイントークンの一元管理

**ユーザーストーリー:** 開発者として、Figmaで定義されたデザイントークンをCSS変数として一元管理したい。これにより、デザイン変更時にトークンファイルの更新だけで全画面に反映できるようにする。

#### 受け入れ基準

1. THE Design_Token_System SHALL Figmaで定義された色、タイポグラフィ、スペーシング、ボーダー半径、シャドウの値をCSS変数ファイルとして管理する
2. WHEN Figmaでデザイントークンが更新された場合、THE Design_Token_System SHALL 対応するCSS変数ファイルを更新することで全ページに変更を反映する
3. THE Design_Token_System SHALL セマンティックトークン（例: `--color-primary`, `--spacing-md`, `--font-size-body`）とプリミティブトークン（例: `--blue-600`, `--space-16`）を分離して定義する
4. THE Design_Token_System SHALL 既存の`App.css`の`:root`変数を新しいトークン体系に移行する
5. IF デザイントークンに未定義の値がコード内で使用されている場合、THEN THE Design_Token_System SHALL リントルールまたはレビューチェックリストで検出可能にする

### 要件2: 共通UIコンポーネントライブラリの構築

**ユーザーストーリー:** 開発者として、Figmaデザインに基づいた共通UIコンポーネントライブラリを使いたい。これにより、画面間でデザインの一貫性を保ちながら効率的に開発できるようにする。

#### 受け入れ基準

1. THE Component_Library SHALL Figmaのコンポーネント定義に基づいて、Button、Badge、Card、Table、Modal、Form要素の共通コンポーネントを提供する
2. THE Component_Library SHALL 各コンポーネントにデザイントークンのCSS変数を使用してスタイリングする
3. WHEN 新しいコンポーネントがFigmaで定義された場合、THE Component_Library SHALL 対応するReactコンポーネントとCSSファイルを追加する手順を文書化する
4. THE Component_Library SHALL 各コンポーネントにアクセシビリティ属性（aria-label、role、キーボード操作対応）を含める
5. THE Component_Library SHALL 各コンポーネントのpropsインターフェースをTypeScriptの型定義で提供する
6. IF コンポーネントがFigmaのDesign_Specと視覚的に乖離している場合、THEN THE Component_Library SHALL Storybookまたは同等のツールで視覚的に比較検証できる仕組みを提供する

### 要件3: 既存ページのデザインリファクタリング

**ユーザーストーリー:** ユーザーとして、全ページで統一されたデザインを体験したい。これにより、操作の学習コストが下がり、効率的にシステムを利用できるようにする。

#### 受け入れ基準

1. THE UI_Page SHALL Dashboard、Alerts、FakeSites、CrawlResultReview、Sites、Screenshots、Verification、HierarchyViewの各ページでComponent_Libraryの共通コンポーネントを使用する
2. THE UI_Page SHALL 各ページのインラインスタイルおよびページ固有のCSS定義をデザイントークンベースのスタイルに置き換える
3. WHEN ページのリファクタリングが完了した場合、THE UI_Page SHALL 既存の機能テストが全て通過する状態を維持する
4. THE UI_Page SHALL 各ページのレイアウト構造（ヘッダー、フィルター、コンテンツ、フッター）をFigmaのレイアウトガイドラインに準拠させる

### 要件4: ナビゲーションとレイアウトの改善

**ユーザーストーリー:** ユーザーとして、直感的なナビゲーションで目的のページに素早くアクセスしたい。これにより、監視業務の効率が向上する。

#### 受け入れ基準

1. THE Navigation_System SHALL Figmaで定義されたナビゲーションデザイン（サイドバーまたはトップバー）に基づいてナビゲーション構造を実装する
2. THE Navigation_System SHALL 現在のアクティブページをナビゲーション上で視覚的に示す
3. THE Navigation_System SHALL 10個の既存ナビゲーション項目を論理的なグループ（監視、分析、設定など）に分類して表示する
4. WHILE 画面幅が768px以下の場合、THE Navigation_System SHALL モバイル対応のナビゲーション（ハンバーガーメニューまたはドロワー）を表示する
5. THE Navigation_System SHALL キーボードナビゲーション（Tab、Enter、Escape）に対応する

### 要件5: レスポンシブデザインの強化

**ユーザーストーリー:** ユーザーとして、タブレットやモバイルデバイスでも快適にシステムを利用したい。これにより、外出先でもアラートの確認や対応ができるようにする。

#### 受け入れ基準

1. THE Responsive_Layout SHALL Figmaで定義されたブレークポイント（モバイル、タブレット、デスクトップ）に基づいてレイアウトを切り替える
2. THE Responsive_Layout SHALL stats-grid、sites-table、alerts-list、screenshots-gridの各レイアウトをブレークポイントごとに最適化する
3. THE Responsive_Layout SHALL タッチデバイスでのタップターゲットサイズを44px以上に確保する
4. WHEN 画面幅が変更された場合、THE Responsive_Layout SHALL レイアウトの切り替えを滑らかに行う（リフローによるちらつきを防止する）
5. THE Responsive_Layout SHALL テーブルコンポーネントをモバイル表示時にカード形式またはスクロール可能な形式に変換する

### 要件6: Figma連携ワークフローの確立

**ユーザーストーリー:** 開発チームとして、Figmaデザインの変更をコードに反映する標準的なワークフローを持ちたい。これにより、デザインとコードの乖離を防ぎ、継続的にUXを改善できるようにする。

#### 受け入れ基準

1. THE Figma_Sync_Workflow SHALL Figmaファイルからデザイントークンを抽出してCSS変数ファイルに変換する手順を文書化する
2. THE Figma_Sync_Workflow SHALL Kiro Figma Powerを活用してFigmaデザインからコンポーネント仕様を取得する手順を定義する
3. THE Figma_Sync_Workflow SHALL デザイン変更時のコード反映手順（トークン更新→コンポーネント更新→ページ更新→テスト）を定義する
4. THE Figma_Sync_Workflow SHALL Figmaコンポーネントとコードコンポーネントの対応表（マッピングドキュメント）を維持する
5. IF Figmaデザインとコード実装の間に視覚的な差異が検出された場合、THEN THE Figma_Sync_Workflow SHALL 差異を記録し修正タスクとして管理する

### 要件7: ダークモード対応

**ユーザーストーリー:** ユーザーとして、長時間の監視業務で目の疲れを軽減するためにダークモードを利用したい。

#### 受け入れ基準

1. WHERE ダークモードが有効な場合、THE Design_Token_System SHALL ダークモード用のセマンティックトークン値に切り替える
2. THE Design_Token_System SHALL `prefers-color-scheme`メディアクエリによるシステム設定の自動検出に対応する
3. THE UI_Page SHALL ユーザーがライトモード・ダークモードを手動で切り替えるトグルUIを提供する
4. WHEN モードが切り替えられた場合、THE UI_Page SHALL ユーザーの選択をlocalStorageに保存し、次回アクセス時に復元する
5. THE Design_Token_System SHALL ダークモード時にコントラスト比がWCAG 2.1 AAレベル（4.5:1以上）を満たすトークン値を定義する

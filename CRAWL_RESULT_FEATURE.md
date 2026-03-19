# クロール結果表示機能

## 概要
クロール完了後に結果を表示するモーダル機能を実装しました。

## 実装内容

### 1. 新規コンポーネント

#### CrawlResultModal.tsx
- クロール結果を表示するモーダルコンポーネント
- 機能:
  - クロールステータスの表示（成功/失敗/エラー）
  - 違反情報の詳細表示
  - 重要度別の色分け表示（低/中/高/重大）
  - アラート送信状態の表示
  - エラーメッセージの表示

#### CrawlResultModal.css
- モーダルのスタイル定義
- レスポンシブデザイン対応
- アニメーション効果（スピナー）

### 2. 既存コンポーネントの更新

#### SiteRow.tsx
- `CrawlResultModal`のインポートと統合
- 状態管理の追加:
  - `showResultModal`: モーダルの表示/非表示
  - `currentJobId`: 現在のクロールジョブID
- クロール完了時の自動モーダル表示
- 「結果を表示」ボタンの追加
- ボタンクリックでモーダルを開く機能

#### App.css
- `.crawl-result-button`スタイルの追加
- ホバー/アクティブ状態のスタイル

### 3. テスト

#### CrawlResultModal.test.tsx
- 10個のテストケース:
  1. ローディング状態の表示
  2. フェッチ失敗時のエラー表示
  3. クロール失敗時のエラー表示
  4. 違反なし時の成功メッセージ
  5. 違反検出時の詳細表示
  6. エラーメッセージの表示
  7. ×ボタンでモーダルを閉じる
  8. 閉じるボタンでモーダルを閉じる
  9. オーバーレイクリックでモーダルを閉じる
  10. 重要度バッジの正しい表示

### 4. テストHTML

#### test_crawl_result_modal.html
- 手動テスト用のHTMLファイル
- 機能:
  - サイト一覧の取得
  - クロールの実行
  - クロール結果の確認
  - リアルタイムステータスポーリング

## 使用方法

### ユーザー操作フロー

1. **階層ビューでサイトを表示**
   - サイト一覧が表示される

2. **クロールを実行**
   - 「今すぐクロール」ボタンをクリック
   - クロールが開始され、ステータスが「クロール中...」に変わる

3. **クロール完了**
   - クロールが完了すると自動的に結果モーダルが表示される
   - 「結果を表示」ボタンが表示される

4. **結果の確認**
   - モーダルで以下の情報を確認:
     - URL
     - ステータス（成功/失敗/エラー）
     - 検出された違反（あれば）
     - 各違反の詳細（タイプ、重要度、フィールド、メッセージ）
     - アラート送信状態

5. **モーダルを閉じる**
   - ×ボタン、閉じるボタン、またはオーバーレイをクリック

### API連携

```typescript
// クロール結果の取得
const statusResponse = await getCrawlStatus(jobId);

// レスポンス構造
{
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result?: {
    site_id: number;
    url: string;
    status: 'success' | 'crawl_failed' | 'error';
    violations: Array<{
      type: string;
      severity: 'low' | 'medium' | 'high' | 'critical';
      field: string;
      message: string;
    }>;
    alerts_sent: boolean;
    error: string | null;
  };
}
```

## 技術詳細

### 状態管理
- React Hooksを使用（useState, useEffect）
- ローカル状態でモーダルの表示/非表示を管理
- ジョブIDを保持して結果取得に使用

### スタイリング
- CSS Modulesではなく通常のCSSファイルを使用
- BEM命名規則に準拠
- レスポンシブデザイン（モバイル対応）
- アクセシビリティ考慮（キーボード操作、ARIA属性）

### エラーハンドリング
- ネットワークエラー
- APIエラー
- クロール失敗
- タイムアウト

## テスト結果

```
✓ src/components/hierarchy/CrawlResultModal.test.tsx (10 tests) 178ms
✓ All frontend tests: 157 passed (157)
```

## 今後の改善案

1. **履歴表示**
   - 過去のクロール結果を一覧表示
   - 結果の比較機能

2. **詳細フィルタリング**
   - 重要度別フィルター
   - 違反タイプ別フィルター

3. **エクスポート機能**
   - PDF/CSV形式でのエクスポート
   - レポート生成

4. **通知機能**
   - ブラウザ通知
   - メール通知の設定

5. **グラフ表示**
   - 違反の推移グラフ
   - 重要度別の円グラフ

## ファイル一覧

### 新規作成
- `genai/frontend/src/components/hierarchy/CrawlResultModal.tsx`
- `genai/frontend/src/components/hierarchy/CrawlResultModal.css`
- `genai/frontend/src/components/hierarchy/CrawlResultModal.test.tsx`
- `genai/test_crawl_result_modal.html`

### 更新
- `genai/frontend/src/components/hierarchy/SiteRow.tsx`
- `genai/frontend/src/App.css`

## 関連ドキュメント
- [階層型UI実装仕様](.kiro/specs/hierarchical-ui-restructure/design.md)
- [タスク一覧](.kiro/specs/hierarchical-ui-restructure/tasks.md)

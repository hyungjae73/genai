# 決済条件監視システム - フロントエンド

React + TypeScript + Vite で構築された決済条件監視システムのダッシュボードです。

## 機能

- **ダッシュボード**: 監視サイト数、違反数、成功率などの統計情報を表示
- **監視サイト一覧**: 監視対象サイトの一覧とコンプライアンスステータスを表示
- **アラート一覧**: 検出された違反のアラートを重要度別に表示
- **自動リフレッシュ**: 30秒ごとにデータを自動更新

## セットアップ

### 前提条件

- Node.js 18以上
- npm または yarn

### インストール

```bash
npm install
```

### 環境変数

`.env` ファイルを作成し、以下の環境変数を設定してください：

```
VITE_API_BASE_URL=http://localhost:8000
```

### 開発サーバーの起動

```bash
npm run dev
```

ブラウザで `http://localhost:5173` を開いてください。

### ビルド

```bash
npm run build
```

ビルドされたファイルは `dist/` ディレクトリに出力されます。

### プレビュー

```bash
npm run preview
```

## 技術スタック

- **React 18**: UIライブラリ
- **TypeScript**: 型安全な開発
- **Vite**: 高速なビルドツール
- **React Router**: ルーティング
- **Axios**: HTTP通信
- **Chart.js**: グラフ表示
- **React Chart.js 2**: Chart.jsのReactラッパー

## プロジェクト構造

```
frontend/
├── src/
│   ├── pages/          # ページコンポーネント
│   │   ├── Dashboard.tsx
│   │   ├── Sites.tsx
│   │   └── Alerts.tsx
│   ├── services/       # API通信
│   │   └── api.ts
│   ├── hooks/          # カスタムフック
│   │   └── useAutoRefresh.ts
│   ├── App.tsx         # メインアプリケーション
│   ├── App.css         # スタイル
│   └── main.tsx        # エントリーポイント
├── public/
└── package.json
```

## API エンドポイント

バックエンドAPIは以下のエンドポイントを提供します：

- `GET /sites` - 監視サイト一覧
- `GET /alerts` - アラート一覧
- `GET /monitoring-history` - 監視履歴
- `GET /monitoring-history/statistics` - 統計情報

## 開発

### コードスタイル

- ESLintを使用してコード品質を維持
- TypeScriptの型チェックを活用

### 自動リフレッシュ

各ページは `useAutoRefresh` カスタムフックを使用して、30秒ごとにデータを自動更新します。

## ライセンス

MIT

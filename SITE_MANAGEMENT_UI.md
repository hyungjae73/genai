# サイト管理UI - 実装完了

監視対象URLの登録、編集、削除機能を実装しました。

## 実装内容

### フロントエンド機能

1. **サイト一覧表示**
   - サイト名、URL、ステータス、最終クロール日時、監視状態を表示
   - 検索機能（サイト名・URLで検索）
   - ステータスフィルター（準拠/違反/保留中/エラー）

2. **新規サイト登録**
   - サイト名入力
   - URL入力（バリデーション付き）
   - 監視有効/無効の切り替え
   - モーダルダイアログで入力

3. **サイト編集**
   - 既存サイトの情報を編集
   - サイト名、URL、監視状態を変更可能
   - モーダルダイアログで編集

4. **サイト削除**
   - 確認ダイアログ付き削除機能
   - データベースから完全削除

### バックエンドAPI

すべてのAPIエンドポイントがデータベースと連携：

- `POST /api/sites/` - サイト新規登録
- `GET /api/sites/` - サイト一覧取得
- `GET /api/sites/{id}` - 特定サイト取得
- `PUT /api/sites/{id}` - サイト更新
- `DELETE /api/sites/{id}` - サイト削除

### UI/UXの特徴

- **レスポンシブデザイン**: モバイル対応
- **リアルタイム更新**: 30秒ごとに自動更新
- **バリデーション**: URL形式チェック、必須項目チェック
- **エラーハンドリング**: わかりやすいエラーメッセージ
- **確認ダイアログ**: 削除時の誤操作防止
- **ローディング状態**: 処理中の視覚的フィードバック

## アクセス方法

### フロントエンド
- URL: http://localhost:5174/
- サイト管理ページ: http://localhost:5174/ (ナビゲーションから「サイト」を選択)

### API
- Swagger UI: http://localhost:8080/docs
- API Base URL: http://localhost:8080/api/sites/

## 使い方

### 1. 新規サイト登録

1. サイト管理ページを開く
2. 「+ 新規サイト登録」ボタンをクリック
3. モーダルが開くので以下を入力：
   - サイト名: 例「Example Payment Site」
   - URL: 例「https://example.com」
   - 監視を有効にする: チェックボックスで選択
4. 「登録」ボタンをクリック

### 2. サイト編集

1. サイト一覧から編集したいサイトの「編集」ボタンをクリック
2. モーダルが開くので情報を変更
3. 「更新」ボタンをクリック

### 3. サイト削除

1. サイト一覧から削除したいサイトの「削除」ボタンをクリック
2. 確認ダイアログで「OK」をクリック

### 4. サイト検索

- 検索ボックスにサイト名またはURLを入力
- リアルタイムで絞り込み表示

### 5. ステータスフィルター

- ドロップダウンからステータスを選択
- 選択したステータスのサイトのみ表示

## APIの使用例

### cURLでサイト登録

```bash
curl -X POST "http://localhost:8080/api/sites/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example Payment Site",
    "url": "https://example.com",
    "monitoring_enabled": true
  }'
```

### cURLでサイト一覧取得

```bash
curl "http://localhost:8080/api/sites/"
```

### cURLでサイト更新

```bash
curl -X PUT "http://localhost:8080/api/sites/1" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Site Name",
    "monitoring_enabled": false
  }'
```

### cURLでサイト削除

```bash
curl -X DELETE "http://localhost:8080/api/sites/1"
```

## データベーススキーマ

サイト情報は `monitoring_sites` テーブルに保存されます：

```sql
CREATE TABLE monitoring_sites (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_crawled_at TIMESTAMP,
    compliance_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 実装ファイル

### フロントエンド
- `frontend/src/pages/Sites.tsx` - サイト管理UIコンポーネント
- `frontend/src/services/api.ts` - API通信関数
- `frontend/src/App.css` - スタイル定義

### バックエンド
- `src/api/sites.py` - サイト管理APIエンドポイント
- `src/api/schemas.py` - Pydanticスキーマ定義
- `src/models.py` - SQLAlchemyモデル定義

## 今後の拡張可能性

1. **一括操作**
   - 複数サイトの一括登録
   - 複数サイトの一括削除
   - CSVインポート/エクスポート

2. **高度な検索**
   - 正規表現検索
   - 複数条件での絞り込み
   - 保存された検索条件

3. **ソート機能**
   - 各カラムでのソート
   - 複数カラムでのソート

4. **ページネーション**
   - 大量データ対応
   - ページサイズ変更

5. **詳細表示**
   - サイト詳細ページ
   - クロール履歴表示
   - 違反履歴表示

6. **通知設定**
   - サイトごとの通知設定
   - アラート条件のカスタマイズ

## トラブルシューティング

### サイトが表示されない

```bash
# APIが起動しているか確認
curl http://localhost:8080/health

# データベース接続を確認
psql -U payment_monitor -d payment_monitor -c "SELECT * FROM monitoring_sites;"
```

### 登録/更新/削除が失敗する

1. ブラウザのコンソールでエラーを確認
2. APIログを確認: `tail -f genai/logs/api.log`
3. データベースの状態を確認

### CORSエラーが発生する

`.env` ファイルの `CORS_ORIGINS` を確認：
```
CORS_ORIGINS=http://localhost:5174,http://localhost:5173,http://localhost:3000
```

## まとめ

監視対象URLの完全なCRUD機能が実装され、直感的なUIで操作できるようになりました。データベースと完全に連携しており、本番環境でも使用可能です。

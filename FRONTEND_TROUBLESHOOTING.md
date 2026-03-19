# フロントエンド表示問題 - トラブルシューティングガイド

## 現在の状況

### 稼働中のサービス
- ✅ API: http://localhost:8080 (正常稼働)
- ✅ Frontend: http://localhost:5173 (正常稼働)
- ✅ PostgreSQL: localhost:5432
- ✅ Redis: localhost:6379

### 確認済み項目
1. ✅ HTMLが正しく返される
2. ✅ JavaScriptが正しくトランスパイルされる
3. ✅ APIエンドポイントが正常に応答
4. ✅ CORS設定が正しい
5. ✅ 環境変数が正しく設定されている

## ブラウザでの確認手順

### 1. 基本的な接続テスト

**テストページにアクセス:**
```
http://localhost:5173/test.html
```

このページで「✅ API接続成功!」と表示されれば、API接続は正常です。

### 2. メインアプリケーションにアクセス

**メインページ:**
```
http://localhost:5173/
```

### 3. ブラウザのデベロッパーツールで確認

#### Chromeの場合:
1. `F12` または `Cmd+Option+I` (Mac) でデベロッパーツールを開く
2. **Console** タブを確認
   - エラーメッセージがないか確認
   - 赤いエラーがあればコピーして報告

3. **Network** タブを確認
   - ページをリロード (`Cmd+R` または `F5`)
   - 失敗しているリクエストがないか確認
   - 赤い行があればクリックして詳細を確認

4. **Elements** タブを確認
   - `<div id="root"></div>` の中身が空かどうか確認
   - 空の場合、Reactアプリが起動していない

### 4. よくある問題と解決策

#### 問題1: 白い画面が表示される

**原因**: JavaScriptエラーでReactアプリが起動していない

**確認方法**:
```
ブラウザのConsoleタブでエラーを確認
```

**解決策**:
- エラーメッセージを確認
- 依存関係の問題の場合: `npm install` を再実行

#### 問題2: "Failed to fetch" エラー

**原因**: APIサーバーに接続できない

**確認方法**:
```bash
curl http://localhost:8080/health
```

**解決策**:
```bash
# APIサーバーを再起動
cd genai
pkill -f "uvicorn"
./start_api.sh > logs/api.log 2>&1 &
```

#### 問題3: CORS エラー

**エラーメッセージ例**:
```
Access to fetch at 'http://localhost:8080/api/sites/' from origin 'http://localhost:5173' has been blocked by CORS policy
```

**解決策**:
1. `.env` ファイルの `CORS_ORIGINS` を確認
2. APIサーバーを再起動

#### 問題4: モジュールが見つからない

**エラーメッセージ例**:
```
Failed to resolve module specifier "react-router-dom"
```

**解決策**:
```bash
cd genai/frontend
npm install
```

## 手動での確認コマンド

### APIエンドポイントテスト

```bash
# ヘルスチェック
curl http://localhost:8080/health

# サイト一覧
curl http://localhost:8080/api/sites/

# 統計情報
curl http://localhost:8080/api/monitoring/statistics

# アラート一覧
curl http://localhost:8080/api/alerts/
```

### フロントエンドテスト

```bash
# HTMLが返されるか確認
curl -I http://localhost:5173/

# JavaScriptが返されるか確認
curl -s http://localhost:5173/src/main.tsx | head -20
```

### プロセス確認

```bash
# Viteプロセス確認
ps aux | grep vite | grep -v grep

# APIプロセス確認
ps aux | grep uvicorn | grep -v grep
```

## デバッグ用のログ確認

```bash
cd genai

# APIログ
tail -f logs/api.log

# フロントエンドログ
tail -f logs/frontend.log

# Celery Workerログ
tail -f logs/celery_worker.log
```

## 完全リセット手順

すべてがうまくいかない場合、以下の手順で完全リセット:

```bash
cd genai

# 1. すべてのサービスを停止
./stop_all.sh

# 2. すべてのポートをクリーンアップ
lsof -ti:5173,8080 | xargs kill -9 2>/dev/null || true

# 3. フロントエンドの依存関係を再インストール
cd frontend
rm -rf node_modules
npm install
cd ..

# 4. すべてのサービスを再起動
./start_all.sh

# 5. 5秒待ってから確認
sleep 5
curl http://localhost:8080/health
curl -I http://localhost:5173/
```

## 期待される動作

### 正常な場合の表示

1. **ダッシュボード** (http://localhost:5173/)
   - ナビゲーションバー: 「決済条件監視システム」
   - メニュー: ダッシュボード、監視サイト、アラート
   - 統計カード: サイト数、違反数など
   - グラフ: 監視履歴

2. **監視サイト** (http://localhost:5173/sites)
   - 「+ 新規サイト登録」ボタン
   - サイト一覧テーブル
   - 検索・フィルター機能

3. **アラート** (http://localhost:5173/alerts)
   - アラート一覧
   - 重要度別フィルター

## 報告すべき情報

問題が解決しない場合、以下の情報を報告してください:

1. **ブラウザのConsoleエラー**
   ```
   F12 → Console タブ → エラーメッセージをコピー
   ```

2. **Networkタブの失敗リクエスト**
   ```
   F12 → Network タブ → 赤い行をクリック → Response タブの内容
   ```

3. **ログファイルの内容**
   ```bash
   tail -50 genai/logs/api.log
   tail -50 genai/logs/frontend.log
   ```

4. **プロセスの状態**
   ```bash
   ps aux | grep -E "(vite|uvicorn)" | grep -v grep
   ```

5. **ポートの使用状況**
   ```bash
   lsof -i:5173
   lsof -i:8080
   ```

## 次のステップ

1. まず http://localhost:5173/test.html でAPI接続をテスト
2. 次に http://localhost:5173/ でメインアプリを確認
3. ブラウザのConsoleでエラーを確認
4. エラーがあれば上記の解決策を試す

---

**作成日**: 2026-03-07  
**最終更新**: 2026-03-07 03:05 JST

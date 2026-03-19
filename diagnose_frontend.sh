#!/bin/bash
# フロントエンド診断スクリプト

echo "=========================================="
echo "フロントエンド診断"
echo "=========================================="
echo ""

echo "1. Viteプロセス確認..."
if ps aux | grep -v grep | grep vite > /dev/null; then
    echo "✅ Viteプロセスが実行中"
    ps aux | grep -v grep | grep vite | head -1
else
    echo "❌ Viteプロセスが見つかりません"
fi
echo ""

echo "2. ポート5173の確認..."
if lsof -i:5173 > /dev/null 2>&1; then
    echo "✅ ポート5173が使用中"
    lsof -i:5173
else
    echo "❌ ポート5173が使用されていません"
fi
echo ""

echo "3. HTTP接続テスト..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5173/)
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ HTTP接続成功 (ステータス: $HTTP_CODE)"
else
    echo "❌ HTTP接続失敗 (ステータス: $HTTP_CODE)"
fi
echo ""

echo "4. HTMLコンテンツ確認..."
if curl -s http://localhost:5173/ | grep -q "root"; then
    echo "✅ HTMLに<div id=\"root\">が含まれています"
else
    echo "❌ HTMLに<div id=\"root\">が見つかりません"
fi
echo ""

echo "5. JavaScriptファイル確認..."
if curl -s http://localhost:5173/src/main.tsx | grep -q "createRoot"; then
    echo "✅ main.tsxが正しく読み込まれています"
else
    echo "❌ main.tsxの読み込みに問題があります"
fi
echo ""

echo "6. API接続テスト..."
API_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health)
if [ "$API_CODE" = "200" ]; then
    echo "✅ API接続成功 (ステータス: $API_CODE)"
else
    echo "❌ API接続失敗 (ステータス: $API_CODE)"
fi
echo ""

echo "7. 依存関係確認..."
if [ -d "frontend/node_modules" ]; then
    echo "✅ node_modulesが存在します"
    echo "   パッケージ数: $(ls frontend/node_modules | wc -l)"
else
    echo "❌ node_modulesが見つかりません"
fi
echo ""

echo "=========================================="
echo "診断完了"
echo "=========================================="
echo ""
echo "次のステップ:"
echo "1. ブラウザで http://localhost:5173/ を開く"
echo "2. F12キーでデベロッパーツールを開く"
echo "3. Consoleタブでエラーを確認"
echo ""
echo "エラーがある場合は、エラーメッセージを報告してください"

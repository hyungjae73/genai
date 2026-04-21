# 実装計画: クロールモーダル自動化 (crawl-modal-automation)

## 概要

クロール時のモーダル・オーバーレイ問題を3層アプローチで解決する。
(1) Accept-Language ヘッダー + ロケール設定、(2) 汎用モーダル自動閉じ、(3) サイト固有プレキャプチャスクリプト。

**注記**: 本 spec の全要件は crawl-pipeline-architecture spec の実装時に既に実装済み。
本 tasks.md はその記録として作成する。

## タスク

- [x] 1. LocalePlugin の実装
  - `genai/src/pipeline/plugins/locale_plugin.py` を作成
  - ブラウザコンテキストに `locale="ja-JP"`, `Accept-Language: ja-JP,ja;q=0.9` を設定
  - ビューポート 1920x1080、デバイススケールファクター 2 を維持
  - PageFetcher ステージに統合
  - _要件: 1.1, 1.2, 1.3, 1.4_

- [x] 2. ModalDismissPlugin の実装
  - `genai/src/pipeline/plugins/modal_dismiss_plugin.py` を作成
  - MODAL_SELECTORS（`[role="dialog"]`, `.modal`, `[class*="cookie"]` 等）でモーダル検出
  - CLOSE_BUTTON_SELECTORS でボタンクリック → Escape キーフォールバック
  - 閉じ処理後 500ms 待機
  - エラー時は ctx.errors に記録してパイプライン継続
  - _要件: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 3. PreCaptureScriptPlugin の実装
  - `genai/src/pipeline/plugins/pre_capture_script_plugin.py` を作成
  - `parse_script()` / `serialize_script()` 純粋関数を実装
  - click / wait / select / type アクション型をサポート
  - label 付きアクション実行後にスクリーンショットを VariantCapture として保存
  - エラー時は残りアクションをスキップしてパイプライン継続
  - _要件: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.1-4.8_

- [x] 4. PageFetcher への統合と実行順序制御
  - `genai/src/pipeline/page_fetcher.py` に LocalePlugin → PreCaptureScriptPlugin → ModalDismissPlugin の順で統合
  - 実行順序: ロケール設定 → goto → DOM安定化 → PreCaptureScript → ModalDismiss → スクリーンショット
  - _要件: 5.1, 5.2, 5.3_

- [x] 5. MonitoringSite モデルと Alembic マイグレーション
  - `genai/src/models.py` に `pre_capture_script` カラム（JSONB, nullable）を追加
  - crawl-pipeline-architecture spec の Alembic マイグレーション（j5k6l7m8n9o0）に含まれて適用済み
  - _要件: 3.1, 8.1, 8.2, 8.3_

- [x] 6. API スキーマ拡張
  - `genai/src/api/schemas.py` の `MonitoringSiteUpdate` に `pre_capture_script` フィールドを追加
  - `genai/src/api/sites.py` と `genai/src/api/schedules.py` で JSON バリデーション実装
  - _要件: 6.1, 6.2, 6.3, 6.4_

- [x] 7. フロントエンド: ScheduleTab に PreCaptureScript エディタを追加
  - `genai/frontend/src/components/hierarchy/tabs/ScheduleTab.tsx` に textarea フィールドを追加
  - JSON バリデーション（不正形式時はエラー表示・送信阻止）
  - 空値時は null として送信
  - プレースホルダーにJSON形式の例を表示
  - _要件: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 8. 後方互換性の確認
  - pre_capture_script 未設定サイトは従来通り動作することを確認
  - モーダルなしサイトは追加遅延なしでスクリーンショット撮影
  - `capture_screenshot()` メソッドのインターフェース変更なし
  - _要件: 9.1, 9.2, 9.3_

## 備考

- 全タスクは crawl-pipeline-architecture spec の実装時に完了済み
- StealthBrowserFactory にも `locale="ja-JP"` が設定済み（stealth-browser-hardening spec）
- フロントエンドのテストは `ScheduleTab.test.tsx` に実装済み

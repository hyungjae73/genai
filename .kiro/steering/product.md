---
inclusion: auto
---

# Product Constitution (プロダクト憲法)

本ドキュメントは、決済条件監視システムの開発における不可侵の原則を定義する。
全ての新規実装・既存コード変更・spec作成時にこれらの原則を遵守すること。

## 1. 非同期タスクのUX原則 (Asynchronous UX)

- バックエンドの `crawl`, `extract`, `validate`, `report` タスクは数秒〜数分かかる前提とする。
- **絶対命令:** フロントエンド（React）でこれらの処理を呼び出す際、ユーザーを単なるローディングスピナーで待たせ続けてはならない。
- バックエンドは即座に `task_id` を返し、フロントエンドはポーリング（またはSSE/WebSocket）によって進捗を取得し、段階的なUIフィードバックを提供する設計とせよ。

### 実装ガイドライン

- バックエンドAPI: 長時間処理は `202 Accepted` + `task_id` を即座に返却
- フロントエンド: `task_id` を受け取ったら、ポーリング（`/api/tasks/{task_id}/status`）で進捗を取得
- UI表示: ステージ別の進捗バー（PageFetcher → DataExtractor → Validator → Reporter）を表示
- 完了通知: タスク完了時にトースト通知で結果を表示

## 2. 証拠保全とトレーサビリティ (Evidence First)

- スクレイピング（Playwright）やOCR処理が失敗した際のリトライ調査のため、生HTMLとスクリーンショットは必ずMinIOに保存せよ。
- フロントエンドでは `react-zoom-pan-pinch` を用い、ユーザーが取得された証拠画像を詳細に確認（拡大・縮小）できるビューアを必ず実装せよ。

### 実装ガイドライン

- ObjectStoragePlugin: 全スクリーンショット・ROI画像・生HTMLをMinIOに保存
- パス形式: `{bucket}/{site_id}/{date}/{filename}` を厳守
- フォールバック: MinIO接続失敗時はローカルファイルシステムに保存（データ消失を防止）
- フロントエンド: 証拠画像は `react-zoom-pan-pinch` の `TransformWrapper` / `TransformComponent` でラップ
- EvidenceRecord: 全証拠に `verification_result_id`, `evidence_type`, `ocr_confidence` を必ず記録

## 3. グローバルエラーハンドリング

- Axiosのエラーレスポンス、またはバックエンドのHTTP 500エラー発生時、ユーザーの画面をクラッシュさせてはならない。
- ReactのError Boundaryで適切に捕捉し、システム起因のエラーか、ユーザー入力起因かを明確に分けて通知せよ。

### 実装ガイドライン

- Axiosインターセプター: 全APIレスポンスを共通ハンドラで処理
  - 4xx: ユーザー入力起因 → フォームバリデーションエラーとして表示
  - 5xx: システム起因 → トースト通知 + エラーコード表示（`error_codes.py` 参照）
  - ネットワークエラー: 接続失敗メッセージ + リトライボタン
- Error Boundary: アプリケーションルートとページ単位の2層で設置
  - ルートレベル: 致命的エラーのフォールバックUI
  - ページレベル: 個別ページのクラッシュを他ページに波及させない
- バックエンド: 全例外を `ctx.errors` に記録し、パイプラインを中断しない（CrawlPipeline のエラー隔離原則）

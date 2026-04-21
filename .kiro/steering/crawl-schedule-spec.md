---
inclusion: manual
---

# クロールスケジュール詳細仕様

最終更新: 2026-03-22

## 概要

Celery Beatによる定期タスクスケジュール。設定は `genai/src/celery_app.py` にハードコードされている。

## 定期タスク一覧

| タスク名 | Celeryタスク | スケジュール | 説明 |
|---|---|---|---|
| daily-crawling | `src.tasks.crawl_all_sites` | 毎日 AM2:00 (UTC) | 全アクティブサイトを一括クロール |
| weekly-fake-site-scan | `src.tasks.scan_all_fake_sites` | 毎週月曜 AM3:00 (UTC) | 偽サイトスキャン |
| monthly-cleanup | `src.tasks.cleanup_old_data` | 毎月1日 AM4:00 (UTC) | 古いデータのクリーンアップ（デフォルト365日保持） |

## daily-crawling の動作

1. `crawl_all_sites` が `MonitoringSite.is_active == True` のサイトを全件取得
2. 各サイトに対して `crawl_site` タスクを非同期でエンキュー
3. 結果: `total_sites`, `successful`, `failed` を集計して返却

## 現行の制約・課題

- クロール頻度は `celery_app.py` に `crontab(hour=2, minute=0)` でハードコード
- 全サイト一律で1日1回、AM2:00に実行
- サイト個別の頻度設定機能なし
- UI上から頻度を変更する手段なし（コード変更＋デプロイが必要）
- タイムゾーンはUTC固定

## ダッシュボード「最終クロール」について

- `MAX(crawl_results.crawled_at)` で全サイト中の最新クロール日時を表示
- 目的: システム全体の稼働状況確認（Celeryスケジューラーが正常に動作しているかの指標）
- 複数サイトがある場合、どのサイトのクロールかは区別しない

## 関連ファイル

- `genai/src/celery_app.py` - Celery Beat スケジュール設定
- `genai/src/tasks.py` - タスク実装（`crawl_all_sites`, `crawl_site`）
- `genai/src/api/monitoring.py` - `/statistics` エンドポイント（最終クロール日時取得）
- `genai/src/models.py` - `MonitoringSite.is_active`, `CrawlResult.crawled_at`

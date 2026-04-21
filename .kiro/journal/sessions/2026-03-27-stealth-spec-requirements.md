# Session: 2026-03-27 Stealth Spec Requirements

## Summary
stealth-browser-hardening spec の requirements.md を作成。Phase 1（実装済み5件）+ Phase 2（Redis セッション管理4件）+ Phase 3（SaaS ルーティング5件）の14要件を定義。

## Tasks Completed
- stealth-browser-hardening spec ディレクトリ作成（.config.kiro + requirements.md）
- 14要件を3フェーズに分けて定義:
  - Phase 1 (Req 1-5): StealthBrowserFactory、jitter、proxy-ready、ScrapingConfig、消費者移行（全て実装済み）
  - Phase 2 (Req 6-9): SessionManager（Redis Cookie管理）、ログインタスク、分散ロック、ステートレス原則
  - Phase 3 (Req 10-14): PageFetcherプロトコル、FetcherRouter、SaaSFetcher、リトライ/フォールバック、自己実装禁止制約

## Decisions Made
- Phase 2 の分散ロック: Redis lock key `login_lock:{site_id}`, TTL 120秒
- Phase 3 のフォールバック: SaaS API 全リトライ失敗後に Playwright stealth にフォールバック
- 自己実装禁止: マウス移動シミュレーション、TLS JA3フィンガープリント偽装は SaaS に委譲

## Open Items
- requirements.md のレビュー後、design.md → tasks.md 作成
- MonitoringSite に is_hard_target カラム追加（Phase 3 実装時）

## Related Specs
- stealth-browser-hardening（requirements.md 作成完了）
- crawl-pipeline-architecture（依存先）

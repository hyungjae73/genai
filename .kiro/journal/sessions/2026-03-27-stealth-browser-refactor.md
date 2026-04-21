# Session: 2026-03-27 Stealth Browser Refactoring

## Summary
商用ボット対策（Cloudflare等）への脆弱性を解消するため、全Playwrightラッパーをリファクタリング。StealthBrowserFactory を新設し、playwright-stealth統合、固定UA、ランダムviewport、delay jitter、プロキシ対応を一元化。

## Tasks Completed
- アーキテクチャ修正レポート出力（設定管理/依存注入/リソース管理の3観点）
- scraping_config.py 新設（ScrapingConfig BaseSettings: proxy SecretStr、UA、viewport pool、jitter）
- stealth_browser.py 新設（StealthBrowserFactory: stealth適用+UA/viewport/proxy/jitter の単一エントリポイント）
- browser_pool.py リファクタ（_create_browser/acquire → Factory経由、stealth context+page返却）
- crawler.py リファクタ（_get_browser/_crawl_page → Factory経由、jitter挿入、context管理）
- screenshot_manager.py リファクタ（_do_capture → Factory経由、async_playwright直接呼び出し廃止）
- screenshot_capture.py リファクタ（__aenter__/capture_screenshot → Factory経由、jitter挿入）
- requirements.txt に playwright-stealth==1.0.6 追加

## Decisions Made
- User-Agent: ランダム化せず最新Windows Chrome UA を1つ固定（矛盾による検知防止）
- Viewport: [1920x1080, 1366x768, 1440x900, 1536x864] からContext生成時にランダム選択
- Jitter: random.uniform(0.8, 2.5)秒をリクエスト前に挿入
- プロキシ: 環境変数ベースのProxy-Readyアーキテクチャ（現在はNoneでフォールバック）
- DRY: StealthBrowserFactory が全Playwright消費者の単一エントリポイント

## Open Items
- playwright-stealth パッケージのインストール（pip install playwright-stealth）
- 既存テストの更新（BrowserPool等のモック調整が必要な可能性）
- advanced-dark-pattern-detection の着手

## Related Specs
- crawl-pipeline-architecture（BrowserPool, PageFetcherStage）
- crawl-data-enhancement（ScreenshotManager）

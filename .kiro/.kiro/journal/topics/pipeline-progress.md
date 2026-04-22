# Topic: Pipeline Progress — crawl-pipeline-architecture 実装進捗

## Timeline

### 2026-03-26
- Task 1 (DB モデル拡張) — 完了: MonitoringSite 5カラム, VerificationResult 5カラム, EvidenceRecord テーブル, CrawlSchedule テーブル, Alembic マイグレーション
- Task 2 (コアフレームワーク) — 完了: CrawlContext, CrawlPlugin, CrawlPipeline, resolve_plugin_config, Property tests (1,5,6,7,8,17)
- Task 3 (Checkpoint) — 完了: 全60テスト通過
- Task 4.1-4.5 — 完了: BrowserPool, LocalePlugin, ModalDismissPlugin, PreCaptureScriptPlugin, Property test (26)
- Task 4.6 — 完了: Property tests (4, 9, 24)
- Task 4.7 — 完了: PageFetcherStage 実行順序制御（前セッション実装、テスト25件通過確認）
- Task 4.8 — 完了: Property test (20: Delta crawl conditional headers)
- Task 5.1 — 完了: StructuredDataPlugin（JSON-LD, Microdata, Open Graph、優先順位マージ、26テスト）
- Task 5.2 — 完了: ShopifyPlugin（/products/{handle}.json API、バリアント抽出、25テスト）
- Task 5.3 — 完了: HTMLParserPlugin（PaymentInfoExtractorフォールバック、19テスト）
- Task 5.4 — 完了: OCRPlugin（ROI検出、価格パターン、証拠レコード、26テスト）
- Task 5.5 — 完了: DataExtractor property tests (Properties 2, 3, 9, 10)
- Task 6 — 完了: Checkpoint 264テスト通過
- Task 7 — 完了: Validator plugins + Property tests (11, 12)
- Task 8 — 完了: Reporter plugins + Property tests (13, 14, 15, 16)
- Task 9 — 完了: Checkpoint 351テスト通過
- Task 10 — 完了: Scalability (RateLimiter, Dispatcher, Scheduler) + Property tests (18, 21, 22, 23)
- Task 11 — 完了: Celery queue separation + backward compatibility + Property test (19)
- Task 12 — 完了: Checkpoint 427テスト通過
- Task 13 — 完了: Schedule CRUD API + Property test (25)
- Task 14 — 完了: docker-compose (MinIO, 4 queue workers)
- Task 15 — 完了: Frontend ScheduleTab + Property test (27)
- Task 16 — 完了: Final checkpoint 1,045テスト全通過
- **SPEC COMPLETED** — 全16タスク、27プロパティテスト完了
  - 関連: sessions/2026-03-26-spec-complete.md
  - 関連: sessions/2026-03-26-initial.md, sessions/2026-03-26-review.md

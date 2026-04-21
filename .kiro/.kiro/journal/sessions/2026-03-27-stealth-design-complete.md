# Session: 2026-03-27 Stealth Design Complete

## Summary
stealth-browser-hardening の design.md を作成。5フェーズ18要件をカバーする9コンポーネント、23 correctness properties、Redis キー設計、エラーハンドリング、テスト戦略を定義。

## Tasks Completed
- design.md 作成（全セクション完成）:
  - 9コンポーネント: SessionManager, PageFetcher Protocol, StealthPlaywrightFetcher, SaaSFetcher, FetcherRouter, ValidationStage, TelemetryCollector, AdaptiveEvasionEngine, ScrapingConfig拡張
  - 2 Mermaid図: システムアーキテクチャ + リクエストフロー
  - Redis キー設計: 7パターン（Cookie, Lock, Telemetry, Bandit state）
  - 23 correctness properties（全18要件にトレーサビリティ）
  - フェーズ別エラーハンドリング表
  - Hypothesis PBT + ユニット + 統合テスト戦略

## Decisions Made
- PageFetcher: Python Protocol（構造的部分型）で抽象化
- SessionManager: redis.asyncio + redis-py Lock で分散ロック
- テレメトリ: Redis Sorted Set（score=timestamp）+ 24h TTL
- バンディット: Epsilon-Greedy（UCB1より運用理解が容易）
- ValidationStage: CrawlPlugin として validator ステージに配置
- VLM: 非同期 Celery タスク（パイプライン非ブロック）
- DB変更: MonitoringSite.is_hard_target（Boolean, default false）

## Open Items
- tasks.md 作成（次セッション）

## Related Specs
- stealth-browser-hardening（requirements + design 完成）

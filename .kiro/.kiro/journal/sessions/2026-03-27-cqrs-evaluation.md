# Session: 2026-03-27 (CQRS Evaluation)

## Summary
CQRSの導入メリットを評価。現状が既にCQRS的な分離を部分的に実現しており、フル導入は不要と判断。将来的にはマテリアライズドビューで対応する方針。

## Tasks Completed
- なし（アーキテクチャ評価のみ）

## Decisions Made
- **フルCQRSは導入しない**: 読み書き負荷比率が極端でなく、クエリも複雑でなく、結果整合性を許容するユースケースが少ない
- **マテリアライズドビューで対応**: DarkPatternScoreのダッシュボード集計が重くなった場合、PostgreSQLマテリアライズドビューで読み取りパフォーマンスを改善
- **既存のCQRS的分離を維持**: Command側=CrawlPipeline（Celery非同期）、Query側=FastAPI GETエンドポイント（直接PostgreSQL）

## Topics Discussed
- 現状のCommand/Query分離状況（CrawlPipeline vs FastAPI GET）
- フルCQRS導入時の変更点（Read Model分離、イベントバス、結果整合性）
- 10万サイト規模でのPostgreSQLインデックス対応可能性
- DarkPatternScore集計クエリの将来的な負荷予測

## Open Items
- testcontainers-migration tasks.md 作成・実装
- dark-pattern-notification design.md → tasks.md
- advanced-dark-pattern-detection design.md → tasks.md

## Related Specs
- .kiro/specs/crawl-pipeline-architecture/ (既存のCQRS的分離)
- .kiro/specs/advanced-dark-pattern-detection/ (マテリアライズドビュー候補)

# Session: 2026-03-26 (Architecture Constitution)

## Summary
アーキテクチャ憲法（structure.md）をsteeringファイルとして作成。Celeryキュー厳格ルーティング、フロントエンドFeature-Sliced Design、同期/非同期境界防御の3原則を定義。

## Tasks Completed
- `.kiro/steering/structure.md` 作成（auto inclusion）

## Decisions Made
- **Celeryキュー4分離の厳格化**: crawl/extract/validate/reportの用途・concurrency・依存技術を明文化。キュー混同を禁止。違反例も明記。
- **フロントエンドFeature-Sliced Design採用**: pages（ルーティングのみ）/ features（ドメインUI）/ components/ui（プレゼンテーショナル）/ api（Axiosクライアント）の責務分離を定義
- **psycopg2-binary同期/非同期境界防御**: async def + 直接DBアクセスを禁止。def（同期）またはrun_in_threadpoolパターンを必須化。既存コードの技術的負債も認識。

## Topics Discussed
- Celeryキューの責務分離とリソース競合防止
- Reactコンポーネントの責務分離パターン
- FastAPI + psycopg2-binaryのイベントループブロック問題

## Open Items
- 既存エンドポイントのasync def + 直接DBアクセスパターンの修正（技術的負債）
- features/ ディレクトリへの段階的移行検討

## Related Specs
- .kiro/steering/structure.md
- .kiro/steering/product.md

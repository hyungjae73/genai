# Session: 2026-03-26 (Technology Constitution)

## Summary
技術・コード憲法（tech.md）をsteeringファイルとして作成。PBT強制、TypeScript/React最新記法、SQLAlchemy/Pydantic厳格構文、リソース管理の4原則を定義。3つの憲法が全て揃った。

## Tasks Completed
- `.kiro/steering/tech.md` 作成（auto inclusion）

## Decisions Made
- **PBT強制**: バックエンドHypothesis + フロントエンドfast-check。データパーサー、シリアライズ、設定マージ、価格比較、フォームバリデーション、状態遷移で必須
- **any絶対禁止**: TypeScript Strictモード前提。APIレスポンスは型定義で検証
- **useEffectデータフェッチ禁止**: React 19のuse/useActionState活用、カスタムフックに隠蔽
- **Pydantic V1メソッド禁止**: .dict()→.model_dump()、.parse_obj()→.model_validate()
- **with句/try-finally必須**: Playwright、Pillow、BeautifulSoupのリソース管理

## Topics Discussed
- 3つの憲法体系の完成: product.md（プロダクト）+ structure.md（アーキテクチャ）+ tech.md（技術・コード）

## Open Items
- dark-pattern-notification / advanced-dark-pattern-detection の design.md → tasks.md 作成・実装
- 既存コードの憲法準拠チェック（async def + DB直接アクセス、Pydantic V1メソッド等）

## Related Specs
- .kiro/steering/tech.md
- .kiro/steering/product.md
- .kiro/steering/structure.md

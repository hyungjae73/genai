# Session: 2026-03-31 (core-interfaces-implementation)

## Summary
CTO承認済みアーキテクチャの具現化。DynamicComplianceRuleModel（SQLAlchemy）、ContentFingerprintModel（pgvector対応）、Pydanticスキーマ（LLMJudgeVerdict等）、DynamicLLMValidatorPlugin（CrawlPlugin統合版）を実装。

## Tasks Completed
- `genai/src/rules/models.py` — DynamicComplianceRuleModel（DB自然言語ルール）+ ContentFingerprintModel（pgvector Vector(384)、is_canonical_product フラグ）
- `genai/src/rules/schemas.py` — RuleSeverity/DarkPatternCategory Enum、LLMJudgeVerdict（Structured Outputs）、DynamicRuleCreate/Update/Response、LLMJudgeResultResponse
- `genai/src/rules/dynamic_llm_validator.py` — CrawlPlugin 統合版に書き直し。should_run/execute 実装、DB ルールロード → LLM Judge 順次評価 → violations 追加

## Decisions Made
- **pgvector フォールバック**: pgvector 未インストール時は JSONB にフォールバック（テスト環境対応）
- **Structured Outputs**: LLMJudgeVerdict Pydantic モデルで LLM 出力を型安全にパース
- **DarkPatternCategory Enum**: 11値の Enum で分類タクソノミーを型レベルで強制
- **execution_order**: ルール実行順序を DB で制御可能に（server_default=100）
- **applicable_site_ids**: サイト単位のルール適用制御を JSONB で実現

## Open Items
- Alembic マイグレーション作成（dynamic_compliance_rules + content_fingerprints テーブル）
- DynamicRuleProvider の DB 実装
- LLMJudgeClient の各プロバイダー実装（Gemini/Claude/OpenAI）
- API エンドポイント（ルール CRUD）
- advanced-dark-pattern-detection タスク実行

## Related Specs
- .kiro/specs/advanced-dark-pattern-detection/

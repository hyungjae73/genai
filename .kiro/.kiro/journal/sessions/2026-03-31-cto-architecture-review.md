# Session: 2026-03-31 (cto-architecture-review)

## Summary
CTOからの3つのアーキテクチャ修正指令を反映。Hybrid Rule Engine（Built-in + LLM as a Judge）、TF-IDF廃止→Dense Vector（all-MiniLM-L6-v2）、ContentFingerprint爆発防止（is_canonical_product）を実装。

## Tasks Completed
- `genai/src/rules/engine.py` — RuleEngine を Hybrid 化（Built-in + Dynamic LLM の2フェーズ実行）
- `genai/src/rules/dynamic_llm_validator.py` — DynamicLLMValidatorPlugin 新規作成（LLM as a Judge、DynamicComplianceRule dataclass、LLMJudgeClient/DynamicRuleProvider Protocol）
- `genai/src/darksite/protocol.py` — TF-IDF 廃止、Dense Vector（all-MiniLM-L6-v2, 384次元）に置換、ContentFingerprint に is_canonical_product フラグ追加、ContentEmbedder/FingerprintStore Protocol 追加

## Decisions Made
- **Hybrid Rule Engine**: Built-in Rules（Python コード）+ Dynamic LLM Rules（DB 自然言語プロンプト）の2層。コンプライアンス担当者はコード変更ゼロでルール追加可能
- **LLM as a Judge**: JUDGE_SYSTEM_PROMPT でJSON出力を強制、confidence_threshold（デフォルト0.7）で違反判定
- **TF-IDF 全廃**: テキストSpinning対策として all-MiniLM-L6-v2 Dense Vector をLayer 1に採用。コサイン類似度 >= 0.85 で高類似判定
- **Fingerprint 爆発防止**: is_canonical_product=True のみ保存、max_fingerprints_per_site=50、TTL 90日自動削除
- **コンテンツ類似度加重**: text(0.6) + image(0.4) に変更（旧: text 0.4 + field 0.3 + structure 0.15 + visual 0.15）

## Open Items
- DynamicComplianceRule の DB テーブル作成（Alembic マイグレーション）
- ContentFingerprint の DB テーブル作成（pgvector 拡張含む）
- MonitoringSite.merchant_category カラム追加
- advanced-dark-pattern-detection タスク実行

## Related Specs
- .kiro/specs/advanced-dark-pattern-detection/
- .kiro/specs/fake-site-detection-alert/

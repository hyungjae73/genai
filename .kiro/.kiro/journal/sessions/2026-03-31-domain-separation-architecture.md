# Session: 2026-03-31 (domain-separation-architecture)

## Summary
契約違反検出（In-site）とDarksite検出（Off-site）のドメイン分離アーキテクチャを設計・実装。BaseContractRule + RuleEngine（Strategy/Registry パターン）と DarksiteDetectorProtocol（独立サービス）のインターフェースを作成。

## Tasks Completed
- ドメイン分離・拡張性設計レポート出力（3セクション: 動的拡張OCP証明、Darksite同定手法、データモデル変更）
- `genai/src/rules/base.py` — BaseContractRule ABC + RuleResult dataclass
- `genai/src/rules/engine.py` — RuleEngine（レジストリ + 動的ロード + カテゴリフィルタ）
- `genai/src/rules/price_match.py` — 既存ContractComparisonPluginの価格比較をルール化した参考実装
- `genai/src/darksite/protocol.py` — DarksiteDetectorProtocol + DomainMatch/ContentMatch/ContentFingerprint/DarksiteReport

## Decisions Made
- **契約違反検出**: Strategy + Rule Registry パターン。新ルール追加は1ファイル作成+DB設定のみ（OCP準拠）
- **Darksite検出**: CrawlPipelineとは完全分離した独立サービス（DarksiteDetectorProtocol）
- **同一商品同定**: 3層アプローチ（TF-IDF → pHash → ベクトル埋め込み）。初期はLayer 1+2のみ
- **データモデル拡張方針**: MonitoringSiteにmerchant_category追加、ContractConditionにvalidation_rules(JSONB)追加、新規ContentFingerprintテーブル（実装は別spec）
- **動的ルールロード**: `src.rules.{rule_id}` モジュール規約で自動検出

## Topics Discussed
- Open-Closed Principleの具体的な証明（新ルール追加時の作業範囲）
- ベクトル埋め込みの将来拡張（pgvector/Qdrant）
- 既存FakeSiteDetectorとDarksiteDetectorProtocolの関係

## Open Items
- MonitoringSite.merchant_category カラム追加（Alembicマイグレーション）
- ContractCondition.validation_rules カラム追加
- ContentFingerprint テーブル作成
- ContractValidatorPlugin（RuleEngine統合版）の実装
- DarksiteHunterService（Protocol実装）の実装
- advanced-dark-pattern-detection タスク実行

## Related Specs
- .kiro/specs/advanced-dark-pattern-detection/（契約違反検出の高度化）
- .kiro/specs/fake-site-detection-alert/（既存Darksite検出 — リファクタ対象）

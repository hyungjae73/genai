# Session: 2026-03-27 Phase 2.5 & Phase 4 Requirements

## Summary
stealth-browser-hardening に Phase 2.5（Soft Block 検知 + VLM ラベリング）と Phase 4（バンディットアルゴリズム適応型回避エンジン）の4要件を追加。合計18要件に拡張。

## Tasks Completed
- Requirement 15: Page Validation Engine（Soft Block 検知、DOM 分析、anti-bot signature レジストリ）
- Requirement 16: Vision-LLM フォールバックラベリング（未知ブロック画面の VLM 自動分類）
- Requirement 17: テレメトリと成功率モニタリング（Redis 時系列、異常検知イベント）
- Requirement 18: バンディットアルゴリズム動的ルーティング（Epsilon-Greedy、Exploration Mode）
- 既存 Req 15→17、Req 16→18 に繰り下げ
- Introduction、Glossary を Phase 2.5/4 の用語で更新

## Decisions Made
- Phase 2.5 を Phase 2 と Phase 3 の間に配置（Soft Block 検知は SaaS ルーティングの前提知識）
- VLM API コスト制御: サイトあたり5回/時のレート制限
- バンディット AC 8: Req 13（自殺的フォールバック禁止）との整合性を明示的に参照
- Soft Block ラベル体系: SUCCESS / SOFT_BLOCKED / HARD_BLOCKED / CAPTCHA_CHALLENGE / ACCESS_DENIED / CONTENT_CHANGED / UNKNOWN_BLOCK

## Open Items
- design.md → tasks.md 作成

## Related Specs
- stealth-browser-hardening（18要件完成）

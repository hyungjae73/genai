# Session: 2026-03-27 Suicide Fallback Fix

## Summary
CTOレビューにより Requirement 13 の「自殺的フォールバック」を修正。高難度ターゲットで SaaS 全リトライ失敗時に Playwright にフォールバックする設計を禁止し、即座停止 + SAAS_BLOCKED ステータス + critical アラート発報に変更。

## Decisions Made
- 高難度ターゲット（is_hard_target=True）で SaaS が全滅した場合、自前 Playwright へのフォールバックは禁止
- 理由: SaaS でブロックされたサイトに非力な Playwright で突撃すると IP BAN → システム全体が焼け野原
- 代替: リクエスト失敗 + SAAS_BLOCKED ステータス + 運用チームへの critical アラート

## Related Specs
- stealth-browser-hardening（Requirement 13 修正）

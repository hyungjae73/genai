# Session: 2026-03-27 CTO Design Review Fixes

## Summary
CTOレビューによる design.md の5つの致命的問題を修正。リトライの死の螺旋、VLM破産トラップ、バンディット非定常性、Redisロックゾンビ化、SPA偽陽性を解消。

## Tasks Completed
- Fix 1: SaaS リトライ死の螺旋 → base_delay 30→5、Jitter追加、soft_time_limit=180s の数学的制約
- Fix 2: VLM 破産トラップ → DOM構造ハッシュ（pHash）による Redis キャッシュ + ショートサーキット
- Fix 3: バンディット非定常性 → 累積カウンター廃止、Redis List Sliding Window（直近100件）
- Fix 4: Redis Lock ゾンビ化 → _active_locks dict で token 追跡、verify_lock_held() 追加
- Fix 5: MIN_BODY_SIZE 脆弱性 → Text-to-Tag Ratio チェック追加（SPA偽陽性防止）
- Design Decisions テーブル更新、Redis キーテーブル更新

## Decisions Made
- SaaS リトライ: T_wait = Σ(5×2^n) + 5×3.0 = 170s < soft_time_limit(180s)
- バンディット: Sliding Window N=100（非定常環境で古いデータの影響を排除）
- VLM キャッシュ: DOM タグ構造のみハッシュ化（テキスト変更を無視）、Redis TTL 24h
- ロック安全性: Cookie 保存前に lock.locked() で再確認（TTL超過による競合防止）
- DOM anomaly: body_bytes < 1KB OR (tag_count > 10 AND text_to_tag_ratio < 5.0)

## Open Items
- tasks.md 作成

## Related Specs
- stealth-browser-hardening（design.md CTOレビュー修正完了）

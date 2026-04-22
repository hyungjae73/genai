# Session: 2026-03-27 (Steering憲法設置)

## Summary
pytest.iniに`filterwarnings = error`を設定し、Zero Warning Policyを実装基盤レベルで強制化。サードパーティWarning3種のホワイトリストを追加。debugging.mdを例外ハンドリング方針で改訂。workflow.md（開発プロセスと影響範囲の憲法）を新設。

## Tasks Completed
- pytest.ini: `filterwarnings = error` + サードパーティ3種のホワイトリスト設定
- debugging.md: 例外ハンドリング方針（ホワイトリスト運用ルール）を追記
- workflow.md: ボーイスカウトの規則、全体影響把握、負債タスク化提案の3原則を新設

## Decisions Made
- **urllib3 Warningはメッセージパターンで除外**: `ignore::urllib3.exceptions.NotOpenSSLWarning`はimport時にWarningが発火してクラス解決自体が失敗するため、`ignore:urllib3 v2 only supports OpenSSL:Warning`のメッセージパターン方式を採用
- **filterwarnings = errorを絶対に削除しない**: サードパーティWarningが出た場合はホワイトリスト追加で対応する運用ルールを明文化

## Topics Discussed
- pytest filterwarningsのクラス解決順序問題（import時Warning発火）
- steering fileの役割分担: debugging.md（エラー修復思考）、workflow.md（影響範囲・負債管理）

## Open Items
- なし

## Related Specs
- .kiro/steering/debugging.md
- .kiro/steering/workflow.md
- genai/pytest.ini

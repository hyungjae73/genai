---
inclusion: auto
---

# Session Journal — 意思決定・会話履歴の記録ルール

## 概要

各セッションの意思決定、進捗、会話サマリーを `.kiro/journal/` 配下のMDファイルに記録する。
後から振り返り・検索できるように、テーマ別と日付時間軸別の2軸で整理する。

## ディレクトリ構造

```
.kiro/journal/
├── sessions/           # 日付時間軸: セッションごとの記録
│   └── YYYY-MM-DD-HHmm.md
├── topics/             # テーマ別: トピックごとの累積記録
│   ├── architecture.md
│   ├── decisions.md
│   ├── figma-integration.md
│   └── ...
└── index.md            # 全セッション・トピックの索引
```

## セッション記録のフォーマット

各セッションファイル (`sessions/YYYY-MM-DD-HHmm.md`) は以下の形式:

```markdown
# Session: YYYY-MM-DD HH:MM

## Summary
（1-3文でセッションの概要）

## Tasks Completed
- タスクID: 簡潔な説明

## Decisions Made
- **決定事項**: 理由・背景

## Topics Discussed
- トピック名: 要約

## Open Items
- 未完了・次回持ち越し事項

## Related Specs
- spec名へのリンク
```

## トピックファイルのフォーマット

各トピックファイル (`topics/{topic-name}.md`) は以下の形式:

```markdown
# Topic: トピック名

## Timeline
### YYYY-MM-DD
- 決定事項や議論の要約
- 関連セッション: sessions/YYYY-MM-DD-HHmm.md
```

## 記録タイミング

1. **セッション開始時**: 前回セッションのサマリーがあれば読み込み、コンテキストを復元
2. **セッション終了時**: そのセッションで行った作業・決定・議論をファイルに記録
3. **重要な意思決定時**: decisions トピックファイルに即座に追記

## 記録対象

- spec作成・更新の決定とその理由
- アーキテクチャ上の選択（技術選定、設計方針）
- ユーザーからのフィードバックと対応
- タスク実行の進捗と結果
- Figma連携やツール利用の結果
- 未解決の課題・次回アクション

## 記録しない対象

- コードの詳細な差分（gitで管理）
- テスト実行の生ログ
- 一時的なデバッグ情報

# Session: 2026-04-06 (darksite-ui-requirement)

## Summary
フロントエンド要件シートにFR-9（ダークサイト候補サイト確認UI）を追加。既存の偽サイト検知ページではドメイン/コンテンツ類似度スコアのみで実コンテンツ確認手段がなかった問題を解決するため、サイト詳細のダークパターンタブ内にダークサイト候補サブタブを新設する要件を定義。

## Tasks Completed
- FR-9: ダークサイト候補サイト確認UI要件作成（Before/After ASCIIワイヤーフレーム、型定義、API設計）
- api.tsまとめセクションにDarksiteCandidate/DarksiteContentComparison型追加
- 実装優先度テーブルにFR-9（🔴高）追加
- 概要の合計カウント更新（8→9カテゴリ、23→25コンポーネント変更）

## Decisions Made
- **ダークサイト候補UIはダークパターンタブ内に統合**: 偽サイト検知ページ（FakeSites.tsx）とは別に、サイト詳細のダークパターンタブ内サブタブとして配置。理由: サイトコンテキストでの確認が自然、コンテンツ比較はサイト単位の操作。
- **コンテンツ比較は左右並列表示**: 正規サイト vs 候補サイトのテキスト・画像を横並びで比較。契約条件乖離リストも表示。
- **バックエンドAPI 2本新規必要**: `/api/sites/{site_id}/darksites`（一覧）と `/api/darksites/{id}/content`（詳細比較）。DarksiteReport/ContentMatch/DomainMatchのデータをフロント向けに整形して返す。
- **FR-9は🔴高優先度**: コンテンツ確認なしでは偽サイト判定の精度検証ができないため。

## Topics Discussed
- DarksiteDetectorProtocol（protocol.py）のDomainMatch/ContentMatch/DarksiteReportデータ構造をフロントエンド型に変換する設計
- 既存FakeSites.tsxの限界（スコアのみ、コンテンツ確認不可）

## Open Items
- バックエンドAPI `/api/sites/{site_id}/darksites` と `/api/darksites/{id}/content` の実装が必要
- DarksiteDetectorProtocolの実装（full_scan, compare_content）がまだプロトコル定義のみ
- 画像比較のサムネイル表示にはスクリーンショット保存パスの連携が必要

## Related Specs
- `.kiro/specs/advanced-dark-pattern-detection/`
- `.kiro/specs/fake-site-detection-alert/`

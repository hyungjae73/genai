---
inclusion: manual
---

# 偽サイト検知 詳細仕様

最終更新: 2026-03-22

## 概要

監視対象サイトに類似したドメイン（タイポスクワッティング等）を検知し、偽サイトの存在をアラートする機能。毎週月曜AM3:00 (UTC) に自動実行。

## 検知フロー

### ステップ1: 候補ドメイン生成

`_generate_candidate_domains()` が正規ドメインから以下のパターンで候補を自動生成（最大50件）:

| パターン | 例（`example.com`の場合） |
|---|---|
| 文字置換 | `l→1`, `i→1`, `o→0`, `a→@`, `e→3`, `s→5` |
| 文字省略 | `exampl.com`, `exmple.com` 等 |
| 文字重複 | `eexample.com`, `exxample.com` 等 |
| TLD変更 | `example.net`, `example.org`, `example.co`, `example.io` |

### ステップ2: ドメイン類似度チェック

- `FakeSiteDetector.scan_similar_domains()` でレーベンシュタイン距離を計算
- 類似度 = `1.0 - (距離 / max(len(d1), len(d2)))`
- 閾値: **0.8以上** で「疑わしい」と判定
- ドメインは正規化（`www.` 除去、小文字化、ポート除去）

### ステップ3: コンテンツ類似度チェック（未接続）

- `verify_fake_site()` でTF-IDF + コサイン類似度を計算
- 閾値: **0.7以上** で「偽サイト確定」
- HTMLタグ除去後、3文字以上の単語を抽出して単語頻度ベクトルを比較

## 実装上の既知の問題

### 致命的な問題

1. **`domain`属性の不在**: `MonitoringSite` モデルには `url` フィールドしかなく `domain` フィールドがない。`scan_all_fake_sites` 内の `site.domain` で `AttributeError` になる可能性が高い
2. **コンテンツ比較が未接続**: `_scan_fake_sites_async` 内で `verify_fake_site()` が呼ばれていない。`scan_similar_domains` は常に `is_confirmed_fake=False` で返すため、確定判定が動作しない。具体的には:
   - 類似ドメインが見つかっても、そのドメインを実際にクロールする処理がない
   - クロールしたコンテンツを `verify_fake_site()` に渡す処理がない
   - `confirmed = [s for s in suspicious if s.is_confirmed_fake]` は常に空リストになる
   - 結果としてアラートは一切送信されない
3. **候補ドメインのDNS確認なし**: 存在しないドメインも候補に含まれ、無駄な処理が発生する
4. **商品名単位の比較なし**: `calculate_content_similarity()` はHTML全体のTF-IDFコサイン類似度のみ。商品名・価格・ブランド名等の個別フィールド比較は未実装

### 検知できないケース

- 全く異なるドメイン名を使った偽サイト（例: `payment-support-center.com` が `example-shop.com` を模倣）
- サブドメインを使った偽装（例: `example-shop.evil.com`）
- ハイフンの追加/削除パターン（`example-shop` → `exampleshop`）
- 日本語ドメイン（IDN/Punycode）のバリエーション
- 候補生成パターンに含まれない文字置換（`rn→m`, `vv→w` 等のビジュアル類似）
- 正規ドメインのTLDが `.co.jp` 等の複合TLDの場合、`rsplit('.', 1)` で正しく分割できない

## 設定値

| パラメータ | デフォルト値 | 説明 |
|---|---|---|
| `domain_similarity_threshold` | 0.8 | ドメイン類似度の疑わしい判定閾値 |
| `content_similarity_threshold` | 0.7 | コンテンツ類似度の確定判定閾値 |
| 候補ドメイン上限 | 50 | 1ドメインあたりの候補生成数上限 |

## 改善予定（Requirement 9, 10で対応）

### ドメイン類似度
- Damerau-Levenshtein距離への変更（隣接文字転置対応）
- ビジュアル類似文字の事前正規化（`rn→m`, `vv→w`, `cl→d`等）
- ハイフン除去後の追加比較
- 複合TLD対応
- ハイフン追加/削除パターンの候補生成

### コンテンツ類似度
- IDF重み付けの追加
- 商品名・価格・ブランド名等の重要フィールド重み付け
- DOM構造類似度の補助指標追加
- スクリーンショットpHash比較による視覚的類似度
- 加重平均スコア: テキスト(0.4) + フィールド一致(0.3) + 構造(0.15) + 視覚(0.15)

## 関連ファイル

- `genai/src/fake_detector.py` - `FakeSiteDetector` クラス（検知ロジック本体）
- `genai/src/tasks.py` - `scan_all_fake_sites`, `scan_fake_sites`, `_generate_candidate_domains`
- `genai/src/celery_app.py` - `weekly-fake-site-scan` スケジュール定義
- `genai/src/alert_system.py` - アラート送信（偽サイト確定時）

# フロントエンド実装要件シート: Dark Pattern Detection UI

## 概要

advanced-dark-pattern-detection バックエンドで追加された全概念のフロントエンドUI実装要件。
9カテゴリ、合計25画面/コンポーネント変更。

---

## FR-1: ダークパターンスコア表示（サイト詳細）

**対象ファイル:** `SiteDetailPanel.tsx`, 新規 `DarkPatternTab.tsx`
**バックエンドAPI:** `GET /api/sites/{site_id}/dark-patterns`
**優先度:** 🔴 高

### Before
```
┌─────────────────────────────────────────────┐
│ [契約条件] [スクリーンショット] [検証・比較]  │
│ [アラート] [スケジュール]                     │
│                                              │
│  （ダークパターン関連の表示なし）              │
└─────────────────────────────────────────────┘
```

### After
```
┌──────────────────────────────────────────────────────┐
│ [契約条件] [スクリーンショット] [検証・比較]           │
│ [アラート] [スケジュール] [🛡️ ダークパターン]  ← 新規 │
│                                                       │
│  ┌─────────────────────────────────────────────┐      │
│  │ 総合リスクスコア                              │      │
│  │ ████████████░░░░░░░░  0.75 / 1.0  ⚠️ 高リスク│      │
│  │                                              │      │
│  │ サブスコア内訳:                                │      │
│  │  CSS視覚欺瞞    ████░░░░  0.40               │      │
│  │  LLM分類        ████████  0.75               │      │
│  │  ジャーニー      ██░░░░░░  0.15 (ペナルティ)  │      │
│  │  UIトラップ      ██████░░  0.50               │      │
│  │                                              │      │
│  │ 検出パターン:                                  │      │
│  │  🔴 high_dark_pattern_risk (critical)         │      │
│  │  🟡 hidden_subscription (warning)             │      │
│  │  🟡 sneak_into_basket (warning)               │      │
│  │  🔵 distant_cancellation_terms (info)         │      │
│  │                                              │      │
│  │ 最終検出: 2026-04-06 14:30:00                 │      │
│  └─────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────┘
```

### 実装要件
- `SiteDetailPanel.tsx` に6番目のタブ「ダークパターン」を追加
- 新規 `DarkPatternTab.tsx` コンポーネント作成
- `api.ts` に `getDarkPatterns(siteId)` API関数追加
- スコアゲージ: 0-0.3=緑, 0.3-0.6=黄, 0.6-1.0=赤
- サブスコアは横棒グラフ（CSS `width: ${score * 100}%`）
- 検出パターンは Badge コンポーネント（severity別色分け）

---

## FR-2: ダークパターンスコア履歴チャート（時系列）

**対象ファイル:** `DarkPatternTab.tsx`（FR-1内に統合）
**バックエンドAPI:** `GET /api/sites/{site_id}/dark-patterns/history`
**優先度:** 🟡 中

### Before
```
（FR-1のダークパターンタブ内にスコア表示のみ、履歴なし）
```

### After
```
┌──────────────────────────────────────────────────┐
│ 🛡️ ダークパターン                                 │
│                                                   │
│  [スコア概要]  [📈 スコア推移]  ← タブ切替         │
│                                                   │
│  スコア推移（直近30日）                             │
│  1.0 ┤                                            │
│  0.8 ┤        ╭──╮                                │
│  0.6 ┤   ╭────╯  ╰──╮                            │
│  0.4 ┤───╯           ╰────╮                       │
│  0.2 ┤                    ╰───                    │
│  0.0 ┤────────────────────────                    │
│      └─┬──┬──┬──┬──┬──┬──┬──                     │
│       3/7 3/14 3/21 3/28 4/4                      │
│                                                   │
│  --- サブスコア推移 ---                             │
│  ── CSS視覚欺瞞  ── LLM分類                       │
│  ── ジャーニー    ── UIトラップ                     │
└──────────────────────────────────────────────────┘
```

### 実装要件
- `DarkPatternTab.tsx` 内にサブタブ「スコア概要 / スコア推移」を設置
- Chart.js `Line` コンポーネントで時系列折れ線グラフ
- 総合スコア + 4サブスコアを5本の折れ線で表示
- `api.ts` に `getDarkPatternHistory(siteId, limit?, offset?)` 追加
- レスポンス型: `DarkPatternHistoryResponse`

---

## FR-3: 加盟店カテゴリ（merchant_category）設定

**対象ファイル:** `SiteDetailPanel.tsx` → `ContractTab.tsx` or サイト編集モーダル
**バックエンドAPI:** `PUT /api/sites/{site_id}` （merchant_category フィールド追加）
**優先度:** 🟡 中

### Before
```
┌─────────────────────────────────┐
│ サイト編集                       │
│                                  │
│  サイト名: [____________]        │
│  URL:      [____________]        │
│  有効:     [✓]                   │
│                                  │
│  （カテゴリ設定なし）             │
└─────────────────────────────────┘
```

### After
```
┌─────────────────────────────────────────┐
│ サイト編集                               │
│                                          │
│  サイト名: [____________]                │
│  URL:      [____________]                │
│  有効:     [✓]                           │
│                                          │
│  加盟店カテゴリ:                          │
│  [▼ subscription          ]  ← Select   │
│    ├ subscription（定期購入）             │
│    ├ ec_general（EC一般）                │
│    ├ digital_content（デジタル）          │
│    ├ travel（旅行）                      │
│    └ other（その他）                     │
│                                          │
│  ℹ️ カテゴリに応じて適用される             │
│    検出ルールが変わります                  │
└─────────────────────────────────────────┘
```

### 実装要件
- サイト編集フォームに `merchant_category` Select を追加
- カテゴリ選択肢: subscription, ec_general, digital_content, travel, other
- `api.ts` の `updateSite` に `merchant_category` パラメータ追加
- `Site` 型に `merchant_category?: string` 追加

---

## FR-4: 動的LLMルール管理CRUD画面

**対象ファイル:** 既存 `Rules.tsx` を拡張（現在はハードコード静的表示）
**バックエンドAPI:** `GET/POST/PUT/DELETE /api/dark-patterns/rules`（新規API必要）
**優先度:** 🔴 高

### Before
```
┌─────────────────────────────────────────────┐
│ コンプライアンスチェックルール               │
│                                              │
│  [カテゴリ ▼]                                │
│                                              │
│  ┌──────────────────────────────────┐        │
│  │ 契約価格との一致        [高] [有効]│        │
│  │ 表示されている価格が...           │        │
│  │ ▶ チェックポイント                │        │
│  └──────────────────────────────────┘        │
│  （ハードコードされた5つの静的ルールのみ）     │
│  （CRUD操作なし、DB連携なし）                 │
└─────────────────────────────────────────────┘
```

### After
```
┌──────────────────────────────────────────────────────┐
│ コンプライアンスチェックルール                         │
│                                                       │
│  [ビルトイン] [🤖 LLMルール]  ← タブ切替              │
│  [カテゴリ ▼] [重要度 ▼]                              │
│                                                       │
│  + 新規LLMルール登録                                  │
│                                                       │
│  ┌──────────────────────────────────────────────┐     │
│  │ 隠れサブスク検出  [warning] [有効] [subscription]│   │
│  │ 定期購入の条件が明確に表示されているか...        │     │
│  │                                               │     │
│  │ プロンプト:                                    │     │
│  │ ┌─────────────────────────────────────┐       │     │
│  │ │ 以下のページテキストを分析し、        │       │     │
│  │ │ 定期購入の条件が明確に...             │       │     │
│  │ │ {page_text}                          │       │     │
│  │ └─────────────────────────────────────┘       │     │
│  │                                               │     │
│  │ 確信度閾値: 0.7  実行順序: 100                 │     │
│  │ 対象カテゴリ: subscription                     │     │
│  │ 作成者: admin  作成日: 2026-04-01              │     │
│  │                                               │     │
│  │ [編集] [無効化] [削除]                         │     │
│  └──────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘

--- 新規LLMルール登録モーダル ---
┌──────────────────────────────────────────────────┐
│ 新規LLMルール登録                                 │
│                                                   │
│  ルール名 *:     [________________________]       │
│  説明:           [________________________]       │
│  重要度:         [▼ warning    ]                  │
│  カテゴリ:       [▼ other      ]                  │
│  確信度閾値:     [0.7____]                        │
│  実行順序:       [100____]                        │
│  作成者 *:       [________________________]       │
│                                                   │
│  プロンプトテンプレート *:                          │
│  ┌──────────────────────────────────────────┐    │
│  │ 以下のページテキストを分析してください。    │    │
│  │                                           │    │
│  │ {page_text}                               │    │
│  │                                           │    │
│  │ 契約条件: {contract_terms}                │    │
│  │ サイトURL: {site_url}                     │    │
│  └──────────────────────────────────────────┘    │
│  ⚠️ {page_text} は必須です                        │
│                                                   │
│  対象カテゴリ:   [+ 追加] subscription ×          │
│  対象サイトID:   [+ 追加] 1 × 5 ×                │
│                                                   │
│  [キャンセル]                    [登録]            │
└──────────────────────────────────────────────────┘
```

### 実装要件
- `Rules.tsx` にタブ切替追加: 「ビルトイン」（既存静的）/ 「LLMルール」（DB連携CRUD）
- 新規バックエンドAPI必要（`dark_patterns.py` に追加 or 新規 `rules_api.py`）:
  - `GET /api/dark-patterns/rules` — 一覧取得
  - `POST /api/dark-patterns/rules` — 新規作成
  - `PUT /api/dark-patterns/rules/{id}` — 更新
  - `DELETE /api/dark-patterns/rules/{id}` — 削除
- `api.ts` に型定義追加:
  ```typescript
  interface DynamicRule {
    id: number;
    rule_name: string;
    description: string | null;
    prompt_template: string;
    severity: 'critical' | 'warning' | 'info';
    dark_pattern_category: string;
    confidence_threshold: number;
    applicable_categories: string[] | null;
    applicable_site_ids: number[] | null;
    is_active: boolean;
    execution_order: number;
    created_by: string;
    created_at: string;
    updated_at: string;
  }
  ```
- `api.ts` に CRUD 関数追加:
  ```typescript
  getDynamicRules(): Promise<DynamicRule[]>
  createDynamicRule(data: DynamicRuleCreate): Promise<DynamicRule>
  updateDynamicRule(id: number, data: DynamicRuleUpdate): Promise<DynamicRule>
  deleteDynamicRule(id: number): Promise<void>
  ```
- フロントエンドバリデーション: `prompt_template` に `{page_text}` 必須チェック
- プロンプトテンプレートは `<textarea>` で複数行入力

---

## FR-5: サイト別検出ルールセット設定

**対象ファイル:** `SiteDetailPanel.tsx` → 新規 `DetectionRuleTab.tsx` or `DarkPatternTab.tsx` 内
**バックエンドAPI:** `GET /api/dark-patterns/rules` + サイトID絞り込み
**優先度:** 🟢 低

### Before
```
（サイト詳細にルール設定UIなし。
  どのルールが適用されるかサイト側から確認不可）
```

### After
```
┌──────────────────────────────────────────────────┐
│ 🛡️ ダークパターン                                 │
│                                                   │
│  [スコア概要] [スコア推移] [⚙️ 適用ルール]         │
│                                                   │
│  このサイトに適用されるルール:                      │
│                                                   │
│  ビルトインルール:                                  │
│  ┌──────────────────────────────────────┐         │
│  │ ✅ 契約価格との一致          [高]     │         │
│  │ ✅ 許可された決済方法        [中]     │         │
│  │ ✅ 手数料の妥当性            [中]     │         │
│  │ ✅ サブスクリプション条件    [高]     │         │
│  │ ✅ 情報の透明性              [中]     │         │
│  └──────────────────────────────────────┘         │
│                                                   │
│  LLMルール（このサイトに適用）:                     │
│  ┌──────────────────────────────────────┐         │
│  │ ✅ 隠れサブスク検出  [warning]        │         │
│  │ ✅ 解約導線チェック  [critical]       │         │
│  │ ⬜ 価格操作検出      [warning] (対象外)│        │
│  └──────────────────────────────────────┘         │
│                                                   │
│  ℹ️ LLMルールの追加・編集は                        │
│    「チェックルール」ページから行えます              │
└──────────────────────────────────────────────────┘
```

### 実装要件
- `DarkPatternTab.tsx` 内に3番目のサブタブ「適用ルール」追加
- ビルトインルール（静的5件）+ LLMルール（API取得）を表示
- LLMルールは `applicable_site_ids` にサイトIDが含まれるか、null（全サイト対象）のものを表示
- 読み取り専用表示（編集はRulesページへ誘導）

---

## FR-6: 違反カテゴリバッジ（dark_pattern_category）

**対象ファイル:** `Alerts.tsx`, `AlertTab.tsx`
**バックエンドAPI:** 既存 `GET /api/alerts/` （レスポンスに `dark_pattern_category` 追加必要）
**優先度:** 🟡 中

### Before
```
┌──────────────────────────────────────────┐
│ [緊急] [契約違反]                         │
│ サイトA                                   │
│ price_mismatch                            │
│ 価格が契約と一致しません                   │
│                                           │
│ （ダークパターンカテゴリ表示なし）          │
└──────────────────────────────────────────┘
```

### After
```
┌──────────────────────────────────────────────────┐
│ [緊急] [契約違反] [🎭 hidden_subscription]  ← 新規│
│ サイトA                                           │
│ price_mismatch                                    │
│ 価格が契約と一致しません                           │
│                                                   │
│ ダークパターン分類:                                │
│  🔴 hidden_subscription（隠れサブスクリプション）   │
│  確信度: 0.85                                     │
└──────────────────────────────────────────────────┘
```

### 実装要件
- `Alert` 型に `dark_pattern_category?: string`, `dark_pattern_confidence?: number` 追加
- アラートカードのヘッダーバッジ列に `dark_pattern_category` Badge 追加
- カテゴリ別色分け:
  - visual_deception → 紫
  - hidden_subscription → 赤
  - confirmshaming → オレンジ
  - hidden_fees → 赤
  - urgency_pattern → 黄
  - その他 → グレー
- アラートフィルターに「ダークパターンカテゴリ」Select 追加
- `alertTypeFilterOptions` に `dark_pattern` 選択肢追加

---

## FR-7: ジャーニースクリプトGUIエディタ

**対象ファイル:** 新規 `JourneyScriptEditor.tsx`（サイト設定内）
**バックエンドAPI:** `PUT /api/sites/{site_id}` （journey_script フィールド追加）
**優先度:** 🟢 低（Phase 2）

### Before
```
（ジャーニースクリプトの設定UIなし。
  バックエンドのみで定義、フロントから設定不可）
```

### After
```
┌──────────────────────────────────────────────────┐
│ 🛡️ ダークパターン                                 │
│                                                   │
│  [スコア概要] [スコア推移] [適用ルール]             │
│  [🗺️ ジャーニー設定]  ← 新規サブタブ               │
│                                                   │
│  ユーザージャーニースクリプト:                       │
│  ┌──────────────────────────────────────────┐    │
│  │ STEP 1: navigate "https://example.com"   │    │
│  │ STEP 2: click "カートに追加"              │    │
│  │ STEP 3: wait 2000                        │    │
│  │ STEP 4: click "購入手続きへ"              │    │
│  │ STEP 5: assert_visible "合計金額"         │    │
│  │ STEP 6: assert_not_visible "隠れ手数料"   │    │
│  └──────────────────────────────────────────┘    │
│                                                   │
│  利用可能なコマンド:                                │
│  navigate, click, wait, assert_visible,            │
│  assert_not_visible, fill, scroll                  │
│                                                   │
│  [バリデーション] [保存]                            │
└──────────────────────────────────────────────────┘
```

### 実装要件
- `DarkPatternTab.tsx` 内に4番目のサブタブ「ジャーニー設定」追加
- `<textarea>` ベースのスクリプトエディタ（シンタックスハイライトは Phase 2+）
- コマンドリファレンス表示
- クライアントサイドバリデーション（各行が有効なコマンドか）
- 保存時にサイト設定として `journey_script` を PUT

---

## FR-8: ダッシュボード統合（スコア分布・高リスクアラート・カテゴリトレンド）

**対象ファイル:** `Dashboard.tsx`
**バックエンドAPI:** `GET /api/monitoring/statistics` （レスポンス拡張必要）
**優先度:** 🟡 中

### Before
```
┌─────────────────────────────────────────────┐
│ 統計ダッシュボード                            │
│                                              │
│  [監視サイト数] [違反数] [成功率]             │
│  [最終クロール] [偽サイト検知]                │
│                                              │
│  📈 違反数の推移（折れ線グラフ）              │
│                                              │
│  （ダークパターン関連の統計なし）              │
└─────────────────────────────────────────────┘
```

### After
```
┌──────────────────────────────────────────────────────┐
│ 統計ダッシュボード                                    │
│                                                       │
│  [監視サイト数] [違反数] [成功率]                     │
│  [最終クロール] [偽サイト検知]                         │
│  [🛡️ 高リスクサイト] [🎭 DP検出数]  ← 新規カード2枚  │
│                                                       │
│  📈 違反数の推移                                      │
│                                                       │
│  --- 新規セクション ---                                │
│  🛡️ ダークパターンスコア分布                           │
│  ┌──────────────────────────────────────┐             │
│  │  低リスク(0-0.3)  ████████████  12   │             │
│  │  中リスク(0.3-0.6) ██████       6    │             │
│  │  高リスク(0.6-1.0) ███          3    │             │
│  └──────────────────────────────────────┘             │
│                                                       │
│  🎭 カテゴリ別検出トレンド（直近7日）                   │
│  ┌──────────────────────────────────────┐             │
│  │  hidden_subscription  ████████  8    │             │
│  │  visual_deception     ██████    6    │             │
│  │  confirmshaming       ████      4    │             │
│  │  hidden_fees          ██        2    │             │
│  └──────────────────────────────────────┘             │
└──────────────────────────────────────────────────────┘
```

### 実装要件
- `Statistics` 型に追加:
  ```typescript
  dark_pattern_high_risk_count: number;
  dark_pattern_detection_count: number;
  dark_pattern_score_distribution: {
    low: number;    // 0-0.3
    medium: number; // 0.3-0.6
    high: number;   // 0.6-1.0
  };
  dark_pattern_category_counts: Record<string, number>;
  ```
- ダッシュボードに統計カード2枚追加（高リスクサイト数、DP検出数）
- スコア分布の横棒グラフ（Chart.js `Bar` horizontal）
- カテゴリ別検出数の横棒グラフ
- バックエンド `GET /api/monitoring/statistics` のレスポンス拡張が前提

---

## FR-9: ダークサイト候補サイト確認UI（URL・コンテンツプレビュー）

**対象ファイル:** `DarkPatternTab.tsx`（FR-1内に統合）, 新規 `DarksitePreviewPanel.tsx`
**バックエンドAPI:** `GET /api/sites/{site_id}/darksites`（新規API必要）, `GET /api/darksites/{id}/content`（新規API必要）
**優先度:** 🔴 高

### Before
```
┌──────────────────────────────────────────────────┐
│ 🛡️ ダークパターン                                 │
│                                                   │
│  [スコア概要] [スコア推移] [適用ルール]             │
│                                                   │
│  （ダークサイト候補の表示なし。                     │
│    偽サイト検知ページにドメイン類似度のみ表示。      │
│    候補URLの実コンテンツ確認手段なし）               │
└──────────────────────────────────────────────────┘
```

### After
```
┌──────────────────────────────────────────────────────────┐
│ 🛡️ ダークパターン                                        │
│                                                           │
│  [スコア概要] [スコア推移] [適用ルール]                    │
│  [🌐 ダークサイト候補]  ← 新規サブタブ                     │
│                                                           │
│  ダークサイト候補一覧（3件検出）                            │
│                                                           │
│  ┌────────────────────────────────────────────────────┐   │
│  │ 🔴 fake-shop-example.com          リスク: 0.92     │   │
│  │    マッチ種別: typosquat                            │   │
│  │    ドメイン類似度: 0.95  コンテンツ類似度: 0.88      │   │
│  │    検出日: 2026-04-05 10:30                         │   │
│  │    ステータス: 到達可能 (HTTP 200)                   │   │
│  │                                                     │   │
│  │    [コンテンツ確認 ▼]                                │   │
│  │    ┌─────────────────────────────────────────────┐  │   │
│  │    │ 📄 テキスト比較                              │  │   │
│  │    │ ┌──────────────┐  ┌──────────────┐          │  │   │
│  │    │ │ 正規サイト     │  │ 候補サイト     │          │  │   │
│  │    │ │ 商品A ¥1,000  │  │ 商品A ¥980    │          │  │   │
│  │    │ │ 送料無料      │  │ 送料無料      │          │  │   │
│  │    │ │ 30日返品可    │  │ 返品不可      │ ← 差異  │  │   │
│  │    │ └──────────────┘  └──────────────┘          │  │   │
│  │    │                                              │  │   │
│  │    │ 🖼️ 画像比較                                  │  │   │
│  │    │ ┌──────────────┐  ┌──────────────┐          │  │   │
│  │    │ │ [正規画像]     │  │ [候補画像]     │          │  │   │
│  │    │ │ pHash一致度:   │  │ 92%           │          │  │   │
│  │    │ └──────────────┘  └──────────────┘          │  │   │
│  │    │                                              │  │   │
│  │    │ 📋 契約条件の乖離:                            │  │   │
│  │    │  ⚠️ 返品ポリシー: 正規=30日返品可 / 候補=返品不可│ │   │
│  │    │  ⚠️ 価格差異: ¥1,000 → ¥980 (-2%)            │  │   │
│  │    │                                              │  │   │
│  │    │ 一致商品:                                     │  │   │
│  │    │  商品A (テキスト類似度: 0.91, 画像pHash: 92%) │  │   │
│  │    └─────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────┘   │
│                                                           │
│  ┌────────────────────────────────────────────────────┐   │
│  │ 🟡 shop-examp1e.com               リスク: 0.65     │   │
│  │    マッチ種別: homoglyph                            │   │
│  │    ドメイン類似度: 0.80  コンテンツ類似度: 0.50      │   │
│  │    ステータス: 到達可能 (HTTP 200)                   │   │
│  │    [コンテンツ確認 ▼]                                │   │
│  └────────────────────────────────────────────────────┘   │
│                                                           │
│  ┌────────────────────────────────────────────────────┐   │
│  │ ⚪ shop-example.net                リスク: 0.30     │   │
│  │    マッチ種別: tld_swap                             │   │
│  │    ステータス: 到達不可                              │   │
│  └────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

### 実装要件
- `DarkPatternTab.tsx` 内に新規サブタブ「ダークサイト候補」追加
- 新規 `DarksitePreviewPanel.tsx` コンポーネント作成
- 候補一覧表示:
  - 候補ドメイン、マッチ種別（typosquat/subdomain/homoglyph/tld_swap）
  - ドメイン類似度・コンテンツ類似度（overall_similarity）
  - HTTP到達可能性（is_reachable, http_status）
  - リスクスコア色分け: 0-0.3=グレー, 0.3-0.6=黄, 0.6-1.0=赤
- コンテンツ確認パネル（アコーディオン展開）:
  - テキスト比較: 正規サイト vs 候補サイトの商品テキストを左右並列表示
  - 画像比較: pHash一致度付きで正規/候補の商品画像をサムネイル表示
  - 契約条件の乖離リスト（`contract_discrepancies`）
  - 一致商品リスト（`matched_products` — テキスト類似度・画像pHash付き）
- 新規バックエンドAPI必要:
  - `GET /api/sites/{site_id}/darksites` — サイトに関連するダークサイト候補一覧
    - レスポンス: `DarksiteListResponse` （DomainMatch + ContentMatch の統合ビュー）
  - `GET /api/darksites/{id}/content` — 候補サイトの詳細コンテンツ比較データ
    - レスポンス: テキスト比較、画像比較、契約乖離、一致商品
- `api.ts` に型定義追加:
  ```typescript
  interface DarksiteCandidate {
    id: number;
    site_id: number;
    candidate_domain: string;
    legitimate_domain: string;
    match_type: 'typosquat' | 'subdomain' | 'homoglyph' | 'tld_swap';
    domain_similarity_score: number;
    content_similarity_score: number;
    overall_similarity: number;
    is_reachable: boolean;
    http_status: number | null;
    risk_score: number;
    detected_at: string;
  }

  interface DarksiteContentComparison {
    candidate_id: number;
    source_url: string;
    target_url: string;
    text_comparison: {
      source_text: string;
      target_text: string;
      text_similarity: number;
    };
    image_comparison: {
      source_images: string[];  // URLs
      target_images: string[];  // URLs
      image_similarity: number;
    };
    matched_products: Array<{
      product_name: string;
      text_similarity: number;
      image_similarity: number;
    }>;
    contract_discrepancies: Array<{
      field: string;
      legitimate_value: string;
      candidate_value: string;
      severity: 'high' | 'medium' | 'low';
    }>;
  }
  ```
- `api.ts` に API関数追加:
  ```typescript
  getDarksiteCandidates(siteId: number): Promise<DarksiteCandidate[]>
  getDarksiteContent(candidateId: number): Promise<DarksiteContentComparison>
  ```

---

## api.ts 追加型定義・関数まとめ

### 新規型定義
```typescript
// Dark Pattern Detection
interface DarkPatternResult {
  site_id: number;
  verification_result_id: number;
  dark_pattern_score: number | null;
  dark_pattern_subscores: Record<string, number> | null;
  dark_pattern_types: Record<string, any> | null;
  detected_at: string;
}

interface DarkPatternHistoryItem {
  verification_result_id: number;
  dark_pattern_score: number | null;
  dark_pattern_subscores: Record<string, number> | null;
  dark_pattern_types: Record<string, any> | null;
  detected_at: string;
}

interface DarkPatternHistoryResponse {
  site_id: number;
  results: DarkPatternHistoryItem[];
  total: number;
  limit: number;
  offset: number;
}

// Dynamic LLM Rules
interface DynamicRule {
  id: number;
  rule_name: string;
  description: string | null;
  prompt_template: string;
  severity: 'critical' | 'warning' | 'info';
  dark_pattern_category: string;
  confidence_threshold: number;
  applicable_categories: string[] | null;
  applicable_site_ids: number[] | null;
  is_active: boolean;
  execution_order: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

interface DynamicRuleCreate {
  rule_name: string;
  description?: string;
  prompt_template: string;
  severity?: 'critical' | 'warning' | 'info';
  dark_pattern_category?: string;
  confidence_threshold?: number;
  applicable_categories?: string[];
  applicable_site_ids?: number[];
  execution_order?: number;
  created_by: string;
}

interface DynamicRuleUpdate {
  description?: string;
  prompt_template?: string;
  severity?: 'critical' | 'warning' | 'info';
  dark_pattern_category?: string;
  confidence_threshold?: number;
  applicable_categories?: string[];
  applicable_site_ids?: number[];
  is_active?: boolean;
  execution_order?: number;
}

// Darksite Candidates (FR-9)
interface DarksiteCandidate {
  id: number;
  site_id: number;
  candidate_domain: string;
  legitimate_domain: string;
  match_type: 'typosquat' | 'subdomain' | 'homoglyph' | 'tld_swap';
  domain_similarity_score: number;
  content_similarity_score: number;
  overall_similarity: number;
  is_reachable: boolean;
  http_status: number | null;
  risk_score: number;
  detected_at: string;
}

interface DarksiteContentComparison {
  candidate_id: number;
  source_url: string;
  target_url: string;
  text_comparison: {
    source_text: string;
    target_text: string;
    text_similarity: number;
  };
  image_comparison: {
    source_images: string[];
    target_images: string[];
    image_similarity: number;
  };
  matched_products: Array<{
    product_name: string;
    text_similarity: number;
    image_similarity: number;
  }>;
  contract_discrepancies: Array<{
    field: string;
    legitimate_value: string;
    candidate_value: string;
    severity: 'high' | 'medium' | 'low';
  }>;
}
```

### 新規API関数
```typescript
// FR-1: ダークパターンスコア取得
getDarkPatterns(siteId: number): Promise<DarkPatternResult | null>

// FR-2: スコア履歴取得
getDarkPatternHistory(siteId: number, limit?: number, offset?: number): Promise<DarkPatternHistoryResponse>

// FR-4: 動的LLMルールCRUD
getDynamicRules(): Promise<DynamicRule[]>
createDynamicRule(data: DynamicRuleCreate): Promise<DynamicRule>
updateDynamicRule(id: number, data: DynamicRuleUpdate): Promise<DynamicRule>
deleteDynamicRule(id: number): Promise<void>

// FR-9: ダークサイト候補
getDarksiteCandidates(siteId: number): Promise<DarksiteCandidate[]>
getDarksiteContent(candidateId: number): Promise<DarksiteContentComparison>
```

### 既存型の拡張
```typescript
// Site型に追加
Site.merchant_category?: string;

// Alert型に追加
Alert.dark_pattern_category?: string;
Alert.dark_pattern_confidence?: number;

// Statistics型に追加
Statistics.dark_pattern_high_risk_count?: number;
Statistics.dark_pattern_detection_count?: number;
Statistics.dark_pattern_score_distribution?: { low: number; medium: number; high: number };
Statistics.dark_pattern_category_counts?: Record<string, number>;
```

---

## サイドバーナビゲーション変更

**対象ファイル:** `AppLayout.tsx`

### 変更なし
既存の「チェックルール」(`/rules`) ナビゲーション項目をそのまま利用。
FR-4 で `Rules.tsx` 内にタブ切替（ビルトイン / LLMルール）を追加するため、
新規サイドバー項目の追加は不要。

---

## 実装優先度まとめ

| 優先度 | FR | 内容 | 依存 |
|--------|-----|------|------|
| 🔴 高 | FR-1 | ダークパターンスコア表示 | バックエンドAPI済 |
| 🔴 高 | FR-4 | LLMルール管理CRUD | バックエンドCRUD API新規必要 |
| 🔴 高 | FR-9 | ダークサイト候補確認UI | バックエンドAPI新規必要 |
| 🟡 中 | FR-2 | スコア履歴チャート | FR-1, バックエンドAPI済 |
| 🟡 中 | FR-3 | 加盟店カテゴリ設定 | バックエンドフィールド追加 |
| 🟡 中 | FR-6 | 違反カテゴリバッジ | バックエンドレスポンス拡張 |
| 🟡 中 | FR-8 | ダッシュボード統合 | バックエンド統計API拡張 |
| 🟢 低 | FR-5 | サイト別ルール表示 | FR-4 |
| 🟢 低 | FR-7 | ジャーニーエディタ | Phase 2 |

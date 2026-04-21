# Topic: Dark Pattern Detection — ダークパターン検知

## Timeline

### 2026-03-26
- advanced-dark-pattern-detection spec の requirements.md を作成（14要件）
- 4つの検知アプローチを定義:
  1. CSSVisualPlugin: コントラスト比（WCAG 2.0）、フォントサイズ異常、CSS隠蔽6パターン
  2. LLMClassifierPlugin: Gemini/Claude/GPT-4o対応、Vision API、レート制限・コスト制御
  3. JourneyPlugin: カート追加後チェック、チェックアウトポップアップ、DOM差分比較
  4. UITrapPlugin: Sneak into Basket、デフォルト定期購入、コンファームシェイミング日英辞書
- DarkPatternScore: 4サブスコアの加重統合（CSS 0.25, LLM 0.30, Journey 0.25, UI Trap 0.20）
- 別specとして管理する方針を決定（crawl-pipeline-architectureとは関心の分離）
- 次ステップ: design.md → tasks.md 作成
  - 関連: sessions/2026-03-26-plugins-and-specs.md

### 2026-03-28
- CTOレビューによる5つのアーキテクチャ安全設計修正をrequirements.mdに適用:
  1. CSSVisualPlugin: 要素ごとgetComputedStyleループ禁止 → 単一page.evaluate一括計算+1回RPC
  2. LLMClassifierPlugin: 先頭切り捨て禁止 → Middle-Out Truncation（上部20%+下部30%保持）
  3. JourneyPlugin: 生HTML差分禁止 → Playwright locator+isVisible可視要素トラッキング
  4. JourneyPlugin: セレクタ未検出時のget_by_roleヒューリスティック・フォールバック追加
  5. DarkPatternScore: 加重平均+未実行除外禁止 → Max Pooling+ペナルティベースライン(0.15)
- アーキテクチャ安全設計レポートを出力（RPC最適化、Middle-Out、ノイズ排除、スコアリング戦略）
- 次ステップ: design.md作成
  - 関連: sessions/2026-03-28-cto-override-review.md

### 2026-03-31
- 既存コードベースの検出ロジック包括監査を実施
- 現状の検出能力: 価格抽出（JSON-LD/Microdata/OG/HTML/OCR）→ 契約比較 → アラート/通知
- specカバー外の6つの検出ギャップを特定:
  1. Price Bait-and-Switch（クロール前後の価格操作）
  2. 解約導線の機能検証（リンク先有効性）
  3. 税込/税抜表示の欺瞞（コンテキスト判定なし）
  4. 偽の緊急性パターン（カウントダウン/残数）
  5. dark_pattern_type分類体系の未定義（LLM自由テキスト問題）
  6. クロスプラグイン相関（複合パターンの重み付けなし）
- 優先度高: #5（分類体系）と #4（偽の緊急性）
- 判断待ち: spec拡張するか現状スコープで実装に進むか
  - 関連: sessions/2026-03-31-detection-logic-audit.md

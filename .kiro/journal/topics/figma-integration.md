# Topic: Figma Integration — Figma連携

## Timeline

### 2026-03-26
- Figma Power を有効化、利用可能ツールを確認
- 空のFigmaファイル（KG2LaCI0AiUBv3ufP6txuY）への連携を試みるも、Figma Powerはデザイン→コード方向のみで、コード→Figma書き出しは非対応と判明
- 代替としてFigJamのgenerate_diagramツールでMermaid記法からアーキテクチャ図を生成
- 生成した図（7枚）:
  1. Crawl Pipeline Architecture（全体構成）
  2. Celery Queue Separation（4キュー分離）
  3. BrowserPool Architecture（プール管理）
  4. Plugin Config 3-Layer Merge（設定マージ）
  5. CrawlPipeline State Flow（状態遷移）
  6. DB Schema - Entity Relationships（ER図）
  7. Frontend Component Architecture（React構成）
- 今後: Figmaにデザインコンポーネントが追加されたらCode Connect連携を検討
  - 関連: sessions/2026-03-26-figma.md

### 2026-04-14

- **Kiro → Figma 連携方法確定**: `generate_figma_design` ツールで `localhost:5173` の各ページを直接 Figma にキャプチャ送信できることを確認。Figma アカウント（Pro プラン、team key: `team::1254317544677975050`）確認済み。
- 対象12ページ: ダッシュボード・サイト管理・アラート・偽サイト検知・契約条件・チェックルール・顧客・カテゴリ・審査キュー・審査ダッシュボード・ユーザ管理・ログイン
- 実際のキャプチャ実行は次セッションへ持ち越し
- 関連セッション: sessions/2026-04-14-1500.md

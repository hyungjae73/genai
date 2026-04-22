# Topic: Decisions — 意思決定履歴

## Timeline

### 2026-03-26

- **JSON型をJSONBの代わりに使用**: SQLiteテスト互換性のため。本番PostgreSQLではJSONBとして動作。
  - 関連: sessions/2026-03-26-initial.md

- **BrowserPoolにplaywright_launcher注入パターン採用**: Playwrightがインストールされていないテスト環境でもモック可能にするため。TYPE_CHECKINGでの遅延インポートと組み合わせ。
  - 関連: sessions/2026-03-26-initial.md

- **LocalePluginはctx.metadataに設定格納**: ブラウザページのライフサイクルはPageFetcherステージが管理。プラグインは設定値の提供のみ担当する分離設計。
  - 関連: sessions/2026-03-26-initial.md

- **Figma Powerはデザイン→コード方向のみ**: コードからFigmaへの書き出しは非対応。アーキテクチャ図はFigJamのgenerate_diagram（Mermaid記法）で代替。
  - 関連: sessions/2026-03-26-figma.md

- **通知機能は別spec（dark-pattern-notification）として設計**: crawl-pipeline-architectureのAlertPluginの後にNotificationPluginとして統合。Slack Webhook + Customer.email宛SMTPの2チャネル。重複通知は24時間窓で抑制。Celery非同期タスクでパイプラインをブロックしない。
  - 関連: sessions/2026-03-26-review.md

- **specは先に作成、実装はパイプライン完了後**: dark-pattern-notification specを先行作成し、crawl-pipeline-architectureのタスク実行を優先する方針。
  - 関連: sessions/2026-03-26-review.md

- **ジャーナルは2軸で管理**: sessions/（日付時間軸）+ topics/（テーマ別）。agentStop hookで自動記録、steering auto inclusionで毎セッション読み込み。
  - 関連: sessions/2026-03-26-journal-setup.md

- **プロダクト憲法をsteering auto inclusionで管理**: 3つの不可侵原則 — (1) 非同期UX: ローディングスピナー禁止、task_id+ポーリング必須 (2) 証拠保全: MinIO保存必須、react-zoom-pan-pinchビューア必須 (3) エラーハンドリング: 画面クラッシュ禁止、Error Boundary 2層、4xx/5xx分離
  - 関連: sessions/2026-03-26-product-constitution.md

- **アーキテクチャ憲法をsteering auto inclusionで管理**: 3つの不可侵原則 — (1) Celeryキュー4分離厳格化: crawl/extract/validate/reportの混同禁止 (2) フロントエンドFeature-Sliced Design: pages/features/components/ui/apiの責務分離 (3) psycopg2-binary同期/非同期境界防御: async def+直接DBアクセス禁止
  - 関連: sessions/2026-03-26-architecture-constitution.md

- **技術・コード憲法をsteering auto inclusionで管理**: 4つの不可侵原則 — (1) PBT強制: Hypothesis+fast-check (2) any禁止+React 19新フック活用 (3) Pydantic V1メソッド禁止+SQLAlchemy 2.0 mapped_column必須 (4) with句/try-finallyによるリソース管理必須
  - 関連: sessions/2026-03-26-tech-constitution.md

- **Powers/MCPスキル強化の優先度**: DB直接操作MCP（高）→ キーワード駆動ドメイン知識（高）→ インフラ操作統合（中）。DB MCPはPostgreSQL MCP Server、ドメイン知識はsteering fileMatchで実現
  - 関連: sessions/2026-03-26-powers-mcp-discussion.md

- **SQLiteテストDB→testcontainers-python移行推奨**: JSONB非対応・インデックス差異・タイムスタンプ精度が限界。次のDB変更（advanced-dark-pattern-detection）時に合わせて実施が効率的
  - 関連: sessions/2026-03-26-sqlite-evaluation.md

- **testcontainers-pythonが理想、2層テスト構成採用**: ユニット/PBT→testcontainers（scope=session、rollback分離）、E2E→docker-compose profile（将来追加）。conftest.py変更のみで既存446テスト互換
  - 関連: sessions/2026-03-27-testcontainers-decision.md

- **フルCQRS不採用、マテリアライズドビューで将来対応**: 読み書き負荷比率が極端でなく、クエリも複雑でなく、結果整合性許容ユースケースが少ない。DarkPatternScore集計が重くなった場合にPostgreSQLマテリアライズドビューで対応
  - 関連: sessions/2026-03-27-cqrs-evaluation.md

- **advanced-dark-pattern-detectionは別specで管理**: crawl-pipeline-architectureはインフラ層、検知ロジックはアプリケーション層で関心が異なる。LLM連携は外部API依存があり独立イテレーション必要。4アプローチを段階的リリース可能。
  - 関連: sessions/2026-03-26-plugins-and-specs.md

- **DarkPatternScoreの加重配分**: CSS Visual 0.25、LLM 0.30、Journey 0.25、UI Trap 0.20。LLMのセマンティック分析を最重視。
  - 関連: sessions/2026-03-26-plugins-and-specs.md

### 2026-03-27

- **pytest filterwarnings = error を基盤設定として強制**: Zero Warning Policyをpytest.iniレベルで実装。サードパーティWarningはホワイトリスト方式で除外。error設定の削除・無効化は禁止。
  - 関連: sessions/2026-03-27-steering-constitution.md

- **urllib3 Warningはメッセージパターンで除外**: クラス名指定（`ignore::urllib3.exceptions.NotOpenSSLWarning`）はimport時にWarningが発火してクラス解決自体が失敗するため、`ignore:urllib3 v2 only supports OpenSSL:Warning`方式を採用。
  - 関連: sessions/2026-03-27-steering-constitution.md

- **workflow.md（開発プロセス憲法）新設**: ボーイスカウトの規則（既存負債の修正義務）、全体影響把握（既存バグ顕在化時のRCA義務）、負債タスク化提案（巨大リファクタのエスカレーション義務）の3原則。
  - 関連: sessions/2026-03-27-steering-constitution.md

- **JSONB数値正規化への対応方針**: PostgreSQLのJSONBは大きなfloat値を内部的にintとして正規化する仕様。テストの等価比較を`==`から再帰的数値等価比較に変更。テスト改ざんではなくPostgreSQLの仕様に合わせた正しい等価性定義。
  - 関連: sessions/2026-03-27-property-tests-complete.md

### 2026-03-31

- **検出の2軸分離（ドメイン知識）**: システムの検出は「契約違反検出」と「Darksite検出」の2つの独立した軸。契約違反は加盟店の商品特性により検出項目が異なり動的拡張が必要。Darksiteは類似ドメイン・契約外コンテンツ・契約偽りの3要素。現状: 軸1=ContractComparisonPlugin+advanced-dark-pattern-detection、軸2=fake-site-detection-alert。
  - 関連: sessions/2026-03-31-domain-knowledge-two-axes.md
  - 判断待ち: 検出ルール拡張性の設計を現specに組み込むか別specとして切り出すか

- **Hybrid Rule Engine（CTO指令）**: Pythonファイル依存を脱却。Built-in Rules + Dynamic LLM Rules（DB自然言語プロンプト）の2層。コンプライアンス担当者がコード変更ゼロでルール追加可能。
  - 関連: sessions/2026-03-31-cto-architecture-review.md

- **TF-IDF全廃（CTO指令）**: テキストSpinning対策として all-MiniLM-L6-v2 Dense Vector に置換。コサイン類似度 >= 0.85 で高類似判定。
  - 関連: sessions/2026-03-31-cto-architecture-review.md

- **ContentFingerprint爆発防止（CTO指令）**: is_canonical_product=True のみ保存、max_fingerprints_per_site=50、TTL 90日自動削除。
  - 関連: sessions/2026-03-31-cto-architecture-review.md

### 2026-04-07
- **競合差分分析実施**: SecondXight Analytica社の加盟店審査システム提案資料と現状システムを比較。11項目の機能ギャップを特定。
- **P0ギャップ**: ユーザ管理・権限管理（認証/RBAC完全欠落）、手動審査ワークフロー（二次判定・承認フロー欠落）
- **P1ギャップ**: 外部データ連携I/F（申込受付WebAPI）、反社・ネガ情報チェック（JDM照会・独自ネガDB）
- **P2ギャップ**: 風評検索、住所・法人情報収集、シミュレーション、類似度チェック（重複加盟店検出）
- **P3ギャップ**: URL自動判定、CSV/BI連携、商材資料自動チェック
  - 関連: sessions/2026-04-07-competitor-gap-analysis.md

### 2026-04-08
- **フロントエンド未カバー要件の所属先確定**: dark-pattern-frontendのスコープは「ダークパターン検出UI」に限定維持。パスワード変更/エラーページ/監査ログUIはuser-auth-rbacに追記。通知設定UI/契約動的フォーム/スケジュール拡張は各親specまたは新規specとして扱う。
  - 関連: sessions/2026-04-08-frontend-gap-resolution.md

### 2026-04-13

- **dynamic-contract-form: dynamic_fields はモデルカラム追加なし**: ContractCondition の既存 JSONB フィールドを活用。DB スキーマ変更・Alembic マイグレーション不要。category_id は既に models.py に存在していたため schemas.py への追加のみで対応。
  - 関連: sessions/2026-04-13-1600.md

- **テスト認証バイパスは X-API-Key ヘッダーで統一**: `get_current_user_or_api_key` の legacy API key パスを活用。conftest.py の client fixture と TestClient 生成箇所に `headers={"X-API-Key": "dev-api-key"}` を追加するだけで全テストに適用可能。dependency override より侵襲性が低い。
  - 関連: sessions/2026-04-13-1700.md

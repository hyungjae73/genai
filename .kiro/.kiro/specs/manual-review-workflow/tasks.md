# 実装計画: 手動審査ワークフロー (manual-review-workflow)

## 概要

自動検出でNGとなった案件を審査キューに自動投入し、一次審査（reviewer）→ 二次審査（admin）の二段階承認フローを実装する。バックエンド基盤（モデル・状態遷移マシン）→ サービス層 → API → 既存システム統合 → フロントエンドの順に段階的に構築する。

前提: user-auth-rbac spec（reviewer/admin ロール）が実装済みであること。

## タスク

- [x] 1. ReviewItem / ReviewDecision モデルと Alembic マイグレーション
  - [x] 1.1 ReviewItem モデルを `genai/src/models.py` に追加
    - review_items テーブル: id, alert_id (FK→alerts), site_id (FK→monitoring_sites), review_type, status (default="pending"), priority, assigned_to (nullable), created_at, updated_at
    - Alert, MonitoringSite へのリレーションシップ、ReviewDecision への cascade リレーションシップ
    - status, priority, alert_id (unique), site_id, assigned_to, 複合インデックス (status, priority, created_at) を設定
    - _要件: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 1.2 ReviewDecision モデルを `genai/src/models.py` に追加
    - review_decisions テーブル: id, review_item_id (FK→review_items), reviewer_id, decision, comment (Text, NOT NULL), review_stage, decided_at
    - ReviewItem への back_populates リレーションシップ
    - review_item_id, reviewer_id にインデックスを設定
    - _要件: 5.1, 5.5_

  - [x] 1.3 Alembic マイグレーションファイルを作成
    - `genai/alembic/versions/p1q2r3s4t5u6_add_review_items_and_decisions.py`
    - review_items テーブルと review_decisions テーブルの作成、外部キー制約、インデックス
    - downgrade で両テーブルを drop
    - _要件: 1.1, 1.4, 1.5, 1.6, 5.1_

- [x] 2. ReviewStateMachine（状態遷移マシン）
  - [x] 2.1 `genai/src/review/state_machine.py` を作成
    - VALID_TRANSITIONS dict: pending→{in_review}, in_review→{approved, rejected, escalated}, escalated→{approved, rejected}, approved→set(), rejected→set()
    - validate_transition(current, new) → bool
    - get_allowed_transitions(current) → set[str]
    - is_terminal_state(status) → bool
    - _要件: 10.1, 10.2, 10.3, 10.5_

  - [ ]* 2.2 状態遷移の不変条件プロパティテスト（Hypothesis）
    - **Property 1: 有効な遷移の閉包性** — validate_transition が True を返す (current, new) ペアは VALID_TRANSITIONS に定義されたもののみ
    - **検証対象: 要件 10.6**

  - [ ]* 2.3 最終状態の不変条件プロパティテスト（Hypothesis）
    - **Property 2: 最終状態からの遷移不可** — is_terminal_state が True のステータスに対して、get_allowed_transitions は空集合を返す
    - **検証対象: 要件 10.5**

  - [ ]* 2.4 不正遷移の拒否プロパティテスト（Hypothesis）
    - **Property 3: 不正遷移の拒否** — VALID_TRANSITIONS に定義されていない (current, new) ペアに対して validate_transition は False を返す
    - **検証対象: 要件 10.4, 10.6**

- [ ] 3. チェックポイント - モデルと状態遷移マシンの検証
  - すべてのテストが通ることを確認し、不明点があればユーザに質問する。

- [x] 4. ReviewService（ビジネスロジック層）
  - [x] 4.1 `genai/src/review/service.py` に ReviewService クラスを作成
    - __init__(self, db: Session) で AuditLogger を初期化
    - _要件: 全般_

  - [x] 4.2 自動投入メソッドを実装
    - enqueue_from_alert(alert): Alert の severity が critical/high/medium の場合に ReviewItem を作成。alert_type が fake_site なら priority を "critical" に上書き。同一 alert_id の重複チェック
    - enqueue_from_dark_pattern(site_id, alert, score): dark_pattern_score >= 0.7 の場合に review_type="dark_pattern" で ReviewItem を作成
    - SEVERITY_TO_PRIORITY マッピングによる priority 自動設定
    - _要件: 2.1, 2.2, 2.3, 2.4, 2.5, 1.3_

  - [ ]* 4.3 自動投入のプロパティテスト（Hypothesis）
    - **Property 4: 重複投入の防止** — 同一 alert_id で enqueue_from_alert を2回呼んでも ReviewItem は1件のみ
    - **検証対象: 要件 2.5**

  - [ ]* 4.4 Priority マッピングのプロパティテスト（Hypothesis）
    - **Property 5: fake_site の priority 上書き** — alert_type が "fake_site" の場合、生成される ReviewItem の priority は常に "critical"
    - **検証対象: 要件 2.4**

  - [x] 4.5 一次審査メソッドを実装
    - assign_reviewer(review_item_id, reviewer_id, username): status を pending→in_review に遷移、assigned_to を設定、AuditLog 記録
    - decide_primary(review_item_id, decision, comment, reviewer_id, username): in_review から approved/rejected/escalated に遷移、ReviewDecision (review_stage="primary") を作成、AuditLog 記録
    - 不正な状態遷移時は HTTP 409 を返す
    - _要件: 3.5, 3.7, 3.8, 3.9, 3.10, 3.11, 5.2, 5.3_

  - [x] 4.6 二次審査メソッドを実装
    - decide_secondary(review_item_id, decision, comment, reviewer_id, username): escalated から approved/rejected に遷移、ReviewDecision (review_stage="secondary") を作成、AuditLog 記録
    - status が escalated 以外の場合は HTTP 409 を返す
    - _要件: 4.3, 4.4, 4.5, 4.6, 5.2, 5.3_

  - [x] 4.7 クエリメソッドを実装
    - list_reviews(status, priority, review_type, assigned_to, limit, offset): フィルタリング + ソート (priority DESC, created_at ASC) + ページネーション
    - get_review_detail(review_item_id): Alert + Violation + VerificationResult + MonitoringSite + Decisions の統合ビュー (JOIN クエリ)
    - get_stats(): by_status, by_priority (pending のみ), by_review_type (pending のみ)
    - get_escalated_reviews(limit, offset): escalated 案件一覧
    - _要件: 3.1, 3.2, 3.3, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.2, 8.3, 8.4, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 4.8 一次審査の状態遷移プロパティテスト（Hypothesis）
    - **Property 6: 一次審査は in_review 状態からのみ判定可能** — status が in_review 以外の ReviewItem に対して decide_primary は HTTP 409 を返す
    - **検証対象: 要件 3.11**

  - [ ]* 4.9 二次審査の状態遷移プロパティテスト（Hypothesis）
    - **Property 7: 二次審査は escalated 状態からのみ判定可能** — status が escalated 以外の ReviewItem に対して decide_secondary は HTTP 409 を返す
    - **検証対象: 要件 4.4**

- [ ] 5. チェックポイント - サービス層の検証
  - すべてのテストが通ることを確認し、不明点があればユーザに質問する。

- [x] 6. Reviews Router（API エンドポイント）
  - [x] 6.1 API スキーマを `genai/src/api/schemas.py` に追加
    - ReviewItemResponse, PaginatedReviewResponse, ReviewDecisionRequest, AssignReviewerRequest, ReviewDecisionResponse, ReviewDetailResponse, AlertDetailInReview, ViolationDetailInReview, DarkPatternDetailInReview, FakeSiteDetailInReview, SiteBasicInfo, ReviewStatsResponse
    - ReviewDecisionRequest.comment に min_length=1 バリデーション
    - _要件: 5.5, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x] 6.2 `genai/src/api/reviews.py` に Reviews Router を作成
    - GET / — 審査キュー一覧 (reviewer/admin)、status/priority/review_type/assigned_to フィルタ、limit/offset ページネーション
    - GET /stats — 審査統計 (viewer/reviewer/admin)
    - GET /escalated — エスカレーション案件一覧 (admin のみ)
    - GET /{review_id} — 審査案件詳細 (reviewer/admin)
    - POST /{review_id}/assign — 担当者割り当て (reviewer/admin)
    - POST /{review_id}/decide — 一次審査判定 (reviewer/admin)
    - POST /{review_id}/final-decide — 二次審査判定 (admin のみ)
    - GET /{review_id}/decisions — 判定履歴 (reviewer/admin)
    - 各エンドポイントで require_role による RBAC 制御
    - _要件: 3.1, 3.2, 3.4, 3.6, 4.1, 4.2, 4.7, 5.4, 7.1, 7.2, 7.3, 7.4, 7.6, 8.1, 8.5_

  - [x] 6.3 `genai/src/main.py` に Reviews Router を登録
    - `from src.api.reviews import router as reviews_router`
    - `app.include_router(reviews_router, prefix="/api/reviews", tags=["reviews"])`
    - _要件: 3.1, 4.1, 8.1_

  - [ ]* 6.4 API エンドポイントのユニットテスト
    - RBAC 制御テスト: reviewer が final-decide にアクセスすると 403
    - 不正遷移テスト: pending 状態の ReviewItem に decide すると 409
    - ページネーションテスト: limit/offset が正しく動作する
    - _要件: 4.7, 3.11, 7.6_

- [x] 7. 既存システム統合
  - [x] 7.1 Alert 作成フックの実装
    - `genai/src/api/alerts.py` の Alert 作成エンドポイントに ReviewService.enqueue_from_alert() 呼び出しを追加
    - severity が critical/high/medium の Alert 作成時に自動投入
    - 既存の Alert 作成フローへの影響を最小限にする（try-except でラップし、審査キュー投入失敗時もAlert作成は成功させる）
    - _要件: 2.1, 2.2_

  - [x] 7.2 ダークパターン検出フックの実装
    - `genai/src/api/verification.py` の VerificationResult 更新時に dark_pattern_score >= 0.7 なら ReviewService.enqueue_from_dark_pattern() を呼び出す
    - _要件: 2.3_

  - [x] 7.3 審査結果に基づく Alert 更新の実装
    - ReviewService の decide_primary / decide_secondary 内で、approved 時に Alert.is_resolved = True に更新
    - rejected 時は Alert.is_resolved = False のまま維持
    - _要件: 6.1, 6.2_

  - [x] 7.4 通知連携の実装
    - rejected 判定時に NotificationService で違反確定通知を送信
    - escalated 判定時に admin ロールのユーザにエスカレーション通知を送信
    - _要件: 6.3, 6.4_

  - [x] 7.5 監査ログ連携の確認
    - ReviewService の各操作（assign, decide_primary, decide_secondary）で AuditLogger.log() が正しく呼ばれることを確認
    - resource_type="review_item"、action="assign"/"decide"/"escalate" 等
    - _要件: 5.3_

  - [ ]* 7.6 統合テスト: Alert 作成 → 審査キュー自動投入 → 一次審査 → 二次審査の E2E フロー
    - Alert 作成から最終判定までの一連のフローをテスト
    - AuditLog が各ステップで記録されることを検証
    - _要件: 2.1, 3.5, 3.8, 4.5, 5.2, 5.3, 6.1_

- [ ] 8. チェックポイント - バックエンド全体の検証
  - すべてのテストが通ることを確認し、不明点があればユーザに質問する。

- [x] 9. フロントエンド: 型定義と API クライアント
  - [x] 9.1 `genai/frontend/src/types/review.ts` に審査関連の型定義を作成
    - ReviewItem, ReviewDecision, ReviewDetail, ReviewStats, PaginatedReviewResponse 等の TypeScript 型
    - _要件: 1.1, 5.1, 8.2_

  - [x] 9.2 `genai/frontend/src/services/api.ts` に審査 API クライアント関数を追加
    - fetchReviews, fetchReviewDetail, assignReviewer, decidePrimary, decideSecondary, fetchReviewStats, fetchEscalatedReviews, fetchDecisions
    - _要件: 3.1, 3.2, 3.4, 3.6, 4.1, 4.2, 5.4, 8.1_

- [x] 10. フロントエンド: 審査キュー一覧ページ
  - [x] 10.1 `genai/frontend/src/pages/Reviews.tsx` を作成
    - 審査キュー一覧テーブル（ReviewItem の status, priority, review_type, assigned_to, created_at を表示）
    - status / priority / review_type フィルタ（既存 Select コンポーネント使用）
    - ページネーション（limit/offset）
    - 各行クリックで審査案件詳細ページへ遷移
    - 既存の Card, Badge コンポーネントを再利用
    - _要件: 3.1, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 10.2 `genai/frontend/src/pages/Reviews.css` を作成
    - 審査キュー一覧のスタイル定義
    - _要件: 7.1_

- [x] 11. フロントエンド: 審査案件詳細ページ
  - [x] 11.1 `genai/frontend/src/pages/ReviewDetail.tsx` を作成
    - 審査案件の統合ビュー表示: Alert 詳細、Violation/DarkPattern/FakeSite 詳細、Site 基本情報
    - 過去の ReviewDecision 履歴表示
    - 担当者割り当てボタン（pending 状態時）
    - 一次審査判定フォーム（in_review 状態時）: approved/rejected/escalated 選択 + コメント入力
    - 二次審査判定フォーム（escalated 状態時、admin のみ）: approved/rejected 選択 + コメント入力
    - ステータスに応じたフォーム表示制御
    - _要件: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.2, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x] 11.2 `genai/frontend/src/pages/ReviewDetail.css` を作成
    - 審査案件詳細のスタイル定義
    - _要件: 9.1_

- [x] 12. フロントエンド: 審査ダッシュボード
  - [x] 12.1 `genai/frontend/src/pages/ReviewDashboard.tsx` を作成
    - ステータス別件数表示（pending, in_review, escalated, approved, rejected）
    - priority 別の未審査件数表示
    - review_type 別の未審査件数表示
    - 既存の Card コンポーネントで統計カードを表示
    - _要件: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 12.2 `genai/frontend/src/pages/ReviewDashboard.css` を作成
    - 審査ダッシュボードのスタイル定義
    - _要件: 8.1_

- [x] 13. フロントエンド: ルーティングとナビゲーション統合
  - [x] 13.1 `genai/frontend/src/App.tsx` にルーティングを追加
    - /reviews → Reviews.tsx
    - /reviews/:id → ReviewDetail.tsx
    - /review-dashboard → ReviewDashboard.tsx
    - AuthGuard で reviewer/admin ロールを要求（ダッシュボードは viewer も許可）
    - _要件: 3.1, 3.2, 4.1, 8.5_

  - [x] 13.2 `genai/frontend/src/layouts/AppLayout.tsx` のナビゲーションに「審査」グループを追加
    - 審査キュー、審査ダッシュボードへのリンク
    - ロールに応じた表示制御
    - _要件: 3.1, 8.1_

- [x] 14. 最終チェックポイント - 全体検証
  - すべてのテストが通ることを確認し、不明点があればユーザに質問する。

## 備考

- `*` マーク付きのタスクはオプションであり、MVP では省略可能
- 各タスクは具体的な要件番号を参照しており、トレーサビリティを確保
- チェックポイントで段階的に検証を行い、問題の早期発見を促進
- プロパティテストは状態遷移の不変条件検証を最重要とし、Hypothesis で実装
- 既存の Alert 作成フローへの影響を最小限にするため、審査キュー投入は try-except でラップ

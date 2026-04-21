# 要件定義書: 手動審査ワークフロー (manual-review-workflow)

## はじめに

決済条件監視システム（Payment Compliance Monitor）に手動審査ワークフローを導入する。現状は自動検出（契約違反・ダークパターン・偽サイト）の結果がアラートとして表示されるのみで、人間による審査判定→承認のワークフローが存在しない。本機能により、自動検出でNGとなった案件を審査キューに投入し、一次審査（reviewer）→ 二次審査（admin）の二段階承認フローを経て最終判定を行う仕組みを実現する。

本機能は user-auth-rbac spec（admin / reviewer / viewer の3ロール）が前提であり、既存の Alert、VerificationResult、Violation モデルと統合する。

## 用語集

- **System**: 決済条件監視システム全体（FastAPI バックエンド + React フロントエンド）
- **Review_Queue**: 審査対象案件を管理するキュー。自動検出でNGとなったサイトが投入される
- **Review_Item**: 審査キュー内の個別案件。Alert と関連データへの参照を持つ
- **Review_Service**: 審査ワークフローのビジネスロジックを担当するバックエンドモジュール
- **Review_Decision**: 審査判定の記録。判定結果・理由・審査者情報を保持する
- **Reviewer**: reviewer ロールを持つユーザ。一次審査を担当する
- **Admin**: admin ロールを持つユーザ。二次審査（エスカレーション案件の最終判定）を担当する
- **Escalation**: 一次審査で判断が困難な案件を二次審査に回すこと
- **Review_Dashboard**: 審査状況の統計情報を表示するダッシュボードコンポーネント
- **AuditLog**: 操作履歴を記録する既存の監査ログモデル
- **Alert**: 既存のアラートモデル。違反・偽サイト検出時に生成される
- **VerificationResult**: 既存の検証結果モデル。サイト検証データを保持する
- **Notification_Service**: 既存の通知システム（dark-pattern-notification）

## 要件

### 要件 1: 審査キューモデルとデータベース

**ユーザストーリー:** 審査担当者として、自動検出でNGとなった案件が審査キューに自動投入されるようにしたい。審査対象を漏れなく管理するため。

#### 受入条件

1. THE Review_Item SHALL 以下のフィールドを持つ: id（主キー）、alert_id（Alert への外部キー）、site_id（MonitoringSite への外部キー）、review_type（"violation"、"dark_pattern"、"fake_site" のいずれか）、status（"pending"、"in_review"、"approved"、"rejected"、"escalated" のいずれか）、priority（"critical"、"high"、"medium"、"low" のいずれか）、assigned_to（審査担当者のユーザID、nullable）、created_at、updated_at
2. THE Review_Item SHALL status フィールドのデフォルト値を "pending" に設定する
3. THE Review_Item SHALL priority フィールドを関連する Alert の severity から自動設定する
4. THE Review_Item SHALL alert_id フィールドに Alert テーブルへの外部キー制約を設定する
5. THE Review_Item SHALL site_id フィールドに MonitoringSite テーブルへの外部キー制約を設定する
6. THE Review_Item SHALL status と priority にインデックスを設定する

### 要件 2: 審査キューへの自動投入

**ユーザストーリー:** システム管理者として、自動検出でNGとなった案件が自動的に審査キューに投入されるようにしたい。手動での案件登録を不要にするため。

#### 受入条件

1. WHEN 新しい Alert が severity "critical" または "high" で作成された場合、THE Review_Service SHALL 該当 Alert に対応する Review_Item を審査キューに自動投入する
2. WHEN 新しい Alert が severity "medium" で作成された場合、THE Review_Service SHALL 該当 Alert に対応する Review_Item を審査キューに自動投入する
3. WHEN VerificationResult の dark_pattern_score が 0.7 以上の場合、THE Review_Service SHALL 該当サイトの Review_Item を review_type "dark_pattern" で審査キューに投入する
4. WHEN Alert の alert_type が "fake_site" の場合、THE Review_Service SHALL 該当 Review_Item の priority を "critical" に設定する
5. IF 同一 Alert に対する Review_Item が既に存在する場合、THEN THE Review_Service SHALL 重複する Review_Item を作成しない

### 要件 3: 一次審査（reviewer による判定）

**ユーザストーリー:** 審査担当者（reviewer）として、審査キューから案件を取得し、検出結果を確認して判定を行いたい。効率的に審査業務を遂行するため。

#### 受入条件

1. WHILE ユーザのロールが reviewer または admin の場合、THE System SHALL 審査キュー一覧エンドポイント（GET /api/reviews）を提供する
2. WHILE ユーザのロールが reviewer または admin の場合、THE System SHALL 審査案件詳細エンドポイント（GET /api/reviews/{id}）を提供する
3. WHEN 審査案件詳細が要求された場合、THE Review_Service SHALL 関連する Alert、VerificationResult、Violation、ダークパターン検出結果を含む統合ビューを返す
4. WHILE ユーザのロールが reviewer または admin の場合、THE System SHALL 審査案件の担当者割り当てエンドポイント（POST /api/reviews/{id}/assign）を提供する
5. WHEN 審査案件が担当者に割り当てられた場合、THE Review_Service SHALL Review_Item の status を "in_review" に更新し、assigned_to に担当者のユーザIDを設定する
6. WHILE ユーザのロールが reviewer または admin の場合、THE System SHALL 審査判定エンドポイント（POST /api/reviews/{id}/decide）を提供する
7. THE Review_Service SHALL 一次審査の判定種別として "approved"（承認）、"rejected"（却下）、"escalated"（エスカレーション）を受け付ける
8. WHEN 一次審査で "approved" が選択された場合、THE Review_Service SHALL Review_Item の status を "approved" に更新する
9. WHEN 一次審査で "rejected" が選択された場合、THE Review_Service SHALL Review_Item の status を "rejected" に更新する
10. WHEN 一次審査で "escalated" が選択された場合、THE Review_Service SHALL Review_Item の status を "escalated" に更新する
11. IF Review_Item の status が "pending" または "in_review" 以外の場合、THEN THE Review_Service SHALL 判定操作を拒否し HTTP 409 ステータスコードを返す

### 要件 4: 二次審査（admin による最終判定）

**ユーザストーリー:** 管理者（admin）として、エスカレーションされた案件の最終判定を行いたい。判断が困難な案件に対して責任ある最終決定を下すため。

#### 受入条件

1. WHILE ユーザのロールが admin の場合、THE System SHALL エスカレーション案件一覧エンドポイント（GET /api/reviews/escalated）を提供する
2. WHILE ユーザのロールが admin の場合、THE System SHALL 二次審査判定エンドポイント（POST /api/reviews/{id}/final-decide）を提供する
3. THE Review_Service SHALL 二次審査の判定種別として "approved"（最終承認）と "rejected"（最終却下）を受け付ける
4. IF Review_Item の status が "escalated" 以外の場合、THEN THE Review_Service SHALL 二次審査判定を拒否し HTTP 409 ステータスコードを返す
5. WHEN 二次審査で "approved" が選択された場合、THE Review_Service SHALL Review_Item の status を "approved" に更新する
6. WHEN 二次審査で "rejected" が選択された場合、THE Review_Service SHALL Review_Item の status を "rejected" に更新する
7. WHILE ユーザのロールが reviewer の場合、THE Review_Service SHALL 二次審査判定エンドポイントへのアクセスを拒否し HTTP 403 ステータスコードを返す

### 要件 5: 審査判定記録

**ユーザストーリー:** セキュリティ担当者として、全ての審査判定の履歴を記録・参照したい。判定の追跡と監査対応のため。

#### 受入条件

1. THE Review_Decision SHALL 以下のフィールドを持つ: id（主キー）、review_item_id（Review_Item への外部キー）、reviewer_id（審査者のユーザID）、decision（"approved"、"rejected"、"escalated" のいずれか）、comment（判定理由コメント、必須）、review_stage（"primary"、"secondary" のいずれか）、decided_at
2. WHEN 審査判定が実行された場合、THE Review_Service SHALL Review_Decision レコードを作成する
3. WHEN 審査判定が実行された場合、THE Review_Service SHALL AuditLog に審査者の username、判定アクション、対象 Review_Item の ID を記録する
4. THE System SHALL 審査判定履歴取得エンドポイント（GET /api/reviews/{id}/decisions）を提供する
5. THE Review_Decision SHALL comment フィールドを空文字列で保存しない（1文字以上を要求する）

### 要件 6: 審査結果に基づくアラート更新と通知

**ユーザストーリー:** システム管理者として、審査結果に基づいてアラートのステータスが自動更新され、関係者に通知されるようにしたい。審査結果を迅速に反映するため。

#### 受入条件

1. WHEN Review_Item が "approved"（問題なし）と判定された場合、THE Review_Service SHALL 関連する Alert の is_resolved を true に更新する
2. WHEN Review_Item が "rejected"（違反確定）と判定された場合、THE Review_Service SHALL 関連する Alert の is_resolved を false のまま維持する
3. WHEN Review_Item が "rejected" と判定された場合、THE Notification_Service SHALL 該当サイトの顧客に違反確定通知を送信する
4. WHEN Review_Item が "escalated" と判定された場合、THE Notification_Service SHALL admin ロールのユーザにエスカレーション通知を送信する

### 要件 7: 審査キューのフィルタリングとソート

**ユーザストーリー:** 審査担当者として、審査キューを優先度・ステータス・種別でフィルタリングしたい。効率的に審査対象を選択するため。

#### 受入条件

1. THE System SHALL 審査キュー一覧エンドポイントで status パラメータによるフィルタリングを提供する
2. THE System SHALL 審査キュー一覧エンドポイントで priority パラメータによるフィルタリングを提供する
3. THE System SHALL 審査キュー一覧エンドポイントで review_type パラメータによるフィルタリングを提供する
4. THE System SHALL 審査キュー一覧エンドポイントで assigned_to パラメータによるフィルタリングを提供する
5. THE System SHALL 審査キュー一覧のデフォルトソート順を priority 降順（critical → low）、created_at 昇順（古い案件優先）とする
6. THE System SHALL 審査キュー一覧エンドポイントで limit と offset によるページネーションを提供する

### 要件 8: 審査ダッシュボード

**ユーザストーリー:** 管理者として、審査業務の全体状況を把握したい。審査の進捗管理とリソース配分の判断に活用するため。

#### 受入条件

1. THE System SHALL 審査統計エンドポイント（GET /api/reviews/stats）を提供する
2. THE Review_Service SHALL 審査統計として以下の件数を返す: 未審査（pending）件数、審査中（in_review）件数、エスカレーション（escalated）件数、承認済み（approved）件数、却下済み（rejected）件数
3. THE Review_Service SHALL 審査統計として priority 別の未審査件数を返す
4. THE Review_Service SHALL 審査統計として review_type 別の未審査件数を返す
5. WHILE ユーザのロールが viewer の場合、THE System SHALL 審査統計エンドポイントへの読み取りアクセスを許可する

### 要件 9: 審査案件詳細ビュー

**ユーザストーリー:** 審査担当者として、審査対象の全関連情報を一画面で確認したい。正確な判定を効率的に行うため。

#### 受入条件

1. WHEN 審査案件詳細が要求された場合、THE Review_Service SHALL 関連する Alert の詳細情報（severity、message、alert_type）を含めて返す
2. WHEN 審査案件の review_type が "violation" の場合、THE Review_Service SHALL 関連する Violation の詳細（violation_type、expected_value、actual_value）を含めて返す
3. WHEN 審査案件の review_type が "dark_pattern" の場合、THE Review_Service SHALL 関連する VerificationResult のダークパターン検出結果（dark_pattern_score、dark_pattern_types）を含めて返す
4. WHEN 審査案件の review_type が "fake_site" の場合、THE Review_Service SHALL 関連する Alert の偽サイト情報（fake_domain、domain_similarity_score、content_similarity_score）を含めて返す
5. THE Review_Service SHALL 審査案件詳細に過去の Review_Decision 履歴を含めて返す
6. THE Review_Service SHALL 審査案件詳細に関連する MonitoringSite の基本情報（name、url）を含めて返す

### 要件 10: 審査ワークフローの状態遷移制約

**ユーザストーリー:** システム管理者として、審査ワークフローの状態遷移が正しく制御されるようにしたい。不正な状態遷移を防止するため。

#### 受入条件

1. THE Review_Service SHALL "pending" から "in_review" への状態遷移のみを担当者割り当て時に許可する
2. THE Review_Service SHALL "in_review" から "approved"、"rejected"、"escalated" への状態遷移のみを一次審査判定時に許可する
3. THE Review_Service SHALL "escalated" から "approved"、"rejected" への状態遷移のみを二次審査判定時に許可する
4. IF 許可されていない状態遷移が要求された場合、THEN THE Review_Service SHALL 操作を拒否し HTTP 409 ステータスコードと現在のステータスを含むエラーメッセージを返す
5. THE Review_Service SHALL "approved" および "rejected" ステータスからの状態遷移を許可しない（最終状態）
6. FOR ALL Review_Item の状態遷移において、遷移前のステータスと遷移後のステータスの組み合わせが上記ルールに合致する場合のみ遷移が成功する（状態遷移の不変条件）

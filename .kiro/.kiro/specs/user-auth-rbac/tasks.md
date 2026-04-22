# 実装計画: ユーザ管理・権限管理 (user-auth-rbac)

## 概要

バックエンド認証基盤 → API エンドポイント → 既存 API 統合 → フロントエンド → 初期セットアップ・マイグレーションの順で段階的に実装する。各フェーズでプロパティベーステスト（Hypothesis）を組み込み、正当性を検証しながら進める。移行期間中は `X-API-Key` と JWT の両方をサポートする互換依存関数を使用し、既存テストが壊れないようにする。

## タスク

- [x] 1. バックエンド認証基盤の構築
  - [x] 1.1 User モデルと Pydantic スキーマの作成
    - `genai/src/models.py` に `User` モデルを追加（id, username, email, hashed_password, role, is_active, created_at, updated_at）
    - `genai/src/auth/schemas.py` に `LoginRequest`, `UserCreate`, `UserUpdate`, `UserResponse`, `TokenResponse`, `MeResponse` を作成
    - username, email の一意制約、role のインデックスを設定
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 1.2 Alembic マイグレーションの作成
    - `genai/alembic/versions/xxxx_add_users_table.py` を作成
    - users テーブル、一意制約、インデックスを定義
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 1.3 Password Hasher の実装
    - `genai/src/auth/password.py` に `hash_password`, `verify_password`, `validate_password_policy` を実装
    - passlib[bcrypt] の CryptContext を使用
    - _Requirements: 1.6, 1.7, 9.1, 9.2, 9.3_

  - [x]* 1.4 パスワードハッシュのプロパティテスト（Hypothesis）
    - `genai/tests/test_auth_password.py` を作成
    - **Property 1: パスワードハッシュのラウンドトリップ** — 任意の平文パスワードに対して hash → verify が True を返し、ハッシュ値 ≠ 平文
    - **Validates: Requirements 1.6, 1.7**

  - [x]* 1.5 パスワードポリシーのプロパティテスト（Hypothesis）
    - `genai/tests/test_auth_password.py` に追加
    - **Property 4: パスワードポリシーバリデーション** — 任意の文字列に対して、8文字未満・大文字なし・小文字なし・数字なしの各違反を正しく検出し、全条件を満たす文字列には空リストを返す
    - **Validates: Requirements 9.1, 9.2, 9.3**

  - [x] 1.6 JWT Manager の実装
    - `genai/src/auth/jwt.py` に `create_access_token`, `create_refresh_token`, `decode_access_token`, `decode_refresh_token` を実装
    - HS256 アルゴリズム、アクセストークン 30 分、リフレッシュトークン 7 日
    - _Requirements: 2.1, 2.5, 2.6_

  - [x]* 1.7 トークン有効期限のプロパティテスト（Hypothesis）
    - `genai/tests/test_auth_jwt.py` を作成
    - **Property 5: トークン有効期限の設定** — 任意のユーザに対して、アクセストークンの exp は発行時刻 +30 分、リフレッシュトークンの exp は発行時刻 +7 日
    - **Validates: Requirements 2.5, 2.6**

  - [x]* 1.8 ロール値バリデーションのプロパティテスト（Hypothesis）
    - `genai/tests/test_auth_jwt.py` に追加
    - **Property 2: ロール値のバリデーション** — 任意の文字列に対して、"admin"/"reviewer"/"viewer" のみ受け入れ、それ以外は拒否
    - **Validates: Requirements 1.4**

  - [x] 1.9 RBAC Engine の実装
    - `genai/src/auth/rbac.py` に `Role` Enum、`ROLE_PERMISSIONS` 定数、`check_permission` 関数を実装
    - admin: 全許可、viewer: GET のみ、reviewer: 定義済みエンドポイント・メソッドの組み合わせ
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x]* 1.10 RBAC パーミッションチェックのプロパティテスト（Hypothesis）
    - `genai/tests/test_auth_rbac.py` を作成
    - **Property 12: RBAC パーミッションチェックの正当性** — 任意のロール・パス・メソッドの組み合わせに対して、admin は常に True、viewer は GET のみ True、reviewer は定義済み許可のみ True
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**

  - [x] 1.11 Session Manager の実装
    - `genai/src/auth/session.py` に `store_refresh_token`, `validate_refresh_token`, `revoke_refresh_token`, `revoke_all_user_tokens` を実装
    - Redis キー: `refresh_token:{user_id}:{jti}`、TTL: 7 日
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 1.12 Rate Limiter の実装
    - `genai/src/auth/rate_limit.py` に `check_login_rate_limit` を実装
    - Redis キー: `login_attempts:{username}`、制限: 5 分間に 10 回
    - _Requirements: 9.4, 9.5_

  - [x]* 1.13 レート制限のプロパティテスト（Hypothesis）
    - `genai/tests/test_auth_rate_limit.py` を作成
    - **Property 18: ログインレート制限** — 任意のユーザ名に対して、5 分間に 10 回失敗後、11 回目は HTTP 429 を返し残り待機時間を含む
    - **Validates: Requirements 9.4, 9.5**

  - [x] 1.14 認証依存関数の実装
    - `genai/src/auth/dependencies.py` に `get_redis`, `get_current_user`, `require_role`, `get_current_user_or_api_key` を実装
    - `get_current_user_or_api_key` は JWT 優先、フォールバックで X-API-Key をサポート（移行期間用）
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_


- [x] 2. チェックポイント — Phase 1 検証
  - 全プロパティテスト・ユニットテストを実行し、認証基盤モジュールが正しく動作することを確認する
  - 問題があればユーザに確認する

- [x] 3. API エンドポイントの実装
  - [x] 3.1 Auth Router の実装
    - `genai/src/api/auth.py` に `POST /api/auth/login`, `POST /api/auth/refresh`, `POST /api/auth/logout`, `GET /api/auth/me` を実装
    - ログイン: パスワード検証 → JWT 発行 → リフレッシュトークン Redis 保存 → HttpOnly Cookie 設定
    - ログアウト: リフレッシュトークン Redis 削除 → Cookie クリア
    - リフレッシュ: Cookie からリフレッシュトークン取得 → Redis 検証 → トークンローテーション
    - タイミング攻撃対策: ユーザ不在時もダミーパスワード検証を実行
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.7, 2.8, 2.9_

  - [ ]* 3.2 ログイン認証のプロパティテスト（Hypothesis）
    - `genai/tests/test_auth_login.py` を作成
    - **Property 7: 無効な認証情報に対する汎用エラー** — 任意の無効なユーザ名・パスワードの組み合わせに対して、ユーザ名不在もパスワード不一致も同一エラーメッセージの HTTP 401 を返す
    - **Validates: Requirements 2.2, 2.3**

  - [ ]* 3.3 ログイン認証のユニットテスト
    - `genai/tests/test_auth_login.py` に追加
    - **Property 6: 有効な認証情報によるトークン発行** — アクティブユーザ + 正しいパスワードで JWT が発行され、ペイロードに id, username, role が含まれる
    - **Property 8: 無効化ユーザのログイン拒否** — is_active=False のユーザは正しいパスワードでも HTTP 401
    - **Validates: Requirements 2.1, 2.9**

  - [ ]* 3.4 セッション管理のユニットテスト
    - `genai/tests/test_auth_session.py` を作成
    - **Property 9: ログアウトによるトークン無効化** — ログアウト後のリフレッシュトークンでリフレッシュが失敗（HTTP 401）
    - **Property 10: ユーザ無効化による全セッション破棄** — 複数トークン保持ユーザの無効化で全トークンが Redis から削除
    - **Property 11: リフレッシュトークンの Redis TTL 一致** — 発行されたトークンの Redis TTL が 7 日と一致（±数秒）
    - **Validates: Requirements 2.4, 3.1, 3.2, 3.3, 3.4**

  - [x] 3.5 Users Router の実装
    - `genai/src/api/users.py` に `POST /api/users`, `GET /api/users`, `GET /api/users/{id}`, `PUT /api/users/{id}`, `POST /api/users/{id}/deactivate` を実装
    - 全エンドポイントに `require_role(Role.ADMIN)` を適用
    - ユーザ作成時: パスワードポリシー検証 → 重複チェック → ハッシュ化 → 保存
    - ユーザ無効化時: 自分自身の無効化を拒否 → is_active=False → 全セッション破棄
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

  - [ ]* 3.6 Users API のユニットテスト
    - `genai/tests/test_auth_users_api.py` を作成
    - **Property 3: ユーザ名・メールアドレスの一意性** — 重複 username/email でのユーザ作成は HTTP 409、既存データ不変
    - **Property 13: ユーザ一覧レスポンスからのパスワードハッシュ除外** — レスポンスに hashed_password フィールドが含まれない
    - 自分自身の無効化拒否のエッジケーステスト
    - **Validates: Requirements 1.2, 1.3, 5.6, 5.7, 5.8, 5.9**

  - [x] 3.7 Auth Router と Users Router を main.py に登録
    - `genai/src/main.py` に auth_router と users_router を include_router で追加
    - _Requirements: 2.1, 5.1_

- [x] 4. チェックポイント — Phase 2 検証
  - Auth Router / Users Router の全テストを実行し、認証・ユーザ管理 API が正しく動作することを確認する
  - 問題があればユーザに確認する

- [x] 5. 既存 API ルーターへの認証統合
  - [x] 5.1 既存 16 ルーターに認証依存関数を追加
    - 全既存ルーター（sites, customers, contracts, monitoring, alerts, screenshots, verification, categories, field_schemas, extraction, crawl, extracted_data, price_history, audit_logs, schedules, notifications, dark_patterns）の各エンドポイントに `Depends(get_current_user_or_api_key)` を追加
    - GET エンドポイント: `get_current_user_or_api_key`（認証のみ）
    - 書き込みエンドポイント（POST, PUT, DELETE）: `require_role(Role.ADMIN, Role.REVIEWER)` を適用（エンドポイントに応じて適切なロールを設定）
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 5.2 監査ログ統合の実装
    - 既存の書き込み操作エンドポイントで `AuditLog.user` に `current_user.username` を記録するよう修正
    - `genai/src/api/auth.py` のログイン成功・失敗時に認証イベントの監査ログを記録
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 5.3 認証統合のテスト
    - `genai/tests/test_auth_integration.py` を作成
    - **Property 14: 未認証リクエストの拒否** — 保護対象エンドポイントに認証なし/無効トークンでアクセスすると HTTP 401
    - **Property 15: リフレッシュトークンによるアクセストークン更新** — 有効なリフレッシュトークンで新アクセストークン取得、無効トークンは HTTP 401
    - **Property 16: 書き込み操作の監査ログ記録** — 認証済みユーザの書き込み操作後に AuditLog にエントリが作成される
    - **Property 17: 認証イベントの監査ログ記録** — ログイン試行（成功・失敗）で AuditLog に認証イベントが記録される
    - **Validates: Requirements 6.1, 6.2, 6.3, 2.7, 2.8, 7.1, 7.2, 7.4**

- [x] 6. チェックポイント — Phase 3 検証
  - 既存 API の認証統合テストを実行し、既存テストが壊れていないことを確認する
  - 問題があればユーザに確認する

- [x] 7. フロントエンド認証の実装
  - [x] 7.1 AuthContext / AuthProvider の実装
    - `genai/frontend/src/contexts/AuthContext.tsx` に `AuthState`, `AuthContextType`, `AuthProvider` を実装
    - login, logout, refreshToken, hasRole メソッドを提供
    - アクセストークンはステート（メモリ）に保持
    - アプリ起動時に `/api/auth/refresh` でセッション復元を試行
    - _Requirements: 8.3, 8.4_

  - [x] 7.2 Axios Interceptor の拡張
    - `genai/frontend/src/services/api.ts` にリクエスト/レスポンスインターセプターを追加
    - リクエスト: `Authorization: Bearer <accessToken>` ヘッダーを自動付与
    - レスポンス: 401 時に自動リフレッシュ → リトライ、リフレッシュ失敗時はログアウト
    - _Requirements: 8.4, 8.5_

  - [x] 7.3 Login Page の実装
    - `genai/frontend/src/pages/Login.tsx` にログインフォームを作成
    - ユーザ名・パスワード入力、エラーメッセージ表示（認証失敗、レート制限）
    - ログイン成功後、元のページまたはダッシュボードにリダイレクト
    - _Requirements: 8.1, 8.2_

  - [x] 7.4 ProtectedRoute コンポーネントの実装
    - `genai/frontend/src/components/ProtectedRoute.tsx` を作成
    - 未認証 → `/login` にリダイレクト、ロール不足 → 403 ページ表示
    - 既存ルーティングを ProtectedRoute でラップ
    - _Requirements: 8.2, 8.6_

  - [x] 7.5 ナビゲーション制御の実装
    - `AppLayout.tsx` を拡張し、`AuthContext` の `user.role` に基づいてメニュー項目をフィルタリング
    - admin のみ「ユーザ管理」メニューを表示
    - viewer は書き込み操作の UI コンポーネント（作成・編集・削除ボタン）を非表示
    - _Requirements: 8.6, 8.7, 8.8_

  - [ ]* 7.6 フロントエンドテスト（Vitest）
    - `genai/frontend/src/__tests__/AuthContext.test.tsx` — AuthProvider のログイン・ログアウト・リフレッシュ動作
    - `genai/frontend/src/__tests__/ProtectedRoute.test.tsx` — 未認証リダイレクト、ロール不足時の 403 表示
    - `genai/frontend/src/__tests__/Login.test.tsx` — フォーム表示、バリデーション、エラーメッセージ
    - `genai/frontend/src/__tests__/api-interceptor.test.ts` — 自動リフレッシュ、リトライ動作
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7**

- [x] 8. チェックポイント — Phase 4 検証
  - フロントエンドテストを実行し、認証 UI が正しく動作することを確認する
  - 問題があればユーザに確認する

- [x] 9. 初期セットアップとマイグレーション
  - [x] 9.1 初期 admin ユーザ作成の実装
    - `genai/src/main.py` の lifespan イベントに `_create_initial_admin` を追加
    - DB にユーザが 0 件の場合のみ実行
    - `ADMIN_USERNAME`（デフォルト: "admin"）、`ADMIN_PASSWORD`（未設定時はランダム生成 + 警告ログ）から読み取り
    - 作成を AuditLog に記録
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 9.2 初期セットアップのユニットテスト
    - `genai/tests/test_auth_initial_setup.py` を作成
    - ユーザ 0 件時に admin ユーザが作成されること
    - ユーザ既存時にスキップされること
    - ADMIN_PASSWORD 未設定時にランダムパスワードが生成されること
    - AuditLog に初期セットアップが記録されること
    - **Validates: Requirements 10.1, 10.2, 10.3, 10.4, 10.5**

  - [x] 9.3 環境変数の追加
    - `genai/.env.example` に `JWT_SECRET_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` を追加
    - _Requirements: 10.2, 10.3_

- [x] 10. 最終チェックポイント — 全体検証
  - 全テスト（バックエンド pytest + フロントエンド vitest）を実行し、全テストがパスすることを確認する
  - 既存テストが壊れていないことを確認する（X-API-Key 互換依存関数による後方互換性）
  - 問題があればユーザに確認する

## 備考

- `*` マーク付きタスクはオプションであり、MVP 優先時はスキップ可能
- 各タスクは対応する要件番号を参照しており、トレーサビリティを確保
- チェックポイントで段階的に検証を行い、問題の早期発見を促進
- プロパティテストは Hypothesis を使用し、ランダム入力による正当性検証を実施
- 移行期間中は `get_current_user_or_api_key` を使用し、既存の X-API-Key 認証との後方互換性を維持

# 要件定義書: ユーザ管理・権限管理 (user-auth-rbac)

## はじめに

決済条件監視システム（Payment Compliance Monitor）に、ユーザ認証・ユーザ管理・ロールベースアクセス制御（RBAC）を導入する。現状は `X-API-Key` ヘッダーによる単一キー認証のみであり、個別ユーザの識別・権限制御・セッション管理が存在しない。本機能により、管理画面の利用者を個別に管理し、ロールに基づくアクセス制御を実現する。

## 用語集

- **System**: 決済条件監視システム全体（FastAPI バックエンド + React フロントエンド）
- **Auth_Service**: 認証・認可を担当するバックエンドモジュール
- **User_Model**: ユーザ情報を格納するデータベースモデル
- **Session_Store**: Redis を利用したセッション情報の保存先
- **RBAC_Engine**: ロールとパーミッションに基づくアクセス制御エンジン
- **AuditLog**: 操作履歴を記録する既存の監査ログモデル
- **Admin**: 全機能にアクセス可能なロール（ユーザ管理、ルール管理、サイト管理、審査）
- **Reviewer**: 審査・判定操作が可能なロール（サイト閲覧、アラート確認、手動審査）
- **Viewer**: 閲覧のみ可能なロール（ダッシュボード、アラート閲覧、結果参照）
- **Password_Hasher**: bcrypt を使用したパスワードハッシュ化モジュール
- **Login_Page**: フロントエンドのログイン画面コンポーネント

## 要件

### 要件 1: ユーザモデルとデータベース

**ユーザストーリー:** 管理者として、システム利用者の情報をデータベースで管理したい。利用者ごとにアカウントを発行し、個別に認証・追跡できるようにするため。

#### 受入条件

1. THE User_Model SHALL 以下のフィールドを持つ: id（主キー）、username（一意）、email（一意）、hashed_password、role、is_active、created_at、updated_at
2. THE User_Model SHALL username フィールドに一意制約を設定する
3. THE User_Model SHALL email フィールドに一意制約を設定する
4. THE User_Model SHALL role フィールドに "admin"、"reviewer"、"viewer" のいずれかの値のみを許可する
5. THE User_Model SHALL is_active フィールドのデフォルト値を true に設定する
6. THE Password_Hasher SHALL パスワードを bcrypt アルゴリズムでハッシュ化して保存する
7. THE Password_Hasher SHALL 平文パスワードをデータベースに保存しない

### 要件 2: ユーザ認証（ログイン・ログアウト）

**ユーザストーリー:** システム利用者として、ユーザ名とパスワードでログインし、セッションを確立したい。安全にシステムを利用するため。

#### 受入条件

1. WHEN 有効なユーザ名とパスワードが送信された場合、THE Auth_Service SHALL JWT アクセストークンとリフレッシュトークンを発行する
2. WHEN 無効なユーザ名またはパスワードが送信された場合、THE Auth_Service SHALL HTTP 401 ステータスコードとエラーメッセージを返す
3. WHEN 無効な認証情報が送信された場合、THE Auth_Service SHALL ユーザ名が存在するかどうかを区別できない汎用エラーメッセージを返す
4. WHEN ログアウトリクエストが送信された場合、THE Auth_Service SHALL 該当セッションのトークンを無効化する
5. THE Auth_Service SHALL アクセストークンの有効期限を30分に設定する
6. THE Auth_Service SHALL リフレッシュトークンの有効期限を7日間に設定する
7. WHEN アクセストークンが期限切れの場合、THE Auth_Service SHALL 有効なリフレッシュトークンを使用して新しいアクセストークンを発行する
8. WHEN リフレッシュトークンが期限切れまたは無効の場合、THE Auth_Service SHALL HTTP 401 ステータスコードを返し再ログインを要求する
9. WHILE ユーザアカウントが無効化されている間、THE Auth_Service SHALL 該当ユーザのログインを拒否する

### 要件 3: セッション管理

**ユーザストーリー:** システム管理者として、アクティブなセッションを管理し、不正アクセスを防止したい。セキュリティを確保するため。

#### 受入条件

1. THE Session_Store SHALL Redis にリフレッシュトークンのホワイトリストを保存する
2. WHEN ログアウトが実行された場合、THE Session_Store SHALL 該当リフレッシュトークンを Redis から削除する
3. WHEN ユーザアカウントが無効化された場合、THE Session_Store SHALL 該当ユーザの全リフレッシュトークンを Redis から削除する
4. THE Session_Store SHALL リフレッシュトークンの TTL をトークンの有効期限と一致させる

### 要件 4: ロールベースアクセス制御（RBAC）

**ユーザストーリー:** システム管理者として、ユーザのロールに基づいてアクセス可能な機能を制限したい。情報セキュリティと職務分離を実現するため。

#### 受入条件

1. THE RBAC_Engine SHALL 以下の3つのロールを定義する: admin、reviewer、viewer
2. WHILE ユーザのロールが admin の場合、THE RBAC_Engine SHALL 全APIエンドポイントへのアクセスを許可する
3. WHILE ユーザのロールが reviewer の場合、THE RBAC_Engine SHALL サイト閲覧、アラート閲覧、手動審査（承認・却下）、抽出データ閲覧のエンドポイントへのアクセスを許可する
4. WHILE ユーザのロールが viewer の場合、THE RBAC_Engine SHALL 読み取り専用エンドポイント（GET メソッド）へのアクセスのみを許可する
5. WHEN 権限のないエンドポイントにアクセスした場合、THE RBAC_Engine SHALL HTTP 403 ステータスコードとエラーメッセージを返す
6. THE RBAC_Engine SHALL ロールとパーミッションのマッピングを設定ファイルまたは定数として管理する

### 要件 5: ユーザ管理 CRUD

**ユーザストーリー:** 管理者として、システム利用者のアカウントを作成・閲覧・更新・削除したい。利用者のライフサイクルを管理するため。

#### 受入条件

1. WHILE ユーザのロールが admin の場合、THE System SHALL ユーザ作成エンドポイント（POST /api/users）を提供する
2. WHILE ユーザのロールが admin の場合、THE System SHALL ユーザ一覧取得エンドポイント（GET /api/users）を提供する
3. WHILE ユーザのロールが admin の場合、THE System SHALL ユーザ詳細取得エンドポイント（GET /api/users/{id}）を提供する
4. WHILE ユーザのロールが admin の場合、THE System SHALL ユーザ更新エンドポイント（PUT /api/users/{id}）を提供する
5. WHILE ユーザのロールが admin の場合、THE System SHALL ユーザ無効化エンドポイント（POST /api/users/{id}/deactivate）を提供する
6. WHEN 既に存在するユーザ名でユーザ作成が試行された場合、THE System SHALL HTTP 409 ステータスコードを返す
7. WHEN 既に存在するメールアドレスでユーザ作成が試行された場合、THE System SHALL HTTP 409 ステータスコードを返す
8. WHEN ユーザが自分自身のアカウントを無効化しようとした場合、THE System SHALL 操作を拒否しエラーメッセージを返す
9. THE System SHALL ユーザ一覧レスポンスにパスワードハッシュを含めない

### 要件 6: 既存APIエンドポイントの認証統合

**ユーザストーリー:** システム管理者として、既存の全APIエンドポイントにユーザ認証を適用したい。未認証アクセスを防止するため。

#### 受入条件

1. THE System SHALL 既存の全APIエンドポイント（/health と /api/auth/* を除く）に JWT 認証を適用する
2. WHEN 認証トークンが付与されていないリクエストを受信した場合、THE System SHALL HTTP 401 ステータスコードを返す
3. WHEN 無効または期限切れの認証トークンを受信した場合、THE System SHALL HTTP 401 ステータスコードを返す
4. THE System SHALL 既存の X-API-Key 認証から JWT 認証への移行期間中、両方の認証方式をサポートする
5. THE System SHALL 移行完了後に X-API-Key 認証を廃止できる設計とする

### 要件 7: 監査ログ統合

**ユーザストーリー:** セキュリティ担当者として、全操作を実行ユーザに紐付けて記録したい。操作の追跡と責任の明確化のため。

#### 受入条件

1. THE AuditLog SHALL user フィールドに認証済みユーザの username を記録する
2. WHEN 認証済みユーザが書き込み操作を実行した場合、THE System SHALL AuditLog に操作者の username、アクション、対象リソースを記録する
3. THE AuditLog SHALL 既存のログエントリとの後方互換性を維持する（既存の文字列型 user フィールドを保持する）
4. WHEN ログイン成功またはログイン失敗が発生した場合、THE Auth_Service SHALL AuditLog に認証イベントを記録する

### 要件 8: フロントエンド認証統合

**ユーザストーリー:** システム利用者として、ブラウザからログインし、権限に応じた画面を利用したい。安全かつ直感的にシステムを操作するため。

#### 受入条件

1. THE Login_Page SHALL ユーザ名とパスワードの入力フィールドを持つログインフォームを表示する
2. WHEN 認証されていない状態でページにアクセスした場合、THE System SHALL Login_Page にリダイレクトする
3. WHEN ログインに成功した場合、THE System SHALL アクセストークンをメモリ（変数）に保存し、リフレッシュトークンを HttpOnly Cookie に保存する
4. WHEN アクセストークンが期限切れの場合、THE System SHALL リフレッシュトークンを使用して自動的にトークンを更新する
5. WHEN トークン更新に失敗した場合、THE System SHALL Login_Page にリダイレクトする
6. THE System SHALL ユーザのロールに基づいてナビゲーションメニューの表示項目を制御する
7. WHILE ユーザのロールが viewer の場合、THE System SHALL 書き込み操作のUIコンポーネント（作成・編集・削除ボタン）を非表示にする
8. WHILE ユーザのロールが admin の場合、THE System SHALL ナビゲーションに「ユーザ管理」メニュー項目を表示する

### 要件 9: パスワードセキュリティ

**ユーザストーリー:** セキュリティ担当者として、パスワードポリシーを適用したい。不正アクセスのリスクを低減するため。

#### 受入条件

1. THE System SHALL パスワードの最小文字数を8文字に設定する
2. THE System SHALL パスワードに英大文字、英小文字、数字をそれぞれ1文字以上含むことを要求する
3. WHEN パスワードポリシーを満たさないパスワードが送信された場合、THE System SHALL 具体的なポリシー違反内容を含むエラーメッセージを返す
4. THE Auth_Service SHALL ログイン試行を同一ユーザ名に対して5分間に10回までに制限する
5. WHEN ログイン試行回数の上限に達した場合、THE Auth_Service SHALL HTTP 429 ステータスコードを返し、残り待機時間を含むエラーメッセージを返す

### 要件 10: 初期セットアップ

**ユーザストーリー:** システム管理者として、初回デプロイ時にデフォルト管理者アカウントを作成したい。システムの初期設定を完了するため。

#### 受入条件

1. WHEN データベースにユーザが1件も存在しない場合、THE System SHALL 環境変数から初期管理者アカウントの情報を読み取り、admin ロールのユーザを作成する
2. THE System SHALL 初期管理者のユーザ名を環境変数 `ADMIN_USERNAME` から読み取る（デフォルト値: "admin"）
3. THE System SHALL 初期管理者のパスワードを環境変数 `ADMIN_PASSWORD` から読み取る
4. IF 環境変数 `ADMIN_PASSWORD` が設定されていない場合、THEN THE System SHALL 起動時に警告ログを出力し、ランダムなパスワードを生成してログに出力する
5. THE System SHALL 初期管理者アカウントの作成を AuditLog に記録する

### 要件 11: パスワード変更

**ユーザストーリー:** システム利用者として、自分のパスワードを変更したい。定期的なパスワード更新やセキュリティ上の理由でパスワードを変更するため。

#### 受入条件

1. THE System SHALL パスワード変更エンドポイント（POST /api/auth/change-password）を提供する
2. WHEN パスワード変更リクエストが送信された場合、THE Auth_Service SHALL 現在のパスワードの検証を要求する
3. WHEN 現在のパスワードが正しく、新しいパスワードがパスワードポリシーを満たす場合、THE Auth_Service SHALL パスワードを更新する
4. WHEN 現在のパスワードが間違っている場合、THE Auth_Service SHALL HTTP 401 ステータスコードを返す
5. WHEN パスワード変更が成功した場合、THE Auth_Service SHALL 該当ユーザの全リフレッシュトークンを Redis から削除する（全セッション強制ログアウト）
6. WHEN パスワード変更が成功した場合、THE Auth_Service SHALL AuditLog にパスワード変更イベントを記録する
7. THE System SHALL フロントエンドのヘッダーメニューまたはプロフィール画面に「パスワード変更」リンクを表示する
8. THE パスワード変更フォーム SHALL 現在のパスワード、新しいパスワード、新しいパスワード（確認）の3つの入力フィールドを持つ

### 要件 12: エラーページ

**ユーザストーリー:** システム利用者として、エラー発生時に適切なエラーページを表示してほしい。何が起きたかを理解し、次のアクションを判断するため。

#### 受入条件

1. THE System SHALL 403 Forbidden エラーページコンポーネントを提供し、「権限がありません」メッセージとダッシュボードへの戻りリンクを表示する
2. THE System SHALL 404 Not Found エラーページコンポーネントを提供し、「ページが見つかりません」メッセージとダッシュボードへの戻りリンクを表示する
3. THE System SHALL 500 Server Error エラーページコンポーネントを提供し、「サーバーエラーが発生しました」メッセージとリロードボタンを表示する
4. WHEN ProtectedRoute でロール不足が検出された場合、THE System SHALL 403 エラーページを表示する
5. WHEN 存在しないURLにアクセスした場合、THE System SHALL 404 エラーページを表示する

### 要件 13: 監査ログ閲覧UI

**ユーザストーリー:** 管理者として、システムの操作履歴を閲覧したい。セキュリティ監査や問題調査のため。

#### 受入条件

1. WHILE ユーザのロールが admin の場合、THE System SHALL 監査ログ一覧ページ（/audit-logs）を提供する
2. THE 監査ログ一覧ページ SHALL AuditLog のエントリを日時降順で表示する
3. THE 監査ログ一覧ページ SHALL ユーザ名、アクション、リソースタイプによるフィルタリングを提供する
4. THE 監査ログ一覧ページ SHALL 日時範囲による検索を提供する
5. THE 監査ログ一覧ページ SHALL limit と offset によるページネーションを提供する
6. WHILE ユーザのロールが admin の場合、THE System SHALL ナビゲーションに「監査ログ」メニュー項目を表示する

# 要件定義書: 契約条件動的フォーム (dynamic-contract-form)

## はじめに

契約条件登録フォーム（`Contracts.tsx`）を、カテゴリ別の動的フィールドスキーマ（`Category` + `FieldSchema`）に基づく動的フォームに拡張する。現状は固定フィールド（prices, payment_methods, fees, subscription_terms）のみがハードコードされており、カテゴリに応じた追加フィールドの定義・入力ができない。

バックエンドには既に `Category` モデル、`FieldSchema` モデル、`GET /api/categories/`、`GET /api/field-schemas/category/{category_id}` の各APIが実装済みである。本specはフロントエンドの契約条件フォームをこれらのAPIと連携させ、動的フィールド入力を実現する。

## 用語集

- **ContractForm**: 契約条件登録・編集フォーム（`Contracts.tsx` 内のモーダル）
- **Category**: 商品/サービスカテゴリ（既存モデル）
- **FieldSchema**: カテゴリ別の動的フィールド定義（既存モデル: field_name, field_type, is_required, validation_rules, display_order）
- **DynamicField**: FieldSchema に基づいて動的に生成されるフォーム入力フィールド
- **FieldType**: フィールドの型（text, number, currency, percentage, date, boolean, list）

## 要件

### 要件 1: カテゴリ選択による動的フィールド表示

**ユーザストーリー:** 管理者として、契約条件登録時にカテゴリを選択すると、そのカテゴリに定義された追加フィールドが自動的にフォームに表示されるようにしたい。カテゴリ固有の契約条件を漏れなく登録するため。

#### 受入条件

1. THE ContractForm SHALL カテゴリ選択 Select コンポーネントを提供する
2. WHEN ユーザーがカテゴリを選択した場合、THE ContractForm SHALL `GET /api/field-schemas/category/{category_id}` APIを呼び出し、該当カテゴリの FieldSchema 一覧を取得する
3. WHEN FieldSchema 一覧が取得された場合、THE ContractForm SHALL 各 FieldSchema に対応する入力フィールドを display_order 順に動的生成する
4. THE ContractForm SHALL FieldSchema の field_type に応じて適切な入力コンポーネントを表示する: text→Input、number→数値Input、currency→通貨Input（金額+通貨コード）、percentage→パーセンテージInput、date→日付Input、boolean→チェックボックス、list→複数値入力
5. THE ContractForm SHALL FieldSchema の is_required が true のフィールドに必須マーク（*）を表示する
6. WHEN カテゴリが変更された場合、THE ContractForm SHALL 前のカテゴリの動的フィールドをクリアし、新しいカテゴリのフィールドを表示する
7. IF カテゴリが未選択の場合、THEN THE ContractForm SHALL 固定フィールド（prices, payment_methods, fees, subscription_terms）のみを表示する

### 要件 2: 動的フィールドのバリデーション

**ユーザストーリー:** 管理者として、動的フィールドの入力値がバリデーションルールに従っているか自動チェックされるようにしたい。不正な契約条件の登録を防止するため。

#### 受入条件

1. WHEN FieldSchema に validation_rules が定義されている場合、THE ContractForm SHALL 入力値に対してクライアントサイドバリデーションを実行する
2. THE ContractForm SHALL validation_rules の以下のルールをサポートする: min（最小値）、max（最大値）、pattern（正規表現）、options（選択肢リスト）
3. WHEN is_required が true のフィールドが空の場合、THE ContractForm SHALL 「必須項目です」エラーメッセージを表示する
4. WHEN バリデーションエラーがある場合、THE ContractForm SHALL 送信ボタンを無効化する

### 要件 3: 動的フィールド値の保存と表示

**ユーザストーリー:** 管理者として、動的フィールドに入力した値が契約条件として保存され、一覧画面で確認できるようにしたい。登録した追加条件を後から参照するため。

#### 受入条件

1. WHEN 契約条件が保存される場合、THE ContractForm SHALL 動的フィールドの値を ContractCondition の JSONB フィールドに含めて送信する
2. THE 契約条件一覧 SHALL 動的フィールドの値をカード内に表示する
3. THE 契約条件編集モーダル SHALL 既存の動的フィールド値をフォームに事前入力する
4. THE ApiService SHALL `ContractConditionCreate` 型に `dynamic_fields?: Record<string, any>` フィールドを追加する

### 要件 4: フィールドスキーマ管理UI

**ユーザストーリー:** 管理者として、カテゴリごとのフィールドスキーマ（追加フィールド定義）を管理画面から作成・編集・削除したい。新しい契約条件項目を柔軟に追加するため。

#### 受入条件

1. WHILE ユーザのロールが admin の場合、THE System SHALL カテゴリ管理ページ内にフィールドスキーマ管理セクションを提供する
2. THE フィールドスキーマ管理セクション SHALL 選択されたカテゴリの FieldSchema 一覧を表示する
3. THE フィールドスキーマ管理セクション SHALL フィールドの追加（POST /api/field-schemas/）、編集（PUT /api/field-schemas/{id}）、削除（DELETE /api/field-schemas/{id}）を提供する
4. THE フィールド追加フォーム SHALL field_name、field_type（Select）、is_required（チェックボックス）、validation_rules（JSON入力）、display_order（数値）の入力を提供する
5. THE フィールドスキーマ管理セクション SHALL ドラッグ&ドロップまたは数値入力で display_order を変更可能にする

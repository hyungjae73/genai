# 実装計画: 契約条件動的フォーム (dynamic-contract-form)

## 概要

契約条件登録フォーム（`Contracts.tsx`）をカテゴリ別の動的フィールドスキーマに基づく動的フォームに拡張する。バックエンドの Category / FieldSchema モデルおよび API は実装済みのため、主な変更はフロントエンドと schemas.py の最小限の拡張。

## タスク

- [x] 1. バックエンド: schemas.py の拡張
  - [x] 1.1 `genai/src/api/schemas.py` の `ContractConditionCreate` に `dynamic_fields` と `category_id` を追加
    - `dynamic_fields: Optional[dict[str, Any]] = None`
    - `category_id: Optional[int] = None`
    - _要件: 3.4_

  - [x] 1.2 `ContractConditionUpdate` にも同フィールドを追加
    - `dynamic_fields: Optional[dict[str, Any]] = None`
    - `category_id: Optional[int] = None`
    - _要件: 3.4_

  - [x] 1.3 `ContractConditionResponse` に `dynamic_fields` と `category_id` を追加
    - `dynamic_fields: Optional[dict[str, Any]] = None`
    - `category_id: Optional[int] = None`
    - _要件: 3.2, 3.3_

- [x] 2. チェックポイント - バックエンド変更の確認
  - schemas.py の変更が既存テストに影響しないことを確認する。

- [x] 3. フロントエンド: api.ts の型拡張
  - [x] 3.1 `genai/frontend/src/services/api.ts` の `ContractConditionCreate` 型に `dynamic_fields` と `category_id` を追加
    - `category_id?: number`
    - `dynamic_fields?: Record<string, unknown>`
    - _要件: 3.4_

  - [x] 3.2 `ContractCondition` レスポンス型にも同フィールドを追加
    - _要件: 3.2, 3.3_

- [x] 4. フロントエンド: DynamicFieldInput コンポーネントの作成
  - [x] 4.1 `genai/frontend/src/components/contract/DynamicFieldInput.tsx` を作成
    - `FieldSchema` の `field_type` に応じた入力コンポーネントを返す
    - text → Input、number → 数値 Input、currency → 金額 + 通貨コード、percentage → 数値 + %、date → 日付 Input、boolean → チェックボックス、list → 複数値入力
    - `is_required` が true の場合は必須マーク（*）を表示
    - _要件: 1.4, 1.5_

  - [x] 4.2 `genai/frontend/src/components/contract/DynamicFieldInput.css` を作成
    - 動的フィールドのスタイル定義
    - _要件: 1.4_

- [x] 5. フロントエンド: バリデーションロジックの実装
  - [x] 5.1 `genai/frontend/src/components/contract/validateDynamicField.ts` を作成
    - `validateDynamicField(schema: FieldSchema, value: unknown): string | null`
    - min / max / pattern / options の4ルールをサポート
    - is_required チェック
    - _要件: 2.1, 2.2, 2.3_

- [x] 6. フロントエンド: Contracts.tsx の動的フォーム化
  - [x] 6.1 カテゴリ選択 Select を追加
    - `getCategories()` で取得したカテゴリ一覧を表示
    - カテゴリ未選択時は固定フィールドのみ表示
    - _要件: 1.1, 1.7_

  - [x] 6.2 カテゴリ選択時の動的フィールド取得と表示
    - `getFieldSchemas(categoryId)` を呼び出し、`display_order` 順にソート
    - `DynamicFieldInput` コンポーネントで各フィールドを動的生成
    - カテゴリ変更時は前カテゴリのフィールド値をクリア
    - _要件: 1.2, 1.3, 1.6_

  - [x] 6.3 バリデーション統合
    - `validateDynamicField` を使用してリアルタイムバリデーション
    - エラーがある場合は送信ボタンを無効化
    - _要件: 2.3, 2.4_

  - [x] 6.4 保存時に `dynamic_fields` と `category_id` を送信
    - `ContractConditionCreate` に `dynamic_fields` と `category_id` を含める
    - _要件: 3.1_

  - [x] 6.5 編集モーダルで既存の `dynamic_fields` 値を事前入力
    - 編集時に `contract.dynamic_fields` を `dynamicFields` state に設定
    - 編集時に `contract.category_id` でカテゴリを選択状態にし、対応フィールドを表示
    - _要件: 3.3_

  - [x] 6.6 契約条件カードに `dynamic_fields` の値を表示
    - `contract.dynamic_fields` の key-value を一覧表示
    - _要件: 3.2_

- [x] 7. フロントエンド: Categories.tsx への FieldSchemaManager 統合
  - [x] 7.1 `genai/frontend/src/pages/Categories.tsx` にカテゴリ選択時の FieldSchemaManager を追加
    - admin ロールのみ表示
    - 選択されたカテゴリの `FieldSchemaManager` を表示
    - _要件: 4.1, 4.2_

  - [x] 7.2 FieldSchemaManager の display_order 変更 UI を確認
    - 既存の `FieldSchemaManager` コンポーネントに display_order 変更機能があるか確認
    - なければ数値入力フィールドを追加
    - _要件: 4.5_

- [x] 8. 最終チェックポイント - 全体検証
  - すべてのテストが通ることを確認し、不明点があればユーザに質問する。

## 備考

- バックエンドの Category / FieldSchema モデルおよび CRUD API は実装済み
- `FieldSchemaManager` コンポーネント（`genai/frontend/src/components/category/FieldSchemaManager.tsx`）は実装済み
- DB スキーマ変更不要（ContractCondition の既存 JSONB フィールドを活用）
- `category_id` を ContractCondition モデルに追加する場合は Alembic マイグレーションが必要（オプション）

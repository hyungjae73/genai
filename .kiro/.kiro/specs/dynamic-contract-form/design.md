# 設計書: 契約条件動的フォーム (dynamic-contract-form)

## 概要

契約条件登録フォーム（`Contracts.tsx`）を、カテゴリ別の動的フィールドスキーマに基づく動的フォームに拡張する。バックエンドの `Category` / `FieldSchema` モデルおよび API は実装済みであり、本 spec はフロントエンドの変更が主体となる。

### 技術スタック

- フロントエンド: React + TypeScript + Vite（既存）
- バックエンド: FastAPI + SQLAlchemy（既存 API を利用）
- 既存 API: `GET /api/categories/`, `GET /api/field-schemas/category/{id}`, `POST /api/field-schemas/`, `PUT /api/field-schemas/{id}`, `DELETE /api/field-schemas/{id}`

### 設計方針

- **バックエンド変更最小化**: `ContractConditionCreate` に `dynamic_fields` フィールドを追加するのみ。既存の JSONB フィールドに格納
- **既存コンポーネント再利用**: `FieldSchemaManager` コンポーネントは既に実装済み。`Categories.tsx` に統合するだけ
- **フロントエンド中心**: 主要変更は `Contracts.tsx` の動的フォーム化と `api.ts` の型拡張

## アーキテクチャ

```mermaid
graph TD
    subgraph Frontend
        CT[Contracts.tsx<br>動的フォーム拡張]
        CAT[Categories.tsx<br>FieldSchemaManager統合]
        API[api.ts<br>型拡張]
    end

    subgraph Backend["バックエンド (既存)"]
        CC[ContractCondition API<br>/api/contracts/]
        FS[FieldSchema API<br>/api/field-schemas/]
        CA[Category API<br>/api/categories/]
    end

    CT -->|GET /api/categories/| CA
    CT -->|GET /api/field-schemas/category/{id}| FS
    CT -->|POST /api/contracts/| CC
    CAT -->|CRUD /api/field-schemas/| FS
```

## コンポーネントとインターフェース

### 1. api.ts の型拡張

```typescript
// ContractConditionCreate に dynamic_fields を追加
export interface ContractConditionCreate {
  site_id: number;
  prices: { ... };
  payment_methods: { ... };
  fees: { ... };
  subscription_terms?: { ... };
  category_id?: number;                          // 追加
  dynamic_fields?: Record<string, unknown>;      // 追加（要件 3.4）
}

// ContractCondition レスポンスにも追加
export interface ContractCondition {
  // 既存フィールド...
  category_id?: number;
  dynamic_fields?: Record<string, unknown>;
}
```

### 2. Contracts.tsx の動的フォーム化

**変更点:**

1. カテゴリ選択 Select を追加（要件 1.1）
2. カテゴリ選択時に `getFieldSchemas(categoryId)` を呼び出し（要件 1.2）
3. `DynamicFieldInput` コンポーネントで field_type に応じた入力を動的生成（要件 1.3, 1.4）
4. `dynamic_fields` state を管理し、保存時に `ContractConditionCreate` に含める（要件 3.1）
5. 編集時に既存の `dynamic_fields` 値を事前入力（要件 3.3）

**フォーム状態管理:**

```typescript
const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
const [fieldSchemas, setFieldSchemas] = useState<FieldSchema[]>([]);
const [dynamicFields, setDynamicFields] = useState<Record<string, unknown>>({});
const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
```

**カテゴリ変更ハンドラ:**

```typescript
const handleCategoryChange = async (categoryId: number | null) => {
  setSelectedCategoryId(categoryId);
  setDynamicFields({});   // 前カテゴリのフィールドをクリア（要件 1.6）
  setFieldErrors({});
  if (categoryId) {
    const schemas = await getFieldSchemas(categoryId);
    setFieldSchemas(schemas.sort((a, b) => a.display_order - b.display_order));
  } else {
    setFieldSchemas([]);
  }
};
```

### 3. DynamicFieldInput コンポーネント（新規）

`genai/frontend/src/components/contract/DynamicFieldInput.tsx`

field_type に応じた入力コンポーネントを返す純粋コンポーネント。

```typescript
interface DynamicFieldInputProps {
  schema: FieldSchema;
  value: unknown;
  onChange: (fieldName: string, value: unknown) => void;
  error?: string;
}
```

**field_type マッピング（要件 1.4）:**

| field_type | 入力コンポーネント |
|---|---|
| text | `<Input type="text">` |
| number | `<Input type="number">` |
| currency | 金額 Input + 通貨コード Select |
| percentage | `<Input type="number" min=0 max=100>` + % 表示 |
| date | `<Input type="date">` |
| boolean | `<input type="checkbox">` |
| list | 複数値入力（カンマ区切りまたは追加ボタン） |

### 4. バリデーションロジック（要件 2）

```typescript
const validateDynamicField = (
  schema: FieldSchema,
  value: unknown
): string | null => {
  if (schema.is_required && !value) return '必須項目です';
  
  const rules = schema.validation_rules;
  if (!rules) return null;
  
  if (rules.min !== undefined && Number(value) < rules.min)
    return `${rules.min} 以上の値を入力してください`;
  if (rules.max !== undefined && Number(value) > rules.max)
    return `${rules.max} 以下の値を入力してください`;
  if (rules.pattern && !new RegExp(rules.pattern).test(String(value)))
    return '入力形式が正しくありません';
  if (rules.options && !rules.options.includes(value))
    return `選択肢から選んでください: ${rules.options.join(', ')}`;
  
  return null;
};
```

### 5. 契約条件一覧での動的フィールド表示（要件 3.2）

`Contracts.tsx` の契約条件カード内に `dynamic_fields` の key-value を表示する。

```tsx
{contract.dynamic_fields && Object.entries(contract.dynamic_fields).map(([key, val]) => (
  <div key={key} className="contract-dynamic-field">
    <span className="contract-dynamic-field__label">{key}</span>
    <span className="contract-dynamic-field__value">{String(val)}</span>
  </div>
))}
```

### 6. Categories.tsx への FieldSchemaManager 統合（要件 4）

`FieldSchemaManager` コンポーネントは既に `genai/frontend/src/components/category/FieldSchemaManager.tsx` に実装済み。`Categories.tsx` のカテゴリ詳細セクションに組み込むだけ。

```tsx
// Categories.tsx 内
{selectedCategory && user?.role === 'admin' && (
  <FieldSchemaManager categoryId={selectedCategory.id} />
)}
```

## データモデル

### バックエンド変更（最小限）

`ContractCondition` モデルは既存の JSONB フィールドを活用するため、DB スキーマ変更は不要。ただし、`category_id` フィールドを `ContractCondition` に追加することで、どのカテゴリの動的フィールドが使われたかを記録できる。

**オプション**: `ContractCondition` に `category_id` カラムを追加（nullable）。

```python
# models.py への追加（オプション）
category_id: Mapped[Optional[int]] = mapped_column(
    Integer, ForeignKey("categories.id"), nullable=True
)
```

**必須**: `ContractConditionCreate` / `ContractConditionUpdate` スキーマに `dynamic_fields` を追加。

```python
# schemas.py への追加
class ContractConditionCreate(ContractConditionBase):
    dynamic_fields: Optional[dict[str, Any]] = None
    category_id: Optional[int] = None
```

### dynamic_fields の JSON 構造

```json
{
  "subscription_period_months": 12,
  "cancellation_fee_jpy": 5000,
  "trial_period_days": 30,
  "auto_renewal": true
}
```

## 正確性プロパティ

### Property 1: 動的フィールドのラウンドトリップ

任意の `dynamic_fields` dict を持つ ContractCondition を保存し、再取得した場合、`dynamic_fields` の内容が変化しない。

**検証対象: 要件 3.1, 3.3**

### Property 2: バリデーションの完全性

任意の FieldSchema（is_required=true）に対して、空値を入力した場合は必ずバリデーションエラーが発生し、送信ボタンが無効化される。

**検証対象: 要件 2.3, 2.4**

### Property 3: カテゴリ変更時のフィールドクリア

カテゴリ A のフィールドを入力後にカテゴリ B に変更した場合、カテゴリ A のフィールド値は全てクリアされる。

**検証対象: 要件 1.6**

### Property 4: display_order の順序保証

`getFieldSchemas` で取得した FieldSchema リストを display_order でソートした場合、常に昇順になる。

**検証対象: 要件 1.3**

## エラーハンドリング

| エラー状況 | 対応 |
|---|---|
| `getFieldSchemas` API 失敗 | エラーメッセージ表示、固定フィールドのみ表示継続 |
| `getCategories` API 失敗 | エラーメッセージ表示、カテゴリ選択なしで継続 |
| 必須フィールド未入力 | フィールド下にエラーメッセージ、送信ボタン無効化 |
| バリデーションルール違反 | フィールド下にエラーメッセージ、送信ボタン無効化 |
| 契約保存失敗 | 既存のエラーハンドリングに準拠 |

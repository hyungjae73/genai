---
inclusion: auto
---

# フルスタック統合チェック — DB・API・フロントエンド連携検証

## 目的

機能追加・変更時に、DB（モデル/マイグレーション）・バックエンドAPI（スキーマ/ルーター）・フロントエンド（型定義/API関数）の3層が一貫して連携されているかを自動的に検証する。

---

## 1. DB層チェック（models.py 変更時）

`models.py` を変更した場合、以下を必ず実行する:

- [ ] Alembic マイグレーションファイルを `genai/alembic/versions/` に作成した
- [ ] `down_revision` が最新の既存マイグレーションを指している
- [ ] `alembic upgrade head` を実行してマイグレーションを適用した
- [ ] `.kiro/specs/spec-dependencies.md` のマイグレーションチェーンを更新した

**新規カラム追加時の確認事項:**
- SQLAlchemy モデルのフィールド型と Alembic の `sa.Column` 型が一致しているか
- `nullable` / `server_default` の設定が既存データに影響しないか
- インデックスが必要なカラムに `Index()` を追加したか

---

## 2. バックエンドAPI層チェック（schemas.py / api/*.py 変更時）

`schemas.py` または `src/api/` 配下を変更した場合:

- [ ] Pydantic スキーマのフィールドが SQLAlchemy モデルのフィールドと一致している
- [ ] レスポンススキーマに `model_config = ConfigDict(from_attributes=True)` が設定されている
- [ ] 新規 APIルーターが `src/main.py` に `app.include_router()` で登録されている
- [ ] 新規エンドポイントに認証依存関数 `Depends(get_current_user_or_api_key)` が追加されている
- [ ] 書き込みエンドポイント（POST/PUT/DELETE）に適切な `require_role()` が設定されている

**型の整合性チェック:**
- Optional フィールドは `Optional[X]` で定義し、`None` を許容しているか
- 日時フィールドは `datetime` 型で統一されているか（文字列との混在に注意）
- JSONB フィールドは `dict` または `list` 型で定義されているか

---

## 3. フロントエンド層チェック（api.ts / *.tsx 変更時）

`genai/frontend/src/services/api.ts` または `*.tsx` を変更した場合:

- [ ] TypeScript の `interface` / `type` 定義がバックエンドの Pydantic スキーマと一致している
- [ ] 新規 API 関数が `api.ts` に追加されている（`export const get/create/update/delete...`）
- [ ] 新規フィールドが `optional` (`?`) か `required` かがバックエンドと一致している
- [ ] 新規ページが `App.tsx` のルーティングに追加されている
- [ ] ロール制御が必要なページに `<ProtectedRoute requiredRoles={[...]}>`  が設定されている
- [ ] 新規ナビゲーション項目が `AppLayout.tsx` の `navigationItems` に追加されている

---

## 4. 3層整合性チェック（機能追加完了時）

機能追加が完了したら、以下の整合性を確認する:

### DB ↔ バックエンド
| DB (models.py) | Backend (schemas.py) | 確認 |
|---|---|---|
| `column_name: Mapped[str]` | `field_name: str` | フィールド名・型が一致 |
| `nullable=True` | `Optional[str] = None` | Nullable は Optional |
| `server_default="false"` | `bool = False` | デフォルト値が一致 |

### バックエンド ↔ フロントエンド
| Backend (schemas.py) | Frontend (api.ts) | 確認 |
|---|---|---|
| `str` | `string` | 型マッピング |
| `Optional[str]` | `string \| null` または `string?` | Optional マッピング |
| `datetime` | `string` (ISO 8601) | 日時は文字列で受け取る |
| `list[str]` | `string[]` | 配列型 |
| `dict[str, Any]` | `Record<string, any>` | 辞書型 |

---

## 5. よくある連携ミスのパターン

### ❌ モデル追加後にマイグレーション忘れ
```python
# models.py に追加したが alembic upgrade head を実行していない
class NewModel(Base):
    __tablename__ = "new_table"
    ...
```
→ サービス起動時に `relation "new_table" does not exist` エラー

### ❌ スキーマとモデルのフィールド不一致
```python
# models.py
must_change_password: Mapped[bool] = mapped_column(Boolean, ...)

# schemas.py (フィールド追加忘れ)
class UserResponse(BaseModel):
    id: int
    username: str
    # must_change_password が抜けている！
```
→ フロントエンドで `undefined` になる

### ❌ APIルーター登録忘れ
```python
# src/api/new_feature.py を作成したが main.py に追加していない
from src.api.new_feature import router as new_feature_router
app.include_router(new_feature_router, prefix="/api/new-feature", ...)
```
→ 404 Not Found

### ❌ フロントエンド型定義の不一致
```typescript
// バックエンドが boolean を返すのに string で定義
interface User {
  is_active: string;  // ❌ boolean が正しい
}
```
→ 条件分岐が意図通りに動かない

### ❌ 認証 Depends 追加忘れ
```python
# 新規エンドポイントに認証を追加していない
@router.get("/sensitive-data")
async def get_sensitive_data(db: Session = Depends(get_db)):
    # current_user = Depends(get_current_user_or_api_key) が抜けている！
```
→ 未認証アクセスが可能になる

---

## 6. spec-dependencies.md の更新ルール

機能追加後、必ず `.kiro/specs/spec-dependencies.md` を更新する:

```markdown
| spec-name | 機能名 | in-progress | 
  DB: テーブル名/カラム名, Alembic: revision_id | 
  Frontend: 変更したページ/コンポーネント | 
  API: 追加したエンドポイント |
```

Reference: #[[file:.kiro/specs/spec-dependencies.md]]

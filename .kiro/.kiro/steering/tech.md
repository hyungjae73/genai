---
inclusion: auto
---

# Technology & Coding Constitution (技術・コード憲法)

本ドキュメントは、テスト戦略・言語バージョン・ライブラリ構文・リソース管理の不可侵ルールを定義する。
全ての新規実装・既存コード変更・spec作成時にこれらの原則を遵守すること。

## 1. プロパティベーステスト (PBT) の強制

単なる正常系のユニットテスト（Example-based test）だけでなく、エッジケースを網羅するために必ずPBTを実装せよ。

### バックエンド（Python）

- 複雑なデータパースや検証ロジックを作成した際は、必ず `Hypothesis` を用いて、ランダムな文字列や不正なHTML構造を入力とするテスト（`@given`）を生成せよ
- `@settings(max_examples=100)` を標準設定とする
- カスタムストラテジーは `genai/tests/strategies.py` に集約する
- プロパティテストファイルは `test_*_properties.py` の命名規則に従う

```python
# 必須パターン
from hypothesis import given, settings, strategies as st

@given(html=st.text(min_size=10, max_size=5000))
@settings(max_examples=100)
def test_parser_handles_arbitrary_html(html):
    """任意のHTML文字列でクラッシュしないことを検証"""
    result = parse(html)
    assert result is not None
```

### フロントエンド（TypeScript）

- 複雑な状態遷移や入力フォームのフックを作成した際は、`fast-check` と `Vitest` を用いてプロパティテストを記述せよ
- テストデータ生成には `Faker` を活用すること
- プロパティテストファイルは `*.property.test.ts` または `*.property.test.tsx` の命名規則に従う

```typescript
// 必須パターン
import fc from 'fast-check';

it('handles any valid input without crashing', () => {
  fc.assert(
    fc.property(fc.string(), (input) => {
      const result = processInput(input);
      expect(result).toBeDefined();
    }),
    { numRuns: 100 },
  );
});
```

### PBT実装が必須となるケース

- データパーサー（HTML, JSON-LD, Microdata, Open Graph）
- シリアライズ/デシリアライズ（CrawlContext to_dict/from_dict）
- 設定マージロジック（plugin_config 3層マージ）
- 価格比較・違反検出ロジック
- フォームバリデーション
- 状態遷移ロジック

## 2. TypeScript 5.9 と React 19 の最新記法

### TypeScript Strict モード

- `any` は絶対禁止。APIからのレスポンスは必ずZodや型定義で検証・キャストせよ
- `unknown` を使い、型ガードで安全にナローイングする

```typescript
// NG: any の使用
const data: any = await api.get('/sites');

// OK: 型定義 + バリデーション
interface SiteResponse { id: number; name: string; }
const data = await api.get<SiteResponse>('/sites');
```

### React 19 の新しいフック

- `use`, `useActionState` 等を積極的に活用する
- 旧来の冗長な `useEffect` によるデータフェッチは極力避ける
- データ取得はVite環境に適したSWRやReact Queryライクなカスタムフックに隠蔽せよ

```typescript
// NG: useEffect でデータフェッチ
useEffect(() => {
  fetchData().then(setData);
}, []);

// OK: カスタムフックに隠蔽
const { data, loading, error } = useSchedule(siteId);
```

## 3. SQLAlchemy 2.0 と Pydantic 2.5 の厳格な構文

### SQLAlchemy 2.0 スタイル

- 必ず `mapped_column` を使用する（旧 `Column()` は禁止）
- クエリは `select()` と `session.execute()` を推奨する

```python
# OK: 2.0 スタイル
class MonitoringSite(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

# OK: select() スタイル（推奨）
stmt = select(MonitoringSite).where(MonitoringSite.id == site_id)
result = session.execute(stmt).scalar_one_or_none()

# 許容: 既存コードの session.query() スタイル（新規コードでは select() を優先）
result = session.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
```

### Pydantic V2 メソッド

- `.dict()`, `.parse_obj()` の使用は禁止。必ず V2 メソッドを使用せよ

| 禁止（V1） | 必須（V2） |
|------------|-----------|
| `.dict()` | `.model_dump()` |
| `.parse_obj()` | `.model_validate()` |
| `.schema()` | `.model_json_schema()` |
| `Config` 内部クラス | `model_config = ConfigDict(...)` |

```python
# NG: V1 メソッド
data = schema.dict(exclude_unset=True)
obj = MyModel.parse_obj(raw_data)

# OK: V2 メソッド
data = schema.model_dump(exclude_unset=True)
obj = MyModel.model_validate(raw_data)
```

## 4. バックグラウンドワーカーのリソース管理

Playwright、Tesseract（画像処理）、BeautifulSoup（lxml）を扱う際は、メモリリークを防ぐため `with` 句（コンテキストマネージャ）を徹底せよ。

### 必須パターン

```python
# Playwright: BrowserPool の acquire/release パターン
browser, page = await pool.acquire()
try:
    # ページ操作
    await page.goto(url)
finally:
    await pool.release(browser, page)

# 画像処理: Pillow
from PIL import Image
with Image.open(path) as img:
    cropped = img.crop(bbox)
    cropped.save(output_path)

# BeautifulSoup: 明示的な decompose
soup = BeautifulSoup(html, "html.parser")
try:
    # パース処理
    result = extract_data(soup)
finally:
    soup.decompose()  # メモリ解放

# ファイル操作
with open(path, 'rb') as f:
    content = f.read()
```

### 禁止パターン

```python
# NG: リソースリーク
img = Image.open(path)
cropped = img.crop(bbox)  # img が閉じられない

# NG: BrowserPool の release 忘れ
browser, page = await pool.acquire()
await page.goto(url)  # 例外発生時に release されない
```

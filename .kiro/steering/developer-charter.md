---
inclusion: auto
---

# 開発憲章（Developer Charter）

本プロジェクトの全開発者（人間・AI エージェント問わず）が遵守すべき7つの規約。
違反はコードレビューで即座にリジェクトする。

---

## 1. データベース・非同期 ORM 憲章（FastAPI + SQLAlchemy 2.0）

### 規約 1: Lazy Loading の禁止

AsyncSession でリレーション属性（例: `review_item.alert`）にアクセスすると、
データ未ロード時に同期クエリが発行され `MissingGreenlet` でクラッシュする。

```python
# ❌ 禁止: Lazy Loading（暗黙の同期クエリ）
item = (await db.execute(select(ReviewItem))).scalar_one()
alert = item.alert  # → MissingGreenlet 例外

# ✅ 必須: Eager Loading（明示的な事前取得）
from sqlalchemy.orm import selectinload
stmt = select(ReviewItem).options(selectinload(ReviewItem.alert))
item = (await db.execute(stmt)).scalar_one()
alert = item.alert  # → 安全にアクセス可能
```

使い分け:
- `selectinload` — 1:N リレーション（サブクエリで一括取得）
- `joinedload` — N:1 リレーション（JOIN で同時取得）

### 規約 2: 自動コミットの禁止（トランザクション境界の明示）

`get_async_db` 依存関数内で `commit()` を呼ばない。
GET リクエストで無駄なコミットラウンドトリップが発生するため。

```python
# ❌ 禁止: 依存関数内での自動コミット
async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session
        await session.commit()  # ← GET でも毎回コミットされる

# ✅ 必須: Service 層 / エンドポイントでの明示的コミット
async def create_site(site: SiteCreate, db: AsyncSession = Depends(get_async_db)):
    db.add(MonitoringSite(**site.dict()))
    await db.commit()  # ← POST/PUT/DELETE のみ
```

---

## 2. 非同期タスク・パイプライン憲章（Celery + Redis）

### 規約 3: タスクの冪等性（Idempotency）の強制

ネットワークエラーで Celery タスクが複数回実行されてもシステム状態が壊れないこと。

```python
# ❌ 禁止: 重複レコード生成
@celery_app.task
def process_crawl(site_id):
    result = CrawlResult(site_id=site_id, ...)
    db.add(result)  # → 2回実行で2レコード

# ✅ 必須: 既存チェック or upsert
@celery_app.task
def process_crawl(site_id):
    existing = db.query(CrawlResult).filter_by(
        site_id=site_id, job_id=current_job_id
    ).first()
    if existing:
        return  # 冪等: 既に処理済み
    db.add(CrawlResult(site_id=site_id, job_id=current_job_id, ...))
```

### 規約 4: ペイロードの最小化（ID 渡し原則）

Redis ブローカー経由のタスク引数に巨大オブジェクトを渡さない。

```python
# ❌ 禁止: HTML 全体をタスク引数に渡す
celery_app.send_task("crawl_task", args=[site_id, html_content])  # → Redis メモリ枯渇

# ✅ 必須: ID のみ渡し、ワーカー側で DB/MinIO から取得
celery_app.send_task("crawl_task", args=[site_id])
# ワーカー内で:
crawl_result = db.query(CrawlResult).filter_by(site_id=site_id).first()
html = crawl_result.html_content
```

---

## 3. フロントエンド状態管理憲章（React + TanStack Query）

### 規約 5: サーバー状態と UI 状態の厳格な分離

API データを `useState` にコピーしない。TanStack Query のキャッシュが唯一の真実。

```tsx
// ❌ 禁止: サーバーデータを useState にコピー
const [sites, setSites] = useState([]);
const { data } = useSites();
useEffect(() => { setSites(data ?? []); }, [data]);  // → Stale State, 無限ループのリスク

// ✅ 必須: TanStack Query の返り値を直接使用
const { data: sites = [], isLoading } = useSites();
// useState はモーダル開閉・フォーム入力など UI 状態のみ
const [isModalOpen, setIsModalOpen] = useState(false);
```

Celery タスクを伴う操作のキャッシュ無効化:
```tsx
// ❌ 禁止: 202 Accepted 受信時に即座にキャッシュ無効化
onSuccess: () => queryClient.invalidateQueries(['sites'])  // → ワーカー未完了で古いデータ

// ✅ 必須: タスクステータスポーリングが SUCCESS を返した時に無効化
refetchInterval: (query) => {
  if (query.state.data?.status === 'SUCCESS') {
    queryClient.invalidateQueries({ queryKey: ['sites'] });
    return false;
  }
  return status === 'PENDING' || status === 'STARTED' ? 2000 : false;
}
```

---

## 4. クローラ・スクレイピング憲章（Playwright）

### 規約 6: 脆いセレクタの原則禁止

対象サイトの DOM 構造変更に耐性のあるセレクタを使用する。

```python
# ❌ 禁止: 階層依存の CSS セレクタ
await page.locator('div.product > ul > li:nth-child(2) > span.price').text_content()

# ❌ 禁止: 脆い XPath
await page.locator('//div[@class="product"]/ul/li[2]/span').text_content()

# ✅ 推奨: アクセシビリティベースのセレクタ
await page.get_by_role('button', name='購入').click()
await page.get_by_text('¥').text_content()
await page.get_by_label('数量').fill('1')

# ✅ 許容: data-testid（自社サイトの E2E テスト用）
await page.locator('[data-testid="price-display"]').text_content()
```

外部サイトのスクレイピングでは構造化データ（JSON-LD, product.json）を優先し、
DOM 解析は最終手段とする。

---

## 5. リトライとエラーハンドリング憲章（Tenacity）

### 規約 7: サイレントフェイラーの禁止とログの統一

例外を握りつぶさない。リトライの発生理由を必ずログに記録する。

```python
# ❌ 厳禁: 例外の握りつぶし
try:
    await call_external_api()
except Exception:
    pass  # → 何が起きたか追跡不能

# ❌ 禁止: Tenacity で before_sleep_log なし
@with_retry(retry_on=(ConnectionError,))  # → リトライが無言で実行される

# ✅ 必須: src/core/retry.py の with_retry を使用（before_sleep_log 組み込み済み）
from src.core.retry import with_retry

@with_retry(
    retry_on=(httpx.ConnectError, httpx.TimeoutException),
    max_attempts=3,
)
async def fetch_external():
    ...  # → リトライ時に WARNING ログ + trace_id が自動出力される
```

リトライ対象の判断基準:
- ✅ リトライする: HTTP 429, HTTP 5xx, ConnectionError, TimeoutError
- ❌ リトライしない: HTTP 4xx (400/401/403/404), ValidationError, ビジネスロジックエラー

---

## 規約一覧（クイックリファレンス）

| # | 領域 | 規約 | 一言 |
|---|------|------|------|
| 1 | DB/ORM | Lazy Loading 禁止 | `selectinload` / `joinedload` を使え |
| 2 | DB/ORM | 自動コミット禁止 | Service 層で明示的 `await db.commit()` |
| 3 | Celery | 冪等性の強制 | upsert or 既存チェック必須 |
| 4 | Celery | ID 渡し原則 | タスク引数は ID のみ、データはワーカーで取得 |
| 5 | Frontend | サーバー/UI 状態分離 | API データを useState にコピーするな |
| 6 | Playwright | 脆いセレクタ禁止 | getByRole / getByText を使え |
| 7 | Tenacity | サイレントフェイラー禁止 | try-except pass 厳禁、with_retry を使え |

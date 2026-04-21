---
inclusion: auto
---

# Architecture Constitution (アーキテクチャ憲法)

本ドキュメントは、システムのキュー分離・レイヤー境界・同期/非同期の厳密なルールを定義する。
全ての新規実装・既存コード変更・spec作成時にこれらの原則を遵守すること。

## 1. Celeryキューの厳格なルーティング

非同期タスクは、Docker Composeで定義された以下の4キューに厳密にルーティングせよ。絶対に混同してはならない。

| キュー | 用途 | concurrency | 依存技術 |
|--------|------|-------------|----------|
| `crawl` | Playwrightによるサイトクロール専用 | 2 | Playwright, BrowserPool |
| `extract` | BeautifulSoup/lxml, Tesseractによる抽出専用 | 8 | BeautifulSoup4, pytesseract, Pillow |
| `validate` | Pydanticやscikit-learnによるデータ検証・解析専用 | 8 | Pydantic, scikit-learn |
| `report` | MinIOへの保存やDBへの書き込み、通知（SendGrid/Slack）専用 | 4 | MinIO SDK, SQLAlchemy, SendGrid, slack-sdk |

### ルーティングルール

- `celery_app.py` の `PIPELINE_TASK_ROUTES` でタスク→キューのマッピングを定義
- 新規タスク追加時は必ず対応するキューにルーティングを設定すること
- `crawl` キューのワーカーのみ Playwright + BrowserPool を初期化（`worker_init` シグナル）
- `extract` / `validate` ワーカーは Playwright を初期化しない（メモリ節約）
- `report` ワーカーは DB接続 + MinIO接続を持つ

### 違反例（やってはいけないこと）

- `crawl` キューのタスク内でDB書き込みを行う → `report` キューで行え
- `extract` キューのタスク内でPlaywrightを使う → `crawl` キューで行え
- キュー指定なしでタスクを定義する → デフォルトキューに落ちてリソース競合が発生する

## 2. フロントエンドのコンポーネント設計 (Feature-Sliced Design)

Reactコンポーネントは、責務に応じて厳密に分割せよ。

| ディレクトリ | 責務 | 含めるもの | 含めないもの |
|-------------|------|-----------|-------------|
| `pages/` | React Routerのエントリーポイント | レイアウト、コンテキストプロバイダ | ビジネスロジック、API呼び出し |
| `features/` (※) | ドメインごとのUI | Hooks、API呼び出し（Axios）、ドメイン固有コンポーネント | 汎用UIコンポーネント |
| `components/ui/` | 純粋なプレゼンテーショナルコンポーネント | Chart.js/Rechartsラッパー、Button、Input、Modal、Table、Card | ドメイン知識、API呼び出し |
| `components/hierarchy/` | サイト管理ドメインのコンポーネント | SiteDetailPanel、タブ群、CustomerGroup、SiteRow | 他ドメインのロジック |
| `api/` | APIクライアント関数 | Axios呼び出し、型定義 | UIロジック |
| `services/` | 共通サービス | Axiosインスタンス設定、認証ヘッダー | コンポーネント |

※ 現在は `components/hierarchy/` が features 層の役割を担っている。将来的に `features/` ディレクトリへの移行を検討。

### コンポーネント設計ルール

- `pages/` のコンポーネントは直接 `axios` を呼ばない。`api/` または `features/` 経由で呼ぶ
- `components/ui/` のコンポーネントは `props` のみで動作し、外部状態に依存しない
- タブコンポーネント（ContractTab, ScreenshotTab等）は `siteId: number` を受け取り、自身でデータフェッチする

## 3. 同期・非同期の境界防御（psycopg2-binary問題の回避）

**警告:** DBドライバに同期型の `psycopg2-binary` を使用している。

FastAPIのルーター関数を `async def` で定義し、その中で直接DBアクセスを行うとイベントループがブロックされる。

### 必須ルール

- DBアクセスを伴うFastAPIのエンドポイントは、必ず通常の `def`（同期関数）として定義するか、`run_in_threadpool` を利用せよ
- `async def` エンドポイントで `db.query()` を直接呼んではならない

### 安全なパターン

```python
# パターン1: 同期関数（推奨）
@router.get("/sites/{site_id}")
def get_site(site_id: int, db: Session = Depends(get_db)):
    return db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()

# パターン2: run_in_threadpool
from starlette.concurrency import run_in_threadpool

@router.get("/sites/{site_id}")
async def get_site(site_id: int, db: Session = Depends(get_db)):
    return await run_in_threadpool(
        lambda: db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
    )
```

### 危険なパターン（やってはいけない）

```python
# NG: async def + 直接DB呼び出し → イベントループブロック
@router.get("/sites/{site_id}")
async def get_site(site_id: int, db: Session = Depends(get_db)):
    return db.query(MonitoringSite).filter(MonitoringSite.id == site_id).first()
```

### 注意事項

- 現在の既存エンドポイントの一部は `async def` + 直接DBアクセスのパターンを使用している（技術的負債）
- 新規エンドポイント作成時は必ず上記の安全なパターンに従うこと
- 将来的に `asyncpg` への移行を検討する場合は、全エンドポイントの `async def` 化が可能になる

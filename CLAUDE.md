# Payment Compliance Monitor — Claude Code Context

決済条件監視システム（Payment Compliance Monitor）の開発コンテキスト。
加盟店ECサイトの契約条件違反・ダークパターン・偽サイトを自動検出する。

---

## 開発コマンド

```bash
# バックエンドテスト（-x で最初の失敗で停止）
cd genai && pytest tests/ -x --tb=short

# フロントエンドテスト（watch モードなし）
cd genai/frontend && npm run test -- --run

# DB マイグレーション適用
cd genai && alembic upgrade head

# Docker 環境起動
cd genai && docker compose up -d

# バックエンド起動（ローカル）
cd genai && uvicorn src.main:app --reload

# フロントエンド起動（ローカル）
cd genai/frontend && npm run dev
```

---

## プロジェクト構造

```
genai/
├── src/
│   ├── main.py              # FastAPI アプリ + ルーター登録
│   ├── models.py            # SQLAlchemy 2.0 モデル（全テーブル）
│   ├── api/schemas.py       # Pydantic V2 スキーマ（全エンドポイント）
│   ├── api/                 # FastAPI ルーター群
│   ├── pipeline/            # CrawlPipeline + プラグイン群
│   │   └── plugins/         # 各ステージのプラグイン
│   ├── review/              # 手動審査ワークフロー
│   ├── auth/                # JWT認証・RBAC・レートリミット
│   └── rules/               # 動的コンプライアンスルールエンジン
├── tests/                   # pytest テスト（Hypothesis PBT含む）
├── alembic/versions/        # DB マイグレーションファイル
├── frontend/src/
│   ├── pages/               # React Router エントリーポイント
│   ├── components/          # UIコンポーネント群
│   ├── services/api.ts      # Axios API クライアント
│   └── lib/queryClient.ts   # TanStack Query クライアント
└── .kiro/
    ├── specs/               # 機能仕様書（requirements/design/tasks）
    └── journal/             # 開発ジャーナル（sessions/topics）
```

---

## アーキテクチャ憲法（不可侵）

### 1. Celery キュー4分離厳格化

| キュー | 用途 | concurrency |
|--------|------|-------------|
| `crawl` | Playwright クロール専用 | 2 |
| `extract` | BeautifulSoup/OCR 抽出専用 | 8 |
| `validate` | データ検証・解析専用 | 8 |
| `report` | DB書き込み・通知専用 | 4 |

**禁止**: `crawl` キューでDB書き込み、`extract` キューでPlaywright使用

### 2. フロントエンド Feature-Sliced Design

| ディレクトリ | 責務 |
|-------------|------|
| `pages/` | ルートエントリーポイントのみ（API呼び出し禁止） |
| `components/hierarchy/` | ドメインコンポーネント（API呼び出し可） |
| `components/ui/` | 純粋プレゼンテーション（props のみ） |
| `services/api.ts` | Axios API クライアント関数 |

### 3. 同期/非同期境界防御

```python
# ✅ 安全: AsyncSession を使用（production-readiness 移行済み）
@router.get("/sites/{site_id}")
async def get_site(site_id: int, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(select(MonitoringSite).where(...))
    return result.scalar_one_or_none()

# ⚠️ AlertPlugin 等の sync session factory コンテキストでは:
from sqlalchemy.ext.asyncio import AsyncSession
if isinstance(session, AsyncSession):
    await svc.enqueue_from_alert(alert)  # async メソッドは AsyncSession 時のみ呼ぶ
```

---

## プロダクト憲法（不可侵）

### 1. 非同期 UX
- 長時間処理は `202 Accepted` + `task_id` を即座に返す
- フロントエンドはポーリングで進捗取得（ローディングスピナーで待たせない）

### 2. 証拠保全
- 全スクリーンショット・ROI画像・生HTMLは MinIO に保存必須
- フロントエンドは `react-zoom-pan-pinch` でビューア実装必須

### 3. エラーハンドリング
- 画面クラッシュ禁止（Error Boundary 2層）
- 4xx: ユーザー入力起因、5xx: システム起因で分離表示

---

## 開発憲章（7規約）

| # | 規約 | 内容 |
|---|------|------|
| 1 | Lazy Loading 禁止 | `selectinload` / `joinedload` で Eager Loading |
| 2 | 自動コミット禁止 | Service 層で明示的 `await db.commit()` |
| 3 | 冪等性保証 | upsert or 既存チェック必須（Celery リトライ対策） |
| 4 | ID 渡し原則 | タスク引数は ID のみ、データはワーカーで取得 |
| 5 | サーバー/UI 状態分離 | API データを `useState` にコピーしない（TanStack Query を使う） |
| 6 | 脆いセレクタ禁止 | `getByRole` / `getByText` を使う |
| 7 | サイレントフェイラー禁止 | `except: pass` 厳禁、`with_retry` を使う |

---

## テスト方針

```ini
# pytest.ini（Zero Warning Policy）
filterwarnings = error
```

- **Hypothesis PBT 必須**: 複雑なパース・検証ロジックには `@given` テストを追加
- **テスト認証**: `headers={"X-API-Key": "dev-api-key"}` で統一
- **テスト DB**: testcontainers-python（PostgreSQL コンテナ自動管理）
- **フロントエンド PBT**: `fast-check` + Vitest

---

## SQLAlchemy 2.0 / Pydantic V2 必須構文

```python
# SQLAlchemy 2.0: mapped_column 必須
class MonitoringSite(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

# Pydantic V2: model_dump / model_validate 必須（.dict() / .parse_obj() 禁止）
data = schema.model_dump(exclude_unset=True)
obj = MyModel.model_validate(raw_data)

# Pydantic V2: ConfigDict 必須（class Config 禁止）
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
```

---

## 認証・RBAC

```python
# 全エンドポイントに認証必須
from src.auth.dependencies import get_current_user_or_api_key, require_role
from src.auth.rbac import Role

@router.get("/reviews")
async def list_reviews(
    current_user = Depends(get_current_user_or_api_key),  # 認証
    db: AsyncSession = Depends(get_async_db),
):
    ...

@router.post("/reviews/{id}/final-decide")
async def final_decide(
    current_user = Depends(require_role(Role.ADMIN)),  # admin のみ
    ...
):
    ...
```

**ロール**: `admin`（全権限）/ `reviewer`（審査操作）/ `viewer`（読み取り専用）

---

## DB マイグレーション チェックリスト

`models.py` を変更したら必ず:

1. `genai/alembic/versions/` にマイグレーションファイルを作成
2. `down_revision` を最新マイグレーションに設定
3. `cd genai && alembic upgrade head` を実行
4. `.kiro/specs/spec-dependencies.md` のマイグレーションチェーンを更新

**現在の HEAD**: `p1q2r3s4t5u6`（review_items, review_decisions テーブル）

---

## フルスタック整合性チェック

機能追加完了時に確認:

- [ ] `models.py` 変更 → Alembic マイグレーション作成・適用済み
- [ ] `schemas.py` 変更 → モデルフィールドと一致している
- [ ] 新規 API ルーター → `src/main.py` に `app.include_router()` 登録済み
- [ ] 新規エンドポイント → `Depends(get_current_user_or_api_key)` 追加済み
- [ ] フロントエンド型定義 → バックエンドスキーマと一致している
- [ ] 新規ページ → `App.tsx` ルーティング + `AppLayout.tsx` ナビゲーション追加済み

---

## パイプラインアーキテクチャ

```
CrawlPipeline (4ステージ)
├── Stage 1: PageFetcher    → LocalePlugin, PreCaptureScriptPlugin, JourneyPlugin, ModalDismissPlugin
├── Stage 2: DataExtractor  → StructuredDataPlugin, ShopifyPlugin, HTMLParserPlugin, OCRPlugin,
│                             CSSVisualPlugin, LLMClassifierPlugin
├── Stage 3: Validator      → ContractComparisonPlugin, UITrapPlugin, EvidencePreservationPlugin
└── Stage 4: Reporter       → DBStoragePlugin, ObjectStoragePlugin, AlertPlugin, NotificationPlugin
                              ↓ (DarkPatternScore ポストプロセス: Validator → Reporter 間)
```

**DarkPatternScore**: Max Pooling 方式、未実行プラグインにペナルティ 0.15、閾値 0.6 で `high_dark_pattern_risk` 違反追加

---

## 重要な設計決定

- **passlib 排除済み**: `bcrypt` 直接使用（`src/auth/password.py`）
- **AlertPlugin async/sync 境界**: `isinstance(session, AsyncSession)` チェック後に async メソッド呼び出し
- **misleading_font_size 検出**: `MISLEADING_FONT_SIZE_RATIO` 環境変数（デフォルト 0.75）で閾値設定
- **OCR スマートリトライ**: 信頼度 0% → 5秒待機 → 再取得 → リトライ → 失敗時は審査キューに投入
- **テスト日時**: `toLocaleString('ja-JP')` は TZ 依存のため、テストでは動的計算を使う

---

## 仕様書・ジャーナルの場所

```
.kiro/specs/{spec-name}/
  ├── requirements.md   # 要件定義
  ├── design.md         # 設計書
  └── tasks.md          # 実装タスク一覧

.kiro/journal/
  ├── topics/           # テーマ別まとめ（architecture, decisions, tech-stack 等）
  └── sessions/         # セッション別記録
```

**完了済み Spec**: crawl-pipeline-architecture, dark-pattern-notification, stealth-browser-hardening, advanced-dark-pattern-detection, user-auth-rbac, manual-review-workflow, verification-flow-restructure, dynamic-contract-form, production-readiness-improvements

---

## デバッグ原則

1. **RCA 先行**: エラー修正前に根本原因を特定してから修正コードを書く
2. **Warning = Error**: `pytest.ini` の `filterwarnings = error` を削除・無効化しない
3. **テスト改ざん禁止**: 実装バグでテストが落ちた場合、テスト側のアサーションを削除しない
4. **ボーイスカウト規則**: 既存ファイルを開いたら技術的負債も修正する

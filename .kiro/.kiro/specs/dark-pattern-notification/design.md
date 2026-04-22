# Design Document: Dark Pattern Notification

## Overview

本設計は、CrawlPipeline の Reporter ステージに NotificationPlugin を追加し、ダークパターン違反検出時に Slack および メール で担当者へ通知する機能を実現する。

現状、AlertPlugin が違反検出時に Alert レコードを DB に保存しているが、外部通知は旧フロー（`AlertSystem`）でのみ実装されている。本機能では以下を実現する:

1. **NotificationPlugin**: CrawlPlugin を継承し、AlertPlugin の後に実行される Reporter ステージプラグイン
2. **通知チャネル**: Slack Incoming Webhook と SMTP メールの2チャネル
3. **3層設定マージ**: グローバル環境変数 → サイト単位 plugin_config → 環境変数オーバーライド
4. **重複通知抑制**: NotificationRecord テーブルによる時間窓ベースの重複判定
5. **非同期送信**: Celery タスク `send_notification` による非同期通知送信（フォールバック: 同期送信）
6. **管理API**: 通知設定の取得/更新 API と通知履歴 API

### 設計判断

- **Celery タスク分離**: 通知送信はパイプライン実行時間に影響させないため、Celery タスクとして非同期実行する。Celery ワーカー不可時は同期フォールバックで信頼性を確保する。
- **3層マージの純粋関数化**: 既存の `resolve_plugin_config()` パターンに倣い、通知設定マージも純粋関数として実装し、テスタビリティを確保する。
- **テンプレートエンジン不使用**: Python の `str.format_map()` + `defaultdict` で十分。外部テンプレートエンジンの依存追加は不要。
- **重複判定キー**: `(site_id, violation_type)` の組み合わせで判定。同一サイトの異なる違反種別は独立して通知する。
- **2層リトライ戦略**: HTTP送信レベル（1s, 2s, 4s の指数バックオフ、最大3回）と Celery タスクレベル（60秒間隔、最大3回）の2層。HTTP リトライは `send_notification` タスク内の `_send_slack()` / `_send_email()` で実装し、全HTTP リトライ失敗後に Celery タスクリトライが発動する。
- **メール受信者の解決**: Customer.email をベース受信者とし、plugin_config の `additional_email_recipients` を追加受信者としてマージする。`merge_notification_config` は Customer.email を第1引数として受け取り、`email_recipients` リストの先頭に配置する。
- **重複判定の楽観的アプローチ**: 重複判定は NotificationPlugin.execute() 内で同期的に実行し、Celery タスク側では再判定しない。パイプライン実行間隔（通常数時間〜1日）を考慮すると、レースコンディションのリスクは許容範囲内。

## Architecture

### パイプライン統合

```mermaid
graph LR
    subgraph Reporter Stage
        A[DBStoragePlugin] --> B[AlertPlugin]
        B --> C[NotificationPlugin]
    end
    C -->|async| D[Celery: send_notification]
    D --> E[Slack Webhook]
    D --> F[SMTP Email]
    D --> G[NotificationRecord DB]
```

### 通知フロー

```mermaid
sequenceDiagram
    participant Pipeline as CrawlPipeline
    participant NP as NotificationPlugin
    participant Cfg as ConfigMerger
    participant Dup as DuplicateChecker
    participant Tpl as TemplateRenderer
    participant Celery as Celery Worker
    participant Slack as Slack API
    participant SMTP as SMTP Server
    participant DB as Database

    Pipeline->>NP: execute(ctx)
    NP->>Cfg: merge_notification_config(env, site_config)
    Cfg-->>NP: merged_config
    NP->>Dup: check_duplicates(site_id, violation_types, window)
    Dup->>DB: SELECT from notification_records
    DB-->>Dup: existing records
    Dup-->>NP: new_violation_types (filtered)
    NP->>Tpl: render(violations, config)
    Tpl-->>NP: slack_payload, email_body
    NP->>Celery: send_notification.delay(payload)
    Note over NP: パイプラインは待機せず続行
    Celery->>Slack: POST webhook (with retry)
    Celery->>SMTP: send email (with retry)
    Celery->>DB: INSERT NotificationRecord
    Celery->>DB: UPDATE Alert.slack_sent / email_sent
```

### 設定マージフロー

```mermaid
graph TD
    A[グローバル環境変数] -->|ベース| M[merge_notification_config]
    B[サイト plugin_config.params.NotificationPlugin] -->|上書き| M
    C[NOTIFICATION_OVERRIDE_DISABLED] -->|緊急停止| M
    M --> D[merged NotificationConfig]
```

## Components and Interfaces

### 1. NotificationPlugin (CrawlPlugin)

```python
class NotificationPlugin(CrawlPlugin):
    """Reporter ステージ通知プラグイン。AlertPlugin 実行後に動作。"""

    def __init__(self, session_factory=None, celery_app=None):
        self._session_factory = session_factory
        self._celery_app = celery_app

    def should_run(self, ctx: CrawlContext) -> bool:
        """violations >= 1 かつ 通知チャネルが1つ以上有効。"""
        ...

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """通知設定マージ → 重複判定 → テンプレート生成 → Celery投入。"""
        ...
```

### 2. merge_notification_config (純粋関数)

```python
@dataclass
class NotificationConfig:
    slack_enabled: bool
    slack_webhook_url: str | None
    slack_channel: str
    email_enabled: bool
    email_recipients: list[str]  # Customer.email + additional_email_recipients
    suppression_window_hours: int

def merge_notification_config(
    customer_email: str,
    site_config: dict | None = None,
) -> NotificationConfig:
    """3層マージ: 環境変数 → site plugin_config → オーバーライド。
    
    メール受信者の解決順序 (Req 3.2, 4.3):
    1. Customer.email をベース受信者として email_recipients の先頭に配置
    2. site plugin_config の additional_email_recipients を追加
    3. 重複を除去
    
    純粋関数（環境変数読み取りを除く）。テスト時は env_overrides で注入可能。
    """
    ...
```

### 3. NotificationTemplateRenderer

```python
class NotificationTemplateRenderer:
    """違反情報からSlack/メール通知メッセージを生成する。"""

    def render_slack_payload(
        self, violations: list[dict], config: NotificationConfig, site: MonitoringSite
    ) -> dict:
        """Slack Block Kit 形式のペイロードを生成。severity 色分け付き。"""
        ...

    def render_email(
        self, violations: list[dict], config: NotificationConfig, site: MonitoringSite
    ) -> tuple[str, str]:
        """(subject, body) タプルを返す。"""
        ...

    def render_violation_fields(self, violation: dict, site: MonitoringSite) -> dict[str, str]:
        """違反 dict からテンプレートフィールド値を抽出。欠損値は 'N/A'。"""
        ...
```

### 4. DuplicateSuppressionChecker

```python
class DuplicateSuppressionChecker:
    """NotificationRecord テーブルを参照し重複通知を判定する。"""

    def __init__(self, session_factory):
        self._session_factory = session_factory

    def filter_new_violations(
        self, site_id: int, violation_types: list[str], window_hours: int
    ) -> list[str]:
        """重複でない violation_type のリストを返す。"""
        ...
```

### 5. Celery タスク: send_notification

リトライは2層構造:
- **HTTP送信レベル**: `_send_slack()` / `_send_email()` 内で最大3回リトライ（指数バックオフ: 1s, 2s, 4s）。Req 2.4, 3.5 準拠。
- **Celery タスクレベル**: HTTP送信レベルの全リトライ失敗後、Celery の `self.retry()` で最大3回リトライ（60秒間隔）。Req 8.3 準拠。

```python
@celery_app.task(
    bind=True,
    name="src.notification_tasks.send_notification",
    queue="notification",
    max_retries=3,
    default_retry_delay=60,
)
def send_notification(self, payload: dict) -> dict:
    """Slack/メール送信 → NotificationRecord 保存 → Alert フラグ更新。
    
    内部で _send_slack() / _send_email() を呼び出し、各メソッドは
    HTTP レベルで最大3回リトライ（1s, 2s, 4s 指数バックオフ）を行う。
    全 HTTP リトライ失敗後、Celery タスクリトライが発動する。
    """
    ...

def _send_slack(webhook_url: str, payload: dict) -> bool:
    """Slack Webhook に POST。HTTP レベルで最大3回リトライ（1s, 2s, 4s）。"""
    for attempt in range(3):
        try:
            resp = httpx.post(webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2 ** attempt)  # 1s, 2s, 4s
    return False

def _send_email(recipients: list[str], subject: str, body: str) -> bool:
    """SMTP メール送信。HTTP レベルで最大3回リトライ（1s, 2s, 4s）。"""
    for attempt in range(3):
        try:
            # SMTP 送信処理
            return True
        except Exception:
            pass
        time.sleep(2 ** attempt)  # 1s, 2s, 4s
    return False
```

### 6. API エンドポイント

```python
# GET /api/sites/{site_id}/notification-config
# PUT /api/sites/{site_id}/notification-config
# GET /api/sites/{site_id}/notifications
```

## Data Models

### NotificationRecord テーブル

```python
class NotificationRecord(Base):
    __tablename__ = "notification_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("monitoring_sites.id"), nullable=False
    )
    alert_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("alerts.id"), nullable=True
    )
    violation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)  # 'slack' or 'email'
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)  # 'sent', 'failed', 'skipped'
    sent_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    site: Mapped["MonitoringSite"] = relationship("MonitoringSite")
    alert: Mapped[Optional["Alert"]] = relationship("Alert")

    __table_args__ = (
        Index("ix_notification_records_site_violation_sent",
              "site_id", "violation_type", "sent_at"),
        Index("ix_notification_records_alert_id", "alert_id"),
    )
```

### NotificationConfig データクラス (in-memory)

```python
@dataclass
class NotificationConfig:
    slack_enabled: bool = False
    slack_webhook_url: str | None = None
    slack_channel: str = "#alerts"
    email_enabled: bool = True
    email_recipients: list[str] = field(default_factory=list)
    suppression_window_hours: int = 24
```

### Celery キュー追加

```python
# celery_app.py に追加
Queue('notification', routing_key='notification')

# タスクルーティング追加
'src.notification_tasks.send_notification': {'queue': 'notification'}
```

### docker-compose.yml: notification-worker 追加

```yaml
notification-worker:
  build:
    context: .
    dockerfile: docker/Dockerfile
  container_name: payment-monitor-notification-worker
  command: celery -A src.celery_app worker -Q notification --loglevel=info --concurrency=4
  environment:
    - DATABASE_URL=postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    - REDIS_URL=redis://redis:6379/0
    - CELERY_BROKER_URL=redis://redis:6379/0
    - CELERY_RESULT_BACKEND=redis://redis:6379/0
    - NOTIFICATION_SLACK_WEBHOOK_URL=${NOTIFICATION_SLACK_WEBHOOK_URL:-}
    - NOTIFICATION_SLACK_ENABLED=${NOTIFICATION_SLACK_ENABLED:-false}
    - NOTIFICATION_EMAIL_ENABLED=${NOTIFICATION_EMAIL_ENABLED:-true}
    - SMTP_HOST=${SMTP_HOST:-localhost}
    - SMTP_PORT=${SMTP_PORT:-587}
  env_file:
    - .env
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
  networks:
    - payment-monitor-network
```

### API スキーマ

```python
class NotificationConfigResponse(BaseModel):
    slack_enabled: bool
    slack_webhook_url: str | None  # マスク済み
    slack_channel: str
    email_enabled: bool
    email_recipients: list[str]
    suppression_window_hours: int

class NotificationConfigUpdate(BaseModel):
    slack_enabled: bool | None = None
    slack_webhook_url: str | None = None
    slack_channel: str | None = None
    email_enabled: bool | None = None
    additional_email_recipients: list[str] | None = None
    suppression_window_hours: int | None = Field(None, ge=1, le=168)

class NotificationHistoryResponse(BaseModel):
    id: int
    violation_type: str
    channel: str
    recipient: str
    status: str
    sent_at: datetime

class PaginatedNotificationHistoryResponse(BaseModel):
    items: list[NotificationHistoryResponse]
    total: int
    limit: int
    offset: int
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: should_run reflects violations and channel availability

*For any* CrawlContext and notification configuration, `should_run()` returns `True` if and only if `len(ctx.violations) >= 1` AND at least one notification channel (Slack or email) is enabled in the merged config.

**Validates: Requirements 1.2**

### Property 2: execute records metadata with notification_ prefix

*For any* CrawlContext with violations and a valid notification config, after `execute()` completes (success or failure), the returned context's `metadata` dict contains at least one key with the `notification_` prefix.

**Validates: Requirements 1.4**

### Property 3: execute never raises exceptions

*For any* CrawlContext (including contexts that trigger internal errors), calling `execute()` never raises an exception. Errors are appended to `ctx.errors` and the context is returned.

**Validates: Requirements 1.5**

### Property 4: Slack payload contains all required violation fields

*For any* violation dict and MonitoringSite, the rendered Slack Block Kit payload contains: site name, violation type, severity, and detected_at. When present in the violation, it also contains detected price and evidence URL.

**Validates: Requirements 2.2, 2.3**

### Property 5: Slack severity color mapping

*For any* severity value in `{"warning", "critical", "info"}`, the Slack payload attachment color matches the specified mapping (warning → yellow/`#FFA500`, critical → red/`#FF0000`, info → blue/`#0000FF`).

**Validates: Requirements 2.3**

### Property 6: Email subject format

*For any* severity string and site name string, the generated email subject matches the format `[決済条件監視] {severity}: {site_name} でダークパターン違反を検出`.

**Validates: Requirements 3.3**

### Property 7: Email body contains all required violation fields

*For any* violation dict and MonitoringSite, the rendered email body contains: site name, site URL, violation type, severity, and detected_at. When present in the violation, it also contains detected price, expected price, and evidence URL.

**Validates: Requirements 3.4**

### Property 8: 3-layer config merge priority

*For any* combination of global environment variables, site-level plugin_config, customer email, and override flag: (1) when `NOTIFICATION_OVERRIDE_DISABLED=true`, all channels are disabled regardless of other settings; (2) otherwise, site-level values override global values for any key present in both; (3) global values serve as defaults for keys absent from site config; (4) `email_recipients` always contains `customer_email` as the first element, followed by any `additional_email_recipients` from site config, with duplicates removed.

**Validates: Requirements 3.2, 4.1, 4.2, 4.3, 4.4, 4.5**

### Property 9: Multiple violations produce single notification

*For any* list of violations with length > 1, the renderer produces exactly one Slack payload and one email body (not one per violation), and each violation's details appear in the output.

**Validates: Requirements 5.3**

### Property 10: Missing template fields default to N/A

*For any* violation dict with one or more optional fields (`detected_price`, `expected_price`, `evidence_url`) missing, the rendered output displays "N/A" for each missing field.

**Validates: Requirements 5.4**

### Property 11: Template field round-trip

*For any* set of template field values (site_name, violation_type, severity, detected_price, evidence_url, detected_at), rendering them into the notification template and then parsing the rendered output recovers the original field values.

**Validates: Requirements 5.5**

### Property 12: Duplicate suppression within time window

*For any* site_id, violation_type, and suppression window W, if a NotificationRecord with status `sent` exists for that (site_id, violation_type) within the last W hours, then `filter_new_violations()` excludes that violation_type. If no such record exists, the violation_type is included.

**Validates: Requirements 6.2, 6.4, 6.5**

### Property 13: Successful send creates NotificationRecord and updates Alert flags

*For any* successful notification send (Slack or email), a NotificationRecord with status `sent` is created, and the corresponding Alert record's `slack_sent` or `email_sent` flag is set to `True`.

**Validates: Requirements 2.5, 3.6, 6.3, 8.4**

### Property 14: Webhook URL masking

*For any* Slack webhook URL of length >= 8, the masked version hides all characters except the last 8. For URLs shorter than 8 characters, the entire URL is masked.

**Validates: Requirements 9.4**

### Property 15: Notification config API round-trip

*For any* valid NotificationConfigUpdate payload, PUTting it to `/api/sites/{site_id}/notification-config` and then GETting the same endpoint returns a config that reflects the updated values.

**Validates: Requirements 9.1, 9.2**

### Property 16: Notification history filtering

*For any* set of NotificationRecords for a site, filtering by `channel` returns only records matching that channel, and filtering by `status` returns only records matching that status. Applying both filters returns the intersection.

**Validates: Requirements 10.3, 10.4**

### Property 17: Notification history pagination

*For any* set of N notification records, requesting with `limit=L` and `offset=O` returns exactly `min(L, max(0, N-O))` items, and the `total` field equals N.

**Validates: Requirements 10.5**

## Error Handling

| エラー状況 | 対応 | 影響範囲 |
|---|---|---|
| Slack Webhook 送信失敗 (HTTP != 200) | Celery タスク内で最大3回リトライ（指数バックオフ 1s, 2s, 4s）。全失敗後 NotificationRecord に `status=failed` を記録 | パイプライン実行に影響なし |
| SMTP メール送信失敗 | Celery タスク内で最大3回リトライ（指数バックオフ 1s, 2s, 4s）。全失敗後 NotificationRecord に `status=failed` を記録 | パイプライン実行に影響なし |
| Celery ワーカー不可 | NotificationPlugin がフォールバックとして同期送信を試行。失敗時は `ctx.errors` に記録 | パイプライン実行時間が増加する可能性あり |
| DB 接続エラー（重複判定時） | エラーを `ctx.errors` に記録し、重複判定をスキップ（通知を送信する方向にフェイルオーバー） | 重複通知が発生する可能性あり |
| DB 接続エラー（NotificationRecord 保存時） | Celery タスク内でリトライ。全失敗後はログに記録 | 次回の重複判定が不正確になる可能性あり |
| 不正な plugin_config 形式 | `merge_notification_config` がデフォルト値にフォールバック。警告ログを出力 | グローバル設定で動作 |
| テンプレートレンダリングエラー | エラーを `ctx.errors` に記録。通知送信をスキップ | 該当パイプライン実行の通知が送信されない |
| 存在しない site_id (API) | 404 レスポンスを返却 | API 呼び出し元にエラー通知 |
| 不正な設定値 (API) | 422 バリデーションエラーを返却 | API 呼び出し元にエラー通知 |

## Testing Strategy

### Property-Based Testing

ライブラリ: **Hypothesis** (Python)

各プロパティテストは最低100イテレーション実行する。各テストにはデザインドキュメントのプロパティ番号をタグとしてコメントに記載する。

タグ形式: `# Feature: dark-pattern-notification, Property {number}: {property_text}`

テスト対象の純粋関数/コンポーネント:

1. **merge_notification_config**: Property 8 (3層マージ優先順位)
2. **NotificationPlugin.should_run**: Property 1 (violations + channel 判定)
3. **NotificationTemplateRenderer.render_slack_payload**: Property 4, 5 (Slack フィールド + 色分け)
4. **NotificationTemplateRenderer.render_email**: Property 6, 7 (メール件名 + 本文フィールド)
5. **NotificationTemplateRenderer.render_violation_fields**: Property 10, 11 (N/A デフォルト + ラウンドトリップ)
6. **render → 複数違反**: Property 9 (1通にまとめ)
7. **DuplicateSuppressionChecker.filter_new_violations**: Property 12 (重複抑制)
8. **mask_webhook_url**: Property 14 (URL マスク)
9. **Notification history filtering/pagination**: Property 16, 17

Hypothesis ストラテジー:

```python
from hypothesis import strategies as st

# 違反 dict のストラテジー
violation_strategy = st.fixed_dictionaries({
    "violation_type": st.sampled_from(["price_mismatch", "structured_data_failure", "dark_pattern"]),
    "severity": st.sampled_from(["warning", "critical", "info"]),
}, optional={
    "variant_name": st.text(min_size=1, max_size=50),
    "contract_price": st.floats(min_value=0, max_value=100000, allow_nan=False),
    "actual_price": st.floats(min_value=0, max_value=100000, allow_nan=False),
    "data_source": st.sampled_from(["html", "ocr", "structured_data"]),
    "evidence_url": st.text(min_size=1, max_size=200),
})

# NotificationConfig のストラテジー
notification_config_strategy = st.builds(
    NotificationConfig,
    slack_enabled=st.booleans(),
    slack_webhook_url=st.one_of(st.none(), st.text(min_size=10, max_size=200)),
    slack_channel=st.text(min_size=1, max_size=50),
    email_enabled=st.booleans(),
    email_recipients=st.lists(st.emails(), max_size=5),
    suppression_window_hours=st.integers(min_value=1, max_value=168),
)
```

### Unit Testing

ユニットテストは以下に焦点を当てる:

- **統合テスト**: NotificationPlugin の execute() フロー全体（モック使用）
- **Celery タスク**: send_notification タスクのリトライ動作、フォールバック動作
- **API エンドポイント**: 正常系レスポンス、404/422 エラーケース
- **DB モデル**: NotificationRecord の CRUD 操作
- **パイプライン順序**: Reporter ステージ内の実行順序確認

エッジケース:
- 空の violations リスト（should_run = False）
- 全チャネル無効（should_run = False）
- NOTIFICATION_OVERRIDE_DISABLED=true での緊急停止
- Celery ワーカー不可時の同期フォールバック
- 存在しない site_id での API 呼び出し（404）
- 不正な設定値での API 呼び出し（422）
- webhook URL が8文字未満の場合のマスク処理

# クロールデータ取得と構造化の詳細分析

## 概要
現在のシステムは、Webサイトをクロールして支払い情報を抽出し、契約条件と照合して違反を検出する仕組みになっています。

---

## 1. クロール処理フロー

### 1.1 全体の流れ
```
クロール開始
    ↓
CrawlerEngine (crawler.py)
    ↓ HTMLコンテンツ取得
ContentAnalyzer (analyzer.py)
    ↓ 支払い情報抽出
ValidationEngine (validator.py)
    ↓ 契約条件との照合
違反検出 & アラート送信
    ↓
データベース保存
```

---

## 2. CrawlerEngine - データ取得層

### 2.1 取得するデータ
```python
@dataclass
class CrawlResponse:
    url: str                    # クロールしたURL
    html_content: str           # 生のHTMLコンテンツ（全体）
    status_code: int            # HTTPステータスコード
    crawled_at: datetime        # クロール実行日時
    success: bool               # 成功/失敗フラグ
    error_message: Optional[str] # エラーメッセージ
```

### 2.2 技術スタック
- **Playwright**: ヘッドレスブラウザでJavaScript実行後のHTMLを取得
- **Redis**: レート制限管理（同一ドメインへの連続アクセス制御）
- **robots.txt**: クロール許可チェック

### 2.3 主要機能
1. **robots.txt準拠**: クロール前に許可確認
2. **レート制限**: 同一ドメインへ最低10秒間隔
3. **リトライロジック**: 最大3回、指数バックオフ（1秒、2秒、4秒）
4. **タイムアウト**: 300秒（5分）

### 2.4 データベース保存
```python
# crawl_resultsテーブルに保存
CrawlResult:
    id: int
    site_id: int
    url: str
    html_content: str          # 生のHTML全体を保存
    screenshot_path: str       # スクリーンショットパス（オプション）
    status_code: int
    crawled_at: datetime
```

**問題点**: 
- HTMLコンテンツ全体を保存（非効率）
- 構造化されたデータは保存されていない
- 抽出された支払い情報は保存されていない

---

## 3. ContentAnalyzer - データ抽出層

### 3.1 抽出するデータ構造
```python
@dataclass
class PaymentInfo:
    prices: dict[str, Any]              # 価格情報
    payment_methods: list[str]          # 支払い方法
    fees: dict[str, Any]                # 手数料情報
    subscription_terms: Optional[dict]  # サブスクリプション条件
    is_complete: bool                   # 抽出完了フラグ
```

### 3.2 抽出方法

#### 3.2.1 価格抽出
```python
# 正規表現パターン
PRICE_PATTERNS = [
    r'¥\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # ¥10,000
    r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $100.00
    r'€\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # €50.00
    r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*円',  # 10000円
]

# 抽出結果の構造
prices = {
    'JPY': [10000, 15000, 20000],  # 複数の価格を配列で保存
    'USD': [100.00],
    'EUR': [50.00]
}
```

#### 3.2.2 支払い方法抽出
```python
# キーワードマッチング
PAYMENT_METHOD_KEYWORDS = {
    'credit_card': ['クレジットカード', 'credit card', 'visa', 'mastercard'],
    'bank_transfer': ['銀行振込', 'bank transfer'],
    'convenience_store': ['コンビニ', 'convenience store'],
    'paypal': ['paypal', 'ペイパル'],
    'cash_on_delivery': ['代金引換', 'cash on delivery']
}

# 抽出結果
payment_methods = ['credit_card', 'bank_transfer', 'paypal']
```

#### 3.2.3 手数料抽出
```python
# パーセンテージ手数料
percentage_pattern = r'(\d+(?:\.\d+)?)\s*%'  # 3%, 3.5%

# 固定手数料（手数料キーワード近くの金額）
fee_pattern = r'手数料[^0-9]*(\d{1,3}(?:,\d{3})*)'

# 抽出結果
fees = {
    'percentage': [3.0, 3.5],  # パーセンテージ
    'fixed': [500, 1000]       # 固定額
}
```

#### 3.2.4 サブスクリプション条件抽出
```python
# キーワードマッチング
SUBSCRIPTION_KEYWORDS = {
    'commitment': ['定期', '縛り', 'commitment', 'subscription'],
    'cancellation': ['解約', 'cancel', 'キャンセル']
}

# 期間抽出
period_pattern = r'(\d+)\s*(?:ヶ月|か月|months?)'

# 抽出結果
subscription_terms = {
    'has_commitment': True,
    'has_cancellation_policy': True,
    'commitment_months': [6, 12]  # 6ヶ月、12ヶ月
}
```

### 3.3 技術スタック
- **BeautifulSoup4**: HTML解析
- **正規表現**: パターンマッチング
- **lxml**: 高速HTMLパーサー

### 3.4 問題点
- **抽出精度が低い**: 単純な正規表現とキーワードマッチングのみ
- **構造化が不十分**: HTMLの構造を活用していない
- **コンテキスト無視**: 価格がどの商品のものか不明
- **データベース未保存**: 抽出結果がメモリ上のみ
- **多言語対応不足**: 日本語と英語のみ

---

## 4. ValidationEngine - 検証層

### 4.1 検証プロセス
```python
@dataclass
class Violation:
    violation_type: str      # 違反タイプ
    severity: str           # 重要度（low/medium/high/critical）
    field_name: str         # 違反フィールド名
    expected_value: Any     # 期待値
    actual_value: Any       # 実際の値
    message: str            # メッセージ
```

### 4.2 検証ルール

#### 4.2.1 価格検証
```python
# 許容誤差付き比較
def _validate_prices(actual_prices, expected_prices):
    # 各通貨ごとに検証
    for currency, expected_amounts in expected_prices.items():
        # 実際の価格が期待値の範囲内か確認
        # price_tolerance（デフォルト0%）を考慮
        if not within_tolerance(actual, expected):
            violations.append(Violation(
                violation_type='price',
                severity='high',
                field_name=f'prices.{currency}',
                expected_value=expected,
                actual_value=actual,
                message=f'価格不一致: 期待値 {expected}, 実際 {actual}'
            ))
```

#### 4.2.2 支払い方法検証
```python
# 許可された方法のチェック
allowed_methods = ['credit_card', 'bank_transfer']
required_methods = ['credit_card']

# 実際の方法が許可リストにあるか
# 必須の方法が含まれているか
```

#### 4.2.3 手数料検証
```python
# パーセンテージと固定額の両方を検証
# 期待値と実際の値を比較
```

#### 4.2.4 サブスクリプション条件検証
```python
# コミットメント期間の確認
# 解約ポリシーの有無確認
```

### 4.3 データベース保存
```python
# violationsテーブルに保存
Violation:
    id: int
    validation_result_id: int
    violation_type: str
    severity: str
    field_name: str
    expected_value: dict (JSONB)  # 期待値をJSON形式で保存
    actual_value: dict (JSONB)    # 実際の値をJSON形式で保存
    detected_at: datetime
```

---

## 5. データベーススキーマ

### 5.1 主要テーブル

#### crawl_results（クロール結果）
```sql
CREATE TABLE crawl_results (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    html_content TEXT NOT NULL,        -- 生のHTML全体
    screenshot_path TEXT,
    status_code INTEGER NOT NULL,
    crawled_at TIMESTAMP NOT NULL,
    FOREIGN KEY (site_id) REFERENCES monitoring_sites(id)
);
```

#### violations（違反）
```sql
CREATE TABLE violations (
    id SERIAL PRIMARY KEY,
    validation_result_id INTEGER NOT NULL,
    violation_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    expected_value JSONB NOT NULL,     -- 期待値（JSON）
    actual_value JSONB NOT NULL,       -- 実際の値（JSON）
    detected_at TIMESTAMP NOT NULL
);
```

#### contract_conditions（契約条件）
```sql
CREATE TABLE contract_conditions (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL,
    version INTEGER NOT NULL,
    prices JSONB NOT NULL,             -- 価格情報（JSON）
    payment_methods JSONB NOT NULL,    -- 支払い方法（JSON）
    fees JSONB NOT NULL,               -- 手数料（JSON）
    subscription_terms JSONB,          -- サブスク条件（JSON）
    is_current BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (site_id) REFERENCES monitoring_sites(id)
);
```

### 5.2 契約条件のJSON構造例
```json
{
  "prices": {
    "JPY": [10000, 15000],
    "USD": [100]
  },
  "payment_methods": {
    "allowed": ["credit_card", "bank_transfer", "paypal"],
    "required": ["credit_card"]
  },
  "fees": {
    "percentage": [3.0],
    "fixed": [500]
  },
  "subscription_terms": {
    "has_commitment": true,
    "commitment_months": [6, 12],
    "has_cancellation_policy": true
  }
}
```

---

## 6. 現在の問題点と改善提案

### 6.1 データ取得の問題

#### 問題
1. **HTML全体を保存**: 非効率、ストレージ圧迫
2. **構造化データ未保存**: 抽出した`PaymentInfo`がメモリ上のみ
3. **スクリーンショット未取得**: 視覚的証拠がない
4. **メタデータ不足**: ページタイトル、説明文などが未取得

#### 改善提案
```python
# 新しいテーブル: extracted_payment_info
CREATE TABLE extracted_payment_info (
    id SERIAL PRIMARY KEY,
    crawl_result_id INTEGER NOT NULL,
    prices JSONB NOT NULL,
    payment_methods JSONB NOT NULL,
    fees JSONB NOT NULL,
    subscription_terms JSONB,
    extraction_confidence FLOAT,      -- 抽出信頼度
    extraction_method VARCHAR(50),    -- 抽出方法（regex/ml/manual）
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (crawl_result_id) REFERENCES crawl_results(id)
);
```

### 6.2 データ抽出の問題

#### 問題
1. **精度が低い**: 正規表現のみ、コンテキスト無視
2. **構造化不足**: 価格と商品の関連付けなし
3. **多言語対応不足**: 日本語・英語のみ
4. **動的コンテンツ対応不足**: JavaScript生成コンテンツの抽出が不完全

#### 改善提案
```python
# より構造化されたデータモデル
@dataclass
class StructuredPaymentInfo:
    products: List[Product]           # 商品リスト
    payment_options: List[PaymentOption]  # 支払いオプション
    pricing_tiers: List[PricingTier]  # 価格帯
    terms_and_conditions: TermsInfo   # 利用規約情報
    metadata: PageMetadata            # ページメタデータ

@dataclass
class Product:
    name: str
    description: str
    price: Price
    currency: str
    availability: str
    sku: Optional[str]

@dataclass
class Price:
    amount: float
    currency: str
    display_text: str
    is_promotional: bool
    original_price: Optional[float]

@dataclass
class PaymentOption:
    method: str
    provider: str
    fees: Optional[Fee]
    restrictions: List[str]

@dataclass
class Fee:
    type: str  # 'percentage' or 'fixed'
    amount: float
    description: str
```

### 6.3 検証の問題

#### 問題
1. **単純な値比較のみ**: ビジネスロジックが不足
2. **時系列分析なし**: 価格変動の追跡なし
3. **異常検知なし**: 急激な変更の検出なし

#### 改善提案
```python
# 時系列分析テーブル
CREATE TABLE price_history (
    id SERIAL PRIMARY KEY,
    site_id INTEGER NOT NULL,
    product_identifier VARCHAR(255),
    price DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    recorded_at TIMESTAMP NOT NULL,
    change_percentage FLOAT,          -- 前回からの変化率
    is_anomaly BOOLEAN DEFAULT FALSE, -- 異常値フラグ
    FOREIGN KEY (site_id) REFERENCES monitoring_sites(id)
);
```

---

## 7. 推奨される改善アーキテクチャ

### 7.1 データ取得の改善
```
Playwright (現在)
    ↓
+ スクリーンショット取得
+ ページメタデータ取得
+ 構造化HTML抽出（JSON-LD, Microdata）
    ↓
保存: crawl_results + page_metadata + screenshots
```

### 7.2 データ抽出の改善
```
BeautifulSoup + Regex (現在)
    ↓
+ セマンティックHTML解析（<article>, <section>）
+ JSON-LD / Microdata パース
+ 機械学習モデル（価格・商品名抽出）
+ OCR（スクリーンショットから）
    ↓
保存: extracted_payment_info (構造化データ)
```

### 7.3 検証の改善
```
単純比較 (現在)
    ↓
+ 時系列分析
+ 異常検知
+ ビジネスルール検証
+ 信頼度スコアリング
    ↓
保存: violations + price_history + anomaly_detection
```

---

## 8. 実装優先度

### 高優先度
1. **抽出データの構造化保存**: `extracted_payment_info`テーブル追加
2. **スクリーンショット取得**: 証拠保存
3. **抽出精度向上**: セマンティックHTML解析

### 中優先度
4. **時系列分析**: 価格変動追跡
5. **OCR統合**: スクリーンショットからのデータ抽出
6. **多言語対応**: 言語検出と多言語パターン

### 低優先度
7. **機械学習モデル**: 高精度抽出
8. **異常検知**: 自動アラート
9. **ビジネスルール拡張**: 複雑な検証ロジック

---

## 9. まとめ

### 現在の状態
- ✅ 基本的なクロール機能は動作
- ✅ 正規表現ベースの抽出は実装済み
- ✅ 契約条件との照合は可能
- ❌ 抽出データが構造化されていない
- ❌ データベースに保存されていない
- ❌ 抽出精度が低い
- ❌ 時系列分析がない

### 次のステップ
1. `extracted_payment_info`テーブルの追加
2. 抽出データの保存処理実装
3. スクリーンショット取得機能追加
4. セマンティックHTML解析の実装
5. 抽出精度の測定と改善

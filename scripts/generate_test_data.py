#!/usr/bin/env python3
"""
Test data generation script for crawl data enhancement features.

Generates sample data for:
- extracted_payment_info records with varying confidence scores and languages
- Sample placeholder screenshots (PNG)
- price_history records with time-series data including anomalous changes

Usage:
    python scripts/generate_test_data.py
"""

import os
import sys
import random
from datetime import datetime, timedelta

# Add parent directory to path so we can import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal, init_db
from src.models import (
    Customer,
    MonitoringSite,
    CrawlResult,
    ExtractedPaymentInfo,
    PriceHistory,
)

# ---------------------------------------------------------------------------
# Sample data definitions
# ---------------------------------------------------------------------------

SAMPLE_SITES = [
    {
        "lang": "ja",
        "name": "テストショップA",
        "url": "https://example-shop-a.jp",
        "products": [
            {"name": "プレミアムプラン", "sku": "PLAN-JP-001", "base_price": 9800, "currency": "JPY"},
            {"name": "スタンダードプラン", "sku": "PLAN-JP-002", "base_price": 4980, "currency": "JPY"},
        ],
    },
    {
        "lang": "en",
        "name": "Test Shop B",
        "url": "https://example-shop-b.com",
        "products": [
            {"name": "Enterprise Plan", "sku": "PLAN-EN-001", "base_price": 99.99, "currency": "USD"},
            {"name": "Starter Plan", "sku": "PLAN-EN-002", "base_price": 29.99, "currency": "USD"},
        ],
    },
    {
        "lang": "zh",
        "name": "测试商店C",
        "url": "https://example-shop-c.cn",
        "products": [
            {"name": "高级套餐", "sku": "PLAN-ZH-001", "base_price": 688, "currency": "CNY"},
        ],
    },
]

PAYMENT_METHODS_BY_LANG = {
    "ja": [
        {"method_name": "クレジットカード", "provider": "Stripe", "processing_fee": 3.6, "fee_type": "percentage"},
        {"method_name": "銀行振込", "provider": None, "processing_fee": 0, "fee_type": "fixed"},
    ],
    "en": [
        {"method_name": "Credit Card", "provider": "Stripe", "processing_fee": 2.9, "fee_type": "percentage"},
        {"method_name": "PayPal", "provider": "PayPal", "processing_fee": 3.49, "fee_type": "percentage"},
    ],
    "zh": [
        {"method_name": "支付宝", "provider": "Alipay", "processing_fee": 0.6, "fee_type": "percentage"},
        {"method_name": "微信支付", "provider": "WeChat", "processing_fee": 0.6, "fee_type": "percentage"},
    ],
}

FEES_BY_LANG = {
    "ja": [{"fee_type": "送料", "amount": 500, "currency": "JPY", "description": "全国一律", "condition": "5000円未満"}],
    "en": [{"fee_type": "Shipping", "amount": 5.99, "currency": "USD", "description": "Standard", "condition": "Orders under $50"}],
    "zh": [{"fee_type": "运费", "amount": 10, "currency": "CNY", "description": "全国统一", "condition": "满99免运费"}],
}

# Confidence profiles: high, medium, low
CONFIDENCE_PROFILES = {
    "high": {
        "product_name": 0.95, "product_description": 0.88, "base_price": 0.92,
        "currency": 0.98, "payment_methods": 0.85, "fees": 0.80,
    },
    "medium": {
        "product_name": 0.72, "product_description": 0.60, "base_price": 0.75,
        "currency": 0.80, "payment_methods": 0.55, "fees": 0.50,
    },
    "low": {
        "product_name": 0.40, "product_description": 0.30, "base_price": 0.45,
        "currency": 0.50, "payment_methods": 0.35, "fees": 0.25,
    },
}

MINIMAL_HTML = "<html><head><title>Test</title></head><body><p>Test page</p></body></html>"


# ---------------------------------------------------------------------------
# Screenshot generation (placeholder PNGs via Pillow)
# ---------------------------------------------------------------------------

def generate_placeholder_screenshot(path: str, label: str, width: int = 1280, height: int = 800) -> str:
    """Create a simple placeholder PNG screenshot with a label."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  [WARN] Pillow not installed – skipping screenshot generation")
        return ""

    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = Image.new("RGB", (width, height), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)

    # Draw border
    draw.rectangle([0, 0, width - 1, height - 1], outline=(200, 200, 200), width=2)

    # Draw label text
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except (OSError, IOError):
        font = ImageFont.load_default()

    text = f"Screenshot: {label}"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((width - tw) / 2, (height - th) / 2), text, fill=(100, 100, 100), font=font)

    # Add timestamp
    ts_text = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    draw.text((20, height - 40), ts_text, fill=(150, 150, 150), font=font)

    img.save(path, "PNG", optimize=True)
    return path


# ---------------------------------------------------------------------------
# Data generation helpers
# ---------------------------------------------------------------------------

def _overall_confidence(scores: dict) -> float:
    values = list(scores.values())
    return round(sum(values) / len(values), 4) if values else 0.0


def _price_series(base_price: float, num_points: int = 12, include_anomaly: bool = True):
    """Generate a time-series of prices with optional anomalous jumps."""
    prices = []
    current = base_price
    now = datetime.utcnow()

    for i in range(num_points):
        ts = now - timedelta(days=(num_points - 1 - i) * 7)  # weekly intervals

        # Introduce anomaly at ~75% through the series
        if include_anomaly and i == int(num_points * 0.75):
            change_pct = random.choice([0.25, -0.30])  # >20% change
            current = round(current * (1 + change_pct), 2)
        else:
            # Normal small fluctuation ±3%
            change_pct = random.uniform(-0.03, 0.03)
            current = round(current * (1 + change_pct), 2)

        prices.append((ts, max(current, 0)))

    return prices


# ---------------------------------------------------------------------------
# Main generation logic
# ---------------------------------------------------------------------------

def generate_test_data():
    """Generate all test data and insert into the database."""
    db = SessionLocal()
    try:
        print("=== Test Data Generation ===\n")

        # 1. Ensure a test customer exists
        customer = db.query(Customer).filter(Customer.name == "Test Customer").first()
        if not customer:
            customer = Customer(
                name="Test Customer",
                company_name="Test Corp",
                email="test@example.com",
                is_active=True,
            )
            db.add(customer)
            db.flush()
            print(f"  Created customer: {customer.name} (id={customer.id})")
        else:
            print(f"  Using existing customer: {customer.name} (id={customer.id})")

        confidence_keys = list(CONFIDENCE_PROFILES.keys())
        screenshot_base = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "screenshots",
        )

        for site_def in SAMPLE_SITES:
            lang = site_def["lang"]
            print(f"\n--- Site: {site_def['name']} (lang={lang}) ---")

            # 2. Create or reuse MonitoringSite
            site = db.query(MonitoringSite).filter(MonitoringSite.url == site_def["url"]).first()
            if not site:
                site = MonitoringSite(
                    customer_id=customer.id,
                    name=site_def["name"],
                    url=site_def["url"],
                    is_active=True,
                )
                db.add(site)
                db.flush()
                print(f"  Created site id={site.id}")
            else:
                print(f"  Using existing site id={site.id}")

            for prod in site_def["products"]:
                print(f"  Product: {prod['name']}")

                # 3. Create CrawlResult
                crawl = CrawlResult(
                    site_id=site.id,
                    url=site_def["url"],
                    html_content=MINIMAL_HTML,
                    status_code=200,
                    crawled_at=datetime.utcnow(),
                )
                db.add(crawl)
                db.flush()

                # 4. Generate placeholder screenshot (task 26.2)
                now = datetime.utcnow()
                ss_dir = os.path.join(
                    screenshot_base,
                    str(now.year),
                    f"{now.month:02d}",
                    str(site.id),
                )
                ss_filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{site.id}.png"
                ss_path = os.path.join(ss_dir, ss_filename)
                generated_path = generate_placeholder_screenshot(ss_path, prod["name"])
                if generated_path:
                    crawl.screenshot_path = generated_path
                    print(f"    Screenshot: {generated_path}")

                # 5. Create ExtractedPaymentInfo with varying confidence (task 26.1)
                profile_name = random.choice(confidence_keys)
                scores = CONFIDENCE_PROFILES[profile_name]
                overall = _overall_confidence(scores)

                epi = ExtractedPaymentInfo(
                    crawl_result_id=crawl.id,
                    site_id=site.id,
                    product_info={
                        "name": prod["name"],
                        "description": f"Description for {prod['name']}",
                        "sku": prod["sku"],
                        "category": "SaaS",
                        "brand": site_def["name"],
                    },
                    price_info=[
                        {
                            "amount": prod["base_price"],
                            "currency": prod["currency"],
                            "price_type": "base_price",
                            "condition": "Regular",
                            "tax_included": True,
                        },
                    ],
                    payment_methods=PAYMENT_METHODS_BY_LANG.get(lang, []),
                    fees=FEES_BY_LANG.get(lang, []),
                    extraction_metadata={"source": "test_data_generator", "profile": profile_name},
                    confidence_scores=scores,
                    overall_confidence_score=overall,
                    status="pending",
                    language=lang,
                    extracted_at=datetime.utcnow(),
                )
                db.add(epi)
                db.flush()
                print(f"    ExtractedPaymentInfo id={epi.id} confidence={profile_name} ({overall})")

                # 6. Generate price history time-series (task 26.3)
                include_anomaly = random.random() < 0.7  # 70% chance of anomaly
                series = _price_series(prod["base_price"], num_points=12, include_anomaly=include_anomaly)
                prev_price = None
                for ts, price_val in series:
                    change_amt = None
                    change_pct = None
                    if prev_price is not None:
                        change_amt = round(price_val - prev_price, 2)
                        if prev_price != 0:
                            change_pct = round((change_amt / prev_price) * 100, 2)
                        else:
                            change_pct = 100.0 if price_val != 0 else 0.0

                    ph = PriceHistory(
                        site_id=site.id,
                        product_identifier=prod["sku"],
                        price=price_val,
                        currency=prod["currency"],
                        price_type="base_price",
                        previous_price=prev_price,
                        price_change_amount=change_amt,
                        price_change_percentage=change_pct,
                        recorded_at=ts,
                        extracted_payment_info_id=epi.id,
                    )
                    db.add(ph)
                    prev_price = price_val

                anomaly_tag = " (with anomaly)" if include_anomaly else ""
                print(f"    PriceHistory: {len(series)} records{anomaly_tag}")

        db.commit()
        print("\n=== Done – test data committed successfully ===")

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    generate_test_data()

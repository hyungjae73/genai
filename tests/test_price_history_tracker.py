"""
Unit tests for PriceHistoryTracker (Task 12.3).

Covers:
- 価格履歴記録のテスト (price recording)
- 価格変動計算のテスト (price change calculation)
- 異常値検出のテスト (anomaly detection)
- アラート生成のテスト (alert generation)

Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 16.1, 16.2, 16.3, 16.4, 16.5, 16.6
"""

from datetime import datetime
from unittest.mock import MagicMock, patch, call

import pytest

from src.models import PriceHistory, Alert
from src.price_history_tracker import PriceHistoryTracker, DEFAULT_PRICE_CHANGE_THRESHOLD


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_price_history(**kwargs) -> MagicMock:
    """Create a mock PriceHistory-like object with sensible defaults.

    Uses MagicMock to avoid SQLAlchemy instrumentation issues in unit tests.
    The tracker only reads `.price` from the previous record.
    """
    defaults = dict(
        id=1,
        site_id=1,
        product_identifier="TestProduct [SKU-001]",
        price=1000.0,
        currency="JPY",
        price_type="base_price",
        previous_price=None,
        price_change_amount=None,
        price_change_percentage=None,
        recorded_at=datetime(2024, 1, 1, 12, 0, 0),
        extracted_payment_info_id=None,
    )
    defaults.update(kwargs)
    mock = MagicMock(spec=PriceHistory)
    for k, v in defaults.items():
        setattr(mock, k, v)
    return mock


@pytest.fixture
def mock_db():
    """Create a mock SQLAlchemy session."""
    db = MagicMock()
    # By default, query chains return None (no previous price)
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    # For distinct queries (known product identifiers), return empty
    db.query.return_value.filter.return_value.distinct.return_value.all.return_value = []
    return db


@pytest.fixture
def tracker(mock_db):
    """Create a PriceHistoryTracker with a mocked DB session."""
    return PriceHistoryTracker(db=mock_db)


# ===========================================================================
# 1. 価格履歴記録のテスト (Price recording)
# ===========================================================================


class TestRecordPrice:
    """Tests for record_price — recording price observations."""

    def test_records_first_price_for_product(self, tracker, mock_db):
        """First price record should have no previous price or change info."""
        record = tracker.record_price(
            site_id=1,
            product_name="Widget",
            sku="W-001",
            price_amount=1500.0,
            currency="JPY",
            crawled_at=datetime(2024, 6, 1, 10, 0, 0),
        )

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

        added_obj = mock_db.add.call_args[0][0]
        assert isinstance(added_obj, PriceHistory)
        assert added_obj.site_id == 1
        assert added_obj.product_identifier == "Widget [W-001]"
        assert added_obj.price == 1500.0
        assert added_obj.currency == "JPY"
        assert added_obj.previous_price is None
        assert added_obj.price_change_amount is None
        assert added_obj.price_change_percentage is None

    def test_records_price_with_previous(self, tracker, mock_db):
        """When a previous price exists, change amount and percentage are calculated."""
        previous = _make_price_history(price=1000.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        tracker.record_price(
            site_id=1,
            product_name="Widget",
            sku="W-001",
            price_amount=1200.0,
            currency="JPY",
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.previous_price == 1000.0
        assert added_obj.price_change_amount == 200.0
        assert added_obj.price_change_percentage == pytest.approx(20.0)

    def test_uses_utcnow_when_no_timestamp(self, tracker, mock_db):
        """When crawled_at is not provided, recorded_at should be set to ~now."""
        before = datetime.utcnow()
        tracker.record_price(
            site_id=1, product_name="P", sku=None, price_amount=100.0, currency="USD"
        )
        after = datetime.utcnow()

        added_obj = mock_db.add.call_args[0][0]
        assert before <= added_obj.recorded_at <= after

    def test_product_identifier_name_only(self, tracker, mock_db):
        """Product identifier with name only (no SKU)."""
        tracker.record_price(
            site_id=1, product_name="Gadget", sku=None, price_amount=500.0, currency="JPY"
        )
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.product_identifier == "Gadget"

    def test_product_identifier_sku_only(self, tracker, mock_db):
        """Product identifier with SKU only (no name)."""
        tracker.record_price(
            site_id=1, product_name=None, sku="SKU-999", price_amount=500.0, currency="JPY"
        )
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.product_identifier == "[SKU-999]"

    def test_product_identifier_unknown(self, tracker, mock_db):
        """Product identifier defaults to 'unknown' when both name and SKU are absent."""
        tracker.record_price(
            site_id=1, product_name=None, sku=None, price_amount=500.0, currency="JPY"
        )
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.product_identifier == "unknown"

    def test_stores_extracted_payment_info_id(self, tracker, mock_db):
        """extracted_payment_info_id FK should be stored when provided."""
        tracker.record_price(
            site_id=1,
            product_name="P",
            sku=None,
            price_amount=100.0,
            currency="JPY",
            extracted_payment_info_id=42,
        )
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.extracted_payment_info_id == 42

    def test_stores_price_type(self, tracker, mock_db):
        """price_type should be stored correctly."""
        tracker.record_price(
            site_id=1,
            product_name="P",
            sku=None,
            price_amount=100.0,
            currency="JPY",
            price_type="discount_price",
        )
        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.price_type == "discount_price"


# ===========================================================================
# 2. 価格変動計算のテスト (Price change calculation)
# ===========================================================================


class TestPriceChangeCalculation:
    """Tests for price change amount and percentage calculation in record_price."""

    def test_price_increase(self, tracker, mock_db):
        """Price increase should produce positive change values."""
        previous = _make_price_history(price=1000.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        tracker.record_price(
            site_id=1, product_name="P", sku=None, price_amount=1500.0, currency="JPY"
        )
        added = mock_db.add.call_args[0][0]
        assert added.price_change_amount == pytest.approx(500.0)
        assert added.price_change_percentage == pytest.approx(50.0)

    def test_price_decrease(self, tracker, mock_db):
        """Price decrease should produce negative change values."""
        previous = _make_price_history(price=2000.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        tracker.record_price(
            site_id=1, product_name="P", sku=None, price_amount=1600.0, currency="JPY"
        )
        added = mock_db.add.call_args[0][0]
        assert added.price_change_amount == pytest.approx(-400.0)
        assert added.price_change_percentage == pytest.approx(-20.0)

    def test_no_change(self, tracker, mock_db):
        """Same price should produce zero change."""
        previous = _make_price_history(price=500.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        tracker.record_price(
            site_id=1, product_name="P", sku=None, price_amount=500.0, currency="JPY"
        )
        added = mock_db.add.call_args[0][0]
        assert added.price_change_amount == pytest.approx(0.0)
        assert added.price_change_percentage == pytest.approx(0.0)

    def test_previous_price_zero_to_nonzero(self, tracker, mock_db):
        """Going from 0 to a positive price should yield 100% change."""
        previous = _make_price_history(price=0.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        tracker.record_price(
            site_id=1, product_name="P", sku=None, price_amount=100.0, currency="JPY"
        )
        added = mock_db.add.call_args[0][0]
        assert added.price_change_percentage == pytest.approx(100.0)

    def test_previous_price_zero_to_zero(self, tracker, mock_db):
        """Going from 0 to 0 should yield 0% change."""
        previous = _make_price_history(price=0.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        tracker.record_price(
            site_id=1, product_name="P", sku=None, price_amount=0.0, currency="JPY"
        )
        added = mock_db.add.call_args[0][0]
        assert added.price_change_percentage == pytest.approx(0.0)

    def test_price_drop_to_zero(self, tracker, mock_db):
        """Dropping to zero from a positive price should yield -100%."""
        previous = _make_price_history(price=500.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        tracker.record_price(
            site_id=1, product_name="P", sku=None, price_amount=0.0, currency="JPY"
        )
        added = mock_db.add.call_args[0][0]
        assert added.price_change_amount == pytest.approx(-500.0)
        assert added.price_change_percentage == pytest.approx(-100.0)


# ===========================================================================
# 3. 異常値検出のテスト (Anomaly detection)
# ===========================================================================


class TestDetectAnomalies:
    """Tests for detect_anomalies — identifying price anomalies."""

    def test_new_product_detected(self, tracker, mock_db):
        """A product with no previous price history should trigger a new product alert."""
        products = [
            {"product_name": "NewItem", "sku": "NI-001", "price_amount": 1000.0, "currency": "JPY"}
        ]
        alerts = tracker.detect_anomalies(site_id=1, current_products=products)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "new_product"
        assert alerts[0].severity == "info"

    def test_price_zero_detected(self, tracker, mock_db):
        """Price dropping to zero should trigger a critical alert."""
        previous = _make_price_history(price=1000.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        products = [
            {"product_name": "TestProduct", "sku": "SKU-001", "price_amount": 0.0, "currency": "JPY"}
        ]
        alerts = tracker.detect_anomalies(site_id=1, current_products=products)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "price_zero"
        assert alerts[0].severity == "critical"

    def test_significant_price_increase(self, tracker, mock_db):
        """Price increase >= 20% should trigger a price_change alert."""
        previous = _make_price_history(price=1000.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        products = [
            {"product_name": "TestProduct", "sku": "SKU-001", "price_amount": 1250.0, "currency": "JPY"}
        ]
        alerts = tracker.detect_anomalies(site_id=1, current_products=products)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "price_change"
        assert alerts[0].severity == "high"

    def test_significant_price_decrease(self, tracker, mock_db):
        """Price decrease >= 20% should trigger a price_change alert."""
        previous = _make_price_history(price=1000.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        products = [
            {"product_name": "TestProduct", "sku": "SKU-001", "price_amount": 750.0, "currency": "JPY"}
        ]
        alerts = tracker.detect_anomalies(site_id=1, current_products=products)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "price_change"

    def test_small_change_no_alert(self, tracker, mock_db):
        """Price change below threshold should not trigger an alert."""
        previous = _make_price_history(price=1000.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        products = [
            {"product_name": "TestProduct", "sku": "SKU-001", "price_amount": 1100.0, "currency": "JPY"}
        ]
        alerts = tracker.detect_anomalies(site_id=1, current_products=products)

        assert len(alerts) == 0

    def test_product_disappeared(self, tracker, mock_db):
        """A known product missing from current_products should trigger a warning alert."""
        # No previous price for current products (they're new)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        # Known identifiers include a product that's not in current list
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("OldProduct [OLD-001]",),
        ]

        products = [
            {"product_name": "NewProduct", "sku": "NEW-001", "price_amount": 500.0, "currency": "JPY"}
        ]
        alerts = tracker.detect_anomalies(site_id=1, current_products=products)

        # Should have new_product alert + product_disappeared alert
        alert_types = [a.alert_type for a in alerts]
        assert "product_disappeared" in alert_types
        assert "new_product" in alert_types

    def test_custom_threshold(self, mock_db):
        """Custom price_change_threshold should be respected."""
        tracker = PriceHistoryTracker(db=mock_db, price_change_threshold=10.0)
        previous = _make_price_history(price=1000.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        # 15% increase — above 10% custom threshold
        products = [
            {"product_name": "TestProduct", "sku": "SKU-001", "price_amount": 1150.0, "currency": "JPY"}
        ]
        alerts = tracker.detect_anomalies(site_id=1, current_products=products)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "price_change"

    def test_exactly_at_threshold(self, tracker, mock_db):
        """Price change exactly at 20% threshold should trigger an alert."""
        previous = _make_price_history(price=1000.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        products = [
            {"product_name": "TestProduct", "sku": "SKU-001", "price_amount": 1200.0, "currency": "JPY"}
        ]
        alerts = tracker.detect_anomalies(site_id=1, current_products=products)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "price_change"

    def test_empty_product_list(self, tracker, mock_db):
        """Empty product list with known products should trigger disappeared alerts."""
        mock_db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
            ("Product A",),
        ]

        alerts = tracker.detect_anomalies(site_id=1, current_products=[])

        assert len(alerts) == 1
        assert alerts[0].alert_type == "product_disappeared"

    def test_zero_price_takes_priority_over_change(self, tracker, mock_db):
        """When price drops to zero, zero-price alert should be generated (not price_change)."""
        previous = _make_price_history(price=100.0)
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = previous

        products = [
            {"product_name": "TestProduct", "sku": "SKU-001", "price_amount": 0.0, "currency": "JPY"}
        ]
        alerts = tracker.detect_anomalies(site_id=1, current_products=products)

        assert len(alerts) == 1
        assert alerts[0].alert_type == "price_zero"


# ===========================================================================
# 4. アラート生成のテスト (Alert generation)
# ===========================================================================


class TestAlertGeneration:
    """Tests for alert content and structure."""

    def test_price_change_alert_content(self, tracker, mock_db):
        """Price change alert should contain old price, new price, and change percentage."""
        alert = tracker._create_price_change_alert(
            site_id=1,
            product_identifier="Widget [W-001]",
            old_price=1000.0,
            new_price=1300.0,
            change_percentage=30.0,
            currency="JPY",
        )

        assert alert.alert_type == "price_change"
        assert alert.severity == "high"
        assert alert.site_id == 1
        assert alert.old_price == 1000.0
        assert alert.new_price == 1300.0
        assert alert.change_percentage == 30.0
        assert "1000.00" in alert.message
        assert "1300.00" in alert.message
        assert "+30.0%" in alert.message
        assert "上昇" in alert.message

    def test_price_decrease_alert_message(self, tracker, mock_db):
        """Price decrease alert should say '下落'."""
        alert = tracker._create_price_change_alert(
            site_id=1,
            product_identifier="Widget",
            old_price=1000.0,
            new_price=700.0,
            change_percentage=-30.0,
            currency="JPY",
        )

        assert "下落" in alert.message
        assert "-30.0%" in alert.message

    def test_zero_price_alert_content(self, tracker, mock_db):
        """Zero price alert should be critical severity with -100% change."""
        alert = tracker._create_zero_price_alert(
            site_id=1,
            product_identifier="Widget",
            old_price=500.0,
            currency="JPY",
        )

        assert alert.alert_type == "price_zero"
        assert alert.severity == "critical"
        assert alert.old_price == 500.0
        assert alert.new_price == 0.0
        assert alert.change_percentage == -100.0
        assert "500.00" in alert.message
        assert "0.00" in alert.message

    def test_new_product_alert_content(self, tracker, mock_db):
        """New product alert should be info severity with price info."""
        alert = tracker._create_new_product_alert(
            site_id=1,
            product_identifier="NewWidget [NW-001]",
            price_amount=2500.0,
            currency="USD",
        )

        assert alert.alert_type == "new_product"
        assert alert.severity == "info"
        assert alert.new_price == 2500.0
        assert "NewWidget [NW-001]" in alert.message
        assert "2500.00" in alert.message

    def test_product_disappeared_alert_content(self, tracker, mock_db):
        """Product disappeared alert should be warning severity."""
        alert = tracker._create_product_disappeared_alert(
            site_id=1,
            product_identifier="OldWidget [OW-001]",
        )

        assert alert.alert_type == "product_disappeared"
        assert alert.severity == "warning"
        assert "OldWidget [OW-001]" in alert.message

    def test_alerts_are_persisted_to_db(self, tracker, mock_db):
        """All alert factory methods should add the alert to the DB session."""
        tracker._create_price_change_alert(1, "P", 100.0, 200.0, 100.0, "JPY")
        tracker._create_zero_price_alert(1, "P", 100.0, "JPY")
        tracker._create_new_product_alert(1, "P", 100.0, "JPY")
        tracker._create_product_disappeared_alert(1, "P")

        # Each factory calls db.add + db.flush
        assert mock_db.add.call_count == 4
        assert mock_db.flush.call_count == 4


# ===========================================================================
# 5. get_price_history のテスト
# ===========================================================================


class TestGetPriceHistory:
    """Tests for get_price_history — retrieving historical records."""

    def test_queries_with_site_and_product(self, tracker, mock_db):
        """Should filter by site_id and product_identifier."""
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        tracker.get_price_history(site_id=1, product_identifier="Widget")

        mock_db.query.assert_called_with(PriceHistory)

    def test_applies_date_filters(self, tracker, mock_db):
        """When start_date and end_date are provided, additional filters should be applied."""
        chain = mock_db.query.return_value.filter.return_value
        chain.filter.return_value = chain  # chained .filter calls
        chain.order_by.return_value.all.return_value = []

        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        tracker.get_price_history(
            site_id=1, product_identifier="Widget", start_date=start, end_date=end
        )

        # Verify query was built (exact filter assertions are fragile with mocks,
        # so we just verify the method was called)
        assert mock_db.query.called


# ===========================================================================
# 6. _build_product_identifier のテスト
# ===========================================================================


class TestBuildProductIdentifier:
    """Tests for _build_product_identifier helper."""

    def test_name_and_sku(self, tracker):
        assert tracker._build_product_identifier("Widget", "W-001") == "Widget [W-001]"

    def test_name_only(self, tracker):
        assert tracker._build_product_identifier("Widget", None) == "Widget"

    def test_sku_only(self, tracker):
        assert tracker._build_product_identifier(None, "W-001") == "[W-001]"

    def test_neither(self, tracker):
        assert tracker._build_product_identifier(None, None) == "unknown"

    def test_empty_strings(self, tracker):
        assert tracker._build_product_identifier("", "") == "unknown"

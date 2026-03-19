"""
Price history tracking module.

Provides PriceHistoryTracker class for recording price changes,
calculating price differentials, and detecting anomalies.
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from src.models import PriceHistory, Alert

logger = logging.getLogger(__name__)

# Default threshold for significant price change alerts
DEFAULT_PRICE_CHANGE_THRESHOLD = 20.0


class PriceHistoryTracker:
    """
    Tracks price history for products on monitored sites.

    Records prices with timestamps, calculates differentials against
    previous crawls, and generates alerts for anomalous changes.
    """

    def __init__(self, db: Session, price_change_threshold: float = DEFAULT_PRICE_CHANGE_THRESHOLD):
        """
        Initialize PriceHistoryTracker.

        Args:
            db: SQLAlchemy database session.
            price_change_threshold: Percentage threshold for price change alerts.
        """
        self.db = db
        self.price_change_threshold = price_change_threshold

    def _build_product_identifier(
        self,
        product_name: Optional[str] = None,
        sku: Optional[str] = None,
    ) -> str:
        """
        Build a product identifier string from name and SKU.

        Args:
            product_name: Product name.
            sku: Product SKU.

        Returns:
            Combined identifier string.
        """
        parts = []
        if product_name:
            parts.append(product_name)
        if sku:
            parts.append(f"[{sku}]")
        return " ".join(parts) if parts else "unknown"

    def get_latest_price(
        self,
        site_id: int,
        product_identifier: str,
    ) -> Optional[PriceHistory]:
        """
        Get the most recent price record for a product.

        Args:
            site_id: Site ID.
            product_identifier: Product identifier string.

        Returns:
            Latest PriceHistory record or None.
        """
        return (
            self.db.query(PriceHistory)
            .filter(
                PriceHistory.site_id == site_id,
                PriceHistory.product_identifier == product_identifier,
            )
            .order_by(PriceHistory.recorded_at.desc())
            .first()
        )

    def record_price(
        self,
        site_id: int,
        product_name: Optional[str],
        sku: Optional[str],
        price_amount: float,
        currency: str,
        crawled_at: Optional[datetime] = None,
        price_type: str = "base_price",
        extracted_payment_info_id: Optional[int] = None,
    ) -> PriceHistory:
        """
        Record a price observation and calculate change from previous crawl.

        Args:
            site_id: Site ID.
            product_name: Product name.
            sku: Product SKU.
            price_amount: Current price amount.
            currency: Currency code.
            crawled_at: Timestamp of the crawl (defaults to now).
            price_type: Type of price (e.g. base_price, discount_price).
            extracted_payment_info_id: Optional FK to extracted_payment_info.

        Returns:
            The created PriceHistory record.
        """
        product_identifier = self._build_product_identifier(product_name, sku)
        timestamp = crawled_at or datetime.utcnow()

        # Look up previous price for this product
        previous = self.get_latest_price(site_id, product_identifier)

        previous_price: Optional[float] = None
        change_amount: Optional[float] = None
        change_percentage: Optional[float] = None

        if previous is not None:
            previous_price = previous.price
            change_amount = price_amount - previous_price
            if previous_price != 0:
                change_percentage = (change_amount / previous_price) * 100.0
            else:
                change_percentage = 0.0 if price_amount == 0 else 100.0

        record = PriceHistory(
            site_id=site_id,
            product_identifier=product_identifier,
            price=price_amount,
            currency=currency,
            price_type=price_type,
            previous_price=previous_price,
            price_change_amount=change_amount,
            price_change_percentage=change_percentage,
            recorded_at=timestamp,
            extracted_payment_info_id=extracted_payment_info_id,
        )

        self.db.add(record)
        self.db.flush()

        logger.info(
            "Price recorded: site_id=%d, product=%s, price=%.2f %s, change=%.2f%%",
            site_id,
            product_identifier,
            price_amount,
            currency,
            change_percentage if change_percentage is not None else 0.0,
        )

        return record

    def get_price_history(
        self,
        site_id: int,
        product_identifier: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[PriceHistory]:
        """
        Retrieve price history for a product.

        Args:
            site_id: Site ID.
            product_identifier: Product identifier string.
            start_date: Optional start date filter.
            end_date: Optional end date filter.

        Returns:
            List of PriceHistory records ordered by recorded_at ascending.
        """
        query = self.db.query(PriceHistory).filter(
            PriceHistory.site_id == site_id,
            PriceHistory.product_identifier == product_identifier,
        )

        if start_date:
            query = query.filter(PriceHistory.recorded_at >= start_date)
        if end_date:
            query = query.filter(PriceHistory.recorded_at <= end_date)

        return query.order_by(PriceHistory.recorded_at.asc()).all()

    # ------------------------------------------------------------------
    # Anomaly detection
    # ------------------------------------------------------------------

    def detect_anomalies(
        self,
        site_id: int,
        current_products: List[dict],
    ) -> List[Alert]:
        """
        Detect price anomalies and generate alerts.

        Checks for:
        - Price changes exceeding the threshold (default 20%)
        - Price dropping to zero
        - New products appearing
        - Products disappearing

        Args:
            site_id: Site ID.
            current_products: List of dicts with keys:
                product_name, sku, price_amount, currency.

        Returns:
            List of generated Alert objects.
        """
        alerts: List[Alert] = []

        # Build set of current product identifiers
        current_identifiers: set[str] = set()

        for product in current_products:
            product_name = product.get("product_name")
            sku = product.get("sku")
            price_amount = product.get("price_amount", 0.0)
            currency = product.get("currency", "JPY")
            identifier = self._build_product_identifier(product_name, sku)
            current_identifiers.add(identifier)

            previous = self.get_latest_price(site_id, identifier)

            if previous is None:
                # New product
                alert = self._create_new_product_alert(site_id, identifier, price_amount, currency)
                alerts.append(alert)
                continue

            old_price = previous.price

            # Price dropped to zero
            if price_amount == 0 and old_price > 0:
                alert = self._create_zero_price_alert(
                    site_id, identifier, old_price, currency,
                )
                alerts.append(alert)
                continue

            # Significant price change
            if old_price != 0:
                change_pct = ((price_amount - old_price) / old_price) * 100.0
            else:
                change_pct = 0.0 if price_amount == 0 else 100.0

            if abs(change_pct) >= self.price_change_threshold:
                alert = self._create_price_change_alert(
                    site_id, identifier, old_price, price_amount, change_pct, currency,
                )
                alerts.append(alert)

        # Check for disappeared products
        known_identifiers = self._get_known_product_identifiers(site_id)
        disappeared = known_identifiers - current_identifiers
        for identifier in disappeared:
            alert = self._create_product_disappeared_alert(site_id, identifier)
            alerts.append(alert)

        return alerts

    # ------------------------------------------------------------------
    # Alert factory helpers
    # ------------------------------------------------------------------

    def _create_price_change_alert(
        self,
        site_id: int,
        product_identifier: str,
        old_price: float,
        new_price: float,
        change_percentage: float,
        currency: str,
    ) -> Alert:
        direction = "上昇" if change_percentage > 0 else "下落"
        message = (
            f"価格{direction}アラート: {product_identifier} - "
            f"旧価格: {old_price:.2f} {currency}, "
            f"新価格: {new_price:.2f} {currency}, "
            f"変動率: {change_percentage:+.1f}%"
        )
        alert = Alert(
            alert_type="price_change",
            severity="high",
            message=message,
            site_id=site_id,
            old_price=old_price,
            new_price=new_price,
            change_percentage=change_percentage,
        )
        self.db.add(alert)
        self.db.flush()
        logger.warning("Price change alert: %s", message)
        return alert

    def _create_zero_price_alert(
        self,
        site_id: int,
        product_identifier: str,
        old_price: float,
        currency: str,
    ) -> Alert:
        message = (
            f"価格ゼロアラート: {product_identifier} - "
            f"旧価格: {old_price:.2f} {currency}, "
            f"新価格: 0.00 {currency}, "
            f"変動率: -100.0%"
        )
        alert = Alert(
            alert_type="price_zero",
            severity="critical",
            message=message,
            site_id=site_id,
            old_price=old_price,
            new_price=0.0,
            change_percentage=-100.0,
        )
        self.db.add(alert)
        self.db.flush()
        logger.critical("Zero price alert: %s", message)
        return alert

    def _create_new_product_alert(
        self,
        site_id: int,
        product_identifier: str,
        price_amount: float,
        currency: str,
    ) -> Alert:
        message = (
            f"新商品検出: {product_identifier} - "
            f"価格: {price_amount:.2f} {currency}"
        )
        alert = Alert(
            alert_type="new_product",
            severity="info",
            message=message,
            site_id=site_id,
            new_price=price_amount,
        )
        self.db.add(alert)
        self.db.flush()
        logger.info("New product alert: %s", message)
        return alert

    def _create_product_disappeared_alert(
        self,
        site_id: int,
        product_identifier: str,
    ) -> Alert:
        message = f"商品消失アラート: {product_identifier}"
        alert = Alert(
            alert_type="product_disappeared",
            severity="warning",
            message=message,
            site_id=site_id,
        )
        self.db.add(alert)
        self.db.flush()
        logger.warning("Product disappeared alert: %s", message)
        return alert

    def _get_known_product_identifiers(self, site_id: int) -> set[str]:
        """
        Get all known product identifiers for a site from price history.

        Returns:
            Set of product identifier strings.
        """
        rows = (
            self.db.query(PriceHistory.product_identifier)
            .filter(PriceHistory.site_id == site_id)
            .distinct()
            .all()
        )
        return {row[0] for row in rows}

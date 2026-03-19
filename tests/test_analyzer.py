"""
Unit tests for ContentAnalyzer.

Tests price extraction, payment method extraction, fee extraction,
and subscription term extraction functionality.
"""

import pytest
from src.analyzer import ContentAnalyzer, PaymentInfo


class TestContentAnalyzer:
    """Test suite for ContentAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create a ContentAnalyzer instance."""
        return ContentAnalyzer()
    
    def test_extract_prices_jpy(self, analyzer):
        """Test extraction of Japanese Yen prices."""
        html = """
        <html>
            <body>
                <p>商品価格: ¥10,000</p>
                <p>送料: 500円</p>
            </body>
        </html>
        """
        result = analyzer.extract_payment_info(html)
        
        assert 'JPY' in result.prices
        assert 10000.0 in result.prices['JPY']
        assert 500.0 in result.prices['JPY']
    
    def test_extract_prices_usd(self, analyzer):
        """Test extraction of US Dollar prices."""
        html = """
        <html>
            <body>
                <p>Price: $99.99</p>
                <p>Shipping: $5.00</p>
            </body>
        </html>
        """
        result = analyzer.extract_payment_info(html)
        
        assert 'USD' in result.prices
        assert 99.99 in result.prices['USD']
        assert 5.0 in result.prices['USD']
    
    def test_extract_payment_methods(self, analyzer):
        """Test extraction of payment methods."""
        html = """
        <html>
            <body>
                <p>お支払い方法: クレジットカード、銀行振込、コンビニ決済</p>
            </body>
        </html>
        """
        result = analyzer.extract_payment_info(html)
        
        assert 'credit_card' in result.payment_methods
        assert 'bank_transfer' in result.payment_methods
        assert 'convenience_store' in result.payment_methods
    
    def test_extract_fees_percentage(self, analyzer):
        """Test extraction of percentage fees."""
        html = """
        <html>
            <body>
                <p>手数料: 3.5%</p>
            </body>
        </html>
        """
        result = analyzer.extract_payment_info(html)
        
        assert 'percentage' in result.fees
        assert 3.5 in result.fees['percentage']
    
    def test_extract_fees_fixed(self, analyzer):
        """Test extraction of fixed fees."""
        html = """
        <html>
            <body>
                <p>振込手数料: 220円</p>
            </body>
        </html>
        """
        result = analyzer.extract_payment_info(html)
        
        assert 'fixed' in result.fees
        assert 220.0 in result.fees['fixed']
    
    def test_extract_subscription_terms(self, analyzer):
        """Test extraction of subscription terms."""
        html = """
        <html>
            <body>
                <p>定期購入: 6ヶ月の契約期間</p>
                <p>解約は契約期間終了後に可能です</p>
            </body>
        </html>
        """
        result = analyzer.extract_payment_info(html)
        
        assert result.subscription_terms is not None
        assert result.subscription_terms['has_commitment'] is True
        assert result.subscription_terms['has_cancellation_policy'] is True
        assert 6 in result.subscription_terms['commitment_months']
    
    def test_is_complete_with_required_fields(self, analyzer):
        """Test that is_complete is True when required fields are present."""
        html = """
        <html>
            <body>
                <p>価格: ¥5,000</p>
                <p>支払い: クレジットカード</p>
            </body>
        </html>
        """
        result = analyzer.extract_payment_info(html)
        
        assert result.is_complete is True
    
    def test_is_complete_missing_payment_methods(self, analyzer):
        """Test that is_complete is False when payment methods are missing."""
        html = """
        <html>
            <body>
                <p>価格: ¥5,000</p>
            </body>
        </html>
        """
        result = analyzer.extract_payment_info(html)
        
        assert result.is_complete is False
    
    def test_empty_html(self, analyzer):
        """Test handling of empty HTML."""
        html = "<html><body></body></html>"
        result = analyzer.extract_payment_info(html)
        
        assert result.prices == {}
        assert result.payment_methods == []
        assert result.fees == {}
        assert result.subscription_terms is None
        assert result.is_complete is False
    
    def test_malformed_html(self, analyzer):
        """Test handling of malformed HTML."""
        html = "<html><body><p>Price: ¥1,000</p><p>Payment: クレジットカード"
        result = analyzer.extract_payment_info(html)
        
        # Should still extract data despite malformed HTML
        assert 'JPY' in result.prices
        assert 'credit_card' in result.payment_methods

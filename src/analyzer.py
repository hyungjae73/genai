"""
Content Analyzer for Payment Compliance Monitor.

This module extracts payment information from HTML content using BeautifulSoup4
and regular expressions.
"""

import re
from dataclasses import dataclass
from typing import Any, Optional

from bs4 import BeautifulSoup


@dataclass
class PaymentInfo:
    """
    Structured payment information extracted from HTML content.
    
    Attributes:
        prices: Dictionary of extracted prices with currency and amounts
        payment_methods: List of detected payment methods
        fees: Dictionary of fee information (percentage or fixed amounts)
        subscription_terms: Dictionary of subscription terms (commitment periods, cancellation)
        is_complete: Whether all required fields were successfully extracted
    """
    prices: dict[str, Any]
    payment_methods: list[str]
    fees: dict[str, Any]
    subscription_terms: Optional[dict[str, Any]]
    is_complete: bool = True


class ContentAnalyzer:
    """
    Analyzes HTML content to extract payment information.
    
    Uses BeautifulSoup4 for HTML parsing and regular expressions for pattern matching.
    """
    
    # Price patterns: matches various currency formats
    PRICE_PATTERNS = [
        r'¥\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # Japanese Yen
        r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # US Dollar
        r'€\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # Euro
        r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*円',  # Japanese Yen (suffix)
        r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*yen',  # Yen (text)
    ]
    
    # Payment method keywords
    PAYMENT_METHOD_KEYWORDS = {
        'credit_card': ['クレジットカード', 'credit card', 'visa', 'mastercard', 'amex'],
        'bank_transfer': ['銀行振込', 'bank transfer', '振込', '振り込み'],
        'convenience_store': ['コンビニ', 'convenience store', 'コンビニ決済'],
        'paypal': ['paypal', 'ペイパル'],
        'cash_on_delivery': ['代金引換', 'cash on delivery', '代引き'],
    }
    
    # Fee keywords
    FEE_KEYWORDS = [
        '手数料', 'fee', 'charge', '料金', 'commission'
    ]
    
    # Subscription term keywords
    SUBSCRIPTION_KEYWORDS = {
        'commitment': ['定期', '縛り', 'commitment', 'subscription', '契約期間'],
        'cancellation': ['解約', 'cancel', 'キャンセル', '退会'],
    }
    
    def extract_payment_info(
        self,
        html_content: str,
        extraction_rules: Optional[dict[str, Any]] = None
    ) -> PaymentInfo:
        """
        Extract payment information from HTML content.
        
        Args:
            html_content: Raw HTML content to analyze
            extraction_rules: Optional custom extraction rules (not used in minimal implementation)
        
        Returns:
            PaymentInfo object with extracted data
        """
        soup = BeautifulSoup(html_content, 'lxml')
        text_content = soup.get_text(separator=' ', strip=True)
        
        # Extract prices
        prices = self._extract_prices(text_content)
        
        # Extract payment methods
        payment_methods = self._extract_payment_methods(text_content)
        
        # Extract fees
        fees = self._extract_fees(text_content)
        
        # Extract subscription terms
        subscription_terms = self._extract_subscription_terms(text_content)
        
        # Check if extraction is complete
        is_complete = bool(prices and payment_methods)
        
        return PaymentInfo(
            prices=prices,
            payment_methods=payment_methods,
            fees=fees,
            subscription_terms=subscription_terms,
            is_complete=is_complete
        )
    
    def _extract_prices(self, text: str) -> dict[str, Any]:
        """
        Extract price information using regex patterns.
        
        Args:
            text: Text content to search
        
        Returns:
            Dictionary with currency and amounts
        """
        prices = {}
        
        for pattern in self.PRICE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Convert to float, removing commas
                amounts = [float(m.replace(',', '')) for m in matches]
                
                # Determine currency from pattern
                if '¥' in pattern or '円' in pattern or 'yen' in pattern:
                    currency = 'JPY'
                elif '$' in pattern:
                    currency = 'USD'
                elif '€' in pattern:
                    currency = 'EUR'
                else:
                    currency = 'UNKNOWN'
                
                if currency not in prices:
                    prices[currency] = []
                prices[currency].extend(amounts)
        
        return prices
    
    def _extract_payment_methods(self, text: str) -> list[str]:
        """
        Extract payment methods using keyword matching.
        
        Args:
            text: Text content to search
        
        Returns:
            List of detected payment methods
        """
        detected_methods = []
        text_lower = text.lower()
        
        for method, keywords in self.PAYMENT_METHOD_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    if method not in detected_methods:
                        detected_methods.append(method)
                    break
        
        return detected_methods
    
    def _extract_fees(self, text: str) -> dict[str, Any]:
        """
        Extract fee information.
        
        Args:
            text: Text content to search
        
        Returns:
            Dictionary with fee information
        """
        fees = {}
        
        # Look for percentage fees (e.g., "3%", "3.5%")
        percentage_pattern = r'(\d+(?:\.\d+)?)\s*%'
        percentage_matches = re.findall(percentage_pattern, text)
        
        if percentage_matches:
            fees['percentage'] = [float(m) for m in percentage_matches]
        
        # Look for fixed fees near fee keywords
        for keyword in self.FEE_KEYWORDS:
            # Search for amounts near fee keywords
            pattern = rf'{keyword}[^0-9]*(\d{{1,3}}(?:,\d{{3}})*(?:\.\d{{2}})?)'
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                if 'fixed' not in fees:
                    fees['fixed'] = []
                fees['fixed'].extend([float(m.replace(',', '')) for m in matches])
        
        return fees
    
    def _extract_subscription_terms(self, text: str) -> Optional[dict[str, Any]]:
        """
        Extract subscription term information.
        
        Args:
            text: Text content to search
        
        Returns:
            Dictionary with subscription terms or None
        """
        terms = {}
        text_lower = text.lower()
        
        # Check for commitment keywords
        has_commitment = any(
            keyword.lower() in text_lower
            for keyword in self.SUBSCRIPTION_KEYWORDS['commitment']
        )
        
        # Check for cancellation keywords
        has_cancellation = any(
            keyword.lower() in text_lower
            for keyword in self.SUBSCRIPTION_KEYWORDS['cancellation']
        )
        
        if has_commitment or has_cancellation:
            terms['has_commitment'] = has_commitment
            terms['has_cancellation_policy'] = has_cancellation
            
            # Try to extract commitment period (e.g., "6ヶ月", "12 months")
            period_pattern = r'(\d+)\s*(?:ヶ月|か月|months?|ヵ月)'
            period_matches = re.findall(period_pattern, text_lower)
            if period_matches:
                terms['commitment_months'] = [int(m) for m in period_matches]
            
            return terms
        
        return None

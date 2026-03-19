"""
Unit tests for ValidationEngine.

Tests the validation of payment information against contract conditions.
"""

import pytest

from src.analyzer import PaymentInfo
from src.validator import ValidationEngine, ValidationResult, Violation


class TestValidationEngine:
    """Test suite for ValidationEngine."""
    
    def test_validate_matching_prices(self):
        """Test validation passes when prices match exactly."""
        engine = ValidationEngine(price_tolerance=0.0)
        
        payment_info = PaymentInfo(
            prices={'JPY': [1000.0]},
            payment_methods=['credit_card'],
            fees={},
            subscription_terms=None,
            is_complete=True
        )
        
        contract_conditions = {
            'prices': {'JPY': [1000.0]},
            'payment_methods': {'allowed': ['credit_card']},
            'fees': {},
            'subscription_terms': None
        }
        
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        assert result.is_valid
        assert len(result.violations) == 0
    
    def test_validate_price_mismatch(self):
        """Test validation detects price violations."""
        engine = ValidationEngine(price_tolerance=0.0)
        
        payment_info = PaymentInfo(
            prices={'JPY': [2000.0]},
            payment_methods=['credit_card'],
            fees={},
            subscription_terms=None,
            is_complete=True
        )
        
        contract_conditions = {
            'prices': {'JPY': [1000.0]},
            'payment_methods': {'allowed': ['credit_card']},
            'fees': {},
            'subscription_terms': None
        }
        
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        assert not result.is_valid
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == 'price'
        assert result.violations[0].severity == 'high'
    
    def test_validate_price_with_tolerance(self):
        """Test validation with price tolerance."""
        engine = ValidationEngine(price_tolerance=5.0)  # 5% tolerance
        
        payment_info = PaymentInfo(
            prices={'JPY': [1040.0]},  # 4% higher
            payment_methods=['credit_card'],
            fees={},
            subscription_terms=None,
            is_complete=True
        )
        
        contract_conditions = {
            'prices': {'JPY': [1000.0]},
            'payment_methods': {'allowed': ['credit_card']},
            'fees': {},
            'subscription_terms': None
        }
        
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        assert result.is_valid
        assert len(result.violations) == 0
    
    def test_validate_unauthorized_payment_method(self):
        """Test validation detects unauthorized payment methods."""
        engine = ValidationEngine()
        
        payment_info = PaymentInfo(
            prices={'JPY': [1000.0]},
            payment_methods=['credit_card', 'paypal'],
            fees={},
            subscription_terms=None,
            is_complete=True
        )
        
        contract_conditions = {
            'prices': {'JPY': [1000.0]},
            'payment_methods': {'allowed': ['credit_card']},
            'fees': {},
            'subscription_terms': None
        }
        
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        assert not result.is_valid
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == 'payment_method'
        assert result.violations[0].actual_value == 'paypal'
    
    def test_validate_missing_required_payment_method(self):
        """Test validation detects missing required payment methods."""
        engine = ValidationEngine()
        
        payment_info = PaymentInfo(
            prices={'JPY': [1000.0]},
            payment_methods=['credit_card'],
            fees={},
            subscription_terms=None,
            is_complete=True
        )
        
        contract_conditions = {
            'prices': {'JPY': [1000.0]},
            'payment_methods': {
                'allowed': ['credit_card', 'bank_transfer'],
                'required': ['bank_transfer']
            },
            'fees': {},
            'subscription_terms': None
        }
        
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        assert not result.is_valid
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == 'payment_method'
        assert result.violations[0].expected_value == 'bank_transfer'
    
    def test_validate_fee_mismatch(self):
        """Test validation detects fee violations."""
        engine = ValidationEngine()
        
        payment_info = PaymentInfo(
            prices={'JPY': [1000.0]},
            payment_methods=['credit_card'],
            fees={'percentage': [5.0]},
            subscription_terms=None,
            is_complete=True
        )
        
        contract_conditions = {
            'prices': {'JPY': [1000.0]},
            'payment_methods': {'allowed': ['credit_card']},
            'fees': {'percentage': 3.0},
            'subscription_terms': None
        }
        
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        assert not result.is_valid
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == 'fee'
        assert result.violations[0].field_name == 'fees.percentage'
    
    def test_validate_subscription_terms_mismatch(self):
        """Test validation detects subscription term violations."""
        engine = ValidationEngine()
        
        payment_info = PaymentInfo(
            prices={'JPY': [1000.0]},
            payment_methods=['credit_card'],
            fees={},
            subscription_terms={
                'has_commitment': True,
                'commitment_months': [12]
            },
            is_complete=True
        )
        
        contract_conditions = {
            'prices': {'JPY': [1000.0]},
            'payment_methods': {'allowed': ['credit_card']},
            'fees': {},
            'subscription_terms': {
                'has_commitment': True,
                'commitment_months': 6
            }
        }
        
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        assert not result.is_valid
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == 'subscription'
        assert result.violations[0].field_name == 'subscription_terms.commitment_months'
    
    def test_validate_multiple_violations(self):
        """Test validation detects multiple violations."""
        engine = ValidationEngine()
        
        payment_info = PaymentInfo(
            prices={'JPY': [2000.0]},
            payment_methods=['paypal'],
            fees={'percentage': [5.0]},
            subscription_terms=None,
            is_complete=True
        )
        
        contract_conditions = {
            'prices': {'JPY': [1000.0]},
            'payment_methods': {'allowed': ['credit_card']},
            'fees': {'percentage': 3.0},
            'subscription_terms': None
        }
        
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        assert not result.is_valid
        assert len(result.violations) == 3
        violation_types = [v.violation_type for v in result.violations]
        assert 'price' in violation_types
        assert 'payment_method' in violation_types
        assert 'fee' in violation_types

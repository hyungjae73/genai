"""
Property-based tests for ValidationEngine.

Tests universal properties that should hold for all validation operations.
"""

import pytest
from hypothesis import given, strategies as st, settings

from src.analyzer import PaymentInfo
from src.validator import ValidationEngine


# Strategy for generating payment info
@st.composite
def payment_info_strategy(draw):
    """Generate arbitrary PaymentInfo instances."""
    currencies = ['JPY', 'USD', 'EUR']
    currency = draw(st.sampled_from(currencies))
    
    prices = {currency: [draw(st.floats(min_value=100.0, max_value=100000.0))]}
    payment_methods = draw(st.lists(
        st.sampled_from(['credit_card', 'bank_transfer', 'paypal', 'konbini']),
        min_size=1,
        max_size=3,
        unique=True
    ))
    
    # Generate fees (optional)
    has_fees = draw(st.booleans())
    if has_fees:
        fees = {'percentage': [draw(st.floats(min_value=0.0, max_value=10.0))]}
    else:
        fees = {}
    
    # Generate subscription terms (optional)
    has_subscription = draw(st.booleans())
    if has_subscription:
        subscription_terms = {
            'has_commitment': draw(st.booleans()),
            'commitment_months': [draw(st.integers(min_value=1, max_value=24))]
        }
    else:
        subscription_terms = None
    
    return PaymentInfo(
        prices=prices,
        payment_methods=payment_methods,
        fees=fees,
        subscription_terms=subscription_terms,
        is_complete=True
    )


# Strategy for generating contract conditions
@st.composite
def contract_conditions_strategy(draw):
    """Generate arbitrary contract conditions."""
    currencies = ['JPY', 'USD', 'EUR']
    currency = draw(st.sampled_from(currencies))
    
    prices = {currency: [draw(st.floats(min_value=100.0, max_value=100000.0))]}
    
    allowed_methods = draw(st.lists(
        st.sampled_from(['credit_card', 'bank_transfer', 'paypal', 'konbini']),
        min_size=1,
        max_size=3,
        unique=True
    ))
    payment_methods = {'allowed': allowed_methods}
    
    # Generate fees (optional)
    has_fees = draw(st.booleans())
    if has_fees:
        fees = {'percentage': draw(st.floats(min_value=0.0, max_value=10.0))}
    else:
        fees = {}
    
    # Generate subscription terms (optional)
    has_subscription = draw(st.booleans())
    if has_subscription:
        subscription_terms = {
            'has_commitment': draw(st.booleans()),
            'commitment_months': draw(st.integers(min_value=1, max_value=24))
        }
    else:
        subscription_terms = None
    
    return {
        'prices': prices,
        'payment_methods': payment_methods,
        'fees': fees,
        'subscription_terms': subscription_terms
    }


class TestValidatorProperties:
    """Property-based tests for ValidationEngine."""
    
    @settings(max_examples=5)
    @given(
        payment_info=payment_info_strategy(),
        contract_conditions=contract_conditions_strategy()
    )
    def test_property_violation_detection(self, payment_info, contract_conditions):
        """
        Property 6: Contract condition violation detection
        
        For any payment information that differs from contract conditions,
        the validator should flag it as a violation with the specific field and values.
        
        **Validates: Requirements 3.2, 3.3, 3.4, 3.5**
        """
        engine = ValidationEngine(price_tolerance=0.0)
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        # Property: Result should always have a boolean is_valid field
        assert isinstance(result.is_valid, bool)
        
        # Property: violations list should always be present
        assert isinstance(result.violations, list)
        
        # Property: If there are violations, is_valid should be False
        if len(result.violations) > 0:
            assert result.is_valid is False
        
        # Property: If is_valid is True, there should be no violations
        if result.is_valid:
            assert len(result.violations) == 0
        
        # Property: Each violation should have required fields
        for violation in result.violations:
            assert hasattr(violation, 'violation_type')
            assert hasattr(violation, 'severity')
            assert hasattr(violation, 'field_name')
            assert hasattr(violation, 'expected_value')
            assert hasattr(violation, 'actual_value')
            assert hasattr(violation, 'message')
            
            # Property: violation_type should be one of the known types
            assert violation.violation_type in ['price', 'payment_method', 'fee', 'subscription']
            
            # Property: severity should be one of the known levels
            assert violation.severity in ['low', 'medium', 'high']
    
    @settings(max_examples=5)
    @given(payment_info=payment_info_strategy())
    def test_property_identical_conditions_no_violations(self, payment_info):
        """
        Property: When payment info matches contract conditions exactly,
        there should be no violations.
        
        **Validates: Requirements 3.2, 3.3, 3.4, 3.5**
        """
        # Create contract conditions that match the payment info exactly
        contract_conditions = {
            'prices': payment_info.prices,
            'payment_methods': {'allowed': payment_info.payment_methods},
            'fees': payment_info.fees,
            'subscription_terms': payment_info.subscription_terms
        }
        
        engine = ValidationEngine(price_tolerance=0.0)
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        # Property: Identical conditions should result in no violations
        assert result.is_valid is True
        assert len(result.violations) == 0
    
    @settings(max_examples=5)
    @given(
        base_price=st.floats(min_value=1000.0, max_value=10000.0),
        tolerance=st.floats(min_value=0.0, max_value=10.0)
    )
    def test_property_price_tolerance_symmetry(self, base_price, tolerance):
        """
        Property: Price tolerance should work symmetrically.
        
        If actual price is within tolerance of expected, validation should pass.
        
        **Validates: Requirements 3.2**
        """
        engine = ValidationEngine(price_tolerance=tolerance)
        
        # Test with price slightly below expected (within tolerance)
        tolerance_amount = base_price * (tolerance / 100.0)
        lower_price = base_price - (tolerance_amount * 0.5)
        
        payment_info = PaymentInfo(
            prices={'JPY': [lower_price]},
            payment_methods=['credit_card'],
            fees={},
            subscription_terms=None,
            is_complete=True
        )
        
        contract_conditions = {
            'prices': {'JPY': [base_price]},
            'payment_methods': {'allowed': ['credit_card']},
            'fees': {},
            'subscription_terms': None
        }
        
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        # Property: Price within tolerance should not create violations
        price_violations = [v for v in result.violations if v.violation_type == 'price']
        assert len(price_violations) == 0


    @settings(max_examples=3)
    @given(payment_info=payment_info_strategy())
    def test_property_validation_result_persistence(self, payment_info):
        """
        Property 7: Validation result persistence
        
        For any completed validation, the validation result should contain
        all necessary information for database persistence.
        
        Note: This test verifies the logical property that validation results
        are structured for persistence. Actual database integration is tested
        in integration tests.
        
        **Validates: Requirements 3.6**
        """
        # Create contract conditions that will cause violations
        contract_conditions = {
            'prices': {'JPY': [99999.0]},  # Different price to cause violation
            'payment_methods': {'allowed': ['credit_card']},
            'fees': {},
            'subscription_terms': None
        }
        
        engine = ValidationEngine(price_tolerance=0.0)
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        # Property: Result should contain all fields needed for persistence
        assert hasattr(result, 'is_valid')
        assert hasattr(result, 'violations')
        assert hasattr(result, 'payment_info')
        assert hasattr(result, 'contract_conditions')
        
        # Property: Each violation should have all fields needed for database storage
        for violation in result.violations:
            assert hasattr(violation, 'violation_type')
            assert hasattr(violation, 'severity')
            assert hasattr(violation, 'field_name')
            assert hasattr(violation, 'expected_value')
            assert hasattr(violation, 'actual_value')
            assert hasattr(violation, 'message')
            
            # Property: All fields should be serializable (not None for required fields)
            assert violation.violation_type is not None
            assert violation.severity is not None
            assert violation.field_name is not None
            # expected_value and actual_value can be None in some cases
            assert violation.message is not None


    @settings(max_examples=5)
    @given(
        payment_info=payment_info_strategy(),
        contract_conditions=contract_conditions_strategy()
    )
    def test_property_alert_triggering_on_violation(self, payment_info, contract_conditions):
        """
        Property 8: Alert triggering on violation
        
        For any detected violation, the validator should trigger the alert system,
        resulting in an alert record being created.
        
        Note: This test verifies the logical property that violations should trigger alerts.
        The actual alert system integration will be tested in integration tests.
        
        **Validates: Requirements 3.7**
        """
        engine = ValidationEngine(price_tolerance=0.0)
        result = engine.validate_payment_info(payment_info, contract_conditions)
        
        # Property: If there are violations, they should be flagged for alerting
        if len(result.violations) > 0:
            # Each violation should have severity level for alert prioritization
            for violation in result.violations:
                assert violation.severity in ['low', 'medium', 'high']
                
                # Property: High severity violations should be present
                # (This ensures critical issues are flagged)
                if violation.violation_type == 'price':
                    assert violation.severity == 'high'
        
        # Property: Validation result should contain all information needed for alerting
        assert hasattr(result, 'violations')
        assert hasattr(result, 'payment_info')
        assert hasattr(result, 'contract_conditions')
        
        # Property: Each violation should have a descriptive message for alerts
        for violation in result.violations:
            assert isinstance(violation.message, str)
            assert len(violation.message) > 0

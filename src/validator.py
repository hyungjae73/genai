"""
Validation Engine for Payment Compliance Monitor.

This module validates extracted payment information against contract conditions
and detects violations.
"""

from dataclasses import dataclass
from typing import Any, Optional

from src.analyzer import PaymentInfo


@dataclass
class Violation:
    """
    Represents a detected violation of contract conditions.
    
    Attributes:
        violation_type: Type of violation (price, payment_method, fee, subscription)
        severity: Severity level (low, medium, high)
        field_name: Name of the field that violated
        expected_value: Expected value from contract
        actual_value: Actual value detected
        message: Human-readable description
    """
    violation_type: str
    severity: str
    field_name: str
    expected_value: Any
    actual_value: Any
    message: str


@dataclass
class ValidationResult:
    """
    Result of validation operation.
    
    Attributes:
        is_valid: Whether validation passed (no violations)
        violations: List of detected violations
        payment_info: The payment information that was validated
        contract_conditions: The contract conditions used for validation
    """
    is_valid: bool
    violations: list[Violation]
    payment_info: PaymentInfo
    contract_conditions: dict[str, Any]


class ValidationEngine:
    """
    Validates payment information against contract conditions.
    
    Compares extracted PaymentInfo from ContentAnalyzer against ContractCondition
    and detects violations.
    """
    
    def __init__(self, price_tolerance: float = 0.0):
        """
        Initialize ValidationEngine.
        
        Args:
            price_tolerance: Allowed price difference as a percentage (0.0 = exact match)
        """
        self.price_tolerance = price_tolerance
    
    def validate_payment_info(
        self,
        payment_info: PaymentInfo,
        contract_conditions: dict[str, Any]
    ) -> ValidationResult:
        """
        Validate payment information against contract conditions.
        
        Args:
            payment_info: Extracted payment information
            contract_conditions: Contract conditions to validate against
        
        Returns:
            ValidationResult with detected violations
        """
        violations = []
        
        # Validate prices
        price_violations = self._validate_prices(
            payment_info.prices,
            contract_conditions.get('prices', {})
        )
        violations.extend(price_violations)
        
        # Validate payment methods
        payment_method_violations = self._validate_payment_methods(
            payment_info.payment_methods,
            contract_conditions.get('payment_methods', {})
        )
        violations.extend(payment_method_violations)
        
        # Validate fees
        fee_violations = self._validate_fees(
            payment_info.fees,
            contract_conditions.get('fees', {})
        )
        violations.extend(fee_violations)
        
        # Validate subscription terms
        subscription_violations = self._validate_subscription_terms(
            payment_info.subscription_terms,
            contract_conditions.get('subscription_terms')
        )
        violations.extend(subscription_violations)
        
        return ValidationResult(
            is_valid=len(violations) == 0,
            violations=violations,
            payment_info=payment_info,
            contract_conditions=contract_conditions
        )
    
    def _validate_prices(
        self,
        actual_prices: dict[str, Any],
        expected_prices: dict[str, Any]
    ) -> list[Violation]:
        """
        Validate price information with tolerance support.
        
        Args:
            actual_prices: Detected prices from content
            expected_prices: Expected prices from contract
        
        Returns:
            List of price violations
        """
        violations = []
        
        # Check each expected currency
        for currency, expected_amounts in expected_prices.items():
            if currency not in actual_prices:
                violations.append(Violation(
                    violation_type='price',
                    severity='high',
                    field_name=f'prices.{currency}',
                    expected_value=expected_amounts,
                    actual_value=None,
                    message=f'Expected currency {currency} not found in payment info'
                ))
                continue
            
            actual_amounts = actual_prices[currency]
            
            # Ensure both are lists
            if not isinstance(expected_amounts, list):
                expected_amounts = [expected_amounts]
            if not isinstance(actual_amounts, list):
                actual_amounts = [actual_amounts]
            
            # Check if any expected amount matches any actual amount (within tolerance)
            for expected_amount in expected_amounts:
                found_match = False
                for actual_amount in actual_amounts:
                    if self._is_within_tolerance(actual_amount, expected_amount):
                        found_match = True
                        break
                
                if not found_match:
                    violations.append(Violation(
                        violation_type='price',
                        severity='high',
                        field_name=f'prices.{currency}',
                        expected_value=expected_amount,
                        actual_value=actual_amounts,
                        message=f'Price mismatch for {currency}: expected {expected_amount}, found {actual_amounts}'
                    ))
        
        return violations

    
    def _validate_payment_methods(
        self,
        actual_methods: list[str],
        expected_methods: dict[str, Any]
    ) -> list[Violation]:
        """
        Validate payment methods.
        
        Args:
            actual_methods: Detected payment methods
            expected_methods: Expected payment methods from contract
        
        Returns:
            List of payment method violations
        """
        violations = []
        
        # Extract allowed methods from contract
        allowed_methods = expected_methods.get('allowed', [])
        if not allowed_methods:
            return violations
        
        # Check if all actual methods are allowed
        for method in actual_methods:
            if method not in allowed_methods:
                violations.append(Violation(
                    violation_type='payment_method',
                    severity='medium',
                    field_name='payment_methods',
                    expected_value=allowed_methods,
                    actual_value=method,
                    message=f'Unauthorized payment method detected: {method}'
                ))
        
        # Check if required methods are present
        required_methods = expected_methods.get('required', [])
        for required_method in required_methods:
            if required_method not in actual_methods:
                violations.append(Violation(
                    violation_type='payment_method',
                    severity='high',
                    field_name='payment_methods',
                    expected_value=required_method,
                    actual_value=actual_methods,
                    message=f'Required payment method missing: {required_method}'
                ))
        
        return violations
    
    def _validate_fees(
        self,
        actual_fees: dict[str, Any],
        expected_fees: dict[str, Any]
    ) -> list[Violation]:
        """
        Validate fee information.
        
        Args:
            actual_fees: Detected fees
            expected_fees: Expected fees from contract
        
        Returns:
            List of fee violations
        """
        violations = []
        
        # Validate percentage fees
        if 'percentage' in expected_fees:
            expected_percentage = expected_fees['percentage']
            actual_percentage = actual_fees.get('percentage')
            
            if actual_percentage is None:
                violations.append(Violation(
                    violation_type='fee',
                    severity='medium',
                    field_name='fees.percentage',
                    expected_value=expected_percentage,
                    actual_value=None,
                    message=f'Expected percentage fee {expected_percentage}% not found'
                ))
            else:
                # Check if any actual percentage matches expected
                if isinstance(actual_percentage, list):
                    actual_values = actual_percentage
                else:
                    actual_values = [actual_percentage]
                
                if isinstance(expected_percentage, list):
                    expected_values = expected_percentage
                else:
                    expected_values = [expected_percentage]
                
                for expected_val in expected_values:
                    if not any(self._is_within_tolerance(actual_val, expected_val) 
                              for actual_val in actual_values):
                        violations.append(Violation(
                            violation_type='fee',
                            severity='medium',
                            field_name='fees.percentage',
                            expected_value=expected_val,
                            actual_value=actual_values,
                            message=f'Percentage fee mismatch: expected {expected_val}%, found {actual_values}'
                        ))
        
        # Validate fixed fees
        if 'fixed' in expected_fees:
            expected_fixed = expected_fees['fixed']
            actual_fixed = actual_fees.get('fixed')
            
            if actual_fixed is None:
                violations.append(Violation(
                    violation_type='fee',
                    severity='medium',
                    field_name='fees.fixed',
                    expected_value=expected_fixed,
                    actual_value=None,
                    message=f'Expected fixed fee {expected_fixed} not found'
                ))
            else:
                # Check if any actual fixed fee matches expected
                if isinstance(actual_fixed, list):
                    actual_values = actual_fixed
                else:
                    actual_values = [actual_fixed]
                
                if isinstance(expected_fixed, list):
                    expected_values = expected_fixed
                else:
                    expected_values = [expected_fixed]
                
                for expected_val in expected_values:
                    if not any(self._is_within_tolerance(actual_val, expected_val) 
                              for actual_val in actual_values):
                        violations.append(Violation(
                            violation_type='fee',
                            severity='medium',
                            field_name='fees.fixed',
                            expected_value=expected_val,
                            actual_value=actual_values,
                            message=f'Fixed fee mismatch: expected {expected_val}, found {actual_values}'
                        ))
        
        return violations
    
    def _validate_subscription_terms(
        self,
        actual_terms: Optional[dict[str, Any]],
        expected_terms: Optional[dict[str, Any]]
    ) -> list[Violation]:
        """
        Validate subscription terms.
        
        Args:
            actual_terms: Detected subscription terms
            expected_terms: Expected subscription terms from contract
        
        Returns:
            List of subscription term violations
        """
        violations = []
        
        if expected_terms is None:
            return violations
        
        # Check if subscription terms are required but missing
        if actual_terms is None:
            violations.append(Violation(
                violation_type='subscription',
                severity='high',
                field_name='subscription_terms',
                expected_value=expected_terms,
                actual_value=None,
                message='Expected subscription terms not found'
            ))
            return violations
        
        # Validate commitment requirement
        if 'has_commitment' in expected_terms:
            expected_commitment = expected_terms['has_commitment']
            actual_commitment = actual_terms.get('has_commitment', False)
            
            if expected_commitment != actual_commitment:
                violations.append(Violation(
                    violation_type='subscription',
                    severity='high',
                    field_name='subscription_terms.has_commitment',
                    expected_value=expected_commitment,
                    actual_value=actual_commitment,
                    message=f'Commitment requirement mismatch: expected {expected_commitment}, found {actual_commitment}'
                ))
        
        # Validate commitment period
        if 'commitment_months' in expected_terms:
            expected_months = expected_terms['commitment_months']
            actual_months = actual_terms.get('commitment_months')
            
            if actual_months is None:
                violations.append(Violation(
                    violation_type='subscription',
                    severity='medium',
                    field_name='subscription_terms.commitment_months',
                    expected_value=expected_months,
                    actual_value=None,
                    message=f'Expected commitment period {expected_months} months not found'
                ))
            else:
                # Check if any actual period matches expected
                if isinstance(actual_months, list):
                    actual_values = actual_months
                else:
                    actual_values = [actual_months]
                
                if isinstance(expected_months, list):
                    expected_values = expected_months
                else:
                    expected_values = [expected_months]
                
                for expected_val in expected_values:
                    if expected_val not in actual_values:
                        violations.append(Violation(
                            violation_type='subscription',
                            severity='medium',
                            field_name='subscription_terms.commitment_months',
                            expected_value=expected_val,
                            actual_value=actual_values,
                            message=f'Commitment period mismatch: expected {expected_val} months, found {actual_values}'
                        ))
        
        # Validate cancellation policy
        if 'has_cancellation_policy' in expected_terms:
            expected_cancellation = expected_terms['has_cancellation_policy']
            actual_cancellation = actual_terms.get('has_cancellation_policy', False)
            
            if expected_cancellation != actual_cancellation:
                violations.append(Violation(
                    violation_type='subscription',
                    severity='medium',
                    field_name='subscription_terms.has_cancellation_policy',
                    expected_value=expected_cancellation,
                    actual_value=actual_cancellation,
                    message=f'Cancellation policy mismatch: expected {expected_cancellation}, found {actual_cancellation}'
                ))
        
        return violations
    
    def _is_within_tolerance(self, actual: float, expected: float) -> bool:
        """
        Check if actual value is within tolerance of expected value.
        
        Args:
            actual: Actual value
            expected: Expected value
        
        Returns:
            True if within tolerance, False otherwise
        """
        if self.price_tolerance == 0.0:
            return actual == expected
        
        tolerance_amount = expected * (self.price_tolerance / 100.0)
        return abs(actual - expected) <= tolerance_amount

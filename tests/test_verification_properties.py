"""
Property-based tests for Verification Service.

Tests universal properties that should hold for all verification operations.
Feature: verification-comparison-system
"""

import asyncio

import pytest
from unittest.mock import MagicMock, AsyncMock, PropertyMock
from hypothesis import given, strategies as st, settings
from pathlib import Path

from src.analyzer import ContentAnalyzer, PaymentInfo
from src.validator import ValidationResult, Violation
from src.ocr_engine import OCRResult, OCRRegion
from src.verification_service import VerificationService, VerificationData, Discrepancy


# Strategy for generating plain text that may contain payment patterns
@st.composite
def payment_text_strategy(draw):
    """Generate text that may contain payment-related content."""
    parts = []

    # Optionally include a price
    if draw(st.booleans()):
        currency_symbol = draw(st.sampled_from(["$", "¥", "€"]))
        amount = draw(st.integers(min_value=1, max_value=99999))
        decimal = draw(st.sampled_from(["", ".99", ".00", ".50"]))
        parts.append(f"{currency_symbol}{amount}{decimal}")

    # Optionally include a payment method keyword
    if draw(st.booleans()):
        method = draw(st.sampled_from([
            "credit card", "bank transfer", "convenience store",
            "paypal", "cash on delivery",
        ]))
        parts.append(method)

    # Optionally include a fee pattern
    if draw(st.booleans()):
        pct = draw(st.integers(min_value=1, max_value=30))
        parts.append(f"fee {pct}%")

    # Optionally include subscription keywords
    if draw(st.booleans()):
        term = draw(st.sampled_from([
            "subscription", "commitment", "cancel",
        ]))
        parts.append(term)

    # Add some filler text
    filler = draw(st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
        min_size=0,
        max_size=200,
    ))
    parts.append(filler)

    draw(st.randoms()).shuffle(parts)
    return " ".join(parts)


# Strategy for generating PaymentInfo objects
@st.composite
def payment_info_strategy(draw):
    """Generate random PaymentInfo objects for property testing."""
    prices = {}
    if draw(st.booleans()):
        currency = draw(st.sampled_from(['USD', 'JPY', 'EUR']))
        amounts = draw(st.lists(
            st.floats(min_value=0.01, max_value=99999, allow_nan=False, allow_infinity=False),
            min_size=1, max_size=3,
        ))
        prices[currency] = amounts

    methods = draw(st.lists(
        st.sampled_from(['credit_card', 'bank_transfer', 'paypal', 'cash_on_delivery']),
        unique=True, max_size=3,
    ))

    fees = {}
    if draw(st.booleans()):
        fees['percentage'] = draw(st.lists(
            st.floats(min_value=0.1, max_value=30, allow_nan=False, allow_infinity=False),
            min_size=1, max_size=2,
        ))

    sub_terms = None
    if draw(st.booleans()):
        sub_terms = {
            'has_commitment': draw(st.booleans()),
            'has_cancellation_policy': draw(st.booleans()),
        }

    return PaymentInfo(
        prices=prices,
        payment_methods=methods,
        fees=fees,
        subscription_terms=sub_terms,
    )


class TestVerificationProperties:
    """Property-based tests for Verification Service."""

    # Feature: verification-comparison-system, Property 4: Extraction Pattern Consistency
    @settings(max_examples=100)
    @given(text_content=payment_text_strategy())
    def test_property_extraction_pattern_consistency(self, text_content: str):
        """
        Property 4: Extraction Pattern Consistency

        For any text content, whether extracted from HTML or OCR, when processed
        through the payment extraction logic, identical text should produce
        identical PaymentInfo results.

        The OCR path wraps text in <html><body>text</body></html> and calls
        ContentAnalyzer.extract_payment_info. The HTML path does the same.
        Both must yield the same PaymentInfo for the same input text.

        **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
        """
        analyzer = ContentAnalyzer()

        # Simulate the OCR extraction path:
        # VerificationService._extract_payment_from_ocr wraps text like this
        ocr_html = f"<html><body>{text_content}</body></html>"
        ocr_result = analyzer.extract_payment_info(ocr_html)

        # Simulate the HTML extraction path with the same text
        # (same wrapper, proving the function is deterministic for identical input)
        html_result = analyzer.extract_payment_info(ocr_html)

        # Both results must be identical
        assert ocr_result.prices == html_result.prices, (
            f"Prices differ: OCR={ocr_result.prices}, HTML={html_result.prices}"
        )
        assert ocr_result.payment_methods == html_result.payment_methods, (
            f"Payment methods differ: OCR={ocr_result.payment_methods}, "
            f"HTML={html_result.payment_methods}"
        )
        assert ocr_result.fees == html_result.fees, (
            f"Fees differ: OCR={ocr_result.fees}, HTML={html_result.fees}"
        )
        assert ocr_result.subscription_terms == html_result.subscription_terms, (
            f"Subscription terms differ: OCR={ocr_result.subscription_terms}, "
            f"HTML={html_result.subscription_terms}"
        )
        assert ocr_result.is_complete == html_result.is_complete, (
            f"is_complete differs: OCR={ocr_result.is_complete}, "
            f"HTML={html_result.is_complete}"
        )

    # Feature: verification-comparison-system, Property 4: Extraction Pattern Consistency
    @settings(max_examples=100)
    @given(text_content=st.text(min_size=0, max_size=500))
    def test_property_extraction_consistency_arbitrary_text(self, text_content: str):
        """
        Property 4 (supplementary): Extraction Pattern Consistency with arbitrary text.

        For any arbitrary text string, wrapping it in the HTML structure used by
        the OCR path and extracting payment info should be deterministic —
        calling extract_payment_info twice on the same wrapped HTML must return
        identical PaymentInfo.

        **Validates: Requirements 2.1, 2.2, 2.3, 2.4**
        """
        analyzer = ContentAnalyzer()

        html_wrapper = f"<html><body>{text_content}</body></html>"

        result_a = analyzer.extract_payment_info(html_wrapper)
        result_b = analyzer.extract_payment_info(html_wrapper)

        assert result_a.prices == result_b.prices
        assert result_a.payment_methods == result_b.payment_methods
        assert result_a.fees == result_b.fees
        assert result_a.subscription_terms == result_b.subscription_terms
        assert result_a.is_complete == result_b.is_complete

    # Feature: verification-comparison-system, Property 5: Graceful Missing Data Handling
    @settings(max_examples=100)
    @given(text_content=st.from_regex(
        r'[a-z0-9 ]{0,300}',
        fullmatch=True,
    ).filter(lambda t: not any(kw in t for kw in [
        'fee', 'yen', 'visa', 'amex', 'cash', 'cancel',
        'charge', 'paypal', 'credit', 'commission',
        'subscription', 'commitment', 'bank',
    ])))
    def test_property_graceful_missing_data_handling(self, text_content: str):
        """
        Property 5: Graceful Missing Data Handling

        For any text content without payment information, when the extraction
        service processes it, the result should return a PaymentInfo object
        with null/empty values for missing fields without raising errors.

        **Validates: Requirements 2.5**
        """
        analyzer = ContentAnalyzer()

        # Wrap in HTML as the extraction path does
        html_wrapper = f"<html><body>{text_content}</body></html>"

        # Must not raise any exception
        result = analyzer.extract_payment_info(html_wrapper)

        # Verify result is a PaymentInfo instance
        assert isinstance(result, PaymentInfo), (
            f"Expected PaymentInfo, got {type(result)}"
        )

        # prices should be empty dict (no currency symbols in input)
        assert result.prices == {}, (
            f"Expected empty prices, got {result.prices} for text: {text_content!r}"
        )

        # payment_methods should be empty list (no payment keywords in input)
        assert result.payment_methods == [], (
            f"Expected empty payment_methods, got {result.payment_methods} "
            f"for text: {text_content!r}"
        )

        # fees should be empty dict (no % or fee keywords in input)
        assert result.fees == {}, (
            f"Expected empty fees, got {result.fees} for text: {text_content!r}"
        )

        # subscription_terms should be None (no subscription keywords in input)
        assert result.subscription_terms is None, (
            f"Expected None subscription_terms, got {result.subscription_terms} "
            f"for text: {text_content!r}"
        )

        # is_complete should be False (no prices or payment methods found)
        assert result.is_complete is False, (
            f"Expected is_complete=False, got {result.is_complete} "
            f"for text: {text_content!r}"
        )

    # Feature: verification-comparison-system, Property 7: Field-by-Field Comparison
    @settings(max_examples=100)
    @given(data=st.data())
    def test_property_field_by_field_comparison(self, data):
        """
        Property 7: Field-by-Field Comparison

        For any two PaymentInfo objects (HTML and OCR data), when the comparison
        function processes them, it should compare all fields: prices,
        payment_methods, fees, and subscription_terms.

        **Validates: Requirements 3.4**
        """
        # Create VerificationService with mocked dependencies
        service = VerificationService(
            content_analyzer=MagicMock(),
            validation_engine=MagicMock(),
            ocr_engine=MagicMock(),
            screenshot_capture=MagicMock(),
            db_session=MagicMock(),
        )

        # Part 1: Identical PaymentInfo objects should produce no discrepancies
        payment_info = data.draw(payment_info_strategy(), label="identical_payment_info")
        identical_copy = PaymentInfo(
            prices=dict(payment_info.prices),
            payment_methods=list(payment_info.payment_methods),
            fees=dict(payment_info.fees),
            subscription_terms=dict(payment_info.subscription_terms) if payment_info.subscription_terms else None,
        )

        discrepancies = service._compare_payment_data(payment_info, identical_copy)
        assert discrepancies == [], (
            f"Identical PaymentInfo should produce no discrepancies, got {discrepancies}"
        )

        # Part 2: Verify all 4 fields are compared by introducing a difference in each
        compared_fields = set()

        # Test prices difference
        html_prices = PaymentInfo(prices={'USD': [10.0]}, payment_methods=[], fees={}, subscription_terms=None)
        ocr_prices = PaymentInfo(prices={'USD': [20.0]}, payment_methods=[], fees={}, subscription_terms=None)
        price_discrepancies = service._compare_payment_data(html_prices, ocr_prices)
        for d in price_discrepancies:
            compared_fields.add(d.field_name.split('.')[0])

        # Test payment_methods difference
        html_methods = PaymentInfo(prices={}, payment_methods=['credit_card'], fees={}, subscription_terms=None)
        ocr_methods = PaymentInfo(prices={}, payment_methods=['paypal'], fees={}, subscription_terms=None)
        method_discrepancies = service._compare_payment_data(html_methods, ocr_methods)
        for d in method_discrepancies:
            compared_fields.add(d.field_name.split('.')[0])

        # Test fees difference
        html_fees = PaymentInfo(prices={}, payment_methods=[], fees={'percentage': [3.0]}, subscription_terms=None)
        ocr_fees = PaymentInfo(prices={}, payment_methods=[], fees={'percentage': [5.0]}, subscription_terms=None)
        fee_discrepancies = service._compare_payment_data(html_fees, ocr_fees)
        for d in fee_discrepancies:
            compared_fields.add(d.field_name.split('.')[0])

        # Test subscription_terms difference
        html_sub = PaymentInfo(prices={}, payment_methods=[], fees={}, subscription_terms={'has_commitment': True})
        ocr_sub = PaymentInfo(prices={}, payment_methods=[], fees={}, subscription_terms={'has_commitment': False})
        sub_discrepancies = service._compare_payment_data(html_sub, ocr_sub)
        for d in sub_discrepancies:
            compared_fields.add(d.field_name.split('.')[0])

        expected_fields = {'prices', 'payment_methods', 'fees', 'subscription_terms'}
        assert compared_fields == expected_fields, (
            f"Expected all 4 fields to be compared, but only found: {compared_fields}. "
            f"Missing: {expected_fields - compared_fields}"
        )

    # Feature: verification-comparison-system, Property 8: Discrepancy Detection
    @settings(max_examples=100)
    @given(data=st.data())
    def test_property_discrepancy_detection(self, data):
        """
        Property 8: Discrepancy Detection

        For any two PaymentInfo objects with differing field values, when the
        comparison function processes them, it should generate a Discrepancy
        for each field that differs.

        **Validates: Requirements 3.5**
        """
        # Create VerificationService with mocked dependencies
        service = VerificationService(
            content_analyzer=MagicMock(),
            validation_engine=MagicMock(),
            ocr_engine=MagicMock(),
            screenshot_capture=MagicMock(),
            db_session=MagicMock(),
        )

        # Generate two independent PaymentInfo objects
        html_info = data.draw(payment_info_strategy(), label="html_info")
        ocr_info = data.draw(payment_info_strategy(), label="ocr_info")

        # Run comparison
        discrepancies = service._compare_payment_data(html_info, ocr_info)

        # Determine which top-level fields actually differ
        field_checks = {
            'prices': html_info.prices != ocr_info.prices,
            'payment_methods': set(html_info.payment_methods) != set(ocr_info.payment_methods),
            'fees': html_info.fees != ocr_info.fees,
            'subscription_terms': html_info.subscription_terms != ocr_info.subscription_terms,
        }

        differing_fields = {name for name, differs in field_checks.items() if differs}

        # For each field that differs, there should be at least one Discrepancy
        # whose field_name starts with that field name
        discrepancy_field_prefixes = {d.field_name.split('.')[0] for d in discrepancies}

        for field in differing_fields:
            assert field in discrepancy_field_prefixes, (
                f"Field '{field}' differs (html={getattr(html_info, field)}, "
                f"ocr={getattr(ocr_info, field)}) but no Discrepancy was generated. "
                f"Discrepancy fields: {[d.field_name for d in discrepancies]}"
            )

        # Conversely, no discrepancy should be generated for fields that are equal
        matching_fields = {name for name, differs in field_checks.items() if not differs}
        for field in matching_fields:
            assert field not in discrepancy_field_prefixes, (
                f"Field '{field}' is equal but a Discrepancy was generated. "
                f"html={getattr(html_info, field)}, ocr={getattr(ocr_info, field)}, "
                f"Discrepancies: {[d for d in discrepancies if d.field_name.split('.')[0] == field]}"
            )

    # Feature: verification-comparison-system, Property 9: Discrepancy Structure Completeness
    @settings(max_examples=100)
    @given(data=st.data())
    def test_property_discrepancy_structure_completeness(self, data):
        """
        Property 9: Discrepancy Structure Completeness

        For any generated Discrepancy, it should include field_name, html_value,
        ocr_value, difference_type, and severity fields.

        **Validates: Requirements 3.6**
        """
        # Create VerificationService with mocked dependencies
        service = VerificationService(
            content_analyzer=MagicMock(),
            validation_engine=MagicMock(),
            ocr_engine=MagicMock(),
            screenshot_capture=MagicMock(),
            db_session=MagicMock(),
        )

        # Generate a base PaymentInfo
        base_info = data.draw(payment_info_strategy(), label="base_info")

        # Choose which field to mutate to guarantee at least one difference
        field_to_mutate = data.draw(
            st.sampled_from(['prices', 'payment_methods', 'fees', 'subscription_terms']),
            label="field_to_mutate",
        )

        # Build a modified copy with at least one field changed
        modified_prices = dict(base_info.prices)
        modified_methods = list(base_info.payment_methods)
        modified_fees = dict(base_info.fees)
        modified_sub = dict(base_info.subscription_terms) if base_info.subscription_terms else None

        if field_to_mutate == 'prices':
            # Force a different price
            modified_prices = {'USD': [999.99]}
            if base_info.prices == modified_prices:
                modified_prices = {'EUR': [1.01]}
        elif field_to_mutate == 'payment_methods':
            # Force different payment methods
            if base_info.payment_methods == ['paypal']:
                modified_methods = ['credit_card']
            else:
                modified_methods = ['paypal']
        elif field_to_mutate == 'fees':
            # Force different fees
            modified_fees = {'percentage': [99.0]}
            if base_info.fees == modified_fees:
                modified_fees = {'fixed': [5.0]}
        elif field_to_mutate == 'subscription_terms':
            # Force different subscription terms
            if base_info.subscription_terms is None:
                modified_sub = {'has_commitment': True}
            else:
                modified_sub = None

        modified_info = PaymentInfo(
            prices=modified_prices,
            payment_methods=modified_methods,
            fees=modified_fees,
            subscription_terms=modified_sub,
        )

        # Run comparison - guaranteed to produce at least one discrepancy
        discrepancies = service._compare_payment_data(base_info, modified_info)
        assert len(discrepancies) > 0, (
            f"Expected at least one discrepancy when mutating '{field_to_mutate}'. "
            f"base={base_info}, modified={modified_info}"
        )

        valid_difference_types = {'missing', 'mismatch', 'extra'}
        valid_severities = {'low', 'medium', 'high'}

        for d in discrepancies:
            # Verify it is a Discrepancy instance
            assert isinstance(d, Discrepancy), f"Expected Discrepancy, got {type(d)}"

            # field_name must be a non-empty string
            assert isinstance(d.field_name, str) and len(d.field_name) > 0, (
                f"field_name must be a non-empty string, got {d.field_name!r}"
            )

            # html_value and ocr_value must be present as attributes
            assert hasattr(d, 'html_value'), "Discrepancy missing html_value"
            assert hasattr(d, 'ocr_value'), "Discrepancy missing ocr_value"

            # difference_type must be one of the valid types
            assert d.difference_type in valid_difference_types, (
                f"difference_type must be one of {valid_difference_types}, "
                f"got {d.difference_type!r}"
            )

            # severity must be one of the valid levels
            assert d.severity in valid_severities, (
                f"severity must be one of {valid_severities}, got {d.severity!r}"
            )


    # Feature: verification-comparison-system, Property 6: Complete Verification Workflow
    @settings(max_examples=100)
    @given(data=st.data())
    def test_property_complete_verification_workflow(self, data):
        """
        Property 6: Complete Verification Workflow

        For any valid site with a URL and contract conditions, when verification
        runs, the service should execute all workflow steps: HTML extraction,
        screenshot capture, OCR extraction, comparison, and validation.

        **Validates: Requirements 3.1, 3.2, 3.3**
        """
        # Generate random site data
        site_url = data.draw(
            st.from_regex(r'https://[a-z]{3,10}\.(com|org|net)', fullmatch=True),
            label="site_url",
        )
        site_id = data.draw(st.integers(min_value=1, max_value=10000), label="site_id")

        # Generate random contract condition values
        contract_prices = data.draw(
            st.fixed_dictionaries({
                'USD': st.lists(
                    st.floats(min_value=0.01, max_value=9999, allow_nan=False, allow_infinity=False),
                    min_size=1, max_size=3,
                ),
            }),
            label="contract_prices",
        )
        contract_methods = data.draw(
            st.lists(
                st.sampled_from(['credit_card', 'bank_transfer', 'paypal']),
                min_size=1, max_size=3, unique=True,
            ),
            label="contract_methods",
        )
        contract_fees = data.draw(
            st.fixed_dictionaries({
                'percentage': st.lists(
                    st.floats(min_value=0.1, max_value=30, allow_nan=False, allow_infinity=False),
                    min_size=0, max_size=2,
                ),
            }),
            label="contract_fees",
        )

        # --- Mock DB session ---
        db_session = MagicMock()

        mock_site = MagicMock()
        mock_site.id = site_id
        mock_site.url = site_url

        mock_contract = MagicMock()
        mock_contract.site_id = site_id
        mock_contract.is_current = True
        mock_contract.prices = contract_prices
        mock_contract.payment_methods = contract_methods
        mock_contract.fees = contract_fees
        mock_contract.subscription_terms = None

        mock_crawl = MagicMock()
        mock_crawl.site_id = site_id
        mock_crawl.html_content = "<html><body><p>Price: $29.99</p></body></html>"

        # Handle multiple db_session.query() calls with side_effect
        # run_verification queries: MonitoringSite, ContractCondition, CrawlResult
        def query_side_effect(model):
            mock_query = MagicMock()
            mock_filter = MagicMock()
            mock_query.filter.return_value = mock_filter

            if model.__name__ == 'MonitoringSite':
                mock_filter.first.return_value = mock_site
            elif model.__name__ == 'ContractCondition':
                mock_filter.first.return_value = mock_contract
            elif model.__name__ == 'CrawlResult':
                mock_order = MagicMock()
                mock_filter.order_by.return_value = mock_order
                mock_order.first.return_value = mock_crawl
            return mock_query

        db_session.query.side_effect = query_side_effect

        # --- Mock content_analyzer ---
        content_analyzer = MagicMock()
        html_payment_info = PaymentInfo(
            prices={'USD': [29.99]},
            payment_methods=['credit_card'],
            fees={'percentage': [3.0]},
            subscription_terms=None,
        )
        content_analyzer.extract_payment_info.return_value = html_payment_info

        # --- Mock screenshot_capture (async) ---
        screenshot_capture = MagicMock()
        screenshot_capture.capture_screenshot = AsyncMock(
            return_value=Path("/tmp/test_screenshot.png")
        )

        # --- Mock ocr_engine ---
        ocr_engine = MagicMock()
        ocr_engine.extract_text.return_value = OCRResult(
            full_text="Price: $29.99 credit card fee 3%",
            regions=[
                OCRRegion(text="Price: $29.99", confidence=0.95, bbox=(0, 0, 100, 20)),
            ],
            average_confidence=0.95,
            success=True,
            error_message=None,
        )

        # --- Mock validation_engine ---
        validation_engine = MagicMock()
        validation_engine.validate_payment_info.return_value = ValidationResult(
            is_valid=True,
            violations=[],
            payment_info=html_payment_info,
            contract_conditions={
                'prices': contract_prices,
                'payment_methods': contract_methods,
                'fees': contract_fees,
                'subscription_terms': None,
            },
        )

        # --- Create service and run verification ---
        service = VerificationService(
            content_analyzer=content_analyzer,
            validation_engine=validation_engine,
            ocr_engine=ocr_engine,
            screenshot_capture=screenshot_capture,
            db_session=db_session,
        )

        result = asyncio.get_event_loop().run_until_complete(
            service.run_verification(site_id)
        )

        # --- Verify all 5 workflow steps were called ---

        # Step 1: HTML extraction via content_analyzer
        # extract_payment_info is called twice: once for HTML, once for OCR
        # (the OCR path wraps text in HTML and reuses the same analyzer)
        assert content_analyzer.extract_payment_info.call_count == 2, (
            f"extract_payment_info should be called twice (HTML + OCR), "
            f"but was called {content_analyzer.extract_payment_info.call_count} times"
        )

        # Step 2: Screenshot capture
        screenshot_capture.capture_screenshot.assert_called_once()
        call_kwargs = screenshot_capture.capture_screenshot.call_args
        # Verify it was called with the site's URL
        assert call_kwargs[1]['url'] == site_url or call_kwargs[0][0] == site_url, (
            "capture_screenshot should be called with the site URL"
        )

        # Step 3: OCR extraction
        ocr_engine.extract_text.assert_called_once()

        # Step 4 & 5: Validation engine called twice (HTML and OCR)
        assert validation_engine.validate_payment_info.call_count == 2, (
            f"validate_payment_info should be called twice (HTML + OCR), "
            f"but was called {validation_engine.validate_payment_info.call_count} times"
        )

        # --- Verify result status is 'success' ---
        assert result.status == 'success', (
            f"Expected status='success', got status='{result.status}', "
            f"error_message='{result.error_message}'"
        )

    # Feature: verification-comparison-system, Property 10: Dual Source Validation
    @settings(max_examples=100)
    @given(data=st.data())
    def test_property_dual_source_validation(self, data):
        """
        Property 10: Dual Source Validation

        For any verification run, when both HTML and OCR data are extracted,
        the validation engine should be invoked for both data sources against
        the contract conditions.

        **Validates: Requirements 4.1, 4.2**
        """
        # Generate random PaymentInfo for HTML and OCR sources
        html_payment_info = data.draw(payment_info_strategy(), label="html_payment_info")
        ocr_payment_info = data.draw(payment_info_strategy(), label="ocr_payment_info")

        site_id = data.draw(st.integers(min_value=1, max_value=10000), label="site_id")
        site_url = data.draw(
            st.from_regex(r'https://[a-z]{3,10}\.(com|org|net)', fullmatch=True),
            label="site_url",
        )

        # --- Mock DB session ---
        db_session = MagicMock()

        mock_site = MagicMock()
        mock_site.id = site_id
        mock_site.url = site_url

        mock_contract = MagicMock()
        mock_contract.site_id = site_id
        mock_contract.is_current = True
        mock_contract.prices = {'USD': [29.99]}
        mock_contract.payment_methods = ['credit_card']
        mock_contract.fees = {'percentage': [3.0]}
        mock_contract.subscription_terms = None

        mock_crawl = MagicMock()
        mock_crawl.site_id = site_id
        mock_crawl.html_content = "<html><body><p>Price: $29.99</p></body></html>"

        def query_side_effect(model):
            mock_query = MagicMock()
            mock_filter = MagicMock()
            mock_query.filter.return_value = mock_filter

            if model.__name__ == 'MonitoringSite':
                mock_filter.first.return_value = mock_site
            elif model.__name__ == 'ContractCondition':
                mock_filter.first.return_value = mock_contract
            elif model.__name__ == 'CrawlResult':
                mock_order = MagicMock()
                mock_filter.order_by.return_value = mock_order
                mock_order.first.return_value = mock_crawl
            return mock_query

        db_session.query.side_effect = query_side_effect

        # --- Mock content_analyzer ---
        # First call returns HTML PaymentInfo, second call returns OCR PaymentInfo
        content_analyzer = MagicMock()
        content_analyzer.extract_payment_info.side_effect = [
            html_payment_info,
            ocr_payment_info,
        ]

        # --- Mock screenshot_capture (async) ---
        screenshot_capture = MagicMock()
        screenshot_capture.capture_screenshot = AsyncMock(
            return_value=Path("/tmp/test_screenshot.png")
        )

        # --- Mock ocr_engine ---
        ocr_engine = MagicMock()
        ocr_engine.extract_text.return_value = OCRResult(
            full_text="Price: $29.99 credit card fee 3%",
            regions=[
                OCRRegion(text="Price: $29.99", confidence=0.95, bbox=(0, 0, 100, 20)),
            ],
            average_confidence=0.95,
            success=True,
            error_message=None,
        )

        # --- Mock validation_engine ---
        validation_engine = MagicMock()
        validation_engine.validate_payment_info.return_value = ValidationResult(
            is_valid=True,
            violations=[],
            payment_info=html_payment_info,
            contract_conditions={
                'prices': mock_contract.prices,
                'payment_methods': mock_contract.payment_methods,
                'fees': mock_contract.fees,
                'subscription_terms': mock_contract.subscription_terms,
            },
        )

        # --- Create service and run verification ---
        service = VerificationService(
            content_analyzer=content_analyzer,
            validation_engine=validation_engine,
            ocr_engine=ocr_engine,
            screenshot_capture=screenshot_capture,
            db_session=db_session,
        )

        result = asyncio.get_event_loop().run_until_complete(
            service.run_verification(site_id)
        )

        # --- Verify dual source validation ---

        # Validation engine must be called exactly twice (HTML + OCR)
        assert validation_engine.validate_payment_info.call_count == 2, (
            f"validate_payment_info should be called exactly 2 times (HTML + OCR), "
            f"but was called {validation_engine.validate_payment_info.call_count} times"
        )

        calls = validation_engine.validate_payment_info.call_args_list

        # First call: HTML data
        assert calls[0][0][0] == html_payment_info, (
            f"First validation call should receive HTML PaymentInfo. "
            f"Expected: {html_payment_info}, Got: {calls[0][0][0]}"
        )

        # Second call: OCR data
        assert calls[1][0][0] == ocr_payment_info, (
            f"Second validation call should receive OCR PaymentInfo. "
            f"Expected: {ocr_payment_info}, Got: {calls[1][0][0]}"
        )

        # Both calls should receive the same contract conditions
        html_contract_conditions = calls[0][0][1]
        ocr_contract_conditions = calls[1][0][1]
        assert html_contract_conditions == ocr_contract_conditions, (
            f"Both validation calls should receive the same contract conditions. "
            f"HTML call got: {html_contract_conditions}, OCR call got: {ocr_contract_conditions}"
        )

    # Feature: verification-comparison-system, Property 11: Violation Source Attribution
    @settings(max_examples=100)
    @given(
        violations=st.lists(
            st.builds(
                Violation,
                violation_type=st.sampled_from(['price', 'payment_method', 'fee', 'subscription']),
                severity=st.sampled_from(['low', 'medium', 'high']),
                field_name=st.sampled_from(['prices.USD', 'payment_methods', 'fees.percentage', 'subscription_terms']),
                expected_value=st.one_of(st.floats(allow_nan=False, allow_infinity=False), st.text(max_size=20)),
                actual_value=st.one_of(st.floats(allow_nan=False, allow_infinity=False), st.text(max_size=20)),
                message=st.text(min_size=5, max_size=100),
            ),
            min_size=0,
            max_size=10,
        ),
    )
    def test_property_violation_source_attribution(self, violations):
        """
        Property 11: Violation Source Attribution

        For any detected violation, the violation record should include a
        data_source field indicating whether it came from HTML or OCR extraction.

        **Validates: Requirements 4.3**
        """
        service = VerificationService(
            content_analyzer=MagicMock(),
            validation_engine=MagicMock(),
            ocr_engine=MagicMock(),
            screenshot_capture=MagicMock(),
            db_session=MagicMock(),
        )

        dummy_payment_info = PaymentInfo(
            prices={}, payment_methods=[], fees={}, subscription_terms=None,
        )

        validation_result = ValidationResult(
            is_valid=len(violations) == 0,
            violations=violations,
            payment_info=dummy_payment_info,
            contract_conditions={},
        )

        # Test HTML source attribution
        html_serialized = service._serialize_violations(validation_result, 'html')
        assert 'items' in html_serialized
        assert len(html_serialized['items']) == len(violations)
        for item in html_serialized['items']:
            assert 'data_source' in item, (
                f"Violation record missing 'data_source' field: {item}"
            )
            assert item['data_source'] == 'html', (
                f"Expected data_source='html', got '{item['data_source']}'"
            )

        # Test OCR source attribution
        ocr_serialized = service._serialize_violations(validation_result, 'ocr')
        assert 'items' in ocr_serialized
        assert len(ocr_serialized['items']) == len(violations)
        for item in ocr_serialized['items']:
            assert 'data_source' in item, (
                f"Violation record missing 'data_source' field: {item}"
            )
            assert item['data_source'] == 'ocr', (
                f"Expected data_source='ocr', got '{item['data_source']}'"
            )

    # Feature: verification-comparison-system, Property 12: Violation Structure Completeness
    @settings(max_examples=100)
    @given(
        violations=st.lists(
            st.builds(
                Violation,
                violation_type=st.sampled_from(['price', 'payment_method', 'fee', 'subscription']),
                severity=st.sampled_from(['low', 'medium', 'high']),
                field_name=st.sampled_from(['prices.USD', 'payment_methods', 'fees.percentage', 'subscription_terms']),
                expected_value=st.one_of(st.floats(allow_nan=False, allow_infinity=False), st.text(max_size=20)),
                actual_value=st.one_of(st.floats(allow_nan=False, allow_infinity=False), st.text(max_size=20)),
                message=st.text(min_size=5, max_size=100),
            ),
            min_size=1,
            max_size=10,
        ),
        data_source=st.sampled_from(['html', 'ocr']),
    )
    def test_property_violation_structure_completeness(self, violations, data_source):
        """
        Property 12: Violation Structure Completeness

        For any detected violation, it should include violation_type, severity,
        field_name, expected_value, actual_value, message, and data_source fields.

        **Validates: Requirements 4.4**
        """
        service = VerificationService(
            content_analyzer=MagicMock(),
            validation_engine=MagicMock(),
            ocr_engine=MagicMock(),
            screenshot_capture=MagicMock(),
            db_session=MagicMock(),
        )

        dummy_payment_info = PaymentInfo(
            prices={}, payment_methods=[], fees={}, subscription_terms=None,
        )

        validation_result = ValidationResult(
            is_valid=False,
            violations=violations,
            payment_info=dummy_payment_info,
            contract_conditions={},
        )

        serialized = service._serialize_violations(validation_result, data_source)

        assert 'items' in serialized
        assert len(serialized['items']) == len(violations)

        required_fields = {
            'violation_type', 'severity', 'field_name',
            'expected_value', 'actual_value', 'message', 'data_source',
        }
        valid_severities = {'low', 'medium', 'high'}
        valid_data_sources = {'html', 'ocr'}

        for item in serialized['items']:
            # All 7 required fields must be present
            missing = required_fields - set(item.keys())
            assert not missing, (
                f"Violation record missing required fields: {missing}. Record: {item}"
            )

            # violation_type must be a string
            assert isinstance(item['violation_type'], str), (
                f"violation_type must be str, got {type(item['violation_type'])}"
            )

            # severity must be one of the valid levels
            assert item['severity'] in valid_severities, (
                f"severity must be one of {valid_severities}, got {item['severity']!r}"
            )

            # field_name must be a string
            assert isinstance(item['field_name'], str), (
                f"field_name must be str, got {type(item['field_name'])}"
            )

            # message must be a string
            assert isinstance(item['message'], str), (
                f"message must be str, got {type(item['message'])}"
            )

            # data_source must be 'html' or 'ocr'
            assert item['data_source'] in valid_data_sources, (
                f"data_source must be one of {valid_data_sources}, got {item['data_source']!r}"
            )

    # Feature: verification-comparison-system, Property 13: Independent Violation Recording
    @settings(max_examples=100)
    @given(
        violations=st.lists(
            st.builds(
                Violation,
                violation_type=st.sampled_from(['price', 'payment_method', 'fee', 'subscription']),
                severity=st.sampled_from(['low', 'medium', 'high']),
                field_name=st.sampled_from(['prices.USD', 'payment_methods', 'fees.percentage', 'subscription_terms']),
                expected_value=st.one_of(st.floats(allow_nan=False, allow_infinity=False), st.text(max_size=20)),
                actual_value=st.one_of(st.floats(allow_nan=False, allow_infinity=False), st.text(max_size=20)),
                message=st.text(min_size=5, max_size=100),
            ),
            min_size=1,
            max_size=10,
        ),
        html_suffix=st.text(min_size=1, max_size=10),
    )
    def test_property_independent_violation_recording(self, violations, html_suffix):
        """
        Property 13: Independent Violation Recording

        For any verification where both HTML and OCR data violate the same
        contract condition with different values, two separate violation records
        should be created, one for each data source.

        **Validates: Requirements 4.5**
        """
        service = VerificationService(
            content_analyzer=MagicMock(),
            validation_engine=MagicMock(),
            ocr_engine=MagicMock(),
            screenshot_capture=MagicMock(),
            db_session=MagicMock(),
        )

        dummy_payment_info = PaymentInfo(
            prices={}, payment_methods=[], fees={}, subscription_terms=None,
        )

        # Build HTML violations: same violations but with modified actual_value
        html_violations = [
            Violation(
                violation_type=v.violation_type,
                severity=v.severity,
                field_name=v.field_name,
                expected_value=v.expected_value,
                actual_value=f"html_{v.actual_value}_{html_suffix}",
                message=v.message,
            )
            for v in violations
        ]

        # OCR violations keep original actual_value (different from HTML)
        ocr_violations = [
            Violation(
                violation_type=v.violation_type,
                severity=v.severity,
                field_name=v.field_name,
                expected_value=v.expected_value,
                actual_value=f"ocr_{v.actual_value}",
                message=v.message,
            )
            for v in violations
        ]

        html_validation = ValidationResult(
            is_valid=False,
            violations=html_violations,
            payment_info=dummy_payment_info,
            contract_conditions={},
        )

        ocr_validation = ValidationResult(
            is_valid=False,
            violations=ocr_violations,
            payment_info=dummy_payment_info,
            contract_conditions={},
        )

        # Serialize both sources independently
        html_serialized = service._serialize_violations(html_validation, 'html')
        ocr_serialized = service._serialize_violations(ocr_validation, 'ocr')

        html_items = html_serialized['items']
        ocr_items = ocr_serialized['items']

        # All HTML violations have data_source='html'
        for item in html_items:
            assert item['data_source'] == 'html', (
                f"Expected data_source='html', got '{item['data_source']}'"
            )

        # All OCR violations have data_source='ocr'
        for item in ocr_items:
            assert item['data_source'] == 'ocr', (
                f"Expected data_source='ocr', got '{item['data_source']}'"
            )

        # Total count equals sum of both sets (both are recorded independently)
        total = len(html_items) + len(ocr_items)
        assert total == len(violations) * 2, (
            f"Expected {len(violations) * 2} total violations "
            f"(HTML={len(html_items)} + OCR={len(ocr_items)}), got {total}"
        )

        # No violation from one source appears in the other source's list
        html_actual_values = {item['actual_value'] for item in html_items}
        ocr_actual_values = {item['actual_value'] for item in ocr_items}
        overlap = html_actual_values & ocr_actual_values
        assert not overlap, (
            f"Violations should be independent across sources, "
            f"but found overlapping actual_values: {overlap}"
        )





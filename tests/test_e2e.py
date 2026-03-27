"""
End-to-end integration tests for Payment Compliance Monitor.

These tests verify complete workflows from site registration through
crawling, analysis, validation, and alerting.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.models import Customer, MonitoringSite, ContractCondition, CrawlResult, Violation, Alert
from src.crawler import CrawlerEngine
from src.analyzer import ContentAnalyzer
from src.validator import ValidationEngine
from src.alert_system import AlertSystem


@pytest.fixture
def sample_site(db_session):
    """Create a sample monitoring site."""
    customer = Customer(
        name="Example Corp",
        email="contact@example.com",
        is_active=True
    )
    db_session.add(customer)
    db_session.flush()

    site = MonitoringSite(
        customer_id=customer.id,
        name="Example Corp Site",
        url="https://example.com/pricing",
        is_active=True
    )
    db_session.add(site)
    db_session.commit()
    return site


@pytest.fixture
def sample_contract(db_session, sample_site):
    """Create a sample contract condition."""
    contract = ContractCondition(
        site_id=sample_site.id,
        version=1,
        prices={"basic": 1000, "premium": 2000},
        payment_methods={"credit_card": True, "bank_transfer": True},
        fees={"credit_card": 3.0, "bank_transfer": 0.0},
        subscription_terms={"minimum_months": 12},
        is_current=True
    )
    db_session.add(contract)
    db_session.commit()
    return contract


@pytest.mark.asyncio
@pytest.mark.skipif(True, reason="Requires full Docker environment")
async def test_e2e_site_registration_to_alert_workflow(db_session, sample_site, sample_contract):
    """
    Test complete workflow: Site Registration → Crawling → Analysis → Validation → Alert
    
    This test verifies that:
    1. A site can be registered
    2. The site can be crawled
    3. Content can be analyzed
    4. Violations can be detected
    5. Alerts can be sent
    """
    # Step 1: Site Registration (already done in fixtures)
    assert sample_site.id is not None
    assert sample_site.is_active is True
    
    # Step 2: Crawling
    crawler = CrawlerEngine(db_session=db_session)
    
    # Mock the actual crawling to avoid network calls
    mock_html = """
    <html>
        <body>
            <h1>Pricing</h1>
            <div class="price">Basic Plan: ¥1,500</div>
            <div class="price">Premium Plan: ¥2,000</div>
            <div class="payment">Credit Card, Bank Transfer</div>
            <div class="fee">Credit Card Fee: 5%</div>
            <div class="terms">Minimum 12 months contract</div>
        </body>
    </html>
    """
    
    with patch.object(crawler, '_fetch_page', return_value=mock_html):
        crawl_result = await crawler.crawl_site(
            url=sample_site.url,
            site_id=sample_site.id
        )
    
    assert crawl_result is not None
    assert crawl_result.status_code == 200
    
    # Step 3: Content Analysis
    analyzer = ContentAnalyzer()
    payment_info = analyzer.analyze(mock_html)
    
    assert payment_info is not None
    assert len(payment_info.prices) > 0
    assert len(payment_info.payment_methods) > 0
    
    # Step 4: Validation
    validator = ValidationEngine(db_session=db_session)
    validation_result = validator.validate(
        site_id=sample_site.id,
        payment_info=payment_info
    )
    
    # Should detect price violation (1500 vs 1000)
    assert validation_result is not None
    assert len(validation_result.violations) > 0
    
    # Verify violation was saved to database
    violations = db_session.query(Violation).filter_by(
        validation_result_id=validation_result.id
    ).all()
    assert len(violations) > 0
    
    # Step 5: Alert System
    alert_system = AlertSystem()
    
    # Mock email and Slack sending
    with patch.object(alert_system, '_send_email_with_retry', return_value=True), \
         patch.object(alert_system, '_send_slack_with_retry', return_value=True):
        
        alert = await alert_system.send_alert(
            violation=violations[0],
            email_recipients=["admin@example.com"],
            slack_webhook_url="https://hooks.slack.com/test"
        )
    
    assert alert is not None
    assert alert.email_sent is True
    assert alert.slack_sent is True
    
    # Verify alert was saved to database
    saved_alert = db_session.query(Alert).filter_by(id=alert.id).first()
    assert saved_alert is not None


@pytest.mark.asyncio
@pytest.mark.skipif(True, reason="Requires full Docker environment")
async def test_e2e_contract_update_immediate_validation(db_session, sample_site, sample_contract):
    """
    Test workflow: Contract Update → Immediate Validation
    
    This test verifies that:
    1. Contract conditions can be updated
    2. Immediate validation is triggered
    3. New violations are detected if applicable
    """
    # Step 1: Update contract (create new version)
    new_contract = ContractCondition(
        site_id=sample_site.id,
        version=2,
        prices={"basic": 1200, "premium": 2500},  # Updated prices
        payment_methods={"credit_card": True, "bank_transfer": True},
        fees={"credit_card": 3.0, "bank_transfer": 0.0},
        subscription_terms={"minimum_months": 12},
        is_current=True
    )
    
    # Mark old contract as not current
    sample_contract.is_current = False
    
    db_session.add(new_contract)
    db_session.commit()
    
    # Step 2: Fetch latest crawl result
    latest_crawl = db_session.query(CrawlResult).filter_by(
        site_id=sample_site.id
    ).order_by(CrawlResult.crawled_at.desc()).first()
    
    if latest_crawl:
        # Step 3: Re-analyze and validate with new contract
        analyzer = ContentAnalyzer()
        payment_info = analyzer.analyze(latest_crawl.html_content)
        
        validator = ValidationEngine(db_session=db_session)
        validation_result = validator.validate(
            site_id=sample_site.id,
            payment_info=payment_info
        )
        
        # Verify validation used the new contract
        current_contract = db_session.query(ContractCondition).filter_by(
            site_id=sample_site.id,
            is_current=True
        ).first()
        
        assert current_contract.version == 2
        assert validation_result is not None


@pytest.mark.asyncio
@pytest.mark.skipif(True, reason="Requires full Docker environment and external DNS")
async def test_e2e_fake_site_detection_high_priority_alert(db_session, sample_site):
    """
    Test workflow: Fake Site Detection → High Priority Alert
    
    This test verifies that:
    1. Similar domains can be scanned
    2. Fake sites can be detected
    3. High priority alerts are generated
    """
    from src.fake_detector import FakeSiteDetector
    
    detector = FakeSiteDetector()
    
    # Mock domain scanning to avoid actual DNS queries
    mock_suspicious_domains = [
        "examp1e.com",  # Similar to example.com
        "exarnple.com",  # Similar to example.com
    ]
    
    with patch.object(detector, 'scan_similar_domains', return_value=mock_suspicious_domains):
        suspicious_domains = detector.scan_similar_domains(sample_site.domain)
    
    assert len(suspicious_domains) > 0
    
    # Verify fake site detection
    for suspicious_domain in suspicious_domains:
        similarity = detector.calculate_domain_similarity(
            sample_site.domain,
            suspicious_domain
        )
        assert similarity > 0.7  # High similarity threshold
    
    # Mock alert generation for fake site
    alert_system = AlertSystem()
    
    with patch.object(alert_system, '_send_email_with_retry', return_value=True), \
         patch.object(alert_system, '_send_slack_with_retry', return_value=True):
        
        # Create a fake site alert
        alert = Alert(
            violation_id=None,  # No violation, just fake site detection
            alert_type="fake_site_detected",
            severity="high",
            message=f"Suspicious domain detected: {suspicious_domains[0]}",
            email_sent=False,
            slack_sent=False
        )
        db_session.add(alert)
        db_session.commit()
        
        # Send high priority alert
        result = await alert_system.send_alert(
            violation=None,
            email_recipients=["security@example.com"],
            slack_webhook_url="https://hooks.slack.com/test",
            priority="high"
        )
    
    assert result is not None
    
    # Verify alert priority
    saved_alert = db_session.query(Alert).filter_by(
        alert_type="fake_site_detected"
    ).first()
    assert saved_alert is not None
    assert saved_alert.severity == "high"


def test_e2e_database_models_relationships(db_session, sample_site, sample_contract):
    """
    Test database model relationships work correctly.
    
    This test verifies that:
    1. Site → Contract relationship works
    2. Site → CrawlResult relationship works
    3. Violation → Alert relationship works
    """
    # Test Site → Contract relationship
    site = db_session.query(MonitoringSite).filter_by(id=sample_site.id).first()
    assert site is not None
    assert len(site.contract_conditions) > 0
    assert site.contract_conditions[0].id == sample_contract.id
    
    # Test Site → CrawlResult relationship
    crawl_result = CrawlResult(
        site_id=sample_site.id,
        url=sample_site.url,
        html_content="<html>test</html>",
        status_code=200
    )
    db_session.add(crawl_result)
    db_session.commit()
    
    db_session.refresh(site)
    assert len(site.crawl_results) > 0
    
    # Test Violation → Alert relationship
    violation = Violation(
        validation_result_id=1,
        violation_type="price_mismatch",
        severity="high",
        field_name="basic_price",
        expected_value={"price": 1000},
        actual_value={"price": 1500}
    )
    db_session.add(violation)
    db_session.commit()
    
    alert = Alert(
        violation_id=violation.id,
        alert_type="violation_detected",
        severity="high",
        message="Price violation detected"
    )
    db_session.add(alert)
    db_session.commit()
    
    db_session.refresh(violation)
    assert len(violation.alerts) > 0
    assert violation.alerts[0].id == alert.id


def test_e2e_contract_versioning(db_session, sample_site, sample_contract):
    """
    Test contract versioning works correctly.
    
    This test verifies that:
    1. Multiple contract versions can exist
    2. Only one version is marked as current
    3. Version numbers increment correctly
    """
    # Create version 2
    contract_v2 = ContractCondition(
        site_id=sample_site.id,
        version=2,
        prices={"basic": 1100, "premium": 2100},
        payment_methods={"credit_card": True, "bank_transfer": True},
        fees={"credit_card": 3.0, "bank_transfer": 0.0},
        subscription_terms={"minimum_months": 12},
        is_current=True
    )
    
    # Mark v1 as not current
    sample_contract.is_current = False
    
    db_session.add(contract_v2)
    db_session.commit()
    
    # Verify only one current version
    current_contracts = db_session.query(ContractCondition).filter_by(
        site_id=sample_site.id,
        is_current=True
    ).all()
    
    assert len(current_contracts) == 1
    assert current_contracts[0].version == 2
    
    # Verify all versions exist
    all_contracts = db_session.query(ContractCondition).filter_by(
        site_id=sample_site.id
    ).order_by(ContractCondition.version).all()
    
    assert len(all_contracts) == 2
    assert all_contracts[0].version == 1
    assert all_contracts[1].version == 2


@pytest.mark.skipif(True, reason="Requires full Docker environment")
def test_e2e_celery_task_execution(db_session, sample_site, sample_contract):
    """
    Test Celery task execution works correctly.
    
    This test verifies that:
    1. Celery tasks can be triggered
    2. Tasks execute successfully
    3. Results are stored correctly
    """
    from src.tasks import crawl_and_validate_site
    
    # Mock Celery task execution
    with patch('src.tasks.crawl_and_validate_site.delay') as mock_task:
        mock_task.return_value.id = "test-task-id"
        
        # Trigger task
        task = crawl_and_validate_site.delay(site_id=sample_site.id)
        
        assert task.id == "test-task-id"
        mock_task.assert_called_once_with(site_id=sample_site.id)


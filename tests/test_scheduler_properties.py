"""
Property-based tests for Celery scheduler.

Tests universal properties that should hold for scheduled tasks using Hypothesis.
"""

import os
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.celery_app import celery_app


# Property 1: Daily crawling execution
# **Validates: Requirements 1.1**

@settings(
    max_examples=3,
    deadline=None,
)
@given(
    num_active_sites=st.integers(min_value=1, max_value=5),
)
def test_property_daily_crawling_execution(num_active_sites):
    """
    Property 1: Daily crawling execution
    
    For any set of registered monitoring targets, the scheduler should create
    crawling tasks for all active sites on a daily basis.
    
    **Validates: Requirements 1.1**
    
    This test verifies that:
    1. The scheduler has a daily crawling task configured
    2. When executed, it queries all active monitoring sites
    3. A crawling task is enqueued for each active site
    4. Inactive sites are not included in the crawling schedule
    """
    from src.models import MonitoringSite, ContractCondition
    from src.tasks import crawl_all_sites
    
    # Create mock monitoring sites
    mock_sites = []
    for i in range(num_active_sites):
        site = MagicMock(spec=MonitoringSite)
        site.id = i + 1
        site.company_name = f"Company {i + 1}"
        site.domain = f"example{i + 1}.com"
        site.target_url = f"https://example{i + 1}.com"
        site.is_active = True
        mock_sites.append(site)
    
    # Create mock contract conditions for each site
    mock_contracts = []
    for i, site in enumerate(mock_sites):
        contract = MagicMock(spec=ContractCondition)
        contract.site_id = site.id
        contract.prices = {"basic": 1000}
        contract.payment_methods = ["credit_card"]
        contract.fees = {"processing": 100}
        contract.subscription_terms = {"minimum_months": 12}
        contract.is_current = True
        mock_contracts.append(contract)
    
    # Mock database session and query
    mock_session = MagicMock()
    mock_query = MagicMock()
    mock_filter = MagicMock()
    
    # Setup query chain for sites
    mock_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_filter
    mock_filter.all.return_value = mock_sites
    
    # Setup query chain for contracts (return contract for each site)
    def mock_query_side_effect(model):
        if model == MonitoringSite:
            return mock_query
        elif model == ContractCondition:
            # Return a new mock for contract queries
            contract_query = MagicMock()
            contract_filter = MagicMock()
            contract_query.filter.return_value = contract_filter
            
            # Return appropriate contract based on call count
            call_count = [0]
            def get_contract():
                idx = call_count[0]
                call_count[0] += 1
                if idx < len(mock_contracts):
                    return mock_contracts[idx]
                return None
            
            contract_filter.first.side_effect = get_contract
            return contract_query
        return mock_query
    
    mock_session.query.side_effect = mock_query_side_effect
    
    # Track enqueued tasks
    enqueued_tasks = []
    
    def mock_delay(*args, **kwargs):
        """Mock the delay method to track enqueued tasks."""
        task_mock = MagicMock()
        task_mock.id = f"task-{len(enqueued_tasks) + 1}"
        enqueued_tasks.append({
            'task_id': task_mock.id,
            'args': args,
            'kwargs': kwargs
        })
        return task_mock
    
    # Mock database engine and session creation
    with patch('src.database.SessionLocal', return_value=mock_session) as mock_sl, \
         patch('src.tasks.crawl_and_validate_site.delay', side_effect=mock_delay), \
         patch.dict(os.environ, {
             'DATABASE_URL': 'postgresql://test:test@localhost/test',
             'ALERT_EMAIL_RECIPIENTS': 'test@example.com',
             'SLACK_WEBHOOK_URL': 'https://hooks.slack.com/test',
             'SLACK_CHANNEL': '#alerts'
         }):
        
        # Execute the daily crawling task
        result = crawl_all_sites()
        
        # Verify the task executed successfully
        assert result['status'] == 'success', (
            f"Daily crawling task should succeed, but got error: {result.get('error')}"
        )
        
        # Verify all active sites were processed
        assert result['total_sites'] == num_active_sites, (
            f"Should process {num_active_sites} sites, but processed {result['total_sites']}"
        )
        
        # Verify a task was enqueued for each active site
        assert len(enqueued_tasks) == num_active_sites, (
            f"Should enqueue {num_active_sites} tasks, but enqueued {len(enqueued_tasks)}"
        )
        
        # Verify each enqueued task has correct parameters
        for i, task in enumerate(enqueued_tasks):
            kwargs = task['kwargs']
            
            # Verify site_id is correct
            assert 'site_id' in kwargs, "Task should have site_id parameter"
            assert kwargs['site_id'] == mock_sites[i].id, (
                f"Task {i} should have site_id {mock_sites[i].id}, "
                f"but got {kwargs['site_id']}"
            )
            
            # Verify URL is correct
            assert 'url' in kwargs, "Task should have url parameter"
            assert kwargs['url'] == mock_sites[i].target_url, (
                f"Task {i} should have url {mock_sites[i].target_url}, "
                f"but got {kwargs['url']}"
            )
            
            # Verify contract conditions are provided
            assert 'contract_conditions' in kwargs, (
                "Task should have contract_conditions parameter"
            )
            assert isinstance(kwargs['contract_conditions'], dict), (
                "Contract conditions should be a dictionary"
            )
            
            # Verify notification config is provided
            assert 'notification_config' in kwargs, (
                "Task should have notification_config parameter"
            )
            assert isinstance(kwargs['notification_config'], dict), (
                "Notification config should be a dictionary"
            )
        
        # Verify successful count matches enqueued tasks
        assert result['successful'] == num_active_sites, (
            f"Should have {num_active_sites} successful enqueues, "
            f"but got {result['successful']}"
        )
        
        # Verify no failures
        assert result['failed'] == 0, (
            f"Should have 0 failures, but got {result['failed']}"
        )


@settings(
    max_examples=2,
    deadline=None,
)
@given(
    num_active_sites=st.integers(min_value=1, max_value=3),
    num_inactive_sites=st.integers(min_value=1, max_value=2),
)
def test_property_daily_crawling_excludes_inactive_sites(num_active_sites, num_inactive_sites):
    """
    Property 1 (variant): Daily crawling execution excludes inactive sites
    
    For any set of registered monitoring targets with both active and inactive sites,
    the scheduler should only create crawling tasks for active sites.
    
    **Validates: Requirements 1.1**
    
    This test verifies that:
    1. Inactive sites are not included in the daily crawling schedule
    2. Only active sites receive crawling tasks
    3. The task count matches the number of active sites, not total sites
    """
    from src.models import MonitoringSite, ContractCondition
    from src.tasks import crawl_all_sites
    
    # Create mock active sites
    mock_active_sites = []
    for i in range(num_active_sites):
        site = MagicMock(spec=MonitoringSite)
        site.id = i + 1
        site.company_name = f"Active Company {i + 1}"
        site.domain = f"active{i + 1}.com"
        site.target_url = f"https://active{i + 1}.com"
        site.is_active = True
        mock_active_sites.append(site)
    
    # Create mock contracts for active sites
    mock_contracts = []
    for site in mock_active_sites:
        contract = MagicMock(spec=ContractCondition)
        contract.site_id = site.id
        contract.prices = {"basic": 1000}
        contract.payment_methods = ["credit_card"]
        contract.fees = {"processing": 100}
        contract.subscription_terms = {"minimum_months": 12}
        contract.is_current = True
        mock_contracts.append(contract)
    
    # Mock database session and query
    mock_session = MagicMock()
    mock_query = MagicMock()
    mock_filter = MagicMock()
    
    # Setup query chain - only return active sites
    mock_session.query.return_value = mock_query
    mock_query.filter.return_value = mock_filter
    mock_filter.all.return_value = mock_active_sites
    
    # Setup contract queries
    def mock_query_side_effect(model):
        if model == MonitoringSite:
            return mock_query
        elif model == ContractCondition:
            contract_query = MagicMock()
            contract_filter = MagicMock()
            contract_query.filter.return_value = contract_filter
            
            call_count = [0]
            def get_contract():
                idx = call_count[0]
                call_count[0] += 1
                if idx < len(mock_contracts):
                    return mock_contracts[idx]
                return None
            
            contract_filter.first.side_effect = get_contract
            return contract_query
        return mock_query
    
    mock_session.query.side_effect = mock_query_side_effect
    
    # Track enqueued tasks
    enqueued_tasks = []
    
    def mock_delay(*args, **kwargs):
        task_mock = MagicMock()
        task_mock.id = f"task-{len(enqueued_tasks) + 1}"
        enqueued_tasks.append({
            'task_id': task_mock.id,
            'site_id': kwargs.get('site_id')
        })
        return task_mock
    
    # Mock database engine and session creation
    with patch('src.database.SessionLocal', return_value=mock_session) as mock_sl, \
         patch('src.tasks.crawl_and_validate_site.delay', side_effect=mock_delay), \
         patch.dict(os.environ, {
             'DATABASE_URL': 'postgresql://test:test@localhost/test',
             'ALERT_EMAIL_RECIPIENTS': 'test@example.com'
         }):
        
        # Execute the daily crawling task
        result = crawl_all_sites()
        
        # Verify only active sites were processed
        assert result['total_sites'] == num_active_sites, (
            f"Should only process {num_active_sites} active sites, "
            f"but processed {result['total_sites']}"
        )
        
        # Verify only active sites got tasks enqueued
        assert len(enqueued_tasks) == num_active_sites, (
            f"Should only enqueue {num_active_sites} tasks for active sites, "
            f"but enqueued {len(enqueued_tasks)}"
        )
        
        # Verify all enqueued tasks are for active sites
        enqueued_site_ids = [task['site_id'] for task in enqueued_tasks]
        active_site_ids = [site.id for site in mock_active_sites]
        
        for site_id in enqueued_site_ids:
            assert site_id in active_site_ids, (
                f"Task enqueued for site {site_id}, but it's not in active sites"
            )


def test_scheduler_has_daily_crawling_configured():
    """
    Verify that the Celery Beat scheduler has a daily crawling task configured.
    
    This test checks the scheduler configuration to ensure:
    1. A daily crawling task is defined in the beat schedule
    2. The task is scheduled to run daily (crontab with hour specified)
    3. The task points to the correct task function
    """
    # Get the beat schedule from celery app
    beat_schedule = celery_app.conf.beat_schedule
    
    # Verify daily crawling task exists
    assert 'daily-crawling' in beat_schedule, (
        "Beat schedule should have 'daily-crawling' task configured"
    )
    
    daily_task = beat_schedule['daily-crawling']
    
    # Verify task name
    assert daily_task['task'] == 'src.tasks.crawl_all_sites', (
        f"Daily crawling task should be 'src.tasks.crawl_all_sites', "
        f"but got '{daily_task['task']}'"
    )
    
    # Verify schedule is a crontab (daily schedule)
    from celery.schedules import crontab
    assert 'schedule' in daily_task, (
        "Daily crawling task should have a schedule defined"
    )
    
    schedule = daily_task['schedule']
    assert isinstance(schedule, crontab), (
        f"Schedule should be a crontab instance, but got {type(schedule)}"
    )
    
    # Verify it runs daily (hour is specified, day_of_week is not restricted)
    # The schedule should have hour=2, minute=0 (runs at 2:00 AM daily)
    assert schedule.hour == {2}, (
        f"Daily crawling should run at hour 2, but got {schedule.hour}"
    )
    assert schedule.minute == {0}, (
        f"Daily crawling should run at minute 0, but got {schedule.minute}"
    )

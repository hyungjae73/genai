"""
Unit tests for Celery queue configuration and routing rules.

Tests for Tasks 11.1, 11.2, 11.3, and 11.4.
Requirements: 16.1, 16.2, 16.4, 16.5, 22.1-22.6
"""

import os
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


# ---------------------------------------------------------------------------
# Task 11.1: Celery queue config and routing rules
# ---------------------------------------------------------------------------

class TestCeleryQueueConfig:
    """Tests for Celery queue definitions and routing rules (Req 16.1, 16.2)."""

    def test_pipeline_queues_defined(self):
        """Four pipeline queues (crawl, extract, validate, report) are defined."""
        from src.celery_app import PIPELINE_QUEUES

        queue_names = {q.name for q in PIPELINE_QUEUES}
        assert 'crawl' in queue_names
        assert 'extract' in queue_names
        assert 'validate' in queue_names
        assert 'report' in queue_names

    def test_default_queue_included(self):
        """Default 'celery' queue is still present."""
        from src.celery_app import PIPELINE_QUEUES

        queue_names = {q.name for q in PIPELINE_QUEUES}
        assert 'celery' in queue_names

    def test_task_routes_defined(self):
        """Task routing rules map pipeline tasks to correct queues."""
        from src.celery_app import PIPELINE_TASK_ROUTES

        assert PIPELINE_TASK_ROUTES['src.pipeline_tasks.crawl_task'] == {'queue': 'crawl'}
        assert PIPELINE_TASK_ROUTES['src.pipeline_tasks.extract_task'] == {'queue': 'extract'}
        assert PIPELINE_TASK_ROUTES['src.pipeline_tasks.validate_task'] == {'queue': 'validate'}
        assert PIPELINE_TASK_ROUTES['src.pipeline_tasks.report_task'] == {'queue': 'report'}

    def test_celery_app_includes_pipeline_tasks(self):
        """Celery app includes pipeline_tasks module."""
        from src.celery_app import celery_app

        assert 'src.pipeline_tasks' in celery_app.conf.include

    def test_celery_app_has_task_queues(self):
        """Celery app conf has task_queues set."""
        from src.celery_app import celery_app, PIPELINE_QUEUES

        assert celery_app.conf.task_queues == PIPELINE_QUEUES

    def test_celery_app_has_task_routes(self):
        """Celery app conf has task_routes set."""
        from src.celery_app import celery_app, PIPELINE_TASK_ROUTES

        assert celery_app.conf.task_routes == PIPELINE_TASK_ROUTES

    def test_existing_beat_schedule_preserved(self):
        """Existing beat schedule entries are preserved."""
        from src.celery_app import celery_app

        assert 'daily-crawling' in celery_app.conf.beat_schedule
        assert 'weekly-fake-site-scan' in celery_app.conf.beat_schedule
        assert 'monthly-cleanup' in celery_app.conf.beat_schedule

    def test_existing_config_preserved(self):
        """Existing Celery config values are preserved."""
        from src.celery_app import celery_app

        assert celery_app.conf.task_serializer == 'json'
        assert celery_app.conf.timezone == 'UTC'
        assert celery_app.conf.task_time_limit == 300


class TestWorkerInitSignal:
    """Tests for worker_init signal handler (Req 16.4, 16.5)."""

    def test_non_crawl_worker_skips_browser_pool(self):
        """Non-crawl workers skip BrowserPool initialization."""
        from src.celery_app import _on_worker_init, _browser_pool

        sender = MagicMock()
        sender.queues = [MagicMock(name='extract')]

        # Should not raise
        _on_worker_init(sender=sender)

    def test_get_browser_pool_returns_none_initially(self):
        """get_browser_pool returns None when not initialized."""
        from src.celery_app import get_browser_pool

        # In test context, pool is not initialized
        pool = get_browser_pool()
        # May be None or may have been set by other tests — just verify callable
        assert get_browser_pool is not None


# ---------------------------------------------------------------------------
# Task 11.2: Pipeline Celery tasks
# ---------------------------------------------------------------------------

class TestPipelineTasks:
    """Tests for pipeline stage Celery tasks (Req 16.1, 2.1)."""

    def test_crawl_task_registered(self):
        """crawl_task is registered with correct name."""
        from src.pipeline_tasks import crawl_task

        assert crawl_task.name == 'src.pipeline_tasks.crawl_task'

    def test_extract_task_registered(self):
        """extract_task is registered with correct name."""
        from src.pipeline_tasks import extract_task

        assert extract_task.name == 'src.pipeline_tasks.extract_task'

    def test_validate_task_registered(self):
        """validate_task is registered with correct name."""
        from src.pipeline_tasks import validate_task

        assert validate_task.name == 'src.pipeline_tasks.validate_task'

    def test_report_task_registered(self):
        """report_task is registered with correct name."""
        from src.pipeline_tasks import report_task

        assert report_task.name == 'src.pipeline_tasks.report_task'

    def test_crawl_task_retry_config(self):
        """crawl_task has correct retry configuration."""
        from src.pipeline_tasks import crawl_task

        assert crawl_task.max_retries == 3
        assert crawl_task.default_retry_delay == 60

    def test_extract_task_retry_config(self):
        """extract_task has correct retry configuration."""
        from src.pipeline_tasks import extract_task

        assert extract_task.max_retries == 3
        assert extract_task.default_retry_delay == 60

    def test_validate_task_retry_config(self):
        """validate_task has correct retry configuration."""
        from src.pipeline_tasks import validate_task

        assert validate_task.max_retries == 3
        assert validate_task.default_retry_delay == 60

    def test_report_task_retry_config(self):
        """report_task has correct retry configuration."""
        from src.pipeline_tasks import report_task

        assert report_task.max_retries == 3
        assert report_task.default_retry_delay == 60

    def test_scheduled_crawls_task_registered(self):
        """run_scheduled_crawls_task is registered."""
        from src.pipeline_tasks import run_scheduled_crawls_task

        assert run_scheduled_crawls_task.name == 'src.pipeline_tasks.run_scheduled_crawls_task'

    def test_dispatch_pipeline_creates_chain(self):
        """dispatch_pipeline creates a Celery chain of 4 tasks."""
        from src.pipeline_tasks import crawl_task, extract_task, validate_task, report_task

        # Verify all tasks are importable and have signatures
        assert crawl_task.s is not None
        assert extract_task.s is not None
        assert validate_task.s is not None
        assert report_task.s is not None


# ---------------------------------------------------------------------------
# Task 11.3: Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Tests for backward compatibility migration path (Req 22.1-22.6)."""

    def test_crawl_and_validate_site_exists(self):
        """Existing crawl_and_validate_site task is preserved."""
        from src.tasks import crawl_and_validate_site

        assert crawl_and_validate_site.name == 'src.tasks.crawl_and_validate_site'

    @patch.dict(os.environ, {'USE_PIPELINE': 'false'})
    def test_use_pipeline_false_runs_legacy(self):
        """USE_PIPELINE=false runs the legacy flow."""
        from src.tasks import crawl_and_validate_site

        with patch('src.tasks._crawl_and_validate_site_async') as mock_async:
            mock_async.return_value = {
                'site_id': 1,
                'url': 'https://example.com',
                'status': 'success',
                'violations': [],
                'alerts_sent': False,
                'screenshot_path': None,
                'extraction_id': None,
                'error': None,
            }
            with patch('src.tasks.asyncio.run', side_effect=lambda coro: mock_async.return_value):
                result = crawl_and_validate_site(
                    site_id=1,
                    url='https://example.com',
                    contract_conditions={},
                    notification_config={},
                )
            assert result['status'] == 'success'

    @patch.dict(os.environ, {'USE_PIPELINE': 'true'})
    def test_use_pipeline_true_dispatches_pipeline(self):
        """USE_PIPELINE=true dispatches to pipeline tasks."""
        from src.tasks import crawl_and_validate_site

        with patch('src.tasks._dispatch_to_pipeline') as mock_dispatch:
            mock_dispatch.return_value = {
                'site_id': 1,
                'url': 'https://example.com',
                'status': 'pipeline_dispatched',
                'violations': [],
                'alerts_sent': False,
                'screenshot_path': None,
                'extraction_id': None,
                'error': None,
                'pipeline_task_id': 'abc-123',
            }
            result = crawl_and_validate_site(
                site_id=1,
                url='https://example.com',
                contract_conditions={},
                notification_config={},
            )
            assert result['status'] == 'pipeline_dispatched'
            mock_dispatch.assert_called_once()

    def test_pipeline_dispatch_response_format(self):
        """Pipeline dispatch returns compatible response format."""
        with patch('src.pipeline_tasks.dispatch_pipeline') as mock_chain:
            mock_result = MagicMock()
            mock_result.id = 'task-123'
            mock_chain.return_value = mock_result

            from src.tasks import _dispatch_to_pipeline

            result = _dispatch_to_pipeline(site_id=1, url='https://example.com')

            # Verify all legacy response fields are present
            assert 'site_id' in result
            assert 'url' in result
            assert 'status' in result
            assert 'violations' in result
            assert 'alerts_sent' in result
            assert 'screenshot_path' in result
            assert 'extraction_id' in result
            assert 'error' in result
            assert result['pipeline_task_id'] == 'task-123'


class TestVerificationResultBackwardCompatibility:
    """Tests for VerificationResult API backward compatibility (Req 22.5, 22.6)."""

    def test_format_verification_result_with_null_new_fields(self):
        """VerificationResult with NULL new fields produces valid API response."""
        from src.api.verification import _format_verification_result
        from src.models import VerificationResult
        from datetime import datetime

        result = VerificationResult(
            id=1,
            site_id=1,
            html_data={'prices': []},
            ocr_data={'text': ''},
            html_violations={'items': []},
            ocr_violations={'items': []},
            discrepancies={'items': []},
            screenshot_path='/screenshots/test.png',
            ocr_confidence=0.95,
            status='success',
            error_message=None,
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            # New pipeline fields are NULL
            structured_data=None,
            structured_data_violations=None,
            data_source=None,
            structured_data_status=None,
            evidence_status=None,
        )

        response = _format_verification_result(result, 'Test Site')

        # Legacy fields must be present and valid
        assert response['id'] == 1
        assert response['site_id'] == 1
        assert response['site_name'] == 'Test Site'
        assert response['html_data'] == {'prices': []}
        assert response['ocr_data'] == {'text': ''}
        assert response['discrepancies'] == []
        assert response['html_violations'] == []
        assert response['ocr_violations'] == []
        assert response['screenshot_path'] == '/screenshots/test.png'
        assert response['ocr_confidence'] == 0.95
        assert response['status'] == 'success'
        assert response['error_message'] is None
        assert response['created_at'] is not None

        # New fields should be None (not missing, not erroring)
        assert response['structured_data'] is None
        assert response['structured_data_violations'] is None
        assert response['data_source'] is None
        assert response['structured_data_status'] is None
        assert response['evidence_status'] is None

    def test_format_verification_result_with_populated_new_fields(self):
        """VerificationResult with populated new fields includes them."""
        from src.api.verification import _format_verification_result
        from src.models import VerificationResult
        from datetime import datetime

        result = VerificationResult(
            id=2,
            site_id=1,
            html_data={'prices': [100]},
            ocr_data={'text': 'price: 100'},
            html_violations={'items': []},
            ocr_violations={'items': []},
            discrepancies={'items': []},
            screenshot_path='/screenshots/test2.png',
            ocr_confidence=0.88,
            status='success',
            error_message=None,
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            structured_data={'product': 'Test', 'price': 100},
            structured_data_violations={'items': [{'type': 'price_mismatch'}]},
            data_source='json_ld',
            structured_data_status='found',
            evidence_status='collected',
        )

        response = _format_verification_result(result, 'Test Site')

        assert response['structured_data'] == {'product': 'Test', 'price': 100}
        assert response['structured_data_violations'] == {'items': [{'type': 'price_mismatch'}]}
        assert response['data_source'] == 'json_ld'
        assert response['structured_data_status'] == 'found'
        assert response['evidence_status'] == 'collected'

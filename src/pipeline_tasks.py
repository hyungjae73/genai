"""
Celery tasks for the crawl pipeline architecture.

Defines stage tasks (crawl_task, extract_task, validate_task, report_task)
that receive serialized CrawlContext dicts, deserialize, run the stage,
and serialize the result for the next stage.

Requirements: 16.1, 2.1
"""

from __future__ import annotations

import logging
import os
from typing import Any

from celery import chain

from src.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage tasks — each receives a serialized CrawlContext dict
# ---------------------------------------------------------------------------

@celery_app.task(
    name='src.pipeline_tasks.crawl_task',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def crawl_task(self, ctx_dict: dict[str, Any]) -> dict[str, Any]:
    """PageFetcher stage task.

    Receives serialized CrawlContext, runs page_fetcher plugins,
    returns serialized CrawlContext for the next stage.

    Retry: max_retries=3, exponential backoff (60s base).
    """
    import asyncio

    try:
        return asyncio.run(_run_stage('page_fetcher', ctx_dict))
    except Exception as exc:
        retry_delay = 60 * (2 ** self.request.retries)
        logger.error(
            "crawl_task failed (attempt %d/%d): %s",
            self.request.retries + 1,
            self.max_retries + 1,
            exc,
        )
        raise self.retry(exc=exc, countdown=retry_delay)


@celery_app.task(
    name='src.pipeline_tasks.extract_task',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def extract_task(self, ctx_dict: dict[str, Any]) -> dict[str, Any]:
    """DataExtractor stage task.

    Receives serialized CrawlContext from crawl_task,
    runs data_extractor plugins, returns serialized CrawlContext.
    """
    import asyncio

    try:
        return asyncio.run(_run_stage('data_extractor', ctx_dict))
    except Exception as exc:
        retry_delay = 60 * (2 ** self.request.retries)
        logger.error(
            "extract_task failed (attempt %d/%d): %s",
            self.request.retries + 1,
            self.max_retries + 1,
            exc,
        )
        raise self.retry(exc=exc, countdown=retry_delay)


@celery_app.task(
    name='src.pipeline_tasks.validate_task',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def validate_task(self, ctx_dict: dict[str, Any]) -> dict[str, Any]:
    """Validator stage task.

    Receives serialized CrawlContext from extract_task,
    runs validator plugins, returns serialized CrawlContext.
    """
    import asyncio

    try:
        return asyncio.run(_run_stage('validator', ctx_dict))
    except Exception as exc:
        retry_delay = 60 * (2 ** self.request.retries)
        logger.error(
            "validate_task failed (attempt %d/%d): %s",
            self.request.retries + 1,
            self.max_retries + 1,
            exc,
        )
        raise self.retry(exc=exc, countdown=retry_delay)


@celery_app.task(
    name='src.pipeline_tasks.report_task',
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def report_task(self, ctx_dict: dict[str, Any]) -> dict[str, Any]:
    """Reporter stage task.

    Receives serialized CrawlContext from validate_task,
    runs reporter plugins, returns final serialized CrawlContext.
    """
    import asyncio

    try:
        return asyncio.run(_run_stage('reporter', ctx_dict))
    except Exception as exc:
        retry_delay = 60 * (2 ** self.request.retries)
        logger.error(
            "report_task failed (attempt %d/%d): %s",
            self.request.retries + 1,
            self.max_retries + 1,
            exc,
        )
        raise self.retry(exc=exc, countdown=retry_delay)


# ---------------------------------------------------------------------------
# Scheduled crawls task (for Celery Beat)
# ---------------------------------------------------------------------------

@celery_app.task(name='src.pipeline_tasks.run_scheduled_crawls_task')
def run_scheduled_crawls_task() -> dict[str, Any]:
    """Celery Beat task that triggers the CrawlScheduler."""
    from src.pipeline.scheduler import CrawlScheduler
    from src.pipeline.dispatcher import BatchDispatcher

    scheduler = CrawlScheduler(
        dispatcher=BatchDispatcher(),
        use_pipeline=True,
    )
    dispatched = scheduler.run_scheduled_crawls()
    return {'dispatched': dispatched}


# ---------------------------------------------------------------------------
# Pipeline chain helper
# ---------------------------------------------------------------------------

def dispatch_pipeline(ctx_dict: dict[str, Any]) -> Any:
    """Dispatch a full pipeline as a Celery chain.

    crawl_task → extract_task → validate_task → report_task

    Args:
        ctx_dict: Serialized CrawlContext dict.

    Returns:
        Celery AsyncResult for the chain.
    """
    pipeline_chain = chain(
        crawl_task.s(ctx_dict),
        extract_task.s(),
        validate_task.s(),
        report_task.s(),
    )
    return pipeline_chain.apply_async()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _run_stage(stage_name: str, ctx_dict: dict[str, Any]) -> dict[str, Any]:
    """Run a single pipeline stage on a deserialized CrawlContext.

    Args:
        stage_name: One of 'page_fetcher', 'data_extractor', 'validator', 'reporter'.
        ctx_dict: Serialized CrawlContext dict.

    Returns:
        Serialized CrawlContext dict after stage execution.
    """
    from src.pipeline.context import CrawlContext
    from src.pipeline.pipeline import CrawlPipeline

    # Deserialize CrawlContext (site is restored from site_id)
    ctx = CrawlContext.from_dict(ctx_dict)

    # Build a pipeline that only runs the specified stage
    pipeline = CrawlPipeline()
    ctx = await pipeline._run_stage(stage_name, ctx)

    # Serialize back for the next stage
    return ctx.to_dict()

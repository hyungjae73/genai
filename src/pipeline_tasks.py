"""
Celery tasks for the crawl pipeline architecture.

Defines stage tasks (crawl_task, extract_task, validate_task, report_task)
that receive serialized CrawlContext dicts, deserialize, run the stage,
and serialize the result for the next stage.

Also defines the perform_login task for distributed login with retry and locking.

Requirements: 16.1, 2.1, 7.2, 7.3, 7.4, 8.1, 8.3
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import redis.asyncio as aioredis
from celery import chain

from src.celery_app import celery_app
from src.pipeline.session_manager import SessionManager

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
# Login task — distributed lock + 3 retries (Req 7.2, 7.3, 7.4, 8.1, 8.3)
# ---------------------------------------------------------------------------

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')


@celery_app.task(
    name='src.pipeline_tasks.perform_login',
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    acks_late=True,
)
def perform_login(self, site_id: int) -> dict[str, Any]:
    """Login task with distributed lock and 3 retries.

    Flow:
    1. Acquire distributed lock (skip if already held by another worker)
    2. Perform login (placeholder — actual login logic is site-specific)
    3. Verify lock still held before saving cookies
    4. Release lock on completion
    5. Mark login_failed after 3 retries exhausted

    Requirements: 7.2, 7.3, 7.4, 8.1, 8.3
    """
    try:
        return asyncio.run(_perform_login_async(self, site_id))
    except self.MaxRetriesExceededError:
        # All 3 retries exhausted — mark login_failed (Req 7.4)
        asyncio.run(_mark_login_failed(site_id))
        logger.error(
            "perform_login exhausted all retries for site_id=%d, marked login_failed",
            site_id,
        )
        return {
            'site_id': site_id,
            'status': 'login_failed',
            'retries_exhausted': True,
        }


async def _perform_login_async(task, site_id: int) -> dict[str, Any]:
    """Async implementation of the login flow with distributed lock."""
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    session_mgr = SessionManager(redis_client)

    try:
        # Step 1: Acquire distributed lock (Req 8.1)
        lock_acquired = await session_mgr.acquire_login_lock(site_id)
        if not lock_acquired:
            logger.info(
                "Login lock already held for site_id=%d, skipping",
                site_id,
            )
            return {
                'site_id': site_id,
                'status': 'lock_held',
                'skipped': True,
            }

        try:
            # Step 2: Perform login (placeholder — site-specific logic)
            cookies = await _do_site_login(site_id)

            # Step 3: Verify lock still held before saving cookies (Req 8.3 / CTO Review Fix)
            lock_still_held = await session_mgr.verify_lock_held(site_id)
            if not lock_still_held:
                logger.warning(
                    "Login lock expired before cookie save for site_id=%d",
                    site_id,
                )
                raise RuntimeError(
                    f"Login lock expired before cookie save for site_id={site_id}"
                )

            # Step 4: Save refreshed cookies (Req 7.3)
            await session_mgr.save_cookies(site_id, cookies)
            logger.info("Login succeeded for site_id=%d, cookies saved", site_id)

            return {
                'site_id': site_id,
                'status': 'login_success',
                'cookies_saved': True,
            }
        finally:
            # Step 5: Release lock on completion (Req 8.3)
            await session_mgr.release_login_lock(site_id)
    finally:
        await redis_client.aclose()


async def _do_site_login(site_id: int) -> list[dict[str, Any]]:
    """Placeholder for site-specific login logic.

    In production, this would use Playwright to navigate to the login page,
    fill credentials, and extract cookies. For now, returns dummy cookies.
    """
    return [
        {
            'name': 'session_token',
            'value': f'token_for_site_{site_id}',
            'domain': f'site-{site_id}.example.com',
            'path': '/',
        }
    ]


async def _mark_login_failed(site_id: int) -> None:
    """Mark session as login_failed after retries exhausted (Req 7.4)."""
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    try:
        session_mgr = SessionManager(redis_client)
        await session_mgr.mark_login_failed(site_id)
    finally:
        await redis_client.aclose()


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

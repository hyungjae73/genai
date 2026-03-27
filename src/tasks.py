"""
Celery tasks for Payment Compliance Monitor.

This module defines asynchronous tasks for crawling, validation, and maintenance.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from src.celery_app import celery_app
from src.crawler import CrawlerEngine
from src.analyzer import ContentAnalyzer
from src.validator import ValidationEngine
from src.fake_detector import FakeSiteDetector, COMPOUND_TLDS
from src.alert_system import AlertSystem, NotificationConfig

logger = logging.getLogger(__name__)


@celery_app.task(name='src.tasks.crawl_and_validate_site')
def crawl_and_validate_site(
    site_id: int,
    url: str,
    contract_conditions: dict[str, Any],
    notification_config: dict[str, Any],
    crawl_job_id: int | None = None,
) -> dict[str, Any]:
    """
    Crawl a site, extract payment info, validate, and send alerts if needed.

    When USE_PIPELINE=true, dispatches to the new pipeline tasks instead
    of running the legacy monolithic flow. The response format is identical
    for both paths (Req 22.1-22.6).
    
    Args:
        site_id: Monitoring site ID
        url: URL to crawl
        contract_conditions: Contract conditions to validate against
        notification_config: Notification configuration
        crawl_job_id: Optional CrawlJob DB id for status tracking
    
    Returns:
        Task result with status and details
    """
    import os

    use_pipeline = os.getenv('USE_PIPELINE', 'false').lower() == 'true'

    if use_pipeline:
        return _dispatch_to_pipeline(site_id, url, crawl_job_id)

    return asyncio.run(_crawl_and_validate_site_async(
        site_id, url, contract_conditions, notification_config, crawl_job_id
    ))


def _dispatch_to_pipeline(
    site_id: int,
    url: str,
    crawl_job_id: int | None = None,
) -> dict[str, Any]:
    """Dispatch to the new pipeline via Celery chain.

    Builds a serialized CrawlContext and dispatches the pipeline chain.
    Returns a compatible response format (Req 22.5, 22.6).
    """
    from src.pipeline_tasks import dispatch_pipeline

    ctx_dict = {
        'site_id': site_id,
        'url': url,
        'html_content': None,
        'screenshots': [],
        'extracted_data': {},
        'violations': [],
        'evidence_records': [],
        'errors': [],
        'metadata': {},
    }

    if crawl_job_id is not None:
        ctx_dict['metadata']['crawl_job_id'] = crawl_job_id

    result = dispatch_pipeline(ctx_dict)

    return {
        'site_id': site_id,
        'url': url,
        'status': 'pipeline_dispatched',
        'violations': [],
        'alerts_sent': False,
        'screenshot_path': None,
        'extraction_id': None,
        'error': None,
        'pipeline_task_id': result.id if result else None,
    }


async def _crawl_and_validate_site_async(
    site_id: int,
    url: str,
    contract_conditions: dict[str, Any],
    notification_config: dict[str, Any],
    crawl_job_id: int | None = None,
) -> dict[str, Any]:
    """Async implementation of crawl_and_validate_site."""
    from src.extraction_config import ExtractionConfig
    from src.database import SessionLocal
    from src.models import CrawlJob

    config = ExtractionConfig()

    # Update CrawlJob status to running
    if crawl_job_id:
        _update_crawl_job_status(crawl_job_id, "running")

    result = {
        'site_id': site_id,
        'url': url,
        'status': 'success',
        'violations': [],
        'alerts_sent': False,
        'screenshot_path': None,
        'extraction_id': None,
        'error': None
    }
    
    try:
        # 1. Crawl site
        crawler = CrawlerEngine()
        crawl_result = await crawler.crawl_site(site_id=site_id, url=url)
        await crawler.close()
        
        if not crawl_result.success:
            result['status'] = 'crawl_failed'
            result['error'] = 'Failed to crawl site'
            if crawl_job_id:
                _update_crawl_job_status(crawl_job_id, "failed", error_message="Failed to crawl site")
            return result

        # 2. Launch screenshot capture as a background task (Req 19.2)
        screenshot_task = None
        if config.screenshot_enabled:
            async def _capture_screenshot() -> str | None:
                try:
                    from src.screenshot_manager import ScreenshotManager

                    screenshot_mgr = ScreenshotManager()
                    return await screenshot_mgr.capture_screenshot(
                        url=url,
                        site_id=site_id,
                        timeout=config.screenshot_timeout,
                    )
                except Exception as e:
                    logger.warning(
                        "Screenshot capture failed for site_id=%d: %s",
                        site_id, e,
                    )
                    return None

            screenshot_task = asyncio.create_task(_capture_screenshot())

        # 3. Extract payment info via HTML analysis (ContentAnalyzer)
        analyzer = ContentAnalyzer()
        payment_info = analyzer.extract_payment_info(crawl_result.html_content)

        # 4. Run structured data extraction pipeline + save both HTML and OCR results
        if config.extraction_enabled:
            try:
                import time as _time
                from src.extractors.payment_info_extractor import PaymentInfoExtractor
                from src.models import CrawlResult as CrawlResultModel, MonitoringSite, ExtractedPaymentInfo

                extraction_start = _time.monotonic()
                extractor = PaymentInfoExtractor()
                session = SessionLocal()
                try:
                    # Save crawl result to DB
                    db_crawl = CrawlResultModel(
                        site_id=site_id,
                        url=url,
                        html_content=crawl_result.html_content,
                        status_code=crawl_result.status_code,
                        crawled_at=crawl_result.crawled_at,
                    )
                    session.add(db_crawl)
                    session.flush()

                    crawl_result_id = db_crawl.id

                    if crawl_result_id:
                        # (A) Extract and save structured payment info (HTML source)
                        extraction_id = extractor.extract_and_save(
                            session=session,
                            html=crawl_result.html_content,
                            url=url,
                            crawl_result_id=crawl_result_id,
                            site_id=site_id,
                        )
                        result['extraction_id'] = extraction_id

                        # Tag the HTML extraction record with source='html'
                        if extraction_id:
                            html_record = session.query(ExtractedPaymentInfo).filter(
                                ExtractedPaymentInfo.id == extraction_id
                            ).first()
                            if html_record:
                                html_record.source = "html"
                                session.flush()

                        # (B) Save ContentAnalyzer result as a separate HTML-analysis record
                        #     (This captures the simpler regex-based extraction for comparison)
                        # Already covered by PaymentInfoExtractor above.

                        # (C) OCR extraction from screenshot
                        if screenshot_task is not None:
                            result['screenshot_path'] = await screenshot_task
                            screenshot_task = None

                        if result['screenshot_path']:
                            # Run OCR on the high-res copy for better accuracy
                            try:
                                from src.ocr_engine import OCREngine
                                from src.screenshot_manager import ScreenshotManager as _SM
                                from pathlib import Path

                                ocr_image = _SM.get_ocr_image_path(result['screenshot_path'])
                                ocr_engine = OCREngine()
                                ocr_result = ocr_engine.extract_text(Path(ocr_image))

                                if ocr_result.success and ocr_result.full_text:
                                    # Pass OCR text directly (not wrapped in HTML)
                                    # to preserve spatial structure from OCR regions
                                    ocr_payment_info = analyzer.extract_payment_info(
                                        ocr_result.full_text
                                    )

                                    ocr_record = ExtractedPaymentInfo(
                                        crawl_result_id=crawl_result_id,
                                        site_id=site_id,
                                        source="ocr",
                                        product_info=None,
                                        price_info=(
                                            [{"amount": p, "currency": c, "price_type": "ocr_detected"}
                                             for c, prices in ocr_payment_info.prices.items()
                                             for p in (prices if isinstance(prices, list) else [prices])]
                                            if ocr_payment_info.prices else None
                                        ),
                                        payment_methods=(
                                            [{"method_name": m} for m in ocr_payment_info.payment_methods]
                                            if ocr_payment_info.payment_methods else None
                                        ),
                                        fees=(
                                            [{"fee_type": k, "amount": v, "currency": "JPY"}
                                             for k, vals in ocr_payment_info.fees.items()
                                             for v in (vals if isinstance(vals, list) else [vals])]
                                            if ocr_payment_info.fees else None
                                        ),
                                        extraction_metadata={
                                            "ocr_confidence": ocr_result.average_confidence,
                                            "screenshot_path": result['screenshot_path'],
                                            "ocr_image_path": ocr_image,
                                            "ocr_text_length": len(ocr_result.full_text),
                                            "ocr_regions_count": len(ocr_result.regions),
                                        },
                                        overall_confidence_score=ocr_result.average_confidence,
                                        status="pending",
                                    )
                                    session.add(ocr_record)
                                    session.flush()
                                    logger.info(
                                        "OCR extraction saved for site_id=%d, crawl_result_id=%d",
                                        site_id, crawl_result_id,
                                    )
                                else:
                                    logger.warning(
                                        "OCR extraction returned no text for site_id=%d: %s",
                                        site_id, ocr_result.error_message or "empty text",
                                    )
                            except Exception as e:
                                logger.warning(
                                    "OCR extraction failed for site_id=%d: %s", site_id, e
                                )

                        extraction_elapsed = _time.monotonic() - extraction_start
                        logger.info(
                            "Data extraction completed in %.2fs for site_id=%d (Req 19.5)",
                            extraction_elapsed, site_id,
                        )

                        # Update screenshot path on crawl result
                        if result['screenshot_path'] and db_crawl:
                            db_crawl.screenshot_path = result['screenshot_path']
                            session.flush()

                        # Update site's last_crawled_at
                        site_record = session.query(MonitoringSite).filter(
                            MonitoringSite.id == site_id
                        ).first()
                        if site_record:
                            site_record.last_crawled_at = db_crawl.crawled_at

                        session.commit()
                except Exception:
                    session.rollback()
                    raise
                finally:
                    session.close()
            except Exception as e:
                logger.error(
                    "Extraction pipeline failed for site_id=%d: %s", site_id, e
                )

        # If screenshot task hasn't been consumed yet, await it now
        if screenshot_task is not None:
            result['screenshot_path'] = await screenshot_task
        
        # 5. Validate (existing logic preserved)
        validator = ValidationEngine(price_tolerance=5.0)
        validation_result = validator.validate_payment_info(
            payment_info, contract_conditions
        )
        
        # 6. Send alerts if violations detected
        if not validation_result.is_valid:
            result['violations'] = [
                {
                    'type': v.violation_type,
                    'severity': v.severity,
                    'field': v.field_name,
                    'message': v.message
                }
                for v in validation_result.violations
            ]
            
            alert_system = AlertSystem()
            alert_config = NotificationConfig(**notification_config)
            
            for violation in validation_result.violations:
                await alert_system.send_alert(
                    violation=violation,
                    site_info={'company_name': f'Site {site_id}', 'target_url': url},
                    notification_config=alert_config,
                    alert_id=site_id
                )
            
            result['alerts_sent'] = True

        # Update CrawlJob to completed
        if crawl_job_id:
            _update_crawl_job_status(crawl_job_id, "completed", result=result)
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        if crawl_job_id:
            _update_crawl_job_status(crawl_job_id, "failed", error_message=str(e))
    
    return result


def _update_crawl_job_status(
    crawl_job_id: int,
    status: str,
    result: dict | None = None,
    error_message: str | None = None,
) -> None:
    """Helper to update CrawlJob status in DB."""
    from src.database import SessionLocal
    from src.models import CrawlJob

    session = SessionLocal()
    try:
        job = session.query(CrawlJob).filter(CrawlJob.id == crawl_job_id).first()
        if job:
            job.status = status
            if result is not None:
                job.result = result
            if error_message is not None:
                job.error_message = error_message
            if status in ("completed", "failed"):
                job.completed_at = datetime.utcnow()
            session.commit()
    except Exception as e:
        session.rollback()
        logger.error("Failed to update CrawlJob %d: %s", crawl_job_id, e)
    finally:
        session.close()


@celery_app.task(name='src.tasks.scan_fake_sites')
def scan_fake_sites(
    legitimate_domain: str,
    candidate_domains: list[str],
    notification_config: dict[str, Any]
) -> dict[str, Any]:
    """
    Scan for fake sites similar to legitimate domain.
    
    Args:
        legitimate_domain: Legitimate domain to protect
        candidate_domains: List of candidate domains to check
        notification_config: Notification configuration
    
    Returns:
        Task result with detected fake sites
    """
    return asyncio.run(_scan_fake_sites_async(
        legitimate_domain, candidate_domains, notification_config
    ))


async def _scan_fake_sites_async(
    legitimate_domain: str,
    candidate_domains: list[str],
    notification_config: dict[str, Any]
) -> dict[str, Any]:
    """Async implementation of scan_fake_sites."""
    import httpx

    result: dict[str, Any] = {
        'legitimate_domain': legitimate_domain,
        'suspicious_domains': [],
        'confirmed_fakes': [],
        'alerts_sent': False,
        'error': None
    }

    try:
        # Scan for similar domains
        detector = FakeSiteDetector(
            domain_similarity_threshold=0.8,
            content_similarity_threshold=0.7
        )

        suspicious = detector.scan_similar_domains(
            legitimate_domain, candidate_domains
        )

        result['suspicious_domains'] = [
            {
                'domain': s.domain,
                'similarity_score': s.similarity_score
            }
            for s in suspicious
        ]

        if not suspicious:
            return result

        # Fetch legitimate site content once for comparison
        legitimate_url = f"https://{legitimate_domain}"
        legitimate_content: str | None = None
        legitimate_screenshot: str | None = None

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            verify=False,
        ) as client:
            # Fetch legitimate content
            try:
                resp = await client.get(legitimate_url)
                resp.raise_for_status()
                legitimate_content = resp.text
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                logger.warning(
                    "Failed to fetch legitimate site %s: %s", legitimate_domain, exc
                )
                return result
            except Exception as exc:
                logger.warning(
                    "Unexpected error fetching legitimate site %s: %s",
                    legitimate_domain, exc,
                )
                return result

            # Try to capture legitimate site screenshot
            try:
                from src.screenshot_manager import ScreenshotManager
                screenshot_mgr = ScreenshotManager()
                legitimate_screenshot = await screenshot_mgr.capture_screenshot(
                    url=legitimate_url, site_id=0, timeout=10
                )
            except Exception as exc:
                logger.warning(
                    "Screenshot capture failed for legitimate site %s: %s",
                    legitimate_domain, exc,
                )

            # Verify each suspicious domain
            for susp in suspicious:
                suspicious_url = f"https://{susp.domain}"
                try:
                    resp = await client.get(suspicious_url)
                    resp.raise_for_status()
                    suspicious_content = resp.text
                except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                    logger.warning(
                        "Failed to fetch suspicious site %s: %s", susp.domain, exc
                    )
                    continue
                except Exception as exc:
                    logger.warning(
                        "Unexpected error fetching suspicious site %s: %s",
                        susp.domain, exc,
                    )
                    continue

                # Try to capture suspicious site screenshot
                suspicious_screenshot: str | None = None
                try:
                    from src.screenshot_manager import ScreenshotManager
                    screenshot_mgr = ScreenshotManager()
                    suspicious_screenshot = await screenshot_mgr.capture_screenshot(
                        url=suspicious_url, site_id=0, timeout=10
                    )
                except Exception as exc:
                    logger.warning(
                        "Screenshot capture failed for suspicious site %s: %s",
                        susp.domain, exc,
                    )

                # Verify fake site with content comparison
                try:
                    verified = detector.verify_fake_site(
                        suspicious_domain=susp,
                        legitimate_content=legitimate_content,
                        suspicious_content=suspicious_content,
                        legitimate_screenshot=legitimate_screenshot,
                        suspicious_screenshot=suspicious_screenshot,
                    )
                except Exception as exc:
                    logger.error(
                        "verify_fake_site failed for %s: %s", susp.domain, exc
                    )
                    continue

                if verified.is_confirmed_fake:
                    result['confirmed_fakes'].append(verified.domain)

                    # Create Alert record in DB
                    try:
                        from src.database import SessionLocal
                        from src.models import Alert

                        session = SessionLocal()
                        try:
                            alert = Alert(
                                alert_type='fake_site',
                                severity='critical',
                                message=f"偽サイト検知: {verified.domain} が正規ドメイン {legitimate_domain} の偽サイトとして確認されました",
                                fake_domain=verified.domain,
                                legitimate_domain=legitimate_domain,
                                domain_similarity_score=verified.similarity_score,
                                content_similarity_score=verified.content_similarity,
                                is_resolved=False,
                            )
                            session.add(alert)
                            session.commit()
                        except Exception as db_exc:
                            session.rollback()
                            logger.error(
                                "Failed to create alert for fake site %s: %s",
                                verified.domain, db_exc,
                            )
                        finally:
                            session.close()
                    except Exception as import_exc:
                        logger.error(
                            "Failed to import DB dependencies for alert creation: %s",
                            import_exc,
                        )

        # Send alerts for confirmed fakes
        confirmed = [s for s in result['confirmed_fakes']]
        if confirmed:
            alert_system = AlertSystem()
            config = NotificationConfig(**notification_config)
            result['alerts_sent'] = True

    except Exception as e:
        result['error'] = str(e)

    return result


@celery_app.task(name='src.tasks.cleanup_old_data')
def cleanup_old_data(retention_days: int = 365) -> dict[str, Any]:
    """
    Clean up old monitoring data.
    
    Args:
        retention_days: Number of days to retain data
    
    Returns:
        Task result with cleanup statistics
    """
    result = {
        'retention_days': retention_days,
        'deleted_records': {
            'crawl_results': 0,
            'violations': 0,
            'alerts': 0
        },
        'status': 'success',
        'error': None
    }
    
    try:
        from sqlalchemy import delete
        from src.database import SessionLocal
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        result['cutoff_date'] = cutoff_date.isoformat()
        
        session = SessionLocal()
        
        try:
            from src.models import CrawlResult, Violation, Alert
            
            # Delete old crawl results
            crawl_delete = delete(CrawlResult).where(
                CrawlResult.crawled_at < cutoff_date
            )
            crawl_result = session.execute(crawl_delete)
            result['deleted_records']['crawl_results'] = crawl_result.rowcount
            
            # Delete old violations
            violation_delete = delete(Violation).where(
                Violation.detected_at < cutoff_date
            )
            violation_result = session.execute(violation_delete)
            result['deleted_records']['violations'] = violation_result.rowcount
            
            # Delete old alerts
            alert_delete = delete(Alert).where(
                Alert.created_at < cutoff_date
            )
            alert_result = session.execute(alert_delete)
            result['deleted_records']['alerts'] = alert_result.rowcount
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
    
    return result


@celery_app.task(name='src.tasks.crawl_all_sites')
def crawl_all_sites() -> dict[str, Any]:
    """
    Crawl all active monitoring sites.
    
    Returns:
        Task result with crawl statistics
    """
    result = {
        'total_sites': 0,
        'successful': 0,
        'failed': 0,
        'enqueued_tasks': [],
        'status': 'success',
        'error': None
    }
    
    try:
        from src.database import SessionLocal
        import os
        
        session = SessionLocal()
        
        try:
            from src.models import MonitoringSite, ContractCondition
            
            # Query all active monitoring sites
            sites = session.query(MonitoringSite).filter(
                MonitoringSite.is_active == True
            ).all()
            
            result['total_sites'] = len(sites)
            
            # Enqueue crawl task for each site
            for site in sites:
                # Get current contract conditions
                contract = session.query(ContractCondition).filter(
                    ContractCondition.site_id == site.id,
                    ContractCondition.is_current == True
                ).first()
                
                if contract:
                    # Prepare contract conditions
                    contract_conditions = {
                        'prices': contract.prices,
                        'payment_methods': contract.payment_methods,
                        'fees': contract.fees,
                        'subscription_terms': contract.subscription_terms
                    }
                    
                    # Prepare notification config (from environment or defaults)
                    notification_config = {
                        'email_recipients': os.getenv('ALERT_EMAIL_RECIPIENTS', '').split(','),
                        'slack_webhook_url': os.getenv('SLACK_WEBHOOK_URL'),
                        'slack_channel': os.getenv('SLACK_CHANNEL', '#alerts')
                    }
                    
                    # Enqueue task
                    task = crawl_and_validate_site.delay(
                        site_id=site.id,
                        url=site.target_url,
                        contract_conditions=contract_conditions,
                        notification_config=notification_config
                    )
                    
                    result['enqueued_tasks'].append({
                        'site_id': site.id,
                        'task_id': task.id,
                        'url': site.target_url
                    })
                    result['successful'] += 1
                else:
                    result['failed'] += 1
            
        finally:
            session.close()
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
    
    return result


@celery_app.task(name='src.tasks.scan_all_fake_sites')
def scan_all_fake_sites() -> dict[str, Any]:
    """
    Scan for fake sites for all monitoring targets.
    
    Returns:
        Task result with scan statistics
    """
    result = {
        'total_domains': 0,
        'suspicious_found': 0,
        'confirmed_fakes': 0,
        'enqueued_tasks': [],
        'status': 'success',
        'error': None
    }
    
    try:
        from src.database import SessionLocal
        import os
        
        session = SessionLocal()
        
        try:
            from src.models import MonitoringSite
            
            # Query all active monitoring sites
            sites = session.query(MonitoringSite).filter(
                MonitoringSite.is_active == True
            ).all()
            
            result['total_domains'] = len(sites)
            
            # Prepare notification config
            notification_config = {
                'email_recipients': os.getenv('ALERT_EMAIL_RECIPIENTS', '').split(','),
                'slack_webhook_url': os.getenv('SLACK_WEBHOOK_URL'),
                'slack_channel': os.getenv('SLACK_CHANNEL', '#alerts')
            }
            
            # Enqueue scan task for each domain
            for site in sites:
                # Generate candidate domains (common typosquatting patterns)
                candidate_domains = _generate_candidate_domains(site.domain)
                
                # Enqueue task
                task = scan_fake_sites.delay(
                    legitimate_domain=site.domain,
                    candidate_domains=candidate_domains,
                    notification_config=notification_config
                )
                
                result['enqueued_tasks'].append({
                    'site_id': site.id,
                    'task_id': task.id,
                    'domain': site.domain,
                    'candidates_count': len(candidate_domains)
                })
            
        finally:
            session.close()
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
    
    return result


def _generate_candidate_domains(legitimate_domain: str) -> list[str]:
    """
    Generate candidate domains for typosquatting detection.
    
    Args:
        legitimate_domain: Legitimate domain to protect
    
    Returns:
        List of candidate domains to check
    """
    candidates = []
    
    # Remove TLD for manipulation — check compound TLDs first
    domain_name = None
    tld = None
    for compound_tld in COMPOUND_TLDS:
        suffix = '.' + compound_tld
        if legitimate_domain.endswith(suffix):
            domain_name = legitimate_domain[:-len(suffix)]
            tld = compound_tld
            break

    if domain_name is None:
        parts = legitimate_domain.rsplit('.', 1)
        if len(parts) != 2:
            return candidates
        domain_name, tld = parts
    
    # Common typosquatting patterns
    # 1. Character substitution (l -> 1, o -> 0)
    substitutions = {
        'l': '1', 'i': '1', 'o': '0',
        'a': '@', 'e': '3', 's': '5'
    }
    
    for char, replacement in substitutions.items():
        if char in domain_name:
            typo = domain_name.replace(char, replacement, 1)
            candidates.append(f"{typo}.{tld}")
    
    # 2. Character omission
    for i in range(len(domain_name)):
        typo = domain_name[:i] + domain_name[i+1:]
        if typo:
            candidates.append(f"{typo}.{tld}")
    
    # 3. Character duplication
    for i in range(len(domain_name)):
        typo = domain_name[:i] + domain_name[i] + domain_name[i:]
        candidates.append(f"{typo}.{tld}")
    
    # 4. Common TLD variations
    common_tlds = ['com', 'net', 'org', 'co', 'io']
    for alt_tld in common_tlds:
        if alt_tld != tld:
            candidates.append(f"{domain_name}.{alt_tld}")
    
    # 5. Hyphen patterns
    if '-' in domain_name:
        # Remove all hyphens
        no_hyphens = domain_name.replace('-', '')
        if no_hyphens:
            candidates.append(f"{no_hyphens}.{tld}")
    else:
        # Insert hyphens at various positions (only for domains with length >= 4)
        if len(domain_name) >= 4:
            for i in range(1, len(domain_name)):
                hyphenated = domain_name[:i] + '-' + domain_name[i:]
                candidates.append(f"{hyphenated}.{tld}")
    
    # Limit to reasonable number
    return candidates[:50]

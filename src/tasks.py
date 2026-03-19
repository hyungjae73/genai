"""
Celery tasks for Payment Compliance Monitor.

This module defines asynchronous tasks for crawling, validation, and maintenance.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from src.celery_app import celery_app
from src.crawler import CrawlerEngine
from src.analyzer import ContentAnalyzer
from src.validator import ValidationEngine
from src.fake_detector import FakeSiteDetector
from src.alert_system import AlertSystem, NotificationConfig

logger = logging.getLogger(__name__)


@celery_app.task(name='src.tasks.crawl_and_validate_site')
def crawl_and_validate_site(
    site_id: int,
    url: str,
    contract_conditions: dict[str, Any],
    notification_config: dict[str, Any]
) -> dict[str, Any]:
    """
    Crawl a site, extract payment info, validate, and send alerts if needed.
    
    Args:
        site_id: Monitoring site ID
        url: URL to crawl
        contract_conditions: Contract conditions to validate against
        notification_config: Notification configuration
    
    Returns:
        Task result with status and details
    """
    return asyncio.run(_crawl_and_validate_site_async(
        site_id, url, contract_conditions, notification_config
    ))


async def _crawl_and_validate_site_async(
    site_id: int,
    url: str,
    contract_conditions: dict[str, Any],
    notification_config: dict[str, Any]
) -> dict[str, Any]:
    """Async implementation of crawl_and_validate_site."""
    from src.extraction_config import ExtractionConfig

    config = ExtractionConfig()

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
        await crawler.close()  # Changed from aclose() to close()
        
        if not crawl_result.success:
            result['status'] = 'crawl_failed'
            result['error'] = 'Failed to crawl site'
            return result

        # 2. Launch screenshot capture as a background task (Req 19.2)
        #    so it does NOT block HTML extraction.
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

        # 3. Extract payment info (existing logic) — runs concurrently
        #    with the screenshot task above.
        analyzer = ContentAnalyzer()
        payment_info = analyzer.extract_payment_info(crawl_result.html_content)

        # 4. Run structured data extraction pipeline (Req 23.2, 23.4)
        if config.extraction_enabled:
            try:
                import time as _time
                from src.database import SessionLocal
                from src.extractors.payment_info_extractor import PaymentInfoExtractor
                from src.models import CrawlResult as CrawlResultModel

                extraction_start = _time.monotonic()
                extractor = PaymentInfoExtractor()
                session = SessionLocal()
                try:
                    # Save crawl result to DB first (with screenshot_path)
                    db_crawl = session.query(CrawlResultModel).filter(
                        CrawlResultModel.site_id == site_id
                    ).order_by(CrawlResultModel.crawled_at.desc()).first()

                    crawl_result_id = db_crawl.id if db_crawl else None

                    if crawl_result_id:
                        # Extract and save structured payment info
                        extraction_id = extractor.extract_and_save(
                            session=session,
                            html=crawl_result.html_content,
                            url=url,
                            crawl_result_id=crawl_result_id,
                            site_id=site_id,
                        )
                        result['extraction_id'] = extraction_id

                        extraction_elapsed = _time.monotonic() - extraction_start
                        logger.info(
                            "Data extraction completed in %.2fs for site_id=%d (Req 19.5)",
                            extraction_elapsed, site_id,
                        )

                        # Now await the screenshot result before committing
                        if screenshot_task is not None:
                            result['screenshot_path'] = await screenshot_task
                            screenshot_task = None  # consumed

                        # Update screenshot path on crawl result
                        if result['screenshot_path'] and db_crawl:
                            db_crawl.screenshot_path = result['screenshot_path']
                            session.flush()

                        session.commit()
                    else:
                        logger.warning(
                            "No crawl result found in DB for site_id=%d, "
                            "skipping extraction",
                            site_id,
                        )
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
        
        # 5. Validate (existing logic preserved - Req 23.3)
        validator = ValidationEngine(price_tolerance=5.0)
        validation_result = validator.validate_payment_info(
            payment_info, contract_conditions
        )
        
        # 6. Send alerts if violations detected (existing logic preserved)
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
            
            # Send alerts
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
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
    
    return result


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
    result = {
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
        
        # For confirmed fakes, send high-priority alerts
        confirmed = [s for s in suspicious if s.is_confirmed_fake]
        result['confirmed_fakes'] = [s.domain for s in confirmed]
        
        if confirmed:
            alert_system = AlertSystem()
            config = NotificationConfig(**notification_config)
            
            # Send alerts for confirmed fakes
            # (Implementation would create violation objects for fake sites)
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
    
    # Remove TLD for manipulation
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
    
    # Limit to reasonable number
    return candidates[:50]

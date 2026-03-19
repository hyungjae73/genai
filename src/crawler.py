"""
Crawler Engine for Payment Compliance Monitor.

This module provides web crawling functionality using Playwright with support for:
- Asynchronous crawling
- robots.txt compliance
- Rate limiting (Redis-based)
- Retry logic with exponential backoff
- Result persistence

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import redis.asyncio as redis
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CrawlResult as CrawlResultModel

logger = logging.getLogger(__name__)


@dataclass
class CrawlResponse:
    """Response from a crawl operation."""
    url: str
    html_content: str
    status_code: int
    crawled_at: datetime
    success: bool
    error_message: Optional[str] = None


class CrawlerEngine:
    """
    Web crawler engine using Playwright.
    
    Provides asynchronous crawling with robots.txt compliance, rate limiting,
    and retry logic with exponential backoff.
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        rate_limit_seconds: int = 10,
        timeout_seconds: int = 300,
        max_retries: int = 3,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize the crawler engine.
        
        Args:
            redis_url: Redis connection URL for rate limiting
            rate_limit_seconds: Minimum seconds between requests to same domain
            timeout_seconds: Maximum time for a single crawl operation
            max_retries: Maximum number of retry attempts
            user_agent: Custom user agent string
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.user_agent = user_agent or os.getenv(
            "CRAWLER_USER_AGENT",
            "PaymentComplianceMonitor/1.0"
        )
        
        self._redis_client: Optional[redis.Redis] = None
        self._browser: Optional[Browser] = None
        self._robots_cache: dict[str, RobotFileParser] = {}
    
    async def _get_redis_client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._redis_client is None:
            self._redis_client = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis_client
    
    async def _get_browser(self) -> Browser:
        """Get or create Playwright browser instance."""
        if self._browser is None:
            playwright = await async_playwright().start()
            self._browser = await playwright.chromium.launch(headless=True)
        return self._browser
    
    async def close(self):
        """Close browser and Redis connections."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        if self._redis_client:
            await self._redis_client.aclose()
            self._redis_client = None
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    async def _check_robots_txt(self, url: str) -> bool:
        """
        Check if URL is allowed by robots.txt.
        
        Args:
            url: URL to check
            
        Returns:
            True if allowed, False otherwise
        """
        domain = self._get_domain(url)
        
        # Check cache first
        if domain in self._robots_cache:
            parser = self._robots_cache[domain]
            return parser.can_fetch(self.user_agent, url)
        
        # Fetch and parse robots.txt
        robots_url = urljoin(domain, "/robots.txt")
        parser = RobotFileParser()
        parser.set_url(robots_url)
        
        try:
            # Use a simple HTTP request for robots.txt
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                else:
                    # If robots.txt doesn't exist, allow all
                    parser.parse([])
        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt for {domain}: {e}")
            # On error, allow crawling
            parser.parse([])
        
        self._robots_cache[domain] = parser
        return parser.can_fetch(self.user_agent, url)
    
    async def _check_rate_limit(self, domain: str) -> bool:
        """
        Check if we can crawl the domain based on rate limit.
        
        Args:
            domain: Domain to check
            
        Returns:
            True if allowed, False if rate limited
        """
        redis_client = await self._get_redis_client()
        key = f"crawler:ratelimit:{domain}"
        
        # Check last access time
        last_access = await redis_client.get(key)
        if last_access:
            elapsed = time.time() - float(last_access)
            if elapsed < self.rate_limit_seconds:
                return False
        
        return True
    
    async def _update_rate_limit(self, domain: str):
        """
        Update the rate limit timestamp for a domain.
        
        Args:
            domain: Domain to update
        """
        redis_client = await self._get_redis_client()
        key = f"crawler:ratelimit:{domain}"
        
        # Set current timestamp with expiration
        await redis_client.set(
            key,
            str(time.time()),
            ex=self.rate_limit_seconds * 2  # Expire after 2x rate limit
        )
    
    async def _wait_for_rate_limit(self, domain: str):
        """
        Wait until rate limit allows crawling the domain.
        
        Args:
            domain: Domain to wait for
        """
        redis_client = await self._get_redis_client()
        key = f"crawler:ratelimit:{domain}"
        
        while True:
            last_access = await redis_client.get(key)
            if not last_access:
                break
            
            elapsed = time.time() - float(last_access)
            if elapsed >= self.rate_limit_seconds:
                break
            
            wait_time = self.rate_limit_seconds - elapsed
            logger.info(f"Rate limit: waiting {wait_time:.1f}s for {domain}")
            await asyncio.sleep(wait_time)
    
    async def _crawl_page(self, url: str) -> tuple[str, int]:
        """
        Crawl a single page and return HTML content and status code.
        
        Args:
            url: URL to crawl
            
        Returns:
            Tuple of (html_content, status_code)
            
        Raises:
            Exception: If crawling fails
        """
        browser = await self._get_browser()
        page: Page = await browser.new_page(user_agent=self.user_agent)
        
        try:
            # Navigate to page with timeout
            response = await page.goto(url, timeout=self.timeout_seconds * 1000)
            
            if response is None:
                raise Exception(f"Failed to load page: {url}")
            
            status_code = response.status
            
            # Wait for page to be fully loaded
            await page.wait_for_load_state("networkidle", timeout=30000)
            
            # Get HTML content
            html_content = await page.content()
            
            return html_content, status_code
            
        finally:
            await page.close()
    
    async def crawl_site(
        self,
        site_id: int,
        url: str,
        db_session: Optional[AsyncSession] = None,
    ) -> CrawlResponse:
        """
        Crawl a site with robots.txt compliance, rate limiting, and retry logic.
        
        This method implements:
        - robots.txt checking (Requirement 1.4)
        - Rate limiting with minimum 10 seconds between requests (Requirement 1.3)
        - Retry with exponential backoff up to 3 times (Requirement 1.5)
        - Result persistence to database (Requirement 1.6)
        
        Args:
            site_id: ID of the monitoring site
            url: URL to crawl
            db_session: Optional database session for storing results
            
        Returns:
            CrawlResponse object with crawl results
        """
        domain = self._get_domain(url)
        
        # Check robots.txt compliance
        if not await self._check_robots_txt(url):
            logger.warning(f"URL blocked by robots.txt: {url}")
            return CrawlResponse(
                url=url,
                html_content="",
                status_code=403,
                crawled_at=datetime.utcnow(),
                success=False,
                error_message="Blocked by robots.txt"
            )
        
        # Wait for rate limit
        await self._wait_for_rate_limit(domain)
        
        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Update rate limit before crawling
                await self._update_rate_limit(domain)
                
                # Perform crawl
                html_content, status_code = await self._crawl_page(url)
                
                # Create result
                result = CrawlResponse(
                    url=url,
                    html_content=html_content,
                    status_code=status_code,
                    crawled_at=datetime.utcnow(),
                    success=True,
                    error_message=None
                )
                
                # Store in database if session provided
                if db_session:
                    db_result = CrawlResultModel(
                        site_id=site_id,
                        url=url,
                        html_content=html_content,
                        status_code=status_code,
                        crawled_at=result.crawled_at
                    )
                    db_session.add(db_result)
                    await db_session.commit()
                
                logger.info(f"Successfully crawled {url} (attempt {attempt + 1})")
                return result
                
            except PlaywrightTimeoutError as e:
                last_error = f"Timeout: {str(e)}"
                logger.warning(f"Crawl timeout for {url} (attempt {attempt + 1}/{self.max_retries}): {e}")
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Crawl failed for {url} (attempt {attempt + 1}/{self.max_retries}): {e}")
            
            # Exponential backoff before retry
            if attempt < self.max_retries - 1:
                backoff_time = 2 ** attempt  # 1s, 2s, 4s
                logger.info(f"Retrying in {backoff_time}s...")
                await asyncio.sleep(backoff_time)
        
        # All retries failed
        logger.error(f"Failed to crawl {url} after {self.max_retries} attempts")
        return CrawlResponse(
            url=url,
            html_content="",
            status_code=0,
            crawled_at=datetime.utcnow(),
            success=False,
            error_message=last_error
        )

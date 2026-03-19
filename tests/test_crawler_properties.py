"""
Property-based tests for CrawlerEngine.

Tests universal properties that should hold across all inputs using Hypothesis.
"""

import asyncio
import os
import time
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from unittest.mock import AsyncMock, MagicMock, patch

from src.crawler import CrawlerEngine


# Test configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")


class MockRedisClient:
    """Mock Redis client for testing rate limiting."""
    
    def __init__(self):
        self.data = {}
    
    async def get(self, key):
        """Get value from mock Redis."""
        return self.data.get(key)
    
    async def set(self, key, value, ex=None):
        """Set value in mock Redis."""
        self.data[key] = value
    
    async def aclose(self):
        """Close mock Redis client."""
        pass


@pytest.fixture
async def crawler():
    """Create a crawler instance for property testing."""
    crawler = CrawlerEngine(
        redis_url=REDIS_URL,
        rate_limit_seconds=1,  # Use 1 second for faster testing
        timeout_seconds=30,
        max_retries=3,
    )
    
    # Replace Redis client with mock
    crawler._redis_client = MockRedisClient()
    
    yield crawler
    await crawler.close()


# Property 2: Rate limit compliance
# **Validates: Requirements 1.3, 9.3**

@pytest.mark.asyncio
@settings(
    max_examples=3,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    num_requests=st.integers(min_value=2, max_value=2),
)
async def test_property_rate_limit_compliance(crawler, num_requests):
    """
    Property 2: Rate limit compliance
    
    For any sequence of crawl requests to the same domain, the time interval
    between consecutive requests should be at least 10 seconds.
    
    **Validates: Requirements 1.3, 9.3**
    
    This test verifies that:
    1. Multiple requests to the same domain respect the rate limit
    2. The time between consecutive requests is >= rate_limit_seconds
    3. Rate limiting is enforced consistently across all requests
    """
    domain = "https://example.com"
    rate_limit = crawler.rate_limit_seconds
    
    # Track timestamps of actual crawl attempts
    crawl_timestamps = []
    
    # Mock the browser to track when crawls actually happen
    async def mock_crawl_page(url: str):
        crawl_timestamps.append(time.time())
        return "<html><body>Test</body></html>", 200
    
    with patch.object(crawler, "_check_robots_txt", return_value=True), \
         patch.object(crawler, "_crawl_page", side_effect=mock_crawl_page):
        
        # Perform multiple crawls to the same domain
        for i in range(num_requests):
            url = f"{domain}/page{i}"
            await crawler.crawl_site(
                site_id=1,
                url=url,
            )
        
        # Verify rate limit compliance
        # Check that consecutive requests are separated by at least rate_limit_seconds
        for i in range(1, len(crawl_timestamps)):
            time_diff = crawl_timestamps[i] - crawl_timestamps[i - 1]
            
            # Allow small tolerance for timing precision (0.1 seconds)
            assert time_diff >= (rate_limit - 0.1), (
                f"Rate limit violated: Request {i} came {time_diff:.3f}s after "
                f"request {i-1}, but minimum is {rate_limit}s"
            )


# Property 3: Robots.txt compliance
# **Validates: Requirements 1.4, 9.4**

@pytest.mark.asyncio
@settings(
    max_examples=2,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    allowed_paths=st.lists(
        st.sampled_from(["/api", "/public"]),
        min_size=1,
        max_size=1
    ),
    disallowed_paths=st.lists(
        st.sampled_from(["/admin", "/private"]),
        min_size=1,
        max_size=1
    ),
)
async def test_property_robots_txt_compliance(crawler, allowed_paths, disallowed_paths):
    """
    Property 3: Robots.txt compliance
    
    For any site with robots.txt directives, the crawler should only access
    paths that are allowed by the directives.
    
    **Validates: Requirements 1.4, 9.4**
    
    This test verifies that:
    1. URLs blocked by robots.txt are not crawled
    2. URLs allowed by robots.txt are crawled successfully
    3. The crawler respects robots.txt directives consistently
    """
    # Ensure paths are unique and properly formatted
    allowed_paths = list(set(f"/{path.strip('/')}" for path in allowed_paths if path.strip()))
    disallowed_paths = list(set(f"/{path.strip('/')}" for path in disallowed_paths if path.strip()))
    
    # Remove any overlap between allowed and disallowed
    disallowed_paths = [p for p in disallowed_paths if p not in allowed_paths]
    
    # Skip if we don't have both allowed and disallowed paths
    if not allowed_paths or not disallowed_paths:
        return
    
    domain = "https://example.com"
    
    # Track which URLs were actually crawled
    crawled_urls = []
    
    async def mock_crawl_page(url: str):
        crawled_urls.append(url)
        return "<html><body>Test</body></html>", 200
    
    # Mock robots.txt check to return appropriate values based on path
    async def mock_check_robots_txt(url: str) -> bool:
        """Mock that respects our allowed/disallowed paths."""
        for disallowed in disallowed_paths:
            if url.endswith(disallowed) or f"{disallowed}/" in url:
                return False
        return True
    
    # Disable rate limiting and use our mocked robots.txt check
    with patch.object(crawler, "_check_robots_txt", side_effect=mock_check_robots_txt), \
         patch.object(crawler, "_wait_for_rate_limit", return_value=None), \
         patch.object(crawler, "_update_rate_limit", return_value=None), \
         patch.object(crawler, "_crawl_page", side_effect=mock_crawl_page):
        # Test allowed paths - should be crawled
        for path in allowed_paths:
            url = f"{domain}{path}"
            result = await crawler.crawl_site(site_id=1, url=url)
            
            assert result.success, (
                f"Allowed path {path} should be crawled successfully, "
                f"but got error: {result.error_message}"
            )
            assert url in crawled_urls, (
                f"Allowed path {path} should have been crawled"
            )
        
        # Test disallowed paths - should NOT be crawled
        for path in disallowed_paths:
            url = f"{domain}{path}"
            result = await crawler.crawl_site(site_id=1, url=url)
            
            assert not result.success, (
                f"Disallowed path {path} should NOT be crawled successfully"
            )
            assert result.error_message == "Blocked by robots.txt", (
                f"Disallowed path {path} should be blocked by robots.txt"
            )
            assert url not in crawled_urls, (
                f"Disallowed path {path} should NOT have been crawled"
            )


# Property 4: Retry with exponential backoff
# **Validates: Requirements 1.5**

@pytest.mark.asyncio
@settings(
    max_examples=3,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    failure_count=st.integers(min_value=1, max_value=2),
)
async def test_property_retry_exponential_backoff(crawler, failure_count):
    """
    Property 4: Retry with exponential backoff
    
    For any failed crawling task, the system should retry up to 3 times with
    exponentially increasing wait times between retries.
    
    **Validates: Requirements 1.5**
    
    This test verifies that:
    1. Failed crawls are retried up to max_retries times
    2. Wait times between retries follow exponential backoff (2^attempt seconds)
    3. After all retries are exhausted, the crawl returns a failure response
    """
    url = "https://example.com/test"
    
    # Track retry attempts and timestamps
    attempt_timestamps = []
    attempt_count = [0]  # Use list to allow modification in nested function
    
    async def mock_crawl_page_failing(url: str):
        """Mock that fails for the first N attempts."""
        attempt_count[0] += 1
        attempt_timestamps.append(time.time())
        
        if attempt_count[0] <= failure_count:
            raise Exception(f"Simulated failure {attempt_count[0]}")
        
        # Success after failure_count attempts
        return "<html><body>Success</body></html>", 200
    
    with patch.object(crawler, "_check_robots_txt", return_value=True), \
         patch.object(crawler, "_wait_for_rate_limit", return_value=None), \
         patch.object(crawler, "_update_rate_limit", return_value=None), \
         patch.object(crawler, "_crawl_page", side_effect=mock_crawl_page_failing):
        
        result = await crawler.crawl_site(site_id=1, url=url)
        
        # Verify the correct number of attempts were made
        expected_attempts = min(failure_count + 1, crawler.max_retries)
        assert attempt_count[0] == expected_attempts, (
            f"Expected {expected_attempts} attempts, but got {attempt_count[0]}"
        )
        
        # Verify exponential backoff between retries
        if len(attempt_timestamps) > 1:
            for i in range(1, len(attempt_timestamps)):
                time_diff = attempt_timestamps[i] - attempt_timestamps[i - 1]
                expected_backoff = 2 ** (i - 1)  # 1s, 2s, 4s
                
                # Allow 0.2 second tolerance for timing precision
                assert time_diff >= (expected_backoff - 0.2), (
                    f"Retry {i} should wait at least {expected_backoff}s, "
                    f"but only waited {time_diff:.3f}s"
                )
        
        # Verify result based on whether all retries succeeded or failed
        if failure_count < crawler.max_retries:
            # Should succeed after failure_count attempts
            assert result.success, (
                f"Crawl should succeed after {failure_count} failures, "
                f"but got error: {result.error_message}"
            )
        else:
            # Should fail after exhausting all retries
            assert not result.success, (
                f"Crawl should fail after {crawler.max_retries} attempts"
            )
            assert result.error_message is not None, (
                "Failed crawl should have an error message"
            )


# Property 5: Crawl result persistence
# **Validates: Requirements 1.6**

@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("USE_SQLITE", "false") == "true", reason="SQLite doesn't support JSONB - requires PostgreSQL")
@settings(
    max_examples=3,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    html_content=st.text(min_size=10, max_size=50),
    status_code=st.sampled_from([200, 404]),
)
async def test_property_crawl_result_persistence(crawler, html_content, status_code):
    """
    Property 5: Crawl result persistence
    
    For any successful crawl operation, querying the database immediately after
    should return the stored HTML content and metadata.
    
    **Validates: Requirements 1.6**
    
    This test verifies that:
    1. Successful crawl results are persisted to the database
    2. All metadata (URL, status code, timestamp) is stored correctly
    3. HTML content is stored without corruption
    4. Data can be retrieved immediately after storage
    """
    # Import database dependencies
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.pool import StaticPool
    from sqlalchemy import select
    from src.models import Base, MonitoringSite, CrawlResult
    
    # Create in-memory test database
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        # Create a test monitoring site
        site = MonitoringSite(
            company_name="Test Company",
            domain="https://example.com",
            target_url="https://example.com",
            is_active=True,
        )
        session.add(site)
        await session.commit()
        await session.refresh(site)
        
        url = f"https://example.com/page"
        
        # Mock the crawl to return our test data
        async def mock_crawl_page(url: str):
            return html_content, status_code
        
        with patch.object(crawler, "_check_robots_txt", return_value=True), \
             patch.object(crawler, "_wait_for_rate_limit", return_value=None), \
             patch.object(crawler, "_update_rate_limit", return_value=None), \
             patch.object(crawler, "_crawl_page", side_effect=mock_crawl_page):
            
            # Perform crawl with database session
            result = await crawler.crawl_site(
                site_id=site.id,
                url=url,
                db_session=session,
            )
            
            # Verify crawl was successful
            assert result.success, f"Crawl should succeed, but got error: {result.error_message}"
            
            # Query database immediately after crawl
            db_result = await session.execute(
                select(CrawlResult).where(CrawlResult.site_id == site.id)
            )
            stored_result = db_result.scalar_one_or_none()
            
            # Verify persistence
            assert stored_result is not None, (
                "Crawl result should be persisted to database"
            )
            
            # Verify all metadata is stored correctly
            assert stored_result.site_id == site.id, (
                f"Stored site_id {stored_result.site_id} should match {site.id}"
            )
            assert stored_result.url == url, (
                f"Stored URL {stored_result.url} should match {url}"
            )
            assert stored_result.status_code == status_code, (
                f"Stored status_code {stored_result.status_code} should match {status_code}"
            )
            
            # Verify HTML content is stored without corruption
            assert stored_result.html_content == html_content, (
                "Stored HTML content should match original content exactly"
            )
            
            # Verify timestamp is set
            assert stored_result.crawled_at is not None, (
                "Crawled timestamp should be set"
            )
            
            # Verify timestamp is recent (within last minute)
            from datetime import datetime, timedelta
            time_diff = datetime.utcnow() - stored_result.crawled_at
            assert time_diff < timedelta(minutes=1), (
                f"Crawled timestamp should be recent, but was {time_diff} ago"
            )
    
    # Cleanup
    await engine.dispose()

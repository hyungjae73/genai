"""
Unit tests for CrawlerEngine.

Tests basic crawling functionality, robots.txt compliance, rate limiting,
and retry logic.
"""

import asyncio
import os
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from src.crawler import CrawlerEngine, CrawlResponse
from src.models import Base, MonitoringSite, CrawlResult


# Test database setup - Use PostgreSQL if available, fallback to SQLite
USE_SQLITE = os.getenv("USE_SQLITE", "false") == "true"
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:" if USE_SQLITE else "postgresql+asyncpg://payment_monitor:payment_monitor_pass@localhost:5432/payment_monitor_test"
)


@pytest.fixture
async def test_engine():
    """Create a test database engine."""
    if USE_SQLITE:
        engine = create_async_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_async_engine(
            TEST_DATABASE_URL,
            poolclass=NullPool,
        )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
async def crawler():
    """Create a crawler instance for testing."""
    crawler = CrawlerEngine(
        redis_url="redis://localhost:6379/1",  # Use test database
        rate_limit_seconds=1,  # Short rate limit for testing
        timeout_seconds=30,
        max_retries=3,
    )
    yield crawler
    await crawler.close()


@pytest.mark.asyncio
async def test_get_domain():
    """Test domain extraction from URL."""
    crawler = CrawlerEngine()
    
    assert crawler._get_domain("https://example.com/path") == "https://example.com"
    assert crawler._get_domain("http://test.com:8080/page") == "http://test.com:8080"
    assert crawler._get_domain("https://sub.domain.com/") == "https://sub.domain.com"


@pytest.mark.asyncio
async def test_robots_txt_allowed(crawler):
    """Test that allowed URLs pass robots.txt check."""
    # Mock httpx to return a permissive robots.txt
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nAllow: /"
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        allowed = await crawler._check_robots_txt("https://example.com/page")
        assert allowed is True


@pytest.mark.asyncio
async def test_robots_txt_disallowed(crawler):
    """Test that disallowed URLs fail robots.txt check."""
    # Mock httpx to return a restrictive robots.txt
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "User-agent: *\nDisallow: /admin"
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        allowed = await crawler._check_robots_txt("https://example.com/admin/page")
        assert allowed is False


@pytest.mark.asyncio
async def test_robots_txt_not_found(crawler):
    """Test that missing robots.txt allows all URLs."""
    # Mock httpx to return 404
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        
        allowed = await crawler._check_robots_txt("https://example.com/page")
        assert allowed is True


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("REDIS_AVAILABLE", "false") != "true", reason="Redis not available")
async def test_rate_limit_check(crawler):
    """Test rate limit checking."""
    domain = "https://example.com"
    
    # First check should pass
    allowed = await crawler._check_rate_limit(domain)
    assert allowed is True
    
    # Update rate limit
    await crawler._update_rate_limit(domain)
    
    # Immediate second check should fail
    allowed = await crawler._check_rate_limit(domain)
    assert allowed is False
    
    # After waiting, should pass again
    await asyncio.sleep(1.1)  # Wait slightly longer than rate limit
    allowed = await crawler._check_rate_limit(domain)
    assert allowed is True


@pytest.mark.asyncio
@pytest.mark.skipif(USE_SQLITE, reason="SQLite doesn't support JSONB - requires PostgreSQL")
async def test_crawl_site_success(crawler, test_session):
    """Test successful crawling and database persistence."""
    # Create a test site
    site = MonitoringSite(
        company_name="Test Company",
        domain="example.com",
        target_url="https://example.com",
        is_active=True,
    )
    test_session.add(site)
    await test_session.commit()
    await test_session.refresh(site)
    
    # Mock Playwright browser and page
    with patch.object(crawler, "_get_browser") as mock_get_browser, \
         patch.object(crawler, "_check_robots_txt", return_value=True), \
         patch.object(crawler, "_wait_for_rate_limit", return_value=None):
        
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=MagicMock(status=200))
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body>Test</body></html>")
        mock_page.close = AsyncMock()
        
        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_get_browser.return_value = mock_browser
        
        # Perform crawl
        result = await crawler.crawl_site(
            site_id=site.id,
            url="https://example.com",
            db_session=test_session,
        )
        
        # Verify result
        assert result.success is True
        assert result.status_code == 200
        assert result.html_content == "<html><body>Test</body></html>"
        assert result.error_message is None
        
        # Verify database persistence
        from sqlalchemy import select
        db_result = await test_session.execute(
            select(CrawlResult).where(CrawlResult.site_id == site.id)
        )
        crawl_result = db_result.scalar_one()
        
        assert crawl_result.url == "https://example.com"
        assert crawl_result.status_code == 200
        assert crawl_result.html_content == "<html><body>Test</body></html>"


@pytest.mark.asyncio
async def test_crawl_site_robots_blocked(crawler):
    """Test that robots.txt blocking prevents crawling."""
    with patch.object(crawler, "_check_robots_txt", return_value=False):
        result = await crawler.crawl_site(
            site_id=1,
            url="https://example.com/admin",
        )
        
        assert result.success is False
        assert result.status_code == 403
        assert result.error_message == "Blocked by robots.txt"


@pytest.mark.asyncio
async def test_crawl_site_retry_on_failure(crawler):
    """Test retry logic with exponential backoff."""
    with patch.object(crawler, "_check_robots_txt", return_value=True), \
         patch.object(crawler, "_wait_for_rate_limit", return_value=None), \
         patch.object(crawler, "_update_rate_limit", return_value=None), \
         patch.object(crawler, "_get_browser") as mock_get_browser:
        
        # Mock page that fails twice then succeeds
        call_count = 0
        
        async def mock_goto(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Network error")
            return MagicMock(status=200)
        
        mock_page = AsyncMock()
        mock_page.goto = mock_goto
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html>Success</html>")
        mock_page.close = AsyncMock()
        
        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_get_browser.return_value = mock_browser
        
        # Perform crawl
        result = await crawler.crawl_site(
            site_id=1,
            url="https://example.com",
        )
        
        # Should succeed after retries
        assert result.success is True
        assert result.status_code == 200
        assert call_count == 3  # Failed twice, succeeded on third attempt


@pytest.mark.asyncio
async def test_crawl_site_max_retries_exceeded(crawler):
    """Test that crawling fails after max retries."""
    with patch.object(crawler, "_check_robots_txt", return_value=True), \
         patch.object(crawler, "_wait_for_rate_limit", return_value=None), \
         patch.object(crawler, "_update_rate_limit", return_value=None), \
         patch.object(crawler, "_get_browser") as mock_get_browser:
        
        # Mock page that always fails
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=Exception("Network error"))
        mock_page.close = AsyncMock()
        
        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_get_browser.return_value = mock_browser
        
        # Perform crawl
        result = await crawler.crawl_site(
            site_id=1,
            url="https://example.com",
        )
        
        # Should fail after max retries
        assert result.success is False
        assert result.status_code == 0
        assert "Network error" in result.error_message


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("PLAYWRIGHT_AVAILABLE", "false") != "true", reason="Playwright may cause issues in test environment")
async def test_crawler_close():
    """Test that crawler properly closes resources."""
    # Create a new crawler instance for this test
    crawler = CrawlerEngine(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/1"),
        rate_limit_seconds=10,
        timeout_seconds=30,
        max_retries=3,
    )
    
    # Initialize browser (skip redis as it may not be available)
    await crawler._get_browser()
    
    assert crawler._browser is not None
    
    # Close crawler
    await crawler.close()
    
    assert crawler._browser is None

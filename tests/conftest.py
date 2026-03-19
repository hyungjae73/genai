"""
Pytest configuration and shared fixtures.

This module provides shared test fixtures and configuration for all tests.
"""

import os
import pytest
import asyncio
from hypothesis import settings as hypothesis_settings, HealthCheck

# Register hypothesis profile with min 100 examples
hypothesis_settings.register_profile(
    "ci",
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow],
)
hypothesis_settings.register_profile(
    "default",
    max_examples=100,
)
hypothesis_settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))


# Try PostgreSQL first, fallback to SQLite if not available
# Note: SQLite doesn't support JSONB, so some tests may be skipped
def get_test_database_url():
    """Get test database URL, with fallback to SQLite."""
    pg_url = "postgresql+asyncpg://payment_monitor:payment_monitor_pass@localhost:5432/payment_monitor_test"
    sqlite_url = "sqlite+aiosqlite:///:memory:"
    
    # Check if PostgreSQL is available
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 5432))
        sock.close()
        if result == 0:
            return pg_url
    except:
        pass
    
    # Fallback to SQLite
    print("\n⚠️  PostgreSQL not available, using SQLite (JSONB tests will be skipped)")
    return sqlite_url


os.environ["TEST_DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", get_test_database_url())
os.environ["USE_SQLITE"] = "true" if "sqlite" in os.environ["TEST_DATABASE_URL"] else "false"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

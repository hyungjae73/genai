"""Test that Alembic always uses the sync psycopg2 driver.

Validates: Requirements 3.1, 3.2

Verifies that alembic/env.py correctly wires derive_sync_url so that
`alembic upgrade head` never attempts to use the asyncpg driver.
"""

from pathlib import Path

import pytest
from src.database import derive_sync_url

# Read env.py source once — avoids unclosed-file warnings from bare open().
_ENV_PY = Path("alembic/env.py").read_text()


class TestAlembicSyncCompatibility:
    """Unit tests for Alembic ↔ psycopg2 compatibility."""

    def test_derive_sync_url_from_asyncpg(self):
        """asyncpg URLs are converted to psycopg2."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        result = derive_sync_url(url)
        assert result.startswith("postgresql+psycopg2://")
        assert result == "postgresql+psycopg2://user:pass@host:5432/db"

    def test_derive_sync_url_from_plain(self):
        """Plain postgresql:// URLs are converted to psycopg2."""
        url = "postgresql://user:pass@host:5432/db"
        result = derive_sync_url(url)
        assert result.startswith("postgresql+psycopg2://")
        assert result == "postgresql+psycopg2://user:pass@host:5432/db"

    def test_derive_sync_url_from_psycopg2(self):
        """psycopg2 URLs are returned unchanged."""
        url = "postgresql+psycopg2://user:pass@host:5432/db"
        result = derive_sync_url(url)
        assert result == url

    def test_alembic_env_imports_derive_sync_url(self):
        """alembic/env.py imports and calls derive_sync_url."""
        assert "from src.database import derive_sync_url" in _ENV_PY

    def test_alembic_env_sets_sqlalchemy_url(self):
        """alembic/env.py sets sqlalchemy.url via derive_sync_url."""
        assert 'config.set_main_option("sqlalchemy.url"' in _ENV_PY
        # The URL passed to set_main_option must come from derive_sync_url
        assert "derive_sync_url" in _ENV_PY

    def test_alembic_env_does_not_use_asyncpg_directly(self):
        """alembic/env.py never imports or constructs an asyncpg engine."""
        assert "create_async_engine" not in _ENV_PY
        # Filter out comments — only check executable lines for asyncpg usage
        code_lines = [
            line for line in _ENV_PY.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        code_only = "\n".join(code_lines)
        assert "import asyncpg" not in code_only
        assert "asyncpg://" not in code_only

"""
Pytest configuration and shared fixtures.

This module provides shared test fixtures and configuration for all tests.
Uses testcontainers-python to manage a PostgreSQL 15 container for testing.
"""

import os
import subprocess
import pytest
from hypothesis import settings as hypothesis_settings, HealthCheck
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer
from fastapi.testclient import TestClient

from src.models import Base
from src.database import get_db
from src.main import app

# Hypothesis settings
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


def _is_docker_available() -> bool:
    """Check if Docker daemon is available."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


DOCKER_AVAILABLE = _is_docker_available()

# Skip marker for tests that require Docker
requires_docker = pytest.mark.skipif(
    not DOCKER_AVAILABLE,
    reason="Docker is not available",
)


@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container for the test session."""
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker is not available")

    with PostgresContainer("postgres:15-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def engine(postgres_container):
    """Create a SQLAlchemy engine from the container connection URL."""
    url = postgres_container.get_connection_url()
    eng = create_engine(url, echo=False)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def tables(engine):
    """Create all tables at session start, drop them at session end."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(engine, tables):
    """Function-scoped session with transaction rollback for test isolation."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    # Support nested transactions (SAVEPOINTs) inside the outer transaction
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with db_session injected via dependency override."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

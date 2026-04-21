"""
Database configuration and session management.
"""

import os
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

from src.models import Base

# Database URL from environment variable
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://payment_monitor:payment_monitor_pass@localhost:5432/payment_monitor",
)


def derive_async_url(url: str) -> str:
    """Derive an asyncpg URL from any PostgreSQL connection URL.

    Handles three URL patterns:
    - ``postgresql://`` (no driver suffix)
    - ``postgresql+psycopg2://``
    - ``postgresql+asyncpg://``

    Returns a URL with the ``postgresql+asyncpg://`` prefix while preserving
    host, port, database name, and credentials.
    """
    if "+psycopg2" in url:
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    if "+asyncpg" in url:
        return url
    # No driver suffix
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


def derive_sync_url(url: str) -> str:
    """Derive a psycopg2 URL from any PostgreSQL connection URL.

    Handles three URL patterns:
    - ``postgresql://`` (no driver suffix)
    - ``postgresql+psycopg2://``
    - ``postgresql+asyncpg://``

    Returns a URL with the ``postgresql+psycopg2://`` prefix while preserving
    host, port, database name, and credentials.
    """
    if "+asyncpg" in url:
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    if "+psycopg2" in url:
        return url
    # No driver suffix
    return url.replace("postgresql://", "postgresql+psycopg2://", 1)


# Derive sync URL for the engine (ensures psycopg2 driver)
SYNC_DATABASE_URL = derive_sync_url(DATABASE_URL)

# Derive async URL for FastAPI endpoints (asyncpg driver)
ASYNC_DATABASE_URL = derive_async_url(DATABASE_URL)

# Create engine
engine = create_engine(
    SYNC_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

# Create session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# Async engine (for FastAPI endpoints)
async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)

# Async session factory
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    
    Yields:
        Session: Database session
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async dependency function to get database session.

    Does NOT auto-commit — callers (POST/PUT/DELETE handlers) must
    call ``await session.commit()`` explicitly.  On exception the
    session is rolled back; in all cases the session is closed.

    Yields:
        AsyncSession: Async database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def init_db() -> None:
    """
    Initialize database by creating all tables.
    """
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """
    Drop all database tables.
    """
    Base.metadata.drop_all(bind=engine)

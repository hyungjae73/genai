"""
Property-based tests for database models.

Feature: payment-compliance-monitor
Property: Contract versioning
Validates: Requirements 7.2
"""

import os
import pytest
from hypothesis import given, strategies as st, settings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from src.models import Base, MonitoringSite, ContractCondition


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


# Hypothesis strategies for generating test data
@st.composite
def monitoring_site_data(draw):
    """Generate random monitoring site data."""
    return {
        "company_name": draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_characters=["\x00"]))),
        "domain": draw(st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=("Ll", "Nd"), blacklist_characters=["\x00"]))) + ".com",
        "target_url": "https://" + draw(st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=("Ll", "Nd"), blacklist_characters=["\x00"]))) + ".com/payment",
        "is_active": draw(st.booleans()),
    }


@st.composite
def contract_condition_data(draw):
    """Generate random contract condition data."""
    return {
        "prices": {
            "amount": draw(st.floats(min_value=0.01, max_value=10000.0)),
            "currency": draw(st.sampled_from(["USD", "JPY", "EUR"])),
        },
        "payment_methods": draw(st.lists(
            st.sampled_from(["credit_card", "bank_transfer", "paypal", "stripe"]),
            min_size=1,
            max_size=4,
            unique=True,
        )),
        "fees": {
            "percentage": draw(st.floats(min_value=0.0, max_value=10.0)),
            "fixed": draw(st.floats(min_value=0.0, max_value=100.0)),
        },
        "subscription_terms": {
            "commitment_months": draw(st.integers(min_value=0, max_value=24)),
            "cancellation_policy": draw(st.sampled_from(["anytime", "30_days", "end_of_period"])),
        },
    }


@pytest.mark.asyncio
@pytest.mark.skipif(USE_SQLITE, reason="SQLite doesn't support JSONB - requires PostgreSQL")
@given(
    site_data=monitoring_site_data(),
    contract_data=contract_condition_data(),
)
@settings(max_examples=10, deadline=None)
async def test_contract_versioning_property(site_data, contract_data):
    """
    Property: Contract versioning
    
    For any monitoring site and contract condition, when a user updates a contract,
    the system should create a new version and preserve the history.
    
    This property verifies that:
    1. Creating a new contract starts at version 1
    2. Updating a contract increments the version
    3. Only the latest version has is_current=True
    4. Previous versions are preserved with is_current=False
    
    **Validates: Requirements 7.2**
    """
    # Create test database engine and session
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
    
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    try:
        async with async_session() as session:
            # Create a monitoring site
            site = MonitoringSite(**site_data)
            session.add(site)
            await session.flush()
            
            # Create initial contract condition (version 1)
            contract_v1 = ContractCondition(
                site_id=site.id,
                version=1,
                is_current=True,
                **contract_data,
            )
            session.add(contract_v1)
            await session.commit()
            
            # Verify version 1 is current
            await session.refresh(contract_v1)
            assert contract_v1.version == 1
            assert contract_v1.is_current is True
            
            # Simulate contract update: mark v1 as not current and create v2
            contract_v1.is_current = False
            
            # Create updated contract (version 2)
            updated_contract_data = contract_data.copy()
            updated_contract_data["prices"] = {
                "amount": contract_data["prices"]["amount"] * 1.1,  # 10% price increase
                "currency": contract_data["prices"]["currency"],
            }
            
            contract_v2 = ContractCondition(
                site_id=site.id,
                version=2,
                is_current=True,
                **updated_contract_data,
            )
            session.add(contract_v2)
            await session.commit()
            
            # Verify version 2 is current and version 1 is preserved
            await session.refresh(contract_v1)
            await session.refresh(contract_v2)
            
            assert contract_v1.version == 1
            assert contract_v1.is_current is False, "Previous version should not be current"
            
            assert contract_v2.version == 2
            assert contract_v2.is_current is True, "New version should be current"
            
            # Verify both versions exist in database
            from sqlalchemy import select
            result = await session.execute(
                select(ContractCondition).where(ContractCondition.site_id == site.id)
            )
            all_contracts = result.scalars().all()
            
            assert len(all_contracts) == 2, "Both contract versions should be preserved"
            
            # Verify only one is current
            current_contracts = [c for c in all_contracts if c.is_current]
            assert len(current_contracts) == 1, "Only one contract version should be current"
            assert current_contracts[0].version == 2, "The current version should be version 2"
            
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

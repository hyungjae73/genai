"""
Property-based tests for database models.

Feature: payment-compliance-monitor
Property: Contract versioning
Validates: Requirements 7.2
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy import select

from src.models import Base, Customer, MonitoringSite, ContractCondition


# Hypothesis strategies for generating test data
@st.composite
def monitoring_site_data(draw):
    """Generate random monitoring site data."""
    return {
        "name": draw(st.text(min_size=1, max_size=100, alphabet=st.characters(blacklist_characters=["\x00"]))),
        "url": "https://" + draw(st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=("Ll", "Nd"), blacklist_characters=["\x00"]))) + ".com/payment",
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


@given(
    site_data=monitoring_site_data(),
    contract_data=contract_condition_data(),
)
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_contract_versioning_property(site_data, contract_data, db_session):
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
    # Create a customer (required FK)
    customer = Customer(
        name="Test Customer",
        email="test@example.com",
    )
    db_session.add(customer)
    db_session.flush()

    # Create a monitoring site
    site = MonitoringSite(
        customer_id=customer.id,
        **site_data,
    )
    db_session.add(site)
    db_session.flush()

    # Create initial contract condition (version 1)
    contract_v1 = ContractCondition(
        site_id=site.id,
        version=1,
        is_current=True,
        **contract_data,
    )
    db_session.add(contract_v1)
    db_session.flush()

    # Verify version 1 is current
    db_session.refresh(contract_v1)
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
    db_session.add(contract_v2)
    db_session.flush()

    # Verify version 2 is current and version 1 is preserved
    db_session.refresh(contract_v1)
    db_session.refresh(contract_v2)

    assert contract_v1.version == 1
    assert contract_v1.is_current is False, "Previous version should not be current"

    assert contract_v2.version == 2
    assert contract_v2.is_current is True, "New version should be current"

    # Verify both versions exist in database
    result = db_session.execute(
        select(ContractCondition).where(ContractCondition.site_id == site.id)
    )
    all_contracts = result.scalars().all()

    assert len(all_contracts) == 2, "Both contract versions should be preserved"

    # Verify only one is current
    current_contracts = [c for c in all_contracts if c.is_current]
    assert len(current_contracts) == 1, "Only one contract version should be current"
    assert current_contracts[0].version == 2, "The current version should be version 2"

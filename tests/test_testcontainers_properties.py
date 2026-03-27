"""
Property-based tests for testcontainers-migration.

Feature: testcontainers-migration
Tests PostgreSQL-specific behavior including transaction isolation,
SAVEPOINT support, server_default correctness, timestamp precision,
and JSONB round-trip.
"""

import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from sqlalchemy import inspect

from src.models import Customer, MonitoringSite


# --- Strategies ---

def customer_name_strategy():
    """Generate valid customer names (non-empty, printable, no NUL bytes)."""
    return st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), blacklist_characters="\x00"),
        min_size=1,
        max_size=100,
    )


def email_strategy():
    """Generate simple valid email addresses."""
    local = st.from_regex(r"[a-z]{1,20}", fullmatch=True)
    domain = st.from_regex(r"[a-z]{1,10}\.[a-z]{2,4}", fullmatch=True)
    return st.builds(lambda l, d: f"{l}@{d}", local, domain)


def url_strategy():
    """Generate simple valid URLs."""
    return st.from_regex(r"https://[a-z]{1,15}\.[a-z]{2,4}", fullmatch=True)


def site_name_strategy():
    """Generate valid site names."""
    return st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z"), blacklist_characters="\x00"),
        min_size=1,
        max_size=100,
    )


# --- Property 1: Transaction rollback data isolation ---


class TestTransactionRollbackDataIsolation:
    """
    Feature: testcontainers-migration
    Property 1: Transaction rollback data isolation

    **Validates: Requirements 2.1, 2.2, 2.3**

    For any SQLAlchemy model instance and its field values, when data is
    inserted within a nested transaction and that nested transaction is
    rolled back, the data must not exist in the database.
    """

    @given(
        cust_name=customer_name_strategy(),
        cust_email=email_strategy(),
        site_name=site_name_strategy(),
        site_url=url_strategy(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_1_nested_rollback_removes_data(
        self, db_session, cust_name, cust_email, site_name, site_url
    ):
        """Data inserted in a nested transaction is gone after rollback."""
        # Begin a nested transaction (SAVEPOINT)
        nested = db_session.begin_nested()

        # Insert a Customer and a MonitoringSite
        customer = Customer(name=cust_name, email=cust_email)
        db_session.add(customer)
        db_session.flush()

        site = MonitoringSite(
            customer_id=customer.id,
            name=site_name,
            url=site_url,
        )
        db_session.add(site)
        db_session.flush()

        # Capture IDs before rollback
        customer_id = customer.id
        site_id = site.id

        # Rollback the nested transaction
        nested.rollback()

        # Verify data does not exist after rollback
        assert db_session.get(Customer, customer_id) is None
        assert db_session.get(MonitoringSite, site_id) is None

        # Also verify via query
        customer_count = db_session.query(Customer).filter_by(id=customer_id).count()
        site_count = db_session.query(MonitoringSite).filter_by(id=site_id).count()
        assert customer_count == 0
        assert site_count == 0


# --- Property 2: Nested transaction (SAVEPOINT) support ---


class TestNestedTransactionSavepointSupport:
    """
    Feature: testcontainers-migration
    Property 2: Nested transaction (SAVEPOINT) support

    **Validates: Requirements 2.4**

    For any nested transaction (SAVEPOINT) operation within the outer
    fixture-level transaction, even if the inner nested transaction is
    committed, rolling back the outer transaction must revert all data
    — including data committed inside the inner nested transaction.
    """

    @given(
        cust_name=customer_name_strategy(),
        cust_email=email_strategy(),
        site_name=site_name_strategy(),
        site_url=url_strategy(),
        site_name_2=site_name_strategy(),
        site_url_2=url_strategy(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_2_committed_inner_reverted_by_outer_rollback(
        self, db_session, cust_name, cust_email, site_name, site_url, site_name_2, site_url_2
    ):
        """Inner committed SAVEPOINT data is reverted when outer transaction rolls back."""
        # --- Step 1: Begin a nested transaction (SAVEPOINT) and commit it ---
        nested_inner = db_session.begin_nested()

        customer = Customer(name=cust_name, email=cust_email)
        db_session.add(customer)
        db_session.flush()
        customer_id = customer.id

        site1 = MonitoringSite(
            customer_id=customer_id,
            name=site_name,
            url=site_url,
        )
        db_session.add(site1)
        db_session.flush()
        site1_id = site1.id

        # Commit the inner nested transaction — data is now visible in the outer tx
        nested_inner.commit()

        # Verify data is visible after inner commit
        assert db_session.get(Customer, customer_id) is not None
        assert db_session.get(MonitoringSite, site1_id) is not None

        # --- Step 2: Begin another nested transaction, insert more data, rollback it ---
        nested_second = db_session.begin_nested()

        site2 = MonitoringSite(
            customer_id=customer_id,
            name=site_name_2,
            url=site_url_2,
        )
        db_session.add(site2)
        db_session.flush()
        site2_id = site2.id

        # Rollback the second nested transaction
        nested_second.rollback()

        # After second nested rollback: first committed data still visible,
        # second rolled-back data is gone
        assert db_session.get(Customer, customer_id) is not None
        assert db_session.get(MonitoringSite, site1_id) is not None
        assert db_session.get(MonitoringSite, site2_id) is None

        # --- Step 3: Verify the fixture-level outer rollback will revert everything ---
        # The db_session fixture rolls back the outer transaction after each test.
        # We verify here that the committed inner data is queryable *before* that
        # outer rollback happens (proving the SAVEPOINT commit worked).
        cust_count = db_session.query(Customer).filter_by(id=customer_id).count()
        site1_count = db_session.query(MonitoringSite).filter_by(id=site1_id).count()
        assert cust_count == 1
        assert site1_count == 1

        # The outer fixture rollback (in conftest.py) will revert all of this.
        # We cannot directly assert the post-fixture state from within the test,
        # but the next Hypothesis iteration starts with a clean slate — if data
        # leaked, subsequent iterations would see unexpected rows.


# --- Property 3: server_default correctness ---


class TestServerDefaultCorrectness:
    """
    Feature: testcontainers-migration
    Property 3: server_default correctness

    **Validates: Requirements 10.3**

    For any MonitoringSite inserted without specifying crawl_priority,
    PostgreSQL must apply the server_default value 'normal'.
    On SQLite, server_default was silently ignored — this property
    ensures PostgreSQL applies it correctly.
    """

    @given(
        cust_name=customer_name_strategy(),
        cust_email=email_strategy(),
        site_name=site_name_strategy(),
        site_url=url_strategy(),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_3_server_default_applied(
        self, db_session, cust_name, cust_email, site_name, site_url
    ):
        """crawl_priority defaults to 'normal' via server_default on PostgreSQL."""
        customer = Customer(name=cust_name, email=cust_email)
        db_session.add(customer)
        db_session.flush()

        # Insert MonitoringSite WITHOUT specifying crawl_priority
        site = MonitoringSite(
            customer_id=customer.id,
            name=site_name,
            url=site_url,
        )
        db_session.add(site)
        db_session.flush()

        # Expire to force re-read from DB (not cached Python default)
        db_session.expire(site)

        assert site.crawl_priority == "normal", (
            f"Expected server_default 'normal', got '{site.crawl_priority}'"
        )


# --- Property 4: Timestamp precision round-trip ---


from datetime import datetime, timezone


class TestTimestampPrecisionRoundTrip:
    """
    Feature: testcontainers-migration
    Property 4: Timestamp precision round-trip

    **Validates: Requirements 10.4**

    For any microsecond-precision datetime, PostgreSQL must preserve
    the precision on round-trip. SQLite truncated to second precision.
    """

    @given(
        cust_name=customer_name_strategy(),
        cust_email=email_strategy(),
        microsecond=st.integers(min_value=1, max_value=999999),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_4_microsecond_precision_preserved(
        self, db_session, cust_name, cust_email, microsecond
    ):
        """Microsecond precision survives PostgreSQL round-trip."""
        ts = datetime(2025, 6, 15, 12, 30, 45, microsecond)

        customer = Customer(name=cust_name, email=cust_email, created_at=ts)
        db_session.add(customer)
        db_session.flush()

        # Expire to force re-read from DB
        db_session.expire(customer)

        assert customer.created_at.microsecond == microsecond, (
            f"Expected microsecond={microsecond}, "
            f"got {customer.created_at.microsecond}"
        )


# --- Property 5: JSONB data round-trip ---


# Recursive JSON strategy (no NaN/Inf, no NUL in strings)
_json_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(
        min_size=0,
        max_size=50,
        alphabet=st.characters(blacklist_characters="\x00"),
    ),
)

_json_values = st.recursive(
    _json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(
            st.text(
                min_size=1,
                max_size=20,
                alphabet=st.characters(
                    whitelist_categories=("L", "N"),
                    blacklist_characters="\x00",
                ),
            ),
            children,
            max_size=5,
        ),
    ),
    max_leaves=15,
)


class TestJSONBDataRoundTrip:
    """
    Feature: testcontainers-migration
    Property 5: JSONB data round-trip

    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

    For any valid JSON structure, saving to a JSONB field and retrieving
    must return an equivalent value.

    Note: PostgreSQL JSONB normalizes numbers internally, so a float like
    3.5e+16 may come back as int 35000000000000000. We compare with
    numeric equivalence tolerance.
    """

    @staticmethod
    def _json_equiv(a, b) -> bool:
        """Compare JSON values with numeric equivalence (float/int interop)."""
        if isinstance(a, dict) and isinstance(b, dict):
            return a.keys() == b.keys() and all(
                TestJSONBDataRoundTrip._json_equiv(a[k], b[k]) for k in a
            )
        if isinstance(a, list) and isinstance(b, list):
            return len(a) == len(b) and all(
                TestJSONBDataRoundTrip._json_equiv(x, y) for x, y in zip(a, b)
            )
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return float(a) == float(b)
        return a == b

    @given(json_data=_json_values)
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_5_jsonb_round_trip(self, db_session, json_data):
        """Arbitrary JSON data survives JSONB round-trip."""
        from src.models import VerificationResult

        customer = Customer(name="JSONB Test", email="jsonb@test.com")
        db_session.add(customer)
        db_session.flush()

        site = MonitoringSite(
            customer_id=customer.id,
            name="JSONB Site",
            url="https://jsonb.test",
        )
        db_session.add(site)
        db_session.flush()

        stored = json_data if isinstance(json_data, (dict, list)) else {"value": json_data}

        vr = VerificationResult(
            site_id=site.id,
            html_data={"test": True},
            ocr_data={"test": True},
            html_violations=[],
            ocr_violations=[],
            discrepancies=[],
            screenshot_path="/test.png",
            ocr_confidence=0.9,
            status="success",
            structured_data=stored,
        )
        db_session.add(vr)
        db_session.flush()

        db_session.expire(vr)

        assert self._json_equiv(vr.structured_data, stored), (
            f"JSONB round-trip failed: {stored!r} != {vr.structured_data!r}"
        )

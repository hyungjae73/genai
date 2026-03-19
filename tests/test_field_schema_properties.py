"""
Property-based tests for Field Schema API endpoints and validation.

Feature: hierarchical-ui-restructure
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st, settings, HealthCheck

from src.api.field_schemas import router
from src.database import get_db
from src.models import FieldSchema
from src.field_validation import validate_field_value


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_FIELD_TYPES = ["text", "number", "currency", "percentage", "date", "boolean", "list"]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

field_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip() != "")

field_type_strategy = st.sampled_from(VALID_FIELD_TYPES)

validation_rules_strategy = st.one_of(
    st.none(),
    st.fixed_dictionaries({}),
    st.fixed_dictionaries({"min": st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)}),
    st.fixed_dictionaries({
        "min": st.floats(min_value=-1e6, max_value=0, allow_nan=False, allow_infinity=False),
        "max": st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
    }),
    st.fixed_dictionaries({"max_length": st.integers(min_value=1, max_value=1000)}),
    st.fixed_dictionaries({"pattern": st.just(r"^[A-Za-z]+")}),
    st.fixed_dictionaries({"options": st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=10)}),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Create a minimal FastAPI app with the field schemas router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/field-schemas")
    return app


def _make_mock_db():
    """
    Create a mock DB session that stores created field schemas in memory
    and returns them on query, simulating a real DB round-trip.
    """
    db = MagicMock()
    store = {}
    next_id = [1]

    def mock_add(obj):
        obj.id = next_id[0]
        obj.created_at = datetime.utcnow()
        obj.updated_at = datetime.utcnow()
        store[obj.id] = obj
        next_id[0] += 1

    def mock_commit():
        pass

    def mock_refresh(obj):
        pass

    def mock_query(model):
        q = MagicMock()

        def mock_filter(*args, **kwargs):
            f = MagicMock()

            # Support chained .filter() calls for duplicate check
            def inner_filter(*a, **kw):
                ff = MagicMock()
                ff.first.return_value = None
                return ff
            f.filter.side_effect = inner_filter

            # For the duplicate check: .filter(category_id, field_name).first()
            f.first.return_value = None

            # For listing by category: .filter(category_id).order_by(...).all()
            def mock_order_by(*a, **kw):
                ob = MagicMock()
                # Filter by category_id — we extract it from the stored objects
                # Since we can't easily inspect SQLAlchemy filter args in mocks,
                # we return all stored items (the test creates one at a time)
                ob.all.return_value = list(store.values())
                return ob
            f.order_by.side_effect = mock_order_by

            return f

        q.filter.side_effect = mock_filter

        return q

    db.add.side_effect = mock_add
    db.commit.side_effect = mock_commit
    db.refresh.side_effect = mock_refresh
    db.query.side_effect = mock_query

    return db, store


def _make_mock_schema(
    field_type: str = "text",
    is_required: bool = False,
    validation_rules: dict = None,
) -> MagicMock:
    """Create a mock FieldSchema for validation testing."""
    schema = MagicMock()
    schema.field_type = field_type
    schema.is_required = is_required
    schema.validation_rules = validation_rules
    return schema


# ===========================================================================
# Property 12: フィールドスキーマCRUDの往復 (Task 3.5)
# ===========================================================================

class TestFieldSchemaCRUDRoundTrip:
    """
    Property 12: フィールドスキーマCRUDの往復

    For any valid field schema data (category_id, field_name, field_type),
    creating via POST and retrieving via GET should return a field schema
    whose field_name, field_type, and validation_rules match the creation data.

    Feature: hierarchical-ui-restructure, Property 12: フィールドスキーマCRUDの往復
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        field_name=field_name_strategy,
        field_type=field_type_strategy,
        validation_rules=validation_rules_strategy,
        is_required=st.booleans(),
        display_order=st.integers(min_value=0, max_value=100),
    )
    def test_property_field_schema_crud_round_trip(
        self,
        field_name: str,
        field_type: str,
        validation_rules,
        is_required: bool,
        display_order: int,
    ):
        """
        Property 12: フィールドスキーマCRUDの往復

        任意の有効なフィールドスキーマデータ（カテゴリID、フィールド名、フィールド型）に対して、
        作成→取得の操作を行った場合、取得したフィールドスキーマのフィールド名・型・
        バリデーションルールは作成時のデータと一致すること。

        **Validates: Requirements 8.1, 8.5**
        """
        app = _make_app()
        db, store = _make_mock_db()
        category_id = 1

        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app)

        # Step 1: Create a field schema via POST
        payload = {
            "category_id": category_id,
            "field_name": field_name,
            "field_type": field_type,
            "is_required": is_required,
            "display_order": display_order,
        }
        if validation_rules is not None:
            payload["validation_rules"] = validation_rules

        create_response = client.post("/api/field-schemas/", json=payload)

        assert create_response.status_code == 201, (
            f"Expected 201 for field schema creation, "
            f"got {create_response.status_code}: {create_response.text}"
        )

        created = create_response.json()

        # Step 2: Retrieve field schemas by category via GET
        list_response = client.get(f"/api/field-schemas/category/{category_id}")

        assert list_response.status_code == 200, (
            f"Expected 200 for field schema listing, "
            f"got {list_response.status_code}: {list_response.text}"
        )

        schemas = list_response.json()

        # Step 3: Find the created schema in the list
        matching = [s for s in schemas if s["id"] == created["id"]]
        assert len(matching) == 1, (
            f"Expected exactly 1 field schema with id={created['id']}, "
            f"found {len(matching)}"
        )

        retrieved = matching[0]

        # Step 4: Assert round-trip consistency
        assert retrieved["field_name"] == field_name, (
            f"field_name mismatch: expected {field_name!r}, got {retrieved['field_name']!r}"
        )
        assert retrieved["field_type"] == field_type, (
            f"field_type mismatch: expected {field_type!r}, got {retrieved['field_type']!r}"
        )
        assert retrieved["validation_rules"] == validation_rules, (
            f"validation_rules mismatch: expected {validation_rules!r}, "
            f"got {retrieved['validation_rules']!r}"
        )
        assert retrieved["is_required"] == is_required, (
            f"is_required mismatch: expected {is_required!r}, got {retrieved['is_required']!r}"
        )

        # Cleanup
        app.dependency_overrides.clear()


# ===========================================================================
# Property 13: フィールド型の網羅性 (Task 3.6)
# ===========================================================================

class TestFieldTypeCompleteness:
    """
    Property 13: フィールド型の網羅性

    For any supported field type (text, number, currency, percentage, date,
    boolean, list), creating a field schema with that type should succeed
    and the type should be preserved when retrieved.

    Feature: hierarchical-ui-restructure, Property 13: フィールド型の網羅性
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        field_type=st.sampled_from(VALID_FIELD_TYPES),
    )
    def test_property_field_type_completeness(
        self,
        field_type: str,
    ):
        """
        Property 13: フィールド型の網羅性

        任意のサポート対象フィールド型（text, number, currency, percentage,
        date, boolean, list）に対して、その型でフィールドスキーマを作成した場合、
        作成が成功し、取得時に正しい型が返されること。

        **Validates: Requirements 8.2**
        """
        app = _make_app()
        db, store = _make_mock_db()
        category_id = 1

        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app)

        # Step 1: Create a field schema with the given type
        payload = {
            "category_id": category_id,
            "field_name": f"test_field_{field_type}",
            "field_type": field_type,
            "is_required": False,
            "display_order": 0,
        }

        create_response = client.post("/api/field-schemas/", json=payload)

        # Step 2: Assert creation succeeds
        assert create_response.status_code == 201, (
            f"Expected 201 for field type '{field_type}', "
            f"got {create_response.status_code}: {create_response.text}"
        )

        created = create_response.json()

        # Step 3: Assert the type is preserved in the response
        assert created["field_type"] == field_type, (
            f"field_type mismatch in creation response: "
            f"expected {field_type!r}, got {created['field_type']!r}"
        )

        # Step 4: Retrieve and verify type is preserved
        list_response = client.get(f"/api/field-schemas/category/{category_id}")
        assert list_response.status_code == 200

        schemas = list_response.json()
        matching = [s for s in schemas if s["id"] == created["id"]]
        assert len(matching) == 1

        retrieved = matching[0]
        assert retrieved["field_type"] == field_type, (
            f"field_type mismatch after retrieval: "
            f"expected {field_type!r}, got {retrieved['field_type']!r}"
        )

        # Cleanup
        app.dependency_overrides.clear()


# ===========================================================================
# Property 16: フィールドバリデーションルールの適用 (Task 3.7)
# ===========================================================================

class TestFieldValidationRulesApplication:
    """
    Property 16: フィールドバリデーションルールの適用

    For any field schema with validation rules (required/optional, min/max,
    regex pattern), values violating the rules should produce validation
    errors, and conforming values should pass validation.

    Feature: hierarchical-ui-restructure, Property 16: フィールドバリデーションルールの適用
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(data=st.data())
    def test_property_validation_rules_application(self, data):
        """
        Property 16: フィールドバリデーションルールの適用

        任意のバリデーションルール（必須/任意、最小値/最大値、正規表現パターン）が
        設定されたフィールドスキーマに対して、ルールに違反する値はバリデーションエラーとなり、
        ルールに適合する値はバリデーションを通過すること。

        **Validates: Requirements 8.7**
        """
        # Pick a scenario: each scenario generates a schema + conforming value + violating value
        scenario = data.draw(st.sampled_from([
            "required_field",
            "number_min_max",
            "text_pattern",
            "text_max_length",
            "percentage_range",
            "list_options",
        ]))

        if scenario == "required_field":
            # Required field: None should fail, non-empty value should pass
            field_type = data.draw(st.sampled_from(["text", "number", "boolean"]))
            schema = _make_mock_schema(
                field_type=field_type,
                is_required=True,
                validation_rules={},
            )

            # Conforming value
            if field_type == "text":
                conforming = data.draw(st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != ""))
            elif field_type == "number":
                conforming = data.draw(st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False))
            else:
                conforming = data.draw(st.booleans())

            is_valid, error = validate_field_value(conforming, schema)
            assert is_valid, (
                f"Conforming value {conforming!r} for required {field_type} field "
                f"should pass validation, but got error: {error}"
            )

            # Violating value: None
            is_valid, error = validate_field_value(None, schema)
            assert not is_valid, (
                f"None for required {field_type} field should fail validation"
            )

        elif scenario == "number_min_max":
            min_val = data.draw(st.floats(min_value=-1000, max_value=0, allow_nan=False, allow_infinity=False))
            max_val = data.draw(st.floats(min_value=0.01, max_value=1000, allow_nan=False, allow_infinity=False))

            schema = _make_mock_schema(
                field_type="number",
                is_required=False,
                validation_rules={"min": min_val, "max": max_val},
            )

            # Conforming value: within range
            conforming = data.draw(st.floats(
                min_value=min_val, max_value=max_val,
                allow_nan=False, allow_infinity=False,
            ))
            is_valid, error = validate_field_value(conforming, schema)
            assert is_valid, (
                f"Value {conforming} within [{min_val}, {max_val}] should pass, "
                f"but got error: {error}"
            )

            # Violating value: below min
            violating = min_val - data.draw(st.floats(
                min_value=0.01, max_value=1000,
                allow_nan=False, allow_infinity=False,
            ))
            is_valid, error = validate_field_value(violating, schema)
            assert not is_valid, (
                f"Value {violating} below min {min_val} should fail validation"
            )

        elif scenario == "text_pattern":
            # Pattern: must start with uppercase letter
            schema = _make_mock_schema(
                field_type="text",
                is_required=False,
                validation_rules={"pattern": r"^[A-Z]"},
            )

            # Conforming: starts with uppercase
            prefix = data.draw(st.sampled_from(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")))
            suffix = data.draw(st.text(min_size=0, max_size=20))
            conforming = prefix + suffix
            is_valid, error = validate_field_value(conforming, schema)
            assert is_valid, (
                f"Value {conforming!r} starting with uppercase should pass, "
                f"but got error: {error}"
            )

            # Violating: starts with lowercase
            lower_prefix = data.draw(st.sampled_from(list("abcdefghijklmnopqrstuvwxyz")))
            violating = lower_prefix + suffix
            is_valid, error = validate_field_value(violating, schema)
            assert not is_valid, (
                f"Value {violating!r} starting with lowercase should fail pattern validation"
            )

        elif scenario == "text_max_length":
            max_length = data.draw(st.integers(min_value=1, max_value=50))
            schema = _make_mock_schema(
                field_type="text",
                is_required=False,
                validation_rules={"max_length": max_length},
            )

            # Conforming: within max_length
            conforming = data.draw(st.text(min_size=1, max_size=max_length))
            is_valid, error = validate_field_value(conforming, schema)
            assert is_valid, (
                f"Value of length {len(conforming)} within max_length {max_length} "
                f"should pass, but got error: {error}"
            )

            # Violating: exceeds max_length
            violating = "x" * (max_length + 1)
            is_valid, error = validate_field_value(violating, schema)
            assert not is_valid, (
                f"Value of length {len(violating)} exceeding max_length {max_length} "
                f"should fail validation"
            )

        elif scenario == "percentage_range":
            schema = _make_mock_schema(
                field_type="percentage",
                is_required=False,
                validation_rules={"min": 0, "max": 100},
            )

            # Conforming: within [0, 100]
            conforming = data.draw(st.floats(
                min_value=0, max_value=100,
                allow_nan=False, allow_infinity=False,
            ))
            is_valid, error = validate_field_value(conforming, schema)
            assert is_valid, (
                f"Percentage {conforming} within [0, 100] should pass, "
                f"but got error: {error}"
            )

            # Violating: above 100
            violating = 100 + data.draw(st.floats(
                min_value=0.01, max_value=1000,
                allow_nan=False, allow_infinity=False,
            ))
            is_valid, error = validate_field_value(violating, schema)
            assert not is_valid, (
                f"Percentage {violating} above 100 should fail validation"
            )

        elif scenario == "list_options":
            options = data.draw(st.lists(
                st.text(min_size=1, max_size=20).filter(lambda s: s.strip() != ""),
                min_size=2,
                max_size=10,
                unique=True,
            ))
            schema = _make_mock_schema(
                field_type="list",
                is_required=False,
                validation_rules={"options": options},
            )

            # Conforming: pick from options
            conforming = data.draw(st.sampled_from(options))
            is_valid, error = validate_field_value(conforming, schema)
            assert is_valid, (
                f"Value {conforming!r} in options should pass, "
                f"but got error: {error}"
            )

            # Violating: value not in options
            violating = data.draw(
                st.text(min_size=1, max_size=30).filter(lambda s: s not in options)
            )
            is_valid, error = validate_field_value(violating, schema)
            assert not is_valid, (
                f"Value {violating!r} not in options {options} should fail validation"
            )

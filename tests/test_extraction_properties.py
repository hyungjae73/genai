"""
Property-based tests for Data Extraction API endpoints.

Feature: hierarchical-ui-restructure
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st, settings, HealthCheck

from src.api.extraction import router as extraction_router, _infer_field_type
from src.api.field_schemas import router as field_schemas_router
from src.database import get_db
from src.models import ExtractedData, FieldSchema


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_FIELD_TYPES = ["text", "number", "currency", "percentage", "date", "boolean", "list"]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for extracted field values that cover all inferred types
currency_value_strategy = st.one_of(
    st.from_regex(r"\¥[1-9][0-9,]{0,8}", fullmatch=True),
    st.from_regex(r"\$[1-9][0-9]{0,4}\.[0-9]{2}", fullmatch=True),
)

percentage_value_strategy = st.from_regex(r"[1-9][0-9]{0,2}%", fullmatch=True)

date_value_strategy = st.dates().map(lambda d: d.strftime("%Y-%m-%d"))

number_value_strategy = st.integers(min_value=0, max_value=999999).map(str)

boolean_value_strategy = st.sampled_from(["true", "false", "yes", "no", "はい", "いいえ"])

text_value_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L",), whitelist_characters=" "),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() != "" and not s.strip().isdigit())

field_value_strategy = st.one_of(
    currency_value_strategy,
    percentage_value_strategy,
    date_value_strategy,
    number_value_strategy,
    boolean_value_strategy,
    text_value_strategy,
)

# Strategy for field names (excluding "full_text" which is a meta-field)
field_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip() != "" and s != "full_text")

# Strategy for extracted_fields dictionaries
extracted_fields_strategy = st.dictionaries(
    keys=field_name_strategy,
    values=field_value_strategy,
    min_size=1,
    max_size=10,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_extraction_app():
    """Create a minimal FastAPI app with the extraction router."""
    app = FastAPI()
    app.include_router(extraction_router, prefix="/api/extraction")
    return app


def _make_combined_app():
    """Create a FastAPI app with both extraction and field_schemas routers."""
    app = FastAPI()
    app.include_router(extraction_router, prefix="/api/extraction")
    app.include_router(field_schemas_router, prefix="/api/field-schemas")
    return app


def _make_mock_db_with_extracted_data(extracted_fields: dict, confidence_scores: dict):
    """
    Create a mock DB session that returns a pre-populated ExtractedData
    when queried by screenshot_id.
    """
    db = MagicMock()

    mock_extracted = MagicMock(spec=ExtractedData)
    mock_extracted.id = 1
    mock_extracted.screenshot_id = 100
    mock_extracted.site_id = 1
    mock_extracted.extracted_fields = extracted_fields
    mock_extracted.confidence_scores = confidence_scores
    mock_extracted.status = "pending"
    mock_extracted.created_at = datetime.utcnow()

    def mock_query(model):
        q = MagicMock()

        def mock_filter(*args, **kwargs):
            f = MagicMock()
            f.first.return_value = mock_extracted
            return f

        q.filter.side_effect = mock_filter
        return q

    db.query.side_effect = mock_query
    return db


def _make_mock_db_for_approval():
    """
    Create a mock DB session that supports:
    1. Querying ExtractedData (for suggest-fields)
    2. Creating FieldSchema (for POST /api/field-schemas/)
    3. Listing FieldSchema by category (for GET /api/field-schemas/category/{id})
    """
    db = MagicMock()
    field_schema_store = {}
    next_id = [1]
    extracted_data_obj = None

    def set_extracted_data(obj):
        nonlocal extracted_data_obj
        extracted_data_obj = obj

    def mock_add(obj):
        if isinstance(obj, FieldSchema) or hasattr(obj, "field_name"):
            obj.id = next_id[0]
            obj.created_at = datetime.utcnow()
            obj.updated_at = datetime.utcnow()
            field_schema_store[obj.id] = obj
            next_id[0] += 1

    def mock_commit():
        pass

    def mock_refresh(obj):
        pass

    def mock_query(model):
        q = MagicMock()

        if model is ExtractedData or (hasattr(model, "__tablename__") and getattr(model, "__tablename__", None) == "extracted_data"):
            def mock_filter(*args, **kwargs):
                f = MagicMock()
                f.first.return_value = extracted_data_obj
                return f
            q.filter.side_effect = mock_filter
        else:
            # FieldSchema queries
            def mock_filter(*args, **kwargs):
                f = MagicMock()
                # For duplicate check: .filter(...).first() returns None (no duplicates)
                f.first.return_value = None

                # For chained .filter() (name uniqueness check)
                def inner_filter(*a, **kw):
                    ff = MagicMock()
                    ff.first.return_value = None
                    return ff
                f.filter.side_effect = inner_filter

                # For listing: .filter(...).order_by(...).all()
                def mock_order_by(*a, **kw):
                    ob = MagicMock()
                    ob.all.return_value = list(field_schema_store.values())
                    return ob
                f.order_by.side_effect = mock_order_by

                return f
            q.filter.side_effect = mock_filter

        return q

    db.add.side_effect = mock_add
    db.commit.side_effect = mock_commit
    db.refresh.side_effect = mock_refresh
    db.query.side_effect = mock_query

    return db, field_schema_store, set_extracted_data


# ===========================================================================
# Property 14: フィールド候補提案の正確性 (Task 5.4)
# ===========================================================================

class TestFieldSuggestionAccuracy:
    """
    Property 14: フィールド候補提案の正確性

    For any extracted data (extracted_fields), applying the field suggestion
    function should generate a suggestion for each field, and each suggestion
    must contain field_name, field_type, sample_value, and confidence.

    Feature: hierarchical-ui-restructure, Property 14: フィールド候補提案の正確性
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        extracted_fields=extracted_fields_strategy,
    )
    def test_property_field_suggestion_accuracy_via_api(
        self,
        extracted_fields: dict,
    ):
        """
        Property 14: フィールド候補提案の正確性 (API level)

        任意の抽出データ（extracted_fields）に対して、suggest-fields APIを呼び出した場合、
        抽出データの各フィールドに対応する候補が生成され、各候補にはフィールド名、
        推定型、サンプル値、信頼度が含まれること。

        **Validates: Requirements 8.3**
        """
        # Build confidence scores matching the extracted fields
        confidence_scores = {k: 0.85 for k in extracted_fields}

        app = _make_extraction_app()
        db = _make_mock_db_with_extracted_data(extracted_fields, confidence_scores)
        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, headers={"X-API-Key": "dev-api-key"})

        # Call suggest-fields endpoint
        response = client.post("/api/extraction/suggest-fields/100")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

        suggestions = response.json()

        # Each non-"full_text" field should have a corresponding suggestion
        expected_field_names = {k for k in extracted_fields if k != "full_text"}
        suggestion_field_names = {s["field_name"] for s in suggestions}

        assert expected_field_names == suggestion_field_names, (
            f"Suggestion field names mismatch.\n"
            f"Expected: {expected_field_names}\n"
            f"Got: {suggestion_field_names}"
        )

        # Each suggestion must have all required attributes
        for suggestion in suggestions:
            assert "field_name" in suggestion, "Suggestion missing 'field_name'"
            assert "field_type" in suggestion, "Suggestion missing 'field_type'"
            assert "sample_value" in suggestion, "Suggestion missing 'sample_value'"
            assert "confidence" in suggestion, "Suggestion missing 'confidence'"

            # field_type must be one of the valid types
            assert suggestion["field_type"] in VALID_FIELD_TYPES, (
                f"Suggestion field_type '{suggestion['field_type']}' is not a valid type. "
                f"Valid types: {VALID_FIELD_TYPES}"
            )

            # confidence must be a number between 0 and 1
            assert isinstance(suggestion["confidence"], (int, float)), (
                f"Confidence must be numeric, got {type(suggestion['confidence'])}"
            )
            assert 0.0 <= suggestion["confidence"] <= 1.0, (
                f"Confidence {suggestion['confidence']} out of range [0, 1]"
            )

        # Cleanup
        app.dependency_overrides.clear()

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        value=field_value_strategy,
    )
    def test_property_infer_field_type_returns_valid_type(self, value: str):
        """
        Property 14 (supplementary): _infer_field_type always returns a valid type.

        For any string value, _infer_field_type should return one of the
        supported field types.

        **Validates: Requirements 8.3**
        """
        result = _infer_field_type(value)
        assert result in VALID_FIELD_TYPES, (
            f"_infer_field_type({value!r}) returned '{result}', "
            f"which is not in {VALID_FIELD_TYPES}"
        )


# ===========================================================================
# Property 15: フィールド候補承認によるスキーマ追加 (Task 5.5)
# ===========================================================================

class TestFieldSuggestionApprovalAddsSchema:
    """
    Property 15: フィールド候補承認によるスキーマ追加

    When a field suggestion is approved (by creating a FieldSchema from it),
    the field should appear in the category's field schema list.

    Feature: hierarchical-ui-restructure, Property 15: フィールド候補承認によるスキーマ追加
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        extracted_fields=extracted_fields_strategy,
    )
    def test_property_field_suggestion_approval_adds_schema(
        self,
        extracted_fields: dict,
    ):
        """
        Property 15: フィールド候補承認によるスキーマ追加

        任意のフィールド候補を承認した場合、該当カテゴリのフィールドスキーマ一覧に
        当該フィールドが追加されていること。

        **Validates: Requirements 8.4**
        """
        category_id = 1
        confidence_scores = {k: 0.9 for k in extracted_fields}

        app = _make_combined_app()
        db, field_schema_store, set_extracted_data = _make_mock_db_for_approval()

        # Set up the extracted data object
        mock_extracted = MagicMock(spec=ExtractedData)
        mock_extracted.id = 1
        mock_extracted.screenshot_id = 100
        mock_extracted.site_id = 1
        mock_extracted.extracted_fields = extracted_fields
        mock_extracted.confidence_scores = confidence_scores
        mock_extracted.status = "pending"
        mock_extracted.created_at = datetime.utcnow()
        set_extracted_data(mock_extracted)

        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, headers={"X-API-Key": "dev-api-key"})

        # Step 1: Get field suggestions
        suggest_response = client.post("/api/extraction/suggest-fields/100")
        assert suggest_response.status_code == 200, (
            f"Expected 200 for suggest-fields, got {suggest_response.status_code}"
        )
        suggestions = suggest_response.json()

        # Step 2: "Approve" each suggestion by creating a FieldSchema
        for suggestion in suggestions:
            create_payload = {
                "category_id": category_id,
                "field_name": suggestion["field_name"],
                "field_type": suggestion["field_type"],
                "is_required": False,
                "display_order": 0,
            }
            create_response = client.post("/api/field-schemas/", json=create_payload)
            assert create_response.status_code == 201, (
                f"Expected 201 for field schema creation from suggestion "
                f"'{suggestion['field_name']}', got {create_response.status_code}: "
                f"{create_response.text}"
            )

        # Step 3: Retrieve all field schemas for the category
        list_response = client.get(f"/api/field-schemas/category/{category_id}")
        assert list_response.status_code == 200, (
            f"Expected 200 for field schema listing, got {list_response.status_code}"
        )
        schemas = list_response.json()

        # Step 4: Verify each approved suggestion appears in the schema list
        schema_field_names = {s["field_name"] for s in schemas}
        suggestion_field_names = {s["field_name"] for s in suggestions}

        assert suggestion_field_names.issubset(schema_field_names), (
            f"Not all approved suggestions appear in the schema list.\n"
            f"Missing: {suggestion_field_names - schema_field_names}\n"
            f"Schema field names: {schema_field_names}\n"
            f"Suggestion field names: {suggestion_field_names}"
        )

        # Also verify each schema has the correct type from the suggestion
        suggestion_types = {s["field_name"]: s["field_type"] for s in suggestions}
        for schema in schemas:
            if schema["field_name"] in suggestion_types:
                assert schema["field_type"] == suggestion_types[schema["field_name"]], (
                    f"Field type mismatch for '{schema['field_name']}': "
                    f"expected '{suggestion_types[schema['field_name']]}', "
                    f"got '{schema['field_type']}'"
                )

        # Cleanup
        app.dependency_overrides.clear()

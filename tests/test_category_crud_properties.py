"""
Property-based tests for Category CRUD API endpoints.

Feature: hierarchical-ui-restructure
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, strategies as st, settings, HealthCheck

from src.api.categories import router
from src.database import get_db
from src.models import Category, MonitoringSite, ContractCondition


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

hex_color_strategy = st.from_regex(r"^#[0-9A-Fa-f]{6}$", fullmatch=True)

category_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip() != "")

category_description_strategy = st.one_of(
    st.none(),
    st.text(min_size=0, max_size=500),
)

category_color_strategy = st.one_of(
    st.none(),
    hex_color_strategy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Create a minimal FastAPI app with the categories router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/categories")
    return app


def _make_mock_db_for_roundtrip():
    """
    Create a mock DB session that stores created categories in memory
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

        # Support .filter(...).first() for duplicate check
        def mock_filter(*args, **kwargs):
            f = MagicMock()
            # For the duplicate name check during creation:
            # db.query(Category).filter(Category.name == name).first()
            # We check if any stored category has the same name
            f.first.return_value = None
            return f

        q.filter.side_effect = mock_filter

        # Support .order_by(...).all() for listing
        def mock_order_by(*args, **kwargs):
            ob = MagicMock()
            ob.all.return_value = list(store.values())
            return ob

        q.order_by.side_effect = mock_order_by

        return q

    db.add.side_effect = mock_add
    db.commit.side_effect = mock_commit
    db.refresh.side_effect = mock_refresh
    db.query.side_effect = mock_query

    return db


# ===========================================================================
# Property 9: カテゴリCRUDの往復 (Task 2.4)
# ===========================================================================

class TestCategoryCRUDRoundTrip:
    """
    Property 9: カテゴリCRUDの往復

    For any valid category data, creating a category via POST and then
    retrieving it via GET should return a category whose name, description,
    and color match the original creation data.

    Feature: hierarchical-ui-restructure, Property 9: カテゴリCRUDの往復
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        name=category_name_strategy,
        description=category_description_strategy,
        color=category_color_strategy,
    )
    def test_property_category_crud_round_trip(
        self,
        name: str,
        description,
        color,
    ):
        """
        Property 9: カテゴリCRUDの往復

        任意の有効なカテゴリデータに対して、作成→取得の操作を行った場合、
        取得したカテゴリの名前・説明・色は作成時のデータと一致すること。

        **Validates: Requirements 7.1**
        """
        app = _make_app()
        db = _make_mock_db_for_roundtrip()

        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, headers={"X-API-Key": "dev-api-key"})

        # Step 1: Create a category via POST
        payload = {"name": name}
        if description is not None:
            payload["description"] = description
        if color is not None:
            payload["color"] = color

        create_response = client.post("/api/categories/", json=payload)

        assert create_response.status_code == 201, (
            f"Expected 201 for category creation, "
            f"got {create_response.status_code}: {create_response.text}"
        )

        created = create_response.json()

        # Step 2: Retrieve all categories via GET
        list_response = client.get("/api/categories/")

        assert list_response.status_code == 200, (
            f"Expected 200 for category listing, "
            f"got {list_response.status_code}: {list_response.text}"
        )

        categories = list_response.json()

        # Step 3: Find the created category in the list
        matching = [c for c in categories if c["id"] == created["id"]]
        assert len(matching) == 1, (
            f"Expected exactly 1 category with id={created['id']}, "
            f"found {len(matching)} in {categories}"
        )

        retrieved = matching[0]

        # Step 4: Assert round-trip consistency
        assert retrieved["name"] == name, (
            f"Name mismatch: expected {name!r}, got {retrieved['name']!r}"
        )
        assert retrieved["description"] == description, (
            f"Description mismatch: expected {description!r}, "
            f"got {retrieved['description']!r}"
        )
        assert retrieved["color"] == color, (
            f"Color mismatch: expected {color!r}, got {retrieved['color']!r}"
        )

        # Cleanup
        app.dependency_overrides.clear()

# ===========================================================================
# Property 10: カテゴリ削除時の未分類移動 (Task 2.5)
# ===========================================================================

class TestCategoryDeleteUncategorize:
    """
    Property 10: カテゴリ削除時の未分類移動

    For any category with associated sites and contract conditions,
    deleting the category should set category_id=NULL on all related
    MonitoringSite and ContractCondition records.

    Feature: hierarchical-ui-restructure, Property 10: カテゴリ削除時の未分類移動
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        name=category_name_strategy,
        description=category_description_strategy,
        color=category_color_strategy,
        num_sites=st.integers(min_value=0, max_value=10),
        num_contracts=st.integers(min_value=0, max_value=10),
    )
    def test_property_category_delete_uncategorize(
        self,
        name: str,
        description,
        color,
        num_sites: int,
        num_contracts: int,
    ):
        """
        Property 10: カテゴリ削除時の未分類移動

        任意のカテゴリに属するサイトおよび契約条件が存在する場合、
        当該カテゴリを削除した後、それらのサイトおよび契約条件の
        category_id は NULL（未分類）になること。

        **Validates: Requirements 7.4**
        """
        app = _make_app()
        db = MagicMock()

        # --- In-memory stores ---
        category_store = {}
        site_store = []      # list of dicts with 'id' and 'category_id'
        contract_store = []  # list of dicts with 'id' and 'category_id'
        next_cat_id = [1]
        # Track query call sequence to distinguish create vs delete paths
        category_query_call_count = [0]

        # Pre-populate sites and contracts (initially unassigned)
        for i in range(num_sites):
            site_store.append({"id": i + 1, "category_id": None})
        for i in range(num_contracts):
            contract_store.append({"id": i + 1, "category_id": None})

        def mock_add(obj):
            obj.id = next_cat_id[0]
            obj.created_at = datetime.utcnow()
            obj.updated_at = datetime.utcnow()
            category_store[obj.id] = obj
            next_cat_id[0] += 1
            # Assign this category to all sites and contracts
            for s in site_store:
                s["category_id"] = obj.id
            for c in contract_store:
                c["category_id"] = obj.id

        def mock_commit():
            pass

        def mock_refresh(obj):
            pass

        def mock_delete(obj):
            category_store.pop(obj.id, None)

        def mock_query(model):
            q = MagicMock()

            if model is Category:
                def mock_filter(*args, **kwargs):
                    category_query_call_count[0] += 1
                    f = MagicMock()

                    call_num = category_query_call_count[0]
                    if call_num == 1:
                        # First call: duplicate name check during creation
                        # Should return None (no duplicate)
                        f.first.return_value = None
                    else:
                        # Subsequent calls: lookup by id for delete
                        # Return the first stored category
                        cats = list(category_store.values())
                        f.first.return_value = cats[0] if cats else None

                    return f
                q.filter.side_effect = mock_filter

                def mock_order_by(*args, **kwargs):
                    ob = MagicMock()
                    ob.all.return_value = list(category_store.values())
                    return ob
                q.order_by.side_effect = mock_order_by

            elif model is MonitoringSite:
                def mock_filter_sites(*args, **kwargs):
                    f = MagicMock()
                    def mock_update(values):
                        for s in site_store:
                            if s["category_id"] is not None:
                                for key, val in values.items():
                                    s[key] = val
                        return len([s for s in site_store if s["category_id"] is not None])
                    f.update.side_effect = mock_update
                    return f
                q.filter.side_effect = mock_filter_sites

            elif model is ContractCondition:
                def mock_filter_contracts(*args, **kwargs):
                    f = MagicMock()
                    def mock_update(values):
                        for c in contract_store:
                            if c["category_id"] is not None:
                                for key, val in values.items():
                                    c[key] = val
                        return len([c for c in contract_store if c["category_id"] is not None])
                    f.update.side_effect = mock_update
                    return f
                q.filter.side_effect = mock_filter_contracts

            return q

        db.add.side_effect = mock_add
        db.commit.side_effect = mock_commit
        db.refresh.side_effect = mock_refresh
        db.delete.side_effect = mock_delete
        db.query.side_effect = mock_query

        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, headers={"X-API-Key": "dev-api-key"})

        # Step 1: Create a category
        payload = {"name": name}
        if description is not None:
            payload["description"] = description
        if color is not None:
            payload["color"] = color

        create_resp = client.post("/api/categories/", json=payload)
        assert create_resp.status_code == 201, (
            f"Expected 201, got {create_resp.status_code}: {create_resp.text}"
        )
        created = create_resp.json()
        cat_id = created["id"]

        # Verify sites and contracts are assigned to the category
        if num_sites > 0:
            assert all(s["category_id"] == cat_id for s in site_store), (
                "Sites should be assigned to the created category before deletion"
            )
        if num_contracts > 0:
            assert all(c["category_id"] == cat_id for c in contract_store), (
                "Contracts should be assigned to the created category before deletion"
            )

        # Step 2: Delete the category
        delete_resp = client.delete(f"/api/categories/{cat_id}")
        assert delete_resp.status_code == 204, (
            f"Expected 204, got {delete_resp.status_code}: {delete_resp.text}"
        )

        # Step 3: Verify all sites now have category_id=NULL
        for s in site_store:
            assert s["category_id"] is None, (
                f"Site {s['id']} should have category_id=None after category "
                f"deletion, but got category_id={s['category_id']}"
            )

        # Step 4: Verify all contracts now have category_id=NULL
        for c in contract_store:
            assert c["category_id"] is None, (
                f"Contract {c['id']} should have category_id=None after category "
                f"deletion, but got category_id={c['category_id']}"
            )

        # Cleanup
        app.dependency_overrides.clear()


# ===========================================================================
# Property 11: カテゴリ追加の即時反映 (Task 2.6)
# ===========================================================================

class TestCategoryImmediateReflection:
    """
    Property 11: カテゴリ追加の即時反映

    For any newly created category, the category list API should immediately
    include that category, and its id should be a valid integer that can be
    used as a category_id for sites and contract conditions.

    Feature: hierarchical-ui-restructure, Property 11: カテゴリ追加の即時反映
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        name=category_name_strategy,
        description=category_description_strategy,
        color=category_color_strategy,
    )
    def test_property_category_immediate_reflection(
        self,
        name: str,
        description,
        color,
    ):
        """
        Property 11: カテゴリ追加の即時反映

        任意の新規カテゴリが作成された場合、カテゴリ一覧APIの結果に
        当該カテゴリが含まれ、サイトおよび契約条件の分類先として
        選択可能であること。

        **Validates: Requirements 7.3**
        """
        app = _make_app()
        db = _make_mock_db_for_roundtrip()

        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app, headers={"X-API-Key": "dev-api-key"})

        # Step 1: Create a category via POST
        payload = {"name": name}
        if description is not None:
            payload["description"] = description
        if color is not None:
            payload["color"] = color

        create_response = client.post("/api/categories/", json=payload)

        assert create_response.status_code == 201, (
            f"Expected 201 for category creation, "
            f"got {create_response.status_code}: {create_response.text}"
        )

        created = create_response.json()
        created_id = created["id"]

        # Step 2: Immediately retrieve the category list via GET
        list_response = client.get("/api/categories/")

        assert list_response.status_code == 200, (
            f"Expected 200 for category listing, "
            f"got {list_response.status_code}: {list_response.text}"
        )

        categories = list_response.json()

        # Step 3: Assert the newly created category appears in the list
        matching = [c for c in categories if c["id"] == created_id]
        assert len(matching) == 1, (
            f"Newly created category (id={created_id}) should appear "
            f"exactly once in the category list, but found {len(matching)} "
            f"matches in {[c['id'] for c in categories]}"
        )

        found = matching[0]
        assert found["name"] == name, (
            f"Category name mismatch: expected {name!r}, got {found['name']!r}"
        )

        # Step 4: Assert the category id is a valid integer usable as
        # category_id for sites and contract conditions
        assert isinstance(created_id, int), (
            f"Category id should be an integer, got {type(created_id).__name__}"
        )
        assert created_id > 0, (
            f"Category id should be a positive integer, got {created_id}"
        )

        # Cleanup
        app.dependency_overrides.clear()


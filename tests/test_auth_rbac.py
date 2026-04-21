"""
Property-based tests for RBAC permission checking.

Feature: user-auth-rbac
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.auth.rbac import Role, ROLE_PERMISSIONS, check_permission


# ---------------------------------------------------------------------------
# Property 12: RBAC パーミッションチェックの正当性
# Feature: user-auth-rbac, Property 12: RBAC パーミッションチェックの正当性
# **Validates: Requirements 4.2, 4.3, 4.4, 4.5**
# ---------------------------------------------------------------------------

# Realistic API paths for testing
API_PATHS = st.sampled_from([
    "/api/sites/1",
    "/api/sites/",
    "/api/alerts/5",
    "/api/monitoring/status",
    "/api/verification/10",
    "/api/extracted-data/3",
    "/api/crawl/start",
    "/api/categories/2",
    "/api/customers/1",
    "/api/contracts/7",
    "/api/screenshots/4",
    "/api/audit-logs/",
    "/api/dark-patterns/1",
    "/api/users/1",
    "/api/users/",
    "/api/auth/me",
])

HTTP_METHODS = st.sampled_from(["GET", "POST", "PUT", "DELETE"])


class TestRBACPermissionCheck:
    """Property 12: admin always True, viewer GET-only True, reviewer per-definition."""

    @given(path=API_PATHS, method=HTTP_METHODS)
    @settings(max_examples=100)
    def test_admin_always_permitted(self, path: str, method: str):
        """Admin role has access to all endpoints with all methods."""
        assert check_permission(Role.ADMIN, path, method) is True

    @given(path=API_PATHS)
    @settings(max_examples=100)
    def test_viewer_get_permitted(self, path: str):
        """Viewer role can access any /api/* path with GET."""
        assert check_permission(Role.VIEWER, path, "GET") is True

    @given(
        path=API_PATHS,
        method=st.sampled_from(["POST", "PUT", "DELETE"]),
    )
    @settings(max_examples=100)
    def test_viewer_write_denied(self, path: str, method: str):
        """Viewer role cannot use write methods (POST/PUT/DELETE)."""
        assert check_permission(Role.VIEWER, path, method) is False

    @given(
        path=st.sampled_from([
            "/api/verification/10",
            "/api/verification/submit",
        ]),
    )
    @settings(max_examples=50)
    def test_reviewer_verification_post_allowed(self, path: str):
        """Reviewer can POST to verification endpoints (manual review)."""
        assert check_permission(Role.REVIEWER, path, "POST") is True

    @given(
        path=st.sampled_from([
            "/api/sites/1",
            "/api/alerts/5",
            "/api/monitoring/status",
            "/api/categories/2",
            "/api/customers/1",
            "/api/contracts/7",
        ]),
    )
    @settings(max_examples=50)
    def test_reviewer_get_allowed(self, path: str):
        """Reviewer can GET from allowed endpoints."""
        assert check_permission(Role.REVIEWER, path, "GET") is True

    @given(
        path=st.sampled_from([
            "/api/sites/1",
            "/api/alerts/5",
            "/api/customers/1",
            "/api/contracts/7",
        ]),
        method=st.sampled_from(["POST", "PUT", "DELETE"]),
    )
    @settings(max_examples=50)
    def test_reviewer_write_denied_on_readonly_endpoints(self, path: str, method: str):
        """Reviewer cannot write to endpoints that only allow GET."""
        assert check_permission(Role.REVIEWER, path, method) is False

    def test_reviewer_users_denied(self):
        """Reviewer cannot access user management endpoints."""
        assert check_permission(Role.REVIEWER, "/api/users/", "GET") is False
        assert check_permission(Role.REVIEWER, "/api/users/1", "POST") is False

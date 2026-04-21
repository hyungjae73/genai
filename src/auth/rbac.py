"""
Role-Based Access Control (RBAC) engine for Payment Compliance Monitor.

Defines roles, permission mappings, and the permission check function.
"""

import fnmatch
from enum import Enum
from typing import Dict, List


class Role(str, Enum):
    """User roles."""
    ADMIN = "admin"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


# Permission mapping: role -> { path_pattern: [allowed_methods] }
ROLE_PERMISSIONS: Dict[Role, Dict[str, List[str]]] = {
    Role.ADMIN: {
        "*": ["*"],  # all endpoints, all methods
    },
    Role.REVIEWER: {
        "/api/sites/*": ["GET"],
        "/api/alerts/*": ["GET"],
        "/api/monitoring/*": ["GET"],
        "/api/verification/*": ["GET", "POST"],  # manual review
        "/api/extracted-data/*": ["GET"],
        "/api/crawl/*": ["GET"],
        "/api/categories/*": ["GET"],
        "/api/customers/*": ["GET"],
        "/api/contracts/*": ["GET"],
        "/api/screenshots/*": ["GET"],
        "/api/audit-logs/*": ["GET"],
        "/api/dark-patterns/*": ["GET"],
    },
    Role.VIEWER: {
        "/api/*": ["GET"],  # all endpoints, GET only
    },
}


def check_permission(role: Role, path: str, method: str) -> bool:
    """Check whether a role is allowed to access a path with a given HTTP method.

    Args:
        role: The user's role.
        path: The request path (e.g. "/api/sites/1").
        method: The HTTP method (e.g. "GET", "POST").

    Returns:
        True if the role is permitted, False otherwise.
    """
    method = method.upper()
    permissions = ROLE_PERMISSIONS.get(role, {})

    for pattern, allowed_methods in permissions.items():
        if "*" in allowed_methods or method in allowed_methods:
            if pattern == "*" or fnmatch.fnmatch(path, pattern):
                return True

    return False

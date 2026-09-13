"""RBAC policy definitions for Arca Bench (ADR-009)."""

ROLES = {
    "bench_admin": ["read", "write", "execute", "delete", "admin"],
    "bench_runner": ["read", "write", "execute"],
    "bench_reader": ["read"],
}


def role_has_permission(role: str, permission: str) -> bool:
    return permission in ROLES.get(role, [])


def user_has_role(user: dict, role: str) -> bool:
    return role in user.get("roles", [])

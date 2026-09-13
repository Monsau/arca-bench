# OPA/Rego policy example for Arca Bench (ADR-009).
# The production enforcement path is currently implemented in Python
# (src/core/security/jwt.py, src/policies/rbac.py, src/policies/abac.py)
# while this file documents the policy-as-code contract.

package arca.bench

# Roles and permissions
roles := {
    "bench_admin": ["read", "write", "execute", "delete", "admin"],
    "bench_runner": ["read", "write", "execute"],
    "bench_reader": ["read"]
}

# Default deny
default allow := false

# Allow if the user has a role granting the requested permission
allow if {
    some role in input.user.roles
    role in roles
    some perm in roles[role]
    perm == input.permission
}

# ABAC: deny if the user's allowed_targets list is present and excludes the target
deny_abac if {
    input.user.allowed_targets
    not input.target in input.user.allowed_targets
}

allow if {
    allow
    not deny_abac
}

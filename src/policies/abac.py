"""ABAC policy helpers for Arca Bench (ADR-009)."""


def can_access_target(user: dict, target: str) -> bool:
    allowed = user.get("allowed_targets")
    if allowed is None:
        return True
    return target in allowed


def can_run_in_environment(user: dict, environment: str) -> bool:
    allowed = user.get("allowed_environments")
    if allowed is None:
        return True
    return environment in allowed

"""Vault integration: dynamic secrets and PKI via the External Secrets Operator."""
from ..config import settings


def vault_client():
    """Return a Vault client configured from settings.vault_addr, or None.

    In Kubernetes, secrets are injected by the External Secrets Operator;
    this client is only used for dynamic secrets / PKI flows.
    """
    if not settings.vault_addr:
        return None
    raise NotImplementedError("Vault client wiring lands with the platform profile")

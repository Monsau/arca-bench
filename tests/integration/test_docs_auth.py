"""Security: /docs, /redoc and /openapi.json are anonymous API-surface
disclosure on the direct ingress.

Zero Trust / defense-in-depth: outside dev/standalone these metadata
endpoints require a valid Keycloak JWT through the module JWKS/RS256 stack
(ADR-009); in dev they stay open (module dev-gate convention). Health
endpoints stay open for k8s probes. Tests mint real RS256 tokens so they
exercise the same strict validation path as production (no bypass).
"""
import os

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

os.environ.setdefault("BENCH_OIDC_ISSUER", "https://idp.test/realms/test")
os.environ.setdefault("BENCH_OIDC_AUDIENCE", "arca-bench")
os.environ.setdefault("BENCH_OIDC_JWKS_URL", "test-jwks")

from src.config import settings  # noqa: E402
from src.main import app  # noqa: E402
from src.core.security import jwt as bench_jwt  # noqa: E402
from tests.oidc_test_utils import (  # noqa: E402
    generate_keypair,
    install_test_jwks,
    mint_test_token,
)

_PRIVATE_KEY, _ = generate_keypair()

client = TestClient(app)

DOCS_PATHS = ("/openapi.json", "/docs", "/redoc")


@pytest.fixture
def docs_key():
    """Install this module's test key in the JWKS cache for the duration of
    a test, then restore the previous entry (test_api.py uses the same cache
    slot with its own key)."""
    previous = bench_jwt.JWKS_CACHE.get("test-jwks")
    install_test_jwks(_PRIVATE_KEY)
    yield
    if previous is None:
        bench_jwt.JWKS_CACHE.pop("test-jwks", None)
    else:
        bench_jwt.JWKS_CACHE["test-jwks"] = previous


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")


@pytest.fixture
def dev(monkeypatch):
    monkeypatch.setattr(settings, "environment", "dev")


def _auth_headers() -> dict:
    token = mint_test_token(_PRIVATE_KEY, "docs-tester", ["bench_reader"])
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("path", DOCS_PATHS)
def test_metadata_anonymous_is_rejected_in_production(path, production, docs_key):
    response = client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize("path", DOCS_PATHS)
def test_metadata_invalid_token_is_rejected_in_production(path, production, docs_key):
    response = client.get(path, headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


@pytest.mark.parametrize("path", DOCS_PATHS)
def test_metadata_valid_token_is_served_in_production(path, production, docs_key):
    response = client.get(path, headers=_auth_headers())
    assert response.status_code == 200


def test_openapi_schema_content_served_with_token_in_production(production, docs_key):
    response = client.get("/openapi.json", headers=_auth_headers())
    assert response.status_code == 200
    assert response.json()["info"]["title"] == settings.app_name


@pytest.mark.parametrize("path", DOCS_PATHS)
def test_metadata_stays_open_in_dev(path, dev, docs_key):
    response = client.get(path)
    assert response.status_code == 200


def test_health_stays_open_in_production(production, docs_key):
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200

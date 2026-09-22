"""OIDC/JWT security layer (ADR-009).

Security by design: only asymmetric RS256 tokens verified against the
configured Keycloak realm JWKS are accepted. Configure:

- BENCH_OIDC_JWKS_URL   in-cluster Keycloak JWKS (the public issuer URL does
                        not resolve inside the cluster, so discovery is not
                        used by default)
- BENCH_OIDC_ISSUER     expected token issuer (optional but recommended)
- BENCH_OIDC_AUDIENCE   expected audience (default: arca-bench)

The Suite portal injects the user's SSO access token on every call. There
is no symmetric fallback and no auth bypass.
"""
import os
from functools import wraps

import httpx
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

JWKS_CACHE: dict = {}


def _jwks_url() -> str | None:
    return os.environ.get("BENCH_OIDC_JWKS_URL") or None


def _fetch_jwks(url: str) -> dict:
    if url in JWKS_CACHE:
        return JWKS_CACHE[url]
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        jwks = resp.json()
        JWKS_CACHE[url] = jwks
        return jwks
    except Exception as exc:
        raise HTTPException(status_code=503,
                            detail=f"Unable to fetch JWKS: {exc}")


def _get_signing_key(token: str, jwks: dict):
    unverified = jwt.get_unverified_header(token)
    if unverified.get("alg") != "RS256":
        raise HTTPException(status_code=401,
                            detail=f"Unsupported algorithm {unverified.get('alg')}")
    kid = unverified.get("kid")
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    raise HTTPException(status_code=401, detail="Signing key not found")


def _audience() -> str:
    return os.environ.get("BENCH_OIDC_AUDIENCE", "arca-bench")


def _issuer() -> str | None:
    return os.environ.get("BENCH_OIDC_ISSUER") or None


def verify_token(token: str) -> dict:
    jwks_url = _jwks_url()
    if not jwks_url:
        raise HTTPException(status_code=503,
                            detail="OIDC not configured: BENCH_OIDC_JWKS_URL is required")
    try:
        jwks = _fetch_jwks(jwks_url)
        key = _get_signing_key(token, jwks)
        return jwt.decode(token, key, algorithms=["RS256"],
                          audience=_audience(), issuer=_issuer())
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Invalid token: {exc}")


def _extract_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:]
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Missing or invalid Authorization header")


def get_current_user(request: Request) -> dict:
    return verify_token(_extract_token(request))


def require_role(*roles):
    def checker(user: dict = Depends(get_current_user)):
        user_roles = set(user.get("roles", []))
        if not any(r in user_roles for r in roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Insufficient role")
        return user
    return checker


def require_permission(permission: str):
    def checker(user: dict = Depends(get_current_user)):
        perms = set(user.get("permissions", []))
        if permission not in perms:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Insufficient permission")
        return user
    return checker

"""OIDC/JWT security layer (ADR-009).

Supports two verification modes:
- OIDC JWKS: configure BENCH_OIDC_JWKS_URL to fetch RSA/EC keys.
- Shared-secret HS256: configure BENCH_JWT_SECRET for dev/tests.
- Disable: set BENCH_AUTH_DISABLED=1 for local integration tests.
"""
import os
from functools import wraps

import httpx
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

JWKS_CACHE: dict = {}


def _auth_disabled() -> bool:
    return os.environ.get("BENCH_AUTH_DISABLED", "").lower() in ("1", "true", "yes")


def _jwt_secret() -> str | None:
    return os.environ.get("BENCH_JWT_SECRET") or None


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
    kid = unverified.get("kid")
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    raise HTTPException(status_code=401, detail="Signing key not found")


def verify_token(token: str) -> dict:
    if _auth_disabled():
        return {"sub": "anonymous", "roles": ["bench_admin"]}
    secret = _jwt_secret()
    jwks_url = _jwks_url()
    try:
        if secret:
            return jwt.decode(token, secret, algorithms=["HS256"],
                              audience="arca-bench")
        if jwks_url:
            jwks = _fetch_jwks(jwks_url)
            key = _get_signing_key(token, jwks)
            return jwt.decode(token, key, algorithms=[key.get("alg", "RS256")],
                              audience="arca-bench")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail=f"Invalid token: {exc}")
    raise HTTPException(status_code=500,
                        detail="No JWT verifier configured")


def _extract_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:]
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Missing or invalid Authorization header")


def get_current_user(request: Request) -> dict:
    if _auth_disabled():
        return {"sub": "anonymous", "roles": ["bench_admin"]}
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


def create_access_token(data: dict, secret: str,
                        algorithm: str = "HS256") -> str:
    return jwt.encode(data, secret, algorithm=algorithm)

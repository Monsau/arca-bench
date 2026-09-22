"""Test utilities: generate an RSA keypair, publish it as a JWKS and mint
RS256 access tokens, so tests exercise the same strict OIDC validation path
as production (no bypass)."""
from __future__ import annotations

import base64
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt

TEST_ISSUER = "https://idp.test/realms/test"
TEST_AUDIENCE = "arca-bench"
TEST_KID = "test-key"


def _b64_int(n: int) -> str:
    data = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def generate_keypair() -> tuple[rsa.RSAPrivateKey, dict]:
    """Return (private_key, public_jwk_dict) for RS256 test tokens."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": TEST_KID,
        "n": _b64_int(numbers.n),
        "e": _b64_int(numbers.e),
    }
    return private_key, jwk


def private_pem(private_key: rsa.RSAPrivateKey) -> bytes:
    return private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def mint_test_token(private_key: rsa.RSAPrivateKey, sub: str,
                    roles: list[str], expires_in: int = 3600) -> str:
    """Sign an RS256 access token carrying the realm roles claim."""
    now = int(time.time())
    return jose_jwt.encode(
        {
            "sub": sub,
            "email": f"{sub}@test.local",
            "iss": TEST_ISSUER,
            "aud": TEST_AUDIENCE,
            "iat": now,
            "exp": now + expires_in,
            "roles": roles,
        },
        private_pem(private_key),
        algorithm="RS256",
        headers={"kid": TEST_KID},
    )


def install_test_jwks(private_key: rsa.RSAPrivateKey) -> None:
    """Register the test public key in the bench JWKS cache."""
    from src.core.security import jwt as bench_jwt

    _, jwk = generate_keypair()
    numbers = private_key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": TEST_KID,
        "n": _b64_int(numbers.n),
        "e": _b64_int(numbers.e),
    }
    bench_jwt.JWKS_CACHE["test-jwks"] = {"keys": [jwk]}

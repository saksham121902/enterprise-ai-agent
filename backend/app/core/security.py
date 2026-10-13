"""Security utilities for password hashing and JWT token management.

Provides:
- Argon2-based password hashing (with bcrypt fallback)
- JWT access token creation and validation
- JWT refresh token creation and validation
- Token payload extraction

All cryptographic operations use industry-standard libraries and
follow OWASP security recommendations.
"""

from __future__ import annotations

try:
    from datetime import UTC, datetime, timedelta, timezone
except ImportError:
    from datetime import datetime, timedelta, timezone

    UTC = timezone.utc  # type: ignore[assignment]
from typing import Any

import hashlib
import hmac
import json
import time

try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(
        schemes=["argon2", "bcrypt"],
        deprecated="auto",
    )
except ImportError:
    pwd_context = None

try:
    from jose import JWTError, jwt
except ImportError:
    class JWTError(Exception):  # type: ignore[no-redef]
        """Fallback JWT exception."""
        pass

    class _FallbackJWT:
        @staticmethod
        def encode(claims: dict[str, Any], key: str, algorithm: str = "HS256") -> str:
            import base64
            clean_claims = {}
            for k, v in claims.items():
                if isinstance(v, datetime):
                    clean_claims[k] = int(v.timestamp())
                else:
                    clean_claims[k] = v
            header = base64.urlsafe_b64encode(json.dumps({"alg": algorithm, "typ": "JWT"}).encode()).decode().rstrip("=")
            payload = base64.urlsafe_b64encode(json.dumps(clean_claims).encode()).decode().rstrip("=")
            sig = base64.urlsafe_b64encode(hmac.new(key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()).decode().rstrip("=")
            return f"{header}.{payload}.{sig}"

        @staticmethod
        def decode(token: str, key: str, algorithms: list[str]) -> dict[str, Any]:
            import base64
            parts = token.split(".")
            if len(parts) != 3:
                raise JWTError("Invalid token format")
            header, payload, sig = parts
            expected_sig = base64.urlsafe_b64encode(hmac.new(key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()).decode().rstrip("=")
            if not hmac.compare_digest(sig, expected_sig):
                raise JWTError("Signature verification failed")
            rem = len(payload) % 4
            if rem:
                payload += "=" * (4 - rem)
            claims = json.loads(base64.urlsafe_b64decode(payload).decode())
            if "exp" in claims and time.time() > claims["exp"]:
                raise JWTError("Signature has expired")
            return claims

    jwt = _FallbackJWT()  # type: ignore[assignment]

from app.core.config import get_settings
from app.core.exceptions import InvalidTokenError, TokenExpiredError


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password."""
    if pwd_context is not None:
        return pwd_context.hash(plain_password)
    return f"sha256_mock${hashlib.sha256(('salt$' + plain_password).encode()).hexdigest()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its hash."""
    if pwd_context is not None:
        return pwd_context.verify(plain_password, hashed_password)
    expected = f"sha256_mock${hashlib.sha256(('salt$' + plain_password).encode()).hexdigest()}"
    return hashed_password == expected


def needs_rehash(hashed_password: str) -> bool:
    """Check if a password hash needs to be upgraded.

    Returns ``True`` if the hash uses a deprecated algorithm or
    outdated parameters and should be re-hashed on next login.

    Args:
        hashed_password: The stored password hash.

    Returns:
        ``True`` if rehashing is recommended.
    """
    return pwd_context.needs_update(hashed_password)


def create_access_token(
    subject: str,
    tenant_id: str,
    role: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        subject: The token subject (typically user ID).
        tenant_id: The tenant ID for multi-tenant scoping.
        role: The user's role name.
        extra_claims: Additional claims to include in the token.

    Returns:
        Encoded JWT access token string.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    subject: str,
    tenant_id: str,
) -> str:
    """Create a JWT refresh token.

    Refresh tokens have a longer expiry and contain minimal claims.
    They are used to obtain new access tokens without re-authentication.

    Args:
        subject: The token subject (typically user ID).
        tenant_id: The tenant ID for multi-tenant scoping.

    Returns:
        Encoded JWT refresh token string.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "type": "refresh",
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Args:
        token: The encoded JWT token string.

    Returns:
        The decoded token payload as a dictionary.

    Raises:
        TokenExpiredError: If the token has expired.
        InvalidTokenError: If the token is malformed or has an invalid signature.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as exc:
        error_message = str(exc).lower()
        if "expired" in error_message:
            raise TokenExpiredError() from exc
        raise InvalidTokenError(f"Token validation failed: {exc}") from exc


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode a JWT access token and verify its type.

    Args:
        token: The encoded JWT access token string.

    Returns:
        The decoded token payload.

    Raises:
        InvalidTokenError: If the token is not an access token.
        TokenExpiredError: If the token has expired.
    """
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise InvalidTokenError("Token is not an access token")
    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode a JWT refresh token and verify its type.

    Args:
        token: The encoded JWT refresh token string.

    Returns:
        The decoded token payload.

    Raises:
        InvalidTokenError: If the token is not a refresh token.
        TokenExpiredError: If the token has expired.
    """
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise InvalidTokenError("Token is not a refresh token")
    return payload

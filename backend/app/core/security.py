"""
Cryptographic utilities for password hashing and JWT management.

This module is the single source of truth for all security-sensitive
operations in the application:

- **bcrypt hashing** — used for both user passwords and 4-digit operator PINs.
  A shared helper ``_validate_bcrypt_input_length`` enforces the 72-byte bcrypt
  limit before hashing to prevent silent truncation attacks.

- **JWT creation and decoding** — two distinct token types are issued, each
  validated by a ``token_use`` claim to prevent a valid organisation token from
  being accepted on an establishment endpoint and vice versa.

All functions are pure and stateless; they do not interact with the database.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from jwt import InvalidTokenError

from app.core.config import settings


def _validate_bcrypt_input_length(secret: str) -> bytes:
    """Encode a string to UTF-8 and enforce the 72-byte bcrypt input limit.

    bcrypt silently truncates inputs longer than 72 bytes, which means two
    passwords that share the same first 72 bytes would produce the same hash.
    This helper raises early to make the truncation behaviour explicit.

    Args:
        secret (str): The plain-text password or PIN to encode.

    Returns:
        bytes: The UTF-8 encoded bytes if the length is within the limit.

    Raises:
        ValueError: If the encoded secret exceeds 72 bytes.
    """
    secret_bytes = secret.encode("utf-8")
    if len(secret_bytes) > 72:
        raise ValueError("bcrypt secrets must not exceed 72 bytes.")
    return secret_bytes


def verify_password(plain: str, hashed: str) -> bool:
    """Compare a plain-text value against a stored bcrypt hash.

    Used for both manager passwords and operator PIN codes.  Returns ``False``
    for any error (wrong password, malformed hash, length violation) rather
    than propagating exceptions, making it safe to call in authentication flows
    without leaking error details to callers.

    Args:
        plain (str): The plain-text value to verify (password or PIN).
        hashed (str): The bcrypt hash stored in the database.

    Returns:
        bool: ``True`` if the plain-text value matches the hash, ``False``
            for any mismatch or error.
    """
    try:
        plain_bytes = _validate_bcrypt_input_length(plain)
        hashed_bytes = hashed.encode("utf-8")
        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except ValueError:
        return False


def get_password_hash(password: str) -> str:
    """Hash a password or PIN with bcrypt before database storage.

    A new random salt is generated for every call, so the same password will
    produce different hashes on repeated calls.

    Args:
        password (str): The plain-text password or PIN to hash.

    Returns:
        str: The bcrypt hash string suitable for storage in the database.

    Raises:
        ValueError: If the password exceeds 72 bytes after UTF-8 encoding.
    """
    password_bytes = _validate_bcrypt_input_length(password)
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def create_establishment_access_token(data: dict[str, Any]) -> str:
    """Create the long-lived JWT that locks a shared device to one establishment.

    The ``token_use`` claim is set to ``"establishment_access"`` and verified
    during decoding to prevent an organisation supervision token from being
    accepted on establishment-scoped endpoints.

    Args:
        data (dict[str, Any]): Custom claims to embed in the token payload.
            Must include ``etablissement_id``, ``organisation_id``, and
            ``utilisateur_id`` at minimum.

    Returns:
        str: A signed JWT string.
    """
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.ESTABLISHMENT_ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        **data,
        "token_use": "establishment_access",
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_establishment_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an establishment JWT.

    Validates the signature, expiration, and ``token_use`` claim.

    Args:
        token (str): The raw JWT string from the ``Authorization`` header.

    Returns:
        dict[str, Any]: The decoded token payload.

    Raises:
        ValueError: If the token is expired, has an invalid signature, or
            carries the wrong ``token_use`` claim.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired establishment token.") from exc

    if payload.get("token_use") != "establishment_access":
        raise ValueError("Invalid token purpose.")

    return payload


def create_organisation_access_token(data: dict[str, Any]) -> str:
    """Create a JWT for organisation-wide supervision access.

    Identical structure to the establishment token but carries
    ``token_use = "organisation_access"`` to prevent cross-context reuse.

    Args:
        data (dict[str, Any]): Custom claims. Must include ``organisation_id``.

    Returns:
        str: A signed JWT string.
    """
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=settings.ESTABLISHMENT_ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        **data,
        "token_use": "organisation_access",
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_organisation_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an organisation supervision JWT.

    Args:
        token (str): The raw JWT string from the ``Authorization`` header.

    Returns:
        dict[str, Any]: The decoded token payload.

    Raises:
        ValueError: If the token is expired, has an invalid signature, or
            carries the wrong ``token_use`` claim.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired organisation token.") from exc

    if payload.get("token_use") != "organisation_access":
        raise ValueError("Invalid token purpose.")

    return payload

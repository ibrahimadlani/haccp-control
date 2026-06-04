"""Unit tests for app/core/security.py — JWT and bcrypt utilities."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    _validate_bcrypt_input_length,
    create_establishment_access_token,
    create_organisation_access_token,
    decode_establishment_access_token,
    decode_organisation_access_token,
    get_password_hash,
    verify_password,
)


# ── bcrypt ─────────────────────────────────────────────────────────────────────


def test_get_password_hash_returns_string():
    result = get_password_hash("secret123")
    assert isinstance(result, str)
    assert result.startswith("$2b$")


def test_get_password_hash_different_salts():
    h1 = get_password_hash("password")
    h2 = get_password_hash("password")
    assert h1 != h2


def test_verify_password_correct():
    hashed = get_password_hash("correct_password")
    assert verify_password("correct_password", hashed) is True


def test_verify_password_wrong():
    hashed = get_password_hash("correct_password")
    assert verify_password("wrong_password", hashed) is False


def test_verify_password_returns_false_on_overlong_input():
    # Input > 72 bytes must return False, not raise
    long_password = "a" * 73
    hashed = get_password_hash("a" * 10)
    assert verify_password(long_password, hashed) is False


def test_validate_bcrypt_input_length_raises_on_overlong():
    with pytest.raises(ValueError, match="72 bytes"):
        _validate_bcrypt_input_length("a" * 73)


def test_validate_bcrypt_input_length_accepts_exactly_72_bytes():
    result = _validate_bcrypt_input_length("a" * 72)
    assert len(result) == 72


def test_verify_password_with_empty_string():
    hashed = get_password_hash("something")
    assert verify_password("", hashed) is False


# ── Establishment JWT ──────────────────────────────────────────────────────────


def test_create_and_decode_establishment_token_round_trip():
    data = {
        "etablissement_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "organisation_id": "11111111-2222-3333-4444-555555555555",
        "utilisateur_id": "ffffffff-aaaa-bbbb-cccc-dddddddddddd",
    }
    token = create_establishment_access_token(data)
    payload = decode_establishment_access_token(token)

    assert payload["etablissement_id"] == data["etablissement_id"]
    assert payload["token_use"] == "establishment_access"


def test_decode_establishment_token_rejects_wrong_token_use():
    # Forge a token with wrong token_use
    payload = {
        "token_use": "organisation_access",  # wrong
        "etablissement_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    bad_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(ValueError, match="Invalid token purpose"):
        decode_establishment_access_token(bad_token)


def test_decode_establishment_token_rejects_expired():
    payload = {
        "token_use": "establishment_access",
        "etablissement_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "iat": datetime.now(UTC) - timedelta(hours=25),
        "exp": datetime.now(UTC) - timedelta(hours=1),  # expired
    }
    expired_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    with pytest.raises(ValueError):
        decode_establishment_access_token(expired_token)


def test_decode_establishment_token_rejects_tampered_signature():
    token = create_establishment_access_token({"etablissement_id": "x"})
    tampered = token[:-4] + "xxxx"

    with pytest.raises(ValueError):
        decode_establishment_access_token(tampered)


# ── Organisation JWT ───────────────────────────────────────────────────────────


def test_create_and_decode_organisation_token_round_trip():
    data = {"organisation_id": "11111111-2222-3333-4444-555555555555"}
    token = create_organisation_access_token(data)
    payload = decode_organisation_access_token(token)

    assert payload["organisation_id"] == data["organisation_id"]
    assert payload["token_use"] == "organisation_access"


def test_decode_organisation_token_rejects_establishment_token():
    # An establishment token must not be accepted on the organisation endpoint
    establishment_token = create_establishment_access_token({
        "etablissement_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    })

    with pytest.raises(ValueError, match="Invalid token purpose"):
        decode_organisation_access_token(establishment_token)


def test_decode_establishment_token_rejects_organisation_token():
    org_token = create_organisation_access_token({"organisation_id": "x"})

    with pytest.raises(ValueError, match="Invalid token purpose"):
        decode_establishment_access_token(org_token)

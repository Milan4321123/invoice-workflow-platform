from datetime import timedelta

import pytest
from fastapi import HTTPException

from services.auth_service import auth_service


def test_password_hash_roundtrip():
    hashed = auth_service.get_password_hash("Sicheres-Passwort-2025")
    assert hashed != "Sicheres-Passwort-2025"
    assert auth_service.verify_password("Sicheres-Passwort-2025", hashed)
    assert not auth_service.verify_password("falsch", hashed)


def test_token_roundtrip():
    token = auth_service.create_access_token({"sub": "anna"})
    assert auth_service.verify_token(token)["sub"] == "anna"


def test_expired_token_is_rejected():
    token = auth_service.create_access_token({"sub": "anna"}, expires_delta=timedelta(seconds=-1))
    with pytest.raises(HTTPException) as exc:
        auth_service.verify_token(token)
    assert exc.value.status_code == 401


def test_token_without_subject_is_rejected():
    token = auth_service.create_access_token({"role": "admin"})
    with pytest.raises(HTTPException):
        auth_service.verify_token(token)


def test_tampered_token_is_rejected():
    token = auth_service.create_access_token({"sub": "anna"})
    with pytest.raises(HTTPException):
        auth_service.verify_token(token[:-2] + ("aa" if not token.endswith("aa") else "bb"))

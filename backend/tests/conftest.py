"""
Shared test setup.

Tests never touch Supabase or SendGrid: the variables below are set before any
app module is imported, and python-dotenv does not override variables that
already exist, so a developer's local .env cannot leak into a test run.
"""
import os

_TEST_ENV = {
    "SUPA_URL": "",
    "SUPA_KEY": "",
    "SUPA_SERVICE_ROLE_KEY": "",
    "SUPABASE_URL": "",
    "SUPABASE_SERVICE_ROLE_KEY": "",
    "SUPABASE_ANON_KEY": "",
    "SENDGRID_API_KEY": "",
    "JWT_SECRET": "test-jwt-secret-with-enough-entropy-0123456789",
    "ACCOUNTING_EMAIL": "buchhaltung@example.com",
    "SKONTO_SCHEDULER_ENABLED": "false",
    "NODE_ENV": "test",
}
os.environ.update(_TEST_ENV)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture
def client():
    """HTTP client for the FastAPI app. Startup hooks don't run, so no DB checks."""
    from main import app

    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Bearer header for a user that the fake user lookup below accepts."""
    from services.auth_service import auth_service

    token = auth_service.create_access_token({"sub": "testuser"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def fake_user_lookup(monkeypatch):
    """Resolve any token subject to an active user without a database."""
    from services.auth_service import auth_service

    async def get_user_by_username(username):
        return {"id": "00000000-0000-0000-0000-000000000001", "username": username, "is_active": True}

    monkeypatch.setattr(auth_service, "get_user_by_username", get_user_by_username)

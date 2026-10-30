"""
Every API route must require a login unless it is listed here on purpose.

New routes are protected by default (see main.py). If this test fails for a
route you just added, protect it; only add it here if it truly must be public.
"""
import re

import pytest
from fastapi.routing import APIRoute

from main import app

PUBLIC_ROUTES = {
    ("GET", "/"),
    ("GET", "/api/"),
    ("GET", "/api/health"),
    # Login
    ("POST", "/api/auth/token"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/verify"),
    # Links in approval and Skonto e-mails; each carries a signed, expiring token
    ("GET", "/api/approval/{token}"),
    ("GET", "/api/api/approval/{token}"),
    ("GET", "/api/email/skonto-decision"),
    # Placeholder PDF for the demo storage mode
    ("GET", "/api/mock-storage/{filename}"),
}


def api_routes():
    for route in app.routes:
        if isinstance(route, APIRoute):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                yield method, route.path


def concrete(path):
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


def test_public_allowlist_has_no_stale_entries():
    assert PUBLIC_ROUTES <= set(api_routes())


@pytest.mark.parametrize("method, path", sorted(set(api_routes()) - PUBLIC_ROUTES))
def test_route_rejects_anonymous_requests(client, method, path):
    response = client.request(method, concrete(path))
    assert response.status_code in (401, 403), f"{method} {path} answered {response.status_code} without a login"

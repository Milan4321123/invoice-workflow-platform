"""Data subject requests and IP address retention."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from services.database import db_service
from services.privacy_service import ERASED, PrivacyService, subject_hash
from tests.fakes import FakeSupabase, FakeTable

EMAIL = "Bau_Leiter@Muster-Bau.de"
OLD = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
NEW = datetime.now(timezone.utc).isoformat()


@pytest.fixture
def fake():
    return FakeSupabase(
        users=FakeTable([
            {"id": "u1", "username": "bleiter", "email": "bau_leiter@muster-bau.de", "full_name": "Bea Leiter",
             "hashed_password": "$2b$secret", "is_active": True},
            {"id": "u2", "username": "other", "email": "bauXleiter@muster-bau.de", "full_name": "Not Her", "is_active": True},
        ]),
        invoices_clean=FakeTable([
            {"id": "i1", "status": "approved_by_bauleiter", "rechnungseingang": "2026-03-01",
             "bauleiter_email": "bau_leiter@muster-bau.de", "rechnungsbetrag": 1190},
        ]),
        email_audit_log=FakeTable([
            {"id": "e1", "recipient_email": "BAU_LEITER@muster-bau.de", "provider_response": {"id": "x"}},
        ]),
        approval_tokens=FakeTable([
            {"id": "t1", "user_email": "bau_leiter@muster-bau.de", "used_by_ip": "203.0.113.7", "created_at": OLD},
            {"id": "t2", "user_email": "other@muster-bau.de", "used_by_ip": "203.0.113.8", "created_at": NEW},
        ]),
        security_events=FakeTable([
            {"id": "s1", "user_email": "bau_leiter@muster-bau.de", "ip_address": "203.0.113.7", "created_at": OLD},
            {"id": "s2", "user_email": None, "ip_address": "198.51.100.1", "created_at": NEW},
        ]),
        invoice_audit_log=FakeTable([
            {"seq": 1, "invoice_id": "i1", "action": "approval_decided", "actor": "E-Mail-Link bau_leiter@muster-bau.de",
             "changes": {}, "recorded_at": NEW},
            {"seq": 2, "invoice_id": "i1", "action": "updated", "actor": "bleiter", "changes": {}, "recorded_at": NEW},
        ], append_only=True),
    )


@pytest.fixture
def service(fake):
    return PrivacyService(lambda: fake)


def test_access_finds_every_place_case_insensitively(service):
    data = service.subject_access(EMAIL)["kategorien"]
    assert len(data["Benutzerkonto"]) == 1                  # not "bauXleiter": _ is not a wildcard
    assert len(data["Rechnungen, an denen die Person beteiligt war"]) == 1
    assert len(data["Versandprotokoll der E-Mails"]) == 1
    assert len(data["Freigabe-Links"]) == 1
    assert len(data["Sicherheitsprotokoll"]) == 1
    assert len(data["Änderungsprotokoll (Aktionen der Person)"]) == 2


def test_access_never_includes_the_password_hash(service):
    assert "hashed_password" not in json.dumps(service.subject_access(EMAIL), default=str)


def test_erasure_pseudonymises_operational_data(service, fake):
    service.erase(EMAIL)
    user = fake.table("users").rows[0]
    assert (user["email"], user["full_name"], user["is_active"]) == (None, None, False)
    assert fake.table("users").rows[1]["email"] == "bauXleiter@muster-bau.de"
    assert fake.table("email_audit_log").rows[0] == {"id": "e1", "recipient_email": ERASED, "provider_response": None}
    assert fake.table("approval_tokens").rows[0]["user_email"] == ERASED
    assert fake.table("approval_tokens").rows[0]["used_by_ip"] is None
    assert fake.table("security_events").rows[0]["ip_address"] is None


def test_erasure_keeps_accounting_records_and_says_why(service, fake):
    report = service.erase(EMAIL)
    assert fake.table("invoices_clean").rows[0]["bauleiter_email"] == "bau_leiter@muster-bau.de"
    invoices = report["aufbewahrt"][0]
    assert invoices["aufbewahrt_bis"] == "2034-12-31"
    assert "Art. 17 Abs. 3 lit. b" in invoices["grund"]
    assert len(fake.table("invoice_audit_log").rows) == 2


def test_old_ip_addresses_are_removed(service, fake):
    removed = service.remove_old_ip_addresses(older_than_days=30)
    assert removed == {"security_events": 1, "approval_tokens": 1}
    assert fake.table("security_events").rows[1]["ip_address"] == "198.51.100.1"
    assert fake.table("approval_tokens").rows[1]["used_by_ip"] == "203.0.113.8"


# --- API --------------------------------------------------------------------

@pytest.fixture
def api_db(monkeypatch, fake):
    monkeypatch.setattr(db_service, "_client", fake)
    return fake


def test_access_download(client, auth_headers, api_db):
    response = client.get("/api/privacy/subject-access", params={"email": EMAIL}, headers=auth_headers)
    assert response.status_code == 200
    assert "dsgvo-auskunft.json" in response.headers["content-disposition"]
    assert response.json()["rechtsgrundlage"] == "Art. 15 und Art. 20 DSGVO"


def test_requests_are_recorded_without_the_address(client, auth_headers, api_db):
    client.get("/api/privacy/subject-access", params={"email": EMAIL}, headers=auth_headers)
    event = api_db.table("security_events").rows[-1]
    assert event["event_type"] == "dsgvo_subject_access"
    assert json.loads(event["event_data"]) == {"subject": subject_hash(EMAIL), "handled_by": "testuser"}
    assert EMAIL.lower() not in json.dumps(event).lower()


def test_erasure_needs_confirmation(client, auth_headers, api_db):
    response = client.post("/api/privacy/erasure", json={"email": EMAIL}, headers=auth_headers)
    assert response.status_code == 400
    assert api_db.table("users").rows[0]["email"] is not None


def test_erasure_endpoint(client, auth_headers, api_db):
    response = client.post("/api/privacy/erasure", json={"email": EMAIL, "confirm": True}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["geloescht"]["Versandprotokoll der E-Mails"] == 1

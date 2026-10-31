"""Site manager approvals from the dashboard."""
import pytest

from services.database import db_service
from services.demo_data import seed
from services.in_memory_supabase import FakeSupabase


@pytest.fixture
def demo_db(monkeypatch):
    monkeypatch.setattr(db_service, "_client", FakeSupabase())
    seed(db_service)
    return db_service


def wagner(db):
    return next(r for r in db.client.table("invoices_clean").rows if "Wagner" in r["file_name"])


def test_pending_list_shows_invoices_waiting_for_approval(client, auth_headers, demo_db):
    body = client.get("/api/invoices/pending-approval", headers=auth_headers).json()
    assert [i["file_name"] for i in body["pending_approvals"]] == ["20261022_OMEGA_HEIZUNG_Wagner.pdf"]
    assert body["pending_approvals"][0]["projekt_label"] == "Wohnanlage Omega"


def test_approval_records_who_how_and_why(client, auth_headers, demo_db):
    invoice = wagner(demo_db)
    response = client.put(f"/api/invoices/{invoice['id']}/approve", headers=auth_headers,
                          json={"notes": "Leistung abgenommen", "decided_by": "jemand-anderes"})
    assert response.status_code == 200
    row = wagner(demo_db)
    assert row["status"] == "approved_by_bauleiter"
    assert row["reviewed_by"] == "testuser"            # from the login, not the request body
    assert row["approval_method"] == "dashboard"
    assert row["review_notes"] == "Leistung abgenommen"
    entry = demo_db.client.table("invoice_audit_log").rows[-1]
    assert (entry["actor"], entry["action"]) == ("testuser", "approval_decided")


def test_rejection_needs_a_reason(client, auth_headers, demo_db):
    invoice = wagner(demo_db)
    assert client.put(f"/api/invoices/{invoice['id']}/reject", headers=auth_headers, json={}).status_code == 400
    response = client.put(f"/api/invoices/{invoice['id']}/reject", headers=auth_headers,
                          json={"notes": "Montage im 2. OG fehlt noch"})
    assert response.status_code == 200
    assert wagner(demo_db)["review_notes"] == "Montage im 2. OG fehlt noch"

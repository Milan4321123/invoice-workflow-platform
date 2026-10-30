"""GoBD behaviour end to end: API -> DatabaseService -> (fake) Supabase."""
import csv
import io
import zipfile

import pytest

from services.database import db_service
from tests.fakes import FakeSupabase, FakeTable

APPROVED = "11111111-1111-1111-1111-111111111111"
EDITED = "22222222-2222-2222-2222-222222222222"
UPLOADED = "33333333-3333-3333-3333-333333333333"


def invoice(id, status, **fields):
    return {"id": id, "status": status, "file_name": f"{status}.pdf", "file_path": None,
            "rechnungseingang": "2026-10-01", "created_at": "2026-10-01T08:00:00+00:00",
            "rechnungsbetrag": 1190, "rechnungssteller": "Elektro Müller GmbH", **fields}


@pytest.fixture
def db(monkeypatch):
    fake = FakeSupabase(
        invoices_clean=FakeTable([invoice(APPROVED, "approved_by_bauleiter"),
                                  invoice(EDITED, "edited"),
                                  invoice(UPLOADED, "uploaded")]),
        invoice_audit_log=FakeTable(unique=("seq", "entry_hash"), append_only=True),
    )
    monkeypatch.setattr(db_service, "_client", fake)
    return fake


def audit_rows(db):
    return db.table("invoice_audit_log").rows


def save_editor(client, headers, invoice_id, **fields):
    return client.put(f"/api/invoices/{invoice_id}/editor", headers=headers, json={"fields": fields})


def test_edit_is_logged_with_user_and_old_value(client, auth_headers, db):
    response = save_editor(client, auth_headers, EDITED, rechnungsbetrag=1200)
    assert response.status_code == 200, response.text

    entry = next(row for row in audit_rows(db) if row["action"] == "updated")
    assert entry["actor"] == "testuser"
    assert entry["changes"]["rechnungsbetrag"] == {"old": 1190, "new": 1200}


def test_approved_invoice_amount_cannot_change(client, auth_headers, db):
    response = save_editor(client, auth_headers, APPROVED, rechnungsbetrag=1100)
    assert response.status_code == 409
    assert "festgeschrieben" in response.json()["detail"]
    assert db.table("invoices_clean").rows[0]["rechnungsbetrag"] == 1190
    assert audit_rows(db) == []


def test_saving_approved_invoice_does_not_reopen_it(client, auth_headers, db):
    response = save_editor(client, auth_headers, APPROVED, rechnungsbetrag=1190)
    assert response.status_code == 409
    assert db.table("invoices_clean").rows[0]["status"] == "approved_by_bauleiter"


def test_record_in_workflow_cannot_be_deleted(client, auth_headers, db):
    response = client.delete(f"/api/invoices/{EDITED}", headers=auth_headers)
    assert response.status_code == 409
    assert "31.12.2034" in response.json()["detail"]
    assert len(db.table("invoices_clean").rows) == 3


def test_mistaken_upload_can_be_deleted_and_the_deletion_is_logged(client, auth_headers, db):
    response = client.delete(f"/api/invoices/{UPLOADED}", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert [row["id"] for row in db.table("invoices_clean").rows] == [APPROVED, EDITED]
    entry = audit_rows(db)[-1]
    assert (entry["invoice_id"], entry["action"]) == (UPLOADED, "deleted")
    assert entry["changes"]["file_name"]["old"] == "uploaded.pdf"


def test_delete_all_keeps_records_under_retention(client, auth_headers, db):
    response = client.delete("/api/invoices/all", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["total_deleted"] == 1
    assert response.json()["summary"]["kept_for_retention"] == 2
    assert {row["id"] for row in db.table("invoices_clean").rows} == {APPROVED, EDITED}


def test_history_endpoint(client, auth_headers, db):
    save_editor(client, auth_headers, EDITED, rechnungsbetrag=1200)
    entries = client.get(f"/api/invoices/{EDITED}/audit-log", headers=auth_headers).json()["entries"]
    assert entries and all(set(e) == {"seq", "action", "actor", "changes", "recorded_at"} for e in entries)


def test_chain_verification_endpoint(client, auth_headers, db):
    save_editor(client, auth_headers, EDITED, rechnungsbetrag=1200)
    assert client.get("/api/audit/verify", headers=auth_headers).json()["valid"] is True
    audit_rows(db)[0]["actor"] = "someone-else"
    assert client.get("/api/audit/verify", headers=auth_headers).json()["valid"] is False


def test_tax_audit_export(client, auth_headers, db):
    save_editor(client, auth_headers, EDITED, rechnungsbetrag=1200)
    response = client.get("/api/exports/gobd?year=2026", headers=auth_headers)
    assert response.status_code == 200
    assert "gobd-export-eingangsrechnungen-2026.zip" in response.headers["content-disposition"]

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert sorted(archive.namelist()) == ["aenderungsprotokoll.csv", "beschreibung.txt", "rechnungen.csv"]
    invoices = list(csv.DictReader(io.StringIO(archive.read("rechnungen.csv").decode()), delimiter=";"))
    assert len(invoices) == 3
    log = list(csv.DictReader(io.StringIO(archive.read("aenderungsprotokoll.csv").decode()), delimiter=";"))
    assert any(row["action"] == "updated" for row in log)
    assert "unverändert" in archive.read("beschreibung.txt").decode()


def test_export_for_year_without_invoices_is_empty(client, auth_headers, db):
    archive = zipfile.ZipFile(io.BytesIO(client.get("/api/exports/gobd?year=2019", headers=auth_headers).content))
    assert archive.read("rechnungen.csv").decode().count("\n") == 1  # header only

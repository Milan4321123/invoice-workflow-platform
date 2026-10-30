import pytest

from services.database import db_service

STORED = {
    "id": "inv-1",
    "file_name": "20261015_OMEGA_ELEKTRO_Mueller.pdf",
    "rechnungssteller": "Elektro Müller GmbH",
    "rechnungsempfaenger": "Bau AG",
    "rechnungsnummer": "RE-0815",
    "rechnungsdatum": "2026-10-15",
    "leistungsdatum": "2026-10-10",
    "lieferant_ust_id": "DE143454214",
    "nettobetrag": 1000,
    "ust_satz": 19,
    "ust_betrag": 190,
    "rechnungsbetrag": 1190,
}


@pytest.fixture
def fake_db(monkeypatch):
    state = {"duplicates": []}
    monkeypatch.setattr(type(db_service), "is_available", property(lambda self: True))
    monkeypatch.setattr(db_service, "get_invoice",
                        lambda invoice_id: {"success": True, "data": dict(STORED)} if invoice_id == "inv-1"
                        else {"success": False, "error": "Invoice not found"})
    monkeypatch.setattr(db_service, "find_same_invoice_number",
                        lambda supplier, number, exclude_id: {"success": True, "data": state["duplicates"]})
    return state


def test_stored_invoice_passes(client, auth_headers, fake_db):
    response = client.post("/api/invoices/inv-1/compliance-check", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unsaved_editor_values_override_stored_ones(client, auth_headers, fake_db):
    response = client.post("/api/invoices/inv-1/compliance-check", headers=auth_headers,
                           json={"rechnungsbetrag": 1500})
    codes = {f["code"] for f in response.json()["findings"]}
    assert "amounts_inconsistent" in codes


def test_same_number_from_same_supplier_is_flagged(client, auth_headers, fake_db):
    fake_db["duplicates"] = [{"id": "inv-0", "file_name": "20261001_OMEGA_ELEKTRO_Mueller.pdf"}]
    body = client.post("/api/invoices/inv-1/compliance-check", headers=auth_headers).json()
    assert body["status"] == "errors"
    assert body["findings"][0]["code"] == "duplicate_invoice_number"


def test_unknown_invoice_is_404(client, auth_headers, fake_db):
    assert client.post("/api/invoices/nope/compliance-check", headers=auth_headers).status_code == 404

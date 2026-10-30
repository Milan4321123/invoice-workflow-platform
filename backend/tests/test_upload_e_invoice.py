"""The upload endpoint reads e-invoices and stores what they contain."""
from pathlib import Path

import pytest

from services.database import db_service
from services.upload_service import upload_service

FIXTURES = Path(__file__).parent / "fixtures" / "e_invoices"


class _NoRows:
    """Stands in for the Supabase query builder in the duplicate check"""
    data = []

    def __getattr__(self, name):
        return lambda *args, **kwargs: self


@pytest.fixture
def stored(monkeypatch):
    created = []

    async def upload_to_storage(file_data, storage_path):
        return True, f"https://storage.test/{storage_path}", None

    monkeypatch.setattr(type(db_service), "is_available", property(lambda self: True))
    monkeypatch.setattr(type(db_service), "client", property(lambda self: _NoRows()))
    monkeypatch.setattr(db_service, "create_invoice", lambda data: created.append(data) or {"success": True})
    monkeypatch.setattr(upload_service, "upload_to_storage", upload_to_storage)
    return created


def upload(client, auth_headers, filename, content, content_type):
    return client.post("/api/upload", headers=auth_headers, files={"file": (filename, content, content_type)})


def test_xrechnung_xml_fills_the_invoice(client, auth_headers, stored):
    xml = (FIXTURES / "xrechnung_ubl.xml").read_bytes()
    response = upload(client, auth_headers, "20261015_OMEGA_ELEKTRO_Mueller.xml", xml, "text/xml")

    assert response.status_code == 200, response.text
    assert response.json()["e_invoice_format"] == "XRechnung 3.0 (UBL)"
    record = stored[0]
    assert record["file_name"] == "20261015_OMEGA_ELEKTRO_Mueller.xml"
    assert record["rechnungsnummer"] == "RE-2026-0815"
    assert record["rechnungsbetrag"] == 1190.0
    assert record["e_rechnung_format"] == "XRechnung 3.0 (UBL)"


def test_xml_that_is_not_an_invoice_is_rejected(client, auth_headers, stored):
    response = upload(client, auth_headers, "20261015_OMEGA_ELEKTRO_Mueller.xml", b"<order/>", "application/xml")
    assert response.status_code == 400
    assert "E-Rechnung" in response.json()["detail"]
    assert stored == []


def test_xxe_upload_is_rejected(client, auth_headers, stored):
    xml = (FIXTURES / "xxe_attack.xml").read_bytes()
    response = upload(client, auth_headers, "20261015_OMEGA_ELEKTRO_Mueller.xml", xml, "application/xml")
    assert response.status_code == 400
    assert stored == []


def test_plain_pdf_is_stored_without_e_invoice_data(client, auth_headers, stored):
    response = upload(client, auth_headers, "20261015_OMEGA_ELEKTRO_Mueller.pdf", b"%PDF-1.4 scan", "application/pdf")
    assert response.status_code == 200, response.text
    assert response.json()["e_invoice_format"] is None
    assert "rechnungsnummer" not in stored[0]


def test_bad_filename_is_a_client_error(client, auth_headers, stored):
    response = upload(client, auth_headers, "rechnung.pdf", b"%PDF-1.4", "application/pdf")
    assert response.status_code == 400
    assert "EINGANGSDATUM" in response.json()["detail"]


def test_other_file_types_are_rejected(client, auth_headers, stored):
    response = upload(client, auth_headers, "20261015_OMEGA_ELEKTRO_Mueller.png", b"\x89PNG", "image/png")
    assert response.status_code == 400

"""Demo mode must keep working: every seeded invoice shows what it is there to show."""
import pytest

from services.database import DatabaseService
from services.demo_data import seed, simple_pdf
from services.in_memory_supabase import FakeSupabase
from services.invoice_compliance import check_invoice


@pytest.fixture
def demo_db(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    db = DatabaseService()
    assert isinstance(db.client, FakeSupabase)
    seed(db)
    return db


def by_name(db):
    return {row["file_name"]: row for row in db.client.table("invoices_clean").rows}


def codes(row):
    return {f.code for f in check_invoice(row)}


def test_seeded_invoices(demo_db):
    rows = by_name(demo_db)
    assert len(rows) == 6
    assert codes(rows["20261015_OMEGA_ELEKTRO_Mueller.pdf"]) == set()
    assert rows["20261020_OMEGA_FLIESEN_Schmidt.pdf"]["e_rechnung_format"] == "ZUGFeRD/Factur-X (EN 16931)"
    assert rows["20261001_HAFEN_TROCKENBAU_Weber.xml"]["reverse_charge_13b"] is True
    assert {"vat_id_invalid", "invoice_number_missing", "amounts_inconsistent"} <= codes(
        rows["20261005_HAFEN_SANITAER_Becker.pdf"])
    assert rows["20260910_OMEGA_MALER_Klein.pdf"]["status"] == "approved_by_bauleiter"


def test_files_are_stored(demo_db):
    files = demo_db.client.storage.from_("invoices").files
    assert files["20261015_OMEGA_ELEKTRO_Mueller.pdf"].startswith(b"%PDF-1.4")
    assert b"CrossIndustryInvoice" in files["20261001_HAFEN_TROCKENBAU_Weber.xml"]


def test_change_log_is_intact(demo_db):
    assert demo_db.audit.verify_chain()["valid"]


def test_generated_pdf_is_readable():
    from io import BytesIO
    from pypdf import PdfReader

    page = PdfReader(BytesIO(simple_pdf([(12, True, 50, 800, "Rechnung über 1.190,00 €")]))).pages[0]
    assert "Rechnung über 1.190,00 €" in page.extract_text()

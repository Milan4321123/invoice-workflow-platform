from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter

from services.e_invoice import EInvoiceError, extract_embedded_xml, parse_pdf, parse_xml
from services.invoice_compliance import check_invoice, is_valid_iban, summarize

FIXTURES = Path(__file__).parent / "fixtures" / "e_invoices"


def fixture(name):
    return (FIXTURES / name).read_bytes()


def pdf_with_attachment(name=None, content=b""):
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    if name:
        writer.add_attachment(name, content)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_xrechnung_ubl():
    invoice = parse_xml(fixture("xrechnung_ubl.xml"))
    assert invoice.syntax == "UBL"
    assert invoice.format == "XRechnung 3.0 (UBL)"
    assert invoice.invoice_fields() == {
        "rechnungsnummer": "RE-2026-0815",
        "rechnungsdatum": "2026-10-15",
        "leistungsdatum": "2026-10-10",
        "faelligkeit": "2026-11-14",
        "rechnungssteller": "Elektro Müller GmbH",
        "rechnungsempfaenger": "Muster Bau AG",
        "lieferant_ust_id": "DE123456788",
        "lieferant_steuernummer": "12/345/67890",
        "lieferant_iban": "DE89370400440532013000",
        "nettobetrag": 1000.0,
        "ust_betrag": 190.0,
        "ust_satz": 19.0,
        "rechnungsbetrag": 1190.0,
        "reverse_charge_13b": False,
        "skonto_prozent": 2.0,
        "skonto_datum": "2026-10-25",
        "rechnungsart": "rechnung",
    }


def test_zugferd_cii():
    invoice = parse_xml(fixture("zugferd_en16931_cii.xml"))
    assert invoice.syntax == "CII"
    assert invoice.format == "EN 16931 (CII)"
    assert invoice.rechnungsnummer == "2026-4711"
    assert invoice.rechnungsdatum == "2026-10-20"
    assert invoice.leistungsdatum == "2026-10-18"
    assert invoice.faelligkeit == "2026-11-19"
    assert invoice.lieferant_ust_id == "DE987654328"
    assert (invoice.nettobetrag, invoice.ust_betrag, invoice.rechnungsbetrag) == (2500.0, 475.0, 2975.0)
    assert invoice.skonto_prozent == 3.0
    assert invoice.skonto_datum == "2026-11-03"


def test_reverse_charge_credit_note():
    invoice = parse_xml(fixture("reverse_charge_credit_note_cii.xml"))
    assert invoice.format == "XRechnung 3.0 (CII)"
    assert invoice.rechnungsart == "gutschrift"
    assert invoice.reverse_charge_13b is True
    assert invoice.ust_satz == 0
    assert invoice.lieferant_steuernummer == "2181508150"
    assert invoice.lieferant_ust_id is None


@pytest.mark.parametrize("name", ["xrechnung_ubl.xml", "zugferd_en16931_cii.xml"])
def test_parsed_e_invoices_pass_the_compliance_check(name):
    """What the XML carries is exactly what §14 UStG asks for."""
    fields = parse_xml(fixture(name)).invoice_fields()
    report = summarize([f for f in check_invoice(fields) if f.field != "freistellung_48b_gueltig_bis"])
    assert report["status"] == "ok", report["findings"]


def test_fixture_ibans_are_valid():
    assert is_valid_iban(parse_xml(fixture("zugferd_en16931_cii.xml")).lieferant_iban)


def test_external_entities_are_refused():
    with pytest.raises(EInvoiceError, match="DTD"):
        parse_xml(fixture("xxe_attack.xml"))


@pytest.mark.parametrize("content", [b"not xml", b"<html><body/></html>", b"<?xml version='1.0'?><Invoice/>"])
def test_non_invoices_are_rejected(content):
    with pytest.raises(EInvoiceError):
        parse_xml(content)


def test_oversized_xml_is_rejected():
    with pytest.raises(EInvoiceError, match="groß"):
        parse_xml(b"<a>" + b"x" * (5 * 1024 * 1024) + b"</a>")


def test_zugferd_pdf():
    pdf = pdf_with_attachment("factur-x.xml", fixture("zugferd_en16931_cii.xml"))
    invoice = parse_pdf(pdf)
    assert invoice.format == "ZUGFeRD/Factur-X (EN 16931)"
    assert invoice.rechnungsbetrag == 2975.0


def test_attachment_names_are_case_insensitive():
    pdf = pdf_with_attachment("ZUGFeRD-invoice.xml", fixture("zugferd_en16931_cii.xml"))
    assert extract_embedded_xml(pdf) is not None


def test_plain_pdf_is_not_an_e_invoice():
    assert parse_pdf(pdf_with_attachment()) is None
    assert parse_pdf(pdf_with_attachment("lieferschein.xml", b"<x/>")) is None


def test_broken_pdf_is_not_an_e_invoice():
    assert parse_pdf(b"%PDF-1.4 truncated") is None

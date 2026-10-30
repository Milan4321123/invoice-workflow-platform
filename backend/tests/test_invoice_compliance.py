from datetime import date

import pytest

from services.invoice_compliance import (
    check_invoice,
    is_plausible_steuernummer,
    is_valid_de_vat_id,
    is_valid_iban,
    is_valid_vat_id,
    summarize,
)

TODAY = date(2026, 10, 30)


def complete_invoice(**overrides):
    """An invoice with every §14 UStG detail, from a subcontractor with a valid §48b exemption."""
    invoice = {
        "rechnungssteller": "Elektro Müller GmbH",
        "rechnungsempfaenger": "Bau AG",
        "lieferant_ust_id": "DE143454214",
        "rechnungsnummer": "RE-2026-0815",
        "rechnungsdatum": "2026-10-15",
        "leistungsdatum": "2026-10-10",
        "nettobetrag": 1000.00,
        "ust_satz": 19,
        "ust_betrag": 190.00,
        "rechnungsbetrag": 1190.00,
        "lieferant_iban": "DE89 3704 0044 0532 0130 00",
        "gewerk": "elektro",
        "freistellung_48b_gueltig_bis": "2027-06-30",
        "faelligkeit": "2026-11-14",
        "skonto_datum": "2026-10-25",
        "skonto_prozent": 2,
    }
    invoice.update(overrides)
    return invoice


def codes(invoice):
    return {f.code for f in check_invoice(invoice, today=TODAY)}


# --- identifiers ----------------------------------------------------------

@pytest.mark.parametrize("vat_id", ["DE143454214", "DE129274202", "DE 123 475 223", "de129273398"])
def test_real_german_vat_ids_pass(vat_id):
    assert is_valid_de_vat_id(vat_id)


@pytest.mark.parametrize("vat_id", ["DE143454215", "DE12345678", "DE1234567890", "FR143454214", "", None])
def test_bad_german_vat_ids_fail(vat_id):
    assert not is_valid_de_vat_id(vat_id)


def test_foreign_vat_ids_get_format_check_only():
    assert is_valid_vat_id("ATU12345678")
    assert is_valid_vat_id("NL123456789B01")
    assert not is_valid_vat_id("X1")


@pytest.mark.parametrize("iban, ok", [
    ("DE89370400440532013000", True),
    ("DE89 3704 0044 0532 0130 00", True),
    ("DE89370400440532013001", False),   # wrong check digits
    ("DE8937040044053201300", False),    # German IBANs have 22 characters
    ("AT611904300234573201", True),
    ("not an iban", False),
])
def test_iban(iban, ok):
    assert is_valid_iban(iban) is ok


@pytest.mark.parametrize("number, ok", [("12/345/67890", True), ("2181508150", True),
                                        ("9181081508155", True), ("12345", False)])
def test_steuernummer(number, ok):
    assert is_plausible_steuernummer(number) is ok


# --- §14 UStG ---------------------------------------------------------------

def test_complete_invoice_has_no_errors_or_warnings():
    report = summarize(check_invoice(complete_invoice(), today=TODAY))
    assert report["status"] == "ok", report["findings"]


@pytest.mark.parametrize("field, code", [
    ("rechnungssteller", "supplier_missing"),
    ("rechnungsempfaenger", "recipient_missing"),
    ("rechnungsnummer", "invoice_number_missing"),
    ("rechnungsdatum", "invoice_date_missing"),
    ("nettobetrag", "net_missing"),
    ("ust_satz", "rate_missing"),
    ("ust_betrag", "vat_missing"),
])
def test_missing_mandatory_detail_is_an_error(field, code):
    assert code in codes(complete_invoice(**{field: None}))


def test_needs_tax_number_or_vat_id():
    assert "tax_id_missing" in codes(complete_invoice(lieferant_ust_id=None))
    assert "tax_id_missing" not in codes(complete_invoice(lieferant_ust_id=None, lieferant_steuernummer="12/345/67890"))


def test_invalid_vat_id_is_an_error():
    assert "vat_id_invalid" in codes(complete_invoice(lieferant_ust_id="DE143454215"))


def test_future_invoice_date():
    assert "invoice_date_future" in codes(complete_invoice(rechnungsdatum="2026-12-01"))


def test_net_plus_vat_must_equal_gross():
    assert "amounts_inconsistent" in codes(complete_invoice(rechnungsbetrag=1200.00))


def test_cent_rounding_is_tolerated():
    assert "amounts_inconsistent" not in codes(complete_invoice(rechnungsbetrag=1190.03))


def test_vat_must_match_rate():
    assert "vat_inconsistent" in codes(complete_invoice(ust_satz=7))


def test_unusual_rate_warns():
    assert "rate_unusual" in codes(complete_invoice(ust_satz=16, ust_betrag=160, rechnungsbetrag=1160))


# --- §33 UStDV small invoices -------------------------------------------------

def test_small_invoice_needs_fewer_details():
    small = {"rechnungssteller": "Baumarkt", "rechnungsdatum": "2026-10-01", "leistungsdatum": "2026-10-01",
             "rechnungsbetrag": 119.00, "ust_satz": 19}
    found = codes(small)
    assert "small_invoice" in found
    assert not found & {"recipient_missing", "invoice_number_missing", "tax_id_missing", "net_missing"}


def test_limit_is_250_euro_gross():
    assert "small_invoice" in codes(complete_invoice(rechnungsbetrag=250.00, nettobetrag=210.08, ust_betrag=39.92))
    assert "small_invoice" not in codes(complete_invoice(rechnungsbetrag=250.01, nettobetrag=210.09, ust_betrag=39.92))


# --- §13b reverse charge -------------------------------------------------------

def test_reverse_charge_without_vat_is_fine():
    found = codes(complete_invoice(reverse_charge_13b=True, ust_satz=0, ust_betrag=0, rechnungsbetrag=1000))
    assert "reverse_charge" in found
    assert "reverse_charge_with_vat" not in found
    assert "vat_missing" not in found


def test_reverse_charge_with_vat_shown_is_an_error():
    assert "reverse_charge_with_vat" in codes(complete_invoice(reverse_charge_13b=True))


def test_zero_rate_without_13b_needs_a_reason():
    assert "zero_rate_without_reason" in codes(
        complete_invoice(ust_satz=0, ust_betrag=0, rechnungsbetrag=1000))


# --- §48 EStG construction withholding tax -------------------------------------

def test_construction_invoice_without_exemption_warns():
    assert "construction_tax_no_exemption" in codes(complete_invoice(freistellung_48b_gueltig_bis=None))


def test_expired_exemption_is_an_error():
    assert "construction_tax_exemption_expired" in codes(complete_invoice(freistellung_48b_gueltig_bis="2026-09-30"))


def test_non_construction_invoice_skips_48b():
    assert "construction_tax_no_exemption" not in codes(
        complete_invoice(gewerk=None, freistellung_48b_gueltig_bis=None))


# --- payment details -----------------------------------------------------------

def test_invalid_iban_is_an_error():
    assert "iban_invalid" in codes(complete_invoice(lieferant_iban="DE89370400440532013001"))


def test_skonto_after_due_date_warns():
    assert "skonto_after_due" in codes(complete_invoice(skonto_datum="2026-11-20"))


def test_summary_counts():
    report = summarize(check_invoice(complete_invoice(rechnungsnummer=None, leistungsdatum=None), today=TODAY))
    assert report["status"] == "errors"
    assert report["error_count"] == 1
    assert report["warning_count"] == 1

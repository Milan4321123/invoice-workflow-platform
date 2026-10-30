"""
Checks an incoming invoice against German tax rules before it is paid.

Input VAT (Vorsteuer) can only be deducted from an invoice that carries every
detail §14 Abs. 4 UStG requires, so gaps are cheaper to catch in accounts
payable than in a tax audit years later. For construction invoices two more
rules matter: §13b UStG (the recipient owes the VAT) and §48 EStG (15 %
construction withholding tax unless the supplier has an exemption).

Everything here is pure and side-effect free. The duplicate check needs the
database, so the API route adds it.
"""
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Dict, List, Optional

KLEINBETRAG_LIMIT = Decimal("250")  # §33 UStDV, gross, since 2017
USUAL_RATES = {Decimal("19"), Decimal("7"), Decimal("0")}
# Line items are rounded one by one, so totals may differ by a few cents
AMOUNT_TOLERANCE = Decimal("0.05")
UNUSUAL_SKONTO_PERCENT = Decimal("10")

ERROR = "error"      # input VAT deduction or payment at risk
WARNING = "warning"  # likely mistake, check the document
INFO = "info"        # rule that applies, no action needed


@dataclass
class Finding:
    code: str
    severity: str
    field: Optional[str]
    message: str
    legal_ref: Optional[str] = None


# ---------------------------------------------------------------------------
# Identifier checks
# ---------------------------------------------------------------------------

def _compact(value: Optional[str]) -> str:
    return re.sub(r"[\s./-]", "", value or "").upper()


def is_valid_de_vat_id(value: Optional[str]) -> bool:
    """German USt-IdNr.: DE + 9 digits, last one a check digit (ISO 7064, MOD 11,10)."""
    vat_id = _compact(value)
    if not re.fullmatch(r"DE\d{9}", vat_id):
        return False
    digits = vat_id[2:]
    product = 10
    for digit in digits[:8]:
        total = (int(digit) + product) % 10 or 10
        product = (2 * total) % 11
    check = 11 - product
    return (0 if check == 10 else check) == int(digits[8])


def is_valid_vat_id(value: Optional[str]) -> bool:
    """
    German IDs get the full check-digit test. Other EU IDs only get a format
    check here; whether they are registered is only answered by VIES.
    """
    vat_id = _compact(value)
    if vat_id.startswith("DE"):
        return is_valid_de_vat_id(vat_id)
    return bool(re.fullmatch(r"(ATU\d{8}|[A-Z]{2}[0-9A-Z+*]{2,12})", vat_id))


def is_valid_iban(value: Optional[str]) -> bool:
    """ISO 13616: country code, two check digits, mod 97 of the rearranged number is 1."""
    iban = _compact(value)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", iban):
        return False
    if iban.startswith("DE") and len(iban) != 22:
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(char, 36)) for char in rearranged)) % 97 == 1


def is_plausible_steuernummer(value: Optional[str]) -> bool:
    """Tax office number: 10 or 11 digits in state format, 13 in the federal ELSTER format."""
    digits = re.sub(r"\D", "", value or "")
    return len(digits) in (10, 11, 13)


# ---------------------------------------------------------------------------
# Invoice check
# ---------------------------------------------------------------------------

def _decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _date(value: Any) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def check_invoice(invoice: Dict[str, Any], today: Optional[date] = None) -> List[Finding]:
    today = today or date.today()
    findings: List[Finding] = []

    def add(code, severity, field, message, legal_ref=None):
        findings.append(Finding(code, severity, field, message, legal_ref))

    gross = _decimal(invoice.get("rechnungsbetrag"))
    net = _decimal(invoice.get("nettobetrag"))
    vat = _decimal(invoice.get("ust_betrag"))
    rate = _decimal(invoice.get("ust_satz"))
    reverse_charge = bool(invoice.get("reverse_charge_13b"))
    invoice_date = _date(invoice.get("rechnungsdatum"))
    due_date = _date(invoice.get("faelligkeit"))
    skonto_date = _date(invoice.get("skonto_datum"))
    skonto_percent = _decimal(invoice.get("skonto_prozent"))
    vat_id = invoice.get("lieferant_ust_id")
    tax_number = invoice.get("lieferant_steuernummer")

    small_invoice = gross is not None and gross <= KLEINBETRAG_LIMIT and not reverse_charge
    if small_invoice:
        add("small_invoice", INFO, "rechnungsbetrag",
            "Kleinbetragsrechnung bis 250 € brutto: Empfänger, Rechnungsnummer und Steuernummer "
            "sind nicht erforderlich, Bruttobetrag und Steuersatz genügen.",
            "§33 UStDV")

    # §14 Abs. 4 Nr. 1: name and address of supplier and recipient
    if not invoice.get("rechnungssteller"):
        add("supplier_missing", ERROR, "rechnungssteller",
            "Rechnungssteller fehlt.", "§14 Abs. 4 Nr. 1 UStG")
    if not small_invoice and not invoice.get("rechnungsempfaenger"):
        add("recipient_missing", ERROR, "rechnungsempfaenger",
            "Rechnungsempfänger fehlt.", "§14 Abs. 4 Nr. 1 UStG")

    # Nr. 2: tax number or VAT ID of the supplier
    if vat_id and not is_valid_vat_id(vat_id):
        add("vat_id_invalid", ERROR, "lieferant_ust_id",
            "USt-IdNr. ist ungültig (Format oder Prüfziffer stimmt nicht).", "§14 Abs. 4 Nr. 2 UStG")
    if tax_number and not is_plausible_steuernummer(tax_number):
        add("tax_number_implausible", WARNING, "lieferant_steuernummer",
            "Steuernummer hat eine ungewöhnliche Länge (erwartet 10, 11 oder 13 Ziffern).",
            "§14 Abs. 4 Nr. 2 UStG")
    if not small_invoice and not vat_id and not tax_number:
        add("tax_id_missing", ERROR, "lieferant_ust_id",
            "Steuernummer oder USt-IdNr. des Lieferanten fehlt.", "§14 Abs. 4 Nr. 2 UStG")

    # Nr. 3 and 4: invoice date and a unique invoice number
    if not invoice_date:
        add("invoice_date_missing", ERROR, "rechnungsdatum",
            "Rechnungsdatum fehlt.", "§14 Abs. 4 Nr. 3 UStG")
    elif invoice_date > today:
        add("invoice_date_future", ERROR, "rechnungsdatum",
            "Rechnungsdatum liegt in der Zukunft.", "§14 Abs. 4 Nr. 3 UStG")
    if not small_invoice and not invoice.get("rechnungsnummer"):
        add("invoice_number_missing", ERROR, "rechnungsnummer",
            "Rechnungsnummer fehlt.", "§14 Abs. 4 Nr. 4 UStG")

    # Nr. 6: date of supply. May match the invoice date, but must be stated.
    if not invoice.get("leistungsdatum"):
        add("supply_date_missing", WARNING, "leistungsdatum",
            "Leistungsdatum fehlt. Es darf dem Rechnungsdatum entsprechen, muss aber auf der Rechnung stehen.",
            "§14 Abs. 4 Nr. 6 UStG")

    # Nr. 7 and 8: net amount, tax rate and tax amount
    if gross is None:
        add("gross_missing", ERROR, "rechnungsbetrag", "Rechnungsbetrag (brutto) fehlt.")
    if not small_invoice:
        if net is None:
            add("net_missing", ERROR, "nettobetrag",
                "Nettobetrag (Entgelt) fehlt.", "§14 Abs. 4 Nr. 7 UStG")
        if rate is None:
            add("rate_missing", ERROR, "ust_satz",
                "Steuersatz fehlt.", "§14 Abs. 4 Nr. 8 UStG")
        if vat is None and not reverse_charge and rate != 0:
            add("vat_missing", ERROR, "ust_betrag",
                "Umsatzsteuerbetrag fehlt.", "§14 Abs. 4 Nr. 8 UStG")

    if rate is not None and rate not in USUAL_RATES:
        add("rate_unusual", WARNING, "ust_satz",
            f"Steuersatz {rate} % ist in Deutschland unüblich (19 %, 7 % oder 0 %).", "§12 UStG")

    if net is not None and gross is not None:
        expected_gross = net + (vat or Decimal("0"))
        if abs(expected_gross - gross) > AMOUNT_TOLERANCE:
            add("amounts_inconsistent", ERROR, "rechnungsbetrag",
                f"Netto + USt ({expected_gross:.2f} €) ergibt nicht den Bruttobetrag ({gross:.2f} €).")
    if net is not None and rate is not None and vat is not None and not reverse_charge:
        expected_vat = (net * rate / 100).quantize(Decimal("0.01"))
        if abs(expected_vat - vat) > AMOUNT_TOLERANCE:
            add("vat_inconsistent", WARNING, "ust_betrag",
                f"USt-Betrag passt nicht zum Steuersatz: erwartet {expected_vat:.2f} €, ausgewiesen {vat:.2f} €.")

    # §13b: construction services between construction companies
    if reverse_charge:
        add("reverse_charge", INFO, "reverse_charge_13b",
            "Steuerschuldnerschaft des Leistungsempfängers: Wir melden die Umsatzsteuer selbst an. "
            "Die Rechnung muss diesen Hinweis enthalten.",
            "§13b Abs. 2 Nr. 4 UStG, §14a Abs. 5 UStG")
        if vat:
            add("reverse_charge_with_vat", ERROR, "ust_betrag",
                "Bei §13b darf keine Umsatzsteuer ausgewiesen sein. Ausgewiesene Steuer schuldet der "
                "Lieferant trotzdem, abziehbar ist sie für uns nicht. Korrigierte Rechnung anfordern.",
                "§13b UStG, §14c Abs. 1 UStG")
    elif rate == 0 and not small_invoice:
        add("zero_rate_without_reason", WARNING, "ust_satz",
            "0 % ohne §13b: Die Rechnung muss den Grund nennen, z. B. Kleinunternehmer (§19 UStG) "
            "oder eine Steuerbefreiung.",
            "§14 Abs. 4 Nr. 8 UStG")

    # §48 EStG: 15 % withholding on construction services
    if invoice.get("gewerk"):
        exemption_until = _date(invoice.get("freistellung_48b_gueltig_bis"))
        if not exemption_until:
            add("construction_tax_no_exemption", WARNING, "freistellung_48b_gueltig_bis",
                "Bauleistung ohne Freistellungsbescheinigung: 15 % Bauabzugsteuer einbehalten und ans "
                "Finanzamt abführen, sofern die Bagatellgrenze (5.000 € pro Jahr und Lieferant) "
                "überschritten ist.",
                "§48 Abs. 1 und 2 EStG")
        elif exemption_until < (invoice_date or today):
            add("construction_tax_exemption_expired", ERROR, "freistellung_48b_gueltig_bis",
                f"Freistellungsbescheinigung war nur bis {exemption_until:%d.%m.%Y} gültig: "
                "15 % Bauabzugsteuer einbehalten oder aktuelle Bescheinigung anfordern.",
                "§48b EStG")

    # Payment details
    iban = invoice.get("lieferant_iban")
    if iban and not is_valid_iban(iban):
        add("iban_invalid", ERROR, "lieferant_iban",
            "IBAN ist ungültig (Länge oder Prüfziffer stimmt nicht).", "ISO 13616")
    if due_date and invoice_date and due_date < invoice_date:
        add("due_before_invoice", WARNING, "faelligkeit", "Fälligkeit liegt vor dem Rechnungsdatum.")
    if skonto_date and due_date and skonto_date > due_date:
        add("skonto_after_due", WARNING, "skonto_datum", "Skontofrist endet nach der Fälligkeit.")
    if skonto_percent is not None and skonto_percent > UNUSUAL_SKONTO_PERCENT:
        add("skonto_unusual", WARNING, "skonto_prozent",
            f"{skonto_percent} % Skonto ist ungewöhnlich hoch. Bitte mit der Rechnung abgleichen.")

    return findings


def summarize(findings: List[Finding]) -> Dict[str, Any]:
    severities = {finding.severity for finding in findings}
    status = "errors" if ERROR in severities else "warnings" if WARNING in severities else "ok"
    return {
        "status": status,
        "error_count": sum(f.severity == ERROR for f in findings),
        "warning_count": sum(f.severity == WARNING for f in findings),
        "findings": [asdict(f) for f in findings],
    }


def check_stored_invoice(invoice: Dict[str, Any], db: Any) -> List[Finding]:
    """
    check_invoice plus the one rule that needs the database: the same
    invoice number from the same supplier already recorded (double payment).
    """
    findings = check_invoice(invoice)
    supplier, number = invoice.get("rechnungssteller"), invoice.get("rechnungsnummer")
    if supplier and number and invoice.get("id"):
        duplicates = db.find_same_invoice_number(supplier, number, exclude_id=invoice["id"])
        for other in duplicates.get("data", []):
            findings.insert(0, Finding(
                "duplicate_invoice_number", ERROR, "rechnungsnummer",
                f"Rechnungsnummer {number} von {supplier} ist bereits erfasst "
                f"({other.get('file_name')}). Doppelte Zahlung vermeiden.",
            ))
    return findings

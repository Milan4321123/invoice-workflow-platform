"""
Reads structured e-invoices (EN 16931) into invoice fields.

Since 1 January 2025 every German business must be able to receive
e-invoices (§14 Abs. 1 UStG as amended by the Wachstumschancengesetz). They
come in two syntaxes, and either can be the legally binding invoice:

- XRechnung, as UBL 2.1 or as UN/CEFACT CII XML, usually a bare .xml file
- ZUGFeRD / Factur-X, a PDF/A-3 with CII XML embedded. The XML is the
  invoice; the PDF is only a human-readable copy, so the XML wins when they
  disagree.

Reading the XML means nobody has to retype amounts, tax IDs or the IBAN, and
it is exact where OCR guesses. Field comments give the EN 16931 business
term (BT-n).

The XML comes from outside the company, so it is parsed with defusedxml,
which refuses DTDs and entity expansion (XXE, "billion laughs").
"""
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
import logging
import re
from typing import Any, Dict, List, Optional
from xml.etree.ElementTree import Element

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

logger = logging.getLogger(__name__)

MAX_XML_BYTES = 5 * 1024 * 1024

NS = {
    "ubl": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "ublcn": "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}

# File names ZUGFeRD 1/2, Factur-X and XRechnung-in-PDF use for the embedded XML
EMBEDDED_XML_NAMES = ("factur-x.xml", "zugferd-invoice.xml", "zugferd_invoice.xml", "xrechnung.xml")

CREDIT_NOTE_TYPE_CODES = {"381", "396", "532"}
# UNTDID 5305 tax category "AE" = VAT reverse charge
REVERSE_CHARGE_CATEGORY = "AE"
# XRechnung convention for cash discount in the payment terms text (BT-20)
SKONTO_PATTERN = re.compile(r"#SKONTO#TAGE=(\d+)#PROZENT=(\d+(?:\.\d+)?)#", re.IGNORECASE)


class EInvoiceError(ValueError):
    """The file is not an e-invoice we can read."""


@dataclass
class EInvoice:
    syntax: str                 # "UBL" or "CII"
    format: str                 # human-readable, e.g. "XRechnung 3.0 (UBL)"
    specification: Optional[str]  # BT-24 CustomizationID / guideline ID
    rechnungsnummer: Optional[str] = None
    rechnungsdatum: Optional[str] = None
    leistungsdatum: Optional[str] = None
    faelligkeit: Optional[str] = None
    rechnungssteller: Optional[str] = None
    rechnungsempfaenger: Optional[str] = None
    lieferant_ust_id: Optional[str] = None
    lieferant_steuernummer: Optional[str] = None
    lieferant_iban: Optional[str] = None
    nettobetrag: Optional[float] = None
    ust_betrag: Optional[float] = None
    ust_satz: Optional[float] = None
    rechnungsbetrag: Optional[float] = None
    reverse_charge_13b: bool = False
    skonto_prozent: Optional[float] = None
    skonto_datum: Optional[str] = None
    rechnungsart: str = "rechnung"
    waehrung: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def invoice_fields(self) -> Dict[str, Any]:
        """Values to store on the invoice, leaving out what the XML did not contain"""
        skip = {"syntax", "format", "specification", "notes", "waehrung"}
        return {k: v for k, v in asdict(self).items() if k not in skip and v not in (None, "")}


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def parse_xml(content: bytes) -> EInvoice:
    if len(content) > MAX_XML_BYTES:
        raise EInvoiceError("XML-Datei ist zu groß")
    try:
        root = SafeET.fromstring(content)
    except DefusedXmlException as exc:
        raise EInvoiceError("XML enthält unzulässige DTD- oder Entity-Deklarationen") from exc
    except SafeET.ParseError as exc:
        raise EInvoiceError(f"Keine gültige XML-Datei: {exc}") from exc

    if root.tag in (f"{{{NS['ubl']}}}Invoice", f"{{{NS['ublcn']}}}CreditNote"):
        return _parse_ubl(root)
    if root.tag == f"{{{NS['rsm']}}}CrossIndustryInvoice":
        return _parse_cii(root)
    raise EInvoiceError("XML ist weder UBL- noch CII-Rechnung (EN 16931)")


def extract_embedded_xml(pdf_content: bytes) -> Optional[bytes]:
    """The invoice XML attached to a ZUGFeRD/Factur-X PDF, or None for a plain PDF"""
    from pypdf import PdfReader

    try:
        attachments = PdfReader(BytesIO(pdf_content)).attachments
    except Exception as exc:  # damaged or encrypted PDFs are still valid uploads
        logger.info(f"Could not read PDF attachments: {exc}")
        return None

    by_name = {name.lower(): data for name, data in attachments.items()}
    for name in EMBEDDED_XML_NAMES:
        if name in by_name and by_name[name]:
            return by_name[name][0]
    return None


def parse_pdf(pdf_content: bytes) -> Optional[EInvoice]:
    """Parsed ZUGFeRD/Factur-X data, or None if the PDF carries no invoice XML"""
    xml = extract_embedded_xml(pdf_content)
    if xml is None:
        return None
    invoice = parse_xml(xml)
    invoice.format = f"ZUGFeRD/Factur-X ({_profile_name(invoice.specification)})"
    return invoice


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text(element: Optional[Element], path: str) -> Optional[str]:
    if element is None:
        return None
    found = element.find(path, NS)
    if found is None or found.text is None:
        return None
    return found.text.strip() or None


def _amount(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(Decimal(value))
    except InvalidOperation:
        return None


def _cii_date(element: Optional[Element], path: str) -> Optional[str]:
    """CII dates use format 102 (YYYYMMDD)"""
    raw = _text(element, path)
    if raw and re.fullmatch(r"\d{8}", raw):
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return None


def _apply_tax_categories(invoice: EInvoice, categories: List[tuple]) -> None:
    """Single rate goes to ust_satz; mixed rates are left for the user to split."""
    codes = {code for code, _ in categories if code}
    rates = {rate for _, rate in categories if rate is not None}
    invoice.reverse_charge_13b = REVERSE_CHARGE_CATEGORY in codes
    if len(rates) == 1:
        invoice.ust_satz = rates.pop()
    elif len(rates) > 1:
        invoice.notes.append(f"Mehrere Steuersätze ({', '.join(f'{r:g} %' for r in sorted(rates))})")


def _apply_payment_terms(invoice: EInvoice, terms_text: Optional[str]) -> None:
    match = SKONTO_PATTERN.search(terms_text or "")
    if not match:
        return
    days, percent = int(match.group(1)), float(match.group(2))
    invoice.skonto_prozent = percent
    if invoice.rechnungsdatum:
        issued = date.fromisoformat(invoice.rechnungsdatum)
        invoice.skonto_datum = (issued + timedelta(days=days)).isoformat()


def _profile_name(specification: Optional[str]) -> str:
    spec = (specification or "").lower()
    if "xrechnung" in spec:
        version = re.search(r"xrechnung_(\d+(?:\.\d+)?)", spec)
        return f"XRechnung {version.group(1)}" if version else "XRechnung"
    if "extended" in spec:
        return "EXTENDED"
    if "basicwl" in spec:
        return "BASIC WL"
    if "basic" in spec:
        return "BASIC"
    if "minimum" in spec:
        return "MINIMUM"
    if "en16931" in spec:
        return "EN 16931"
    return "unbekanntes Profil"


# ---------------------------------------------------------------------------
# UBL 2.1
# ---------------------------------------------------------------------------

def _parse_ubl(root: Element) -> EInvoice:
    spec = _text(root, "cbc:CustomizationID")
    is_credit_note = root.tag.endswith("CreditNote")
    invoice = EInvoice(syntax="UBL", format=f"{_profile_name(spec)} (UBL)", specification=spec)

    invoice.rechnungsnummer = _text(root, "cbc:ID")                       # BT-1
    invoice.rechnungsdatum = _text(root, "cbc:IssueDate")                 # BT-2
    invoice.faelligkeit = _text(root, "cbc:DueDate") or _text(root, "cac:PaymentMeans/cbc:PaymentDueDate")  # BT-9
    invoice.leistungsdatum = _text(root, "cac:Delivery/cbc:ActualDeliveryDate")  # BT-72
    invoice.waehrung = _text(root, "cbc:DocumentCurrencyCode")            # BT-5

    type_code = _text(root, "cbc:InvoiceTypeCode") or _text(root, "cbc:CreditNoteTypeCode")
    if is_credit_note or type_code in CREDIT_NOTE_TYPE_CODES:
        invoice.rechnungsart = "gutschrift"

    seller = root.find("cac:AccountingSupplierParty/cac:Party", NS)
    invoice.rechnungssteller = (_text(seller, "cac:PartyLegalEntity/cbc:RegistrationName")
                                or _text(seller, "cac:PartyName/cbc:Name"))  # BT-27
    if seller is not None:
        for scheme in seller.findall("cac:PartyTaxScheme", NS):
            scheme_id = _text(scheme, "cac:TaxScheme/cbc:ID")
            if scheme_id == "VAT":
                invoice.lieferant_ust_id = _text(scheme, "cbc:CompanyID")         # BT-31
            elif scheme_id == "FC":
                invoice.lieferant_steuernummer = _text(scheme, "cbc:CompanyID")   # BT-32

    buyer = root.find("cac:AccountingCustomerParty/cac:Party", NS)
    invoice.rechnungsempfaenger = (_text(buyer, "cac:PartyLegalEntity/cbc:RegistrationName")
                                   or _text(buyer, "cac:PartyName/cbc:Name"))  # BT-44

    invoice.lieferant_iban = _text(root, "cac:PaymentMeans/cac:PayeeFinancialAccount/cbc:ID")  # BT-84

    totals = root.find("cac:LegalMonetaryTotal", NS)
    invoice.nettobetrag = _amount(_text(totals, "cbc:TaxExclusiveAmount"))      # BT-109
    invoice.rechnungsbetrag = _amount(_text(totals, "cbc:TaxInclusiveAmount"))  # BT-112

    # BT-110: the TaxTotal in document currency (BT-111 may repeat it in EUR)
    for tax_total in root.findall("cac:TaxTotal", NS):
        amount = tax_total.find("cbc:TaxAmount", NS)
        if amount is not None and amount.get("currencyID") in (None, invoice.waehrung):
            invoice.ust_betrag = _amount(amount.text)
            break

    categories = [
        (_text(sub, "cac:TaxCategory/cbc:ID"), _amount(_text(sub, "cac:TaxCategory/cbc:Percent")))
        for sub in root.findall("cac:TaxTotal/cac:TaxSubtotal", NS)
    ]
    _apply_tax_categories(invoice, categories)
    _apply_payment_terms(invoice, _text(root, "cac:PaymentTerms/cbc:Note"))  # BT-20
    return invoice


# ---------------------------------------------------------------------------
# UN/CEFACT CII (XRechnung CII, ZUGFeRD 2.x, Factur-X)
# ---------------------------------------------------------------------------

def _parse_cii(root: Element) -> EInvoice:
    spec = _text(root, "rsm:ExchangedDocumentContext/ram:GuidelineSpecifiedDocumentContextParameter/ram:ID")
    invoice = EInvoice(syntax="CII", format=f"{_profile_name(spec)} (CII)", specification=spec)

    document = root.find("rsm:ExchangedDocument", NS)
    invoice.rechnungsnummer = _text(document, "ram:ID")                                     # BT-1
    invoice.rechnungsdatum = _cii_date(document, "ram:IssueDateTime/udt:DateTimeString")    # BT-2
    if _text(document, "ram:TypeCode") in CREDIT_NOTE_TYPE_CODES:
        invoice.rechnungsart = "gutschrift"

    transaction = root.find("rsm:SupplyChainTradeTransaction", NS)
    agreement = transaction.find("ram:ApplicableHeaderTradeAgreement", NS) if transaction is not None else None
    delivery = transaction.find("ram:ApplicableHeaderTradeDelivery", NS) if transaction is not None else None
    settlement = transaction.find("ram:ApplicableHeaderTradeSettlement", NS) if transaction is not None else None

    seller = agreement.find("ram:SellerTradeParty", NS) if agreement is not None else None
    invoice.rechnungssteller = _text(seller, "ram:Name")                                    # BT-27
    if seller is not None:
        for registration in seller.findall("ram:SpecifiedTaxRegistration/ram:ID", NS):
            if registration.get("schemeID") == "VA":
                invoice.lieferant_ust_id = (registration.text or "").strip() or None        # BT-31
            elif registration.get("schemeID") == "FC":
                invoice.lieferant_steuernummer = (registration.text or "").strip() or None  # BT-32
    invoice.rechnungsempfaenger = _text(agreement, "ram:BuyerTradeParty/ram:Name")          # BT-44

    invoice.leistungsdatum = _cii_date(
        delivery, "ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime/udt:DateTimeString")  # BT-72

    if settlement is not None:
        invoice.waehrung = _text(settlement, "ram:InvoiceCurrencyCode")                     # BT-5
        invoice.lieferant_iban = _text(
            settlement, "ram:SpecifiedTradeSettlementPaymentMeans/ram:PayeePartyCreditorFinancialAccount/ram:IBANID")  # BT-84
        invoice.faelligkeit = _cii_date(
            settlement, "ram:SpecifiedTradePaymentTerms/ram:DueDateDateTime/udt:DateTimeString")  # BT-9

        summary = settlement.find("ram:SpecifiedTradeSettlementHeaderMonetarySummation", NS)
        invoice.nettobetrag = _amount(_text(summary, "ram:TaxBasisTotalAmount"))            # BT-109
        invoice.rechnungsbetrag = _amount(_text(summary, "ram:GrandTotalAmount"))           # BT-112
        if summary is not None:
            for tax_total in summary.findall("ram:TaxTotalAmount", NS):                     # BT-110
                if tax_total.get("currencyID") in (None, invoice.waehrung):
                    invoice.ust_betrag = _amount(tax_total.text)
                    break

        categories = [
            (_text(tax, "ram:CategoryCode"), _amount(_text(tax, "ram:RateApplicablePercent")))
            for tax in settlement.findall("ram:ApplicableTradeTax", NS)
        ]
        _apply_tax_categories(invoice, categories)
        _apply_payment_terms(invoice, _text(settlement, "ram:SpecifiedTradePaymentTerms/ram:Description"))  # BT-20

    return invoice

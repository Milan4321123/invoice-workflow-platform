"""
Drafts an e-mail asking the supplier for a corrected invoice.

An invoice missing §14 UStG details can be corrected by the supplier
(§31 Abs. 5 UStDV); until then input VAT is at risk. The draft lists what
is missing or wrong, in plain German. It is never sent automatically: the
user reviews, edits and sends it from their own mail program.

Data minimisation: only what the letter needs goes to the model (supplier,
invoice number and date, amount, findings), not IBANs, internal notes or
approver names.
"""
import json
from typing import Any, Dict, List

from services.ai import llm
from services.invoice_compliance import ERROR, WARNING, Finding

# Findings about our own process, not the supplier's document
INTERNAL_CODES = {"duplicate_invoice_number", "skonto_unusual", "due_before_invoice", "skonto_after_due",
                  "construction_tax_no_exemption", "reverse_charge", "small_invoice"}

SYSTEM = (
    "You write short, polite business e-mails in German for the accounts payable team of a construction "
    "company. Ask the supplier for a corrected invoice (Rechnungsberichtigung) that fixes exactly the listed "
    "points, and mention that the input tax deduction depends on it. Don't add facts, deadlines or threats "
    "that aren't given. End with the placeholder [Name] for the signature."
)


def relevant_findings(findings: List[Finding]) -> List[Finding]:
    return [f for f in findings if f.severity in (ERROR, WARNING) and f.code not in INTERNAL_CODES]


def _facts(invoice: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "lieferant": invoice.get("rechnungssteller"),
        "rechnungsnummer": invoice.get("rechnungsnummer"),
        "rechnungsdatum": invoice.get("rechnungsdatum"),
        "bruttobetrag": invoice.get("rechnungsbetrag"),
    }


def draft(invoice: Dict[str, Any], findings: List[Finding]) -> Dict[str, Any]:
    points = relevant_findings(findings)
    if not points:
        return {"mode": llm.mode(), "subject": None, "body": None,
                "reason": "Keine Punkte, die der Lieferant korrigieren müsste."}
    if llm.mode() == "live":
        return _draft_live(invoice, points)
    return _draft_offline(invoice, points)


def _reference(invoice: Dict[str, Any]) -> str:
    number = invoice.get("rechnungsnummer")
    date = invoice.get("rechnungsdatum")
    if number and date:
        return f"Ihre Rechnung {number} vom {date[8:10]}.{date[5:7]}.{date[:4]}"
    if number:
        return f"Ihre Rechnung {number}"
    return f"Ihre Rechnung über {invoice.get('rechnungsbetrag') or '—'} €"


def _draft_offline(invoice: Dict[str, Any], points: List[Finding]) -> Dict[str, Any]:
    reference = _reference(invoice)
    lines = "\n".join(f"- {f.message}" + (f" ({f.legal_ref})" if f.legal_ref else "") for f in points)
    body = (
        "Sehr geehrte Damen und Herren,\n\n"
        f"vielen Dank für {reference}. Bei der Prüfung sind uns folgende Punkte aufgefallen:\n\n"
        f"{lines}\n\n"
        "Damit wir die Vorsteuer geltend machen können, bitten wir Sie um eine berichtigte Rechnung "
        "(§ 31 Abs. 5 UStDV). Bis dahin können wir die Rechnung leider nicht zur Zahlung freigeben.\n\n"
        "Mit freundlichen Grüßen\n[Name]"
    )
    return {"mode": "offline", "subject": f"Bitte um Rechnungsberichtigung – {reference}", "body": body}


def _draft_live(invoice: Dict[str, Any], points: List[Finding]) -> Dict[str, Any]:
    request = {"rechnung": _facts(invoice),
               "punkte": [{"problem": f.message, "rechtsgrundlage": f.legal_ref} for f in points]}
    response = llm.create(
        "correction_request",
        max_tokens=2000,
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": {
                "type": "object",
                "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
                "required": ["subject", "body"],
                "additionalProperties": False,
            }},
        },
        system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(request, ensure_ascii=False)}],
    )
    data = json.loads(llm.text_of(response))
    return {"mode": "live", "subject": data["subject"], "body": data["body"]}

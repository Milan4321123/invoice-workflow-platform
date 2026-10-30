"""
GoBD rules for invoices as accounting records (Buchungsbelege).

The GoBD (BMF letter of 28.11.2019, amended 2024 for e-invoices) require that
records stay complete and unaltered for the retention period, and that every
change remains traceable (Rz. 58 ff., "Unveränderbarkeit"). In practice:

- An invoice that has entered the workflow is a record. It cannot be deleted
  before its retention period ends: 8 years for Buchungsbelege since the
  Bürokratieentlastungsgesetz IV (§147 Abs. 3 AO, from 1 January 2025),
  counted from the end of the calendar year the invoice was received in
  (§147 Abs. 4 AO).
- A file uploaded by mistake (wrong document, duplicate) that nobody has
  worked on yet may be removed. The audit log keeps a record of the deletion.
- Once approved, the booking-relevant content is final. Corrections need a
  new document (credit note / corrected invoice), not an edit.

Pure functions; database.py enforces them on every write.
"""
from datetime import date, datetime
from typing import Any, Dict, Optional

RETENTION_YEARS = 8

# Nobody has worked on the invoice yet, so it is still just an upload
DELETABLE_STATUSES = {"uploaded", "pending", "error"}

# The approver has signed off; the booking-relevant content is final
LOCKED_STATUSES = {"approved_by_bauleiter", "completed"}

# What an approval or booking relies on. Workflow fields (status, e-mail logs,
# Skonto decision, reminders) keep changing after approval and stay editable.
BOOKING_FIELDS = {
    "rechnungsempfaenger", "rechnungssteller", "projekt", "gewerk", "weiter_berechnen_an",
    "rechnungsbetrag", "rechnungseingang", "faelligkeit", "skonto_datum", "skonto_prozent",
    "rechnungsart", "kfw_anrechenbare_kosten",
    "rechnungsnummer", "rechnungsdatum", "leistungsdatum", "nettobetrag", "ust_satz", "ust_betrag",
    "lieferant_ust_id", "lieferant_steuernummer", "lieferant_iban", "reverse_charge_13b",
    "freistellung_48b_gueltig_bis", "file_name", "file_path",
}


class GoBDViolation(Exception):
    """A write the GoBD do not allow. The message explains why, in German, for the user."""


def _year(value: Any) -> Optional[int]:
    if not value:
        return None
    if isinstance(value, (date, datetime)):
        return value.year
    try:
        return int(str(value)[:4])
    except ValueError:
        return None


def retention_until(invoice: Dict[str, Any]) -> date:
    """Last day the invoice must be kept: 31 Dec of the receipt year + 8 years."""
    year = (_year(invoice.get("rechnungseingang"))
            or _year(invoice.get("created_at"))
            or date.today().year)
    return date(year + RETENTION_YEARS, 12, 31)


def deletion_blocked_reason(invoice: Dict[str, Any], today: Optional[date] = None) -> Optional[str]:
    today = today or date.today()
    if invoice.get("status", "uploaded") in DELETABLE_STATUSES:
        return None
    until = retention_until(invoice)
    if today > until:
        return None
    return (f"Die Rechnung ist ein Buchungsbeleg und muss bis {until:%d.%m.%Y} aufbewahrt werden "
            f"(§147 AO, GoBD). Löschen ist erst danach möglich; Korrekturen erfolgen über eine "
            f"Gutschrift oder Rechnungskorrektur.")


def _same(old: Any, new: Any) -> bool:
    if old is None or old == "":
        return new is None or new == ""
    if isinstance(old, (int, float)) or isinstance(new, (int, float)):
        try:
            return float(old) == float(new)
        except (TypeError, ValueError):
            return False
    return str(old) == str(new)


def changed_fields(before: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """{field: {"old": ..., "new": ...}} for every value the update really changes"""
    return {
        field: {"old": before.get(field), "new": value}
        for field, value in update.items()
        if field != "updated_at" and not _same(before.get(field), value)
    }


def edit_blocked_reason(before: Dict[str, Any], update: Dict[str, Any]) -> Optional[str]:
    if before.get("status") not in LOCKED_STATUSES:
        return None
    if "status" in update and update["status"] not in LOCKED_STATUSES:
        # Otherwise saving in the editor would move it back to "edited" and unlock it
        return ("Die Rechnung ist freigegeben; die Freigabe kann nicht zurückgenommen werden (GoBD Rz. 58 ff.). "
                "Für Korrekturen bitte eine Rechnungskorrektur anfordern.")
    locked = sorted(set(changed_fields(before, update)) & BOOKING_FIELDS)
    if not locked:
        return None
    return (f"Die Rechnung ist freigegeben; buchungsrelevante Angaben sind festgeschrieben (GoBD Rz. 58 ff.). "
            f"Nicht änderbar: {', '.join(locked)}. Für Korrekturen bitte eine Rechnungskorrektur anfordern.")

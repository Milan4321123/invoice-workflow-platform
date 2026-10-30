"""
GoBD endpoints: verify the change log and export data for a tax audit.

§147 Abs. 6 AO lets the tax office ask for the accounting data on a data
carrier in machine-readable form ("Datenträgerüberlassung", Z3). The export
is a ZIP of semicolon-separated UTF-8 CSV files plus a description of every
file and column, which is what auditors' tools (e.g. IDEA) import.
"""
import csv
from datetime import datetime, timezone
import io
import json
import zipfile

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from services.database import db_service
from services.audit import verify_entries
from services.gobd import RETENTION_YEARS

router = APIRouter()

INVOICE_COLUMNS = {
    "id": "Interne ID der Rechnung",
    "file_name": "Dateiname des Originalbelegs",
    "rechnungsnummer": "Rechnungsnummer des Lieferanten",
    "rechnungsdatum": "Rechnungsdatum (JJJJ-MM-TT)",
    "rechnungseingang": "Eingangsdatum (JJJJ-MM-TT)",
    "leistungsdatum": "Leistungsdatum (JJJJ-MM-TT)",
    "rechnungssteller": "Lieferant",
    "rechnungsempfaenger": "Rechnungsempfänger",
    "lieferant_ust_id": "USt-IdNr. des Lieferanten",
    "lieferant_steuernummer": "Steuernummer des Lieferanten",
    "nettobetrag": "Nettobetrag in EUR",
    "ust_satz": "Umsatzsteuersatz in Prozent",
    "ust_betrag": "Umsatzsteuerbetrag in EUR",
    "rechnungsbetrag": "Bruttobetrag in EUR",
    "reverse_charge_13b": "Steuerschuldnerschaft des Leistungsempfängers (§13b UStG)",
    "faelligkeit": "Fälligkeit (JJJJ-MM-TT)",
    "skonto_datum": "Ende der Skontofrist (JJJJ-MM-TT)",
    "skonto_prozent": "Skonto in Prozent",
    "projekt": "Projekt",
    "gewerk": "Gewerk",
    "status": "Bearbeitungsstatus",
    "approval_status": "Freigabestatus",
    "approved_at": "Zeitpunkt der Freigabe (UTC)",
    "e_rechnung_format": "Format der E-Rechnung, leer bei Papier/PDF",
    "created_at": "Zeitpunkt der Erfassung (UTC)",
}

AUDIT_COLUMNS = {
    "seq": "Laufende Nummer im Änderungsprotokoll",
    "invoice_id": "Interne ID der Rechnung",
    "action": "Art der Änderung",
    "actor": "Benutzer oder Freigabe-Link",
    "changes": "Geänderte Felder mit altem und neuem Wert (JSON)",
    "recorded_at": "Zeitpunkt (UTC, ISO 8601)",
    "prev_hash": "SHA-256 des vorherigen Eintrags",
    "entry_hash": "SHA-256 dieses Eintrags",
}


def _year_of(invoice):
    for field in ("rechnungseingang", "created_at"):
        if invoice.get(field):
            return int(str(invoice[field])[:4])
    return None


def _csv(rows, columns):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(columns), delimiter=";", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _description(year, invoice_count, audit_count, chain):
    lines = [
        f"Datenexport Eingangsrechnungen {year} nach §147 Abs. 6 AO",
        f"Erstellt: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC",
        "Zeichensatz: UTF-8, Trennzeichen: Semikolon, Dezimaltrennzeichen: Punkt",
        f"Aufbewahrungsfrist: {RETENTION_YEARS} Jahre ab Ende des Eingangsjahres (§147 Abs. 3 und 4 AO)",
        "",
        f"rechnungen.csv ({invoice_count} Zeilen): Eingangsrechnungen mit Eingangsjahr {year}",
        *[f"  {column}: {text}" for column, text in INVOICE_COLUMNS.items()],
        "",
        f"aenderungsprotokoll.csv ({audit_count} Zeilen): alle Änderungen an diesen Rechnungen",
        *[f"  {column}: {text}" for column, text in AUDIT_COLUMNS.items()],
        "",
        "Prüfung der Hash-Kette des gesamten Änderungsprotokolls: "
        + ("unverändert" if chain["valid"] else f"FEHLER: {chain['reason']}")
        + f" ({chain['checked']} Einträge geprüft)",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


@router.get("/audit/verify")
async def verify_audit_chain():
    """Recompute the hash chain of the whole change log"""
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    return db_service.audit.verify_chain()


@router.get("/exports/gobd")
async def export_for_tax_audit(year: int = Query(..., ge=2000, le=2100)):
    """ZIP with the year's incoming invoices, their change log and a file description"""
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")

    invoices = [i for i in db_service.get_invoices_for_export(list(INVOICE_COLUMNS)) if _year_of(i) == year]
    invoice_ids = {i["id"] for i in invoices}
    all_entries = db_service.audit.all_entries()
    chain = verify_entries(all_entries)
    entries = [
        {**e, "changes": json.dumps(e["changes"], ensure_ascii=False)}
        for e in all_entries if e["invoice_id"] in invoice_ids
    ]

    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("beschreibung.txt", _description(year, len(invoices), len(entries), chain))
        zf.writestr("rechnungen.csv", _csv(invoices, INVOICE_COLUMNS))
        zf.writestr("aenderungsprotokoll.csv", _csv(entries, AUDIT_COLUMNS))
    archive.seek(0)

    filename = f"gobd-export-eingangsrechnungen-{year}.zip"
    return StreamingResponse(archive, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})

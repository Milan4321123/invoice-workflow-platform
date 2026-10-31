"""
The pages behind the links in approval and Skonto e-mails.

The links carry a signed token instead of a login. Design rules:

- Opening a link never decides anything. GET shows the invoice (with its PDF)
  and a button; only the POST from that page acts. Mail security scanners
  (e.g. Microsoft Safe Links) open every link in a message to check it, so a
  decision on GET could approve invoices nobody looked at.
- A token decides once. It is claimed with a single conditional update
  ("set used_at where it is still empty"), so two clicks can't both win.
- Validation fails closed: if the token can't be checked against the
  database, the link doesn't work.
- The PDF link in the e-mail works for the token's lifetime (7 days), also
  after the decision; viewing changes nothing.
- Invoice data comes from suppliers, so everything shown is HTML-escaped.
"""
from datetime import datetime, timezone
import hashlib
from html import escape
import logging
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from api.routes.email_workflow import _get_invoice_data, _log_security_event
from services.audit import current_actor
from services.database import db_service
from services.email_service import email_service

logger = logging.getLogger(__name__)
router = APIRouter()

SKONTO_DECISIONS = {"taken": "Skonto nehmen", "missed": "Skonto nicht nehmen"}


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.astimezone()


def validate_token(token: str, ip_address: str, allow_used: bool = False) -> Optional[Dict[str, Any]]:
    """Decoded token if signature, database record, expiry and (unless allow_used) unused state check out."""
    try:
        data = jwt.decode(token, email_service.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as e:
        logger.warning(f"Approval link with invalid token: {e}")
        return None

    if not db_service.is_available:
        logger.error("Approval link checked while the database is unavailable; refusing")
        return None
    try:
        rows = db_service.client.table("approval_tokens").select("*").eq("token_hash", _hash(token)).execute().data
    except Exception as e:
        logger.error(f"Approval token lookup failed; refusing: {e}")
        return None
    if not rows:
        return None

    record = rows[0]
    if record.get("is_revoked"):
        return None
    if _parse_time(record["expires_at"]) < datetime.now(timezone.utc):
        return None
    if record.get("used_at") and not allow_used:
        return None
    return {**data, "used": bool(record.get("used_at"))}


def claim_token(token: str, ip_address: str) -> bool:
    """Mark the token used, atomically. False if someone else used it first."""
    rows = (db_service.client.table("approval_tokens")
            .update({"used_at": datetime.now(timezone.utc).isoformat(), "used_by_ip": ip_address})
            .eq("token_hash", _hash(token))
            .is_("used_at", "null")
            .execute()).data
    return bool(rows)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

def _euro(value: Any) -> str:
    try:
        return f"{float(value):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def _date(value: Any) -> str:
    text = str(value or "")
    return f"{text[8:10]}.{text[5:7]}.{text[:4]}" if len(text) >= 10 else "—"


def page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(status_code=status_code, content=f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{escape(title)}</title>
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; background: #f3f4f6; color: #111827; margin: 0; }}
  main {{ max-width: 960px; margin: 0 auto; padding: 24px 16px; }}
  h1 {{ font-size: 1.4rem; margin: 0 0 4px; }}
  .card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; margin-top: 16px; }}
  dl {{ display: grid; grid-template-columns: max-content 1fr; gap: 6px 16px; margin: 0; }}
  dt {{ color: #6b7280; }} dd {{ margin: 0; font-weight: 600; }}
  iframe {{ width: 100%; height: 70vh; border: 1px solid #d1d5db; border-radius: 8px; margin-top: 12px; }}
  label {{ display: block; font-weight: 600; margin-bottom: 6px; }}
  textarea {{ width: 100%; box-sizing: border-box; border: 1px solid #d1d5db; border-radius: 8px; padding: 8px; font: inherit; }}
  button {{ border: 0; border-radius: 8px; padding: 12px 20px; font-size: 1rem; font-weight: 600; color: #fff; cursor: pointer; margin-top: 12px; }}
  .approve {{ background: #15803d; }} .reject {{ background: #b91c1c; }} .neutral {{ background: #374151; }}
  .note {{ color: #4b5563; font-size: .9rem; }}
  .ok {{ background: #dcfce7; border-color: #86efac; }} .bad {{ background: #fee2e2; border-color: #fca5a5; }}
  a {{ color: #1d4ed8; }}
  :focus-visible {{ outline: 2px solid #2563eb; outline-offset: 2px; }}
</style>
</head>
<body><main>{body}</main></body>
</html>""")


def message(title: str, text: str, ok: bool = False, status_code: int = 200) -> HTMLResponse:
    return page(title, f'<div class="card {"ok" if ok else "bad"}"><h1>{escape(title)}</h1><p>{escape(text)}</p></div>'
                       f'<p class="note">Diese Seite kann geschlossen werden.</p>', status_code)


def _invalid_link() -> HTMLResponse:
    return message("Link nicht mehr gültig",
                   "Dieser Link ist abgelaufen, wurde bereits verwendet oder ist ungültig. "
                   "Bitte wenden Sie sich an die Rechnungsprüfung.", status_code=410)


def _summary(invoice: Dict[str, Any]) -> str:
    rows = [
        ("Lieferant", invoice.get("rechnungssteller")),
        ("Rechnungsnummer", invoice.get("rechnungsnummer")),
        ("Rechnungsdatum", _date(invoice.get("rechnungsdatum"))),
        ("Betrag (brutto)", _euro(invoice.get("rechnungsbetrag"))),
        ("Projekt", invoice.get("projekt_label") or invoice.get("projekt")),
        ("Gewerk", invoice.get("gewerk_label") or invoice.get("gewerk")),
    ]
    items = "".join(f"<dt>{escape(k)}</dt><dd>{escape(str(v or '—'))}</dd>" for k, v in rows)
    return f"<dl>{items}</dl>"


def _pdf_block(token: str, invoice: Dict[str, Any]) -> str:
    if not invoice.get("file_path"):
        return '<p class="note">Zu dieser Rechnung gibt es keine Datei.</p>'
    url = f"/api/approval/{escape(token)}/pdf"
    if (invoice.get("mime_type") or "").endswith("xml"):
        return (f'<p class="note">E-Rechnung (XRechnung): die Daten oben stammen aus dem XML. '
                f'<a href="{url}">XML herunterladen</a></p>')
    return (f'<iframe src="{url}" title="Rechnung als PDF"></iframe>'
            f'<p class="note"><a href="{url}" target="_blank" rel="noopener">PDF in neuem Fenster öffnen</a></p>')


def _invoice_with_labels(invoice_id: str) -> Optional[Dict[str, Any]]:
    from services.dropdown_labels import with_labels
    invoice = None
    result = db_service.get_invoice(invoice_id)
    if result.get("success"):
        invoice = with_labels(result["data"])
    return invoice


# ---------------------------------------------------------------------------
# Approval by the site manager
# ---------------------------------------------------------------------------

@router.get("/approval/{token}", response_class=HTMLResponse)
async def approval_page(token: str, request: Request):
    """Shows the invoice and its PDF with a button. Opening the link decides nothing."""
    data = validate_token(token, request.client.host if request.client else None, allow_used=True)
    if not data or data.get("action") not in ("approve", "reject"):
        return _invalid_link()
    invoice = _invoice_with_labels(data["invoice_id"])
    if not invoice:
        return message("Rechnung nicht gefunden", "Die Rechnung existiert nicht mehr.", status_code=404)

    approve = data["action"] == "approve"
    if data["used"] or invoice.get("status") != "in_review_by_bauleiter":
        decided = {"approved_by_bauleiter": "freigegeben", "rejected_by_bauleiter": "abgelehnt"}.get(invoice.get("status"))
        text = (f"Über diese Rechnung wurde bereits entschieden ({decided})." if decided
                else "Diese Rechnung wartet nicht auf eine Freigabe.")
        return page("Bereits entschieden", f'<h1>Bereits entschieden</h1><p>{escape(text)}</p>'
                                         f'<div class="card">{_summary(invoice)}{_pdf_block(token, invoice)}</div>')

    reason = ('<label for="comment">Grund der Ablehnung (Pflicht)</label>'
              '<textarea id="comment" name="comment" rows="3" required '
              'placeholder="z. B. Leistung im 2. OG noch nicht erbracht"></textarea>') if not approve else (
             '<label for="comment">Anmerkung (optional)</label><textarea id="comment" name="comment" rows="2"></textarea>')
    body = f"""
<h1>Rechnung {"freigeben" if approve else "ablehnen"}</h1>
<p class="note">Freigabe-Anfrage an {escape(data.get("user_email", ""))}. Bitte prüfen Sie Rechnung und Leistung.</p>
<div class="card">{_summary(invoice)}{_pdf_block(token, invoice)}</div>
<form class="card" method="post">
  {reason}
  <button type="submit" class="{"approve" if approve else "reject"}">
    {"Rechnung freigeben" if approve else "Rechnung ablehnen"}
  </button>
  <p class="note">Der Link ist bis zur Entscheidung gültig und kann nur einmal verwendet werden.</p>
</form>"""
    return page("Rechnung freigeben" if approve else "Rechnung ablehnen", body)


@router.post("/approval/{token}", response_class=HTMLResponse)
async def approval_decide(token: str, request: Request, comment: str = Form("")):
    ip_address = request.client.host if request.client else None
    data = validate_token(token, ip_address)
    if not data or data.get("action") not in ("approve", "reject"):
        return _invalid_link()
    invoice = await _get_invoice_data(data["invoice_id"])
    if not invoice or invoice.get("status") != "in_review_by_bauleiter":
        return message("Bereits entschieden", "Diese Rechnung wartet nicht mehr auf eine Freigabe.")

    approve = data["action"] == "approve"
    comment = comment.strip()
    if not approve and not comment:
        return message("Grund fehlt", "Bitte geben Sie einen Grund für die Ablehnung an und senden Sie das Formular erneut.",
                       status_code=400)
    if not claim_token(token, ip_address):
        return _invalid_link()

    current_actor.set(f"E-Mail-Link {data['user_email']}")
    result = db_service.update_invoice_bauleiter_decision(
        invoice_id=data["invoice_id"],
        decision="approved" if approve else "rejected",
        decided_by=data["user_email"],
        decision_notes=comment or None,
        method="email_link",
    )
    if not result.get("success"):
        logger.error(f"Decision via e-mail link failed for {data['invoice_id']}: {result.get('error')}")
        return message("Fehler", "Die Entscheidung konnte nicht gespeichert werden. Bitte die Rechnungsprüfung informieren.",
                       status_code=500)

    await _log_security_event(event_type=f"approval_{data['action']}", ip_address=ip_address,
                              user_email=data["user_email"], invoice_id=data["invoice_id"],
                              event_data={"via": "email_link"})
    return message("Rechnung freigegeben" if approve else "Rechnung abgelehnt",
                   "Vielen Dank. Ihre Entscheidung wurde gespeichert und protokolliert.", ok=True)


@router.get("/approval/{token}/pdf")
async def approval_pdf(token: str, request: Request):
    """The invoice file for the linked invoice; valid for the token's lifetime, also after the decision."""
    data = validate_token(token, request.client.host if request.client else None, allow_used=True)
    if not data:
        return _invalid_link()
    invoice = await _get_invoice_data(data["invoice_id"])
    if not invoice or not invoice.get("file_path"):
        return message("Keine Datei", "Zu dieser Rechnung gibt es keine Datei.", status_code=404)
    bucket, name = db_service._storage_location(invoice["file_path"])
    try:
        content = db_service.client.storage.from_(bucket).download(name)
    except Exception as e:
        logger.error(f"Invoice file download failed: {e}")
        return message("Datei nicht verfügbar", "Die Datei konnte nicht geladen werden.", status_code=502)
    is_xml = name.lower().endswith(".xml")
    return Response(content=content, media_type="application/xml" if is_xml else "application/pdf",
                    headers={"Content-Disposition": f'{"attachment" if is_xml else "inline"}; filename="{name}"',
                             "Cache-Control": "private, no-store", "X-Robots-Tag": "noindex",
                             # Shown inside the approval page (same origin), nowhere else
                             "X-Frame-Options": "SAMEORIGIN",
                             "Content-Security-Policy": "frame-ancestors 'self'"})


# ---------------------------------------------------------------------------
# Skonto decision by accounting
# ---------------------------------------------------------------------------

@router.get("/email/skonto-decision", response_class=HTMLResponse)
async def skonto_page(token: str, decision: str, request: Request):
    data = validate_token(token, request.client.host if request.client else None)
    if not data or decision not in SKONTO_DECISIONS:
        return _invalid_link()
    invoice = _invoice_with_labels(data["invoice_id"])
    if not invoice:
        return message("Rechnung nicht gefunden", "Die Rechnung existiert nicht mehr.", status_code=404)
    saving = (float(invoice.get("rechnungsbetrag") or 0) * float(invoice.get("skonto_prozent") or 0) / 100)
    body = f"""
<h1>{escape(SKONTO_DECISIONS[decision])}?</h1>
<div class="card">{_summary(invoice)}
  <p>Skonto {escape(str(invoice.get("skonto_prozent") or "—"))} % bis {_date(invoice.get("skonto_datum"))}:
     Ersparnis {_euro(saving)}</p>
</div>
<form class="card" method="post">
  <button type="submit" class="{"approve" if decision == "taken" else "neutral"}">{escape(SKONTO_DECISIONS[decision])}</button>
</form>"""
    return page("Skonto-Entscheidung", body)


@router.post("/email/skonto-decision", response_class=HTMLResponse)
async def skonto_decide(token: str, decision: str, request: Request):
    ip_address = request.client.host if request.client else None
    data = validate_token(token, ip_address)
    if not data or decision not in SKONTO_DECISIONS:
        return _invalid_link()
    invoice = await _get_invoice_data(data["invoice_id"])
    if not invoice or not invoice.get("skonto_datum"):
        return message("Kein Skonto", "Diese Rechnung hat kein Skonto.", status_code=404)
    if not claim_token(token, ip_address):
        return _invalid_link()

    current_actor.set(f"E-Mail-Link {data['user_email']}")
    savings = None
    if decision == "taken":
        savings = round(float(invoice.get("rechnungsbetrag") or 0) * float(invoice.get("skonto_prozent") or 0) / 100, 2)
    result = db_service.update_skonto_decision(invoice_id=data["invoice_id"], decision=decision, actual_savings=savings,
                                               decision_timestamp=datetime.now(timezone.utc).isoformat(),
                                               decision_email=data["user_email"])
    if not result.get("success"):
        return message("Fehler", "Die Entscheidung konnte nicht gespeichert werden.", status_code=500)
    await _log_security_event(event_type="skonto_decision_processed", ip_address=ip_address,
                              user_email=data["user_email"], invoice_id=data["invoice_id"],
                              event_data={"decision": decision, "actual_savings": savings})
    text = (f"Skonto wird genommen. Ersparnis: {_euro(savings)}." if decision == "taken"
            else "Skonto wird nicht genommen; die Rechnung wird zum Fälligkeitsdatum voll bezahlt.")
    return message("Entscheidung gespeichert", text, ok=True)

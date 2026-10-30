"""
Data subject rights and storage limitation (DSGVO).

People whose data the platform holds are mostly staff and approvers: their
e-mail address appears on invoices they edited or approved, in the e-mail
send log, on approval links and in security events, sometimes with an IP
address.

- Access and portability (Art. 15, 20): everything stored under an e-mail
  address, as JSON.
- Erasure (Art. 17): operational records are pseudonymised. What belongs to
  an accounting record under retention (who edited and approved an invoice,
  the change log) has to stay: Art. 17 Abs. 3 lit. b DSGVO with §147 AO. The
  report says what was kept, why and until when.
- Storage limitation (Art. 5 Abs. 1 lit. e): IP addresses are only needed to
  investigate misuse of approval links, so they are removed after 30 days.
"""
import asyncio
from datetime import date, datetime, timedelta, timezone
import hashlib
import logging
import os
from typing import Any, Callable, Dict, List

from services.gobd import retention_until

logger = logging.getLogger(__name__)

ERASED = "[gelöscht]"
IP_RETENTION_DAYS = int(os.getenv("IP_RETENTION_DAYS", "30"))

# (table, e-mail columns, what it is) - every place an e-mail address is stored
EMAIL_LOCATIONS = [
    ("users", ["email"], "Benutzerkonto"),
    ("invoices_clean", ["bauleiter_email", "editor_email", "rechnungspruefung"], "Rechnungen, an denen die Person beteiligt war"),
    ("email_audit_log", ["recipient_email"], "Versandprotokoll der E-Mails"),
    ("approval_tokens", ["user_email"], "Freigabe-Links"),
    ("security_events", ["user_email"], "Sicherheitsprotokoll"),
]


def _like_exact(email: str) -> str:
    """ilike pattern for an exact, case-insensitive match (_ and % are wildcards otherwise)"""
    return email.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def subject_hash(email: str) -> str:
    """Lets the accountability log show which request was handled without storing the address again"""
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()[:16]


class PrivacyService:
    def __init__(self, client: Callable[[], Any]):
        self._client = client

    def _rows(self, table: str, column: str, email: str) -> List[Dict[str, Any]]:
        return (self._client().table(table).select("*").ilike(column, _like_exact(email)).execute()).data or []

    def _rows_by_location(self, email: str) -> Dict[str, List[Dict[str, Any]]]:
        found: Dict[str, List[Dict[str, Any]]] = {}
        for table, columns, _ in EMAIL_LOCATIONS:
            rows: Dict[Any, Dict[str, Any]] = {}
            for column in columns:
                for row in self._rows(table, column, email):
                    rows[row.get("id")] = row
            found[table] = list(rows.values())
        return found

    def _actors(self, email: str, users: List[Dict[str, Any]]) -> List[str]:
        return [f"E-Mail-Link {email}"] + [u["username"] for u in users if u.get("username")]

    # ------------------------------------------------------------------
    # Art. 15 / 20
    # ------------------------------------------------------------------

    def subject_access(self, email: str) -> Dict[str, Any]:
        found = self._rows_by_location(email)
        for user in found["users"]:
            user.pop("hashed_password", None)

        audit_entries = []
        for actor in self._actors(email, found["users"]):
            audit_entries += (self._client().table("invoice_audit_log")
                              .select("seq,invoice_id,action,actor,changes,recorded_at")
                              .ilike("actor", _like_exact(actor)).execute()).data or []

        labels = {table: label for table, _, label in EMAIL_LOCATIONS}
        return {
            "betroffene_person": email,
            "erstellt_am": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "rechtsgrundlage": "Art. 15 und Art. 20 DSGVO",
            "kategorien": {
                **{labels[table]: rows for table, rows in found.items()},
                "Änderungsprotokoll (Aktionen der Person)": audit_entries,
            },
        }

    # ------------------------------------------------------------------
    # Art. 17
    # ------------------------------------------------------------------

    def erase(self, email: str, today: date = None) -> Dict[str, Any]:
        today = today or date.today()
        found = self._rows_by_location(email)
        client = self._client()
        erased: Dict[str, int] = {}
        retained: List[Dict[str, Any]] = []

        for user in found["users"]:
            client.table("users").update({"email": None, "full_name": None, "is_active": False}).eq("id", user["id"]).execute()
        erased["Benutzerkonto (deaktiviert, Name und E-Mail entfernt)"] = len(found["users"])

        for row in found["email_audit_log"]:
            client.table("email_audit_log").update({"recipient_email": ERASED, "provider_response": None}).eq("id", row["id"]).execute()
        erased["Versandprotokoll der E-Mails"] = len(found["email_audit_log"])

        for row in found["approval_tokens"]:
            client.table("approval_tokens").update({"user_email": ERASED, "used_by_ip": None}).eq("id", row["id"]).execute()
        erased["Freigabe-Links"] = len(found["approval_tokens"])

        for row in found["security_events"]:
            client.table("security_events").update({"user_email": ERASED, "ip_address": None}).eq("id", row["id"]).execute()
        erased["Sicherheitsprotokoll"] = len(found["security_events"])

        if found["invoices_clean"]:
            until = max(retention_until(invoice) for invoice in found["invoices_clean"])
            retained.append({
                "kategorie": "Rechnungen, an denen die Person beteiligt war",
                "anzahl": len(found["invoices_clean"]),
                "grund": "Wer eine Rechnung geprüft und freigegeben hat, gehört zum Buchungsbeleg und muss "
                         "aufbewahrt werden (Art. 17 Abs. 3 lit. b DSGVO i. V. m. §147 AO, GoBD). Die Daten "
                         "werden bis dahin nur noch für diesen Zweck verwendet.",
                "aufbewahrt_bis": until.isoformat(),
            })
        retained.append({
            "kategorie": "Änderungsprotokoll",
            "anzahl": None,
            "grund": "Das Protokoll ist unveränderbar und Teil der GoBD-Dokumentation "
                     "(Art. 17 Abs. 3 lit. b DSGVO i. V. m. §147 AO).",
            "aufbewahrt_bis": None,
        })

        return {"betroffene_person": email, "geloescht": erased, "aufbewahrt": retained}

    # ------------------------------------------------------------------
    # Art. 5 Abs. 1 lit. e
    # ------------------------------------------------------------------

    def remove_old_ip_addresses(self, older_than_days: int = IP_RETENTION_DAYS) -> Dict[str, int]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        client = self._client()
        removed = {}
        for table, column in (("security_events", "ip_address"), ("approval_tokens", "used_by_ip")):
            rows = (client.table(table).update({column: None})
                    .lt("created_at", cutoff).not_.is_(column, "null").execute()).data or []
            removed[table] = len(rows)
        return removed


async def run_ip_cleanup_daily(service: "PrivacyService") -> None:
    while True:
        try:
            removed = service.remove_old_ip_addresses()
            if any(removed.values()):
                logger.info(f"🧹 Removed IP addresses older than {IP_RETENTION_DAYS} days: {removed}")
        except Exception as e:
            logger.error(f"❌ IP address cleanup failed: {e}")
        await asyncio.sleep(24 * 60 * 60)

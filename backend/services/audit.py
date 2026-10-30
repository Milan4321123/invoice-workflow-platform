"""
Append-only, tamper-evident change log for invoices.

GoBD Rz. 58 ff. require that a change to a record never hides what was there
before. Every create, change and deletion of an invoice is written here with
who did it, when, and each field's old and new value.

Each entry carries the SHA-256 hash of its content plus the previous entry's
hash. Editing or removing an old entry breaks the chain from that point on,
which verify_chain() reports. The database also rejects UPDATE, DELETE and
TRUNCATE on the table (migration 006), so the hash chain is a second line of
defence against someone with direct database access.
"""
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

AUDIT_TABLE = "invoice_audit_log"
GENESIS_HASH = "0" * 64

# Who is acting in the current request. The auth dependency sets the user name;
# approval links set the approver's e-mail; background jobs stay "system".
current_actor: ContextVar[str] = ContextVar("current_actor", default="system")


def _canonical(value: Any) -> Any:
    """JSON-safe copy, so the hash is computed over exactly what the database stores"""
    return json.loads(json.dumps(value, default=str))


def entry_hash(entry: Dict[str, Any], prev_hash: str) -> str:
    content = {key: entry[key] for key in ("seq", "invoice_id", "action", "actor", "changes", "recorded_at")}
    payload = prev_hash + json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, client: Callable[[], Any]):
        self._client = client

    def _last_entry(self) -> Optional[Dict[str, Any]]:
        rows = (self._client().table(AUDIT_TABLE)
                .select("seq,entry_hash")
                .order("seq", desc=True)
                .limit(1)
                .execute()).data
        return rows[0] if rows else None

    def record(self, invoice_id: str, action: str, changes: Dict[str, Any],
               actor: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Append an entry. Retries if another writer took the same sequence number."""
        for _ in range(3):
            last = self._last_entry()
            prev_hash = last["entry_hash"] if last else GENESIS_HASH
            entry = {
                "seq": (last["seq"] + 1) if last else 1,
                "invoice_id": str(invoice_id),
                "action": action,
                "actor": actor or current_actor.get(),
                "changes": _canonical(changes),
                "recorded_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                "prev_hash": prev_hash,
            }
            entry["entry_hash"] = entry_hash(entry, prev_hash)
            try:
                self._client().table(AUDIT_TABLE).insert(entry).execute()
                return entry
            except Exception as e:
                if "duplicate key" not in str(e) and "23505" not in str(e):
                    logger.error(f"❌ Audit log write failed for invoice {invoice_id} ({action}): {e}")
                    return None
        logger.error(f"❌ Audit log write for invoice {invoice_id} ({action}) lost three sequence races")
        return None

    def entries_for(self, invoice_id: str) -> List[Dict[str, Any]]:
        return (self._client().table(AUDIT_TABLE)
                .select("seq,action,actor,changes,recorded_at")
                .eq("invoice_id", invoice_id)
                .order("seq")
                .execute()).data or []

    def all_entries(self, page_size: int = 1000) -> List[Dict[str, Any]]:
        entries, start = [], 0
        while True:
            page = (self._client().table(AUDIT_TABLE)
                    .select("*")
                    .order("seq")
                    .range(start, start + page_size - 1)
                    .execute()).data or []
            entries.extend(page)
            if len(page) < page_size:
                return entries
            start += page_size

    def verify_chain(self) -> Dict[str, Any]:
        return verify_entries(self.all_entries())


def verify_entries(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Recompute every hash in sequence order. The first mismatch is where tampering starts."""
    prev_hash = GENESIS_HASH
    for expected_seq, entry in enumerate(entries, start=1):
        if entry["seq"] != expected_seq:
            return {"valid": False, "checked": expected_seq - 1, "first_invalid_seq": expected_seq,
                    "reason": f"Eintrag {expected_seq} fehlt"}
        if entry["prev_hash"] != prev_hash or entry_hash(entry, prev_hash) != entry["entry_hash"]:
            return {"valid": False, "checked": expected_seq - 1, "first_invalid_seq": entry["seq"],
                    "reason": f"Eintrag {entry['seq']} wurde verändert"}
        prev_hash = entry["entry_hash"]
    return {"valid": True, "checked": len(entries), "first_invalid_seq": None, "reason": None}

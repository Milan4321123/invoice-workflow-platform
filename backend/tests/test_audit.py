import pytest

from services.audit import AuditLog, current_actor, verify_entries
from tests.fakes import FakeSupabase, FakeTable


@pytest.fixture
def log():
    client = FakeSupabase(invoice_audit_log=FakeTable(unique=("seq", "entry_hash")))
    audit = AuditLog(lambda: client)
    audit.record("inv-1", "created", {"rechnungsbetrag": {"old": None, "new": 1190}})
    audit.record("inv-1", "updated", {"rechnungsbetrag": {"old": 1190, "new": 1200}})
    audit.record("inv-2", "created", {"file_name": {"old": None, "new": "a.pdf"}})
    return audit, client.table("invoice_audit_log")


def test_entries_are_chained(log):
    audit, table = log
    assert [row["seq"] for row in table.rows] == [1, 2, 3]
    assert table.rows[1]["prev_hash"] == table.rows[0]["entry_hash"]
    assert audit.verify_chain() == {"valid": True, "checked": 3, "first_invalid_seq": None, "reason": None}


def test_history_per_invoice(log):
    audit, _ = log
    assert [e["action"] for e in audit.entries_for("inv-1")] == ["created", "updated"]


def test_edited_entry_breaks_the_chain(log):
    audit, table = log
    table.rows[1]["changes"]["rechnungsbetrag"]["new"] = 1100  # someone rewrites history
    result = audit.verify_chain()
    assert result["valid"] is False
    assert result["first_invalid_seq"] == 2


def test_removed_entry_is_detected(log):
    _, table = log
    del table.rows[1]
    result = verify_entries(table.rows)
    assert result["valid"] is False
    assert "fehlt" in result["reason"]


def test_actor_comes_from_the_request(log):
    audit, table = log
    token = current_actor.set("anna")
    try:
        audit.record("inv-1", "updated", {})
    finally:
        current_actor.reset(token)
    assert table.rows[-1]["actor"] == "anna"
    assert table.rows[0]["actor"] == "system"


def test_values_are_stored_json_safe(log):
    from datetime import date
    audit, table = log
    audit.record("inv-1", "updated", {"faelligkeit": {"old": None, "new": date(2026, 11, 14)}})
    assert table.rows[-1]["changes"]["faelligkeit"]["new"] == "2026-11-14"
    assert audit.verify_chain()["valid"]

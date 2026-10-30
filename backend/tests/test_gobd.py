from datetime import date

import pytest

from services.gobd import changed_fields, deletion_blocked_reason, edit_blocked_reason, retention_until


def test_retention_is_eight_years_from_end_of_receipt_year():
    assert retention_until({"rechnungseingang": "2025-03-01"}) == date(2033, 12, 31)


def test_retention_falls_back_to_upload_date():
    assert retention_until({"created_at": "2026-10-30T09:00:00+00:00"}) == date(2034, 12, 31)


@pytest.mark.parametrize("status", ["uploaded", "pending", "error"])
def test_untouched_uploads_may_be_deleted(status):
    assert deletion_blocked_reason({"status": status, "rechnungseingang": "2026-10-01"}) is None


@pytest.mark.parametrize("status", ["edited", "in_review_by_bauleiter", "approved_by_bauleiter", "completed"])
def test_records_in_the_workflow_are_kept(status):
    reason = deletion_blocked_reason({"status": status, "rechnungseingang": "2026-10-01"}, today=date(2026, 10, 30))
    assert "31.12.2034" in reason


def test_records_may_go_after_retention_ends():
    invoice = {"status": "completed", "rechnungseingang": "2016-05-01"}
    assert deletion_blocked_reason(invoice, today=date(2025, 1, 1)) is None


def test_changed_fields_ignores_equal_values_in_other_types():
    before = {"rechnungsbetrag": "1190.00", "projekt": "omega", "faelligkeit": None}
    update = {"rechnungsbetrag": 1190, "projekt": "omega", "faelligkeit": "", "updated_at": "now"}
    assert changed_fields(before, update) == {}


def test_changed_fields_reports_old_and_new():
    assert changed_fields({"rechnungsbetrag": 1190}, {"rechnungsbetrag": 1200}) == {
        "rechnungsbetrag": {"old": 1190, "new": 1200}}


@pytest.mark.parametrize("status", ["approved_by_bauleiter", "completed"])
def test_approved_amounts_are_locked(status):
    reason = edit_blocked_reason({"status": status, "rechnungsbetrag": 1190}, {"rechnungsbetrag": 1100})
    assert "rechnungsbetrag" in reason


def test_workflow_fields_stay_editable_after_approval():
    before = {"status": "approved_by_bauleiter", "skonto_decision": "pending"}
    assert edit_blocked_reason(before, {"skonto_decision": "taken", "actual_skonto_savings": 23.8}) is None


def test_saving_unchanged_values_after_approval_is_fine():
    """The editor sends every field on save; only real changes count."""
    before = {"status": "completed", "rechnungsbetrag": 1190, "projekt": "omega"}
    assert edit_blocked_reason(before, {"rechnungsbetrag": 1190.0, "projekt": "omega"}) is None


def test_unapproved_invoices_are_editable():
    assert edit_blocked_reason({"status": "edited", "rechnungsbetrag": 1190}, {"rechnungsbetrag": 1100}) is None


def test_approval_cannot_be_reset_to_editing():
    assert "Freigabe" in edit_blocked_reason({"status": "approved_by_bauleiter"}, {"status": "edited"})


def test_approved_invoice_can_be_completed():
    assert edit_blocked_reason({"status": "approved_by_bauleiter"}, {"status": "completed"}) is None

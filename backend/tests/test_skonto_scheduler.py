from datetime import date, datetime, timedelta

import pytest

from services.skonto_scheduler import SkontoReminderConfig, SkontoSchedulerService


@pytest.fixture
def scheduler():
    return SkontoSchedulerService(SkontoReminderConfig())


def iso(days_from_today):
    return (date.today() + timedelta(days=days_from_today)).isoformat()


@pytest.mark.parametrize("days_left, level", [(0, 1), (1, 1), (2, 3), (3, 3), (5, 7), (7, 7), (8, None)])
def test_urgency_levels(scheduler, days_left, level):
    assert scheduler._urgency_level(days_left) == level


def test_first_reminder_is_due_inside_window(scheduler):
    assert scheduler._reminder_due({"skonto_datum": iso(5)})


def test_no_reminder_outside_window(scheduler):
    assert not scheduler._reminder_due({"skonto_datum": iso(30)})


def test_one_reminder_per_level(scheduler):
    """Sent at '7 days' level today, still at that level: don't send again."""
    invoice = {
        "skonto_datum": iso(6),
        "skonto_reminder_sent": True,
        "skonto_reminder_sent_at": datetime.now().isoformat(),
    }
    assert not scheduler._reminder_due(invoice)


def test_reminder_again_when_more_urgent(scheduler):
    invoice = {
        "skonto_datum": iso(1),
        "skonto_reminder_sent": True,
        "skonto_reminder_sent_at": (datetime.now() - timedelta(days=5)).isoformat(),
    }
    assert scheduler._reminder_due(invoice)


def test_reminders_go_to_accounting(scheduler):
    assert scheduler.skonto_recipient({"bauleiter_email": "bau@example.com"}) == "buchhaltung@example.com"


def test_falls_back_to_bauleiter_without_accounting_address(scheduler):
    scheduler.config.default_recipient_email = None
    assert scheduler.skonto_recipient({"bauleiter_email": "bau@example.com"}) == "bau@example.com"


def test_deduplicate_keeps_first_occurrence(scheduler):
    merged = scheduler._deduplicate_invoices([[{"id": "a"}, {"id": "b"}], [{"id": "a"}, {"id": "c"}]])
    assert [i["id"] for i in merged] == ["a", "b", "c"]

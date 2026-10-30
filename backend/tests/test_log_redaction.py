import logging

import pytest

from services.log_redaction import RedactingFilter, redact


@pytest.mark.parametrize("text, expected", [
    ("sent to anna.schmidt@muster-bau.de", "sent to a***@muster-bau.de"),
    ("IBAN DE89370400440532013000 saved", "IBAN DE**…3000 saved"),
    ("IBAN DE89 3704 0044 0532 0130 00 saved", "IBAN DE**…3000 saved"),
    ("AT611904300234573201", "AT**…3201"),
    ("invoice 2026-4711 for 1190.00 EUR", "invoice 2026-4711 for 1190.00 EUR"),
    ("VAT ID DE123456788", "VAT ID DE123456788"),
])
def test_redact(text, expected):
    assert redact(text) == expected


def test_filter_rewrites_formatted_records():
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "mail to %s", ("bau@example.com",), None)
    assert RedactingFilter().filter(record)
    assert record.getMessage() == "mail to b***@example.com"

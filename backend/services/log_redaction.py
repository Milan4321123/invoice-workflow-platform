"""
Keeps personal data out of the application logs (DSGVO Art. 5 Abs. 1 lit. c, Art. 32).

Logs are shipped to the hosting provider, kept longer than anyone plans and
read by people who don't need to know which supplier's IBAN or which
approver's e-mail address was involved. Masking them at the handler means a
careless log line elsewhere can't leak them.

E-mail addresses keep their domain (useful when debugging delivery), IBANs
keep country code and last four digits (enough to tell accounts apart).
"""
import logging
import re

EMAIL = re.compile(r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")
# IBAN with or without the usual groups of four: DE89 3704 0044 0532 0130 00
IBAN = re.compile(r"\b([A-Z]{2})\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b")


def redact(text: str) -> str:
    text = EMAIL.sub(lambda m: f"{m.group(1)}***@{m.group(2)}", text)
    return IBAN.sub(lambda m: f"{m.group(1)}**…{re.sub(r'[ ]', '', m.group(0))[-4:]}", text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact(message)
        if redacted != message:
            record.msg, record.args = redacted, None
        return True


def install() -> None:
    """Attach the filter to every handler on the root logger (uvicorn's included)."""
    redacting = RedactingFilter()
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access"):
        for handler in logging.getLogger(name).handlers:
            if not any(isinstance(f, RedactingFilter) for f in handler.filters):
                handler.addFilter(redacting)

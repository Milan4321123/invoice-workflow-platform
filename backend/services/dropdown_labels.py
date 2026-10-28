"""
Display labels for dropdown fields.
Invoices store the option value (e.g. 'elektro_mueller'); people should see the
label ('Elektro Müller GmbH') in the dashboard, the Prüfbericht and in emails.
"""
import logging
import time
from typing import Any, Dict, Optional

from services.database import db_service

logger = logging.getLogger(__name__)

DROPDOWN_FIELDS = ("rechnungsempfaenger", "rechnungssteller", "projekt", "gewerk", "weiter_berechnen_an")
_CACHE_SECONDS = 30
_cache: Dict[str, Any] = {"loaded_at": 0.0, "labels": {}}


def _load_labels() -> Dict[str, Dict[str, str]]:
    from api.routes.dropdowns import FALLBACK_DROPDOWN_OPTIONS

    labels = {field: {o["value"]: o["label"] for o in options}
              for field, options in FALLBACK_DROPDOWN_OPTIONS.items()}
    try:
        # Inactive options too, so invoices that use a removed option still show its name
        rows = db_service.client.table("dropdown_options").select("field_name,value,label").execute().data or []
        for row in rows:
            labels.setdefault(row["field_name"], {})[row["value"]] = row["label"]
    except Exception as e:
        logger.warning(f"Could not load dropdown labels, showing stored values: {e}")
    return labels


def _labels() -> Dict[str, Dict[str, str]]:
    if time.time() - _cache["loaded_at"] > _CACHE_SECONDS:
        _cache["labels"] = _load_labels()
        _cache["loaded_at"] = time.time()
    return _cache["labels"]


def display_label(field: str, value: Optional[str]) -> Optional[str]:
    """Label for a stored dropdown value; unknown or free-text values are returned unchanged"""
    if not value:
        return value
    return _labels().get(field, {}).get(value, value)


def with_labels(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """Add '<field>_label' next to every dropdown field of an invoice"""
    for field in DROPDOWN_FIELDS:
        if field in invoice:
            invoice[f"{field}_label"] = display_label(field, invoice.get(field))
    return invoice


def invalidate() -> None:
    """Call after dropdown options change so new labels show up immediately"""
    _cache["loaded_at"] = 0.0

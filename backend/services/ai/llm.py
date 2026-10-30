"""
The one place the platform talks to Claude.

Two modes, decided per request:

- live: AI_FEATURES_ENABLED=true and an Anthropic credential is configured.
  Sending invoice data to an AI provider is a DSGVO decision (processor
  agreement, transfer basis), so it is never on by default.
- offline: everything else. Each feature has a deterministic fallback
  (text extraction and rules, lexical retrieval, templates), so the
  workflow keeps working and nothing leaves the server.

Every live call is recorded in ai_requests with feature, model, tokens and
estimated cost, but never the prompt or the answer (data minimisation).
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

MODEL = os.getenv("AI_MODEL", "claude-opus-5-5")
# Re-runs a request declined by a safety classifier on a suitable model, server-side
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# USD per million tokens (input, output), for the cost estimate only
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

_client: Any = None


class AIUnavailable(Exception):
    """Live AI was requested but isn't configured; callers use the offline path."""


class AIRefused(Exception):
    """The model (and its fallback) declined the request."""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, usage: Any) -> None:
        self.input_tokens += getattr(usage, "input_tokens", 0) or 0
        self.output_tokens += getattr(usage, "output_tokens", 0) or 0

    def cost_usd(self, model: str = MODEL) -> float:
        price_in, price_out = PRICES.get(model, PRICES["claude-opus-5-5"])
        return round((self.input_tokens * price_in + self.output_tokens * price_out) / 1_000_000, 6)


def enabled() -> bool:
    return os.getenv("AI_FEATURES_ENABLED", "false").lower() == "true"


def has_credentials() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")) or _client is not None


def mode() -> str:
    return "live" if enabled() and has_credentials() else "offline"


def set_client(client: Any) -> None:
    """Tests inject a fake client here; production builds the real one lazily."""
    global _client
    _client = client


def client() -> Any:
    global _client
    if mode() != "live":
        raise AIUnavailable("AI is not configured for live use")
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()
    return _client


def create(feature: str, **params: Any) -> Any:
    """
    messages.create with the platform defaults: the configured model,
    server-side refusal fallback, and usage recording. Raises AIRefused if
    the request was still declined after the fallback.
    """
    params.setdefault("model", MODEL)
    response = client().beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **params)
    usage = Usage()
    usage.add(response.usage)
    record_usage(feature, getattr(response, "model", params["model"]), usage)
    if response.stop_reason == "refusal":
        raise AIRefused(getattr(getattr(response, "stop_details", None), "explanation", None) or "declined")
    return response


def text_of(response: Any) -> str:
    return "".join(block.text for block in response.content if block.type == "text")


def record_usage(feature: str, model: str, usage: Usage, user: Optional[str] = None) -> None:
    """Best effort: a failed usage log must never break the feature."""
    try:
        from services.audit import current_actor
        from services.database import db_service

        if not db_service.is_available:
            return
        db_service.client.table("ai_requests").insert({
            "feature": feature,
            "model": model,
            "actor": user or current_actor.get(),
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_usd": usage.cost_usd(model),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.warning(f"Could not record AI usage: {e}")

"""
AI endpoints. Every one works offline (no model configured) and says which
mode answered, so the UI can label AI-generated content (EU AI Act Art. 50).
"""
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field

from services.ai import agent, correction, extraction, llm, rag
from services.ai.gemini import GeminiError, GeminiRateLimit
from services.audit import current_actor
from services.database import db_service
from services.invoice_compliance import check_stored_invoice

logger = logging.getLogger(__name__)
router = APIRouter()


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


class AgentTurn(Question):
    history: List[Dict[str, Any]] = Field(default_factory=list, max_length=200)


def _guard(call):
    """Turn provider problems into a clear 503/422 instead of a 500."""
    import anthropic
    try:
        return call()
    except llm.AIRefused as e:
        raise HTTPException(status_code=422, detail=f"Die KI hat die Anfrage abgelehnt: {e}")
    except GeminiRateLimit:
        raise HTTPException(status_code=503, detail="Das Gratis-Kontingent von Gemini ist gerade aufgebraucht. "
                                                    "Bitte in einer Minute noch einmal versuchen.")
    except GeminiError as e:
        logger.error(f"AI provider error: {e}")
        raise HTTPException(status_code=503, detail="Der KI-Dienst ist nicht erreichbar.")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=503, detail="Der KI-Dienst ist gerade ausgelastet. Bitte gleich noch einmal versuchen.")
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as e:
        logger.error(f"AI provider error: {e}")
        raise HTTPException(status_code=503, detail="Der KI-Dienst ist nicht erreichbar.")


def _invoice(invoice_id: str) -> Dict[str, Any]:
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    result = db_service.get_invoice(invoice_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {**result["data"], "id": invoice_id}


@router.get("/ai/status")
async def ai_status():
    return {"mode": llm.mode(), "provider": llm.provider(), "model": llm.model(), "enabled": llm.enabled(),
            "has_credentials": llm.has_credentials(), "offline_reason": llm.offline_reason()}


@router.post("/ai/ask")
async def ask_regulations(body: Question):
    """Question about the tax rules, answered from the statutes with citations"""
    return _guard(lambda: rag.ask(body.question))


@router.post("/ai/agent")
async def ask_agent(body: AgentTurn):
    """One turn with the AP assistant. Send back `history` from the previous answer unchanged."""
    return _guard(lambda: agent.answer(body.question, body.history, db_service))


@router.post("/invoices/{invoice_id}/ai-extract")
async def extract_fields(invoice_id: str = Path(...)):
    """Suggested field values for a PDF without e-invoice data. Nothing is saved."""
    invoice = _invoice(invoice_id)
    if invoice.get("e_rechnung_format") or (invoice.get("mime_type") == "application/xml"):
        raise HTTPException(status_code=409, detail="E-Rechnung: die Felder stammen bereits aus dem XML.")
    if not invoice.get("file_path"):
        raise HTTPException(status_code=404, detail="Zu dieser Rechnung gibt es keine Datei.")
    bucket, name = db_service._storage_location(invoice["file_path"])
    pdf = db_service.client.storage.from_(bucket).download(name)

    result = _guard(lambda: extraction.extract(pdf))
    # GoBD: it stays traceable that values were suggested by AI, and to whom
    actor = f"KI ({llm.model() if result['mode'] == 'live' else 'offline'}) für {current_actor.get()}"
    db_service.audit.record(invoice_id, "ai_suggestion",
                            {"vorgeschlagene_felder": {"old": None, "new": sorted(result["fields"])}}, actor=actor)
    return result


@router.post("/invoices/{invoice_id}/ai-correction-request")
async def correction_request(invoice_id: str = Path(...)):
    """Draft e-mail to the supplier asking for a corrected invoice. Never sent automatically."""
    invoice = _invoice(invoice_id)
    return _guard(lambda: correction.draft(invoice, check_stored_invoice(invoice, db_service)))


@router.get("/ai/usage")
async def ai_usage(days: int = 30):
    """Live AI calls, tokens and estimated cost per feature (no prompts are stored)"""
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    since = (datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 365)))).isoformat()
    rows = (db_service.client.table("ai_requests").select("*").gte("created_at", since).execute()).data or []
    features: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        f = features.setdefault(row["feature"], {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
        f["requests"] += 1
        f["input_tokens"] += row.get("input_tokens") or 0
        f["output_tokens"] += row.get("output_tokens") or 0
        f["cost_usd"] = round(f["cost_usd"] + float(row.get("cost_usd") or 0), 6)
    return {"since": since, "features": features,
            "total_cost_usd": round(sum(f["cost_usd"] for f in features.values()), 6)}

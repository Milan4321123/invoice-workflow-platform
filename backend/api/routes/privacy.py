"""
Data subject requests (DSGVO Art. 15, 17, 20).

Requests must be answered within a month (Art. 12 Abs. 3). Each handled
request is recorded in security_events for accountability (Art. 5 Abs. 2),
with a hash of the address rather than the address itself.
"""
import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr

from services.audit import current_actor
from services.database import db_service
from services.privacy_service import PrivacyService, subject_hash

router = APIRouter()
privacy = PrivacyService(lambda: db_service.client)


class ErasureRequest(BaseModel):
    email: EmailStr
    confirm: bool = False


def _record(request: Request, event_type: str, email: str) -> None:
    db_service.create_security_event(
        event_type=event_type,
        ip_address=request.client.host if request.client else None,
        event_data={"subject": subject_hash(email), "handled_by": current_actor.get()},
    )


@router.get("/privacy/subject-access")
async def subject_access(request: Request, email: EmailStr = Query(...)):
    """Everything stored about this e-mail address, as a JSON download"""
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    data = privacy.subject_access(email)
    _record(request, "dsgvo_subject_access", email)
    return Response(
        content=json.dumps(data, ensure_ascii=False, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="dsgvo-auskunft.json"'},
    )


@router.post("/privacy/erasure")
async def erasure(request: Request, body: ErasureRequest):
    """Erase or pseudonymise what may go; report what must be kept and why"""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="Löschung bitte ausdrücklich bestätigen (confirm: true)")
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    report = privacy.erase(body.email)
    _record(request, "dsgvo_erasure", body.email)
    return report

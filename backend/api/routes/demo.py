"""
Serves invoice files from the in-memory storage in demo mode.

In production the editor gets short-lived signed URLs from Supabase storage;
this plays that role for the demo. Only mounted when DEMO_MODE=true, and it
only ever holds the fictional demo files and what the visitor uploads.
"""
import json
import os
from pathlib import Path
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from services.database import db_service

router = APIRouter()
# The demo's sent e-mails, so their links can be clicked; behind login
outbox_router = APIRouter()


@router.get("/demo-files/{file_path:path}")
async def demo_file(file_path: str):
    bucket, name = db_service._storage_location(file_path)
    try:
        content = db_service.client.storage.from_(bucket).download(name)
    except KeyError:
        raise HTTPException(status_code=404, detail="File not found")
    media_type = "application/xml" if name.lower().endswith(".xml") else "application/pdf"
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": "inline"})


def _outbox() -> Path:
    return Path(os.getenv("EMAIL_OUTBOX_DIR", "outbox"))


def _header(path: Path) -> dict:
    first = path.read_text(encoding="utf-8").split("\n", 1)[0]
    match = re.match(r"<!-- outbox (\{.*\}) -->", first)
    return json.loads(match.group(1)) if match else {}


@outbox_router.get("/demo/outbox")
async def list_outbox():
    mails = []
    for path in sorted(_outbox().glob("*.html"), reverse=True):
        mails.append({"id": path.name, **_header(path)})
    return {"emails": mails}


@outbox_router.get("/demo/outbox/{mail_id}")
async def read_outbox(mail_id: str):
    if not re.fullmatch(r"[\w.-]+\.html", mail_id):
        raise HTTPException(status_code=400, detail="Invalid id")
    path = _outbox() / mail_id
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return Response(content=path.read_text(encoding="utf-8"), media_type="text/html")

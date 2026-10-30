"""
Serves invoice files from the in-memory storage in demo mode.

In production the editor gets short-lived signed URLs from Supabase storage;
this plays that role for the demo. Only mounted when DEMO_MODE=true, and it
only ever holds the fictional demo files and what the visitor uploads.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from services.database import db_service

router = APIRouter()


@router.get("/demo-files/{file_path:path}")
async def demo_file(file_path: str):
    bucket, name = db_service._storage_location(file_path)
    try:
        content = db_service.client.storage.from_(bucket).download(name)
    except KeyError:
        raise HTTPException(status_code=404, detail="File not found")
    media_type = "application/xml" if name.lower().endswith(".xml") else "application/pdf"
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": "inline"})

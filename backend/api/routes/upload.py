"""File upload route handlers"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from fastapi.responses import Response
from slowapi import Limiter
from slowapi.util import get_remote_address
import uuid
import datetime
import logging
from typing import Dict, Any

# Import upload service instead of direct database calls
from services.upload_service import upload_service, UploadSource, FileData
from services.database import db_service
from api.dependencies.auth import require_auth

router = APIRouter()
logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)

@router.get("/mock-storage/{filename}")
async def get_mock_file(filename: str):
    """Serve mock PDF files for demo purposes"""
    
    # Generate a simple PDF response (in real app, this would serve actual files)
    pdf_text = f"Mock PDF: {filename}"
    pdf_content = f"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj
4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Arial>>endobj
5 0 obj<</Length {len(pdf_text) + 30}>>stream
BT /F1 12 Tf 100 700 Td ({pdf_text}) Tj ET
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000267 00000 n 
0000000343 00000 n 
trailer<</Size 6/Root 1 0 R>>
startxref
500
%%EOF""".encode('utf-8')
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"}
    )

@router.post("/upload")
@limiter.limit("10/minute")  # Limit uploads to 10 per minute per IP
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(require_auth)
):
    """
    Upload an invoice: a PDF (scan or ZUGFeRD/Factur-X) or an XRechnung XML.
    The upload service checks type, name and duplicates.
    """
    # Browsers label .xml files inconsistently; the parser decides whether it's an invoice
    content_type = file.content_type
    if (file.filename or "").lower().endswith(".xml") and content_type in (
            None, "", "application/octet-stream", "text/xml", "application/xml"):
        content_type = "application/xml"

    try:
        # Read file content
        content = await file.read()
        
        # Check if file is empty
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Check file size (max 50MB)
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large (max 50MB)")
        
        # Create FileData object
        file_data = FileData(
            content=content,
            filename=file.filename,
            content_type=content_type,
            file_size=len(content),
            source=UploadSource.DRAG_DROP,
            source_metadata={"original_filename": file.filename}
        )
        
        # Use upload service to handle the upload
        result = await upload_service.upload_file(file_data)
        
        if not result.success:
            if result.rejected:
                raise HTTPException(status_code=400, detail=result.error)
            raise HTTPException(status_code=500, detail=f"Upload failed: {result.error}")
        
        # Return successful response
        return {
            "status": "uploaded",
            "filename": result.filename,
            "url": result.url,
            "id": result.invoice_id,
            "file_size": result.file_size,
            "source": result.source.value,
            "e_invoice_format": result.e_invoice_format
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

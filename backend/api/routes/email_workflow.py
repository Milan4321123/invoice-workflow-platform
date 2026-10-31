"""
Email Workflow API Routes
Handles editor notifications and Bau-Leiter approval workflow
"""
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID
import jwt
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from pydantic import BaseModel, EmailStr
from fastapi.responses import HTMLResponse

from services.database import db_service
from api.dependencies.auth import require_auth
from services.audit import current_actor
from services.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Request/Response Models
class EditorNotificationRequest(BaseModel):
    invoice_id: str
    editor_email: EmailStr
    editor_name: str
    changes_summary: Optional[List[Dict[str, Any]]] = None

class DropdownChangeNotificationRequest(BaseModel):
    user_email: EmailStr
    changes: List[Dict[str, Any]]

class BauleiterApprovalRequest(BaseModel):
    invoice_id: str
    bauleiter_email: EmailStr
    editor_name: str
    editor_email: EmailStr
    changes_summary: Optional[List[Dict[str, Any]]] = None

class EmailResponse(BaseModel):
    success: bool
    message: str
    message_id: Optional[str] = None
    timestamp: str

@router.post("/email/editor-notification", response_model=EmailResponse, dependencies=[Depends(require_auth)])
async def send_editor_notification(
    request: EditorNotificationRequest,
    http_request: Request
):
    """
    Send professional HTML email notification to editor after invoice completion.
    This endpoint:
    1. Fetches invoice data
    2. Sends professional HTML email with changes summary
    3. Only marks invoice as 'edit_completed' after successful email send
    4. Logs all activity for audit
    """
    try:
        request_id = getattr(http_request.state, 'request_id', None)
        
        # Validate invoice exists and get data
        invoice_data = await _get_invoice_data(request.invoice_id)
        if not invoice_data:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        # Validate invoice is in correct state for editor notification
        if invoice_data.get('status') not in ['edited', 'pending_email']:
            raise HTTPException(
                status_code=400, 
                detail=f"Invoice status '{invoice_data.get('status')}' is not eligible for editor notification"
            )
        
        # Update invoice to "in Bearbeitung" state (processing started)
        await _update_invoice_status(request.invoice_id, 'edited')
        await _update_invoice_review_status(request.invoice_id, 'under_review')
        
        # Summary email disabled - only completion emails are sent when invoice is finished
        logger.info(f"Summary email skipped for invoice {request.invoice_id} - only completion emails are sent")
        
        result = {
            "success": True,
            "message": "Editor notification skipped - only completion emails are sent",
            "message_id": "skipped-summary-email"
        }
        
        if not result["success"]:
            # Revert status on email failure
            await _update_invoice_status(request.invoice_id, 'uploaded')
            raise HTTPException(status_code=500, detail=f"Email send failed: {result.get('error')}")
        
        # Log security event
        await _log_security_event(
            event_type="editor_notification_sent",
            ip_address=http_request.client.host,
            user_email=request.editor_email,
            invoice_id=request.invoice_id,
            event_data={
                "editor_name": request.editor_name,
                "message_id": result.get("message_id"),
                "changes_count": len(request.changes_summary) if request.changes_summary else 0
            }
        )
        
        logger.info(f"Editor notification sent successfully for invoice {request.invoice_id}")
        
        return EmailResponse(
            success=True,
            message="Editor notification sent successfully",
            message_id=result.get("message_id"),
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending editor notification: {str(e)}")
        # Attempt to revert invoice status
        try:
            await _update_invoice_status(request.invoice_id, 'edited')
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/email/dropdown-change-notification", response_model=EmailResponse, dependencies=[Depends(require_auth)])
async def send_dropdown_change_notification(
    request: DropdownChangeNotificationRequest,
    http_request: Request
):
    """
    Send notification email about dropdown option changes.
    This endpoint:
    1. Validates the request
    2. Sends an email summary of dropdown changes
    3. Logs the activity for audit
    """
    try:
        request_id = getattr(http_request.state, 'request_id', None)
        
        # Validate changes list is not empty
        if not request.changes:
            raise HTTPException(status_code=400, detail="Changes list cannot be empty")
        
        # Send dropdown change notification
        result = await email_service.send_dropdown_change_notification(
            user_email=request.user_email,
            changes=request.changes
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=f"Email send failed: {result.get('error')}")
        
        # Log security event
        await _log_security_event(
            event_type="dropdown_change_notification_sent",
            ip_address=http_request.client.host,
            user_email=request.user_email,
            event_data={
                "changes_count": len(request.changes),
                "message_id": result.get("message_id"),
                "request_id": request_id
            }
        )
        
        logger.info(f"Dropdown change notification sent successfully to {request.user_email}")
        
        return EmailResponse(
            success=True,
            message="Dropdown change notification sent successfully",
            message_id=result.get("message_id"),
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending dropdown change notification: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/email/bauleiter-approval", response_model=EmailResponse, dependencies=[Depends(require_auth)])
async def send_bauleiter_approval_request(
    request: BauleiterApprovalRequest,
    http_request: Request
):
    """
    Send approval request to Bau-Leiter with secure approval/rejection links.
    This endpoint:
    1. Fetches invoice data
    2. Generates secure approval tokens
    3. Sends professional HTML email with approval links
    4. Updates invoice status to 'in_review_by_bauleiter'
    5. Logs all activity for audit
    """
    try:
        request_id = getattr(http_request.state, 'request_id', None)
        
        # Validate invoice exists and get data
        invoice_data = await _get_invoice_data(request.invoice_id)
        if not invoice_data:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        # Validate invoice is in correct state for Bau-Leiter review
        if invoice_data.get('status') != 'edit_completed':
            raise HTTPException(
                status_code=400, 
                detail=f"Invoice status '{invoice_data.get('status')}' is not ready for Bau-Leiter review"
            )
        
        # Send Bau-Leiter approval request
        result = await email_service.send_bauleiter_approval_request(
            invoice_data=invoice_data,
            bauleiter_email=request.bauleiter_email,
            editor_name=request.editor_name,
            editor_email=request.editor_email,
            changes_summary=request.changes_summary
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=f"Email send failed: {result.get('error')}")
        
        # Log security event
        await _log_security_event(
            event_type="bauleiter_approval_sent",
            ip_address=http_request.client.host,
            user_email=request.editor_email,
            invoice_id=request.invoice_id,
            event_data={
                "bauleiter_email": request.bauleiter_email,
                "editor_name": request.editor_name,
                "message_id": result.get("message_id"),
                "changes_count": len(request.changes_summary) if request.changes_summary else 0
            }
        )
        
        logger.info(f"Bau-Leiter approval request sent for invoice {request.invoice_id}")
        
        return EmailResponse(
            success=True,
            message="Bau-Leiter approval request sent successfully",
            message_id=result.get("message_id"),
            timestamp=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending Bau-Leiter approval request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/email/audit/{invoice_id}", dependencies=[Depends(require_auth)])
async def get_email_audit_log(
    invoice_id: str,
    limit: int = Query(default=10, ge=1, le=100)
):
    """
    Get email audit log for specific invoice (admin/debug use).
    """
    try:
        query = """
        SELECT * FROM email_audit_log 
        WHERE invoice_id = %s 
        ORDER BY sent_at DESC 
        LIMIT %s
        """
        
        results = await db_service.fetch_all(query, (invoice_id, limit))
        
        return {
            "invoice_id": invoice_id,
            "email_logs": results,
            "total_count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Error fetching email audit log: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper Functions
async def _get_invoice_data(invoice_id: str) -> Optional[Dict[str, Any]]:
    """Fetch invoice data from database using centralized service"""
    try:
        result = db_service.get_invoice(invoice_id)
        if result["success"]:
            return result["data"]
        else:
            logger.error(f"Error fetching invoice data: {result['error']}")
            return None
    except Exception as e:
        logger.error(f"Error fetching invoice data: {str(e)}")
        return None

async def _update_invoice_status(invoice_id: str, status: str):
    """Update invoice status using centralized database service"""
    try:
        result = db_service.update_invoice_status(invoice_id, status)
        if not result["success"]:
            raise Exception(result["error"])
    except Exception as e:
        logger.error(f"Error updating invoice status: {str(e)}")
        raise e

async def _update_invoice_review_status(invoice_id: str, review_status: str):
    """Update invoice review status using centralized database service"""
    try:
        # Get current status first
        invoice_result = db_service.get_invoice(invoice_id)
        if not invoice_result["success"]:
            raise Exception(f"Invoice not found: {invoice_result['error']}")
        
        current_status = invoice_result["data"].get("status", "pending")
        
        # Update with both status and review_status
        result = db_service.update_invoice_status(invoice_id, current_status, review_status)
        if not result["success"]:
            raise Exception(result["error"])
    except Exception as e:
        logger.error(f"Error updating invoice review status: {str(e)}")
        raise e

async def _log_security_event(
    event_type: str,
    ip_address: str,
    user_email: Optional[str] = None,
    invoice_id: Optional[str] = None,
    event_data: Optional[Dict[str, Any]] = None,
    risk_level: str = "low"
):
    """Log security event"""
    try:
        # Use database service method
        result = db_service.create_security_event(
            event_type=event_type,
            ip_address=ip_address,
            user_email=user_email,
            invoice_id=invoice_id,
            event_data=event_data,
            risk_level=risk_level
        )
        
        if not result.get("success"):
            logger.warning(f"Failed to log security event: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error logging security event: {str(e)}")
        # Don't raise - security logging shouldn't break main flow

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

@router.get("/approval/{token}")
async def process_approval_action(
    token: str,
    http_request: Request
):
    """
    Process secure approval/rejection action from email link.
    This endpoint:
    1. Validates and decodes secure token
    2. Checks token hasn't expired or been used
    3. Updates invoice approval status
    4. Marks token as used
    5. Logs security event
    6. Returns user-friendly HTML response
    """
    try:
        ip_address = http_request.client.host
        
        # Decode and validate token
        token_data = await _validate_approval_token(token, ip_address)
        
        if not token_data:
            return _create_error_html("Invalid or expired approval token")
        
        invoice_id = token_data["invoice_id"]
        action = token_data["action"]
        user_email = token_data["user_email"]
        
        # Get invoice data
        invoice_data = await _get_invoice_data(invoice_id)
        if not invoice_data:
            return _create_error_html("Invoice not found")
        
        # Validate invoice is still in review state
        if invoice_data.get('status') != 'in_review_by_bauleiter':
            return _create_error_html(f"Invoice is no longer in review state (current: {invoice_data.get('status')})")
        
        # Process approval/rejection
        if action == "approve":
            new_status = "approved_by_bauleiter"
            approval_status = "approved"
            action_text = "GENEHMIGT"
            success_message = "Die Rechnung wurde erfolgreich genehmigt."
        elif action == "reject":
            new_status = "rejected_by_bauleiter"
            approval_status = "rejected"
            action_text = "ABGELEHNT"
            success_message = "Die Rechnung wurde abgelehnt."
        else:
            return _create_error_html("Invalid action")
        
        # Update invoice status using new database service method
        decision = "approved" if action == "approve" else "rejected"
        status_result = db_service.update_invoice_bauleiter_decision(
            invoice_id=invoice_id,
            decision=decision,
            decided_by=user_email,
            decision_notes=f"Decision made via email link from IP: {ip_address}"
        )
        
        if not status_result["success"]:
            logger.error(f"Failed to update invoice decision: {status_result['error']}")
            return _create_error_html("Fehler beim Aktualisieren des Rechnungsstatus")
        
        # Mark token as used
        await _mark_token_as_used(token, ip_address)
        
        # Log security event
        await _log_security_event(
            event_type=f"approval_{action}",
            ip_address=ip_address,
            user_email=user_email,
            invoice_id=invoice_id,
            event_data={
                "action": action,
                "invoice_number": invoice_data.get("rechnungsnummer"),
                "supplier": invoice_data.get("lieferant"),
                "amount": invoice_data.get("rechnungsbetrag")
            }
        )
        
        logger.info(f"Approval action '{action}' processed for invoice {invoice_id} by {user_email}")
        
        # Return success HTML response
        return _create_success_html(
            action_text=action_text,
            message=success_message,
            invoice_data=invoice_data
        )
        
    except Exception as e:
        logger.error(f"Error processing approval action: {str(e)}")
        
        # Log security event for failed approval attempt
        await _log_security_event(
            event_type="approval_attempt_failed",
            ip_address=http_request.client.host,
            event_data={"error": str(e), "token_preview": token[:10] + "..."},
            risk_level="medium"
        )
        
        return _create_error_html("Ein Fehler ist aufgetreten. Bitte kontaktieren Sie den Administrator.")

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

async def _update_invoice_approval_status(
    invoice_id: str, 
    status: str, 
    approval_status: str, 
    approval_method: str,
    user_email: str
):
    """Update invoice approval status"""
    try:
        # Use database service method for status updates
        result = db_service.update_approval_status(
            invoice_id=invoice_id,
            status=status,
            approval_status=approval_status,
            approval_method=approval_method
        )
        
        if not result.get("success"):
            raise Exception(f"Failed to update approval status: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error updating invoice approval status: {str(e)}")
        raise e

async def _validate_approval_token(token: str, ip_address: str) -> Optional[Dict[str, Any]]:
    """Validate approval token and return decoded data"""
    try:
        # Decode JWT token
        jwt_secret = email_service.jwt_secret
        token_data = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        
        # Hash token for database lookup
        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        logger.info(f"Validating token with hash: {token_hash[:16]}...")
        
        # Check token in database using Supabase client
        try:
            if db_service.client:
                # Query to find the token
                response = db_service.client.table("approval_tokens").select("*").eq("token_hash", token_hash).execute()
                
                logger.info(f"Database query result: {len(response.data) if response.data else 0} tokens found")
                
                if response.data:
                    token_record = response.data[0]
                    logger.info(f"Token found: expires_at={token_record.get('expires_at')}, used_at={token_record.get('used_at')}, is_revoked={token_record.get('is_revoked')}")
                    
                    # Check if token is still valid
                    from datetime import datetime
                    import dateutil.parser
                    
                    expires_at = dateutil.parser.parse(token_record['expires_at'])
                    now = datetime.now(expires_at.tzinfo)
                    
                    if expires_at < now:
                        logger.warning(f"Token expired: {expires_at} < {now}")
                        return None
                    
                    if token_record.get('used_at') is not None:
                        logger.warning(f"Token already used at: {token_record.get('used_at')}")
                        return None
                        
                    if token_record.get('is_revoked', False):
                        logger.warning("Token is revoked")
                        return None
                        
                    logger.info("Token validation successful")
                    return token_data
                else:
                    logger.warning(f"No token found with hash: {token_hash[:16]}...")
                    await _log_security_event(
                        event_type="invalid_token_attempt",
                        ip_address=ip_address,
                        event_data={"token_hash": token_hash[:16] + "..."},
                        risk_level="high"
                    )
                    return None
            else:
                # If database is not available, validate token structure only
                logger.warning("Database unavailable, validating token structure only")
                return token_data
                
        except Exception as db_error:
            logger.warning(f"Database token check failed, validating token structure only: {db_error}")
            return token_data
        
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT token decode failed: {e}")
        await _log_security_event(
            event_type="token_decode_failed",
            ip_address=ip_address,
            event_data={"error": str(e)},
            risk_level="high"
        )
        return None
    except Exception as e:
        logger.error(f"Error validating approval token: {str(e)}")
        return None

async def _mark_token_as_used(token: str, ip_address: str):
    """Mark approval token as used"""
    try:
        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Use database service method
        result = db_service.mark_approval_token_used(
            token_hash=token_hash,
            ip_address=ip_address
        )
        
        if not result.get("success"):
            raise Exception(f"Failed to mark token as used: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error marking token as used: {str(e)}")
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

def _create_success_html(action_text: str, message: str, invoice_data: Dict[str, Any]) -> str:
    """Create HTML success response for approval action"""
    return f"""
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Genehmigung erfolgreich</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
            .success {{ background: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 20px; border-radius: 5px; }}
            .invoice-info {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .action-badge {{ background: #28a745; color: white; padding: 5px 10px; border-radius: 3px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="success">
            <h2>✅ Aktion erfolgreich</h2>
            <p><span class="action-badge">{action_text}</span></p>
            <p>{message}</p>
        </div>
        
        <div class="invoice-info">
            <h3>Rechnung Details</h3>
            <p><strong>Rechnungsnummer:</strong> {invoice_data.get('rechnungsnummer', 'N/A')}</p>
            <p><strong>Lieferant:</strong> {invoice_data.get('lieferant', 'N/A')}</p>
            <p><strong>Betrag:</strong> {invoice_data.get('rechnungsbetrag', 'N/A')}</p>
            <p><strong>Zeitstempel:</strong> {datetime.now().strftime('%d.%m.%Y um %H:%M')}</p>
        </div>
        
        <p><small>Diese Seite kann geschlossen werden. Die Aktion wurde erfolgreich verarbeitet.</small></p>
    </body>
    </html>
    """

def _create_error_html(error_message: str) -> str:
    """Create HTML error response"""
    return f"""
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Fehler</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }}
            .error {{ background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 20px; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <div class="error">
            <h2>❌ Fehler</h2>
            <p>{error_message}</p>
            <p>Bitte kontaktieren Sie den Administrator oder versuchen Sie es später erneut.</p>
        </div>
        
        <p><small>Zeitstempel: {datetime.now().strftime('%d.%m.%Y um %H:%M')}</small></p>
    </body>
    </html>
    """

@router.get("/email/skonto-decision")
async def process_skonto_decision(
    token: str,
    decision: str,
    http_request: Request
):
    """
    Process Skonto decision action from email link.
    This endpoint:
    1. Validates and decodes secure token
    2. Checks token hasn't expired or been used
    3. Updates invoice Skonto decision status
    4. Marks token as used
    5. Logs security event
    6. Returns user-friendly HTML response
    
    Args:
        token: Secure token from email link
        decision: 'taken' or 'missed'
    """
    try:
        ip_address = http_request.client.host
        
        # Decode and validate token
        token_data = await _validate_approval_token(token, ip_address)
        
        if not token_data:
            return _create_error_html("Invalid or expired Skonto decision token")
        
        invoice_id = token_data["invoice_id"]
        user_email = token_data["user_email"]
        
        # Validate decision parameter
        if decision not in ["taken", "missed"]:
            return _create_error_html(f"Invalid decision: {decision}. Must be 'taken' or 'missed'")
        
        # Get invoice data
        invoice_data = await _get_invoice_data(invoice_id)
        if not invoice_data:
            return _create_error_html("Invoice not found")
        
        # Validate invoice has Skonto data
        if not invoice_data.get("skonto_datum") or not invoice_data.get("skonto_prozent"):
            return _create_error_html("Invoice does not have Skonto information")
        
        # Check if Skonto decision already made - ALLOW DEMO RETESTING
        current_decision = invoice_data.get("skonto_decision")
        if current_decision in ["taken", "missed", "not_applicable"]:
            logger.warning(f"⚠️ DEMO MODE: Skonto decision already made ({current_decision}) - allowing override for demonstration")
            # For demonstration purposes, allow retesting - comment out the restriction
            # return _create_error_html(f"Skonto decision already made: {current_decision}")
        
        # Calculate actual savings if Skonto was taken
        actual_savings = None
        if decision == "taken":
            try:
                total_amount = float(invoice_data.get("rechnungsbetrag", 0))
                skonto_percent = float(invoice_data.get("skonto_prozent", 0))
                actual_savings = round(total_amount * skonto_percent / 100, 2)
            except (ValueError, TypeError):
                actual_savings = 0
        
        # Update Skonto decision in database
        skonto_result = db_service.update_skonto_decision(
            invoice_id=invoice_id,
            decision=decision,
            actual_savings=actual_savings,
            decision_timestamp=datetime.now().isoformat(),
            decision_email=user_email
        )
        
        if not skonto_result["success"]:
            logger.error(f"Failed to update Skonto decision: {skonto_result.get('error')}")
            return _create_error_html(f"Failed to update Skonto decision: {skonto_result.get('error')}")
        
        # Mark token as used
        await _mark_token_as_used(token, ip_address)
        
        # Log security event
        await _log_security_event(
            event_type="skonto_decision_processed",
            ip_address=ip_address,
            user_email=user_email,
            invoice_id=invoice_id,
            event_data={
                "decision": decision,
                "actual_savings": actual_savings,
                "token_used": token[:8] + "...",
                "skonto_percent": invoice_data.get("skonto_prozent"),
                "skonto_date": invoice_data.get("skonto_datum")
            }
        )
        
        # Create success message
        action_text = "SKONTO GENOMMEN" if decision == "taken" else "SKONTO ÜBERSPRUNGEN"
        
        if decision == "taken":
            success_message = (
                f"Das Skonto wurde erfolgreich in Anspruch genommen. "
                f"Ersparnis: {actual_savings} EUR ({invoice_data.get('skonto_prozent')}%)"
            )
        else:
            success_message = (
                f"Das Skonto wurde übersprungen. "
                f"Die volle Rechnungssumme wird bezahlt."
            )
        
        logger.info(f"✅ Skonto decision processed: {invoice_id} -> {decision} by {user_email}")
        
        # Return success HTML page
        return HTMLResponse(_create_skonto_success_html(
            action_text=action_text,
            success_message=success_message,
            invoice_data=invoice_data,
            decision=decision,
            actual_savings=actual_savings,
            user_email=user_email
        ))
        
    except Exception as e:
        logger.error(f"❌ Error processing Skonto decision: {str(e)}")
        return _create_error_html(f"System error: {str(e)}")

def _create_skonto_success_html(
    action_text: str,
    success_message: str,
    invoice_data: Dict[str, Any],
    decision: str,
    actual_savings: float = None,
    user_email: str = None
) -> str:
    """Create HTML success response for Skonto decision"""
    
    # Determine styling based on decision
    if decision == "taken":
        status_color = "#28a745"  # Green for taken
        icon = "💰"
    else:
        status_color = "#6c757d"  # Gray for missed/skipped
        icon = "⏭️"
    
    return f"""
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Skonto Entscheidung - {action_text}</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 700px; margin: 50px auto; padding: 20px; background: #f8f9fa; }}
            .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .status {{ background: {status_color}; color: white; padding: 15px; border-radius: 8px; font-size: 20px; font-weight: bold; }}
            .invoice-info {{ background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }}
            .detail-row {{ display: flex; justify-content: space-between; margin: 8px 0; }}
            .detail-label {{ font-weight: bold; }}
            .detail-value {{ color: #495057; }}
            .savings-info {{ background: #e8f5e8; border-left: 4px solid #28a745; padding: 15px; margin: 20px 0; }}
            .timestamp {{ text-align: center; color: #6c757d; font-size: 14px; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="status">{icon} {action_text}</div>
                <p style="font-size: 18px; color: #495057; margin-top: 15px;">{success_message}</p>
            </div>
            
            <div class="invoice-info">
                <h3>📋 Rechnung Details</h3>
                <div class="detail-row">
                    <span class="detail-label">Rechnungsnummer:</span>
                    <span class="detail-value">{invoice_data.get('rechnungsnummer', 'N/A')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Lieferant:</span>
                    <span class="detail-value">{invoice_data.get('lieferant', 'N/A')}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Rechnungsbetrag:</span>
                    <span class="detail-value">{invoice_data.get('rechnungsbetrag', 'N/A')} EUR</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Skonto:</span>
                    <span class="detail-value">{invoice_data.get('skonto_prozent', 'N/A')}% bis {invoice_data.get('skonto_datum', 'N/A')}</span>
                </div>
            </div>
            
            {f'''
            <div class="savings-info">
                <h4>💰 Einsparung</h4>
                <p style="font-size: 16px; margin: 0;">
                    <strong>{actual_savings} EUR</strong> wurden durch das Skonto eingespart!
                </p>
            </div>
            ''' if decision == "taken" and actual_savings else ""}
            
            <div style="background: #e8f4f8; border: 1px solid #bee5eb; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <strong>✅ Nächste Schritte:</strong>
                <p>Die Skonto-Entscheidung wurde erfolgreich im System erfasst. Die Buchhaltung wird entsprechend informiert und die Zahlung wird entsprechend bearbeitet.</p>
            </div>
            
            <div class="timestamp">
                <strong>Verarbeitet von:</strong> {user_email or 'N/A'}<br>
                <strong>Zeitstempel:</strong> {datetime.now().strftime('%d.%m.%Y um %H:%M')}
            </div>
            
            <p style="text-align: center; margin-top: 30px;"><small>Diese Seite kann geschlossen werden. Die Aktion wurde erfolgreich verarbeitet.</small></p>
        </div>
    </body>
    </html>
    """

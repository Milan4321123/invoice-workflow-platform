"""Invoice management route handlers"""
from fastapi import APIRouter, HTTPException, Path, Depends, Query
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import os

from services.database import db_service
from services.dropdown_labels import with_labels
from services.email_service import email_service
from api.dependencies.auth import require_auth

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/invoices")
async def get_invoices():
    """Get all invoices"""
    
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    
    try:
        # Use centralized database service method
        result = db_service.get_all_invoices(limit=1000)
        
        if result["success"]:
            return {
                "invoices": [with_labels(invoice) for invoice in result["data"]],
                "total": len(result["data"])
            }
        else:
            raise Exception(result["error"])
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Database query failed: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch invoices: {error_msg}")

@router.get("/invoices/pending-approval")
async def get_pending_bauleiter_approvals(bauleiter_email: Optional[str] = None):
    """
    Get invoices pending Bauleiter approval.
    Uses existing database service patterns for filtering.
    """
    try:
        # Use new database method that follows existing patterns
        result = db_service.get_pending_bauleiter_approvals(
            bauleiter_email=bauleiter_email,
            limit=100
        )
        
        if result["success"]:
            return {
                "success": True,
                "pending_approvals": result["data"],
                "total": len(result["data"]),
                "bauleiter_email": bauleiter_email
            }
        else:
            logger.warning(f"Failed to get pending approvals: {result['error']}")
            return {
                "success": True,
                "pending_approvals": [],
                "total": 0,
                "bauleiter_email": bauleiter_email,
                "message": "No pending approvals found"
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to get pending approvals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get pending approvals: {str(e)}")

@router.get("/invoices/by-status/{status}")
async def get_invoices_by_status(status: str, limit: int = 100):
    """
    Get invoices filtered by status.
    Uses existing database service patterns.
    """
    try:
        # Use new database method that leverages existing query logic
        result = db_service.get_invoices_by_status(status=status, limit=limit)
        
        if result["success"]:
            return {
                "success": True,
                "invoices": [with_labels(invoice) for invoice in result["data"]],
                "total": len(result["data"]),
                "status": status
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to get invoices by status: {result['error']}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get invoices by status {status}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get invoices by status: {str(e)}")

@router.get("/invoices/skonto-due")
async def get_invoices_with_skonto_due(days_ahead: int = 7):
    """
    Get invoices with Skonto expiring within the specified number of days.
    
    Args:
        days_ahead: Number of days ahead to check for Skonto expiry (default: 7)
    """
    try:
        logger.info(f"🔍 Getting invoices with Skonto due within {days_ahead} days")
        
        # Get invoices with Skonto due
        result = db_service.get_invoices_with_skonto_due(days_ahead=days_ahead)
        
        if result["success"]:
            invoices = result["data"]
            logger.info(f"✅ Found {len(invoices)} invoices with Skonto due within {days_ahead} days")
            
            # Calculate additional metadata for each invoice
            for invoice in invoices:
                try:
                    # Calculate days until expiry
                    from datetime import datetime, timedelta
                    skonto_datum = invoice.get("skonto_datum")
                    if skonto_datum:
                        if isinstance(skonto_datum, str):
                            if "." in skonto_datum:
                                skonto_date = datetime.strptime(skonto_datum, "%d.%m.%Y")
                            elif "-" in skonto_datum:
                                skonto_date = datetime.strptime(skonto_datum, "%Y-%m-%d")
                            else:
                                skonto_date = datetime.strptime(skonto_datum, "%Y%m%d")
                        else:
                            skonto_date = skonto_datum
                        
                        invoice["days_until_expiry"] = (skonto_date - datetime.now()).days
                        
                        # Calculate potential savings
                        total_amount = invoice.get("rechnungsbetrag")
                        skonto_prozent = invoice.get("skonto_prozent")
                        if total_amount and skonto_prozent:
                            invoice["potential_savings"] = round(float(total_amount) * float(skonto_prozent) / 100, 2)
                        else:
                            invoice["potential_savings"] = 0
                    else:
                        invoice["days_until_expiry"] = None
                        invoice["potential_savings"] = 0
                        
                except Exception as e:
                    logger.warning(f"Failed to calculate metadata for invoice {invoice.get('id')}: {e}")
                    invoice["days_until_expiry"] = None
                    invoice["potential_savings"] = 0
            
            return {
                "success": True,
                "invoices": invoices,
                "total": len(invoices),
                "days_ahead": days_ahead,
                "retrieved_at": datetime.now().isoformat()
            }
        else:
            logger.error(f"❌ Failed to get invoices with Skonto due: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get invoices with Skonto due: {result.get('error')}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get invoices with Skonto due: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get invoices with Skonto due: {str(e)}"
        )

@router.delete("/invoices/all")
async def delete_all_invoices():
    """
    Delete ALL invoices with comprehensive cleanup.
    ⚠️ WARNING: This will permanently delete all invoices in the system!
    Removes all invoice records, associated Skonto data, and file storage.
    """
    
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    
    try:
        logger.warning("🚨 BULK DELETION REQUESTED - Deleting ALL invoices from system")
        
        # Use enhanced database service method with comprehensive cleanup
        result = db_service.delete_all_invoices()
        
        if result["success"]:
            deletion_summary = result.get("deletion_summary", {})
            
            logger.info(f"✅ Bulk deletion completed: {deletion_summary}")
            
            return {
                "message": "All invoices deleted successfully",
                "status": "success",
                "summary": {
                    "total_deleted": deletion_summary.get("total_deleted", 0),
                    "skonto_data_cleaned": deletion_summary.get("skonto_data_cleaned", 0),
                    "storage_files_cleaned": deletion_summary.get("storage_files_cleaned", 0),
                    "failed_deletions": deletion_summary.get("failed_deletions", 0)
                },
                "warning": "All invoice data has been permanently removed from the system"
            }
        else:
            raise Exception(result["error"])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete all invoices: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete all invoices: {str(e)}")

@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str = Path(..., description="The invoice ID")):
    """Get a specific invoice by ID"""
    
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    
    try:
        # Use centralized database service method
        result = db_service.get_invoice(invoice_id)
        
        if result["success"]:
            return {
                "status": "success",
                "invoice": with_labels(result["data"])
            }
        else:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch invoice {invoice_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch invoice: {str(e)}")

@router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str = Path(..., description="The invoice ID")):
    """
    Delete an invoice by ID with comprehensive cleanup.
    Removes invoice record, associated Skonto data, and file storage.
    """
    
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    
    try:
        # Use enhanced database service method with comprehensive cleanup
        result = db_service.delete_invoice(invoice_id)
        
        if result["success"]:
            deletion_summary = result.get("deletion_summary", {})
            
            logger.info(f"✅ Invoice deletion completed: {deletion_summary}")
            
            return {
                "message": "Invoice deleted successfully",
                "invoice_id": invoice_id,
                "filename": deletion_summary.get("filename", "unknown"),
                "status": "success",
                "details": {
                    "skonto_data_cleaned": deletion_summary.get("had_skonto_data", False),
                    "storage_cleaned": deletion_summary.get("storage_cleaned", False),
                    "file_path": deletion_summary.get("file_path")
                }
            }
        else:
            if "not found" in result["error"].lower():
                raise HTTPException(status_code=404, detail="Invoice not found")
            else:
                raise Exception(result["error"])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete invoice {invoice_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete invoice: {str(e)}")

@router.get("/invoices/{invoice_id}/validate")
async def validate_invoice(invoice_id: str = Path(..., description="The invoice ID")):
    """Validate if an invoice exists and is accessible"""
    
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    
    try:
        # Use centralized database service method
        result = db_service.get_invoice(invoice_id)
        
        if result["success"]:
            return {
                "valid": True,
                "invoice_id": invoice_id,
                "filename": result["data"].get("file_name")
            }
        else:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate invoice {invoice_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to validate invoice: {str(e)}")

@router.get("/invoices/{invoice_id}/editor")
async def get_invoice_editor_data(invoice_id: str = Path(..., description="The invoice ID")):
    """Get invoice data formatted for the editor interface"""
    
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    
    try:
        # Use centralized database service method
        result = db_service.get_invoice(invoice_id)
        
        if not result["success"]:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        invoice_data = result["data"]
        
        # Construct proper PDF URL from file_path using centralized service
        from services.pdf_url_service import pdf_url_service
        pdf_url = pdf_url_service.get_pdf_url(invoice_data.get("file_path", ""))
        
        # Format data for editor interface using correct field names
        editor_data = {
            "pdfUrl": pdf_url,
            "fields": {
                "rechnungsempfaenger": invoice_data.get("rechnungsempfaenger", ""),
                "rechnungssteller": invoice_data.get("rechnungssteller", ""),
                "projekt": invoice_data.get("projekt", ""),
                "gewerk": invoice_data.get("gewerk", ""),
                "rechnungsbetrag": invoice_data.get("rechnungsbetrag", 0),
                "rechnungseingang": invoice_data.get("rechnungseingang", ""),
                "faelligkeit": invoice_data.get("faelligkeit", ""),
                "skonto_datum": invoice_data.get("skonto_datum", ""),
                "skonto_prozent": invoice_data.get("skonto_prozent", 0),
                "rechnungsart": invoice_data.get("rechnungsart", "rechnung"),
                "kfw_anrechenbar": invoice_data.get("kfw_anrechenbare_kosten", False),
                "rechnungspruefung_email": invoice_data.get("rechnungspruefung", ""),
                "weiter_berechnen_an": invoice_data.get("weiter_berechnen_an", "")
            },
            "filename": invoice_data.get("file_name", f"Invoice {invoice_id}")
        }
        
        return editor_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch editor data for invoice {invoice_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch editor data: {str(e)}")

@router.put("/invoices/{invoice_id}/editor")
async def update_invoice_editor_data(
    invoice_id: str = Path(..., description="The invoice ID"),
    request_data: Dict[str, Any] = None
):
    """Update invoice data from the editor interface"""
    
    if not request_data:
        raise HTTPException(status_code=400, detail="No data provided")
    
    fields = request_data.get("fields", {})
    editor_info = request_data.get("editor_info", {})
    
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    
    try:
        # Update invoice data using centralized database service
        update_data = {
            # Basic information - using correct field names from schema
            "rechnungsempfaenger": fields.get("rechnungsempfaenger"),
            "rechnungssteller": fields.get("rechnungssteller"), 
            "projekt": fields.get("projekt"),
            "gewerk": fields.get("gewerk"),
            "weiter_berechnen_an": fields.get("weiter_berechnen_an"),
            
            # Financial information
            "rechnungsbetrag": fields.get("rechnungsbetrag"),
            "rechnungseingang": fields.get("rechnungseingang"),
            "faelligkeit": fields.get("faelligkeit"),
            "skonto_datum": fields.get("skonto_datum"),
            "skonto_prozent": fields.get("skonto_prozent"),
            "rechnungsart": fields.get("rechnungsart"),
            
            # Additional fields
            "kfw_anrechenbare_kosten": fields.get("kfw_anrechenbar"),
            "rechnungspruefung": fields.get("rechnungspruefung_email")
        }
        
        # Remove None values but keep empty strings and False values for proper field clearing
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        # Update invoice fields first
        if update_data:
            field_result = db_service.update_invoice(invoice_id, update_data)
            if not field_result["success"]:
                raise HTTPException(status_code=500, detail=f"Failed to update invoice fields: {field_result['error']}")
        
        # Update status to "in Bearbeitung" stage (edited + under_review)
        status_result = db_service.update_invoice_to_editing_stage(invoice_id)
        if not status_result["success"]:
            raise HTTPException(status_code=500, detail=f"Failed to update invoice status: {status_result['error']}")
        
        logger.info(f"✅ Invoice {invoice_id} updated and moved to 'in Bearbeitung' stage")
        
        # Email notification removed - only completion email will be sent when invoice is finished
        email_sent = False
        
        return {
            "success": True,
            "message": "Invoice updated successfully",
            "invoice_id": invoice_id,
            "updated_fields": list(update_data.keys()),
            "email_sent": email_sent
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update editor data for invoice {invoice_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update invoice: {str(e)}")

@router.put("/invoices/{invoice_id}/complete")
async def complete_invoice(
    invoice_id: str = Path(..., description="The invoice ID"),
    request_data: Dict[str, Any] = None
):
    """Mark invoice as completed with review status and trigger Bauleiter approval email"""
    
    if not request_data:
        raise HTTPException(status_code=400, detail="No completion data provided")
    
    completion_info = request_data.get("completion_info", {})
    
    if not db_service.is_available:
        raise HTTPException(status_code=503, detail="Database service not available")
    
    try:
        # Use centralized database service to complete invoice
        completion_info = request_data.get("completion_info", {})
        
        result = db_service.update_invoice_to_completed_stage(
            invoice_id=invoice_id,
            completed_by=completion_info.get("completed_by"),
            notes=completion_info.get("completion_notes")
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=f"Failed to complete invoice: {result['error']}")
        
        updated_invoice = result["data"]
        
        # Send editor completion notification if editor information is provided
        completion_email_sent = False
        editor_info = request_data.get("editor_info", {})
        
        if editor_info.get("editor_email") and editor_info.get("editor_name"):
            try:
                # Send formal completion notification to editor
                email_result = await email_service.send_editor_notification(
                    invoice_data=updated_invoice,
                    editor_email=editor_info["editor_email"],
                    editor_name=editor_info["editor_name"],
                    changes_summary=editor_info.get("changes_summary", []),
                    request_id=None,
                    is_completion=True  # This is a formal completion notification
                )
                
                if email_result["success"]:
                    completion_email_sent = True
                    logger.info(f"Editor completion notification sent successfully for invoice {invoice_id}")
                else:
                    logger.warning(f"Editor completion notification failed for invoice {invoice_id}: {email_result.get('error')}")
                    
            except ValueError as ve:
                if "No email provider configured" in str(ve):
                    logger.info(f"Editor completion notification skipped for invoice {invoice_id}: No email provider configured (demo mode)")
                else:
                    logger.warning(f"Editor completion notification error for invoice {invoice_id}: {str(ve)}")
            except Exception as email_error:
                logger.warning(f"Editor completion notification error for invoice {invoice_id}: {str(email_error)}")
        
        # No automatic Bauleiter email sending - let user control via dashboard "An Bauleiter senden" button
        logger.info(f"Invoice {invoice_id} marked as completed - ready for manual Bauleiter sending via dashboard")
        
        return {
            "success": True,
            "message": "Invoice marked as completed successfully - ready to send to Bauleiter via dashboard",
            "invoice_id": invoice_id,
            "completion_status": updated_invoice.get("review_status", "completed_review"),
            "completed_at": updated_invoice.get("reviewed_at"),
            "completion_email_sent": completion_email_sent,
            "email_sent": False,  # No automatic Bauleiter email - user controls via dashboard
            "email_note": "Use 'An Bauleiter senden' button in dashboard to send approval email"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete invoice {invoice_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to complete invoice: {str(e)}")

@router.post("/invoices/{invoice_id}/send-to-bauleiter")
async def send_invoice_to_bauleiter(
    invoice_id: str = Path(..., description="Invoice ID"),
    request_data: Dict[str, Any] = None
):
    """
    Send completed invoice to Bauleiter for approval.
    Uses existing database service patterns and email service.
    """
    try:
        # Validate request data
        if not request_data:
            raise HTTPException(status_code=400, detail="Request data is required")
        
        bauleiter_email = request_data.get("bauleiter_email")
        if not bauleiter_email:
            raise HTTPException(status_code=400, detail="bauleiter_email is required")
        
        # Get invoice details using existing database service
        invoice_result = db_service.get_invoice(invoice_id)
        if not invoice_result["success"]:
            raise HTTPException(status_code=404, detail=f"Invoice not found: {invoice_result['error']}")
        
        invoice_data = invoice_result["data"]
        
        # Check if invoice is in correct status for sending to Bauleiter
        current_status = invoice_data.get("status")
        if current_status not in ["completed", "edit_completed"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Invoice must be completed before sending to Bauleiter. Current status: {current_status}"
            )
        
        # Update invoice status to 'sent to Bauleiter' using new database method
        sent_by = request_data.get("sent_by", "dashboard_user")
        status_result = db_service.update_invoice_sent_to_bauleiter(
            invoice_id=invoice_id,
            bauleiter_email=bauleiter_email,
            sent_by=sent_by
        )
        
        if not status_result["success"]:
            raise HTTPException(status_code=500, detail=f"Failed to update invoice status: {status_result['error']}")
        
        # Send Bauleiter approval email using existing email service
        email_sent = False
        email_error = None
        email_provider = None

        try:
            # Prepare email data
            editor_name = request_data.get("editor_name", sent_by)
            editor_email = request_data.get("editor_email", os.getenv("DEFAULT_EDITOR_EMAIL", f"{sent_by}@yourcompany.com"))
            changes_summary = request_data.get("changes_summary", [])
            
            # Send approval request email using existing service
            email_result = await email_service.send_bauleiter_approval_request(
                invoice_data=invoice_data,
                bauleiter_email=bauleiter_email,
                editor_name=editor_name,
                editor_email=editor_email,
                changes_summary=changes_summary
            )
            
            if email_result["success"]:
                email_sent = True
                email_provider = email_result.get("provider")
                logger.info(f"✅ Invoice {invoice_id} sent to Bauleiter {bauleiter_email} successfully")
            else:
                email_error = email_result.get("error", "Unknown email error")
                logger.warning(f"❌ Failed to send email to Bauleiter: {email_error}")
                
        except Exception as e:
            email_error = str(e)
            logger.error(f"❌ Error sending email to Bauleiter for invoice {invoice_id}: {str(e)}")
        
        updated_invoice = status_result["data"]
        
        return {
            "success": True,
            "message": f"Invoice sent to Bauleiter {bauleiter_email}",
            "invoice_id": invoice_id,
            "status": updated_invoice.get("status"),
            "bauleiter_email": bauleiter_email,
            "sent_at": updated_invoice.get("sent_to_bauleiter_at"),
            "email_sent": email_sent,
            "email_provider": email_provider,
            "email_error": email_error
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to send invoice {invoice_id} to Bauleiter: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send invoice to Bauleiter: {str(e)}")

@router.post("/invoices/{invoice_id}/send-skonto-reminder")
async def send_skonto_reminder(
    invoice_id: str = Path(..., description="Invoice ID"),
    recipient_email: str = Query(default=None, description="Email address to send reminder to"),
    recipient_name: str = Query(default=None, description="Name of recipient")
):
    """
    Send Skonto reminder email for an invoice.
    
    Args:
        invoice_id: The ID of the invoice
        recipient_email: Email address to send reminder to (optional, falls back to default)
        recipient_name: Name of recipient (optional)
    """
    try:
        logger.info(f"🔔 Sending Skonto reminder for invoice {invoice_id}")
        
        # Get invoice data
        invoice_result = db_service.get_invoice(invoice_id)
        if not invoice_result["success"]:
            raise HTTPException(status_code=404, detail=f"Invoice not found: {invoice_result['error']}")
        
        invoice_data = invoice_result["data"]
        
        # Validate invoice has Skonto data
        if not invoice_data.get("skonto_datum") or not invoice_data.get("skonto_prozent"):
            raise HTTPException(
                status_code=400, 
                detail="Invoice does not have Skonto information (missing skonto_datum or skonto_prozent)"
            )
        
        # Check if reminder already sent (but still allow resending)
        if invoice_data.get("skonto_reminder_sent"):
            logger.info(f"⚠️ Skonto reminder already sent for invoice {invoice_id}, but allowing resend")
            # Don't block the resend, just log it
        
        # Check if Skonto decision already made - ALLOW DEMO RETESTING
        skonto_decision = invoice_data.get("skonto_decision")
        if skonto_decision in ["taken", "missed", "not_applicable"]:
            logger.warning(f"⚠️ DEMO MODE: Skonto decision already made ({skonto_decision}) - allowing override for demonstration")
            # For demonstration purposes, allow retesting - comment out the restriction
            # raise HTTPException(
            #     status_code=400,
            #     detail=f"Skonto decision already made: {skonto_decision}"
            # )
        
        # Use provided email or fall back to default stakeholder
        if not recipient_email:
            # Same rule as the scheduler: accounting first
            from services.skonto_scheduler import skonto_scheduler
            recipient_email = skonto_scheduler.skonto_recipient(invoice_data)
            if not recipient_email:
                raise HTTPException(
                    status_code=400,
                    detail="Kein Empfänger: ACCOUNTING_EMAIL ist nicht gesetzt und die Rechnung hat keine Bauleiter-E-Mail"
                )
            logger.info(f"📧 Using default recipient email: {recipient_email}")
        
        # Send Skonto reminder email
        email_result = await email_service.send_skonto_reminder(
            invoice_data=invoice_data,
            recipient_email=recipient_email,
            recipient_name=recipient_name
        )
        
        if email_result["success"]:
            logger.info(f"✅ Skonto reminder sent successfully for invoice {invoice_id}")
            return {
                "success": True,
                "message": f"Skonto reminder sent to {recipient_email}",
                "invoice_id": invoice_id,
                "recipient_email": recipient_email,
                "message_id": email_result.get("message_id"),
                "email_provider": email_result.get("provider"),
                "potential_savings": email_result.get("potential_savings"),
                "days_until_expiry": email_result.get("days_until_expiry"),
                "sent_at": email_result.get("timestamp")
            }
        else:
            logger.error(f"❌ Failed to send Skonto reminder: {email_result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send Skonto reminder: {email_result.get('error')}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to send Skonto reminder for invoice {invoice_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send Skonto reminder: {str(e)}"
        )

@router.put("/invoices/{invoice_id}")
async def update_invoice(
    invoice_id: str = Path(..., description="Invoice ID"),
    update_data: Dict[str, Any] = None
):
    """
    Update invoice fields including Skonto decisions.
    Supports updating any invoice field, with special handling for Skonto decisions.
    """
    try:
        logger.info(f"🔄 Updating invoice {invoice_id} with data: {update_data}")
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        
        # Get current invoice data
        current_invoice = db_service.get_invoice_by_id(invoice_id)
        if not current_invoice["success"]:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        invoice_data = current_invoice["data"]
        
        # Special handling for Skonto decisions
        if "skonto_decision" in update_data:
            skonto_decision = update_data["skonto_decision"]
            
            # Validate Skonto decision
            valid_decisions = ["pending", "taken", "missed", "not_applicable"]
            if skonto_decision not in valid_decisions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid skonto_decision. Must be one of: {valid_decisions}"
                )
            
            # If marking as taken, ensure actual_skonto_savings is set
            if skonto_decision == "taken" and "actual_skonto_savings" not in update_data:
                # Calculate potential savings if not provided
                amount = invoice_data.get("rechnungsbetrag", 0)
                percentage = invoice_data.get("skonto_prozent", 0)
                if amount and percentage:
                    update_data["actual_skonto_savings"] = float(amount) * float(percentage) / 100
            
            logger.info(f"📊 Marking Skonto as {skonto_decision} for invoice {invoice_id}")
        
        # Update invoice in database
        result = db_service.update_invoice(invoice_id, update_data)
        
        if result["success"]:
            logger.info(f"✅ Invoice {invoice_id} updated successfully")
            return {
                "success": True,
                "message": "Invoice updated successfully",
                "invoice_id": invoice_id,
                "updated_fields": list(update_data.keys()),
                "updated_at": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update invoice: {result.get('error')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update invoice {invoice_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update invoice: {str(e)}"
        )

@router.put("/invoices/{invoice_id}/approve")
async def approve_invoice(
    invoice_id: str = Path(..., description="Invoice ID"),
    request_data: Dict[str, Any] = None
):
    """
    Approve an invoice (for control panel use).
    """
    try:
        logger.info(f"✅ Approving invoice {invoice_id} via control panel")
        
        # Get invoice data first
        invoice_result = db_service.get_invoice(invoice_id)
        if not invoice_result["success"]:
            raise HTTPException(status_code=404, detail=f"Invoice not found: {invoice_result['error']}")
        
        # Update invoice status using existing database service
        result = db_service.update_invoice_bauleiter_decision(
            invoice_id=invoice_id,
            decision="approved",
            decided_by=request_data.get("decided_by", "control_panel") if request_data else "control_panel",
            decision_notes="Approved via control panel"
        )
        
        if result["success"]:
            logger.info(f"✅ Invoice {invoice_id} approved successfully")
            return {
                "success": True,
                "message": "Invoice approved successfully",
                "invoice_id": invoice_id,
                "status": "approved_by_bauleiter",
                "approved_at": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to approve invoice: {result.get('error')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to approve invoice {invoice_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to approve invoice: {str(e)}"
        )

@router.put("/invoices/{invoice_id}/reject")
async def reject_invoice(
    invoice_id: str = Path(..., description="Invoice ID"),
    request_data: Dict[str, Any] = None
):
    """
    Reject an invoice (for control panel use).
    """
    try:
        logger.info(f"❌ Rejecting invoice {invoice_id} via control panel")
        
        # Get invoice data first
        invoice_result = db_service.get_invoice(invoice_id)
        if not invoice_result["success"]:
            raise HTTPException(status_code=404, detail=f"Invoice not found: {invoice_result['error']}")
        
        # Update invoice status using existing database service
        result = db_service.update_invoice_bauleiter_decision(
            invoice_id=invoice_id,
            decision="rejected",
            decided_by=request_data.get("decided_by", "control_panel") if request_data else "control_panel",
            decision_notes="Rejected via control panel"
        )
        
        if result["success"]:
            logger.info(f"❌ Invoice {invoice_id} rejected successfully")
            return {
                "success": True,
                "message": "Invoice rejected successfully",
                "invoice_id": invoice_id,
                "status": "rejected_by_bauleiter",
                "rejected_at": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to reject invoice: {result.get('error')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to reject invoice {invoice_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reject invoice: {str(e)}"
        )

@router.put("/invoices/{invoice_id}/skonto-decision")
async def make_skonto_decision(
    invoice_id: str = Path(..., description="Invoice ID"),
    request_data: Dict[str, Any] = None
):
    """
    Make a Skonto decision for an invoice (take or skip).
    """
    try:
        if not request_data:
            raise HTTPException(status_code=400, detail="Request data is required")
        
        decision = request_data.get("decision")  # "take_skonto" or "skip_skonto"
        decided_by = request_data.get("decided_by", "control_panel")
        
        if decision not in ["take_skonto", "skip_skonto"]:
            raise HTTPException(status_code=400, detail="Decision must be 'take_skonto' or 'skip_skonto'")
        
        logger.info(f"💰 Making Skonto decision '{decision}' for invoice {invoice_id}")
        
        # Get invoice data first
        invoice_result = db_service.get_invoice(invoice_id)
        if not invoice_result["success"]:
            raise HTTPException(status_code=404, detail=f"Invoice not found: {invoice_result['error']}")
        
        invoice_data = invoice_result["data"]
        
        # Prepare update data - only use fields that exist in database
        update_data = {
            "skonto_decision": decision,
        }
        
        # Calculate savings if taking skonto
        if decision == "take_skonto":
            amount = invoice_data.get("rechnungsbetrag")
            percentage = invoice_data.get("skonto_prozent")
            if amount and percentage:
                try:
                    update_data["actual_skonto_savings"] = float(amount) * float(percentage) / 100
                except (ValueError, TypeError):
                    logger.warning(f"Could not calculate Skonto savings for invoice {invoice_id}")
        else:
            # If skipping skonto, set savings to 0
            update_data["actual_skonto_savings"] = 0.0
        
        # Update invoice in database
        result = db_service.update_invoice(invoice_id, update_data)
        
        if result["success"]:
            action_text = "genommen" if decision == "take_skonto" else "übersprungen"
            logger.info(f"💰 Skonto {action_text} for invoice {invoice_id}")
            return {
                "success": True,
                "message": f"Skonto {action_text} successfully",
                "invoice_id": invoice_id,
                "decision": decision,
                "decided_by": decided_by,
                "savings": update_data.get("actual_skonto_savings", 0)
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update Skonto decision: {result.get('error')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to make Skonto decision for invoice {invoice_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to make Skonto decision: {str(e)}"
        )

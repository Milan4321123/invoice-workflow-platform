"""
Approval Workflow API Routes
Handles secure approval/rejection of invoices via email links
"""
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
import jwt
import hashlib
from datetime import datetime
from typing import Dict, Any
import logging

from services.database import db_service
from services.audit import current_actor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/approval", tags=["approval"])

@router.get("/{token}")
async def handle_approval_action(token: str, request: Request):
    """
    Handle approval/rejection action from email links.
    Validates JWT token and processes the approval decision.
    """
    try:
        # Get JWT secret from environment
        import os
        jwt_secret = os.getenv("JWT_SECRET")
        if not jwt_secret or jwt_secret.startswith("your-"):
            return HTMLResponse(
                content=get_error_page("Configuration Error", "Server configuration error. Please contact administrator."),
                status_code=500
            )
        
        # Decode and validate JWT token
        try:
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return HTMLResponse(
                content=get_error_page("Token Expired", "This approval link has expired. Please contact the administrator."),
                status_code=400
            )
        except jwt.InvalidTokenError:
            return HTMLResponse(
                content=get_error_page("Invalid Token", "This approval link is invalid or has been tampered with."),
                status_code=400
            )
        
        # Extract token data
        invoice_id = payload.get("invoice_id")
        action = payload.get("action")  # "approve" or "reject"
        user_email = payload.get("user_email")
        current_actor.set(f"E-Mail-Link {user_email}")
        nonce = payload.get("nonce")
        created_at = payload.get("created_at")
        
        logger.info(f"Approval request: {action} for invoice {invoice_id} by {user_email}")
        
        # Get client IP for audit
        client_ip = request.client.host
        user_agent = request.headers.get("user-agent", "")
        
        # Check if token was already used (mock check for now)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # Process the approval action
        if action == "approve":
            result = await process_approval(invoice_id, user_email, client_ip, user_agent, token_hash)
            return HTMLResponse(content=get_success_page("approve", invoice_id, user_email))
            
        elif action == "reject":
            result = await process_rejection(invoice_id, user_email, client_ip, user_agent, token_hash)
            return HTMLResponse(content=get_success_page("reject", invoice_id, user_email))
            
        else:
            return HTMLResponse(
                content=get_error_page("Invalid Action", f"Unknown action: {action}"),
                status_code=400
            )
            
    except Exception as e:
        logger.error(f"Error processing approval: {e}")
        return HTMLResponse(
            content=get_error_page("System Error", "An error occurred while processing your request. Please try again or contact support."),
            status_code=500
        )

async def process_approval(invoice_id: str, user_email: str, client_ip: str, user_agent: str, token_hash: str) -> Dict[str, Any]:
    """Process invoice approval - Supports both single-layer and multi-layer approvals"""
    try:
        logger.info(f"✅ PROCESSING INVOICE APPROVAL: {invoice_id} by {user_email} from IP {client_ip}")
        
        # Check if this invoice has multi-layer approval hierarchy
        hierarchy_result = db_service.get_approval_hierarchy(invoice_id)
        
        if hierarchy_result["success"] and hierarchy_result["data"]:
            # Multi-layer approval process
            logger.info(f"🔄 Processing multi-layer approval for invoice {invoice_id}")
            return await process_multi_layer_approval(invoice_id, user_email, client_ip, user_agent, token_hash)
        else:
            # Traditional single-layer approval
            logger.info(f"📝 Processing single-layer approval for invoice {invoice_id}")
            return await process_single_layer_approval(invoice_id, user_email, client_ip, user_agent, token_hash)
            
    except Exception as e:
        logger.error(f"❌ Failed to process approval for invoice {invoice_id}: {e}")
        raise e

async def process_single_layer_approval(invoice_id: str, user_email: str, client_ip: str, user_agent: str, token_hash: str) -> Dict[str, Any]:
    """Process traditional single-layer approval - Updates database through centralized service"""
    try:
        # Update invoice status through centralized database service
        approval_result = db_service.update_invoice_bauleiter_decision(
            invoice_id=invoice_id,
            decision="approved",
            decided_by=user_email,
            decision_notes=f"Approved via email link from IP {client_ip}"
        )
        
        if not approval_result["success"]:
            logger.error(f"❌ Failed to approve invoice {invoice_id}: {approval_result['error']}")
            raise Exception(f"Database update failed: {approval_result['error']}")
        
        # Log approval in audit trail
        audit_result = await db_service.log_email_audit(
            invoice_id=invoice_id,
            event_type="approval_decision",
            recipient_email=user_email,
            success=True,
            details={
                "action": "approved",
                "approval_type": "single_layer",
                "ip_address": client_ip,
                "user_agent": user_agent,
                "token_hash": token_hash
            }
        )
        
        if not audit_result["success"]:
            logger.warning(f"⚠️ Failed to log approval audit for invoice {invoice_id}: {audit_result['error']}")
        
        logger.info(f"✅ SINGLE-LAYER INVOICE APPROVED: {invoice_id} by {user_email}")
        
        return {
            "success": True,
            "action": "approved",
            "approval_type": "single_layer",
            "invoice_id": invoice_id,
            "approved_by": user_email,
            "timestamp": datetime.now().isoformat(),
            "status": approval_result["data"].get("status"),
            "approval_status": approval_result["data"].get("approval_status")
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to process single-layer approval for invoice {invoice_id}: {e}")
        raise e

async def process_multi_layer_approval(invoice_id: str, user_email: str, client_ip: str, user_agent: str, token_hash: str) -> Dict[str, Any]:
    """Process multi-layer approval - Updates database through centralized service only"""
    try:
        # Get current approval layer for this user
        current_layer_result = db_service.get_current_approval_layer(invoice_id)
        
        if not current_layer_result["success"]:
            logger.error(f"❌ Failed to get current approval layer for invoice {invoice_id}: {current_layer_result['error']}")
            raise Exception(f"Could not determine approval layer: {current_layer_result['error']}")
        
        current_layer = current_layer_result["data"]
        layer_order = current_layer["layer_order"]
        
        # Validate that this user is the current approver
        if current_layer["approver_email"] != user_email:
            logger.error(f"❌ User {user_email} is not authorized to approve layer {layer_order} for invoice {invoice_id}")
            raise Exception(f"User {user_email} is not the designated approver for this layer")
        
        logger.info(f"🔄 Processing approval for layer {layer_order} by {user_email}")
        
        # Process the approval through centralized database service
        layer_result = db_service.process_approval_layer_decision(
            invoice_id=invoice_id,
            layer_order=layer_order,
            decision="approved",
            decided_by=user_email,
            decision_notes=f"Approved via email link from IP {client_ip}"
        )
        
        if not layer_result["success"]:
            logger.error(f"❌ Failed to process approval layer {layer_order} for invoice {invoice_id}: {layer_result['error']}")
            raise Exception(f"Layer approval failed: {layer_result['error']}")
        
        # Log approval in audit trail
        audit_result = await db_service.log_email_audit(
            invoice_id=invoice_id,
            event_type="approval_decision",
            recipient_email=user_email,
            success=True,
            details={
                "action": "approved",
                "approval_type": "multi_layer",
                "layer_order": layer_order,
                "layer_name": current_layer.get("layer_name"),
                "approver_role": current_layer.get("approver_role"),
                "ip_address": client_ip,
                "user_agent": user_agent,
                "token_hash": token_hash
            }
        )
        
        if not audit_result["success"]:
            logger.warning(f"⚠️ Failed to log multi-layer approval audit for invoice {invoice_id}: {audit_result['error']}")
        
        # Determine response based on approval action
        action = layer_result["action"]
        if action == "final_approval":
            logger.info(f"🎉 INVOICE FULLY APPROVED: {invoice_id} completed all approval layers")
        elif action == "layer_approved":
            logger.info(f"⏭️ LAYER APPROVED: {invoice_id} layer {layer_order} approved, moving to layer {layer_result['next_layer']}")
        
        return {
            "success": True,
            "action": action,
            "approval_type": "multi_layer",
            "invoice_id": invoice_id,
            "approved_by": user_email,
            "layer_order": layer_order,
            "layer_name": current_layer.get("layer_name"),
            "timestamp": datetime.now().isoformat(),
            "status": layer_result["invoice_status"],
            "next_layer": layer_result.get("next_layer"),
            "is_final": action == "final_approval"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to process multi-layer approval for invoice {invoice_id}: {e}")
        raise e

async def process_rejection(invoice_id: str, user_email: str, client_ip: str, user_agent: str, token_hash: str) -> Dict[str, Any]:
    """Process invoice rejection - Supports both single-layer and multi-layer approvals"""
    try:
        logger.info(f"❌ PROCESSING INVOICE REJECTION: {invoice_id} by {user_email} from IP {client_ip}")
        
        # Check if this invoice has multi-layer approval hierarchy
        hierarchy_result = db_service.get_approval_hierarchy(invoice_id)
        
        if hierarchy_result["success"] and hierarchy_result["data"]:
            # Multi-layer approval process
            logger.info(f"🔄 Processing multi-layer rejection for invoice {invoice_id}")
            return await process_multi_layer_rejection(invoice_id, user_email, client_ip, user_agent, token_hash)
        else:
            # Traditional single-layer rejection
            logger.info(f"📝 Processing single-layer rejection for invoice {invoice_id}")
            return await process_single_layer_rejection(invoice_id, user_email, client_ip, user_agent, token_hash)
            
    except Exception as e:
        logger.error(f"❌ Failed to process rejection for invoice {invoice_id}: {e}")
        raise e

async def process_single_layer_rejection(invoice_id: str, user_email: str, client_ip: str, user_agent: str, token_hash: str) -> Dict[str, Any]:
    """Process traditional single-layer rejection - Updates database through centralized service"""
    try:
        # Update invoice status through centralized database service
        rejection_result = db_service.update_invoice_bauleiter_decision(
            invoice_id=invoice_id,
            decision="rejected",
            decided_by=user_email,
            decision_notes=f"Rejected via email link from IP {client_ip}"
        )
        
        if not rejection_result["success"]:
            logger.error(f"❌ Failed to reject invoice {invoice_id}: {rejection_result['error']}")
            raise Exception(f"Database update failed: {rejection_result['error']}")
        
        # Log rejection in audit trail
        audit_result = await db_service.log_email_audit(
            invoice_id=invoice_id,
            event_type="approval_decision",
            recipient_email=user_email,
            success=True,
            details={
                "action": "rejected",
                "approval_type": "single_layer",
                "ip_address": client_ip,
                "user_agent": user_agent,
                "token_hash": token_hash
            }
        )
        
        if not audit_result["success"]:
            logger.warning(f"⚠️ Failed to log rejection audit for invoice {invoice_id}: {audit_result['error']}")
        
        logger.info(f"❌ SINGLE-LAYER INVOICE REJECTED: {invoice_id} by {user_email}")
        
        return {
            "success": True,
            "action": "rejected",
            "approval_type": "single_layer",
            "invoice_id": invoice_id,
            "rejected_by": user_email,
            "timestamp": datetime.now().isoformat(),
            "status": rejection_result["data"].get("status"),
            "approval_status": rejection_result["data"].get("approval_status")
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to process single-layer rejection for invoice {invoice_id}: {e}")
        raise e

async def process_multi_layer_rejection(invoice_id: str, user_email: str, client_ip: str, user_agent: str, token_hash: str) -> Dict[str, Any]:
    """Process multi-layer rejection - Updates database through centralized service only"""
    try:
        # Get current approval layer for this user
        current_layer_result = db_service.get_current_approval_layer(invoice_id)
        
        if not current_layer_result["success"]:
            logger.error(f"❌ Failed to get current approval layer for invoice {invoice_id}: {current_layer_result['error']}")
            raise Exception(f"Could not determine approval layer: {current_layer_result['error']}")
        
        current_layer = current_layer_result["data"]
        layer_order = current_layer["layer_order"]
        
        # Validate that this user is the current approver
        if current_layer["approver_email"] != user_email:
            logger.error(f"❌ User {user_email} is not authorized to reject layer {layer_order} for invoice {invoice_id}")
            raise Exception(f"User {user_email} is not the designated approver for this layer")
        
        logger.info(f"🔄 Processing rejection for layer {layer_order} by {user_email}")
        
        # Process the rejection through centralized database service
        layer_result = db_service.process_approval_layer_decision(
            invoice_id=invoice_id,
            layer_order=layer_order,
            decision="rejected",
            decided_by=user_email,
            decision_notes=f"Rejected via email link from IP {client_ip}"
        )
        
        if not layer_result["success"]:
            logger.error(f"❌ Failed to process rejection layer {layer_order} for invoice {invoice_id}: {layer_result['error']}")
            raise Exception(f"Layer rejection failed: {layer_result['error']}")
        
        # Log rejection in audit trail
        audit_result = await db_service.log_email_audit(
            invoice_id=invoice_id,
            event_type="approval_decision",
            recipient_email=user_email,
            success=True,
            details={
                "action": "rejected",
                "approval_type": "multi_layer",
                "layer_order": layer_order,
                "layer_name": current_layer.get("layer_name"),
                "approver_role": current_layer.get("approver_role"),
                "ip_address": client_ip,
                "user_agent": user_agent,
                "token_hash": token_hash
            }
        )
        
        if not audit_result["success"]:
            logger.warning(f"⚠️ Failed to log multi-layer rejection audit for invoice {invoice_id}: {audit_result['error']}")
        
        logger.info(f"❌ INVOICE REJECTED AT LAYER {layer_order}: {invoice_id} rejected by {user_email}")
        
        return {
            "success": True,
            "action": "rejected",
            "approval_type": "multi_layer",
            "invoice_id": invoice_id,
            "rejected_by": user_email,
            "layer_order": layer_order,
            "layer_name": current_layer.get("layer_name"),
            "timestamp": datetime.now().isoformat(),
            "status": layer_result["invoice_status"],
            "rejection_layer": layer_order
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to process multi-layer rejection for invoice {invoice_id}: {e}")
        raise e

def get_success_page(action: str, invoice_id: str, user_email: str) -> str:
    """Generate success page HTML"""
    action_text = "✅ GENEHMIGT" if action == "approve" else "❌ ABGELEHNT"
    action_description = "genehmigt" if action == "approve" else "abgelehnt"
    
    return f"""
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Rechnung {action_description}</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }}
            .success {{ background: #d4edda; border: 1px solid #c3e6cb; color: #155724; padding: 30px; border-radius: 8px; }}
            .reject {{ background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 30px; border-radius: 8px; }}
            .icon {{ font-size: 48px; margin-bottom: 20px; }}
            .details {{ background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; text-align: left; }}
            .back-btn {{ display: inline-block; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="{'success' if action == 'approve' else 'reject'}">
            <div class="icon">{action_text}</div>
            <h1>Rechnung erfolgreich {action_description}!</h1>
            <p>Die Rechnung wurde erfolgreich {action_description} und das System wurde aktualisiert.</p>
            
            <div class="details">
                <h3>Details:</h3>
                <p><strong>Rechnung:</strong> {invoice_id}</p>
                <p><strong>Aktion:</strong> {action_description.title()}</p>
                <p><strong>Bearbeitet von:</strong> {user_email}</p>
                <p><strong>Zeitstempel:</strong> {datetime.now().strftime('%d.%m.%Y um %H:%M:%S')}</p>
            </div>
            
            <p><strong>✅ Die Entscheidung wurde gespeichert und alle Beteiligten wurden benachrichtigt.</strong></p>
            
            <div style="margin-top: 30px; padding: 15px; background: #fff3cd; border-radius: 5px;">
                <small><strong>Hinweis:</strong> Dieser Genehmigungslink ist jetzt ungültig und kann nicht erneut verwendet werden.</small>
            </div>
        </div>
    </body>
    </html>
    """

def get_error_page(title: str, message: str) -> str:
    """Generate error page HTML"""
    return f"""
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Fehler - {title}</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }}
            .error {{ background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; padding: 30px; border-radius: 8px; }}
            .icon {{ font-size: 48px; margin-bottom: 20px; }}
            .contact {{ background: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="error">
            <div class="icon">⚠️</div>
            <h1>{title}</h1>
            <p>{message}</p>
            
            <div class="contact">
                <h3>Benötigen Sie Hilfe?</h3>
                <p>Kontaktieren Sie den System-Administrator oder fordern Sie einen neuen Genehmigungslink an.</p>
            </div>
            
            <div style="margin-top: 30px;">
                <small>Zeitstempel: {datetime.now().strftime('%d.%m.%Y um %H:%M:%S')}</small>
            </div>
        </div>
    </body>
    </html>
    """

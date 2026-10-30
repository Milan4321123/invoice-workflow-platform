"""
Centralized database service layer for Invoice Management System.
Handles ALL Supabase database operations in one place.
Single source of truth for database communication.
"""
from typing import Optional, Dict, List, Any, Tuple
from supabase import create_client, Client
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import json

from services.audit import AuditLog
from services.gobd import GoBDViolation, changed_fields, deletion_blocked_reason, edit_blocked_reason

load_dotenv()
logger = logging.getLogger(__name__)

class DatabaseService:
    """
    Single database service for ALL Supabase operations.
    Maps directly to your invoices_clean table schema.
    No field mapping confusion - uses your exact field names.
    """
    
    def __init__(self):
        """Initialize the Supabase client"""
        self._client: Optional[Client] = None
        self.table_name = "invoices_clean"  # Your exact table name
        self.storage_buckets = {
            "invoices": "invoices",
            "folder_watcher": "folderwatcher"
        }
        self._initialize_client()
        self.audit = AuditLog(lambda: self._client)

    @staticmethod
    def _storage_location(file_path: str) -> Tuple[str, str]:
        """Map a stored file_path to its (bucket, object name), mirroring UploadService"""
        if file_path.startswith("folder_watcher/"):
            return "folderwatcher", file_path[len("folder_watcher/"):]
        if file_path.startswith("manual/"):
            return "manual-invoices", file_path[len("manual/"):]
        return "invoices", file_path

    def _sanitize_env(self, value: Optional[str]) -> Optional[str]:
        """Strip whitespace and remove non-printable characters from env values."""
        if value is None:
            return None
        original = value
        # Trim whitespace and remove non-printable characters
        value = ''.join(ch for ch in value.strip() if ch.isprintable())
        if value != original:
            logger.warning("⚠️  Sanitized environment value (removed hidden/whitespace characters)")
        return value

    def _initialize_client(self):
        """Initialize the Supabase client using your .env credentials"""
        # Try multiple environment variable names for flexibility
        url = self._sanitize_env(os.getenv("SUPABASE_URL") or os.getenv("SUPA_URL"))
        
        # PRIORITY: Use SERVICE_ROLE_KEY for backend operations to bypass RLS
        service_key = self._sanitize_env(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPA_SERVICE_ROLE_KEY"))
        anon_key = self._sanitize_env(os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPA_KEY"))
        
        # Use service role key for backend, fallback to anon key
        key = service_key or anon_key
        key_type = "service_role" if service_key else "anon"
        
        if url and key:
            try:
                self._client = create_client(url, key)
                logger.info(f"✅ Database service connected to: {url[:50]}... using {key_type} key")
                if key_type == "anon":
                    logger.warning("⚠️  WARNING: Using ANON key for backend - may cause RLS issues. Add SUPABASE_SERVICE_ROLE_KEY for full access.")
            except Exception as e:
                logger.error(f"❌ Failed to connect to database: {e}")
                self._client = None
        else:
            logger.warning("⚠️ Database credentials missing. Running in offline mode.")
            logger.warning(f"Available env vars: SUPABASE_URL={bool(os.getenv('SUPABASE_URL'))}, SERVICE_ROLE_KEY={bool(service_key)}, ANON_KEY={bool(anon_key)}, SUPA_URL={bool(os.getenv('SUPA_URL'))}")
    
    @property
    def client(self) -> Optional[Client]:
        """Get the Supabase client instance"""
        return self._client
    
    @property
    def is_available(self) -> bool:
        """Check if database service is available"""
        return self._client is not None

    async def execute_query(self, query: str, params: tuple = None) -> Dict[str, Any]:
        """
        Execute raw SQL query for email workflow operations.
        Supabase supports PostgreSQL queries via RPC or direct SQL.
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            # For now, let's handle the specific email workflow operations
            # without raw SQL since Supabase client is preferred
            logger.warning(f"Raw SQL query attempted: {query[:100]}...")
            
            # Return success for now - we'll implement proper table operations
            return {
                "success": True, 
                "message": "Query logged - implement specific table operations instead",
                "query": query[:100] + "..." if len(query) > 100 else query
            }
            
        except Exception as e:
            logger.error(f"Failed to execute query: {e}")
            return {"success": False, "error": str(e)}



    async def log_email_attempt(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Log email attempt for audit purposes.
        Uses your actual email_audit_log table.
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            log_record = {
                "invoice_id": email_data["invoice_id"],
                "email_type": email_data["email_type"],
                "recipient_email": email_data["recipient_email"],
                "subject": email_data["subject"],
                "send_success": email_data["send_success"],
                "provider_message_id": email_data.get("provider_message_id"),
                "provider_response": email_data.get("provider_response", {}),
                "template_used": email_data.get("template_used"),
                "email_size_bytes": email_data.get("email_size_bytes")
            }
            
            response = self._client.table("email_audit_log").insert(log_record).execute()
            
            if response.data:
                logger.info(f"✅ Logged email attempt: {email_data['email_type']} to {email_data['recipient_email']}")
                return {"success": True, "data": response.data[0]}
            else:
                return {"success": False, "error": "Failed to log email attempt"}
            
        except Exception as e:
            logger.error(f"❌ Failed to log email attempt: {e}")
            return {"success": False, "error": str(e)}

    
    # =============================================================================
    # CORE INVOICE OPERATIONS (using your exact invoices_clean schema)
    # =============================================================================
    
    def create_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new invoice record in invoices_clean table.
        Uses your exact field names - no confusing mapping.
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            # Debug logging
            logger.info(f"🔍 Creating invoice with data: {invoice_data}")
            
            # Add timestamps
            now = datetime.utcnow().isoformat()
            invoice_data.update({
                "created_at": now,
                "updated_at": now
            })
            
            # Set defaults if not provided
            invoice_data.setdefault("status", "uploaded")
            invoice_data.setdefault("kfw_anrechenbare_kosten", False)
            
            logger.info(f"🔍 Final invoice data being inserted: {invoice_data}")
            
            response = self._client.table(self.table_name).insert(invoice_data).execute()
            
            logger.info(f"🔍 Supabase response: {response}")
            
            if response.data:
                created = response.data[0]
                logger.info(f"✅ Created invoice: {created['id']}")
                self.audit.record(created["id"], "created", changed_fields({}, {
                    k: v for k, v in invoice_data.items() if k not in ("id", "created_at")
                }))
                return {"success": True, "data": created}
            else:
                logger.error(f"❌ Failed to create invoice: {response}")
                return {"success": False, "error": "Insert failed"}
                
        except Exception as e:
            logger.error(f"❌ Database error creating invoice: {e}")
            logger.error(f"❌ Exception type: {type(e)}")
            logger.error(f"❌ Exception args: {e.args}")
            return {"success": False, "error": str(e)}
    
    def get_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """Get a single invoice by ID from invoices_clean table"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            response = (self._client.table(self.table_name)
                       .select("*")
                       .eq("id", invoice_id)
                       .execute())
            
            if response.data:
                invoice = response.data[0]
                # Add URL field for file access using centralized service
                if invoice.get("file_path"):
                    from services.pdf_url_service import pdf_url_service
                    invoice["url"] = pdf_url_service.get_pdf_url(invoice["file_path"], invoice.get("id"))
                return {"success": True, "data": invoice}
            else:
                return {"success": False, "error": "Invoice not found"}
                
        except Exception as e:
            logger.error(f"❌ Database error fetching invoice {invoice_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_all_invoices(self, limit: int = 100) -> Dict[str, Any]:
        """Get all invoices from invoices_clean table"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            response = (self._client.table(self.table_name)
                       .select("*")
                       .order("created_at", desc=True)
                       .limit(limit)
                       .execute())
            
            if response.data is not None:
                # Add URL field for each invoice (for file access)
                for invoice in response.data:
                    if invoice.get("file_path"):
                        from services.pdf_url_service import pdf_url_service
                        invoice["url"] = pdf_url_service.get_pdf_url(invoice["file_path"], invoice.get("id"))
                
                return {
                    "success": True, 
                    "data": response.data,
                    "total": len(response.data)
                }
            else:
                return {"success": True, "data": [], "total": 0}
                
        except Exception as e:
            logger.error(f"❌ Database error fetching invoices: {e}")
            return {"success": False, "error": str(e)}

    def get_invoices(self, limit: int = 100, offset: int = 0, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get invoices with pagination and filtering support for reports"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            # Start with base query
            query = self._client.table(self.table_name).select("*", count='exact')
            
            # Apply filters if provided
            if filters:
                for field, value in filters.items():
                    if value is not None:
                        query = query.eq(field, value)
            
            # Apply ordering, pagination
            response = (query
                       .order("created_at", desc=True)
                       .range(offset, offset + limit - 1)
                       .execute())
            
            if response.data is not None:
                # Add URL field for each invoice (for file access)
                for invoice in response.data:
                    if invoice.get("file_path"):
                        from services.pdf_url_service import pdf_url_service
                        invoice["url"] = pdf_url_service.get_pdf_url(invoice["file_path"], invoice.get("id"))
                
                return {
                    "success": True, 
                    "data": response.data,
                    "total": len(response.data),
                    "count": response.count if hasattr(response, 'count') else len(response.data)
                }
            else:
                return {"success": True, "data": [], "total": 0, "count": 0}
                
        except Exception as e:
            logger.error(f"❌ Database error fetching filtered invoices: {e}")
            return {"success": False, "error": str(e)}
    
    def get_invoice_by_id(self, invoice_id: str) -> Dict[str, Any]:
        """Get a specific invoice by ID from invoices_clean table"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            response = (self._client.table(self.table_name)
                       .select("*")
                       .eq("id", invoice_id)
                       .execute())
            
            if response.data and len(response.data) > 0:
                # Add URL field for file access using centralized service
                invoice = response.data[0]
                if invoice.get("file_path"):
                    from services.pdf_url_service import pdf_url_service
                    invoice["url"] = pdf_url_service.get_pdf_url(invoice["file_path"], invoice.get("id"))
                
                logger.info(f"✅ Retrieved invoice: {invoice_id}")
                return {"success": True, "data": invoice}
            else:
                return {"success": False, "error": "Invoice not found"}
                
        except Exception as e:
            logger.error(f"❌ Database error fetching invoice {invoice_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def _write_invoice(self, invoice_id: str, update_data: Dict[str, Any], action: str):
        """
        The one way an invoice row changes: refuses what the GoBD forbid
        (raises GoBDViolation) and logs every changed field with old and new value.
        """
        before_rows = self._client.table(self.table_name).select("*").eq("id", invoice_id).execute().data
        before = before_rows[0] if before_rows else {}
        reason = edit_blocked_reason(before, update_data)
        if reason:
            raise GoBDViolation(reason)

        response = self._client.table(self.table_name).update(update_data).eq("id", invoice_id).execute()
        changes = changed_fields(before, update_data)
        if response.data and changes:
            self.audit.record(invoice_id, action, changes)
        return response

    def update_invoice(self, invoice_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an invoice record in invoices_clean table"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            # Add update timestamp
            update_data["updated_at"] = datetime.utcnow().isoformat()
            
            response = self._write_invoice(invoice_id, update_data, "updated")
            
            if response.data:
                logger.info(f"✅ Updated invoice: {invoice_id}")
                return {"success": True, "data": response.data[0]}
            else:
                return {"success": False, "error": "Invoice not found or update failed"}

        except GoBDViolation as e:
            return {"success": False, "error": str(e), "locked": True}
        except Exception as e:
            logger.error(f"❌ Database error updating invoice {invoice_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def update_invoice_status(self, invoice_id: str, status: str, review_status: str = None) -> Dict[str, Any]:
        """
        Update invoice status fields using the 3-stage workflow.
        
        3-Stage Workflow:
        1. nicht begonnen: status='pending'/'uploaded', review_status='pending'/null
        2. in Bearbeitung: status='edited', review_status='under_review'  
        3. abgeschlossen: status='completed', review_status='completed_review'
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        # Validate status values against your schema constraints
        valid_statuses = [
            'pending', 'uploaded', 'edited', 'pending_email', 'edit_completed',
            'in_review_by_bauleiter', 'approved_by_bauleiter', 'rejected_by_bauleiter',
            'completed', 'error'
        ]
        
        valid_review_statuses = ['pending', 'under_review', 'completed_review', 'needs_attention']
        
        if status not in valid_statuses:
            return {"success": False, "error": f"Invalid status: {status}. Must be one of: {valid_statuses}"}
        
        if review_status and review_status not in valid_review_statuses:
            return {"success": False, "error": f"Invalid review_status: {review_status}. Must be one of: {valid_review_statuses}"}
        
        try:
            # Build update data
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if review_status:
                update_data["review_status"] = review_status
            
            # Log the status change for debugging
            logger.info(f"🔄 Updating invoice {invoice_id}: status='{status}', review_status='{review_status}'")
            
            response = self._write_invoice(invoice_id, update_data, "status_changed")
            
            if response.data and len(response.data) > 0:
                updated_invoice = response.data[0]
                logger.info(f"✅ Status updated successfully: {invoice_id} -> status='{updated_invoice.get('status')}', review_status='{updated_invoice.get('review_status')}'")
                return {"success": True, "data": updated_invoice}
            else:
                logger.error(f"❌ Status update failed: No data returned for invoice {invoice_id}")
                return {"success": False, "error": "Invoice not found or status update failed"}
                
        except GoBDViolation as e:
            return {"success": False, "error": str(e), "locked": True}
        except Exception as e:
            logger.error(f"❌ Database error updating status for invoice {invoice_id}: {e}")
            return {"success": False, "error": str(e)}

    def update_invoice_to_editing_stage(self, invoice_id: str) -> Dict[str, Any]:
        """Update invoice to 'in Bearbeitung' stage when editing starts"""
        return self.update_invoice_status(invoice_id, 'edited', 'under_review')
    
    def update_invoice_to_completed_stage(self, invoice_id: str, completed_by: str = None, notes: str = None) -> Dict[str, Any]:
        """Update invoice to 'abgeschlossen' stage when completed"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            # First get the current invoice to check if it has Skonto data
            current_invoice = self.get_invoice(invoice_id)
            
            update_data = {
                "status": "completed",
                "review_status": "completed_review",
                "reviewed_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # If invoice has Skonto data and no decision yet, set to pending for Prüfbericht tracking
            if (current_invoice.get("success") and 
                current_invoice["data"].get("skonto_datum") and 
                current_invoice["data"].get("skonto_prozent") and 
                not current_invoice["data"].get("skonto_decision")):
                update_data["skonto_decision"] = "pending"
                logger.info(f"🎯 Setting skonto_decision to 'pending' for invoice {invoice_id} with Skonto data")
            
            if completed_by:
                update_data["reviewed_by"] = completed_by
            
            if notes:
                update_data["review_notes"] = notes
            
            logger.info(f"🏁 Completing invoice {invoice_id} by {completed_by}")
            
            response = self._write_invoice(invoice_id, update_data, "editing_completed")
            
            if response.data and len(response.data) > 0:
                updated_invoice = response.data[0]
                logger.info(f"✅ Invoice completed successfully: {invoice_id}")
                return {"success": True, "data": updated_invoice}
            else:
                return {"success": False, "error": "Invoice not found or completion failed"}
                
        except GoBDViolation as e:
            return {"success": False, "error": str(e), "locked": True}
        except Exception as e:
            logger.error(f"❌ Database error completing invoice {invoice_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def update_invoice_sent_to_bauleiter(self, invoice_id: str, bauleiter_email: str, sent_by: str = None) -> Dict[str, Any]:
        """
        Update invoice status when sent to Bauleiter for approval.
        Uses your actual database schema columns.
        """
        try:
            now_iso = datetime.utcnow().isoformat()
            
            update_data = {
                "status": "in_review_by_bauleiter",
                "review_status": "under_review",
                "bauleiter_email": bauleiter_email,
                "bauleiter_review_sent_at": now_iso,  # Your actual column!
                "approval_status": "pending",
                "updated_at": now_iso
            }
            
            # Add audit trail in review_notes
            if sent_by:
                update_data["review_notes"] = f"Sent to Bauleiter {bauleiter_email} by {sent_by} at {now_iso}"
            
            logger.info(f"📧 Sending invoice {invoice_id} to Bauleiter: {bauleiter_email}")
            
            return self.update_invoice(invoice_id, update_data)
            
        except Exception as e:
            logger.error(f"❌ Error updating invoice sent to Bauleiter {invoice_id}: {e}")
            return {"success": False, "error": str(e)}

    def update_invoice_bauleiter_decision(self, invoice_id: str, decision: str, decided_by: str = None, decision_notes: str = None) -> Dict[str, Any]:
        """
        Update invoice with Bauleiter's approval/rejection decision.
        Uses your actual database schema columns.
        """
        if decision not in ["approved", "rejected"]:
            return {"success": False, "error": f"Invalid decision: {decision}. Must be 'approved' or 'rejected'"}
        
        try:
            now_iso = datetime.utcnow().isoformat()
            new_status = f"{decision}_by_bauleiter"
            new_review_status = "completed_review" if decision == "approved" else "needs_attention"
            
            update_data = {
                "status": new_status,
                "review_status": new_review_status,
                "approval_status": decision,  # 'approved' or 'rejected'
                "approved_at": now_iso,       # Your actual column!
                "approval_method": "email_link",  # Your actual column!
                "updated_at": now_iso
            }
            
            if decided_by:
                update_data["reviewed_by"] = decided_by
                update_data["reviewed_at"] = now_iso
            
            if decision_notes:
                update_data["review_notes"] = decision_notes
            
            logger.info(f"⚖️ Bauleiter decision for invoice {invoice_id}: {decision.upper()}")
            
            return self.update_invoice(invoice_id, update_data)
            
        except Exception as e:
            logger.error(f"❌ Error updating Bauleiter decision for invoice {invoice_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_invoices_by_status(self, status: str, limit: int = 100) -> Dict[str, Any]:
        """
        Get invoices filtered by status using existing query patterns.
        Useful for dashboard filtering and reports.
        """
        try:
            filters = {"status": status}
            return self.get_invoices(limit=limit, filters=filters)
            
        except Exception as e:
            logger.error(f"❌ Error getting invoices by status {status}: {e}")
            return {"success": False, "error": str(e)}

    def get_pending_bauleiter_approvals(self, bauleiter_email: str = None, limit: int = 50) -> Dict[str, Any]:
        """
        Get invoices pending Bauleiter approval using existing query patterns.
        Optionally filter by specific Bauleiter email.
        """
        try:
            filters = {"status": "in_review_by_bauleiter"}
            
            if bauleiter_email:
                filters["bauleiter_email"] = bauleiter_email
            
            logger.info(f"🔍 Looking for pending approvals with filters: {filters}")
            result = self.get_invoices(limit=limit, filters=filters)
            
            if result["success"]:
                logger.info(f"📋 Found {len(result['data'])} invoices pending Bauleiter approval")
            else:
                logger.warning(f"⚠️ Failed to query pending approvals: {result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error getting pending Bauleiter approvals: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_invoice(self, invoice_id: str) -> Dict[str, Any]:
        """
        Delete an invoice record from invoices_clean table.
        Performs comprehensive cleanup including:
        - Invoice record deletion
        - File storage cleanup
        - Skonto tracking data cleanup (automatic via cascade)
        - Logging for audit trail
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            # First get the invoice to check details before deletion
            invoice_result = self.get_invoice(invoice_id)
            
            if not invoice_result.get("success"):
                return {"success": False, "error": "Invoice not found"}
            
            invoice_data = invoice_result["data"]
            filename = invoice_data.get("file_name", "unknown")
            file_path = invoice_data.get("file_path")

            blocked = deletion_blocked_reason(invoice_data)
            if blocked:
                return {"success": False, "error": blocked, "locked": True}
            
            # Check if invoice has Skonto data for logging
            has_skonto_data = bool(
                invoice_data.get("skonto_datum") or 
                invoice_data.get("skonto_prozent") or 
                invoice_data.get("skonto_reminder_sent") or 
                invoice_data.get("skonto_decision")
            )
            
            # Log pre-deletion information
            logger.info(f"🗑️ Preparing to delete invoice {invoice_id} ('{filename}')")
            if has_skonto_data:
                skonto_status = {
                    "skonto_datum": invoice_data.get("skonto_datum"),
                    "skonto_prozent": invoice_data.get("skonto_prozent"),
                    "reminder_sent": invoice_data.get("skonto_reminder_sent", False),
                    "decision": invoice_data.get("skonto_decision", "pending"),
                    "actual_savings": invoice_data.get("actual_skonto_savings")
                }
                logger.info(f"💰 Invoice contains Skonto data: {skonto_status}")
            
            # Delete the invoice record (this will also delete all associated Skonto data)
            response = (self._client.table(self.table_name)
                       .delete()
                       .eq("id", invoice_id)
                       .execute())
            
            if response.data:
                logger.info(f"✅ Successfully deleted invoice {invoice_id} from database")
                self.audit.record(invoice_id, "deleted", changed_fields(invoice_data, {
                    "file_name": None, "file_path": None, "status": None,
                    "rechnungsnummer": None, "rechnungsbetrag": None, "rechnungssteller": None,
                }))
                if has_skonto_data:
                    logger.info(f"💰 Associated Skonto tracking data automatically cleaned up")
                
                # Also delete from storage if file exists
                if file_path:
                    try:
                        bucket, name = self._storage_location(file_path)
                        self._client.storage.from_(bucket).remove([name])
                        logger.info(f"📁 Successfully deleted file from storage: {bucket}/{name}")
                    except Exception as storage_error:
                        logger.warning(f"⚠️ Could not delete file from storage: {storage_error}")
                        # Don't fail the whole operation if storage cleanup fails
                
                # Return comprehensive deletion info
                deletion_summary = {
                    "invoice_id": invoice_id,
                    "filename": filename,
                    "file_path": file_path,
                    "had_skonto_data": has_skonto_data,
                    "storage_cleaned": file_path is not None
                }
                
                logger.info(f"🎯 Invoice deletion completed successfully: {deletion_summary}")
                return {"success": True, "data": response.data, "deletion_summary": deletion_summary}
            else:
                return {"success": False, "error": "Invoice not found or already deleted"}
                
        except Exception as e:
            logger.error(f"❌ Database error deleting invoice {invoice_id}: {e}")
            return {"success": False, "error": str(e)}

    def delete_all_invoices(self) -> Dict[str, Any]:
        """
        Delete all invoices from the system with comprehensive cleanup.
        Performs bulk deletion including:
        - All invoice records deletion
        - All associated Skonto data cleanup (automatic)
        - Storage cleanup for all files
        - Comprehensive logging and summary
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            # First get all invoices to check details before deletion
            all_invoices_result = self.get_all_invoices(limit=10000)  # Get all invoices
            
            if not all_invoices_result.get("success"):
                return {"success": False, "error": "Failed to retrieve invoices for deletion"}
            
            # Records under retention stay; only untouched uploads are removed (GoBD)
            invoices = [i for i in all_invoices_result["data"] if not deletion_blocked_reason(i)]
            kept_count = len(all_invoices_result["data"]) - len(invoices)
            total_count = len(invoices)
            
            if total_count == 0:
                return {
                    "success": True, 
                    "message": "No invoices to delete",
                    "deletion_summary": {
                        "total_deleted": 0,
                        "kept_for_retention": kept_count,
                        "skonto_data_cleaned": 0,
                        "storage_files_cleaned": 0,
                        "failed_deletions": 0
                    }
                }
            
            logger.info(f"🗑️ Starting bulk deletion of {total_count} invoices...")
            
            # Track deletion statistics
            deleted_count = 0
            skonto_data_count = 0
            storage_cleaned_count = 0
            failed_count = 0
            file_paths_to_clean = []
            
            # Collect statistics before deletion
            for invoice in invoices:
                # Check if invoice has Skonto data
                has_skonto_data = bool(
                    invoice.get("skonto_datum") or 
                    invoice.get("skonto_prozent") or 
                    invoice.get("skonto_reminder_sent") or 
                    invoice.get("skonto_decision")
                )
                if has_skonto_data:
                    skonto_data_count += 1
                
                # Track files for storage cleanup
                file_path = invoice.get("file_path")
                if file_path:
                    file_paths_to_clean.append(file_path)
            
            logger.info(f"💰 Found {skonto_data_count} invoices with Skonto data")
            logger.info(f"📁 Found {len(file_paths_to_clean)} files to clean from storage")
            
            # Perform bulk deletion of all records
            response = (self._client.table(self.table_name)
                       .delete()
                       .in_("id", [invoice["id"] for invoice in invoices])
                       .execute())
            
            if response.data is not None:
                deleted_count = len(response.data) if response.data else total_count
                logger.info(f"✅ Successfully deleted {deleted_count} invoice records from database")
                for invoice in invoices:
                    self.audit.record(invoice["id"], "deleted", changed_fields(invoice, {
                        "file_name": None, "file_path": None, "status": None,
                    }))
                
                # Clean up storage files
                if file_paths_to_clean:
                    logger.info(f"📁 Cleaning up {len(file_paths_to_clean)} files from storage...")
                    try:
                        # Bulk delete from storage
                        by_bucket: Dict[str, List[str]] = {}
                        for path in file_paths_to_clean:
                            bucket, name = self._storage_location(path)
                            by_bucket.setdefault(bucket, []).append(name)
                        for bucket, names in by_bucket.items():
                            self._client.storage.from_(bucket).remove(names)
                        storage_cleaned_count = len(file_paths_to_clean)
                        logger.info(f"✅ Successfully cleaned {storage_cleaned_count} files from storage")
                    except Exception as storage_error:
                        logger.warning(f"⚠️ Storage cleanup partially failed: {storage_error}")
                        # Don't fail the whole operation if storage cleanup fails
                
                deletion_summary = {
                    "total_deleted": deleted_count,
                    "kept_for_retention": kept_count,
                    "skonto_data_cleaned": skonto_data_count,
                    "storage_files_cleaned": storage_cleaned_count,
                    "failed_deletions": failed_count
                }
                
                logger.info(f"🎯 Bulk deletion completed successfully: {deletion_summary}")
                return {
                    "success": True, 
                    "message": f"Successfully deleted {deleted_count} invoices",
                    "deletion_summary": deletion_summary
                }
            else:
                return {"success": False, "error": "Bulk deletion failed - no records affected"}
                
        except Exception as e:
            logger.error(f"❌ Database error during bulk deletion: {e}")
            return {"success": False, "error": str(e)}

    
    # =============================================================================
    # STORAGE OPERATIONS (for your invoices and folderwatcher buckets)
    # =============================================================================
    
    def upload_file_to_storage(self, bucket_name: str, file_path: str, file_content: bytes) -> Dict[str, Any]:
        """Upload file to Supabase storage bucket"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            response = self._client.storage.from_(bucket_name).upload(file_path, file_content)
            
            if response:
                # Get public URL
                public_url = self._client.storage.from_(bucket_name).get_public_url(file_path)
                logger.info(f"✅ Uploaded file to {bucket_name}: {file_path}")
                return {"success": True, "url": public_url, "path": file_path}
            else:
                return {"success": False, "error": "Upload failed"}
                
        except Exception as e:
            logger.error(f"❌ Storage upload error: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_file_from_storage(self, bucket_name: str, file_path: str) -> Dict[str, Any]:
        """Delete file from Supabase storage bucket"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            response = self._client.storage.from_(bucket_name).remove([file_path])
            logger.info(f"✅ Deleted file from {bucket_name}: {file_path}")
            return {"success": True}
                
        except Exception as e:
            logger.error(f"❌ Storage delete error: {e}")
            return {"success": False, "error": str(e)}
    
    # =============================================================================
    # DROPDOWN OPTIONS MANAGEMENT
    # =============================================================================
    
    def get_dropdown_options(self, field_name: Optional[str] = None) -> Dict[str, List[Dict[str, Any]]]:
        """Get dropdown options from database"""
        if not self.is_available:
            return {}
        
        try:
            # Build query
            query = self._client.table("dropdown_options").select("*").eq("is_active", True)
            
            if field_name:
                query = query.eq("field_name", field_name)
            
            response = query.order("field_name", desc=False).order("sort_order", desc=False).execute()
            
            if response.data:
                # Group by field_name
                options_by_field = {}
                for option in response.data:
                    field = option["field_name"]
                    if field not in options_by_field:
                        options_by_field[field] = []
                    
                    options_by_field[field].append({
                        "value": option["value"],
                        "label": option["label"],
                        "is_default": option["is_default"]
                    })
                
                logger.info(f"✅ Retrieved dropdown options for fields: {list(options_by_field.keys())}")
                return options_by_field
            else:
                logger.warning("No dropdown options found in database")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Database error fetching dropdown options: {e}")
            return {}
    
    def add_dropdown_option(self, field_name: str, value: str, label: str, is_default: bool = False, metadata: Dict = None) -> Dict[str, Any]:
        """Add a new dropdown option to database"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            # Check if option already exists
            existing = (self._client.table("dropdown_options")
                       .select("id")
                       .eq("field_name", field_name)
                       .eq("value", value)
                       .execute())
            
            if existing.data:
                return {"success": False, "error": "Option already exists"}
            
            # Get max sort_order for this field
            max_order = (self._client.table("dropdown_options")
                        .select("sort_order")
                        .eq("field_name", field_name)
                        .order("sort_order", desc=True)
                        .limit(1)
                        .execute())
            
            sort_order = 1
            if max_order.data:
                sort_order = (max_order.data[0].get("sort_order", 0) or 0) + 1
            
            # Insert new option
            new_option = {
                "field_name": field_name,
                "value": value,
                "label": label,
                "is_default": is_default,
                "sort_order": sort_order,
                "is_active": True,
                "metadata": metadata or {}
            }
            
            response = (self._client.table("dropdown_options")
                       .insert(new_option)
                       .execute())
            
            if response.data:
                logger.info(f"✅ Added dropdown option: {field_name}.{value}")
                return {"success": True, "data": response.data[0]}
            else:
                return {"success": False, "error": "Insert failed"}
                
        except Exception as e:
            logger.error(f"❌ Database error adding dropdown option: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_dropdown_option(self, field_name: str, value: str) -> Dict[str, Any]:
        """Soft delete a dropdown option (set is_active=false)"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            response = (self._client.table("dropdown_options")
                       .update({"is_active": False})
                       .eq("field_name", field_name)
                       .eq("value", value)
                       .execute())
            
            if response.data:
                logger.info(f"✅ Deleted dropdown option: {field_name}.{value}")
                return {"success": True, "data": response.data[0]}
            else:
                return {"success": False, "error": "Option not found"}
                
        except Exception as e:
            logger.error(f"❌ Database error deleting dropdown option: {e}")
            return {"success": False, "error": str(e)}
    
    def update_dropdown_option(self, field_name: str, old_value: str, new_value: str, new_label: str) -> Dict[str, Any]:
        """Update a dropdown option in the database"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            response = (self._client.table("dropdown_options")
                       .update({
                           "value": new_value,
                           "label": new_label
                       })
                       .eq("field_name", field_name)
                       .eq("value", old_value)
                       .eq("is_active", True)
                       .execute())
            
            if response.data:
                logger.info(f"✅ Updated dropdown option: {field_name}.{old_value} -> {new_value}")
                return {"success": True, "data": response.data[0]}
            else:
                return {"success": False, "error": "Option not found or no changes made"}
                
        except Exception as e:
            logger.error(f"❌ Database error updating dropdown option: {e}")
            return {"success": False, "error": str(e)}

    def log_email_send(self, invoice_id: str, email_type: str, log_entry: str) -> Dict[str, Any]:
        """Log email send event without changing status (email service helper)"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            update_data = {
                "email_logs": f"COALESCE(email_logs, '[]'::jsonb) || '{log_entry}'::jsonb",
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if email_type == "editor_notification":
                update_data["edit_bericht_sent_at"] = datetime.utcnow().isoformat()
            
            response = self._write_invoice(invoice_id, update_data, "email_logged")
            
            if response.data:
                logger.info(f"✅ Email log updated for invoice: {invoice_id}")
                return {"success": True, "data": response.data[0]}
            else:
                return {"success": False, "error": "Email log update failed"}
                
        except GoBDViolation as e:
            return {"success": False, "error": str(e), "locked": True}
        except Exception as e:
            logger.error(f"❌ Failed to log email send: {e}")
            return {"success": False, "error": str(e)}

    def update_bauleiter_email_sent(self, invoice_id: str, bauleiter_email: str, log_entry: str) -> Dict[str, Any]:
        """Update Bauleiter email fields without changing status (email service helper)"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            update_data = {
                "bauleiter_email": bauleiter_email,
                "bauleiter_review_sent_at": datetime.utcnow().isoformat(),
                "email_logs": f"COALESCE(email_logs, '[]'::jsonb) || '{log_entry}'::jsonb",
                "updated_at": datetime.utcnow().isoformat()
            }
            
            response = self._write_invoice(invoice_id, update_data, "bauleiter_email_sent")
            
            if response.data:
                logger.info(f"✅ Bauleiter email fields updated for invoice: {invoice_id}")
                return {"success": True, "data": response.data[0]}
            else:
                return {"success": False, "error": "Bauleiter email update failed"}
                
        except GoBDViolation as e:
            return {"success": False, "error": str(e), "locked": True}
        except Exception as e:
            logger.error(f"❌ Failed to update Bauleiter email fields: {e}")
            return {"success": False, "error": str(e)}

    def create_approval_token(self, token_hash: str, invoice_id: str, action: str, 
                            user_email: str, expires_at: datetime, nonce: str) -> Dict[str, Any]:
        """Create approval token (email service helper)"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            token_data = {
                "token_hash": token_hash,
                "invoice_id": invoice_id,
                "action": action,
                "user_email": user_email,
                "expires_at": expires_at.isoformat(),
                "nonce": nonce,
                "created_at": datetime.utcnow().isoformat()
            }
            
            response = self._client.table("approval_tokens").insert(token_data).execute()
            
            if response.data:
                logger.info(f"✅ Approval token created for invoice: {invoice_id}")
                return {"success": True, "data": response.data[0]}
            else:
                return {"success": False, "error": "Token creation failed"}
                
        except Exception as e:
            logger.error(f"❌ Failed to create approval token: {e}")
            return {"success": False, "error": str(e)}

    def create_email_audit_log(self, invoice_id: str, email_type: str, recipient_email: str,
                             subject: str, send_success: bool, provider_message_id: str = None,
                             provider_response: dict = None, template_used: str = None,
                             email_size_bytes: int = None) -> Dict[str, Any]:
        """Create email audit log entry (email service helper)"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            audit_data = {
                "invoice_id": invoice_id,
                "email_type": email_type,
                "recipient_email": recipient_email,
                "subject": subject,
                "send_success": send_success,
                "provider_message_id": provider_message_id,
                "provider_response": json.dumps(provider_response) if provider_response else None,
                "template_used": template_used,
                "email_size_bytes": email_size_bytes,
                "created_at": datetime.utcnow().isoformat()
            }
            
            response = self._client.table("email_audit_log").insert(audit_data).execute()
            
            if response.data:
                logger.info(f"✅ Email audit log created for invoice: {invoice_id}")
                return {"success": True, "data": response.data[0]}
            else:
                return {"success": False, "error": "Email audit log creation failed"}
                
        except Exception as e:
            logger.error(f"❌ Failed to create email audit log: {e}")
            return {"success": False, "error": str(e)}

    def update_approval_status(self, invoice_id: str, status: str, approval_status: str, 
                             approval_method: str) -> Dict[str, Any]:
        """Update invoice approval status (workflow service helper)"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            update_data = {
                "status": status,
                "approval_status": approval_status,
                "approved_at": datetime.utcnow().isoformat(),
                "approval_method": approval_method,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            response = self._write_invoice(invoice_id, update_data, "approval_decided")
            
            if response.data:
                logger.info(f"✅ Approval status updated for invoice: {invoice_id}")
                return {"success": True, "data": response.data[0]}
            else:
                return {"success": False, "error": "Approval status update failed"}
                
        except GoBDViolation as e:
            return {"success": False, "error": str(e), "locked": True}
        except Exception as e:
            logger.error(f"❌ Failed to update approval status: {e}")
            return {"success": False, "error": str(e)}

    def mark_approval_token_used(self, token_hash: str, ip_address: str) -> Dict[str, Any]:
        """Mark approval token as used (workflow service helper)"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            update_data = {
                "used_at": datetime.utcnow().isoformat(),
                "used_by_ip": ip_address
            }
            
            response = (self._client.table("approval_tokens")
                       .update(update_data)
                       .eq("token_hash", token_hash)
                       .execute())
            
            if response.data:
                logger.info(f"✅ Approval token marked as used: {token_hash[:8]}...")
                return {"success": True, "data": response.data[0]}
            else:
                return {"success": False, "error": "Token update failed"}
                
        except Exception as e:
            logger.error(f"❌ Failed to mark token as used: {e}")
            return {"success": False, "error": str(e)}

    def create_security_event(self, event_type: str, ip_address: str, user_email: str = None,
                            invoice_id: str = None, event_data: dict = None, 
                            risk_level: str = "low") -> Dict[str, Any]:
        """Create security event log (workflow service helper)"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            security_data = {
                "event_type": event_type,
                "ip_address": ip_address,
                "user_email": user_email,
                "invoice_id": invoice_id,
                "event_data": json.dumps(event_data) if event_data else None,
                "risk_level": risk_level,
                "created_at": datetime.utcnow().isoformat()
            }
            
            response = self._client.table("security_events").insert(security_data).execute()
            
            if response.data:
                logger.info(f"✅ Security event logged: {event_type}")
                return {"success": True, "data": response.data[0]}
            else:
                return {"success": False, "error": "Security event creation failed"}
                
        except Exception as e:
            logger.error(f"❌ Failed to create security event: {e}")
            return {"success": False, "error": str(e)}

    # =============================================================================
    # SKONTO MANAGEMENT METHODS
    # =============================================================================
    
    def get_invoices_with_skonto_due(self, days_ahead: int = 7) -> Dict[str, Any]:
        """
        Get invoices with Skonto expiring within specified days.
        
        Args:
            days_ahead: Number of days ahead to check for Skonto expiry
            
        Returns:
            Dict with success status and list of invoices
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            from datetime import timedelta
            
            # Calculate the date range for Skonto due
            today = datetime.now().date()
            future_date = today + timedelta(days=days_ahead)
            
            # Query invoices with Skonto due within the specified period
            # Include invoices where skonto_decision is pending, null, or not set
            response = self._client.table(self.table_name)\
                .select("*")\
                .not_.is_("skonto_datum", "null")\
                .not_.is_("skonto_prozent", "null")\
                .execute()
            
            if response.data:
                # Filter invoices based on Skonto date and decision status
                filtered_invoices = []
                for invoice in response.data:
                    try:
                        # Only include invoices where skonto_decision is pending, null, or not_applicable
                        skonto_decision = invoice.get("skonto_decision")
                        if skonto_decision not in [None, "pending", "not_applicable"]:
                            continue  # Skip taken/missed invoices
                        skonto_datum = invoice.get("skonto_datum")
                        if not skonto_datum:
                            continue
                            
                        # Parse different date formats
                        if isinstance(skonto_datum, str):
                            if "." in skonto_datum:
                                skonto_date = datetime.strptime(skonto_datum, "%d.%m.%Y").date()
                            elif "-" in skonto_datum:
                                skonto_date = datetime.strptime(skonto_datum, "%Y-%m-%d").date()
                            else:
                                skonto_date = datetime.strptime(skonto_datum, "%Y%m%d").date()
                        else:
                            skonto_date = skonto_datum
                        
                        # Check if Skonto is due within the specified period
                        if today <= skonto_date <= future_date:
                            filtered_invoices.append(invoice)
                            
                    except Exception as e:
                        logger.warning(f"Failed to parse Skonto date for invoice {invoice.get('id')}: {e}")
                        continue
                
                logger.info(f"✅ Found {len(filtered_invoices)} invoices with Skonto due within {days_ahead} days")
                return {"success": True, "data": filtered_invoices}
            else:
                logger.info("No invoices found with Skonto due")
                return {"success": True, "data": []}
                
        except Exception as e:
            logger.error(f"❌ Failed to get invoices with Skonto due: {e}")
            return {"success": False, "error": str(e)}

    def update_skonto_reminder_sent(self, invoice_id: str) -> Dict[str, Any]:
        """
        Mark Skonto reminder as sent for an invoice.
        
        Args:
            invoice_id: The ID of the invoice
            
        Returns:
            Dict with success status and updated data
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            update_data = {
                "skonto_reminder_sent": True,
                "skonto_reminder_sent_at": datetime.utcnow().isoformat()
            }
            
            response = self._write_invoice(invoice_id, update_data, "skonto_reminder_sent")
            
            if response.data:
                logger.info(f"✅ Marked Skonto reminder as sent for invoice {invoice_id}")
                return {"success": True, "data": response.data[0]}
            else:
                logger.error(f"❌ Failed to update Skonto reminder status for invoice {invoice_id}")
                return {"success": False, "error": "Skonto reminder update failed"}
                
        except GoBDViolation as e:
            return {"success": False, "error": str(e), "locked": True}
        except Exception as e:
            logger.error(f"❌ Failed to update Skonto reminder status: {e}")
            return {"success": False, "error": str(e)}

    def update_skonto_decision(self, invoice_id: str, decision: str, actual_savings: float = None, 
                             decision_timestamp: str = None, decision_email: str = None) -> Dict[str, Any]:
        """
        Update Skonto decision for an invoice.
        
        Args:
            invoice_id: The ID of the invoice
            decision: The Skonto decision ('taken', 'missed', 'not_applicable')
            actual_savings: The actual savings amount (optional)
            decision_timestamp: When the decision was made (optional)
            decision_email: Email of who made the decision (optional)
            
        Returns:
            Dict with success status and updated data
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        # Validate decision value
        valid_decisions = ["taken", "missed", "not_applicable"]
        if decision not in valid_decisions:
            return {"success": False, "error": f"Invalid decision. Must be one of: {valid_decisions}"}
        
        try:
            update_data = {
                "skonto_decision": decision
            }
            
            # Only update actual_savings if provided
            if actual_savings is not None:
                update_data["actual_skonto_savings"] = actual_savings
            
            response = self._write_invoice(invoice_id, update_data, "skonto_decision")
            
            if response.data:
                logger.info(f"✅ Updated Skonto decision for invoice {invoice_id}: {decision}")
                return {"success": True, "data": response.data[0]}
            else:
                logger.error(f"❌ Failed to update Skonto decision for invoice {invoice_id}")
                return {"success": False, "error": "Skonto decision update failed"}
                
        except GoBDViolation as e:
            return {"success": False, "error": str(e), "locked": True}
        except Exception as e:
            logger.error(f"❌ Failed to update Skonto decision: {e}")
            return {"success": False, "error": str(e)}

    def get_skonto_statistics(self, date_from: str = None, date_to: str = None) -> Dict[str, Any]:
        """
        Get Skonto statistics for reporting.
        
        Args:
            date_from: Start date for statistics (optional)
            date_to: End date for statistics (optional)
            
        Returns:
            Dict with success status and statistics data
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            # Build query
            query = self._client.table(self.table_name).select("*")
            
            # Add date filters if provided
            if date_from:
                query = query.gte("rechnungsdatum", date_from)
            if date_to:
                query = query.lte("rechnungsdatum", date_to)
            
            # Execute query
            response = query.execute()
            
            if response.data:
                invoices = response.data
                
                # Calculate statistics
                stats = {
                    "total_invoices_with_skonto": 0,
                    "skonto_reminders_sent": 0,
                    "skonto_taken": 0,
                    "skonto_missed": 0,
                    "skonto_not_applicable": 0,
                    "total_potential_savings": 0.0,
                    "total_actual_savings": 0.0,
                    "pending_decisions": 0
                }
                
                for invoice in invoices:
                    # Check if invoice has Skonto data
                    if invoice.get("skonto_datum") and invoice.get("skonto_prozent"):
                        stats["total_invoices_with_skonto"] += 1
                        
                        # Calculate potential savings
                        total_amount = invoice.get("rechnungsbetrag")
                        skonto_percent = invoice.get("skonto_prozent")
                        if total_amount and skonto_percent:
                            potential_savings = float(total_amount) * float(skonto_percent) / 100
                            stats["total_potential_savings"] += potential_savings
                        
                        # Check reminder status
                        if invoice.get("skonto_reminder_sent"):
                            stats["skonto_reminders_sent"] += 1
                        
                        # Check decision status
                        decision = invoice.get("skonto_decision")
                        if decision == "taken":
                            stats["skonto_taken"] += 1
                            actual_savings = invoice.get("actual_skonto_savings")
                            if actual_savings:
                                stats["total_actual_savings"] += float(actual_savings)
                        elif decision == "missed":
                            stats["skonto_missed"] += 1
                        elif decision == "not_applicable":
                            stats["skonto_not_applicable"] += 1
                        else:
                            stats["pending_decisions"] += 1
                
                logger.info(f"✅ Generated Skonto statistics for {len(invoices)} invoices")
                return {"success": True, "data": stats}
            else:
                logger.info("No invoices found for statistics")
                return {"success": True, "data": {}}
                
        except Exception as e:
            logger.error(f"❌ Failed to get Skonto statistics: {e}")
            return {"success": False, "error": str(e)}

    def update_expired_skonto_statuses(self) -> Dict[str, Any]:
        """
        Update invoices with expired Skonto dates to 'missed' status.
        Should be called periodically or before displaying Skonto data.
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            from datetime import datetime
            
            # Get current date
            today = datetime.now().date()
            
            # Get all invoices with Skonto data that have pending decision
            response = self._client.table(self.table_name)\
                .select("*")\
                .not_.is_("skonto_datum", "null")\
                .not_.is_("skonto_prozent", "null")\
                .in_("skonto_decision", ["pending", None])\
                .execute()
            
            if not response.data:
                return {"success": True, "updated_count": 0, "message": "No invoices to update"}
            
            updated_count = 0
            
            for invoice in response.data:
                try:
                    skonto_datum = invoice.get("skonto_datum")
                    if not skonto_datum:
                        continue
                    
                    # Parse the Skonto date
                    if isinstance(skonto_datum, str):
                        if "-" in skonto_datum:
                            skonto_date = datetime.strptime(skonto_datum, "%Y-%m-%d").date()
                        else:
                            skonto_date = datetime.strptime(skonto_datum, "%d.%m.%Y").date()
                    else:
                        skonto_date = skonto_datum
                    
                    # Check if expired
                    if skonto_date < today:
                        # Update to missed status
                        update_result = self.update_skonto_decision(
                            invoice["id"], 
                            "missed", 
                            actual_savings=0.0
                        )
                        
                        if update_result["success"]:
                            updated_count += 1
                            logger.info(f"📅 Marked expired Skonto as missed: {invoice['id']}")
                        
                except Exception as e:
                    logger.warning(f"Failed to process invoice {invoice.get('id')}: {e}")
                    continue
            
            logger.info(f"✅ Updated {updated_count} expired Skonto invoices to 'missed' status")
            return {
                "success": True, 
                "updated_count": updated_count,
                "message": f"Updated {updated_count} expired invoices"
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to update expired Skonto statuses: {e}")
            return {"success": False, "error": str(e)}

    # =============================================================================
    # USER MANAGEMENT (for authentication)
    # =============================================================================
    
    async def ensure_users_table_exists(self) -> Dict[str, Any]:
        """Ensure users table exists in database"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            # Check if users table exists by trying to query it
            response = self._client.table("users").select("*").limit(1).execute()
            logger.info("✅ Users table exists")
            return {"success": True, "message": "Users table exists"}
            
        except Exception as e:
            logger.warning(f"⚠️ Users table may not exist: {e}")
            # In Supabase, tables are typically created through the web interface
            # For development, we'll note this and continue
            return {"success": False, "error": f"Users table not found: {e}"}

    def get_all_invoices_with_skonto_data(self) -> Dict[str, Any]:
        """
        Get ALL invoices that have Skonto data, regardless of deadline or status.
        This is used for the Prüfbericht (Skonto report) page to show comprehensive data.
        
        Returns:
            Dict with success status and list of all invoices with Skonto information
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        
        try:
            # Query all invoices that have both skonto_datum and skonto_prozent
            response = self._client.table(self.table_name)\
                .select("*")\
                .not_.is_("skonto_datum", "null")\
                .not_.is_("skonto_prozent", "null")\
                .order("created_at", desc=True)\
                .execute()
            
            if response.data:
                # Add URL field for each invoice (for file access)
                for invoice in response.data:
                    if invoice.get("file_path"):
                        from services.pdf_url_service import pdf_url_service
                        invoice["url"] = pdf_url_service.get_pdf_url(invoice["file_path"], invoice.get("id"))
                
                logger.info(f"✅ Found {len(response.data)} invoices with Skonto data")
                return {"success": True, "data": response.data}
            else:
                logger.info("No invoices found with Skonto data")
                return {"success": True, "data": []}
                
        except Exception as e:
            logger.error(f"❌ Failed to get invoices with Skonto data: {e}")
            return {"success": False, "error": str(e)}

    def find_same_invoice_number(self, supplier: str, invoice_number: str, exclude_id: str) -> Dict[str, Any]:
        """Other invoices from the same supplier with the same number, i.e. a possible double payment"""
        if not self.is_available:
            return {"success": False, "error": "Database unavailable"}
        try:
            response = (self._client.table(self.table_name)
                       .select("id,file_name,rechnungsdatum,rechnungsbetrag,status")
                       .eq("rechnungssteller", supplier)
                       .eq("rechnungsnummer", invoice_number)
                       .neq("id", exclude_id)
                       .execute())
            return {"success": True, "data": response.data or []}
        except Exception as e:
            logger.error(f"❌ Duplicate invoice number check failed: {e}")
            return {"success": False, "error": str(e)}

    def get_invoices_for_export(self, columns: List[str]) -> List[Dict[str, Any]]:
        """All invoices with the given columns, without signed file URLs (export can be large)"""
        rows, start, page_size = [], 0, 1000
        while True:
            page = (self._client.table(self.table_name)
                    .select(",".join(columns))
                    .order("created_at")
                    .range(start, start + page_size - 1)
                    .execute()).data or []
            rows.extend(page)
            if len(page) < page_size:
                return rows
            start += page_size

    def check_duplicate_by_filename(self, filename: str) -> Dict[str, Any]:
        """
        Check if a file with the given filename already exists in the database
        Returns detailed information about existing file if found
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable", "duplicate_found": False}
        
        try:
            response = self._client.table(self.table_name).select(
                "id,file_name,created_at,file_size"
            ).eq("file_name", filename).execute()
            
            if response.data and len(response.data) > 0:
                existing_file = response.data[0]
                return {
                    "success": True,
                    "duplicate_found": True,
                    "existing_file": {
                        "id": existing_file.get("id"),
                        "filename": existing_file.get("file_name"),
                        "created_at": existing_file.get("created_at"),
                        "file_size": existing_file.get("file_size")
                    }
                }
            else:
                return {"success": True, "duplicate_found": False}
                
        except Exception as e:
            logger.error(f"Error checking for duplicate filename '{filename}': {e}")
            return {"success": False, "error": str(e), "duplicate_found": False}
    
    def check_duplicate_by_file_hash(self, file_hash: str) -> Dict[str, Any]:
        """
        Check if a file with the given hash already exists in the database
        Note: Requires file_hash column to be added to schema
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable", "duplicate_found": False}
        
        try:
            # This would require adding a file_hash column to the schema
            # For now, return not found since column doesn't exist yet
            return {"success": True, "duplicate_found": False}
                
        except Exception as e:
            logger.error(f"Error checking for duplicate file hash '{file_hash}': {e}")
            return {"success": False, "error": str(e), "duplicate_found": False}
    
    def check_duplicate_by_content_similarity(self, filename: str, file_size: int, tolerance_bytes: int = 1024) -> Dict[str, Any]:
        """
        Check for files with similar content (same filename pattern and similar file size)
        This can help detect re-uploads of the same invoice with minor modifications
        """
        if not self.is_available:
            return {"success": False, "error": "Database unavailable", "duplicate_found": False}
        
        try:
            # Extract pattern parts from filename
            import re
            pattern_match = re.match(r'^(\d{8})_([^_]+)_([^_]+)_(.+)\.pdf$', filename)
            if not pattern_match:
                return {"success": True, "duplicate_found": False}
            
            date_part, project_part, gewerk_part, lieferant_part = pattern_match.groups()
            
            # Query for files with similar file size and filename patterns
            min_size = max(0, file_size - tolerance_bytes)
            max_size = file_size + tolerance_bytes
            
            response = self._client.table(self.table_name).select(
                "id,file_name,created_at,file_size"
            ).gte("file_size", min_size).lte("file_size", max_size).execute()
            
            if response.data:
                similar_files = []
                for file_record in response.data:
                    # Check if filename matches pattern and has similar components
                    existing_filename = file_record.get("file_name", "")
                    existing_match = re.match(r'^(\d{8})_([^_]+)_([^_]+)_(.+)\.pdf$', existing_filename)
                    
                    if existing_match:
                        _, existing_project, existing_gewerk, existing_lieferant = existing_match.groups()
                        
                        # Check for similarity (case-insensitive)
                        if (project_part.lower() == existing_project.lower() and
                            gewerk_part.lower() == existing_gewerk.lower() and
                            lieferant_part.lower() == existing_lieferant.lower()):
                            similar_files.append(file_record)
                
                if similar_files:
                    return {
                        "success": True,
                        "duplicate_found": True,
                        "similar_files": similar_files
                    }
            
            return {"success": True, "duplicate_found": False}
                
        except Exception as e:
            logger.error(f"Error checking for content similarity for '{filename}': {e}")
            return {"success": False, "error": str(e), "duplicate_found": False}

# =============================================================================
# GLOBAL INSTANCE - Single database service for entire application
# =============================================================================
db_service = DatabaseService()

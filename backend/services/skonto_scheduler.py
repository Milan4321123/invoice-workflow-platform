"""
Automated Skonto Reminder Scheduler Service
Handles automatic sending of Skonto reminder emails based on expiry dates.
"""
import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import os
from dataclasses import dataclass

from services.database import db_service
from services.email_service import email_service

logger = logging.getLogger(__name__)

@dataclass
class SkontoReminderConfig:
    """Configuration for Skonto reminder scheduling"""
    enabled: bool = True
    check_interval_hours: int = 6  # Check every 6 hours
    days_ahead_urgent: int = 1     # Send urgent reminders 1 day before
    days_ahead_normal: int = 3     # Send normal reminders 3 days before
    days_ahead_early: int = 7      # Send early reminders 7 days before
    max_reminders_per_run: int = 50  # Limit batch size
    default_recipient_email: str = None
    dry_run: bool = False  # For testing without actually sending emails

class SkontoSchedulerService:
    """
    Automated service for sending Skonto reminder emails.
    Runs as a background service to monitor and send reminders.
    """
    
    def __init__(self, config: SkontoReminderConfig = None):
        self.config = config or SkontoReminderConfig()
        self.is_running = False
        self.last_run = None
        self.next_run_at: Optional[datetime] = None
        self.stats = {
            "total_runs": 0,
            "total_reminders_sent": 0,
            "total_errors": 0,
            "last_error": None
        }
        
        # Load configuration from environment
        self._load_env_config()
        
    def _load_env_config(self):
        """Load configuration from environment variables"""
        self.config.enabled = os.getenv("SKONTO_SCHEDULER_ENABLED", "true").lower() == "true"
        self.config.check_interval_hours = int(os.getenv("SKONTO_CHECK_INTERVAL_HOURS", "6"))
        self.config.days_ahead_urgent = int(os.getenv("SKONTO_DAYS_AHEAD_URGENT", "1"))
        self.config.days_ahead_normal = int(os.getenv("SKONTO_DAYS_AHEAD_NORMAL", "3"))
        self.config.days_ahead_early = int(os.getenv("SKONTO_DAYS_AHEAD_EARLY", "7"))
        self.config.max_reminders_per_run = int(os.getenv("SKONTO_MAX_REMINDERS_PER_RUN", "50"))
        # Skonto is a payment decision, so reminders go to accounting
        self.config.default_recipient_email = os.getenv("ACCOUNTING_EMAIL") or os.getenv("SKONTO_DEFAULT_RECIPIENT")
        self.config.dry_run = os.getenv("SKONTO_DRY_RUN", "false").lower() == "true"
        
        logger.info(f"📋 Skonto Scheduler Config: {self.config}")
    
    async def check_and_send_reminders(self, trigger: str = "manual") -> Dict[str, Any]:
        """
        Main method to check for invoices needing Skonto reminders and send them.
        Returns summary of actions taken.
        """
        if not self.config.enabled:
            logger.info("⏸️ Skonto scheduler is disabled")
            return {"enabled": False, "reminders_sent": 0}
        
        start_time = datetime.now()
        self.stats["total_runs"] += 1
        reminders_sent = 0
        errors = []
        
        try:
            logger.info(f"🔍 Starting Skonto reminder check at {start_time}")
            
            # Get invoices needing reminders for different urgency levels
            urgent_invoices = await self._get_invoices_needing_reminders(self.config.days_ahead_urgent)
            normal_invoices = await self._get_invoices_needing_reminders(self.config.days_ahead_normal)
            early_invoices = await self._get_invoices_needing_reminders(self.config.days_ahead_early)
            
            # Combine and deduplicate
            all_invoices = self._deduplicate_invoices([
                urgent_invoices,
                normal_invoices, 
                early_invoices
            ])

            invoices_in_window = len(all_invoices)

            # One reminder per urgency level, not one per run
            all_invoices = [inv for inv in all_invoices if self._reminder_due(inv)]
            reminders_due = len(all_invoices)

            logger.info(f"📊 Found {len(all_invoices)} invoices needing Skonto reminders")
            
            # Limit batch size
            if len(all_invoices) > self.config.max_reminders_per_run:
                logger.warning(f"⚠️ Limiting batch to {self.config.max_reminders_per_run} invoices")
                all_invoices = all_invoices[:self.config.max_reminders_per_run]
            
            # Send reminders
            for invoice in all_invoices:
                try:
                    # Validate invoice data before processing
                    if not isinstance(invoice, dict):
                        logger.error(f"❌ Invalid invoice data type: {type(invoice)}, value: {invoice}")
                        continue
                    
                    invoice_id = invoice.get("id", "Unknown")
                    logger.info(f"📧 Processing Skonto reminder for invoice {invoice_id}")
                    
                    success = await self._send_single_reminder(invoice)
                    if success:
                        reminders_sent += 1
                    
                    # Small delay between emails to avoid overwhelming the email service
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    invoice_id = invoice.get("id", "Unknown") if isinstance(invoice, dict) else "Unknown"
                    error_msg = f"Failed to send reminder for invoice {invoice_id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    self.stats["total_errors"] += 1
            
            # Update statistics
            self.stats["total_reminders_sent"] += reminders_sent
            self.last_run = start_time
            
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"✅ Skonto reminder check completed in {duration:.2f}s")
            logger.info(f"📧 Sent {reminders_sent} reminders, {len(errors)} errors")

            self._record_run(trigger, start_time, invoices_in_window, reminders_due, reminders_sent, errors)
            
            return {
                "enabled": True,
                "start_time": start_time.isoformat(),
                "duration_seconds": duration,
                "invoices_found": len(all_invoices),
                "reminders_sent": reminders_sent,
                "errors": errors,
                "dry_run": self.config.dry_run
            }
            
        except Exception as e:
            error_msg = f"Critical error in Skonto scheduler: {str(e)}"
            logger.error(error_msg)
            self.stats["last_error"] = error_msg
            self.stats["total_errors"] += 1
            self._record_run(trigger, start_time, 0, 0, reminders_sent, errors + [error_msg])
            
            return {
                "enabled": True,
                "error": error_msg,
                "start_time": start_time.isoformat(),
                "reminders_sent": reminders_sent
            }
    
    async def _get_invoices_needing_reminders(self, days_ahead: int) -> List[Dict[str, Any]]:
        """Get invoices that need Skonto reminders within specified days"""
        try:
            result = db_service.get_invoices_with_skonto_due(days_ahead=days_ahead)
            
            if result["success"]:
                invoices = result["data"]
                logger.info(f"📋 Found {len(invoices)} invoices with Skonto due within {days_ahead} days")
                return invoices
            else:
                logger.error(f"❌ Failed to get invoices with Skonto due: {result.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Exception getting invoices with Skonto due: {str(e)}")
            return []
    
    def skonto_recipient(self, invoice: Dict[str, Any]) -> Optional[str]:
        """
        Accounting decides whether to pay early, so Skonto reminders go there.
        Falls back to the invoice's Bauleiter only when no accounting address is set.
        """
        if self.config.default_recipient_email:
            return self.config.default_recipient_email
        fallback = invoice.get("bauleiter_email")
        if fallback:
            logger.warning("⚠️ ACCOUNTING_EMAIL not set, sending Skonto reminder to the Bauleiter instead")
        return fallback

    def _urgency_level(self, days_left: int) -> Optional[int]:
        """Map days until the Skonto deadline to the reminder level (1, 3 or 7 days)"""
        for level in sorted([self.config.days_ahead_urgent,
                             self.config.days_ahead_normal,
                             self.config.days_ahead_early]):
            if days_left <= level:
                return level
        return None

    def _reminder_due(self, invoice: Dict[str, Any]) -> bool:
        """
        True if the invoice reached a more urgent level than at its last reminder.
        Gives at most one mail per level (7, 3, 1 days before), however often the check runs.
        """
        try:
            skonto_date = datetime.fromisoformat(str(invoice["skonto_datum"])[:10]).date()
        except (KeyError, ValueError):
            return True  # can't tell, let the normal flow decide

        level_now = self._urgency_level((skonto_date - datetime.now().date()).days)
        if level_now is None:
            return False

        sent_at = invoice.get("skonto_reminder_sent_at")
        if not invoice.get("skonto_reminder_sent") or not sent_at:
            return True

        sent_date = datetime.fromisoformat(str(sent_at).replace("Z", "+00:00")).date()
        level_then = self._urgency_level((skonto_date - sent_date).days)
        return level_then is None or level_now < level_then

    def _deduplicate_invoices(self, invoice_lists: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Remove duplicate invoices from combined lists"""
        seen_ids = set()
        unique_invoices = []
        
        for invoice_list in invoice_lists:
            for invoice in invoice_list:
                invoice_id = invoice.get("id")
                if invoice_id and invoice_id not in seen_ids:
                    seen_ids.add(invoice_id)
                    unique_invoices.append(invoice)
        
        return unique_invoices
    
    async def _send_single_reminder(self, invoice_data: Dict[str, Any]) -> bool:
        """Send a single Skonto reminder email"""
        try:
            # Validate input
            if not isinstance(invoice_data, dict):
                logger.error(f"❌ Invalid invoice data type: {type(invoice_data)}")
                return False
            
            invoice_id = invoice_data.get("id", "Unknown")
            logger.info(f"📧 Preparing Skonto reminder for invoice {invoice_id}")
            
            recipient_email = self.skonto_recipient(invoice_data)
            
            if not recipient_email:
                logger.error(f"❌ No recipient email found for invoice {invoice_id}")
                return False
            
            if self.config.dry_run:
                logger.info(f"🧪 DRY RUN: Would send Skonto reminder for invoice {invoice_id} to {recipient_email}")
                return True
            
            # Send the reminder
            logger.info(f"📧 Sending Skonto reminder for invoice {invoice_id} to {recipient_email}")
            result = await email_service.send_skonto_reminder(
                invoice_data=invoice_data,
                recipient_email=recipient_email,
                recipient_name=None
            )
            
            if result and result.get("success"):
                logger.info(f"✅ Sent Skonto reminder for invoice {invoice_id} to {recipient_email}")
                return True
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'No result returned'
                logger.error(f"❌ Failed to send Skonto reminder for invoice {invoice_id}: {error_msg}")
                return False
                
        except Exception as e:
            invoice_id = invoice_data.get("id", "Unknown") if isinstance(invoice_data, dict) else "Unknown"
            logger.error(f"❌ Exception sending Skonto reminder for invoice {invoice_id}: {str(e)}")
            return False
    
    async def start_scheduler(self):
        """Start the automated scheduler using asyncio"""
        if not self.config.enabled:
            logger.info("⏸️ Skonto scheduler is disabled")
            return
        
        logger.info(f"🚀 Starting Skonto reminder scheduler (check every {self.config.check_interval_hours} hours)")
        
        self.is_running = True
        
        # Run immediately on startup
        logger.info("🔄 Running initial Skonto reminder check...")
        await self.check_and_send_reminders(trigger="startup")
        
        # Keep the scheduler running
        while self.is_running:
            try:
                # Wait for the specified interval
                self.next_run_at = datetime.now() + timedelta(hours=self.config.check_interval_hours)
                await asyncio.sleep(self.config.check_interval_hours * 3600)  # Convert hours to seconds
                
                if self.is_running:  # Check if still running after sleep
                    await self.check_and_send_reminders(trigger="interval")
                    
            except asyncio.CancelledError:
                logger.info("🛑 Scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Scheduler error: {str(e)}")
                # Continue running even if there's an error
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
    
    def stop_scheduler(self):
        """Stop the automated scheduler"""
        logger.info("⏹️ Stopping Skonto reminder scheduler")
        self.is_running = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current scheduler status and statistics"""
        next_run = self.next_run_at.isoformat() if self.is_running and self.next_run_at else None
        
        return {
            "enabled": self.config.enabled,
            "is_running": self.is_running,
            "config": {
                "check_interval_hours": self.config.check_interval_hours,
                "days_ahead_urgent": self.config.days_ahead_urgent,
                "days_ahead_normal": self.config.days_ahead_normal,
                "days_ahead_early": self.config.days_ahead_early,
                "max_reminders_per_run": self.config.max_reminders_per_run,
                "dry_run": self.config.dry_run
            },
            "stats": self.stats,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": next_run,
            "history": self.get_run_history()
        }

    def _record_run(self, trigger: str, start_time: datetime, invoices_in_window: int,
                    reminders_due: int, reminders_sent: int, errors: List[str]) -> None:
        """Store the run so the scheduler's work survives restarts and can be shown"""
        try:
            db_service.client.table("skonto_scheduler_runs").insert({
                "started_at": start_time.astimezone().isoformat(),
                "finished_at": datetime.now().astimezone().isoformat(),
                "trigger": trigger,
                "invoices_in_window": invoices_in_window,
                "reminders_due": reminders_due,
                "reminders_sent": reminders_sent,
                "errors": errors,
                "dry_run": self.config.dry_run,
            }).execute()
        except Exception as e:
            logger.warning(f"⚠️ Could not record scheduler run: {e}")

    def get_run_history(self, limit: int = 10) -> Dict[str, Any]:
        """Totals and most recent runs from the database"""
        try:
            response = (db_service.client.table("skonto_scheduler_runs")
                        .select("started_at,trigger,invoices_in_window,reminders_due,reminders_sent,errors", count="exact")
                        .order("started_at", desc=True)
                        .execute())
            runs = response.data or []
            return {
                "available": True,
                "total_runs": response.count if response.count is not None else len(runs),
                "total_reminders_sent": sum(r.get("reminders_sent") or 0 for r in runs),
                "last_run": runs[0]["started_at"] if runs else None,
                "recent_runs": runs[:limit],
            }
        except Exception as e:
            logger.warning(f"⚠️ Could not load scheduler history: {e}")
            return {"available": False, "total_runs": 0, "total_reminders_sent": 0,
                    "last_run": None, "recent_runs": []}

# Global scheduler instance
skonto_scheduler = SkontoSchedulerService()

async def run_manual_skonto_check() -> Dict[str, Any]:
    """Run a manual Skonto reminder check"""
    logger.info("🔧 Running manual Skonto reminder check")
    return await skonto_scheduler.check_and_send_reminders()

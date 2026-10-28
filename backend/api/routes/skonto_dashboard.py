"""
Skonto Dashboard API Routes
Enhanced reporting and analytics for Skonto performance tracking.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, EmailStr, EmailStr

from services.database import db_service
from services.skonto_scheduler import skonto_scheduler, run_manual_skonto_check

logger = logging.getLogger(__name__)
router = APIRouter()

# Response Models
class SkontoSummaryResponse(BaseModel):
    total_opportunities: int
    total_potential_savings: float
    urgent_count: int
    urgent_potential: float
    monthly_average_savings: float
    success_rate: float
    reminders_sent_count: int
    open_count: int = 0

class SkontoPerformanceResponse(BaseModel):
    month: str
    total_invoices: int
    skonto_taken: int
    skonto_missed: int
    reminders_sent: int
    savings_achieved: float
    savings_missed: float
    success_rate: float

class SkontoOpportunityResponse(BaseModel):
    id: str
    invoice_number: str
    supplier: str
    amount: float
    skonto_percentage: float
    skonto_date: str
    potential_savings: float
    days_until_expiry: int
    urgency_level: str
    reminder_sent: bool
    skonto_decision: str
    reminder_count: int = 0
    last_reminder_at: Optional[str] = None

# Request Models
class SkontoConfigUpdateRequest(BaseModel):
    default_recipient_email: EmailStr
    check_interval_hours: Optional[int] = None
    days_ahead_urgent: Optional[int] = None
    days_ahead_normal: Optional[int] = None
    days_ahead_early: Optional[int] = None
    dry_run: Optional[bool] = None

class SkontoReminderRequest(BaseModel):
    invoice_ids: List[str]
    recipient_email: EmailStr
    recipient_name: Optional[str] = None

def _skonto_reminder_log(invoice_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Count sent Skonto reminders per invoice from the email audit log"""
    if not invoice_ids:
        return {}
    try:
        rows = (db_service.client.table("email_audit_log")
                .select("invoice_id,sent_at")
                .eq("email_type", "skonto_reminder")
                .eq("send_success", True)
                .in_("invoice_id", invoice_ids)
                .execute()).data or []
    except Exception as e:
        logger.warning(f"Could not read reminder log: {e}")
        return {}
    log: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        entry = log.setdefault(row["invoice_id"], {"count": 0, "last": None})
        entry["count"] += 1
        if not entry["last"] or row["sent_at"] > entry["last"]:
            entry["last"] = row["sent_at"]
    return log


@router.get("/skonto/dashboard/summary", response_model=SkontoSummaryResponse)
async def get_skonto_summary():
    """
    Get comprehensive Skonto performance summary.
    Returns current opportunities, savings potential, and performance metrics.
    """
    try:
        logger.info("📊 Fetching Skonto dashboard summary")
        
        # First, update any expired Skonto statuses automatically
        db_service.update_expired_skonto_statuses()
        
        # Get ALL invoices with Skonto data for comprehensive reporting
        skonto_opportunities = db_service.get_all_invoices_with_skonto_data()
        
        if not skonto_opportunities["success"]:
            logger.error(f"Failed to get Skonto opportunities: {skonto_opportunities.get('error')}")
            raise HTTPException(status_code=500, detail="Failed to fetch Skonto opportunities")
        
        invoices = skonto_opportunities["data"]
        
        # Calculate summary metrics
        from collections import defaultdict
        from datetime import datetime, timedelta
        today = datetime.now().date()
        urgent_cutoff = today + timedelta(days=3)

        def parse_date(value):
            if not value:
                return None
            if not isinstance(value, str):
                return value
            try:
                if "." in value:
                    return datetime.strptime(value, "%d.%m.%Y").date()
                return datetime.strptime(value[:10], "%Y-%m-%d").date()
            except ValueError:
                return None

        total_opportunities = len(invoices)
        total_potential_savings = 0.0
        open_count = 0
        urgent_count = 0
        urgent_potential = 0.0
        taken_count = 0
        missed_count = 0
        reminders_sent_count = 0
        savings_by_month = defaultdict(float)

        for invoice in invoices:
            amount = invoice.get("rechnungsbetrag", 0) or 0
            percentage = invoice.get("skonto_prozent", 0) or 0
            potential = float(amount) * float(percentage) / 100 if amount and percentage else 0
            total_potential_savings += potential

            decision = invoice.get("skonto_decision") or "pending"
            skonto_date = parse_date(invoice.get("skonto_datum"))

            if decision == "taken":
                taken_count += 1
                saved = invoice.get("actual_skonto_savings")
                month = skonto_date.strftime("%Y-%m") if skonto_date else "unknown"
                savings_by_month[month] += float(saved) if saved is not None else potential
            elif decision == "missed":
                missed_count += 1
            elif decision == "pending" and skonto_date and skonto_date >= today:
                # Only undecided, still reachable discounts are open or urgent
                open_count += 1
                if skonto_date <= urgent_cutoff:
                    urgent_count += 1
                    urgent_potential += potential

            if invoice.get("skonto_reminder_sent"):
                reminders_sent_count += 1

        decided = taken_count + missed_count
        success_rate = round(100.0 * taken_count / decided, 1) if decided else 0.0
        monthly_average_savings = (
            round(sum(savings_by_month.values()) / len(savings_by_month), 2) if savings_by_month else 0.0
        )

        response = SkontoSummaryResponse(
            total_opportunities=total_opportunities,
            total_potential_savings=total_potential_savings,
            urgent_count=urgent_count,
            urgent_potential=urgent_potential,
            monthly_average_savings=monthly_average_savings,
            success_rate=success_rate,
            reminders_sent_count=reminders_sent_count,
            open_count=open_count
        )
        
        logger.info(f"✅ Skonto summary: {response.total_opportunities} opportunities, €{response.total_potential_savings:.2f} potential")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get Skonto summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get Skonto summary: {str(e)}")

@router.get("/skonto/dashboard/performance", response_model=List[SkontoPerformanceResponse])
async def get_skonto_performance(months: int = Query(default=12, ge=1, le=24)):
    """
    Get monthly Skonto performance metrics.
    
    Args:
        months: Number of months to retrieve (1-24)
    """
    try:
        logger.info(f"📈 Fetching Skonto performance for last {months} months")
        
        # Get all invoices from database and perform calculations in Python
        invoices_result = db_service.get_all_invoices(limit=10000)  # Get enough history
        
        if not invoices_result["success"]:
            raise HTTPException(status_code=500, detail="Failed to fetch invoices")
        
        invoices = invoices_result.get("data", [])
        
        # Group invoices by month and calculate metrics
        from datetime import datetime, timedelta
        from collections import defaultdict
        
        cutoff_date = datetime.now() - timedelta(days=months * 30)
        monthly_data = defaultdict(lambda: {
            "total_invoices": 0,
            "skonto_taken": 0,
            "skonto_missed": 0,
            "reminders_sent": 0,
            "savings_achieved": 0.0,
            "savings_missed": 0.0
        })
        
        for invoice in invoices:
            # Parse created_at date
            created_at = invoice.get("created_at")
            if not created_at:
                continue
                
            try:
                if isinstance(created_at, str):
                    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).replace(tzinfo=None)
                else:
                    created_date = created_at
                    
                # Skip if too old
                if created_date < cutoff_date:
                    continue
                    
                month_key = created_date.strftime('%Y-%m')
                
                # Check if invoice has Skonto data
                skonto_prozent = invoice.get("skonto_prozent")
                skonto_datum = invoice.get("skonto_datum")
                
                if skonto_prozent and skonto_datum:
                    monthly_data[month_key]["total_invoices"] += 1
                    
                    # Check Skonto decision
                    skonto_decision = invoice.get("skonto_decision")
                    if skonto_decision == "taken":
                        monthly_data[month_key]["skonto_taken"] += 1
                        # Use actual savings if available, otherwise calculate
                        actual_savings = invoice.get("actual_skonto_savings")
                        if actual_savings:
                            monthly_data[month_key]["savings_achieved"] += float(actual_savings)
                        else:
                            rechnungsbetrag = invoice.get("rechnungsbetrag") or invoice.get("gesamt_brutto", 0)
                            if rechnungsbetrag:
                                calculated_savings = float(rechnungsbetrag) * float(skonto_prozent) / 100
                                monthly_data[month_key]["savings_achieved"] += calculated_savings
                    elif skonto_decision == "missed":
                        monthly_data[month_key]["skonto_missed"] += 1
                        # Calculate missed savings
                        rechnungsbetrag = invoice.get("rechnungsbetrag") or invoice.get("gesamt_brutto", 0)
                        if rechnungsbetrag:
                            missed_savings = float(rechnungsbetrag) * float(skonto_prozent) / 100
                            monthly_data[month_key]["savings_missed"] += missed_savings
                    
                    # Check if reminder was sent
                    if invoice.get("skonto_reminder_sent"):
                        monthly_data[month_key]["reminders_sent"] += 1
                        
            except Exception as e:
                logger.warning(f"Failed to process invoice {invoice.get('id')} for performance: {e}")
                continue
        
        # Convert to response format
        performance_data = []
        for month_key in sorted(monthly_data.keys(), reverse=True):
            data = monthly_data[month_key]
            
            # Calculate success rate
            total_decisions = data["skonto_taken"] + data["skonto_missed"]
            success_rate = (data["skonto_taken"] / total_decisions * 100) if total_decisions > 0 else 0.0
            
            performance_data.append(SkontoPerformanceResponse(
                month=month_key,
                total_invoices=data["total_invoices"],
                skonto_taken=data["skonto_taken"],
                skonto_missed=data["skonto_missed"],
                reminders_sent=data["reminders_sent"],
                savings_achieved=round(data["savings_achieved"], 2),
                savings_missed=round(data["savings_missed"], 2),
                success_rate=round(success_rate, 2)
            ))
        
        # Limit to requested months
        performance_data = performance_data[:months]
        
        logger.info(f"✅ Retrieved {len(performance_data)} months of performance data")
        return performance_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get Skonto performance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get Skonto performance: {str(e)}")

@router.get("/skonto/dashboard/opportunities", response_model=List[SkontoOpportunityResponse])
async def get_skonto_opportunities(
    urgency: Optional[str] = Query(default=None, regex="^(urgent|important|upcoming|all)$"),
    limit: int = Query(default=50, ge=1, le=200)
):
    """
    Get current Skonto opportunities.
    
    Args:
        urgency: Filter by urgency level (urgent, important, upcoming, all)
        limit: Maximum number of opportunities to return
    """
    try:
        logger.info(f"🎯 Fetching Skonto opportunities (urgency: {urgency}, limit: {limit})")
        
        # First, update any expired Skonto statuses automatically
        db_service.update_expired_skonto_statuses()
        
        # Get ALL invoices with Skonto data for opportunities
        invoices_result = db_service.get_all_invoices_with_skonto_data()
        
        if not invoices_result["success"]:
            raise HTTPException(status_code=500, detail="Failed to fetch invoices")
        
        invoices = invoices_result.get("data", [])
        opportunities = []
        reminder_log = _skonto_reminder_log([str(inv["id"]) for inv in invoices if inv.get("id")])
        
        from datetime import datetime
        today = datetime.now().date()
        
        for invoice in invoices:
            # Check if invoice has Skonto available
            skonto_prozent = invoice.get("skonto_prozent")
            skonto_datum = invoice.get("skonto_datum")
            skonto_decision = invoice.get("skonto_decision")
            
            # Skip if no Skonto data
            if not skonto_prozent or not skonto_datum:
                continue
                
            # Skip if Skonto percentage is 0 or less
            try:
                if float(skonto_prozent) <= 0:
                    continue
            except (ValueError, TypeError):
                continue
                
            # Include ALL invoices with Skonto data regardless of decision status
            # This allows the frontend to filter and categorize properly
            
            try:
                # Parse Skonto date
                if isinstance(skonto_datum, str):
                    if "." in skonto_datum:
                        skonto_date = datetime.strptime(skonto_datum, "%d.%m.%Y").date()
                    elif "-" in skonto_datum:
                        skonto_date = datetime.strptime(skonto_datum, "%Y-%m-%d").date()
                    else:
                        skonto_date = datetime.strptime(skonto_datum, "%Y%m%d").date()
                else:
                    skonto_date = skonto_datum
                
                # Calculate days until expiry (can be negative for expired)
                days_until_expiry = (skonto_date - today).days
                
                # Calculate days until expiry
                days_until_expiry = (skonto_date - today).days
                
                # Determine urgency level
                if days_until_expiry <= 1:
                    urgency_level = "urgent"
                elif days_until_expiry <= 3:
                    urgency_level = "important"
                elif days_until_expiry <= 7:
                    urgency_level = "upcoming"
                else:
                    urgency_level = "normal"
                
                # Filter by urgency if specified
                if urgency and urgency != "all":
                    urgency_days = {
                        "urgent": 1,
                        "important": 3,
                        "upcoming": 7
                    }
                    max_days = urgency_days.get(urgency, 7)
                    if days_until_expiry > max_days:
                        continue
                
                # Get amount (try different field names)
                amount = invoice.get("rechnungsbetrag") or invoice.get("gesamt_brutto", 0)
                if not amount:
                    continue
                
                # Calculate potential savings
                potential_savings = float(amount) * float(skonto_prozent) / 100
                
                opportunities.append(SkontoOpportunityResponse(
                    id=str(invoice["id"]),
                    invoice_number=invoice.get("file_name") or "N/A",  # Use file_name from your schema
                    supplier=invoice.get("rechnungssteller") or "N/A",  # Use rechnungssteller from your schema
                    amount=float(amount),
                    skonto_percentage=float(skonto_prozent),
                    skonto_date=skonto_datum,
                    potential_savings=round(potential_savings, 2),
                    days_until_expiry=days_until_expiry,
                    urgency_level=urgency_level,
                    reminder_sent=bool(invoice.get("skonto_reminder_sent", False)),
                    skonto_decision=skonto_decision or "pending",
                    reminder_count=reminder_log.get(str(invoice["id"]), {}).get("count", 0),
                    last_reminder_at=reminder_log.get(str(invoice["id"]), {}).get("last")
                ))
                
            except Exception as e:
                logger.warning(f"Failed to process Skonto opportunity for invoice {invoice.get('id')}: {e}")
                continue
        
        # Sort by urgency (least days first) and then by potential savings (highest first)
        opportunities.sort(key=lambda x: (x.days_until_expiry, -x.potential_savings))
        
        # Limit results
        opportunities = opportunities[:limit]
        
        logger.info(f"✅ Retrieved {len(opportunities)} Skonto opportunities")
        return opportunities
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get Skonto opportunities: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get Skonto opportunities: {str(e)}")

@router.post("/skonto/scheduler/run-check")
async def run_skonto_reminder_check():
    """
    Manually trigger a Skonto reminder check.
    Useful for testing or immediate processing.
    """
    try:
        logger.info("🔧 Manual Skonto reminder check triggered")
        
        result = await run_manual_skonto_check()
        
        logger.info("✅ Manual Skonto reminder check completed")
        return {
            "success": True,
            "message": "Skonto reminder check completed",
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to run manual Skonto check: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to run Skonto check: {str(e)}")

@router.get("/skonto/scheduler/status")
async def get_scheduler_status():
    """
    Get current status of the Skonto reminder scheduler.
    """
    try:
        status = skonto_scheduler.get_status()
        
        return {
            "success": True,
            "scheduler_status": status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get scheduler status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get scheduler status: {str(e)}")

@router.get("/skonto/reports/savings-potential")
async def get_savings_potential_report():
    """
    Get detailed report on Skonto savings potential and missed opportunities.
    """
    try:
        logger.info("📊 Generating Skonto savings potential report")
        
        # Get all invoices and calculate metrics in Python
        invoices_result = db_service.get_all_invoices(limit=10000)
        
        if not invoices_result["success"]:
            raise HTTPException(status_code=500, detail="Failed to fetch invoices")
        
        invoices = invoices_result.get("data", [])
        
        from datetime import datetime, timedelta
        today = datetime.now().date()
        cutoff_date = datetime.now() - timedelta(days=365)  # Last 12 months
        
        # Initialize counters
        current_opportunities = {
            "count": 0,
            "total_potential": 0.0,
            "potential_values": [],
            "expiry_days": []
        }
        
        historical_performance = {
            "taken_count": 0,
            "missed_count": 0,
            "total_saved": 0.0,
            "total_missed": 0.0
        }
        
        for invoice in invoices:
            # Check for current opportunities
            skonto_prozent = invoice.get("skonto_prozent")
            skonto_datum = invoice.get("skonto_datum")
            skonto_decision = invoice.get("skonto_decision")
            
            if skonto_prozent and skonto_datum:
                try:
                    # Parse Skonto date
                    if isinstance(skonto_datum, str):
                        if "." in skonto_datum:
                            skonto_date = datetime.strptime(skonto_datum, "%d.%m.%Y").date()
                        elif "-" in skonto_datum:
                            skonto_date = datetime.strptime(skonto_datum, "%Y-%m-%d").date()
                        else:
                            skonto_date = datetime.strptime(skonto_datum, "%Y%m%d").date()
                    else:
                        skonto_date = skonto_datum
                    
                    # Current opportunities (still valid, decision pending)
                    if (skonto_decision == "pending" or not skonto_decision) and skonto_date >= today:
                        rechnungsbetrag = invoice.get("rechnungsbetrag") or invoice.get("gesamt_brutto", 0)
                        if rechnungsbetrag and float(skonto_prozent) > 0:
                            potential_savings = float(rechnungsbetrag) * float(skonto_prozent) / 100
                            current_opportunities["count"] += 1
                            current_opportunities["total_potential"] += potential_savings
                            current_opportunities["potential_values"].append(potential_savings)
                            
                            days_until_expiry = (skonto_date - today).days
                            current_opportunities["expiry_days"].append(days_until_expiry)
                    
                    # Historical performance (check if invoice is from last 12 months)
                    created_at = invoice.get("created_at")
                    if created_at:
                        try:
                            if isinstance(created_at, str):
                                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).replace(tzinfo=None)
                            else:
                                created_date = created_at
                                
                            if created_date >= cutoff_date:
                                if skonto_decision == "taken":
                                    historical_performance["taken_count"] += 1
                                    # Use actual savings if available, otherwise calculate
                                    actual_savings = invoice.get("actual_skonto_savings")
                                    if actual_savings:
                                        historical_performance["total_saved"] += float(actual_savings)
                                    else:
                                        rechnungsbetrag = invoice.get("rechnungsbetrag") or invoice.get("gesamt_brutto", 0)
                                        if rechnungsbetrag:
                                            calculated_savings = float(rechnungsbetrag) * float(skonto_prozent) / 100
                                            historical_performance["total_saved"] += calculated_savings
                                elif skonto_decision == "missed":
                                    historical_performance["missed_count"] += 1
                                    # Calculate missed savings
                                    rechnungsbetrag = invoice.get("rechnungsbetrag") or invoice.get("gesamt_brutto", 0)
                                    if rechnungsbetrag:
                                        missed_savings = float(rechnungsbetrag) * float(skonto_prozent) / 100
                                        historical_performance["total_missed"] += missed_savings
                        except Exception as e:
                            logger.warning(f"Failed to parse created_at for invoice {invoice.get('id')}: {e}")
                            continue
                            
                except Exception as e:
                    logger.warning(f"Failed to process invoice {invoice.get('id')} for savings report: {e}")
                    continue
        
        # Calculate derived metrics
        avg_potential = (current_opportunities["total_potential"] / current_opportunities["count"]) if current_opportunities["count"] > 0 else 0.0
        earliest_expiry = min(current_opportunities["expiry_days"]) if current_opportunities["expiry_days"] else None
        latest_expiry = max(current_opportunities["expiry_days"]) if current_opportunities["expiry_days"] else None
        
        total_decisions = historical_performance["taken_count"] + historical_performance["missed_count"]
        success_rate = (historical_performance["taken_count"] / total_decisions * 100) if total_decisions > 0 else 0.0
        
        return {
            "success": True,
            "report": {
                "current_opportunities": {
                    "count": current_opportunities["count"],
                    "total_potential": round(current_opportunities["total_potential"], 2),
                    "average_potential": round(avg_potential, 2),
                    "earliest_expiry_days": earliest_expiry,
                    "latest_expiry_days": latest_expiry
                },
                "historical_performance": {
                    "taken_count": historical_performance["taken_count"],
                    "missed_count": historical_performance["missed_count"],
                    "total_saved": round(historical_performance["total_saved"], 2),
                    "total_missed": round(historical_performance["total_missed"], 2),
                    "success_rate": round(success_rate, 2)
                }
            },
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to generate savings potential report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

@router.put("/skonto/scheduler/config")
async def update_skonto_config(config_update: SkontoConfigUpdateRequest):
    """
    Update Skonto reminder scheduler configuration.
    Allows changing default recipient email and other settings.
    """
    try:
        logger.info(f"🔧 Updating Skonto scheduler configuration")
        
        # Update the scheduler configuration
        if config_update.default_recipient_email:
            skonto_scheduler.config.default_recipient_email = str(config_update.default_recipient_email)
        
        if config_update.check_interval_hours is not None:
            skonto_scheduler.config.check_interval_hours = config_update.check_interval_hours
            
        if config_update.days_ahead_urgent is not None:
            skonto_scheduler.config.days_ahead_urgent = config_update.days_ahead_urgent
            
        if config_update.days_ahead_normal is not None:
            skonto_scheduler.config.days_ahead_normal = config_update.days_ahead_normal
            
        if config_update.days_ahead_early is not None:
            skonto_scheduler.config.days_ahead_early = config_update.days_ahead_early
            
        if config_update.dry_run is not None:
            skonto_scheduler.config.dry_run = config_update.dry_run
        
        logger.info(f"✅ Skonto configuration updated")
        logger.info(f"   Default recipient: {skonto_scheduler.config.default_recipient_email}")
        logger.info(f"   Check interval: {skonto_scheduler.config.check_interval_hours} hours")
        logger.info(f"   Dry run: {skonto_scheduler.config.dry_run}")
        
        return {
            "success": True,
            "message": "Skonto scheduler configuration updated successfully",
            "config": {
                "default_recipient_email": skonto_scheduler.config.default_recipient_email,
                "check_interval_hours": skonto_scheduler.config.check_interval_hours,
                "days_ahead_urgent": skonto_scheduler.config.days_ahead_urgent,
                "days_ahead_normal": skonto_scheduler.config.days_ahead_normal,
                "days_ahead_early": skonto_scheduler.config.days_ahead_early,
                "dry_run": skonto_scheduler.config.dry_run
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to update Skonto config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update configuration: {str(e)}")

@router.post("/skonto/send-reminder")
async def send_manual_skonto_reminder(reminder_request: SkontoReminderRequest):
    """
    Manually send Skonto reminder to a specific email for selected invoices.
    Allows choosing the recipient email address.
    """
    try:
        logger.info(f"📧 Sending manual Skonto reminder to {reminder_request.recipient_email}")
        
        reminders_sent = 0
        errors = []
        
        for invoice_id in reminder_request.invoice_ids:
            try:
                # Get invoice data
                invoice_result = db_service.get_invoice_by_id(invoice_id)
                if not invoice_result["success"]:
                    errors.append(f"Invoice {invoice_id}: {invoice_result.get('error')}")
                    continue
                
                invoice_data = invoice_result["data"]
                
                # Check if invoice has Skonto data
                if not invoice_data.get("skonto_datum") or not invoice_data.get("skonto_prozent"):
                    errors.append(f"Invoice {invoice_id}: Missing Skonto data")
                    continue
                
                # Send reminder with specified email
                from services.email_service import email_service
                result = await email_service.send_skonto_reminder(
                    invoice_data=invoice_data,
                    recipient_email=str(reminder_request.recipient_email),
                    recipient_name=reminder_request.recipient_name,
                    request_id=f"manual-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                )
                
                if result and result.get("success"):
                    reminders_sent += 1
                    logger.info(f"✅ Manual Skonto reminder sent for invoice {invoice_id}")
                else:
                    error_msg = result.get('error', 'Unknown error') if result else 'No result returned'
                    errors.append(f"Invoice {invoice_id}: {error_msg}")
                    
            except Exception as e:
                errors.append(f"Invoice {invoice_id}: {str(e)}")
        
        return {
            "success": True,
            "message": f"Manual Skonto reminders completed",
            "reminders_sent": reminders_sent,
            "total_invoices": len(reminder_request.invoice_ids),
            "errors": errors,
            "recipient_email": str(reminder_request.recipient_email),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to send manual Skonto reminder: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send reminder: {str(e)}")

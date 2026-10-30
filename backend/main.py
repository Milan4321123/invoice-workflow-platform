"""
Clean Invoice Management API
Handles upload, storage, editing, and workflow without OCR dependencies.
"""
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import uuid
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Demo mode: in-memory database with fictional invoices, no Supabase or
# SendGrid account needed. Fixed demo login; e-mails go to the local outbox
# folder, never out; nothing from a local .env reaches a real service.
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"
if DEMO_MODE:
    import secrets
    from services.demo_data import DEMO_PASSWORD, DEMO_USER

    os.environ.update({
        "ADMIN_USERNAME": DEMO_USER,
        "ADMIN_PASSWORD": DEMO_PASSWORD,
        "ADMIN_EMAIL": "demo@muster-bau.example",
        "ADMIN_FULL_NAME": "Demo-Benutzer",
        "ACCOUNTING_EMAIL": "buchhaltung@muster-bau.example",
        "EMAIL_DEMO_MODE": "true",
        "SENDGRID_API_KEY": "",
        "JWT_SECRET": secrets.token_urlsafe(48),
    })
    os.environ.pop("FOLDER_WATCHER_PATH", None)

def validate_environment():
    """Validate critical environment variables on startup"""
    required_vars = {
        "JWT_SECRET": "JWT secret for authentication",
        "SUPA_URL": "Supabase database URL", 
        "SUPA_KEY": "Supabase service key",
        "ADMIN_PASSWORD": "Admin user password for initial setup"
    }
    if DEMO_MODE:
        logger.warning("🧪 DEMO_MODE: skipping Supabase configuration checks")
        return True
    
    missing_vars = []
    insecure_vars = []
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            missing_vars.append(f"  - {var}: {description}")
        elif value.startswith("your-") or value in ["your-jwt-secret-key-here-make-it-long-and-secure", "your-secure-jwt-secret"]:
            insecure_vars.append(f"  - {var}: Still using default/placeholder value")
    
    # Special validation for admin password
    admin_password = os.getenv("ADMIN_PASSWORD")
    if admin_password:
        weak_passwords = ["admin123", "password", "123456", "admin", "password123"]
        if admin_password.lower() in weak_passwords:
            insecure_vars.append(f"  - ADMIN_PASSWORD: Using weak/common password")
        elif len(admin_password) < 8:
            insecure_vars.append(f"  - ADMIN_PASSWORD: Password too short (minimum 8 characters)")
    
    if missing_vars:
        logger.error("❌ CRITICAL: Missing required environment variables:")
        for var in missing_vars:
            logger.error(var)
        logger.error("Please configure your .env file before deployment!")
        return False
    
    if insecure_vars:
        logger.warning("⚠️  WARNING: Insecure environment variables detected:")
        for var in insecure_vars:
            logger.warning(var)
        logger.warning("Please update these values before production deployment!")
        if os.getenv("NODE_ENV") == "production":
            logger.error("❌ Cannot start in production with insecure values!")
            return False
    
    logger.info("✅ Environment validation passed")
    return True

# Configure rate limiter
limiter = Limiter(key_func=get_remote_address)

# Configure logging with filter to reduce noise from frequent requests
class QuietPathsFilter(logging.Filter):
    """Filter to reduce logging noise from frequently called endpoints"""
    
    def __init__(self):
        super().__init__()
        # Paths that should have reduced logging (only log errors)
        self.quiet_paths = [
            "/api/folder-watcher/status",
            "/api/folder-watcher/notifications"
        ]
    
    def filter(self, record):
        # For uvicorn access logs, reduce noise from frequent endpoints
        if hasattr(record, 'getMessage'):
            message = record.getMessage()
            for quiet_path in self.quiet_paths:
                if quiet_path in message and " 200 " in message:
                    # Only log errors for these paths, skip successful 200 responses
                    return False
        return True

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mask e-mail addresses and IBANs in every log line (DSGVO data minimisation)
from services import log_redaction
log_redaction.install()

# Apply quiet filter to uvicorn access logs
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(QuietPathsFilter())

app = FastAPI(
    title="Invoice Management API",
    description="Clean invoice processing without OCR dependencies",
    version="2.0.0"
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
allowed_origins = []

# Development origins
if os.getenv("NODE_ENV") != "production":
    allowed_origins.extend([
        "http://localhost:3000", 
        "http://127.0.0.1:3000", 
        "http://localhost:3001", 
        "http://127.0.0.1:3001"
    ])

# Production origins from environment
production_frontend = os.getenv("FRONTEND_URL")
if production_frontend:
    allowed_origins.append(production_frontend)

# Add any additional origins from environment
additional_origins = os.getenv("ADDITIONAL_CORS_ORIGINS", "").split(",")
for origin in additional_origins:
    if origin.strip():
        allowed_origins.append(origin.strip())

# Fallback for development if no origins configured
if not allowed_origins:
    allowed_origins = ["http://localhost:3000"]

logger.info(f"🔐 CORS allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Only add HSTS in production with HTTPS
    if os.getenv("NODE_ENV") == "production" and request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response

# Add request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# Import routes
from api.routes import (
    health, 
    upload, 
    invoices, 
    dropdowns, 
    approval, 
    approval_workflow,
    email_workflow,
    # email_test,  # Removed - not needed for production
    reports,
    folder_watcher,
    skonto_dashboard,  # Added missing skonto dashboard import
    gobd,
    privacy,
    # multi_layer_approval,  # Removed - using simple single Bauleiter approval only
    auth
)

from api.dependencies.auth import require_auth

# Every router below holds invoice data, so it requires a logged-in user.
# The exceptions decide per route: login and health checks, and the links in
# approval/Skonto e-mails, which carry their own signed, single-use token.
logged_in = [Depends(require_auth)]

# Register routes
app.include_router(auth.router, tags=["authentication"])
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(invoices.router, prefix="/api", tags=["invoices"], dependencies=logged_in)
app.include_router(dropdowns.router, prefix="/api", tags=["dropdowns"], dependencies=logged_in)
app.include_router(approval.router, prefix="/api/approval", tags=["approval"], dependencies=logged_in)
app.include_router(approval_workflow.router, prefix="/api", tags=["workflow"])
app.include_router(email_workflow.router, prefix="/api", tags=["email"])
app.include_router(reports.router, prefix="/api", tags=["reports"], dependencies=logged_in)
app.include_router(skonto_dashboard.router, prefix="/api", tags=["skonto"], dependencies=logged_in)
app.include_router(folder_watcher.router, prefix="/api/folder-watcher", tags=["folder-watcher"], dependencies=logged_in)
app.include_router(gobd.router, prefix="/api", tags=["gobd"], dependencies=logged_in)
app.include_router(privacy.router, prefix="/api", tags=["privacy"], dependencies=logged_in)
if DEMO_MODE:
    from api.routes import demo
    app.include_router(demo.router, prefix="/api", tags=["demo"])
# Removed multi_layer_approval.router - using simple single Bauleiter approval only

@app.get("/")
async def root():
    return {
        "message": "Invoice Management API",
        "version": "2.0.0",
        "status": "running",
        "features": ["manual_entry", "searchable_dropdowns", "workflow", "email"]
    }

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("🚀 Starting Invoice Management API...")
    log_redaction.install()  # uvicorn sets up its handlers after main.py is imported
    
    # Validate environment variables
    if not validate_environment():
        logger.error("❌ Environment validation failed - stopping startup")
        import sys
        sys.exit(1)
    
    if DEMO_MODE:
        from services.database import db_service
        from services import demo_data
        demo_data.seed(db_service)
        logger.warning(f"🧪 DEMO_MODE: demo invoices loaded; log in as {demo_data.DEMO_USER} / {demo_data.DEMO_PASSWORD}")

    # Check if database schema exists, if not, try to set it up
    try:
        from services.database import db_service
        
        # Quick check if main table exists
        try:
            db_service._client.table("invoices_clean").select("*").limit(1).execute()
            logger.info("✅ Database schema exists")
        except Exception:
            logger.info("🏗️  Database schema not found, attempting automatic setup...")
            
            # Try to run automatic database setup
            try:
                import subprocess
                import sys
                from pathlib import Path
                
                setup_script = Path(__file__).parent / "setup_database.py"
                if setup_script.exists():
                    result = subprocess.run([sys.executable, str(setup_script)], 
                                          capture_output=True, text=True, timeout=60)
                    if result.returncode == 0:
                        logger.info("✅ Automatic database setup completed")
                    else:
                        logger.warning("⚠️  Automatic setup failed, manual setup may be required")
                        logger.warning(f"Setup output: {result.stdout}")
                        logger.warning(f"Setup errors: {result.stderr}")
            except Exception as setup_error:
                logger.warning(f"⚠️  Could not run automatic database setup: {setup_error}")
                logger.warning("📋 Manual database setup may be required - see COMPLETE_SUPABASE_SETUP.sql")
    
    except Exception as e:
        logger.error(f"❌ Database check error: {e}")
    
    # Initialize authentication system
    try:
        from services.auth_service import auth_service
        result = await auth_service.initialize_default_user()
        if result["success"]:
            logger.info(f"🔐 {result['message']}")
        else:
            logger.error(f"❌ Auth initialization failed: {result.get('error', 'Unknown error')}")
    except Exception as e:
        logger.error(f"❌ Auth initialization error: {e}")
    
    # Start Skonto reminder scheduler
    try:
        from services.skonto_scheduler import skonto_scheduler
        import asyncio
        
        # Start the scheduler in the background
        asyncio.create_task(skonto_scheduler.start_scheduler())
        logger.info("📅 Skonto reminder scheduler started")
        
    except Exception as e:
        logger.error(f"❌ Failed to start Skonto scheduler: {e}")

    # Remove IP addresses once they are no longer needed (DSGVO storage limitation)
    try:
        from services.privacy_service import run_ip_cleanup_daily
        from api.routes.privacy import privacy
        import asyncio

        if db_service.is_available:
            asyncio.create_task(run_ip_cleanup_daily(privacy))
    except Exception as e:
        logger.error(f"❌ Failed to start IP address cleanup: {e}")

    # Watch folders are kept in memory, so restore the configured one on every start
    watch_path = os.getenv("FOLDER_WATCHER_PATH")
    if watch_path:
        try:
            from services.folder_watcher import folder_watcher_service

            added, _, add_error = await folder_watcher_service.add_watch_folder(watch_path)
            if not added:
                logger.error(f"❌ Could not watch {watch_path}: {add_error}")
            else:
                started, start_error = await folder_watcher_service.start_watcher()
                if started:
                    logger.info(f"📁 Folder watcher running on {watch_path}")
                else:
                    logger.error(f"❌ Failed to start folder watcher: {start_error}")
        except Exception as e:
            logger.error(f"❌ Folder watcher setup error: {e}")

    logger.info("✅ Application startup complete")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
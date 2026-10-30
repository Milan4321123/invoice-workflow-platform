"""Health and debug route handlers"""
from fastapi import APIRouter, Depends
import os
import time
import tempfile
from datetime import datetime
from services.database import db_service
from api.dependencies.auth import require_auth

router = APIRouter()

@router.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Invoice Management API is running", "version": "1.0.0"}

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@router.get("/system-health", dependencies=[Depends(require_auth)])
async def system_health():
    """Comprehensive system health check endpoint"""
    start_time = time.time()
    
    # Initialize components status
    components = {}
    overall_status = "healthy"
    
    # Database component check
    try:
        db_start = time.time()
        
        if db_service.is_available:
            try:
                # Test database connection by getting invoice count
                result = db_service.get_invoices(limit=1)
                if result.get("success"):
                    invoice_count = result.get("count", 0)
                    db_status = "healthy"
                    connection_status = "Connected"
                else:
                    invoice_count = 0
                    db_status = "error"
                    connection_status = "Configuration Error"
                    
                components["database"] = {
                    "status": db_status,
                    "response_time_ms": round((time.time() - db_start) * 1000, 2),
                    "connection": connection_status,
                    "total_invoices": invoice_count
                }
            except Exception as e:
                components["database"] = {
                    "status": "error",
                    "response_time_ms": round((time.time() - db_start) * 1000, 2),
                    "connection": "Configuration Error",
                    "error": str(e),
                    "total_invoices": 0
                }
        else:
            components["database"] = {
                "status": "error",
                "response_time_ms": round((time.time() - db_start) * 1000, 2),
                "connection": "Configuration Error",
                "total_invoices": 0
            }
    except Exception as e:
        components["database"] = {
            "status": "error",
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "connection": "Configuration Error",
            "error": str(e),
            "total_invoices": 0
        }
    
    # Storage component check  
    try:
        storage_start = time.time()
        
        if db_service.is_available:
            try:
                client = db_service.client
                
                # Test storage bucket access
                try:
                    # List files in invoices bucket (no limit parameter for Supabase)
                    files_response = client.storage.from_('invoices').list()
                    bucket_accessible = True
                    files_count = len(files_response) if files_response else 0
                except Exception as bucket_error:
                    bucket_accessible = False
                    files_count = 0
                
                # Test write access with a small test file
                write_access = False
                try:
                    test_content = b"health_check_test"
                    test_filename = f"health_test_{int(time.time())}.txt"
                    
                    upload_response = client.storage.from_('invoices').upload(
                        test_filename, 
                        test_content,
                        file_options={"content-type": "text/plain"}
                    )
                    
                    # Clean up test file
                    client.storage.from_('invoices').remove([test_filename])
                    write_access = True
                    
                except Exception:
                    write_access = False
                
                if bucket_accessible and write_access:
                    components["storage"] = {
                        "status": "healthy",
                        "response_time_ms": round((time.time() - storage_start) * 1000, 2),
                        "connection": "Connected",
                        "bucket": "invoices",
                        "write_access": "Yes"
                    }
                else:
                    components["storage"] = {
                        "status": "error",
                        "response_time_ms": round((time.time() - storage_start) * 1000, 2),
                        "connection": "Configuration Error",
                        "bucket": "invoices",
                        "write_access": "No"
                    }
                    
            except Exception as e:
                components["storage"] = {
                    "status": "error",
                    "response_time_ms": round((time.time() - storage_start) * 1000, 2),
                    "connection": "Configuration Error",
                    "bucket": "invoices",
                    "error": str(e),
                    "write_access": "No"
                }
        else:
            components["storage"] = {
                "status": "error",
                "response_time_ms": round((time.time() - storage_start) * 1000, 2),
                "connection": "Configuration Error",
                "bucket": "invoices",
                "write_access": "No"
            }
    except Exception as e:
        components["storage"] = {
            "status": "error",
            "response_time_ms": round((time.time() - start_time) * 1000, 2),
            "connection": "Configuration Error",
            "bucket": "invoices",
            "error": str(e),
            "write_access": "No"
        }
    
    # Environment component check
    env_config = {}
    env_status = "healthy"
    
    # Check critical environment variables (both naming conventions)
    url_configured = os.getenv("SUPABASE_URL") or os.getenv("SUPA_URL")
    key_configured = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPA_KEY")
    
    env_config["SUPABASE_URL"] = "configured" if url_configured else "missing"
    env_config["SUPABASE_KEY"] = "configured" if key_configured else "missing"
    
    if not url_configured or not key_configured:
        env_status = "error"
        overall_status = "error"
    
    components["environment"] = {
        "status": env_status,
        "response_time_ms": round((time.time() - start_time) * 1000, 2),
        "configuration": env_config
    }
    
    # API endpoints component check
    components["api_endpoints"] = {
        "status": "healthy",
        "response_time_ms": round((time.time() - start_time) * 1000, 2),
        "available_endpoints": ["/", "/health", "/system-health", "/upload", "/invoices"]
    }
    
    # Filesystem component check
    try:
        fs_start = time.time()
        
        # Test write access to temp directory
        with tempfile.NamedTemporaryFile(mode='w', delete=True) as temp_file:
            temp_file.write("health check test")
            temp_file.flush()
            write_access = True
        
        components["filesystem"] = {
            "status": "healthy",
            "response_time_ms": round((time.time() - fs_start) * 1000, 2),
            "write_access": "Yes"
        }
    except Exception as e:
        components["filesystem"] = {
            "status": "error",
            "response_time_ms": round((time.time() - fs_start) * 1000, 2),
            "write_access": "No",
            "error": str(e)
        }
    
    # Determine overall status
    component_statuses = [comp["status"] for comp in components.values()]
    if "error" in component_statuses:
        overall_status = "error"
    elif "degraded" in component_statuses:
        overall_status = "degraded"
    elif "mock" in component_statuses:
        overall_status = "degraded"  # Consider mock as degraded
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "overall_status": overall_status,
        "components": components
    }

# Debug endpoints removed for production - use /health and /system-health instead

"""
Authentication API Routes
Handles login, token validation, and user management
"""
from fastapi import APIRouter, HTTPException, Depends, status, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from typing import Dict, Any
import logging
from pydantic import BaseModel

from services.auth_service import auth_service
from services.audit import current_actor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Security scheme for token validation
security = HTTPBearer()

# Request/Response models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    message: str

class UserResponse(BaseModel):
    username: str
    email: str = None
    full_name: str = None
    is_active: bool

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    payload = auth_service.verify_token(token)
    username = payload.get("sub")
    
    user = await auth_service.get_user_by_username(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    current_actor.set(user["username"])
    return user

@router.post("/token", response_model=LoginResponse)
async def login_for_access_token(request: LoginRequest):
    """Login endpoint - authenticate user and return access token"""
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(request.username, request.password)
        if not user:
            logger.warning(f"❌ Failed login attempt for username: {request.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token = auth_service.create_access_token(
            data={"sub": user["username"]}
        )
        
        logger.info(f"✅ Successful login for user: {request.username}")
        
        return LoginResponse(
            access_token=access_token,
            username=user["username"],
            message="Login successful"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )

@router.post("/login", response_model=LoginResponse)
async def form_login(username: str = Form(...), password: str = Form(...)):
    """Form-based login endpoint for frontend integration"""
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(username, password)
        if not user:
            logger.warning(f"❌ Failed login attempt for username: {username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token = auth_service.create_access_token(
            data={"sub": user["username"]}
        )
        
        logger.info(f"✅ Successful form login for user: {username}")
        
        return LoginResponse(
            access_token=access_token,
            username=user["username"],
            message="Login successful"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Form login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during login"
        )

@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        username=current_user["username"],
        email=current_user.get("email"),
        full_name=current_user.get("full_name"),
        is_active=current_user.get("is_active", True)
    )

@router.post("/verify")
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify if a token is valid"""
    try:
        payload = auth_service.verify_token(credentials.credentials)
        return {
            "valid": True,
            "username": payload.get("sub"),
            "expires": payload.get("exp")
        }
    except HTTPException:
        return {"valid": False}

@router.post("/initialize", dependencies=[Depends(get_current_user)])
async def initialize_auth_system():
    """Initialize authentication system with default admin user"""
    try:
        # Ensure users table exists
        from services.database import db_service
        table_result = await db_service.ensure_users_table_exists()
        
        # Initialize default user
        user_result = await auth_service.initialize_default_user()
        
        return {
            "success": True,
            "message": "Authentication system initialized",
            "table_status": table_result,
            "user_status": user_result
        }
        
    except Exception as e:
        logger.error(f"Auth initialization error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize auth system: {str(e)}"
        )







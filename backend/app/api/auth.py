from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
import time
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import structlog

from app.core.security import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.db.session import get_db_session
from app.db.models import User
from app.api.schemas import Token, UserRead

# Set up logging
logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Performance timer
@asynccontextmanager
async def performance_timer(operation: str):
    """Context manager for timing operations"""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        logger.info("operation_completed", operation=operation, duration_seconds=round(duration, 2))

# Input validation models
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=6, description="Password")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")
        return v.strip().lower()

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: str = Field(..., description="Email address")
    password: str = Field(..., min_length=6, description="Password")
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")
        return v.strip().lower()
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v

class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Refresh token")

class AuthService:
    """Service class for handling authentication operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.failed_attempts = {}  # Simple in-memory tracking (use Redis in production)
    
    async def authenticate_user_safe(self, username: str, password: str) -> Optional[User]:
        """Safely authenticate user with rate limiting"""
        try:
            # Check for too many failed attempts
            if self._is_rate_limited(username):
                logger.warning(f"Rate limited login attempt for user: {username}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many failed login attempts. Please try again later."
                )
            
            user = await authenticate_user(username, password, self.session)
            
            if user:
                # Clear failed attempts on successful login
                self._clear_failed_attempts(username)
                logger.info(f"Successful login for user: {username}")
                return user
            else:
                # Track failed attempt
                self._track_failed_attempt(username)
                logger.warning(f"Failed login attempt for user: {username}")
                return None
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error for user {username}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error"
            )
    
    def _track_failed_attempt(self, username: str):
        """Track failed login attempts"""
        if username not in self.failed_attempts:
            self.failed_attempts[username] = {"count": 0, "last_attempt": 0}
        
        current_time = time.time()
        attempts = self.failed_attempts[username]
        
        # Reset if more than 15 minutes have passed
        if current_time - attempts["last_attempt"] > 900:  # 15 minutes
            attempts["count"] = 0
        
        attempts["count"] += 1
        attempts["last_attempt"] = current_time
    
    def _clear_failed_attempts(self, username: str):
        """Clear failed attempts for successful login"""
        if username in self.failed_attempts:
            del self.failed_attempts[username]
    
    def _is_rate_limited(self, username: str) -> bool:
        """Check if user is rate limited"""
        if username not in self.failed_attempts:
            return False
        
        attempts = self.failed_attempts[username]
        current_time = time.time()
        
        # Reset if more than 15 minutes have passed
        if current_time - attempts["last_attempt"] > 900:
            attempts["count"] = 0
            return False
        
        # Rate limit after 5 failed attempts
        return attempts["count"] >= 5
    
    async def register_user(self, username: str, email: str, password: str) -> User:
        """Register a new user"""
        try:
            # Check if username already exists
            existing_user = await self.session.scalar(
                select(User).where(User.username == username)
            )
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already registered"
                )
            
            # Check if email already exists
            existing_email = await self.session.scalar(
                select(User).where(User.email == email)
            )
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Create new user
            hashed_password = get_password_hash(password)
            new_user = User(
                username=username,
                email=email,
                password_hash=hashed_password
            )
            
            self.session.add(new_user)
            await self.session.commit()
            await self.session.refresh(new_user)
            
            logger.info(
                "user_registered_in_service",
                username=username,
                user_id=str(new_user.id)
            )
            return new_user
            
        except HTTPException:
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(
                "user_registration_error",
                username=username,
                error=str(e),
                error_type=type(e).__name__
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed"
            )

# Initialize auth service (in production, this would be per-request)
auth_service = None

@router.post("/login", 
    response_model=Token,
    responses={
        200: {"description": "Successfully authenticated"},
        401: {"description": "Invalid credentials"},
        429: {"description": "Too many failed attempts"},
        500: {"description": "Authentication service error"}
    },
    summary="User login",
    description="Authenticate user and return access token"
)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db_session),
):
    """Authenticate user and return access token"""
    async with performance_timer("user_login"):
        try:
            service = AuthService(session)
            user = await service.authenticate_user_safe(form_data.username, form_data.password)
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Create access and refresh tokens
            access_token = create_access_token(
                {"sub": str(user.id), "username": user.username},
                expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            )
            refresh_token = create_refresh_token(
                {"sub": str(user.id)},
                expires_delta=timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
            )
            
            logger.info(
                "user_login_success",
                username=user.username,
                user_id=str(user.id),
                ip_address=request.client.host if request.client else None
            )
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "user_login_error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Login failed"
            )

@router.post("/register",
    response_model=UserRead,
    responses={
        201: {"description": "User registered successfully"},
        400: {"description": "Invalid input or user already exists"},
        500: {"description": "Registration failed"}
    },
    summary="User registration",
    description="Register a new user account"
)
async def register(
    request: Request,
    user_data: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Register a new user"""
    async with performance_timer("user_registration"):
        try:
            service = AuthService(session)
            new_user = await service.register_user(
                user_data.username, user_data.email, user_data.password
            )
            
            logger.info(
                "user_registration_success",
                username=new_user.username,
                user_id=str(new_user.id),
                email=new_user.email,
                ip_address=request.client.host if request.client else None
            )
            
            return UserRead(
                id=new_user.id,
                username=new_user.username,
                email=new_user.email,
                status=new_user.status,
                preferences=new_user.preferences,
                travel_history=new_user.travel_history,
                profile_data=new_user.profile_data,
                created_at=new_user.created_at,
                updated_at=new_user.updated_at,
                is_active=new_user.is_active
            )
            
        except HTTPException as he:
            logger.warning(
                "user_registration_http_error",
                status_code=he.status_code,
                detail=he.detail,
                username=user_data.username
            )
            raise
        except Exception as e:
            logger.error(
                "user_registration_unexpected_error",
                error=str(e),
                error_type=type(e).__name__,
                username=user_data.username
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed"
            )

@router.post("/refresh",
    response_model=Token,
    responses={
        200: {"description": "Token refreshed successfully"},
        401: {"description": "Invalid refresh token"},
        500: {"description": "Token refresh failed"}
    },
    summary="Refresh access token",
    description="Refresh access token using refresh token"
)
async def refresh_token(
    request: Request,
    refresh_data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Refresh access token using refresh token"""
    async with performance_timer("token_refresh"):
        try:
            # Verify refresh token and get user
            user = await get_current_user(refresh_data.refresh_token, session)
            
            # Create new access token
            access_token = create_access_token(
                {"sub": str(user.id), "username": user.username},
                expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            )
            
            logger.info(f"Token refreshed for user: {user.username}")
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

@router.post("/logout",
    responses={
        200: {"description": "Successfully logged out"},
        401: {"description": "Invalid token"}
    },
    summary="User logout",
    description="Logout user (invalidate token on client side)"
)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Logout user"""
    async with performance_timer("user_logout"):
        try:
            # In a production system, you might want to blacklist the token
            # For now, we just log the logout event
            logger.info(f"User {current_user.username} logged out", extra={
                'user_id': str(current_user.id),
                'ip_address': request.client.host if request.client else None
            })
            
            return {"message": "Successfully logged out"}
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Logout failed"
            )

@router.get("/me",
    response_model=UserRead,
    responses={
        200: {"description": "Current user information"},
        401: {"description": "Invalid token"}
    },
    summary="Get current user",
    description="Get information about the currently authenticated user"
)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current user information"""
    try:
        return UserRead(
            id=current_user.id,
            username=current_user.username,
            email=current_user.email,
            status=current_user.status,
            preferences=current_user.preferences,
            travel_history=current_user.travel_history,
            profile_data=current_user.profile_data,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
            is_active=current_user.is_active
        )
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )

@router.get("/health")
async def auth_health_check():
    """Check authentication service health"""
    try:
        return {
            "status": "healthy",
            "service": "Authentication",
            "features": ["login", "register", "refresh", "logout"],
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"Auth health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "Authentication",
            "error": str(e),
            "timestamp": "2024-01-01T00:00:00Z"
        }

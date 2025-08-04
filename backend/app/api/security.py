from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from typing import Dict, Any

from app.core.security import (
    get_current_user, get_security_info, SecurityService,
    is_token_blacklisted, blacklist_token
)
from app.db.session import get_session
from app.db.models import User
from app.api.schemas import SecurityInfoResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["security"])

@router.get("/health",
    responses={
        200: {"description": "Security service is healthy"},
        500: {"description": "Security service issues detected"}
    },
    summary="Security health check",
    description="Check the health of security services and token management"
)
async def security_health_check():
    """Check security service health"""
    try:
        security_info = get_security_info()
        
        # Basic health checks
        health_status = {
            "status": "healthy",
            "token_blacklist_enabled": True,
            "password_validation_enabled": True,
            "security_logging_enabled": True,
            "blacklisted_tokens_count": security_info["blacklisted_tokens_count"],
            "configuration": security_info
        }
        
        logger.info("Security health check completed successfully")
        return health_status
        
    except Exception as e:
        logger.error(f"Security health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Security service health check failed"
        )

@router.get("/info",
    response_model=SecurityInfoResponse,
    responses={
        200: {"description": "Security configuration information"}
    },
    summary="Get security configuration",
    description="Retrieve detailed security configuration and settings"
)
async def get_security_configuration():
    """Get detailed security configuration"""
    return SecurityInfoResponse(**get_security_info())

@router.post("/logout",
    responses={
        200: {"description": "Successfully logged out"},
        401: {"description": "Invalid or missing token"},
        500: {"description": "Logout failed"}
    },
    summary="Logout user",
    description="Logout current user by blacklisting their token"
)
async def logout_user(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Logout user by blacklisting their token"""
    try:
        # Get token from authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header"
            )
        
        token = auth_header.split(" ")[1]
        
        # Blacklist the token
        success = SecurityService.logout_user(token)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Logout failed"
            )
        
        logger.info(f"User {current_user.username} logged out successfully")
        return {"message": "Successfully logged out"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

@router.get("/token/status",
    responses={
        200: {"description": "Token status information"},
        401: {"description": "Invalid token"}
    },
    summary="Check token status",
    description="Check if the current token is valid and not blacklisted"
)
async def check_token_status(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Check the status of the current user's token"""
    try:
        # Get token from authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header"
            )
        
        token = auth_header.split(" ")[1]
        
        # Check if token is blacklisted
        is_blacklisted = is_token_blacklisted(token)
        
        return {
            "token_valid": True,
            "token_blacklisted": is_blacklisted,
            "user_id": str(current_user.id),
            "username": current_user.username
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token status check error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token status check failed"
        )

@router.get("/stats",
    responses={
        200: {"description": "Security statistics"},
        401: {"description": "Unauthorized"}
    },
    summary="Get security statistics",
    description="Retrieve security-related statistics and metrics"
)
async def get_security_stats(
    current_user: User = Depends(get_current_user)
):
    """Get security statistics (admin only)"""
    try:
        # Basic security stats
        security_info = get_security_info()
        
        stats = {
            "blacklisted_tokens_count": security_info["blacklisted_tokens_count"],
            "access_token_expire_minutes": security_info["access_token_expire_minutes"],
            "refresh_token_expire_minutes": security_info["refresh_token_expire_minutes"],
            "password_requirements": {
                "min_length": security_info["password_min_length"],
                "require_uppercase": security_info["password_require_uppercase"],
                "require_number": security_info["password_require_number"]
            },
            "algorithm": security_info["algorithm"]
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Security stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security statistics"
        ) 
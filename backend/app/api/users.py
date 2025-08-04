"""
Users API endpoints with enhanced functionality for improved models
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.crud import (
    create_user, get_user_by_id, get_user_by_username, get_user_by_email,
    get_users
)
from app.core.security import get_password_hash, validate_password_strength, get_security_info, SecurityService
from app.api.schemas import (
    UserCreate, UserRead, UserUpdate, PasswordValidationRequest, 
    PasswordValidationResponse, ChangePasswordRequest, SecurityInfoResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users")


@router.post("/", response_model=UserRead)
async def create_user_endpoint(
    payload: UserCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new user with password validation"""
    try:
        # Check if username already exists
        existing_user = await get_user_by_username(session, payload.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # Check if email already exists
        existing_email = await get_user_by_email(session, payload.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Validate password strength
        validation = validate_password_strength(payload.password)
        if not validation["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Password does not meet requirements",
                    "errors": validation["errors"],
                    "warnings": validation["warnings"]
                }
            )
        
        # Hash password
        hashed = get_password_hash(payload.password)
        
        # Create user
        user = await create_user(
            session=session,
            username=payload.username,
            email=payload.email,
            password_hash=hashed
        )
        
        logger.info(f"Created new user: {user.username}")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@router.get("/", response_model=List[UserRead])
async def list_users_endpoint(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    session: AsyncSession = Depends(get_session)
):
    """Get list of active users with pagination"""
    try:
        users = await get_users(session, skip=skip, limit=limit)
        return users
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve users"
        )


@router.get("/{user_id}", response_model=UserRead)
async def get_user_endpoint(
    user_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    """Get user by ID"""
    try:
        user = await get_user_by_id(session, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user"
        )


@router.put("/{user_id}", response_model=UserRead)
async def update_user_endpoint(
    user_id: UUID,
    payload: UserUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update user information"""
    try:
        # Check if user exists
        existing_user = await get_user_by_id(session, user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check for username conflicts if username is being updated
        if payload.username and payload.username != existing_user.username:
            username_exists = await get_user_by_username(session, payload.username)
            if username_exists:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken"
                )
        
        # Check for email conflicts if email is being updated
        if payload.email and payload.email != existing_user.email:
            email_exists = await get_user_by_email(session, payload.email)
            if email_exists:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        
        # Update user
        updated_user = await update_user(session, user_id, **payload.dict(exclude_unset=True))
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user"
            )
        
        logger.info(f"Updated user: {user_id}")
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user"
        )


@router.delete("/{user_id}")
async def delete_user_endpoint(
    user_id: UUID,
    session: AsyncSession = Depends(get_session)
):
    """Soft delete user"""
    try:
        # Check if user exists
        existing_user = await get_user_by_id(session, user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Soft delete user
        success = await soft_delete_user(session, user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user"
            )
        
        logger.info(f"Soft deleted user: {user_id}")
        return {"message": "User deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )


@router.post("/validate-password", response_model=PasswordValidationResponse)
async def validate_password_endpoint(
    payload: PasswordValidationRequest
):
    """Validate password strength"""
    try:
        validation = validate_password_strength(payload.password)
        return PasswordValidationResponse(**validation)
    except Exception as e:
        logger.error(f"Error validating password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate password"
        )


@router.post("/me/change-password")
async def change_password_endpoint(
    payload: ChangePasswordRequest,
    session: AsyncSession = Depends(get_session)
):
    """Change user password (requires authentication)"""
    try:
        # This would typically require authentication
        # For now, we'll just validate the new password
        validation = validate_password_strength(payload.new_password)
        if not validation["is_valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "New password does not meet requirements",
                    "errors": validation["errors"],
                    "warnings": validation["warnings"]
                }
            )
        
        # In a real implementation, you would:
        # 1. Get current user from authentication
        # 2. Verify current password
        # 3. Update password hash
        
        return {"message": "Password change request validated"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.get("/security/info", response_model=SecurityInfoResponse)
async def get_security_info_endpoint():
    """Get security configuration information"""
    try:
        return get_security_info()
    except Exception as e:
        logger.error(f"Error getting security info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security information"
        )
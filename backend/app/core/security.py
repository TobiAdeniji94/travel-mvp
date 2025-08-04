import os
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field, field_validator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.db.session import get_session
from app.db.models import User

# Set up logging
logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = os.getenv("JWT_SECRET", "change_me")
REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET", "refresh_change_me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

# Password configuration
PASSWORD_MIN_LENGTH = 6
PASSWORD_REQUIRE_UPPERCASE = True
PASSWORD_REQUIRE_NUMBER = True

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# In-memory token blacklist (use Redis in production)
token_blacklist = set()

# Performance timer
@asynccontextmanager
async def performance_timer(operation: str):
    """Context manager for timing operations"""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        logger.info(f"{operation} completed in {duration:.2f}s")

class PasswordValidator:
    """Password validation utility"""
    
    @staticmethod
    def validate_password(password: str) -> Dict[str, Any]:
        """Validate password strength and return detailed feedback"""
        errors = []
        warnings = []
        
        if len(password) < PASSWORD_MIN_LENGTH:
            errors.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
        
        if PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if PASSWORD_REQUIRE_NUMBER and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one number")
        
        if len(password) < 8:
            warnings.append("Consider using a longer password for better security")
        
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            warnings.append("Consider adding special characters for better security")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "strength_score": PasswordValidator._calculate_strength(password)
        }
    
    @staticmethod
    def _calculate_strength(password: str) -> int:
        """Calculate password strength score (0-100)"""
        score = 0
        
        # Length contribution
        score += min(len(password) * 4, 40)
        
        # Character variety
        if any(c.islower() for c in password):
            score += 10
        if any(c.isupper() for c in password):
            score += 10
        if any(c.isdigit() for c in password):
            score += 10
        if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            score += 10
        
        # Bonus for mixed case and numbers
        if any(c.isupper() for c in password) and any(c.islower() for c in password):
            score += 10
        if any(c.isdigit() for c in password) and any(c.isalpha() for c in password):
            score += 10
        
        return min(score, 100)

def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    try:
        return pwd_context.verify(plain, hashed)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Generate a secure password hash"""
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"Password hashing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password processing failed"
        )

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    try:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire, "type": "access"})
        
        token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        logger.info("Access token created successfully", extra={
            'user_id': data.get('sub'),
            'expires_in': ACCESS_TOKEN_EXPIRE_MINUTES
        })
        return token
    except Exception as e:
        logger.error(f"Access token creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token creation failed"
        )

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token"""
    try:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire, "type": "refresh"})
        
        token = jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)
        logger.info("Refresh token created successfully", extra={
            'user_id': data.get('sub'),
            'expires_in': REFRESH_TOKEN_EXPIRE_MINUTES
        })
        return token
    except Exception as e:
        logger.error(f"Refresh token creation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Refresh token creation failed"
        )

def blacklist_token(token: str) -> None:
    """Add token to blacklist"""
    try:
        token_blacklist.add(token)
        logger.info("Token added to blacklist")
    except Exception as e:
        logger.error(f"Token blacklisting error: {e}")

def is_token_blacklisted(token: str) -> bool:
    """Check if token is blacklisted"""
    return token in token_blacklist

async def authenticate_user(
    username_or_email: str, 
    password: str, 
    session: AsyncSession
) -> Optional[User]:
    """Authenticate user with enhanced error handling and logging"""
    async with performance_timer("user_authentication"):
        try:
            # Normalize input
            username_or_email = username_or_email.strip().lower()
            
            # Find user by username or email
            user = await session.execute(
                select(User).where(
                    (User.username == username_or_email) | (User.email == username_or_email)
                )
            )
            result = user.scalar_one_or_none()
            
            if not result:
                logger.warning(f"Authentication failed: user not found - {username_or_email}")
                return None
            
            # Verify password
            if not verify_password(password, result.password_hash):
                logger.warning(f"Authentication failed: invalid password for user - {username_or_email}")
                return None
            
            logger.info(f"User authenticated successfully: {result.username}")
            return result
            
        except Exception as e:
            logger.error(f"Authentication error for {username_or_email}: {e}")
            return None

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Get current user from JWT token with enhanced security"""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Check if token is blacklisted
        if is_token_blacklisted(token):
            logger.warning("Attempted to use blacklisted token")
            raise credentials_exc
        
        # Decode token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if not user_id or token_type != "access":
            logger.warning("Invalid token payload")
            raise credentials_exc
            
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise credentials_exc
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise credentials_exc

    # Get user from database
    try:
        user = await session.get(User, user_id)
        if not user:
            logger.warning(f"User not found for token: {user_id}")
            raise credentials_exc
        
        logger.info(f"Current user resolved: {user.username}")
        return user
        
    except Exception as e:
        logger.error(f"Database error during user lookup: {e}")
        raise credentials_exc

async def get_current_user_from_refresh_token(
    token: str,
    session: AsyncSession,
) -> User:
    """Get user from refresh token"""
    try:
        # Decode refresh token
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if not user_id or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
            
    except JWTError as e:
        logger.warning(f"Refresh token decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Get user from database
    try:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return user
        
    except Exception as e:
        logger.error(f"Database error during refresh token lookup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token validation failed"
        )

def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength and return detailed feedback"""
    return PasswordValidator.validate_password(password)

def get_security_info() -> Dict[str, Any]:
    """Get security configuration information"""
    return {
        "access_token_expire_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
        "refresh_token_expire_minutes": REFRESH_TOKEN_EXPIRE_MINUTES,
        "password_min_length": PASSWORD_MIN_LENGTH,
        "password_require_uppercase": PASSWORD_REQUIRE_UPPERCASE,
        "password_require_number": PASSWORD_REQUIRE_NUMBER,
        "algorithm": ALGORITHM,
        "blacklisted_tokens_count": len(token_blacklist)
    }

class SecurityService:
    """Service class for security operations"""
    
    @staticmethod
    async def change_password(
        user: User, 
        current_password: str, 
        new_password: str, 
        session: AsyncSession
    ) -> bool:
        """Change user password with validation"""
        try:
            # Verify current password
            if not verify_password(current_password, user.password_hash):
                logger.warning(f"Password change failed: invalid current password for user {user.username}")
                return False
            
            # Validate new password
            validation = validate_password_strength(new_password)
            if not validation["is_valid"]:
                logger.warning(f"Password change failed: weak password for user {user.username}")
                return False
            
            # Hash new password
            new_hash = get_password_hash(new_password)
            
            # Update user
            user.password_hash = new_hash
            await session.commit()
            
            logger.info(f"Password changed successfully for user: {user.username}")
            return True
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Password change error for user {user.username}: {e}")
            return False
    
    @staticmethod
    def logout_user(token: str) -> bool:
        """Logout user by blacklisting token"""
        try:
            blacklist_token(token)
            return True
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False

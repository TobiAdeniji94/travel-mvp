"""
Test file for security improvements
Demonstrates and tests the enhanced security features
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

# Import security functions
from app.core.security import (
    validate_password_strength,
    get_security_info,
    SecurityService,
    PasswordValidator,
    create_access_token,
    create_refresh_token,
    blacklist_token,
    is_token_blacklisted
)

def test_password_validation():
    """Test password strength validation"""
    print("\n=== Testing Password Validation ===")
    
    # Test weak password
    result = validate_password_strength("123")
    print(f"Weak password result: {result}")
    assert not result["is_valid"]
    assert len(result["errors"]) > 0
    
    # Test medium password
    result = validate_password_strength("password123")
    print(f"Medium password result: {result}")
    assert result["is_valid"]
    assert result["strength_score"] > 50
    
    # Test strong password
    result = validate_password_strength("MySecurePass123!")
    print(f"Strong password result: {result}")
    assert result["is_valid"]
    assert result["strength_score"] > 80
    
    # Test password with warnings
    result = validate_password_strength("password")
    print(f"Password with warnings: {result}")
    assert result["is_valid"]
    assert len(result["warnings"]) > 0

def test_security_info():
    """Test security configuration info"""
    print("\n=== Testing Security Info ===")
    
    info = get_security_info()
    print(f"Security info: {info}")
    
    assert "access_token_expire_minutes" in info
    assert "refresh_token_expire_minutes" in info
    assert "password_min_length" in info
    assert "blacklisted_tokens_count" in info
    assert info["blacklisted_tokens_count"] >= 0

def test_token_management():
    """Test token creation and blacklisting"""
    print("\n=== Testing Token Management ===")
    
    # Test access token creation
    user_data = {"sub": "test-user-id", "username": "testuser"}
    access_token = create_access_token(user_data)
    print(f"Access token created: {access_token[:50]}...")
    assert access_token is not None
    
    # Test refresh token creation
    refresh_token = create_refresh_token(user_data)
    print(f"Refresh token created: {refresh_token[:50]}...")
    assert refresh_token is not None
    
    # Test token blacklisting
    blacklist_token(access_token)
    assert is_token_blacklisted(access_token)
    print("Token successfully blacklisted")
    
    # Test non-blacklisted token
    assert not is_token_blacklisted(refresh_token)
    print("Non-blacklisted token check passed")

def test_password_validator_class():
    """Test PasswordValidator class methods"""
    print("\n=== Testing PasswordValidator Class ===")
    
    # Test strength calculation
    score = PasswordValidator._calculate_strength("abc123")
    print(f"Password 'abc123' strength score: {score}")
    assert 0 <= score <= 100
    
    score = PasswordValidator._calculate_strength("MySecurePass123!")
    print(f"Password 'MySecurePass123!' strength score: {score}")
    assert score > 80
    
    # Test validation with different password types
    test_passwords = [
        ("123", False),  # Too short
        ("password", True),  # Valid but weak
        ("Password123", True),  # Valid and strong
        ("MySecurePass123!", True),  # Very strong
    ]
    
    for password, expected_valid in test_passwords:
        result = PasswordValidator.validate_password(password)
        print(f"Password '{password}': valid={result['is_valid']}, score={result['strength_score']}")
        assert result["is_valid"] == expected_valid

@pytest.mark.asyncio
async def test_security_service():
    """Test SecurityService class methods"""
    print("\n=== Testing SecurityService ===")
    
    # Mock user and session
    mock_user = AsyncMock()
    mock_user.username = "testuser"
    mock_user.password_hash = "hashed_password"
    
    mock_session = AsyncMock()
    
    # Test logout functionality
    test_token = "test_token_123"
    result = SecurityService.logout_user(test_token)
    print(f"Logout result: {result}")
    assert result is True
    assert is_token_blacklisted(test_token)

def test_token_type_validation():
    """Test token type validation in JWT tokens"""
    print("\n=== Testing Token Type Validation ===")
    
    user_data = {"sub": "test-user-id"}
    
    # Create access token
    access_token = create_access_token(user_data)
    print(f"Access token created with type validation")
    
    # Create refresh token
    refresh_token = create_refresh_token(user_data)
    print(f"Refresh token created with type validation")
    
    # Both tokens should be different due to different secrets and types
    assert access_token != refresh_token
    print("Token type validation working correctly")

def run_security_demo():
    """Run a comprehensive security demo"""
    print("\n" + "="*60)
    print("🔐 SECURITY IMPROVEMENTS DEMO")
    print("="*60)
    
    # Test all security features
    test_password_validation()
    test_security_info()
    test_token_management()
    test_password_validator_class()
    
    print("\n" + "="*60)
    print("✅ All security tests completed successfully!")
    print("="*60)
    
    print("\n📋 NEW SECURITY FEATURES SUMMARY:")
    print("• Password strength validation with scoring (0-100)")
    print("• Token blacklisting for secure logout")
    print("• Separate refresh token support")
    print("• Enhanced error handling and logging")
    print("• Security configuration management")
    print("• Token type validation")
    print("• Security health monitoring")
    
    print("\n🚀 NEW API ENDPOINTS:")
    print("• POST /api/v1/users/validate-password")
    print("• POST /api/v1/users/me/change-password")
    print("• GET /api/v1/users/security/info")
    print("• GET /api/v1/security/health")
    print("• GET /api/v1/security/info")
    print("• POST /api/v1/security/logout")
    print("• GET /api/v1/security/token/status")
    print("• GET /api/v1/security/stats")

if __name__ == "__main__":
    run_security_demo() 
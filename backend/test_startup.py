#!/usr/bin/env python3
"""
Quick test to see if the application can start without import errors
"""

if __name__ == "__main__":
    try:
        print("Testing imports...")
        
        # Test basic imports
        print("✓ Testing basic imports")
        from app.db.models import User, Itinerary
        print("✓ Models imported successfully")
        
        from app.db.crud_simple import create_user, get_user_by_id
        print("✓ CRUD imported successfully")
        
        from app.api.users import router as users_router
        print("✓ Users API imported successfully")
        
        from app.main import app
        print("✓ Main app imported successfully")
        
        print("\n🎉 All imports successful! Application should start.")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"❌ Other error: {e}")
        import traceback
        traceback.print_exc()
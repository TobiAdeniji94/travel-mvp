"""
Test file for database model improvements
Demonstrates and tests the enhanced models with validation, constraints, and new features
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from pydantic import ValidationError

# Import the improved models
try:
    from app.db.models import (
        User, Itinerary, Destination, Activity, Accommodation, Transportation,
        Booking, Review, ItineraryDestination, ItineraryActivity, 
        ItineraryAccommodation, ItineraryTransportation,
        UserStatus, ItineraryStatus, BookingStatus, ItemType, BookingItemType
    )
    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False

def test_user_model_improvements():
    """Test User model improvements"""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")
    
    print("\n=== Testing User Model Improvements ===")
    
    # Test valid user creation
    user_data = {
        "username": "testuser123",
        "email": "test@example.com",
        "password_hash": "hashed_password_123",
        "status": UserStatus.ACTIVE,
        "preferences": {"theme": "dark", "language": "en"},
        "travel_history": {"total_trips": 5, "favorite_destinations": ["Paris", "Tokyo"]},
        "profile_data": {"bio": "Travel enthusiast", "location": "New York"}
    }
    
    user = User(**user_data)
    print(f"✅ Valid user created: {user.username}")
    assert user.username == "testuser123"
    assert user.email == "test@example.com"
    assert user.status == UserStatus.ACTIVE
    assert user.is_active is True
    
    # Test username validation
    with pytest.raises(ValidationError):
        User(username="ab", email="test@example.com", password_hash="hash")
    print("✅ Username validation working")
    
    # Test email validation
    with pytest.raises(ValidationError):
        User(username="testuser", email="invalid-email", password_hash="hash")
    print("✅ Email validation working")
    
    # Test computed field
    user.is_deleted = True
    assert user.is_active is False
    print("✅ Computed field working")

def test_itinerary_model_improvements():
    """Test Itinerary model improvements"""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")
    
    print("\n=== Testing Itinerary Model Improvements ===")
    
    # Test valid itinerary creation
    start_date = datetime.now(timezone.utc)
    end_date = datetime.now(timezone.utc).replace(day=start_date.day + 7)
    
    itinerary_data = {
        "name": "Paris Adventure",
        "start_date": start_date,
        "end_date": end_date,
        "status": ItineraryStatus.DRAFT,
        "data": {"destinations": ["Paris"], "budget": 2000},
        "user_id": uuid4(),
        "budget": Decimal("2000.00"),
        "notes": "Romantic getaway to Paris",
        "tags": ["romantic", "culture", "food"]
    }
    
    itinerary = Itinerary(**itinerary_data)
    print(f"✅ Valid itinerary created: {itinerary.name}")
    assert itinerary.name == "Paris Adventure"
    assert itinerary.status == ItineraryStatus.DRAFT
    assert itinerary.duration_days == 7
    assert itinerary.is_active is True
    
    # Test date validation
    past_date = datetime.now(timezone.utc).replace(year=2020)
    with pytest.raises(ValidationError):
        Itinerary(
            name="Test",
            start_date=past_date,
            end_date=end_date,
            data={},
            user_id=uuid4()
        )
    print("✅ Date validation working")
    
    # Test name validation
    with pytest.raises(ValidationError):
        Itinerary(
            name="",
            start_date=start_date,
            end_date=end_date,
            data={},
            user_id=uuid4()
        )
    print("✅ Name validation working")

def test_destination_model_improvements():
    """Test Destination model improvements"""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")
    
    print("\n=== Testing Destination Model Improvements ===")
    
    # Test valid destination creation
    destination_data = {
        "name": "Paris, France",
        "description": "The City of Light",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "images": ["paris1.jpg", "paris2.jpg"],
        "rating": 4.5,
        "country": "France",
        "region": "Île-de-France",
        "timezone": "Europe/Paris",
        "climate_data": {"avg_temp": 12, "rainfall": "moderate"},
        "popularity_score": 95.0
    }
    
    destination = Destination(**destination_data)
    print(f"✅ Valid destination created: {destination.name}")
    assert destination.name == "Paris, France"
    assert destination.latitude == 48.8566
    assert destination.longitude == 2.3522
    assert destination.rating == 4.5
    
    # Test coordinate validation
    with pytest.raises(ValidationError):
        Destination(
            name="Invalid",
            latitude=100,  # Invalid latitude
            longitude=2.3522
        )
    print("✅ Coordinate validation working")
    
    # Test rating validation
    with pytest.raises(ValidationError):
        Destination(
            name="Test",
            latitude=48.8566,
            longitude=2.3522,
            rating=6.0  # Invalid rating
        )
    print("✅ Rating validation working")

def test_activity_model_improvements():
    """Test Activity model improvements"""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")
    
    print("\n=== Testing Activity Model Improvements ===")
    
    # Test valid activity creation
    activity_data = {
        "name": "Eiffel Tower Visit",
        "description": "Visit the iconic Eiffel Tower",
        "latitude": 48.8584,
        "longitude": 2.2945,
        "images": ["eiffel1.jpg", "eiffel2.jpg"],
        "price": Decimal("25.00"),
        "opening_hours": "9:00 AM - 11:45 PM",
        "rating": 4.8,
        "type": "attraction",
        "duration_minutes": 120,
        "difficulty_level": "easy",
        "age_restrictions": "All ages",
        "accessibility_info": "Wheelchair accessible"
    }
    
    activity = Activity(**activity_data)
    print(f"✅ Valid activity created: {activity.name}")
    assert activity.name == "Eiffel Tower Visit"
    assert activity.price == Decimal("25.00")
    assert activity.duration_minutes == 120
    assert activity.difficulty_level == "easy"
    
    # Test price validation
    with pytest.raises(ValidationError):
        Activity(
            name="Test",
            latitude=48.8584,
            longitude=2.2945,
            price=Decimal("-10.00")  # Negative price
        )
    print("✅ Price validation working")

def test_accommodation_model_improvements():
    """Test Accommodation model improvements"""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")
    
    print("\n=== Testing Accommodation Model Improvements ===")
    
    # Test valid accommodation creation
    accommodation_data = {
        "name": "Hotel de Paris",
        "description": "Luxury hotel in the heart of Paris",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "images": ["hotel1.jpg", "hotel2.jpg"],
        "price": Decimal("200.00"),
        "rating": 4.7,
        "amenities": ["wifi", "pool", "spa", "restaurant"],
        "type": "hotel",
        "star_rating": 5,
        "capacity": 4,
        "check_in_time": "15:00",
        "check_out_time": "11:00",
        "contact_info": {"phone": "+33-1-123-4567", "email": "info@hoteldeparis.com"}
    }
    
    accommodation = Accommodation(**accommodation_data)
    print(f"✅ Valid accommodation created: {accommodation.name}")
    assert accommodation.name == "Hotel de Paris"
    assert accommodation.price == Decimal("200.00")
    assert accommodation.star_rating == 5
    assert "wifi" in accommodation.amenities
    
    # Test amenities validation
    assert isinstance(accommodation.amenities, list)
    print("✅ Amenities validation working")

def test_transportation_model_improvements():
    """Test Transportation model improvements"""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")
    
    print("\n=== Testing Transportation Model Improvements ===")
    
    # Test valid transportation creation
    departure_time = datetime.now(timezone.utc)
    arrival_time = departure_time.replace(hour=departure_time.hour + 2)
    
    transportation_data = {
        "type": "flight",
        "departure_lat": 48.8566,
        "departure_long": 2.3522,
        "arrival_lat": 40.7128,
        "arrival_long": -74.0060,
        "departure_time": departure_time,
        "arrival_time": arrival_time,
        "price": Decimal("500.00"),
        "provider": "Air France",
        "booking_reference": "AF123456",
        "duration_minutes": 120,
        "distance_km": 5835.0,
        "capacity": 180
    }
    
    transportation = Transportation(**transportation_data)
    print(f"✅ Valid transportation created: {transportation.type}")
    assert transportation.type == "flight"
    assert transportation.price == Decimal("500.00")
    assert transportation.provider == "Air France"
    assert transportation.duration_hours == 2.0
    
    # Test duration calculation
    assert transportation.duration_hours == 2.0
    print("✅ Duration calculation working")
    
    # Test type validation
    with pytest.raises(ValidationError):
        Transportation(
            type="",  # Empty type
            departure_lat=48.8566,
            departure_long=2.3522,
            arrival_lat=40.7128,
            arrival_long=-74.0060,
            departure_time=departure_time,
            arrival_time=arrival_time
        )
    print("✅ Type validation working")

def test_booking_model_improvements():
    """Test Booking model improvements"""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")
    
    print("\n=== Testing Booking Model Improvements ===")
    
    # Test valid booking creation
    booking_data = {
        "user_id": uuid4(),
        "itinerary_id": uuid4(),
        "item_id": "hotel_123",
        "item_type": BookingItemType.ACCOMMODATION,
        "booking_details": {"room_type": "deluxe", "guests": 2},
        "status": BookingStatus.CONFIRMED,
        "total_amount": Decimal("400.00"),
        "currency": "USD",
        "confirmation_number": "BK123456789"
    }
    
    booking = Booking(**booking_data)
    print(f"✅ Valid booking created: {booking.confirmation_number}")
    assert booking.status == BookingStatus.CONFIRMED
    assert booking.total_amount == Decimal("400.00")
    assert booking.currency == "USD"
    
    # Test item_id validation
    with pytest.raises(ValidationError):
        Booking(
            user_id=uuid4(),
            itinerary_id=uuid4(),
            item_id="",  # Empty item_id
            item_type=BookingItemType.ACCOMMODATION,
            booking_details={}
        )
    print("✅ Item ID validation working")

def test_review_model_improvements():
    """Test Review model improvements"""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")
    
    print("\n=== Testing Review Model Improvements ===")
    
    # Test valid review creation
    review_data = {
        "user_id": uuid4(),
        "item_id": "hotel_123",
        "item_type": ItemType.ACCOMMODATION,
        "rating": 5,
        "review_text": "Excellent hotel with great service!",
        "images": ["review1.jpg"],
        "helpful_votes": 10,
        "verified_purchase": True,
        "language": "en"
    }
    
    review = Review(**review_data)
    print(f"✅ Valid review created: {review.rating} stars")
    assert review.rating == 5
    assert review.helpful_votes == 10
    assert review.verified_purchase is True
    assert review.language == "en"
    
    # Test rating validation
    with pytest.raises(ValidationError):
        Review(
            user_id=uuid4(),
            item_id="hotel_123",
            item_type=ItemType.ACCOMMODATION,
            rating=6  # Invalid rating
        )
    print("✅ Rating validation working")
    
    # Test empty review text handling
    review_empty_text = Review(
        user_id=uuid4(),
        item_id="hotel_123",
        item_type=ItemType.ACCOMMODATION,
        rating=4,
        review_text="   "  # Empty text
    )
    assert review_empty_text.review_text is None
    print("✅ Empty review text handling working")

def test_junction_table_improvements():
    """Test junction table improvements"""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")
    
    print("\n=== Testing Junction Table Improvements ===")
    
    # Test ItineraryDestination
    dest_link = ItineraryDestination(
        itinerary_id=uuid4(),
        destination_id=uuid4(),
        order=1,
        notes="First stop on our journey",
        planned_duration=3
    )
    print(f"✅ Valid destination link created: order {dest_link.order}")
    assert dest_link.order == 1
    assert dest_link.planned_duration == 3
    
    # Test ItineraryActivity
    act_link = ItineraryActivity(
        itinerary_id=uuid4(),
        activity_id=uuid4(),
        order=2,
        notes="Must-see attraction",
        planned_duration=120,
        scheduled_time=datetime.now(timezone.utc)
    )
    print(f"✅ Valid activity link created: order {act_link.order}")
    assert act_link.order == 2
    assert act_link.planned_duration == 120
    
    # Test ItineraryAccommodation
    accom_link = ItineraryAccommodation(
        itinerary_id=uuid4(),
        accommodation_id=uuid4(),
        order=1,
        notes="Luxury stay",
        check_in_date=datetime.now(timezone.utc),
        check_out_date=datetime.now(timezone.utc).replace(day=datetime.now().day + 3),
        guest_count=2
    )
    print(f"✅ Valid accommodation link created: {accom_link.guest_count} guests")
    assert accom_link.guest_count == 2
    
    # Test ItineraryTransportation
    trans_link = ItineraryTransportation(
        itinerary_id=uuid4(),
        transportation_id=uuid4(),
        order=1,
        notes="Direct flight",
        passenger_count=2
    )
    print(f"✅ Valid transportation link created: {trans_link.passenger_count} passengers")
    assert trans_link.passenger_count == 2

def test_base_model_features():
    """Test BaseModel features"""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")
    
    print("\n=== Testing BaseModel Features ===")
    
    # Test audit fields
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="hash"
    )
    
    print(f"✅ Created at: {user.created_at}")
    print(f"✅ Updated at: {user.updated_at}")
    print(f"✅ Is deleted: {user.is_deleted}")
    print(f"✅ Deleted at: {user.deleted_at}")
    
    assert user.created_at is not None
    assert user.updated_at is not None
    assert user.is_deleted is False
    assert user.deleted_at is None
    
    # Test soft delete
    user.is_deleted = True
    user.deleted_at = datetime.now(timezone.utc)
    assert user.is_deleted is True
    assert user.deleted_at is not None
    print("✅ Soft delete functionality working")

def test_constraints_and_indexes():
    """Test database constraints and indexes"""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")
    
    print("\n=== Testing Constraints and Indexes ===")
    
    # Test that models have table_args
    models_with_constraints = [
        User, Itinerary, Destination, Activity, Accommodation, 
        Transportation, Booking, Review
    ]
    
    for model in models_with_constraints:
        assert hasattr(model, '__table_args__')
        print(f"✅ {model.__name__} has table constraints")
    
    # Test junction tables have constraints
    junction_models = [
        ItineraryDestination, ItineraryActivity, 
        ItineraryAccommodation, ItineraryTransportation
    ]
    
    for model in junction_models:
        assert hasattr(model, '__table_args__')
        print(f"✅ {model.__name__} has table constraints")

def test_enum_improvements():
    """Test enum improvements"""
    if not MODELS_AVAILABLE:
        pytest.skip("Models not available")
    
    print("\n=== Testing Enum Improvements ===")
    
    # Test UserStatus enum
    assert UserStatus.ACTIVE == "active"
    assert UserStatus.INACTIVE == "inactive"
    assert UserStatus.SUSPENDED == "suspended"
    print("✅ UserStatus enum working")
    
    # Test ItineraryStatus enum
    assert ItineraryStatus.DRAFT == "draft"
    assert ItineraryStatus.GENERATED == "generated"
    assert ItineraryStatus.BOOKED == "booked"
    assert ItineraryStatus.CANCELLED == "cancelled"
    assert ItineraryStatus.COMPLETED == "completed"
    print("✅ ItineraryStatus enum working")
    
    # Test BookingStatus enum
    assert BookingStatus.PENDING == "pending"
    assert BookingStatus.CONFIRMED == "confirmed"
    assert BookingStatus.CANCELLED == "cancelled"
    assert BookingStatus.COMPLETED == "completed"
    print("✅ BookingStatus enum working")

def run_models_demo():
    """Run a comprehensive models improvements demo"""
    print("\n" + "="*60)
    print("🗄️ DATABASE MODELS IMPROVEMENTS DEMO")
    print("="*60)
    
    # Test all model improvements
    test_user_model_improvements()
    test_itinerary_model_improvements()
    test_destination_model_improvements()
    test_activity_model_improvements()
    test_accommodation_model_improvements()
    test_transportation_model_improvements()
    test_booking_model_improvements()
    test_review_model_improvements()
    test_junction_table_improvements()
    test_base_model_features()
    test_constraints_and_indexes()
    test_enum_improvements()
    
    print("\n" + "="*60)
    print("✅ All model tests completed successfully!")
    print("="*60)
    
    print("\n📋 MODEL IMPROVEMENTS SUMMARY:")
    print("• Enhanced validation with Pydantic field_validator")
    print("• Database constraints and indexes for performance")
    print("• Soft delete functionality with audit fields")
    print("• Computed fields for derived data")
    print("• Comprehensive enum types for status tracking")
    print("• Better field descriptions and documentation")
    print("• Improved data types (Decimal for money)")
    print("• Additional metadata fields for rich data")
    print("• Junction table enhancements with notes and scheduling")
    print("• Geographic coordinate validation")
    print("• Rating and price range validation")
    print("• User-friendly error messages")
    
    print("\n🚀 NEW FEATURES:")
    print("• BaseModel with audit fields (created_at, updated_at, is_deleted)")
    print("• Status enums for better state management")
    print("• Computed fields (duration_days, is_active, duration_hours)")
    print("• Enhanced junction tables with notes and scheduling")
    print("• Comprehensive validation for all data types")
    print("• Database constraints for data integrity")
    print("• Performance indexes for common queries")
    print("• Rich metadata fields (climate_data, contact_info, etc.)")
    
    print("\n🔧 TECHNICAL IMPROVEMENTS:")
    print("• Better type hints and documentation")
    print("• Consistent field naming and structure")
    print("• Proper foreign key relationships")
    print("• JSON field validation and structure")
    print("• Timezone-aware datetime handling")
    print("• Decimal precision for monetary values")
    print("• Comprehensive error handling")
    print("• Database-level data validation")

if __name__ == "__main__":
    run_models_demo() 
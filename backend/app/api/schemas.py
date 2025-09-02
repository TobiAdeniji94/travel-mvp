from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
from uuid import UUID
from datetime import datetime
from decimal import Decimal

# Import enums from models
from app.db.models import UserStatus, ItineraryStatus, BookingStatus, ItemType, BookingItemType

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters long")

class UserRead(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    status: UserStatus
    preferences: Optional[Dict[str, Any]] = None
    travel_history: Optional[Dict[str, Any]] = None
    profile_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        orm_mode = True

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    status: Optional[UserStatus] = None
    preferences: Optional[Dict[str, Any]] = None
    travel_history: Optional[Dict[str, Any]] = None
    profile_data: Optional[Dict[str, Any]] = None

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    sub: str | None = None

class PasswordValidationRequest(BaseModel):
    password: str = Field(..., description="Password to validate")

class PasswordValidationResponse(BaseModel):
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    strength_score: int
    suggestions: List[str]

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=6, description="New password")

class SecurityInfoResponse(BaseModel):
    access_token_expire_minutes: int
    refresh_token_expire_minutes: int
    password_min_length: int
    password_require_uppercase: bool
    password_require_number: bool
    algorithm: str
    blacklisted_tokens_count: int

# ===== CATALOG STATISTICS SCHEMAS =====

class CatalogStats(BaseModel):
    destinations_count: int
    activities_count: int
    accommodations_count: int
    transportations_count: int
    total_items: int
    last_updated: datetime

class SeedingStatus(BaseModel):
    is_seeded: bool
    destinations_seeded: int
    activities_seeded: int
    accommodations_seeded: int
    transportations_seeded: int
    seeding_errors: int
    last_seeding_time: Optional[datetime] = None
    seeding_log_file: Optional[str] = None

# ===== ITINERARY SCHEMAS =====

class ItineraryCreate(BaseModel):
    text: str = Field(..., description="Natural language travel request")
    use_transformer: Optional[bool] = Field(
        default=None,
        description="Override server setting to enable/disable Transformer ordering for this request",
    )
    
    @field_validator('text')
    @classmethod
    def validate_text(cls, v):
        if not v or not v.strip():
            raise ValueError("Travel request cannot be empty")
        if len(v) > 2000:
            raise ValueError("Travel request too long (max 2000 characters)")
        # Check for potentially malicious content
        suspicious_patterns = ['<script>', 'javascript:', 'data:text/html']
        if any(pattern in v.lower() for pattern in suspicious_patterns):
            raise ValueError("Travel request contains invalid content")
        return v.strip()

class ItineraryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[ItineraryStatus] = None
    budget: Optional[Decimal] = None
    notes: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = None
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v and len(v.strip()) == 0:
            raise ValueError("Name cannot be empty")
        return v

# Debug/utility schemas for Transformer ordering preview
class ReorderPreviewRequest(BaseModel):
    poi_ids: List[str] = Field(..., description="List of POI UUID strings to reorder")

class ReorderPreviewResponse(BaseModel):
    input: List[str]
    output: List[str]

# ===== CATALOG ITEM SCHEMAS =====

class DestinationRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    images: Optional[List[str]] = None
    rating: Optional[float] = None
    country: Optional[str] = None
    region: Optional[str] = None
    timezone: Optional[str] = None
    climate_data: Optional[Dict[str, Any]] = None
    popularity_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class ActivityRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    images: Optional[List[str]] = None
    price: Optional[Decimal] = None
    opening_hours: Optional[str] = None
    rating: Optional[float] = None
    type: Optional[str] = None
    duration_minutes: Optional[int] = None
    difficulty_level: Optional[str] = None
    age_restrictions: Optional[str] = None
    accessibility_info: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class AccommodationRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    images: Optional[List[str]] = None
    price: Optional[Decimal] = None
    rating: Optional[float] = None
    amenities: Optional[List[str]] = None
    type: Optional[str] = None
    star_rating: Optional[int] = None
    capacity: Optional[int] = None
    check_in_time: Optional[str] = None
    check_out_time: Optional[str] = None
    contact_info: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class TransportationRead(BaseModel):
    id: UUID
    type: str
    departure_lat: float
    departure_long: float
    arrival_lat: float
    arrival_long: float
    departure_time: datetime
    arrival_time: datetime
    price: Optional[Decimal] = None
    provider: Optional[str] = None
    booking_reference: Optional[str] = None
    duration_minutes: Optional[int] = None
    distance_km: Optional[float] = None
    capacity: Optional[int] = None
    duration_hours: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# ===== JUNCTION TABLE SCHEMAS =====

class ItineraryDestinationRead(BaseModel):
    order: int
    notes: Optional[str] = None
    planned_duration: Optional[int] = None
    destination: DestinationRead

    class Config:
        orm_mode = True

class ItineraryActivityRead(BaseModel):
    order: int
    notes: Optional[str] = None
    planned_duration: Optional[int] = None
    scheduled_time: Optional[datetime] = None
    activity: ActivityRead

    class Config:
        orm_mode = True

class ItineraryAccommodationRead(BaseModel):
    order: int
    notes: Optional[str] = None
    check_in_date: Optional[datetime] = None
    check_out_date: Optional[datetime] = None
    guest_count: Optional[int] = None
    accommodation: AccommodationRead

    class Config:
        orm_mode = True

class ItineraryTransportationRead(BaseModel):
    order: int
    notes: Optional[str] = None
    passenger_count: Optional[int] = None
    transportation: TransportationRead

    class Config:
        orm_mode = True

class ItineraryRead(BaseModel):
    id: UUID
    name: str
    start_date: datetime
    end_date: datetime
    status: ItineraryStatus
    data: Dict[str, Any]
    budget: Optional[Decimal] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    duration_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    scheduled_items: Optional[List[List[Any]]] = None

    dest_links: List[ItineraryDestinationRead]        = []
    act_links:  List[ItineraryActivityRead]           = []
    accom_links:List[ItineraryAccommodationRead]      = []
    trans_links:List[ItineraryTransportationRead]     = []
    
    class Config:
        orm_mode = True


# ===== BOOKING SCHEMAS =====

class BookingCreate(BaseModel):
    item_id: str = Field(..., max_length=100)
    item_type: BookingItemType
    booking_details: Dict[str, Any]
    total_amount: Optional[Decimal] = None
    currency: Optional[str] = Field(default="USD", max_length=3)
    confirmation_number: Optional[str] = Field(None, max_length=100)

class BookingRead(BaseModel):
    id: UUID
    user_id: UUID
    itinerary_id: UUID
    item_id: str
    item_type: BookingItemType
    booking_date: datetime
    booking_details: Dict[str, Any]
    status: BookingStatus
    total_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    confirmation_number: Optional[str] = None
    cancellation_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class BookingUpdate(BaseModel):
    status: Optional[BookingStatus] = None
    booking_details: Optional[Dict[str, Any]] = None
    total_amount: Optional[Decimal] = None
    currency: Optional[str] = None
    cancellation_reason: Optional[str] = Field(None, max_length=500)

# ===== REVIEW SCHEMAS =====

class ReviewCreate(BaseModel):
    item_id: str = Field(..., max_length=100)
    item_type: ItemType
    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = Field(None, max_length=2000)
    images: Optional[List[str]] = None
    language: Optional[str] = Field(default="en", max_length=10)

class ReviewRead(BaseModel):
    id: UUID
    user_id: UUID
    item_id: str
    item_type: ItemType
    rating: int
    review_text: Optional[str] = None
    review_date: datetime
    images: Optional[List[str]] = None
    helpful_votes: int
    verified_purchase: bool
    language: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(None, ge=1, le=5)
    review_text: Optional[str] = Field(None, max_length=2000)
    images: Optional[List[str]] = None
    language: Optional[str] = Field(None, max_length=10)

# ===== RECOMMENDATION SCHEMAS =====

class RecommendationRequest(BaseModel):
    interests: List[str] = Field(..., min_items=1)
    budget: Optional[Decimal] = Field(None, ge=0)
    location: Optional[str] = None
    duration_days: Optional[int] = Field(None, ge=1, le=365)
    travel_style: Optional[str] = None  # luxury, budget, adventure, etc.

class RecommendationResponse(BaseModel):
    items: List[Dict[str, Any]]
    total_count: int
    budget_estimate: Optional[Decimal] = None
    confidence_score: float
    reasoning: Optional[str] = None

# ===== SEARCH SCHEMAS =====

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)
    item_type: Optional[ItemType] = None
    location: Optional[str] = None
    price_min: Optional[Decimal] = None
    price_max: Optional[Decimal] = None
    rating_min: Optional[float] = Field(None, ge=0, le=5)
    limit: Optional[int] = Field(default=20, ge=1, le=100)

class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total_count: int
    query_time_ms: float
    filters_applied: Dict[str, Any]
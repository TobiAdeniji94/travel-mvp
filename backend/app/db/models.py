import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from decimal import Decimal

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, Index, CheckConstraint, Boolean
from sqlalchemy.dialects.postgresql import JSON, ENUM as PG_ENUM, UUID as PG_UUID
from sqlalchemy.orm import declared_attr, Mapped
from pydantic import field_validator, computed_field
from uuid import UUID as PyUUID

# Enums
class ItemType(str, Enum):
    DESTINATION = "DESTINATION"
    ACTIVITY = "ACTIVITY"
    ACCOMMODATION = "ACCOMMODATION"
    TRANSPORTATION = "TRANSPORTATION"

class BookingItemType(str, Enum):
    DESTINATION = "DESTINATION"
    ACTIVITY = "ACTIVITY"
    ACCOMMODATION = "ACCOMMODATION"
    TRANSPORTATION = "TRANSPORTATION"

class ItineraryStatus(str, Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    BOOKED = "booked"
    CANCELLED = "cancelled"
    COMPLETED = "completed"

class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

# Base model with common fields (for new tables only)
class BaseModel(SQLModel):
    """Base model with common audit fields for new tables"""
    pass

class AuditMixin:
    __allow_unmapped__ = True

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:
        return Column(
            DateTime(timezone=True),
            nullable=False,
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
        )

    @declared_attr
    def is_deleted(cls) -> Mapped[bool]:
        return Column(Boolean, nullable=False, default=False)

    @declared_attr
    def deleted_at(cls) -> Mapped[Optional[datetime]]:
        return Column(DateTime(timezone=True), nullable=True)

# Models
class User(AuditMixin, BaseModel, table=True):
    __tablename__ = "users"
    
    # Add indexes for better performance
    __table_args__ = (
        Index('idx_users_username', 'username'),
        Index('idx_users_email', 'email'),
        Index('idx_users_status', 'status'),
        Index('idx_users_created_at', 'created_at'),
        CheckConstraint('length(username) >= 3', name='check_username_length'),
        CheckConstraint('length(email) > 0', name='check_email_not_empty'),
    )

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(
        index=True, 
        unique=True, 
        nullable=False,
        max_length=50,
        description="Unique username for login"
    )
    email: str = Field(
        index=True, 
        unique=True, 
        nullable=False,
        max_length=255,
        description="User's email address"
    )
    password_hash: str = Field(
        nullable=False,
        max_length=255,
        description="Hashed password"
    )
    status: UserStatus = Field(
        default=UserStatus.ACTIVE,
        sa_column=Column(
            PG_ENUM(UserStatus, name="userstatus"),
            nullable=False,
            server_default=UserStatus.ACTIVE.value
        ),
        description="User account status"
    )
    preferences: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSON, nullable=True),
        description="User preferences and settings"
    )
    travel_history: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSON, nullable=True),
        description="User's travel history and statistics"
    )
    profile_data: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Additional profile information"
    )

    # Relationships
    itineraries: List["Itinerary"] = Relationship(back_populates="user")
    bookings: List["Booking"] = Relationship(back_populates="user")
    reviews: List["Review"] = Relationship(back_populates="user")

    # Validators
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v or len(v.strip()) < 3:
            raise ValueError('Username must be at least 3 characters')
        if not v.isalnum() and '_' not in v:
            raise ValueError('Username can only contain alphanumeric characters and underscores')
        return v.strip().lower()

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not v or '@' not in v:
            raise ValueError('Invalid email format')
        return v.strip().lower()

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if user account is active"""
        return self.status == UserStatus.ACTIVE and not self.is_deleted


class Itinerary(AuditMixin, BaseModel, table=True):
    __tablename__ = "itineraries"
    
    __table_args__ = (
        Index('idx_itineraries_user_id', 'user_id'),
        Index('idx_itineraries_status', 'status'),
        Index('idx_itineraries_dates', 'start_date', 'end_date'),
        Index('idx_itineraries_created_at', 'created_at'),
        CheckConstraint('start_date < end_date', name='check_valid_date_range'),
        CheckConstraint('length(name) > 0', name='check_name_not_empty'),
    )

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(
        max_length=200,
        description="Itinerary name"
    )
    start_date: datetime = Field(
        sa_column=Column(DateTime(timezone=True)),
        description="Trip start date"
    )
    end_date: datetime = Field(
        sa_column=Column(DateTime(timezone=True)),
        description="Trip end date"
    )
    status: ItineraryStatus = Field(
        default=ItineraryStatus.DRAFT,
        sa_column=Column(PG_ENUM(ItineraryStatus, name="itinerarystatus")),
        description="Current itinerary status"
    )
    data: Dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False),
        description="Raw parsed parameters (locations, dates, interests, budget)"
    )
    user_id: PyUUID = Field(
        foreign_key="users.id", 
        nullable=False,
        description="Owner of this itinerary"
    )
    
    # Additional fields
    budget: Optional[Decimal] = Field(
        default=None,
        description="Total budget for the trip"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="User notes about the itinerary"
    )
    tags: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Tags for categorizing itineraries"
    )

    # Relationships
    user: User = Relationship(back_populates="itineraries")
    dest_links: List["ItineraryDestination"] = Relationship(back_populates="itinerary")
    act_links: List["ItineraryActivity"] = Relationship(back_populates="itinerary")
    accom_links: List["ItineraryAccommodation"] = Relationship(back_populates="itinerary")
    trans_links: List["ItineraryTransportation"] = Relationship(back_populates="itinerary")
    bookings: List["Booking"] = Relationship(back_populates="itinerary")

    # Validators
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('Itinerary name cannot be empty')
        return v.strip()

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_dates(cls, v: datetime) -> datetime:
        if v and v < datetime.now(timezone.utc):
            raise ValueError('Dates cannot be in the past')
        return v

    @computed_field
    @property
    def duration_days(self) -> int:
        """Calculate trip duration in days"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0

    @computed_field
    @property
    def is_active(self) -> bool:
        """Check if itinerary is active (not cancelled or deleted)"""
        return self.status not in [ItineraryStatus.CANCELLED] and not self.is_deleted


class Destination(AuditMixin, BaseModel, table=True):
    __tablename__ = "destinations"
    
    __table_args__ = (
        Index('idx_destinations_name', 'name'),
        Index('idx_destinations_coordinates', 'latitude', 'longitude'),
        Index('idx_destinations_rating', 'rating'),
        Index('idx_destinations_created_at', 'created_at'),
        CheckConstraint('latitude BETWEEN -90 AND 90', name='check_valid_latitude'),
        CheckConstraint('longitude BETWEEN -180 AND 180', name='check_valid_longitude'),
        CheckConstraint('rating IS NULL OR (rating >= 0 AND rating <= 10)', name='check_valid_rating'),
    )

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(
        max_length=200,
        description="Destination name"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Destination description"
    )
    latitude: float = Field(description="Latitude coordinate")
    longitude: float = Field(description="Longitude coordinate")
    images: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="List of image URLs"
    )
    rating: Optional[float] = Field(
        default=None,
        ge=0,
        le=5,
        description="Average rating (0-5)"
    )
    
    # Additional fields
    country: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Country name"
    )
    region: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Region/state name"
    )
    timezone: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Timezone identifier"
    )
    climate_data: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Climate and weather information"
    )
    popularity_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Popularity score (0-100)"
    )

    # Relationships
    dest_links: List["ItineraryDestination"] = Relationship(back_populates="destination")

    # Validators
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('Destination name cannot be empty')
        return v.strip()

    @field_validator('latitude', 'longitude')
    @classmethod
    def validate_coordinates(cls, v: float) -> float:
        if v is None:
            return v
        if not isinstance(v, (int, float)):
            raise ValueError('Coordinates must be numeric')
        return float(v)


class ItineraryDestination(SQLModel, table=True):
    __tablename__ = "itinerary_destinations"
    
    __table_args__ = (
        Index('idx_itinerary_destinations_itinerary', 'itinerary_id'),
        Index('idx_itinerary_destinations_destination', 'destination_id'),
        Index('idx_itinerary_destinations_order', 'order'),
        CheckConstraint('"order" >= 0', name='check_valid_order'),
    )

    itinerary_id: PyUUID = Field(foreign_key="itineraries.id", primary_key=True)
    destination_id: PyUUID = Field(foreign_key="destinations.id", primary_key=True)
    order: int = Field(description="Order in the itinerary")
    
    # Additional fields
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Notes about this destination in the itinerary"
    )
    planned_duration: Optional[int] = Field(
        default=None,
        ge=1,
        description="Planned duration in days"
    )

    # Relationships
    itinerary: Itinerary = Relationship(back_populates="dest_links")
    destination: Destination = Relationship(back_populates="dest_links")


class Activity(BaseModel, table=True):
    __tablename__ = "activities"
    
    __table_args__ = (
        Index('idx_activities_name', 'name'),
        Index('idx_activities_coordinates', 'latitude', 'longitude'),
        Index('idx_activities_price', 'price'),
        Index('idx_activities_rating', 'rating'),
        Index('idx_activities_type', 'type'),
        CheckConstraint('latitude BETWEEN -90 AND 90', name='check_valid_latitude'),
        CheckConstraint('longitude BETWEEN -180 AND 180', name='check_valid_longitude'),
        CheckConstraint('price IS NULL OR price >= 0', name='check_valid_price'),
        CheckConstraint('rating IS NULL OR (rating >= 0 AND rating <= 5)', name='check_valid_rating'),
    )

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(
        max_length=200,
        description="Activity name"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Activity description"
    )
    latitude: float = Field(description="Latitude coordinate")
    longitude: float = Field(description="Longitude coordinate")
    images: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="List of image URLs"
    )
    price: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Activity price"
    )
    opening_hours: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Opening hours information"
    )
    rating: Optional[float] = Field(
        default=None,
        ge=0,
        le=5,
        description="Average rating (0-5)"
    )
    
    # Additional fields
    type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Activity type/category"
    )
    duration_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        description="Typical duration in minutes"
    )
    difficulty_level: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Difficulty level (easy, moderate, hard)"
    )
    age_restrictions: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Age restrictions information"
    )
    accessibility_info: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Accessibility information"
    )

    # Relationships
    act_links: List["ItineraryActivity"] = Relationship(back_populates="activity")

    # Validators
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('Activity name cannot be empty')
        return v.strip()

    @field_validator('images')
    @classmethod
    def normalize_images(cls, v):
        """Normalize image entries: extract Google `photoreference` tokens
        when a full signed URL was provided so we store only the token.
        """
        if v is None:
            return v
        import re

        def extract(item):
            if not isinstance(item, str):
                return item
            # If it's a Google Place Photo URL, extract photoreference
            m = re.search(r'photoreference=([^&\s]+)', item)
            if m:
                return m.group(1)
            # If it already looks like a photoreference token, keep it
            if not item.startswith('http'):
                return item
            # Otherwise, strip any API key param to be safe
            return re.sub(r'([?&]key=)[^&\s]+', '', item)

        return [extract(it) for it in v]


class ItineraryActivity(SQLModel, table=True):
    __tablename__ = "itinerary_activities"
    
    __table_args__ = (
        Index('idx_itinerary_activities_itinerary', 'itinerary_id'),
        Index('idx_itinerary_activities_activity', 'activity_id'),
        Index('idx_itinerary_activities_order', 'order'),
        CheckConstraint('"order" >= 0', name='check_valid_order'),
    )

    itinerary_id: PyUUID = Field(foreign_key="itineraries.id", primary_key=True)
    activity_id: PyUUID = Field(foreign_key="activities.id", primary_key=True)
    order: int = Field(description="Order in the itinerary")
    
    # Additional fields
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Notes about this activity in the itinerary"
    )
    planned_duration: Optional[int] = Field(
        default=None,
        ge=1,
        description="Planned duration in minutes"
    )
    scheduled_time: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
        description="Scheduled time for this activity"
    )

    # Relationships
    itinerary: Itinerary = Relationship(back_populates="act_links")
    activity: Activity = Relationship(back_populates="act_links")


class Accommodation(AuditMixin, BaseModel, table=True):
    __tablename__ = "accommodations"
    
    __table_args__ = (
        Index('idx_accommodations_name', 'name'),
        Index('idx_accommodations_coordinates', 'latitude', 'longitude'),
        Index('idx_accommodations_price', 'price'),
        Index('idx_accommodations_rating', 'rating'),
        Index('idx_accommodations_type', 'type'),
        CheckConstraint('latitude BETWEEN -90 AND 90', name='check_valid_latitude'),
        CheckConstraint('longitude BETWEEN -180 AND 180', name='check_valid_longitude'),
        CheckConstraint('price IS NULL OR price >= 0', name='check_valid_price'),
        CheckConstraint('rating IS NULL OR (rating >= 0 AND rating <= 5)', name='check_valid_rating'),
    )

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(
        max_length=200,
        description="Accommodation name"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Accommodation description"
    )
    latitude: float = Field(description="Latitude coordinate")
    longitude: float = Field(description="Longitude coordinate")
    images: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="List of image URLs"
    )
    price: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Price per night"
    )
    rating: Optional[float] = Field(
        default=None,
        ge=0,
        le=5,
        description="Average rating (0-5)"
    )
    amenities: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="List of available amenities"
    )
    
    # Additional fields
    type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Accommodation type (hotel, hostel, apartment, etc.)"
    )
    star_rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Star rating (1-5)"
    )
    capacity: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum number of guests"
    )
    check_in_time: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Check-in time (e.g., '14:00')"
    )
    check_out_time: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Check-out time (e.g., '11:00')"
    )
    contact_info: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="Contact information"
    )

    # Relationships
    accom_links: List["ItineraryAccommodation"] = Relationship(back_populates="accommodation")

    # Validators
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('Accommodation name cannot be empty')
        return v.strip()


class ItineraryAccommodation(SQLModel, table=True):
    __tablename__ = "itinerary_accommodations"
    
    __table_args__ = (
        Index('idx_itinerary_accommodations_itinerary', 'itinerary_id'),
        Index('idx_itinerary_accommodations_accommodation', 'accommodation_id'),
        Index('idx_itinerary_accommodations_order', 'order'),
        CheckConstraint('"order" >= 0', name='check_valid_order'),
    )

    itinerary_id: PyUUID = Field(foreign_key="itineraries.id", primary_key=True)
    accommodation_id: PyUUID = Field(foreign_key="accommodations.id", primary_key=True)
    order: int = Field(description="Order in the itinerary")
    
    # Additional fields
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Notes about this accommodation in the itinerary"
    )
    check_in_date: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
        description="Check-in date"
    )
    check_out_date: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
        description="Check-out date"
    )
    guest_count: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of guests"
    )

    # Relationships
    itinerary: Itinerary = Relationship(back_populates="accom_links")
    accommodation: Accommodation = Relationship(back_populates="accom_links")


class Transportation(BaseModel, table=True):
    __tablename__ = "transportations"
    
    __table_args__ = (
        Index('idx_transportations_type', 'type'),
        Index('idx_transportations_departure', 'departure_lat', 'departure_long'),
        Index('idx_transportations_arrival', 'arrival_lat', 'arrival_long'),
        Index('idx_transportations_price', 'price'),
        CheckConstraint('departure_lat BETWEEN -90 AND 90', name='check_valid_departure_lat'),
        CheckConstraint('departure_long BETWEEN -180 AND 180', name='check_valid_departure_long'),
        CheckConstraint('arrival_lat BETWEEN -90 AND 90', name='check_valid_arrival_lat'),
        CheckConstraint('arrival_long BETWEEN -180 AND 180', name='check_valid_arrival_long'),
        CheckConstraint('price IS NULL OR price >= 0', name='check_valid_price'),
        CheckConstraint('departure_time < arrival_time', name='check_valid_time_range'),
    )

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    type: str = Field(
        max_length=100,
        description="Transportation type (flight, train, bus, car, etc.)"
    )
    departure_lat: float = Field(description="Departure latitude")
    departure_long: float = Field(description="Departure longitude")
    arrival_lat: float = Field(description="Arrival latitude")
    arrival_long: float = Field(description="Arrival longitude")
    departure_time: datetime = Field(
        sa_column=Column(DateTime(timezone=True)),
        description="Departure time"
    )
    arrival_time: datetime = Field(
        sa_column=Column(DateTime(timezone=True)),
        description="Arrival time"
    )
    price: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Transportation price"
    )
    
    # Additional fields
    provider: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Transportation provider"
    )
    booking_reference: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Booking reference number"
    )
    duration_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        description="Journey duration in minutes"
    )
    distance_km: Optional[float] = Field(
        default=None,
        ge=0,
        description="Distance in kilometers"
    )
    capacity: Optional[int] = Field(
        default=None,
        ge=1,
        description="Passenger capacity"
    )

    # Relationships
    trans_links: List["ItineraryTransportation"] = Relationship(back_populates="transportation")

    # Validators
    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('Transportation type cannot be empty')
        return v.strip().lower()

    @computed_field
    @property
    def duration_hours(self) -> Optional[float]:
        """Calculate journey duration in hours"""
        if self.departure_time and self.arrival_time:
            duration = self.arrival_time - self.departure_time
            return duration.total_seconds() / 3600
        return None


class ItineraryTransportation(SQLModel, table=True):
    __tablename__ = "itinerary_transportations"
    
    __table_args__ = (
        Index('idx_itinerary_transportations_itinerary', 'itinerary_id'),
        Index('idx_itinerary_transportations_transportation', 'transportation_id'),
        Index('idx_itinerary_transportations_order', 'order'),
        CheckConstraint('"order" >= 0', name='check_valid_order'),
    )

    itinerary_id: PyUUID = Field(foreign_key="itineraries.id", primary_key=True)
    transportation_id: PyUUID = Field(foreign_key="transportations.id", primary_key=True)
    order: int = Field(description="Order in the itinerary")
    
    # Additional fields
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Notes about this transportation in the itinerary"
    )
    passenger_count: Optional[int] = Field(
        default=None,
        ge=1,
        description="Number of passengers"
    )

    # Relationships
    itinerary: Itinerary = Relationship(back_populates="trans_links")
    transportation: Transportation = Relationship(back_populates="trans_links")


class Booking(BaseModel, table=True):
    __tablename__ = "bookings"
    
    __table_args__ = (
        Index('idx_bookings_user_id', 'user_id'),
        Index('idx_bookings_itinerary_id', 'itinerary_id'),
        Index('idx_bookings_status', 'status'),
        Index('idx_bookings_booking_date', 'booking_date'),
        Index('idx_bookings_item', 'item_id', 'item_type'),
    )

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: PyUUID = Field(
        foreign_key="users.id",
        nullable=False,
        description="User who made the booking"
    )
    itinerary_id: PyUUID = Field(
        foreign_key="itineraries.id",
        nullable=False,
        description="Associated itinerary"
    )
    item_id: str = Field(
        max_length=100,
        description="ID of the booked item"
    )
    item_type: BookingItemType = Field(
        sa_column=Column(PG_ENUM(BookingItemType, name="bookingitemtype")),
        description="Type of booked item"
    )
    booking_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="When the booking was made"
    )
    booking_details: Dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False),
        description="Detailed booking information"
    )
    status: BookingStatus = Field(
        default=BookingStatus.PENDING,
        sa_column=Column(PG_ENUM(BookingStatus, name="bookingstatus")),
        description="Current booking status"
    )
    
    # Additional fields
    total_amount: Optional[Decimal] = Field(
        default=None,
        ge=0,
        description="Total booking amount"
    )
    currency: Optional[str] = Field(
        default="USD",
        max_length=3,
        description="Currency code"
    )
    confirmation_number: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Booking confirmation number"
    )
    cancellation_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for cancellation if applicable"
    )

    # Relationships
    user: User = Relationship(back_populates="bookings")
    itinerary: Itinerary = Relationship(back_populates="bookings")

    # Validators
    @field_validator('item_id')
    @classmethod
    def validate_item_id(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('Item ID cannot be empty')
        return v.strip()


class Review(BaseModel, table=True):
    __tablename__ = "reviews"
    
    __table_args__ = (
        Index('idx_reviews_user_id', 'user_id'),
        Index('idx_reviews_item', 'item_id', 'item_type'),
        Index('idx_reviews_rating', 'rating'),
        Index('idx_reviews_review_date', 'review_date'),
        CheckConstraint('rating >= 1 AND rating <= 5', name='check_valid_rating'),
    )

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: PyUUID = Field(
        foreign_key="users.id",
        nullable=False,
        description="User who wrote the review"
    )
    item_id: str = Field(
        max_length=100,
        description="ID of the reviewed item"
    )
    item_type: ItemType = Field(
        sa_column=Column(PG_ENUM(ItemType, name="itemtype")),
        description="Type of reviewed item"
    )
    rating: int = Field(
        ge=1,
        le=5,
        description="Rating (1-5 stars)"
    )
    review_text: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Review text content"
    )
    review_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="When the review was written"
    )
    images: Optional[List[str]] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
        description="List of image URLs"
    )
    
    # Additional fields
    helpful_votes: int = Field(
        default=0,
        ge=0,
        description="Number of helpful votes"
    )
    verified_purchase: bool = Field(
        default=False,
        description="Whether this is a verified purchase review"
    )
    language: Optional[str] = Field(
        default="en",
        max_length=10,
        description="Review language code"
    )

    # Relationships
    user: User = Relationship(back_populates="reviews")

    # Validators
    @field_validator('item_id')
    @classmethod
    def validate_item_id(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError('Item ID cannot be empty')
        return v.strip()

    @field_validator('review_text')
    @classmethod
    def validate_review_text(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) == 0:
            return None
        return v

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSON, ENUM as PG_ENUM
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

# Models
class User(SQLModel, table=True):
    __tablename__ = "users"

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(index=True, unique=True, nullable=False)
    email: str = Field(index=True, unique=True, nullable=False)
    password_hash: str = Field(nullable=False)
    preferences: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    travel_history: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    itineraries: List["Itinerary"] = Relationship(back_populates="user")
    bookings: List["Booking"] = Relationship(back_populates="user")
    reviews: List["Review"] = Relationship(back_populates="user")


class Itinerary(SQLModel, table=True):
    __tablename__ = "itineraries"

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    start_date: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    end_date:   datetime = Field(sa_column=Column(DateTime(timezone=True)))
    status: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    data: dict = Field(
        sa_column=Column(JSON, nullable=False),
        description="Raw parsed parameters (locations, dates, interests, budget)",
    )
    user_id: PyUUID = Field(foreign_key="users.id", nullable=False)

    user: User = Relationship(back_populates="itineraries")
    dest_links: List["ItineraryDestination"] = Relationship(back_populates="itinerary")
    act_links: List["ItineraryActivity"] = Relationship(back_populates="itinerary")
    accom_links: List["ItineraryAccommodation"] = Relationship(back_populates="itinerary")
    trans_links: List["ItineraryTransportation"] = Relationship(back_populates="itinerary")
    bookings: List["Booking"] = Relationship(back_populates="itinerary")


class Destination(SQLModel, table=True):
    __tablename__ = "destinations"

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    images: List[str] = Field(sa_column=Column(JSON, nullable=True))
    rating: Optional[float] = None

    dest_links: List["ItineraryDestination"] = Relationship(back_populates="destination")


class ItineraryDestination(SQLModel, table=True):
    __tablename__ = "itinerary_destinations"

    itinerary_id: PyUUID = Field(foreign_key="itineraries.id", primary_key=True)
    destination_id: PyUUID = Field(foreign_key="destinations.id", primary_key=True)
    order: int

    itinerary: Itinerary   = Relationship(back_populates="dest_links")
    destination: Destination = Relationship(back_populates="dest_links")


class Activity(SQLModel, table=True):
    __tablename__ = "activities"

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    images: List[str] = Field(sa_column=Column(JSON, nullable=True))
    price: Optional[float] = None
    opening_hours: Optional[str] = Field(default=None)
    rating: Optional[float] = None

    act_links: List["ItineraryActivity"] = Relationship(back_populates="activity")


class ItineraryActivity(SQLModel, table=True):
    __tablename__ = "itinerary_activities"

    itinerary_id: PyUUID = Field(foreign_key="itineraries.id", primary_key=True)
    activity_id:  PyUUID = Field(foreign_key="activities.id", primary_key=True)
    order: int

    itinerary: Itinerary = Relationship(back_populates="act_links")
    activity: Activity   = Relationship(back_populates="act_links")


class Accommodation(SQLModel, table=True):
    __tablename__ = "accommodations"

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    images: List[str] = Field(sa_column=Column(JSON, nullable=True))
    price: Optional[float] = None
    rating: Optional[float] = None
    amenities: List[str] = Field(sa_column=Column(JSON, nullable=True))

    accom_links: List["ItineraryAccommodation"] = Relationship(back_populates="accommodation")


class ItineraryAccommodation(SQLModel, table=True):
    __tablename__ = "itinerary_accommodations"

    itinerary_id:     PyUUID = Field(foreign_key="itineraries.id",      primary_key=True)
    accommodation_id: PyUUID = Field(foreign_key="accommodations.id",   primary_key=True)
    order: int

    itinerary:     Itinerary     = Relationship(back_populates="accom_links")
    accommodation: Accommodation = Relationship(back_populates="accom_links")


class Transportation(SQLModel, table=True):
    __tablename__ = "transportations"

    id: PyUUID = Field(default_factory=uuid.uuid4, primary_key=True)
    type: str
    departure_lat: float
    departure_long: float
    arrival_lat: float
    arrival_long: float
    departure_time: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    arrival_time:   datetime = Field(sa_column=Column(DateTime(timezone=True)))
    price: Optional[float] = None

    trans_links: List["ItineraryTransportation"] = Relationship(back_populates="transportation")


class ItineraryTransportation(SQLModel, table=True):
    __tablename__ = "itinerary_transportations"

    itinerary_id:     PyUUID = Field(foreign_key="itineraries.id",       primary_key=True)
    transportation_id: PyUUID = Field(foreign_key="transportations.id",  primary_key=True)
    order: int

    itinerary:      Itinerary       = Relationship(back_populates="trans_links")
    transportation: Transportation = Relationship(back_populates="trans_links")


class Booking(SQLModel, table=True):
    __tablename__ = "bookings"

    id:           PyUUID              = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id:      PyUUID              = Field(foreign_key="users.id",        nullable=False)
    itinerary_id: PyUUID              = Field(foreign_key="itineraries.id",  nullable=False)
    item_id:      str
    item_type:    BookingItemType     = Field(sa_column=Column(PG_ENUM(BookingItemType, name="bookingitemtype")))
    booking_date: datetime            = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    booking_details: dict             = Field(sa_column=Column(JSON, nullable=False))
    status:        str

    user:      User      = Relationship(back_populates="bookings")
    itinerary: Itinerary = Relationship(back_populates="bookings")


class Review(SQLModel, table=True):
    __tablename__ = "reviews"

    id:           PyUUID          = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id:      PyUUID          = Field(foreign_key="users.id",       nullable=False)
    item_id:      str
    item_type:    ItemType        = Field(sa_column=Column(PG_ENUM(ItemType, name="itemtype")))
    rating:       int
    review_text:  Optional[str]   = None
    review_date:  datetime        = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    images:       List[str]       = Field(default_factory=list, sa_column=Column(JSON, nullable=True))

    user: User = Relationship(back_populates="reviews")

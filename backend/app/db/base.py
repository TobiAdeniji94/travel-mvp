"""
Database base configuration
Imports all models to ensure they're registered with SQLModel metadata
"""

from sqlmodel import SQLModel

# Import all models so they're registered with SQLModel.metadata
from app.db.models import (
    User,
    Destination,
    Activity,
    Accommodation,
    Transportation,
    Itinerary,
    ItineraryDestination,
    ItineraryActivity,
    ItineraryAccommodation,
    ItineraryTransportation,
    Booking,
    Review,
)

# Export Base for use in init_db.py and migrations
Base = SQLModel.metadata

__all__ = ["Base", "SQLModel"]

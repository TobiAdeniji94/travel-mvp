# backend/app/db/models.py

import uuid
from datetime import datetime

from sqlalchemy import Column, String, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    preferences = Column(JSON, nullable=True)
    travel_history = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # relationships (assuming you’ll define Itinerary, Booking, Review elsewhere)
    itineraries = relationship("Itinerary", back_populates="user")
    bookings    = relationship("Booking",   back_populates="user")
    reviews     = relationship("Review",    back_populates="user")

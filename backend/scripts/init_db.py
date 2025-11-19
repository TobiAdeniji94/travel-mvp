#!/usr/bin/env python3
"""
Initialize database tables without alembic
Creates all tables defined in SQLAlchemy models
"""

import sys
import os
from pathlib import Path

# Ensure project root (/app) is on sys.path for "app.*" imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text
from sqlmodel import SQLModel
import logging

# Import all models to register them with SQLModel.metadata
from app.db.models import (
    User, Destination, Activity, Accommodation, Transportation,
    Itinerary, ItineraryItem, Booking, BookingItem, Review, SharedItinerary
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _normalize_db_url(db_url: str) -> str:
    if db_url.startswith("postgres://"):
        return "postgresql://" + db_url[len("postgres://"):]
    return db_url


def init_database():
    """Initialize database tables"""
    db_url = os.getenv('DB_URL')
    if not db_url:
        logger.error("DB_URL environment variable not set")
        sys.exit(1)
    db_url = _normalize_db_url(db_url)
    
    try:
        logger.info("Connecting to database...")
        engine = create_engine(db_url, echo=False)
        
        logger.info("Creating all tables...")
        SQLModel.metadata.create_all(bind=engine)
        
        logger.info("✅ Database tables created successfully")
        
        # Verify tables were created
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result]
            logger.info(f"Created tables: {', '.join(tables)}")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()

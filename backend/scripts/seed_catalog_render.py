#!/usr/bin/env python3
"""
Render-optimized catalog seeding script
Idempotent - safe to run multiple times without duplicating data
"""

import sys
import os
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import csv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_already_seeded(engine) -> bool:
    """Check if database is already seeded"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM destinations"))
            count = result.scalar()
            if count > 0:
                logger.info(f"✅ Database already seeded ({count} destinations found)")
                return True
            return False
    except Exception as e:
        logger.warning(f"Could not check if seeded: {e}")
        return False

def seed_destinations(session: Session, csv_path: str):
    """Seed destinations from CSV (idempotent)"""
    if not os.path.exists(csv_path):
        logger.warning(f"Destinations CSV not found: {csv_path}")
        return
    
    logger.info(f"Seeding destinations from {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            # Check if destination already exists
            existing = session.execute(
                text("SELECT id FROM destinations WHERE name = :name LIMIT 1"),
                {"name": row.get('name')}
            ).first()
            
            if existing:
                continue
            
            # Insert new destination
            session.execute(
                text("""
                    INSERT INTO destinations (id, name, description, latitude, longitude, 
                                             country, region, timezone, climate_info, 
                                             avg_rating, created_at, updated_at)
                    VALUES (gen_random_uuid(), :name, :description, :lat, :lon, 
                            :country, :region, :timezone, :climate, :rating, 
                            NOW(), NOW())
                """),
                {
                    "name": row.get('name', 'Unknown'),
                    "description": row.get('description', ''),
                    "lat": float(row.get('latitude', 0)),
                    "lon": float(row.get('longitude', 0)),
                    "country": row.get('country', ''),
                    "region": row.get('region', ''),
                    "timezone": row.get('timezone', 'UTC'),
                    "climate": row.get('climate_info', '{}'),
                    "rating": float(row.get('avg_rating', 4.0))
                }
            )
            count += 1
        
        session.commit()
        logger.info(f"✅ Seeded {count} destinations")

def seed_activities(session: Session, csv_path: str):
    """Seed activities from CSV (idempotent)"""
    if not os.path.exists(csv_path):
        logger.warning(f"Activities CSV not found: {csv_path}")
        return
    
    logger.info(f"Seeding activities from {csv_path}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            # Check if activity already exists
            existing = session.execute(
                text("SELECT id FROM activities WHERE name = :name LIMIT 1"),
                {"name": row.get('name')}
            ).first()
            
            if existing:
                continue
            
            # Insert new activity
            session.execute(
                text("""
                    INSERT INTO activities (id, name, description, category, latitude, longitude,
                                          opening_hours, price_range, avg_rating, duration_minutes,
                                          created_at, updated_at)
                    VALUES (gen_random_uuid(), :name, :description, :category, :lat, :lon,
                            :hours, :price, :rating, :duration, NOW(), NOW())
                """),
                {
                    "name": row.get('name', 'Unknown'),
                    "description": row.get('description', ''),
                    "category": row.get('category', 'general'),
                    "lat": float(row.get('latitude', 0)),
                    "lon": float(row.get('longitude', 0)),
                    "hours": row.get('opening_hours', '09:00-17:00'),
                    "price": float(row.get('price_range', 50)),
                    "rating": float(row.get('avg_rating', 4.0)),
                    "duration": int(row.get('duration_minutes', 120))
                }
            )
            count += 1
        
        session.commit()
        logger.info(f"✅ Seeded {count} activities")

def main():
    """Main seeding function"""
    logger.info("=" * 60)
    logger.info("Starting database seeding (Render-optimized)")
    logger.info("=" * 60)
    
    # Get database URL from environment
    db_url = os.getenv('DB_URL')
    if not db_url:
        logger.error("❌ DB_URL environment variable not set")
        sys.exit(1)
    
    try:
        # Create engine
        engine = create_engine(db_url, echo=False)
        
        # Check if already seeded
        if check_already_seeded(engine):
            logger.info("Skipping seeding - database already populated")
            return
        
        # Create session
        with Session(engine) as session:
            # Seed destinations
            dest_csv = os.path.join(os.path.dirname(__file__), 'destination.csv')
            seed_destinations(session, dest_csv)
            
            # Seed activities
            act_csv = os.path.join(os.path.dirname(__file__), 'activities.csv')
            seed_activities(session, act_csv)
            
            # Add more seeding functions as needed
            # seed_accommodations(session, acc_csv)
            # seed_transportation(session, trans_csv)
        
        logger.info("=" * 60)
        logger.info("✅ Database seeding completed successfully")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Seeding failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

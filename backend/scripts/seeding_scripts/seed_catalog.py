#!/usr/bin/env python3
"""
Database Seeding Script for Travel Catalog
Enhanced version with better error handling, logging, and monitoring
"""

import asyncio
import csv
import json
import logging
import time
from pathlib import Path
from datetime import datetime
from uuid import UUID
from typing import Dict, List, Any, Optional, Tuple
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlmodel import SQLModel
from sqlalchemy.exc import SQLAlchemyError
from app.db.session import init_db, get_engine, get_session
from app.db.models import (
    Destination,
    Activity,
    Accommodation,
    Transportation,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('seed_catalog.log')
    ]
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent

@dataclass
class SeedingConfig:
    """Configuration for database seeding"""
    skip_duplicates: bool = True
    validate_coordinates: bool = True
    validate_required_fields: bool = True
    batch_size: int = 100
    max_errors: int = 50
    coordinate_precision: int = 6

@asynccontextmanager
async def performance_timer(operation: str):
    """Context manager for timing operations"""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        logger.info(f"{operation} completed in {duration:.2f}s")

class DataValidator:
    """Enhanced data validation utility"""
    
    def __init__(self, config: SeedingConfig):
        self.config = config
        self.stats = {
            "total_processed": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "duplicate_records": 0,
            "coordinate_errors": 0,
            "parsing_errors": 0
        }
    
    def validate_coordinates(self, lat: float, lon: float, row_id: str) -> bool:
        """Validate coordinate values"""
        if not self.config.validate_coordinates:
            return True
        
        # Check latitude range (-90 to 90)
        if not -90 <= lat <= 90:
            logger.warning(f"Invalid latitude {lat} for row {row_id}")
            self.stats["coordinate_errors"] += 1
            return False
        
        # Check longitude range (-180 to 180)
        if not -180 <= lon <= 180:
            logger.warning(f"Invalid longitude {lon} for row {row_id}")
            self.stats["coordinate_errors"] += 1
            return False
        
        return True
    
    def validate_required_fields(self, row: Dict[str, str], required_fields: List[str], row_id: str) -> bool:
        """Validate that required fields are present and non-empty"""
        if not self.config.validate_required_fields:
            return True
        
        for field in required_fields:
            if not row.get(field) or not row.get(field).strip():
                logger.warning(f"Missing required field '{field}' for row {row_id}")
                self.stats["invalid_records"] += 1
                return False
        
        return True
    
    def parse_float(self, value: str, field: str, row_id: str) -> Optional[float]:
        """Enhanced float parsing with validation"""
        val = (value or "").strip()
        if not val:
            logger.debug(f"Empty {field} for row {row_id}")
            return None
        
        try:
            result = float(val)
            # Round to specified precision
            return round(result, self.config.coordinate_precision)
        except ValueError:
            logger.warning(f"Invalid {field} '{value}' for row {row_id}")
            self.stats["parsing_errors"] += 1
            return None
    
    def parse_json_array(self, value: str, field: str, row_id: str) -> List[str]:
        """Parse JSON array or comma-separated string"""
        val = (value or "").strip()
        if not val:
            return []
        
        try:
            # Try JSON array first
            if val.startswith("[") and val.endswith("]"):
                return json.loads(val)
            # Fall back to comma-separated
            return [item.strip() for item in val.split(",") if item.strip()]
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Invalid {field} format '{value}' for row {row_id}: {e}")
            self.stats["parsing_errors"] += 1
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get validation statistics"""
        return self.stats.copy()

class CatalogSeeder:
    """Enhanced catalog seeder with monitoring and validation"""
    
    def __init__(self, config: SeedingConfig):
        self.config = config
        self.validator = DataValidator(config)
        self.seeding_stats = {
            "destinations": {"processed": 0, "added": 0, "errors": 0},
            "activities": {"processed": 0, "added": 0, "errors": 0},
            "accommodations": {"processed": 0, "added": 0, "errors": 0},
            "transportations": {"processed": 0, "added": 0, "errors": 0}
        }
    
    async def validate_environment(self) -> bool:
        """Validate that the seeding environment is ready"""
        logger.info("🔍 Validating seeding environment...")
        
        # Check if CSV files exist
        required_files = ["destination.csv", "activities.csv", "accomodation.csv", "transport.csv"]
        missing_files = []
        
        for filename in required_files:
            file_path = BASE_DIR / filename
            if not file_path.exists():
                missing_files.append(filename)
            else:
                file_size = file_path.stat().st_size
                logger.info(f"  ✅ {filename} ({file_size} bytes)")
        
        if missing_files:
            logger.error(f"❌ Missing required files: {missing_files}")
            return False
        
        logger.info("✅ Environment validation passed")
        return True
    
    async def seed_destinations(self, session) -> bool:
        """Seed destinations with enhanced error handling"""
        logger.info("🌍 Seeding destinations...")
        
        try:
            dest_file = BASE_DIR / "destination.csv"
            with open(dest_file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    self.seeding_stats["destinations"]["processed"] += 1
                    row_id = row.get("id", "<no-id>")
                    
                    try:
                        # Validate required fields
                        if not self.validator.validate_required_fields(
                            row, ["id", "name", "latitude", "longitude"], row_id
                        ):
                            continue
                        
                        # Parse coordinates
                        lat = self.validator.parse_float(row.get("latitude"), "latitude", row_id)
                        lon = self.validator.parse_float(row.get("longitude"), "longitude", row_id)
                        
                        if lat is None or lon is None:
                            continue
                        
                        # Validate coordinates
                        if not self.validator.validate_coordinates(lat, lon, row_id):
                            continue
                        
                        # Check for duplicates
                        dest_id = UUID(row_id)
                        exists = await session.get(Destination, dest_id)
                        if exists:
                            self.seeding_stats["destinations"]["errors"] += 1
                            logger.debug(f"Destination {row.get('name')} already exists")
                            continue
                        
                        # Parse additional fields
                        images = self.validator.parse_json_array(row.get("images", ""), "images", row_id)
                        rating = self.validator.parse_float(row.get("rating"), "rating", row_id)
                        
                        # Parse enhanced fields
                        climate_data = None
                        if row.get("climate_data"):
                            try:
                                climate_data = json.loads(row.get("climate_data"))
                            except:
                                climate_data = None
                        
                        popularity_score = self.validator.parse_float(row.get("popularity_score"), "popularity_score", row_id)
                        
                        # Create destination with enhanced fields
                        destination = Destination(
                            id=dest_id,
                            name=row.get("name") or "",
                            description=row.get("description") or None,
                            latitude=lat,
                            longitude=lon,
                            images=images,
                            rating=rating,
                            country=row.get("country") or None,
                            region=row.get("region") or None,
                            timezone=row.get("timezone") or None,
                            climate_data=climate_data,
                            popularity_score=popularity_score,
                        )
                        
                        session.add(destination)
                        self.seeding_stats["destinations"]["added"] += 1
                        logger.debug(f"Added destination: {row.get('name')}")
                        
                    except Exception as e:
                        self.seeding_stats["destinations"]["errors"] += 1
                        logger.error(f"Error processing destination row {row_id}: {e}")
                        continue
            
            return True
            
        except Exception as e:
            logger.error(f"Error seeding destinations: {e}")
            return False
    
    async def seed_activities(self, session) -> bool:
        """Seed activities with enhanced error handling"""
        logger.info("🎯 Seeding activities...")
        
        try:
            act_file = BASE_DIR / "activities.csv"
            with open(act_file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    self.seeding_stats["activities"]["processed"] += 1
                    row_id = row.get("id", "<no-id>")
                    
                    try:
                        # Validate required fields
                        if not self.validator.validate_required_fields(
                            row, ["id", "name", "latitude", "longitude"], row_id
                        ):
                            continue
                        
                        # Parse coordinates
                        lat = self.validator.parse_float(row.get("latitude"), "latitude", row_id)
                        lon = self.validator.parse_float(row.get("longitude"), "longitude", row_id)
                        
                        if lat is None or lon is None:
                            continue
                        
                        # Validate coordinates
                        if not self.validator.validate_coordinates(lat, lon, row_id):
                            continue
                        
                        # Check for duplicates
                        act_id = UUID(row_id)
                        exists = await session.get(Activity, act_id)
                        if exists:
                            self.seeding_stats["activities"]["errors"] += 1
                            logger.debug(f"Activity {row.get('name')} already exists")
                            continue
                        
                        # Parse additional fields
                        images = self.validator.parse_json_array(row.get("images", ""), "images", row_id)
                        price = self.validator.parse_float(row.get("price"), "price", row_id)
                        rating = self.validator.parse_float(row.get("rating"), "rating", row_id)
                        
                        # Parse enhanced fields
                        duration_minutes = None
                        if row.get("duration_minutes"):
                            try:
                                duration_minutes = int(row.get("duration_minutes"))
                            except:
                                duration_minutes = None
                        
                        # Create activity with enhanced fields
                        activity = Activity(
                            id=act_id,
                            name=row.get("name") or "",
                            description=row.get("description") or None,
                            latitude=lat,
                            longitude=lon,
                            images=images,
                            price=price,
                            opening_hours=row.get("opening_hours") or None,
                            rating=rating,
                            type=row.get("type") or None,
                            duration_minutes=duration_minutes,
                            difficulty_level=row.get("difficulty_level") or None,
                            age_restrictions=row.get("age_restrictions") or None,
                            accessibility_info=row.get("accessibility_info") or None,
                        )
                        
                        session.add(activity)
                        self.seeding_stats["activities"]["added"] += 1
                        logger.debug(f"Added activity: {row.get('name')}")
                        
                    except Exception as e:
                        self.seeding_stats["activities"]["errors"] += 1
                        logger.error(f"Error processing activity row {row_id}: {e}")
                        continue
            
            return True
            
        except Exception as e:
            logger.error(f"Error seeding activities: {e}")
            return False
    
    async def seed_accommodations(self, session) -> bool:
        """Seed accommodations with enhanced error handling"""
        logger.info("🏨 Seeding accommodations...")
        
        try:
            acc_file = BASE_DIR / "accomodation.csv"
            with open(acc_file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    self.seeding_stats["accommodations"]["processed"] += 1
                    row_id = row.get("id", "<no-id>")
                    
                    try:
                        # Validate required fields
                        if not self.validator.validate_required_fields(
                            row, ["id", "name", "latitude", "longitude"], row_id
                        ):
                            continue
                        
                        # Parse coordinates
                        lat = self.validator.parse_float(row.get("latitude"), "latitude", row_id)
                        lon = self.validator.parse_float(row.get("longitude"), "longitude", row_id)
                        
                        if lat is None or lon is None:
                            continue
                        
                        # Validate coordinates
                        if not self.validator.validate_coordinates(lat, lon, row_id):
                            continue
                        
                        # Check for duplicates
                        acc_id = UUID(row_id)
                        exists = await session.get(Accommodation, acc_id)
                        if exists:
                            self.seeding_stats["accommodations"]["errors"] += 1
                            logger.debug(f"Accommodation {row.get('name')} already exists")
                            continue
                        
                        # Parse additional fields
                        images = self.validator.parse_json_array(row.get("images", ""), "images", row_id)
                        amenities = self.validator.parse_json_array(row.get("amenities", ""), "amenities", row_id)
                        price = self.validator.parse_float(row.get("price"), "price", row_id)
                        rating = self.validator.parse_float(row.get("rating"), "rating", row_id)
                        
                        # Parse enhanced fields
                        star_rating = None
                        if row.get("star_rating"):
                            try:
                                star_rating = int(row.get("star_rating"))
                            except:
                                star_rating = None
                        
                        capacity = None
                        if row.get("capacity"):
                            try:
                                capacity = int(row.get("capacity"))
                            except:
                                capacity = None
                        
                        contact_info = None
                        if row.get("contact_info"):
                            try:
                                contact_info = json.loads(row.get("contact_info"))
                            except:
                                contact_info = None
                        
                        # Create accommodation with enhanced fields
                        accommodation = Accommodation(
                            id=acc_id,
                            name=row.get("name") or "",
                            description=row.get("description") or None,
                            latitude=lat,
                            longitude=lon,
                            images=images,
                            price=price,
                            rating=rating,
                            amenities=amenities,
                            type=row.get("type") or None,
                            star_rating=star_rating,
                            capacity=capacity,
                            check_in_time=row.get("check_in_time") or None,
                            check_out_time=row.get("check_out_time") or None,
                            contact_info=contact_info,
                        )
                        
                        session.add(accommodation)
                        self.seeding_stats["accommodations"]["added"] += 1
                        logger.debug(f"Added accommodation: {row.get('name')}")
                        
                    except Exception as e:
                        self.seeding_stats["accommodations"]["errors"] += 1
                        logger.error(f"Error processing accommodation row {row_id}: {e}")
                        continue
            
            return True
            
        except Exception as e:
            logger.error(f"Error seeding accommodations: {e}")
            return False
    
    async def seed_transportations(self, session) -> bool:
        """Seed transportations with enhanced error handling"""
        logger.info("🚗 Seeding transportations...")
        
        try:
            trans_file = BASE_DIR / "transport.csv"
            with open(trans_file, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    self.seeding_stats["transportations"]["processed"] += 1
                    row_id = row.get("id", "<no-id>")
                    
                    try:
                        # Validate required fields
                        if not self.validator.validate_required_fields(
                            row, ["id", "type", "departure_lat", "departure_long", 
                                  "arrival_lat", "arrival_long", "departure_time", "arrival_time"], row_id
                        ):
                            continue
                        
                        # Parse coordinates
                        dep_lat = self.validator.parse_float(row.get("departure_lat"), "departure_lat", row_id)
                        dep_lon = self.validator.parse_float(row.get("departure_long"), "departure_long", row_id)
                        arr_lat = self.validator.parse_float(row.get("arrival_lat"), "arrival_lat", row_id)
                        arr_lon = self.validator.parse_float(row.get("arrival_long"), "arrival_long", row_id)
                        
                        if None in (dep_lat, dep_lon, arr_lat, arr_lon):
                            continue
                        
                        # Validate coordinates
                        if not all([
                            self.validator.validate_coordinates(dep_lat, dep_lon, row_id),
                            self.validator.validate_coordinates(arr_lat, arr_lon, row_id)
                        ]):
                            continue
                        
                        # Check for duplicates
                        tr_id = UUID(row_id)
                        exists = await session.get(Transportation, tr_id)
                        if exists:
                            self.seeding_stats["transportations"]["errors"] += 1
                            logger.debug(f"Transportation {row_id} already exists")
                            continue
                        
                        # Parse datetime fields
                        try:
                            departure_time = datetime.fromisoformat(row["departure_time"])
                            arrival_time = datetime.fromisoformat(row["arrival_time"])
                        except ValueError as e:
                            logger.warning(f"Invalid datetime format for row {row_id}: {e}")
                            self.seeding_stats["transportations"]["errors"] += 1
                            continue
                        
                        # Parse price
                        price = self.validator.parse_float(row.get("price"), "price", row_id)
                        
                        # Parse enhanced fields
                        duration_minutes = None
                        if row.get("duration_minutes"):
                            try:
                                duration_minutes = int(row.get("duration_minutes"))
                            except:
                                duration_minutes = None
                        
                        distance_km = self.validator.parse_float(row.get("distance_km"), "distance_km", row_id)
                        
                        capacity = None
                        if row.get("capacity"):
                            try:
                                capacity = int(row.get("capacity"))
                            except:
                                capacity = None
                        
                        # Create transportation with enhanced fields
                        transportation = Transportation(
                            id=tr_id,
                            type=row.get("type") or "",
                            departure_lat=dep_lat,
                            departure_long=dep_lon,
                            arrival_lat=arr_lat,
                            arrival_long=arr_lon,
                            departure_time=departure_time,
                            arrival_time=arrival_time,
                            price=price,
                            provider=row.get("provider") or None,
                            booking_reference=row.get("booking_reference") or None,
                            duration_minutes=duration_minutes,
                            distance_km=distance_km,
                            capacity=capacity,
                        )
                        
                        session.add(transportation)
                        self.seeding_stats["transportations"]["added"] += 1
                        logger.debug(f"Added transportation: {row_id}")
                        
                    except Exception as e:
                        self.seeding_stats["transportations"]["errors"] += 1
                        logger.error(f"Error processing transportation row {row_id}: {e}")
                        continue
            
            return True
            
        except Exception as e:
            logger.error(f"Error seeding transportations: {e}")
            return False
    
    def print_summary(self):
        """Print comprehensive seeding summary"""
        logger.info(f"\n{'='*80}")
        logger.info("📊 SEEDING SUMMARY")
        logger.info(f"{'='*80}")
        
        total_processed = 0
        total_added = 0
        total_errors = 0
        
        for category, stats in self.seeding_stats.items():
            logger.info(f"\n📋 {category.upper()}:")
            logger.info(f"  Processed: {stats['processed']}")
            logger.info(f"  Added: {stats['added']}")
            logger.info(f"  Errors: {stats['errors']}")
            
            total_processed += stats['processed']
            total_added += stats['added']
            total_errors += stats['errors']
        
        logger.info(f"\n📊 OVERALL STATISTICS:")
        logger.info(f"  Total processed: {total_processed}")
        logger.info(f"  Total added: {total_added}")
        logger.info(f"  Total errors: {total_errors}")
        logger.info(f"  Success rate: {(total_added / total_processed * 100):.1f}%" if total_processed > 0 else "N/A")
        
        # Print validation stats
        validation_stats = self.validator.get_stats()
        logger.info(f"\n🔍 VALIDATION STATISTICS:")
        for key, value in validation_stats.items():
            logger.info(f"  {key}: {value}")

async def seed():
    """Enhanced main seeding function"""
    logger.info("🚀 Starting database seeding process")
    
    try:
        await init_db()
        engine = get_engine()
        if engine is None:
            logger.error("Database engine unavailable after init_db()")
            return False
        
        # Configuration
        config = SeedingConfig()
        seeder = CatalogSeeder(config)
        
        # Validate environment
        if not await seeder.validate_environment():
            logger.error("❌ Environment validation failed")
            return False
        
        # Ensure tables exist
        async with performance_timer("database_setup"):
            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)
        
        # Seed all categories
        async with get_session() as session:
            try:
                # Seed destinations
                async with performance_timer("destinations_seeding"):
                    success = await seeder.seed_destinations(session)
                    if not success:
                        logger.error("❌ Destination seeding failed")
                
                # Seed activities
                async with performance_timer("activities_seeding"):
                    success = await seeder.seed_activities(session)
                    if not success:
                        logger.error("❌ Activity seeding failed")
                
                # Seed accommodations
                async with performance_timer("accommodations_seeding"):
                    success = await seeder.seed_accommodations(session)
                    if not success:
                        logger.error("❌ Accommodation seeding failed")
                
                # Seed transportations
                async with performance_timer("transportations_seeding"):
                    success = await seeder.seed_transportations(session)
                    if not success:
                        logger.error("❌ Transportation seeding failed")
                
                # Commit all changes
                await session.commit()
                logger.info("✅ Database changes committed successfully")
                
                # Print summary
                seeder.print_summary()
                
                return True
                
            except SQLAlchemyError as e:
                await session.rollback()
                logger.error(f"❌ Database error during seeding: {e}")
                return False
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Unexpected error during seeding: {e}")
                return False
        
    except Exception as e:
        logger.error(f"❌ Seeding process failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(seed())
    exit(0 if success else 1)


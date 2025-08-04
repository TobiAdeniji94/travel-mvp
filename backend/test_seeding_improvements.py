"""
Test file for database seeding improvements
Demonstrates and tests the enhanced seeding features
"""

import pytest
import asyncio
import tempfile
import csv
from pathlib import Path
from unittest.mock import AsyncMock, patch
from datetime import datetime

# Import seeding functions (these would be available after the improvements)
try:
    from scripts.seed_catalog import (
        SeedingConfig, DataValidator, CatalogSeeder, performance_timer
    )
    SEEDING_IMPROVEMENTS_AVAILABLE = True
except ImportError:
    SEEDING_IMPROVEMENTS_AVAILABLE = False

def test_seeding_config():
    """Test seeding configuration class"""
    if not SEEDING_IMPROVEMENTS_AVAILABLE:
        pytest.skip("Seeding improvements not available")
    
    print("\n=== Testing Seeding Configuration ===")
    
    config = SeedingConfig()
    print(f"Config: skip_duplicates={config.skip_duplicates}")
    print(f"Config: validate_coordinates={config.validate_coordinates}")
    print(f"Config: batch_size={config.batch_size}")
    
    assert config.skip_duplicates is True
    assert config.validate_coordinates is True
    assert config.batch_size == 100
    assert config.max_errors == 50
    assert config.coordinate_precision == 6

def test_data_validator():
    """Test enhanced data validation"""
    if not SEEDING_IMPROVEMENTS_AVAILABLE:
        pytest.skip("Seeding improvements not available")
    
    print("\n=== Testing Data Validator ===")
    
    config = SeedingConfig()
    validator = DataValidator(config)
    
    # Test coordinate validation
    print("Testing coordinate validation...")
    assert validator.validate_coordinates(40.7128, -74.0060, "test") is True  # Valid NYC coordinates
    assert validator.validate_coordinates(91.0, 0.0, "test") is False  # Invalid latitude
    assert validator.validate_coordinates(0.0, 181.0, "test") is False  # Invalid longitude
    
    # Test required fields validation
    print("Testing required fields validation...")
    valid_row = {"id": "123", "name": "Test", "latitude": "40.7128", "longitude": "-74.0060"}
    invalid_row = {"id": "123", "name": "", "latitude": "40.7128", "longitude": "-74.0060"}
    
    assert validator.validate_required_fields(valid_row, ["id", "name"], "test") is True
    assert validator.validate_required_fields(invalid_row, ["id", "name"], "test") is False
    
    # Test float parsing
    print("Testing float parsing...")
    assert validator.parse_float("40.7128", "latitude", "test") == 40.7128
    assert validator.parse_float("", "latitude", "test") is None
    assert validator.parse_float("invalid", "latitude", "test") is None
    
    # Test JSON array parsing
    print("Testing JSON array parsing...")
    assert validator.parse_json_array('["img1.jpg", "img2.jpg"]', "images", "test") == ["img1.jpg", "img2.jpg"]
    assert validator.parse_json_array("img1.jpg,img2.jpg", "images", "test") == ["img1.jpg", "img2.jpg"]
    assert validator.parse_json_array("", "images", "test") == []
    
    # Check statistics
    stats = validator.get_stats()
    print(f"Validation stats: {stats}")
    assert "coordinate_errors" in stats
    assert "parsing_errors" in stats

def test_catalog_seeder_structure():
    """Test catalog seeder class structure"""
    if not SEEDING_IMPROVEMENTS_AVAILABLE:
        pytest.skip("Seeding improvements not available")
    
    print("\n=== Testing Catalog Seeder Structure ===")
    
    config = SeedingConfig()
    seeder = CatalogSeeder(config)
    
    print(f"Seeder created: {type(seeder)}")
    assert hasattr(seeder, 'validator')
    assert hasattr(seeder, 'seeding_stats')
    assert hasattr(seeder, 'validate_environment')
    assert hasattr(seeder, 'seed_destinations')
    assert hasattr(seeder, 'seed_activities')
    assert hasattr(seeder, 'seed_accommodations')
    assert hasattr(seeder, 'seed_transportations')
    assert hasattr(seeder, 'print_summary')
    
    # Check seeding stats structure
    print(f"Seeding stats: {seeder.seeding_stats}")
    assert "destinations" in seeder.seeding_stats
    assert "activities" in seeder.seeding_stats
    assert "accommodations" in seeder.seeding_stats
    assert "transportations" in seeder.seeding_stats

def test_performance_timer():
    """Test performance timer context manager"""
    if not SEEDING_IMPROVEMENTS_AVAILABLE:
        pytest.skip("Seeding improvements not available")
    
    print("\n=== Testing Performance Timer ===")
    
    async def test_timer():
        async with performance_timer("test_operation"):
            await asyncio.sleep(0.1)  # Simulate work
    
    # This should run without errors
    asyncio.run(test_timer())
    print("✅ Performance timer works correctly")

def test_environment_validation():
    """Test environment validation logic"""
    print("\n=== Testing Environment Validation ===")
    
    # Test with non-existent files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a mock seeder with temp directory
        config = SeedingConfig()
        seeder = CatalogSeeder(config)
        
        # Mock the BASE_DIR to point to temp directory
        with patch('scripts.seed_catalog.BASE_DIR', temp_path):
            # Should fail because no CSV files exist
            result = asyncio.run(seeder.validate_environment())
            print(f"Environment validation (no files): {result}")
            assert result is False
        
        # Create some test CSV files
        test_files = ["destination.csv", "activities.csv", "accomodation.csv", "transport.csv"]
        for filename in test_files:
            (temp_path / filename).write_text("id,name\n1,Test")
        
        # Should pass now
        with patch('scripts.seed_catalog.BASE_DIR', temp_path):
            result = asyncio.run(seeder.validate_environment())
            print(f"Environment validation (with files): {result}")
            assert result is True

def test_csv_data_handling():
    """Test CSV data handling improvements"""
    print("\n=== Testing CSV Data Handling ===")
    
    # Create test CSV data
    test_data = [
        {"id": "123", "name": "Test Destination", "latitude": "40.7128", "longitude": "-74.0060", "rating": "4.5"},
        {"id": "124", "name": "Invalid Coords", "latitude": "91.0", "longitude": "181.0", "rating": "3.0"},
        {"id": "125", "name": "Missing Fields", "latitude": "", "longitude": "", "rating": "2.0"},
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "latitude", "longitude", "rating"])
        writer.writeheader()
        writer.writerows(test_data)
        csv_file = f.name
    
    print(f"Created test CSV file: {csv_file}")
    
    # Test reading and validation
    config = SeedingConfig()
    validator = DataValidator(config)
    
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_id = row.get("id", "<no-id>")
            
            # Test coordinate validation
            lat = validator.parse_float(row.get("latitude"), "latitude", row_id)
            lon = validator.parse_float(row.get("longitude"), "longitude", row_id)
            
            if lat is not None and lon is not None:
                is_valid = validator.validate_coordinates(lat, lon, row_id)
                print(f"Row {row_id}: lat={lat}, lon={lon}, valid={is_valid}")
            else:
                print(f"Row {row_id}: Invalid coordinates")
    
    # Cleanup
    Path(csv_file).unlink()

def test_error_handling():
    """Test enhanced error handling"""
    print("\n=== Testing Error Handling ===")
    
    config = SeedingConfig()
    validator = DataValidator(config)
    
    # Test various error scenarios
    error_cases = [
        ("invalid_float", "abc", "latitude"),
        ("empty_string", "", "latitude"),
        ("none_value", None, "latitude"),
        ("negative_coords", "-91.0", "latitude"),
        ("out_of_range", "181.0", "longitude"),
    ]
    
    for case_name, value, field in error_cases:
        result = validator.parse_float(str(value) if value is not None else "", field, "test")
        print(f"Case '{case_name}': {value} -> {result}")
        assert result is None or (isinstance(result, float) and -90 <= result <= 90)

def test_statistics_tracking():
    """Test statistics tracking functionality"""
    if not SEEDING_IMPROVEMENTS_AVAILABLE:
        pytest.skip("Seeding improvements not available")
    
    print("\n=== Testing Statistics Tracking ===")
    
    config = SeedingConfig()
    validator = DataValidator(config)
    seeder = CatalogSeeder(config)
    
    # Perform some operations to generate stats
    validator.validate_coordinates(91.0, 0.0, "test")  # Invalid
    validator.validate_coordinates(40.7128, -74.0060, "test")  # Valid
    validator.parse_float("invalid", "latitude", "test")  # Invalid
    validator.parse_float("40.7128", "latitude", "test")  # Valid
    
    # Check validator stats
    validator_stats = validator.get_stats()
    print(f"Validator stats: {validator_stats}")
    assert validator_stats["coordinate_errors"] > 0
    assert validator_stats["parsing_errors"] > 0
    
    # Check seeder stats structure
    seeder_stats = seeder.seeding_stats
    print(f"Seeder stats: {seeder_stats}")
    for category in ["destinations", "activities", "accommodations", "transportations"]:
        assert category in seeder_stats
        assert "processed" in seeder_stats[category]
        assert "added" in seeder_stats[category]
        assert "errors" in seeder_stats[category]

def run_seeding_demo():
    """Run a comprehensive seeding improvements demo"""
    print("\n" + "="*60)
    print("🌱 DATABASE SEEDING IMPROVEMENTS DEMO")
    print("="*60)
    
    # Test all seeding features
    test_seeding_config()
    test_data_validator()
    test_catalog_seeder_structure()
    test_performance_timer()
    test_environment_validation()
    test_csv_data_handling()
    test_error_handling()
    test_statistics_tracking()
    
    print("\n" + "="*60)
    print("✅ All seeding tests completed successfully!")
    print("="*60)
    
    print("\n📋 NEW SEEDING FEATURES SUMMARY:")
    print("• Enhanced data validation with coordinate checking")
    print("• Comprehensive error handling and logging")
    print("• Performance monitoring and timing")
    print("• Environment validation and file checking")
    print("• Statistics tracking and reporting")
    print("• Modular architecture with separate classes")
    print("• Configurable seeding parameters")
    print("• Detailed success/failure reporting")
    print("• CSV data quality validation")
    print("• Duplicate detection and handling")
    
    print("\n🚀 ENHANCED SEEDING SCRIPT:")
    print("• backend/scripts/seed_catalog.py (completely enhanced)")
    
    print("\n📊 NEW FEATURES:")
    print("• Structured logging with file output")
    print("• Performance timing for all operations")
    print("• Data quality metrics and validation")
    print("• Comprehensive error reporting")
    print("• Environment validation")
    print("• Statistics tracking")
    print("• Configurable validation rules")

if __name__ == "__main__":
    run_seeding_demo() 
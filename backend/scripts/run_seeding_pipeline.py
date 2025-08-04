#!/usr/bin/env python3
"""
Comprehensive Database Seeding Pipeline
Orchestrates the entire seeding process with monitoring and validation
"""

import asyncio
import logging
import time
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('seeding_pipeline.log')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class PipelineConfig:
    """Configuration for the seeding pipeline"""
    validate_environment: bool = True
    run_seeding: bool = True
    validate_results: bool = True
    start_api: bool = False
    api_port: int = 8000
    timeout_minutes: int = 30

@asynccontextmanager
async def performance_timer(operation: str):
    """Context manager for timing operations"""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        logger.info(f"{operation} completed in {duration:.2f}s")

class SeedingPipeline:
    """Manages the complete seeding pipeline"""
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.results = {}
        self.scripts_dir = Path(__file__).parent
    
    def validate_environment(self) -> bool:
        """Validate that the seeding environment is ready"""
        logger.info("🔍 Validating seeding environment...")
        
        # Check if seeding script exists
        seed_script = self.scripts_dir / "seed_catalog.py"
        if not seed_script.exists():
            logger.error(f"Seeding script not found: {seed_script}")
            return False
        
        # Check if CSV files exist
        required_files = ["destination.csv", "activities.csv", "accomodation.csv", "transport.csv"]
        missing_files = []
        
        for filename in required_files:
            file_path = self.scripts_dir / filename
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
    
    async def run_seeding(self) -> bool:
        """Run the database seeding process"""
        logger.info("🌱 Running database seeding...")
        
        try:
            async with performance_timer("database_seeding"):
                # Run the seeding script
                process = await asyncio.create_subprocess_exec(
                    sys.executable, str(self.scripts_dir / "seed_catalog.py"),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Wait for completion with timeout
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.config.timeout_minutes * 60
                    )
                except asyncio.TimeoutError:
                    logger.error(f"❌ Seeding timed out after {self.config.timeout_minutes} minutes")
                    process.kill()
                    return False
                
                # Check if seeding was successful
                if process.returncode == 0:
                    logger.info("✅ Database seeding completed successfully")
                    logger.info(f"STDOUT: {stdout.decode()}")
                    if stderr:
                        logger.warning(f"STDERR: {stderr.decode()}")
                    return True
                else:
                    logger.error(f"❌ Seeding failed with return code {process.returncode}")
                    logger.error(f"STDERR: {stderr.decode()}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Seeding failed with exception: {e}")
            return False
    
    async def validate_results(self) -> bool:
        """Validate that seeding was successful by checking database"""
        logger.info("🔍 Validating seeding results...")
        
        try:
            # Import database models and session
            sys.path.append(str(Path(__file__).parent.parent))
            from app.db.session import async_session
            from app.db.models import Destination, Activity, Accommodation, Transportation
            from sqlalchemy import func
            
            async with async_session() as session:
                # Count seeded items
                destinations_count = await session.scalar(func.count(Destination.id))
                activities_count = await session.scalar(func.count(Activity.id))
                accommodations_count = await session.scalar(func.count(Accommodation.id))
                transportations_count = await session.scalar(func.count(Transportation.id))
                
                total_items = (destinations_count or 0) + (activities_count or 0) + \
                             (accommodations_count or 0) + (transportations_count or 0)
                
                logger.info(f"📊 Seeding Results:")
                logger.info(f"  Destinations: {destinations_count or 0}")
                logger.info(f"  Activities: {activities_count or 0}")
                logger.info(f"  Accommodations: {accommodations_count or 0}")
                logger.info(f"  Transportations: {transportations_count or 0}")
                logger.info(f"  Total: {total_items}")
                
                # Check if we have data
                if total_items > 0:
                    logger.info("✅ Seeding validation passed")
                    return True
                else:
                    logger.error("❌ No data found in database after seeding")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error validating seeding results: {e}")
            return False
    
    async def start_api_server(self) -> bool:
        """Start the API server for testing"""
        logger.info("🚀 Starting API server...")
        
        try:
            # Start the API server in background
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "uvicorn", "app.main:app", 
                "--host", "0.0.0.0", "--port", str(self.config.api_port),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait a bit for server to start
            await asyncio.sleep(5)
            
            if process.returncode is None:  # Still running
                logger.info(f"✅ API server started on port {self.config.api_port}")
                return True
            else:
                logger.error("❌ Failed to start API server")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error starting API server: {e}")
            return False
    
    async def test_api_endpoints(self) -> bool:
        """Test API endpoints to verify seeding"""
        logger.info("🧪 Testing API endpoints...")
        
        try:
            import aiohttp
            
            base_url = f"http://localhost:{self.config.api_port}/api/v1"
            
            async with aiohttp.ClientSession() as session:
                # Test health endpoint
                async with session.get(f"{base_url}/health") as response:
                    if response.status == 200:
                        logger.info("✅ Health endpoint working")
                    else:
                        logger.error(f"❌ Health endpoint failed: {response.status}")
                        return False
                
                # Test catalog stats endpoint
                async with session.get(f"{base_url}/catalog/stats") as response:
                    if response.status == 200:
                        stats = await response.json()
                        logger.info(f"✅ Catalog stats: {stats}")
                    else:
                        logger.error(f"❌ Catalog stats endpoint failed: {response.status}")
                        return False
                
                # Test seeding status endpoint
                async with session.get(f"{base_url}/catalog/seeding-status") as response:
                    if response.status == 200:
                        status = await response.json()
                        logger.info(f"✅ Seeding status: {status}")
                    else:
                        logger.error(f"❌ Seeding status endpoint failed: {response.status}")
                        return False
                
                logger.info("✅ All API endpoints working correctly")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error testing API endpoints: {e}")
            return False
    
    async def run_pipeline(self) -> bool:
        """Run the complete seeding pipeline"""
        logger.info("🚀 Starting comprehensive seeding pipeline")
        
        # Step 1: Validate environment
        if self.config.validate_environment:
            if not self.validate_environment():
                logger.error("❌ Environment validation failed")
                return False
        
        # Step 2: Run seeding
        if self.config.run_seeding:
            if not await self.run_seeding():
                logger.error("❌ Database seeding failed")
                return False
        
        # Step 3: Validate results
        if self.config.validate_results:
            if not await self.validate_results():
                logger.error("❌ Seeding validation failed")
                return False
        
        # Step 4: Start API server (optional)
        if self.config.start_api:
            if not await self.start_api_server():
                logger.error("❌ Failed to start API server")
                return False
            
            # Step 5: Test API endpoints
            if not await self.test_api_endpoints():
                logger.error("❌ API endpoint testing failed")
                return False
        
        logger.info("🎉 Seeding pipeline completed successfully!")
        return True
    
    def print_summary(self):
        """Print pipeline summary"""
        logger.info(f"\n{'='*80}")
        logger.info("📊 SEEDING PIPELINE SUMMARY")
        logger.info(f"{'='*80}")
        
        logger.info("✅ Pipeline completed successfully!")
        logger.info("📋 Steps completed:")
        logger.info("  • Environment validation")
        logger.info("  • Database seeding")
        logger.info("  • Results validation")
        if self.config.start_api:
            logger.info("  • API server startup")
            logger.info("  • API endpoint testing")
        
        logger.info("\n📁 Generated files:")
        logger.info("  • seed_catalog.log (seeding logs)")
        logger.info("  • seeding_pipeline.log (pipeline logs)")
        
        logger.info("\n🌐 Next steps:")
        logger.info("  • Start the API server: uvicorn app.main:app --reload")
        logger.info("  • Test endpoints: curl http://localhost:8000/api/v1/catalog/stats")
        logger.info("  • Run ML training: python backend/scripts/train_all_models.py")

async def main():
    """Main pipeline execution"""
    logger.info("🚀 Starting comprehensive seeding pipeline")
    
    try:
        config = PipelineConfig()
        pipeline = SeedingPipeline(config)
        
        success = await pipeline.run_pipeline()
        
        if success:
            pipeline.print_summary()
        else:
            logger.error("💥 Seeding pipeline failed!")
        
        return success
        
    except Exception as e:
        logger.error(f"💥 Pipeline execution failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1) 
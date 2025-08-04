#!/usr/bin/env python3
"""
Comprehensive ML Training Pipeline
Trains all TF-IDF models with enhanced monitoring and error handling
"""

import asyncio
import logging
import time
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('training_pipeline.log')
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TrainingJob:
    """Represents a training job configuration"""
    name: str
    script_path: str
    description: str
    expected_files: List[str]
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

class TrainingPipeline:
    """Manages the complete ML training pipeline"""
    
    def __init__(self):
        self.jobs = [
            TrainingJob(
                name="accommodations",
                script_path="backend/app/core/recommender/train_tfidf_acc.py",
                description="TF-IDF model for accommodation recommendations",
                expected_files=[
                    "tfidf_vectorizer_acc.pkl",
                    "tfidf_matrix_acc.npz", 
                    "item_index_map_acc.pkl",
                    "training_metadata_acc.pkl"
                ]
            ),
            TrainingJob(
                name="activities",
                script_path="backend/app/core/recommender/train_tfidf_act.py",
                description="TF-IDF model for activity recommendations",
                expected_files=[
                    "tfidf_vectorizer_act.pkl",
                    "tfidf_matrix_act.npz",
                    "item_index_map_act.pkl", 
                    "training_metadata_act.pkl"
                ]
            ),
            TrainingJob(
                name="destinations",
                script_path="backend/app/core/recommender/train_tfidf_dest.py",
                description="TF-IDF model for destination recommendations",
                expected_files=[
                    "tfidf_vectorizer_dest.pkl",
                    "tfidf_matrix_dest.npz",
                    "item_index_map_dest.pkl",
                    "training_metadata_dest.pkl"
                ]
            ),
            TrainingJob(
                name="transportation",
                script_path="backend/app/core/recommender/train_tfidf_trans.py",
                description="TF-IDF model for transportation recommendations",
                expected_files=[
                    "tfidf_vectorizer_trans.pkl",
                    "tfidf_matrix_trans.npz",
                    "item_index_map_trans.pkl",
                    "training_metadata_trans.pkl"
                ]
            )
        ]
        
        self.results = {}
        self.models_dir = Path("/app/models")
    
    def validate_environment(self) -> bool:
        """Validate that the training environment is ready"""
        logger.info("🔍 Validating training environment...")
        
        # Check if models directory exists
        if not self.models_dir.exists():
            logger.error(f"Models directory does not exist: {self.models_dir}")
            return False
        
        # Check if all training scripts exist
        for job in self.jobs:
            script_path = Path(job.script_path)
            if not script_path.exists():
                logger.error(f"Training script not found: {script_path}")
                return False
        
        logger.info("✅ Environment validation passed")
        return True
    
    async def run_training_job(self, job: TrainingJob) -> Dict[str, Any]:
        """Run a single training job with monitoring"""
        logger.info(f"🚀 Starting {job.name} training...")
        
        try:
            async with performance_timer(f"{job.name}_training"):
                # Run the training script
                process = await asyncio.create_subprocess_exec(
                    sys.executable, job.script_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Wait for completion with timeout
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=job.timeout_minutes * 60
                    )
                except asyncio.TimeoutError:
                    logger.error(f"❌ {job.name} training timed out after {job.timeout_minutes} minutes")
                    process.kill()
                    return {
                        "success": False,
                        "error": "Training timed out",
                        "return_code": None
                    }
                
                # Check if training was successful
                if process.returncode == 0:
                    logger.info(f"✅ {job.name} training completed successfully")
                    return {
                        "success": True,
                        "stdout": stdout.decode(),
                        "stderr": stderr.decode(),
                        "return_code": process.returncode
                    }
                else:
                    logger.error(f"❌ {job.name} training failed with return code {process.returncode}")
                    return {
                        "success": False,
                        "stdout": stdout.decode(),
                        "stderr": stderr.decode(),
                        "return_code": process.returncode
                    }
                    
        except Exception as e:
            logger.error(f"❌ {job.name} training failed with exception: {e}")
            return {
                "success": False,
                "error": str(e),
                "return_code": None
            }
    
    def validate_job_output(self, job: TrainingJob) -> bool:
        """Validate that all expected files were created"""
        logger.info(f"🔍 Validating {job.name} output files...")
        
        missing_files = []
        for expected_file in job.expected_files:
            file_path = self.models_dir / expected_file
            if not file_path.exists():
                missing_files.append(expected_file)
            else:
                file_size = file_path.stat().st_size
                logger.info(f"  ✅ {expected_file} ({file_size} bytes)")
        
        if missing_files:
            logger.error(f"❌ Missing files for {job.name}: {missing_files}")
            return False
        
        logger.info(f"✅ {job.name} output validation passed")
        return True
    
    async def run_pipeline(self) -> bool:
        """Run the complete training pipeline"""
        logger.info("🚀 Starting ML training pipeline")
        
        # Validate environment
        if not self.validate_environment():
            return False
        
        # Run all training jobs
        for job in self.jobs:
            logger.info(f"\n{'='*60}")
            logger.info(f"Training: {job.name}")
            logger.info(f"Description: {job.description}")
            logger.info(f"{'='*60}")
            
            # Run the training job
            result = await self.run_training_job(job)
            self.results[job.name] = result
            
            if result["success"]:
                # Validate output files
                if not self.validate_job_output(job):
                    result["success"] = False
                    result["error"] = "Output validation failed"
            else:
                logger.error(f"❌ {job.name} training failed: {result.get('error', 'Unknown error')}")
        
        # Generate summary
        self.print_summary()
        
        # Return overall success
        return all(result["success"] for result in self.results.values())
    
    def print_summary(self):
        """Print a comprehensive training summary"""
        logger.info(f"\n{'='*80}")
        logger.info("📊 TRAINING PIPELINE SUMMARY")
        logger.info(f"{'='*80}")
        
        successful_jobs = []
        failed_jobs = []
        
        for job_name, result in self.results.items():
            if result["success"]:
                successful_jobs.append(job_name)
            else:
                failed_jobs.append(job_name)
        
        logger.info(f"✅ Successful jobs ({len(successful_jobs)}): {', '.join(successful_jobs)}")
        logger.info(f"❌ Failed jobs ({len(failed_jobs)}): {', '.join(failed_jobs)}")
        
        # Print detailed results
        for job_name, result in self.results.items():
            logger.info(f"\n📋 {job_name.upper()} RESULTS:")
            logger.info(f"  Status: {'✅ SUCCESS' if result['success'] else '❌ FAILED'}")
            if not result["success"]:
                logger.info(f"  Error: {result.get('error', 'Unknown error')}")
            if "return_code" in result and result["return_code"] is not None:
                logger.info(f"  Return Code: {result['return_code']}")
        
        # Print final status
        if failed_jobs:
            logger.info(f"\n❌ PIPELINE FAILED - {len(failed_jobs)} job(s) failed")
            return False
        else:
            logger.info(f"\n✅ PIPELINE SUCCESS - All {len(successful_jobs)} jobs completed successfully")
            return True

async def main():
    """Main pipeline execution"""
    logger.info("🚀 Starting comprehensive ML training pipeline")
    
    try:
        pipeline = TrainingPipeline()
        success = await pipeline.run_pipeline()
        
        if success:
            logger.info("🎉 All models trained successfully!")
        else:
            logger.error("💥 Training pipeline failed!")
        
        return success
        
    except Exception as e:
        logger.error(f"💥 Pipeline execution failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1) 
#!/usr/bin/env python3
"""
TF-IDF Training Script for Destination Recommendations
Enhanced version with better error handling, logging, and monitoring
"""

import re
import asyncio
import pickle
import logging
import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from contextlib import asynccontextmanager
from dataclasses import dataclass

from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.exceptions import NotFittedError
from sqlmodel import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import async_session
from app.db.models import Destination

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TrainingConfig:
    """Configuration for TF-IDF training"""
    max_features: int = 5000  # Destinations have diverse descriptions
    min_df: int = 2  # Minimum document frequency
    max_df: float = 0.95  # Maximum document frequency
    ngram_range: Tuple[int, int] = (1, 2)  # Unigrams and bigrams
    stop_words: str = "english"
    lowercase: bool = True
    strip_accents: bool = True
    min_text_length: int = 10  # Minimum text length to include
    max_text_length: int = 10000  # Maximum text length to include

@asynccontextmanager
async def performance_timer(operation: str):
    """Context manager for timing operations"""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        logger.info(f"{operation} completed in {duration:.2f}s")

class TextPreprocessor:
    """Enhanced text preprocessing utility"""
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.stats = {
            "total_processed": 0,
            "valid_documents": 0,
            "rejected_short": 0,
            "rejected_long": 0,
            "empty_documents": 0
        }
    
    def clean(self, text: str) -> Optional[str]:
        """
        Enhanced text cleaning with validation and statistics
        """
        if not text:
            self.stats["empty_documents"] += 1
            return None
        
        # Convert to string and normalize
        text = str(text).lower()
        
        # Remove special characters but keep important ones
        text = re.sub(r"[^a-z0-9\s\-\.\,\!\?]", " ", text)
        
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        
        # Validate length
        if len(text) < self.config.min_text_length:
            self.stats["rejected_short"] += 1
            return None
        
        if len(text) > self.config.max_text_length:
            self.stats["rejected_long"] += 1
            return None
        
        self.stats["valid_documents"] += 1
        return text
    
    def get_stats(self) -> Dict[str, Any]:
        """Get preprocessing statistics"""
        return self.stats.copy()

class DestinationCorpusBuilder:
    """Builds destination corpus with enhanced features"""
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.preprocessor = TextPreprocessor(config)
    
    async def fetch_destinations(self) -> Tuple[List[str], List[str]]:
        """
        Enhanced destination data fetching with error handling and validation
        Returns parallel lists of (ids, cleaned_texts).
        """
        ids, texts = [], []
        
        try:
            async with performance_timer("destination_data_fetch"):
                async with async_session() as session:
                    # Enhanced query with more fields
                    result = await session.execute(
                        select(
                            Destination.id,
                            Destination.name,
                            Destination.description,
                            Destination.country,
                            Destination.region
                        )
                    )
                    
                    for row in result.all():
                        _id, name, desc, country, region = row
                        
                        # Build comprehensive text representation
                        text_parts = []
                        if name:
                            text_parts.append(name)
                        if desc:
                            text_parts.append(desc)
                        if country:
                            text_parts.append(country)
                        if region:
                            text_parts.append(region)
                        
                        raw_text = " ".join(text_parts)
                        cleaned_text = self.preprocessor.clean(raw_text)
                        
                        if cleaned_text:
                            ids.append(str(_id))
                            texts.append(cleaned_text)
                    
                    logger.info(f"Fetched {len(ids)} valid destination documents")
                    logger.info(f"Preprocessing stats: {self.preprocessor.get_stats()}")
                    
        except SQLAlchemyError as e:
            logger.error(f"Database error during destination fetch: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during destination fetch: {e}")
            raise
        
        return ids, texts

class TFIDFTrainer:
    """Enhanced TF-IDF trainer with monitoring and validation"""
    
    def __init__(self, config: TrainingConfig, output_dir: Path):
        self.config = config
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)
        
        # Output file paths
        self.vec_pkl = output_dir / "tfidf_vectorizer_dest.pkl"
        self.mat_npz = output_dir / "tfidf_matrix_dest.npz"
        self.idmap_pkl = output_dir / "item_index_map_dest.pkl"
        self.metadata_pkl = output_dir / "training_metadata_dest.pkl"
        
        self.vectorizer = None
        self.matrix = None
        self.training_stats = {}
    
    def create_vectorizer(self) -> TfidfVectorizer:
        """Create TF-IDF vectorizer with configuration"""
        return TfidfVectorizer(
            max_features=self.config.max_features,
            min_df=self.config.min_df,
            max_df=self.config.max_df,
            ngram_range=self.config.ngram_range,
            stop_words=self.config.stop_words,
            lowercase=self.config.lowercase,
            strip_accents=self.config.strip_accents
        )
    
    def validate_corpus(self, corpus: List[str]) -> bool:
        """Validate corpus quality"""
        if not corpus:
            logger.error("Empty corpus provided")
            return False
        
        avg_length = sum(len(doc) for doc in corpus) / len(corpus)
        min_length = min(len(doc) for doc in corpus)
        max_length = max(len(doc) for doc in corpus)
        
        logger.info(f"Corpus statistics:")
        logger.info(f"  - Document count: {len(corpus)}")
        logger.info(f"  - Average length: {avg_length:.1f} characters")
        logger.info(f"  - Min length: {min_length} characters")
        logger.info(f"  - Max length: {max_length} characters")
        
        if avg_length < 20:
            logger.warning("Average document length is very short")
        
        return True
    
    async def train(self, ids: List[str], corpus: List[str]) -> bool:
        """Train TF-IDF model with enhanced monitoring"""
        try:
            # Validate corpus
            if not self.validate_corpus(corpus):
                return False
            
            # Create and train vectorizer
            async with performance_timer("tfidf_training"):
                self.vectorizer = self.create_vectorizer()
                self.matrix = self.vectorizer.fit_transform(corpus)
            
            # Collect training statistics
            self.training_stats = {
                "document_count": len(corpus),
                "feature_count": self.vectorizer.get_feature_names_out().shape[0],
                "matrix_shape": self.matrix.shape,
                "sparsity": 1 - (self.matrix.nnz / (self.matrix.shape[0] * self.matrix.shape[1])),
                "config": {
                    "max_features": self.config.max_features,
                    "min_df": self.config.min_df,
                    "max_df": self.config.max_df,
                    "ngram_range": self.config.ngram_range
                }
            }
            
            logger.info(f"Training completed successfully:")
            logger.info(f"  - Features: {self.training_stats['feature_count']}")
            logger.info(f"  - Matrix shape: {self.training_stats['matrix_shape']}")
            logger.info(f"  - Sparsity: {self.training_stats['sparsity']:.3f}")
            
            return True
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return False
    
    def save_artifacts(self, ids: List[str]) -> bool:
        """Save all training artifacts with error handling"""
        try:
            # Save vectorizer
            logger.info(f"💾 Saving vectorizer → {self.vec_pkl}")
            with open(self.vec_pkl, "wb") as f:
                pickle.dump(self.vectorizer, f)
            
            # Save matrix
            logger.info(f"💾 Saving matrix → {self.mat_npz}")
            sparse.save_npz(str(self.mat_npz), self.matrix)
            
            # Save ID map
            logger.info(f"💾 Saving ID map → {self.idmap_pkl}")
            with open(self.idmap_pkl, "wb") as f:
                pickle.dump(ids, f)
            
            # Save training metadata
            logger.info(f"💾 Saving training metadata → {self.metadata_pkl}")
            with open(self.metadata_pkl, "wb") as f:
                pickle.dump(self.training_stats, f)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save artifacts: {e}")
            return False
    
    def validate_saved_artifacts(self) -> bool:
        """Validate that saved artifacts can be loaded correctly"""
        try:
            # Test loading vectorizer
            with open(self.vec_pkl, "rb") as f:
                loaded_vec = pickle.load(f)
            
            # Test loading matrix
            loaded_mat = sparse.load_npz(str(self.mat_npz))
            
            # Test loading ID map
            with open(self.idmap_pkl, "rb") as f:
                loaded_ids = pickle.load(f)
            
            # Test loading metadata
            with open(self.metadata_pkl, "rb") as f:
                loaded_metadata = pickle.load(f)
            
            logger.info("✅ All artifacts validated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Artifact validation failed: {e}")
            return False

async def main():
    """Enhanced main function with comprehensive error handling"""
    logger.info("🚀 Starting destination TF-IDF training")
    
    try:
        # Configuration
        config = TrainingConfig()
        output_dir = Path("/app/models")
        
        # Build corpus
        logger.info("⏳ Fetching destination corpus...")
        corpus_builder = DestinationCorpusBuilder(config)
        ids, corpus = await corpus_builder.fetch_destinations()
        
        if not corpus:
            logger.error("⚠️  No destination documents found! (Nothing to vectorize.)")
            return False
        
        # Train model
        logger.info(f"⚙️  Training TF-IDF on {len(corpus)} documents...")
        trainer = TFIDFTrainer(config, output_dir)
        
        if not await trainer.train(ids, corpus):
            logger.error("❌ Training failed")
            return False
        
        # Save artifacts
        if not trainer.save_artifacts(ids):
            logger.error("❌ Failed to save artifacts")
            return False
        
        # Validate saved artifacts
        if not trainer.validate_saved_artifacts():
            logger.error("❌ Artifact validation failed")
            return False
        
        logger.info("✅ Destination TF-IDF training completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Training process failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)

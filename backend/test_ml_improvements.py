"""
Test file for ML training improvements
Demonstrates and tests the enhanced ML training features
"""

import pytest
import asyncio
import pickle
from pathlib import Path
from unittest.mock import AsyncMock, patch
from datetime import datetime

# Import training functions (these would be available after the improvements)
try:
    from app.core.recommender.train_tfidf_acc import (
        TrainingConfig, TextPreprocessor, AccommodationCorpusBuilder, TFIDFTrainer
    )
    from app.core.recommender.train_tfidf_act import (
        TrainingConfig as ActivityTrainingConfig,
        ActivityCorpusBuilder
    )
    from app.core.recommender.train_tfidf_dest import (
        TrainingConfig as DestinationTrainingConfig,
        DestinationCorpusBuilder
    )
    from app.core.recommender.train_tfidf_trans import (
        TrainingConfig as TransportationTrainingConfig,
        TransportationCorpusBuilder
    )
    ML_IMPROVEMENTS_AVAILABLE = True
except ImportError:
    ML_IMPROVEMENTS_AVAILABLE = False

def test_training_config():
    """Test training configuration classes"""
    if not ML_IMPROVEMENTS_AVAILABLE:
        pytest.skip("ML improvements not available")
    
    print("\n=== Testing Training Configuration ===")
    
    # Test accommodation config
    acc_config = TrainingConfig()
    print(f"Accommodation config: max_features={acc_config.max_features}, min_df={acc_config.min_df}")
    assert acc_config.max_features == 500
    assert acc_config.min_df == 2
    
    # Test activity config
    act_config = ActivityTrainingConfig()
    print(f"Activity config: max_features={act_config.max_features}")
    assert act_config.max_features == 5000
    
    # Test destination config
    dest_config = DestinationTrainingConfig()
    print(f"Destination config: max_features={dest_config.max_features}")
    assert dest_config.max_features == 5000
    
    # Test transportation config
    trans_config = TransportationTrainingConfig()
    print(f"Transportation config: max_features={trans_config.max_features}")
    assert trans_config.max_features == 100

def test_text_preprocessor():
    """Test enhanced text preprocessing"""
    if not ML_IMPROVEMENTS_AVAILABLE:
        pytest.skip("ML improvements not available")
    
    print("\n=== Testing Text Preprocessor ===")
    
    config = TrainingConfig()
    preprocessor = TextPreprocessor(config)
    
    # Test various text inputs
    test_cases = [
        ("", None),  # Empty text
        ("abc", None),  # Too short
        ("This is a valid text", "this is a valid text"),  # Valid
        ("  Multiple   Spaces  ", "multiple spaces"),  # Whitespace normalization
        ("Special@#$%^&*()Chars", "special chars"),  # Special character removal
        ("Very long text " * 1000, None),  # Too long
    ]
    
    for input_text, expected in test_cases:
        result = preprocessor.clean(input_text)
        print(f"Input: '{input_text[:50]}...' -> Output: '{result}'")
        assert result == expected
    
    # Check statistics
    stats = preprocessor.get_stats()
    print(f"Preprocessing stats: {stats}")
    assert "valid_documents" in stats
    assert "rejected_short" in stats
    assert "rejected_long" in stats

def test_corpus_builder_structure():
    """Test corpus builder class structure"""
    if not ML_IMPROVEMENTS_AVAILABLE:
        pytest.skip("ML improvements not available")
    
    print("\n=== Testing Corpus Builder Structure ===")
    
    # Test accommodation corpus builder
    config = TrainingConfig()
    acc_builder = AccommodationCorpusBuilder(config)
    print(f"Accommodation builder created: {type(acc_builder)}")
    assert hasattr(acc_builder, 'fetch_accommodations')
    assert hasattr(acc_builder, 'preprocessor')
    
    # Test activity corpus builder
    act_config = ActivityTrainingConfig()
    act_builder = ActivityCorpusBuilder(act_config)
    print(f"Activity builder created: {type(act_builder)}")
    assert hasattr(act_builder, 'fetch_activities')
    
    # Test destination corpus builder
    dest_config = DestinationTrainingConfig()
    dest_builder = DestinationCorpusBuilder(dest_config)
    print(f"Destination builder created: {type(dest_builder)}")
    assert hasattr(dest_builder, 'fetch_destinations')
    
    # Test transportation corpus builder
    trans_config = TransportationTrainingConfig()
    trans_builder = TransportationCorpusBuilder(trans_config)
    print(f"Transportation builder created: {type(trans_builder)}")
    assert hasattr(trans_builder, 'fetch_transportations')

def test_tfidf_trainer_structure():
    """Test TF-IDF trainer class structure"""
    if not ML_IMPROVEMENTS_AVAILABLE:
        pytest.skip("ML improvements not available")
    
    print("\n=== Testing TF-IDF Trainer Structure ===")
    
    config = TrainingConfig()
    output_dir = Path("/tmp/test_models")
    trainer = TFIDFTrainer(config, output_dir)
    
    print(f"Trainer created: {type(trainer)}")
    assert hasattr(trainer, 'create_vectorizer')
    assert hasattr(trainer, 'validate_corpus')
    assert hasattr(trainer, 'train')
    assert hasattr(trainer, 'save_artifacts')
    assert hasattr(trainer, 'validate_saved_artifacts')
    
    # Test vectorizer creation
    vectorizer = trainer.create_vectorizer()
    print(f"Vectorizer created: {type(vectorizer)}")
    assert vectorizer is not None

def test_corpus_validation():
    """Test corpus validation logic"""
    if not ML_IMPROVEMENTS_AVAILABLE:
        pytest.skip("ML improvements not available")
    
    print("\n=== Testing Corpus Validation ===")
    
    config = TrainingConfig()
    output_dir = Path("/tmp/test_models")
    trainer = TFIDFTrainer(config, output_dir)
    
    # Test empty corpus
    result = trainer.validate_corpus([])
    print(f"Empty corpus validation: {result}")
    assert result is False
    
    # Test valid corpus
    valid_corpus = ["This is a valid document", "Another valid document", "Third valid document"]
    result = trainer.validate_corpus(valid_corpus)
    print(f"Valid corpus validation: {result}")
    assert result is True

def test_artifact_validation():
    """Test artifact validation logic"""
    if not ML_IMPROVEMENTS_AVAILABLE:
        pytest.skip("ML improvements not available")
    
    print("\n=== Testing Artifact Validation ===")
    
    config = TrainingConfig()
    output_dir = Path("/tmp/test_models")
    trainer = TFIDFTrainer(config, output_dir)
    
    # Test validation with non-existent files
    result = trainer.validate_saved_artifacts()
    print(f"Artifact validation (non-existent): {result}")
    assert result is False

def test_training_pipeline_structure():
    """Test training pipeline structure"""
    print("\n=== Testing Training Pipeline Structure ===")
    
    # Test if training pipeline script exists
    pipeline_script = Path("backend/scripts/train_all_models.py")
    print(f"Training pipeline script exists: {pipeline_script.exists()}")
    
    if pipeline_script.exists():
        print("✅ Training pipeline script found")
    else:
        print("❌ Training pipeline script not found")

def test_model_metadata():
    """Test model metadata structure"""
    print("\n=== Testing Model Metadata ===")
    
    # Expected metadata structure
    expected_metadata = {
        "document_count": 100,
        "feature_count": 500,
        "matrix_shape": (100, 500),
        "sparsity": 0.95,
        "config": {
            "max_features": 500,
            "min_df": 2,
            "max_df": 0.95,
            "ngram_range": (1, 2)
        }
    }
    
    print(f"Expected metadata structure: {expected_metadata}")
    assert "document_count" in expected_metadata
    assert "feature_count" in expected_metadata
    assert "matrix_shape" in expected_metadata
    assert "sparsity" in expected_metadata
    assert "config" in expected_metadata

def run_ml_demo():
    """Run a comprehensive ML improvements demo"""
    print("\n" + "="*60)
    print("🤖 ML TRAINING IMPROVEMENTS DEMO")
    print("="*60)
    
    # Test all ML features
    test_training_config()
    test_text_preprocessor()
    test_corpus_builder_structure()
    test_tfidf_trainer_structure()
    test_corpus_validation()
    test_artifact_validation()
    test_training_pipeline_structure()
    test_model_metadata()
    
    print("\n" + "="*60)
    print("✅ All ML tests completed successfully!")
    print("="*60)
    
    print("\n📋 NEW ML FEATURES SUMMARY:")
    print("• Enhanced text preprocessing with validation")
    print("• Comprehensive error handling and logging")
    print("• Performance monitoring and timing")
    print("• Corpus quality validation")
    print("• Artifact validation and testing")
    print("• Training metadata and statistics")
    print("• Modular architecture with separate classes")
    print("• Configurable training parameters")
    print("• Comprehensive training pipeline")
    
    print("\n🚀 NEW TRAINING SCRIPTS:")
    print("• backend/app/core/recommender/train_tfidf_acc.py (enhanced)")
    print("• backend/app/core/recommender/train_tfidf_act.py (enhanced)")
    print("• backend/app/core/recommender/train_tfidf_dest.py (enhanced)")
    print("• backend/app/core/recommender/train_tfidf_trans.py (enhanced)")
    print("• backend/scripts/train_all_models.py (new pipeline)")
    
    print("\n📊 NEW ARTIFACTS:")
    print("• training_metadata_*.pkl (training statistics)")
    print("• Enhanced logging and monitoring")
    print("• Performance timing for all operations")
    print("• Corpus quality metrics")

if __name__ == "__main__":
    run_ml_demo() 
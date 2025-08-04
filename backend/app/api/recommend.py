from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import scipy.sparse
import re
import logging
import time
from typing import List, Optional, Dict, Any
from functools import lru_cache
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field, field_validator

from app.db.session import get_session
from app.db.models import Destination, Activity, Accommodation, Transportation

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommend", tags=["recommendations"])

# Performance timer
@asynccontextmanager
async def performance_timer(operation: str):
    """Context manager for timing operations"""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        logger.info(f"{operation} completed in {duration:.2f}s")

# Input validation models
class RecommendationRequest(BaseModel):
    interests: List[str] = Field(default_factory=list, description="User interests")
    budget: float = Field(default=0.0, ge=0, description="Budget in currency units")
    limit: Optional[int] = Field(default=10, ge=1, le=50, description="Number of recommendations to return")
    
    @field_validator('interests')
    @classmethod
    def validate_interests(cls, v):
        if len(v) > 20:
            raise ValueError("Too many interests (max 20)")
        return [interest.lower().strip() for interest in v if interest.strip()]

# Helper to clean free-form query text
def clean(text: str) -> str:
    """Clean and normalize text for ML processing"""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

class MLModelManager:
    """Manages ML models with proper error handling and caching"""
    
    def __init__(self):
        self.models = {}
        self._load_models()
    
    def _load_models(self):
        """Load all ML models with error handling"""
        model_configs = {
            'dest': {
                'vectorizer_path': "/app/models/tfidf_vectorizer_dest.pkl",
                'matrix_path': "/app/models/tfidf_matrix_dest.npz",
                'idmap_path': "/app/models/item_index_map_dest.pkl"
            },
            'act': {
                'vectorizer_path': "/app/models/tfidf_vectorizer_act.pkl",
                'matrix_path': "/app/models/tfidf_matrix_act.npz",
                'idmap_path': "/app/models/item_index_map_act.pkl"
            },
            'acc': {
                'vectorizer_path': "/app/models/tfidf_vectorizer_acc.pkl",
                'matrix_path': "/app/models/tfidf_matrix_acc.npz",
                'idmap_path': "/app/models/item_index_map_acc.pkl"
            },
            'trans': {
                'vectorizer_path': "/app/models/tfidf_vectorizer_trans.pkl",
                'matrix_path': "/app/models/tfidf_matrix_trans.npz",
                'idmap_path': "/app/models/item_index_map_trans.pkl"
            }
        }
        
        for model_type, config in model_configs.items():
            try:
                vectorizer = pickle.load(open(config['vectorizer_path'], "rb"))
                matrix = scipy.sparse.load_npz(config['matrix_path'])
                id_map = pickle.load(open(config['idmap_path'], "rb"))
                
                self.models[model_type] = {
                    'vectorizer': vectorizer,
                    'matrix': matrix,
                    'id_map': id_map
                }
                logger.info(f"Successfully loaded {model_type} model")
            except Exception as e:
                logger.error(f"Failed to load {model_type} model: {e}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"ML model for {model_type} is unavailable"
                )
    
    def get_recommendations(self, model_type: str, query: str, limit: int = 10) -> List[str]:
        """Get recommendations using specified model"""
        if model_type not in self.models:
            raise HTTPException(status_code=500, detail=f"Model {model_type} not available")
        
        try:
            model = self.models[model_type]
            vectorizer = model['vectorizer']
            matrix = model['matrix']
            id_map = model['id_map']
            
            # Transform query
            q_vec = vectorizer.transform([query])
            
            # Compute similarities
            scores = cosine_similarity(q_vec, matrix).flatten()
            top_idxs = scores.argsort()[::-1][:limit]
            
            # Map to IDs and filter by score
            top_ids = [id_map[i] for i in top_idxs if scores[i] > 0]
            
            logger.info(f"Generated {len(top_ids)} {model_type} recommendations", extra={
                'query': query,
                'top_scores': scores[top_idxs].tolist(),
                'model_type': model_type
            })
            
            return top_ids
        except Exception as e:
            logger.error(f"Error getting {model_type} recommendations: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get {model_type} recommendations")

# Initialize ML model manager
try:
    ml_manager = MLModelManager()
except Exception as e:
    logger.error(f"Failed to initialize ML models: {e}")
    ml_manager = None

class RecommendationService:
    """Service class for handling recommendation logic"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_destinations(self, interests: List[str], budget: float, limit: int = 10):
        """Get destination recommendations"""
        if not ml_manager:
            raise HTTPException(status_code=500, detail="ML service unavailable")
        
        query = clean(" ".join(interests) + f" budget {budget}")
        top_ids = ml_manager.get_recommendations('dest', query, limit)
        
        if not top_ids:
            raise HTTPException(status_code=404, detail="No destination recommendations found")
        
        stmt = select(Destination).where(Destination.id.in_(top_ids))
        results = await self.session.scalars(stmt)
        items = results.all()
        
        if not items:
            raise HTTPException(status_code=404, detail="No destination recommendations found")
        
        return items
    
    async def get_activities(self, interests: List[str], budget: float, limit: int = 10):
        """Get activity recommendations"""
        if not ml_manager:
            raise HTTPException(status_code=500, detail="ML service unavailable")
        
        query = clean(" ".join(interests) + f" budget {budget}")
        top_ids = ml_manager.get_recommendations('act', query, limit)
        
        if not top_ids:
            raise HTTPException(status_code=404, detail="No activity recommendations found")
        
        stmt = select(Activity).where(Activity.id.in_(top_ids))
        results = await self.session.scalars(stmt)
        items = results.all()
        
        if not items:
            raise HTTPException(status_code=404, detail="No activity recommendations found")
        
        return items
    
    async def get_accommodations(self, interests: List[str], budget: float, limit: int = 10):
        """Get accommodation recommendations"""
        if not ml_manager:
            raise HTTPException(status_code=500, detail="ML service unavailable")
        
        query = clean(" ".join(interests) + f" budget {budget}")
        top_ids = ml_manager.get_recommendations('acc', query, limit)
        
        if not top_ids:
            raise HTTPException(status_code=404, detail="No accommodation recommendations found")
        
        stmt = select(Accommodation).where(Accommodation.id.in_(top_ids))
        results = await self.session.scalars(stmt)
        items = results.all()
        
        if not items:
            raise HTTPException(status_code=404, detail="No accommodation recommendations found")
        
        return items
    
    async def get_transportations(self, interests: List[str], budget: float, limit: int = 10):
        """Get transportation recommendations"""
        if not ml_manager:
            raise HTTPException(status_code=500, detail="ML service unavailable")
        
        query = clean(" ".join(interests) + f" budget {budget}")
        top_ids = ml_manager.get_recommendations('trans', query, limit)
        
        if not top_ids:
            raise HTTPException(status_code=404, detail="No transportation recommendations found")
        
        stmt = select(Transportation).where(Transportation.id.in_(top_ids))
        results = await self.session.scalars(stmt)
        items = results.all()
        
        if not items:
            raise HTTPException(status_code=404, detail="No transportation recommendations found")
        
        return items

# Cached recommendation function
@lru_cache(maxsize=1000)
def get_cached_recommendations(query_key: str, model_type: str, limit: int):
    """Cache recommendations to improve performance"""
    if not ml_manager:
        return []
    return ml_manager.get_recommendations(model_type, query_key, limit)

@router.post("/destinations", 
    responses={
        200: {"description": "Destination recommendations"},
        400: {"description": "Invalid request parameters"},
        404: {"description": "No recommendations found"},
        500: {"description": "ML service unavailable"}
    },
    summary="Get destination recommendations",
    description="Get personalized destination recommendations based on interests and budget"
)
async def recommend_destinations(
    request: Request,
    prefs: RecommendationRequest,
    session: AsyncSession = Depends(get_session)
):
    """Get destination recommendations"""
    async with performance_timer("destination_recommendations"):
        try:
            service = RecommendationService(session)
            items = await service.get_destinations(
                prefs.interests, prefs.budget, prefs.limit
            )
            
            logger.info(f"Returned {len(items)} destination recommendations", extra={
                'interests': prefs.interests,
                'budget': prefs.budget,
                'count': len(items)
            })
            
            return items
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in destination recommendations: {e}")
            raise HTTPException(status_code=500, detail="Failed to get destination recommendations")

@router.post("/activities",
    responses={
        200: {"description": "Activity recommendations"},
        400: {"description": "Invalid request parameters"},
        404: {"description": "No recommendations found"},
        500: {"description": "ML service unavailable"}
    },
    summary="Get activity recommendations",
    description="Get personalized activity recommendations based on interests and budget"
)
async def recommend_activities(
    request: Request,
    prefs: RecommendationRequest,
    session: AsyncSession = Depends(get_session)
):
    """Get activity recommendations"""
    async with performance_timer("activity_recommendations"):
        try:
            service = RecommendationService(session)
            items = await service.get_activities(
                prefs.interests, prefs.budget, prefs.limit
            )
            
            logger.info(f"Returned {len(items)} activity recommendations", extra={
                'interests': prefs.interests,
                'budget': prefs.budget,
                'count': len(items)
            })
            
            return items
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in activity recommendations: {e}")
            raise HTTPException(status_code=500, detail="Failed to get activity recommendations")

@router.post("/accommodations",
    responses={
        200: {"description": "Accommodation recommendations"},
        400: {"description": "Invalid request parameters"},
        404: {"description": "No recommendations found"},
        500: {"description": "ML service unavailable"}
    },
    summary="Get accommodation recommendations",
    description="Get personalized accommodation recommendations based on interests and budget"
)
async def recommend_accommodations(
    request: Request,
    prefs: RecommendationRequest,
    session: AsyncSession = Depends(get_session)
):
    """Get accommodation recommendations"""
    async with performance_timer("accommodation_recommendations"):
        try:
            service = RecommendationService(session)
            items = await service.get_accommodations(
                prefs.interests, prefs.budget, prefs.limit
            )
            
            logger.info(f"Returned {len(items)} accommodation recommendations", extra={
                'interests': prefs.interests,
                'budget': prefs.budget,
                'count': len(items)
            })
            
            return items
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in accommodation recommendations: {e}")
            raise HTTPException(status_code=500, detail="Failed to get accommodation recommendations")

@router.post("/transportations",
    responses={
        200: {"description": "Transportation recommendations"},
        400: {"description": "Invalid request parameters"},
        404: {"description": "No recommendations found"},
        500: {"description": "ML service unavailable"}
    },
    summary="Get transportation recommendations",
    description="Get personalized transportation recommendations based on interests and budget"
)
async def recommend_transportations(
    request: Request,
    prefs: RecommendationRequest,
    session: AsyncSession = Depends(get_session)
):
    """Get transportation recommendations"""
    async with performance_timer("transportation_recommendations"):
        try:
            service = RecommendationService(session)
            items = await service.get_transportations(
                prefs.interests, prefs.budget, prefs.limit
            )
            
            logger.info(f"Returned {len(items)} transportation recommendations", extra={
                'interests': prefs.interests,
                'budget': prefs.budget,
                'count': len(items)
            })
            
            return items
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in transportation recommendations: {e}")
            raise HTTPException(status_code=500, detail="Failed to get transportation recommendations")

# Health check endpoint for ML models
@router.get("/health")
async def health_check():
    """Check ML model health"""
    if not ml_manager:
        return {"status": "unhealthy", "reason": "ML models not loaded"}
    
    model_status = {}
    for model_type in ['dest', 'act', 'acc', 'trans']:
        model_status[model_type] = model_type in ml_manager.models
    
    all_healthy = all(model_status.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "models": model_status,
        "timestamp": "2024-01-01T00:00:00Z"
    }

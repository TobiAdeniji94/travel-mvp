from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
import time
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
import structlog

from app.core.nlp.parser import parse_travel_request

# Set up logging
logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/nlp", tags=["NLP"])

# Performance timer
@asynccontextmanager
async def performance_timer(operation: str):
    """Context manager for timing operations"""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        logger.info("operation_completed", operation=operation, duration_seconds=round(duration, 2))

# Input validation models
class ParseRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=2000, description="Natural language travel request")
    
    @field_validator('text')
    @classmethod
    def validate_text(cls, v):
        if not v or not v.strip():
            raise ValueError("Text cannot be empty")
        # Check for potentially malicious content
        suspicious_patterns = ['<script>', 'javascript:', 'data:text/html']
        if any(pattern in v.lower() for pattern in suspicious_patterns):
            raise ValueError("Text contains invalid content")
        return v.strip()

class ParseResponse(BaseModel):
    """Response model for NLP parsing results"""
    original_text: str
    parsed_data: Dict[str, Any]
    processing_time: float
    confidence_score: Optional[float] = None
    errors: List[str] = []

class NLPService:
    """Service class for handling NLP operations"""
    
    @staticmethod
    def parse_travel_request_safe(text: str) -> Dict[str, Any]:
        """Safely parse travel request with error handling"""
        try:
            result = parse_travel_request(text)
            logger.info(
                "travel_request_parsed",
                text_length=len(text),
                parsed_keys=list(result.keys()) if result else [],
                has_destination=bool(result.get('destination')),
                has_dates=bool(result.get('dates'))
            )
            return result
        except Exception as e:
            logger.error(
                "travel_request_parse_failed",
                error=str(e),
                error_type=type(e).__name__,
                text_length=len(text)
            )
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to parse travel request: {str(e)}"
            )
    
    @staticmethod
    def get_sample_requests() -> List[Dict[str, str]]:
        """Get sample travel requests for testing"""
        return [
            {
                "description": "Basic trip request",
                "text": "Plan a trip to Paris next month with a budget of $2000. Include sightseeing and local cuisine."
            },
            {
                "description": "Family vacation request",
                "text": "Plan a 7-day family vacation to Tokyo in December. Budget $5000. Include kid-friendly activities and 4-star hotels."
            },
            {
                "description": "Business trip request",
                "text": "Business trip to New York from London, March 15-20. Need flights and hotel near downtown. Budget $3000."
            },
            {
                "description": "Adventure trip request",
                "text": "Adventure trip to Peru for 10 days. Include hiking, Machu Picchu, and local culture. Budget $4000."
            },
            {
                "description": "Luxury trip request",
                "text": "Luxury 5-day trip to Maldives. Include private villa, spa treatments, and fine dining. Budget $15000."
            }
        ]

@router.post("/parse", 
    response_model=ParseResponse,
    responses={
        200: {"description": "Successfully parsed travel request"},
        400: {"description": "Invalid input or parsing failed"},
        500: {"description": "Internal server error"}
    },
    summary="Parse travel request",
    description="Parse natural language travel request into structured data"
)
async def parse_travel_request_endpoint(
    request: Request,
    parse_req: ParseRequest
):
    """Parse a natural language travel request"""
    async with performance_timer("nlp_parsing"):
        try:
            # Parse the request
            start_time = time.time()
            parsed_data = NLPService.parse_travel_request_safe(parse_req.text)
            processing_time = time.time() - start_time
            
            # Calculate confidence score (simple heuristic)
            confidence_score = min(0.95, max(0.5, 1.0 - (len(parse_req.text) / 2000)))
            
            logger.info(
                "nlp_parse_endpoint_success",
                text_length=len(parse_req.text),
                processing_time_ms=round(processing_time * 1000, 2),
                confidence_score=round(confidence_score, 3),
                parsed_fields=list(parsed_data.keys())
            )
            
            return ParseResponse(
                original_text=parse_req.text,
                parsed_data=parsed_data,
                processing_time=processing_time,
                confidence_score=confidence_score,
                errors=[]
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "nlp_parse_endpoint_error",
                error=str(e),
                error_type=type(e).__name__
            )
            raise HTTPException(status_code=500, detail="Failed to parse travel request")

@router.get("/parse-test")
async def parse_test():
    """Test endpoint with a sample travel request"""
    async with performance_timer("nlp_test_parsing"):
        try:
            sample = "Plan a trip to Paris next month with a budget of $2000. Include sightseeing and local cuisine."
            
            start_time = time.time()
            result = NLPService.parse_travel_request_safe(sample)
            processing_time = time.time() - start_time
            
            logger.info(
                "nlp_test_parse_completed",
                sample_length=len(sample),
                processing_time_ms=round(processing_time * 1000, 2)
            )
            
            return {
                "sample_text": sample,
                "parsed_result": result,
                "processing_time": processing_time,
                "status": "success"
            }
        except Exception as e:
            logger.error("nlp_test_parse_failed", error=str(e), error_type=type(e).__name__)
            raise HTTPException(status_code=500, detail=f"Test parsing failed: {str(e)}")

@router.get("/samples")
async def get_sample_requests():
    """Get sample travel requests for testing"""
    try:
        samples = NLPService.get_sample_requests()
        logger.info("nlp_samples_returned", sample_count=len(samples))
        return {
            "samples": samples,
            "count": len(samples),
            "description": "Sample travel requests for testing NLP functionality"
        }
    except Exception as e:
        logger.error("nlp_samples_failed", error=str(e), error_type=type(e).__name__)
        raise HTTPException(status_code=500, detail="Failed to get sample requests")

@router.post("/parse-batch")
async def parse_batch_requests(
    requests: List[ParseRequest]
):
    """Parse multiple travel requests in batch"""
    async with performance_timer("batch_nlp_parsing"):
        try:
            if len(requests) > 10:
                raise HTTPException(status_code=400, detail="Too many requests (max 10)")
            
            results = []
            total_time = 0
            
            for i, req in enumerate(requests):
                start_time = time.time()
                try:
                    parsed_data = NLPService.parse_travel_request_safe(req.text)
                    processing_time = time.time() - start_time
                    total_time += processing_time
                    
                    results.append({
                        "index": i,
                        "original_text": req.text,
                        "parsed_data": parsed_data,
                        "processing_time": processing_time,
                        "status": "success"
                    })
                except Exception as e:
                    results.append({
                        "index": i,
                        "original_text": req.text,
                        "parsed_data": None,
                        "processing_time": 0,
                        "status": "error",
                        "error": str(e)
                    })
            
            logger.info(f"Batch parsing completed", extra={
                'total_requests': len(requests),
                'successful_parses': len([r for r in results if r['status'] == 'success']),
                'total_processing_time': total_time
            })
            
            return {
                "results": results,
                "summary": {
                    "total_requests": len(requests),
                    "successful_parses": len([r for r in results if r['status'] == 'success']),
                    "failed_parses": len([r for r in results if r['status'] == 'error']),
                    "total_processing_time": total_time
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in batch parsing: {e}")
            raise HTTPException(status_code=500, detail="Failed to process batch requests")

@router.get("/health")
async def health_check():
    """Check NLP service health"""
    try:
        # Test with a simple request
        test_text = "Plan a trip to London"
        result = NLPService.parse_travel_request_safe(test_text)
        
        return {
            "status": "healthy",
            "service": "NLP Parser",
            "test_result": "success",
            "timestamp": "2024-01-01T00:00:00Z"
        }
    except Exception as e:
        logger.error(f"NLP health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "NLP Parser",
            "error": str(e),
            "timestamp": "2024-01-01T00:00:00Z"
        }

@router.get("/stats")
async def get_nlp_stats():
    """Get NLP service statistics"""
    try:
        # This would typically come from a metrics service
        # For now, return basic stats
        return {
            "total_parses": 0,  # Would be tracked in production
            "average_processing_time": 0.0,
            "success_rate": 1.0,
            "last_24h_requests": 0,
            "service_uptime": "100%"
        }
    except Exception as e:
        logger.error(f"Failed to get NLP stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get NLP statistics")
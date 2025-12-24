import os
import logging
import re
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.db.session import init_db, get_session
from app.api import users, itinerary, auth, nlp, recommend
import structlog

# ============================================================================
# API Key Redaction & Security Configuration
# ============================================================================

def redact_api_keys(logger, method_name, event_dict):
    """
    Structlog processor that redacts Google API keys and similar secrets from
    all logged strings and nested structures (lists, dicts).
    """
    def _redact_value(v):
        if isinstance(v, str):
            # Redact ?key=... or &key=... query parameters
            v = re.sub(r'([?&]key=)[^&\s]+', r'\1REDACTED', v)
            # Redact common API key patterns (e.g., AIzaSyXXX...)
            v = re.sub(r'(AIza[0-9A-Za-z-_]{35})', 'REDACTED', v)
            return v
        elif isinstance(v, list):
            return [_redact_value(item) for item in v]
        elif isinstance(v, dict):
            return {k: _redact_value(val) for k, val in v.items()}
        return v
    
    return _redact_value(event_dict)


def build_photo_url(photoref: str, maxwidth: int = 400) -> str:
    """
    Build a signed Google Place Photo URL from a photoreference token.
    Requires GOOGLE_MAPS_API_KEY environment variable at runtime.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        # Return unsigned URL if key not configured
        return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth={maxwidth}&photoreference={photoref}"
    return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth={maxwidth}&photoreference={photoref}&key={api_key}"


# Configure structlog with redaction processor
structlog.configure(
    processors=[
        redact_api_keys,  # Must be early in pipeline
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application...")
    try:
        logger.info("Initializing database manager...")
        await db_manager.initialize()
        logger.info("Database manager initialized successfully")
    except Exception as e:
        # logger.error(f"Failed to initialize database manager: {e}")
        logger.exception("Failed to initialize database manager")
        raise
        # Don't raise here to allow app to start in degraded mode
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    try:
        logger.info("Closing database connections...")
        await db_manager.close()
        logger.info("Database connections closed successfully")
    except Exception as e:
        logger.error(f"Error during database cleanup: {e}")

app = FastAPI(
    title="The Calm Route API",
    description="AI-powered travel itinerary generation service",
    version="1.0.0",
    lifespan=lifespan
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Add photo URL builder middleware (response-time URL signing)
@app.middleware("http")
async def photo_url_middleware(request: Request, call_next):
    """
    Middleware that transforms stored photoreference tokens in JSON responses
    into signed Google Place Photo URLs at response time.
    This prevents storage of API keys in the database.
    """
    response = await call_next(request)
    
    # Only process JSON responses
    if "application/json" in response.headers.get("content-type", ""):
        try:
            body = await response.body()
            data = json.loads(body)
            
            # Transform 'images' fields: if they contain photoreference tokens,
            # build signed URLs at response time
            def transform_images(obj):
                if isinstance(obj, dict):
                    if "images" in obj and isinstance(obj["images"], list):
                        obj["images"] = [
                            build_photo_url(img) if not img.startswith("http") else img
                            for img in obj["images"]
                        ]
                    for v in obj.values():
                        if isinstance(v, (dict, list)):
                            transform_images(v)
                elif isinstance(obj, list):
                    for item in obj:
                        if isinstance(item, (dict, list)):
                            transform_images(item)
            
            transform_images(data)
            new_body = json.dumps(data).encode("utf-8")
            return Response(
                content=new_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
        except Exception as e:
            logger.exception(f"Error in photo_url_middleware: {e}")
            # On error, return original response
            return response
    
    return response

# Enable CORS for frontend
# Get allowed origins from environment variable or use defaults
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:3001"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/")
def health_check():
    return {"status": "API active", "version": "1.0.0"}

prefix = "/api/v1"

# Include API routers
app.include_router(auth.router, prefix=prefix, tags=["auth"])
app.include_router(users.router, prefix=prefix, tags=["users"])
app.include_router(itinerary.router, prefix=prefix, tags=["itineraries"])
app.include_router(nlp.router, prefix=prefix, tags=["NLP"])
app.include_router(recommend.router, prefix=prefix, tags=["recommendations"])
app.include_router(security.router, prefix=prefix, tags=["security"])
app.include_router(catalog.router, prefix=prefix, tags=["catalog"])
app.include_router(database.router, prefix=f"{prefix}/database", tags=["database"])



# Database connectivity test
DB_URL = os.getenv("DB_URL", "postgresql://postgres:password@db:5432/traveldb")
engine = create_engine(DB_URL, echo=False, future=True)

@app.get("/test-db")
def test_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"db_status": "connected"}
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {e}")
        return {"db_status": "failed", "error": str(e)}

@app.get("/health")
async def health_check_detailed():
    """Detailed health check endpoint"""
    try:
        # Test database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Check ML models availability
    try:
        from app.api.recommend import ml_manager
        ml_status = "healthy" if ml_manager.models else "degraded"
    except Exception:
        ml_status = "unknown"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "version": "1.0.0",
        "components": {
            "database": db_status,
            "ml_models": ml_status,
            "api": "healthy"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

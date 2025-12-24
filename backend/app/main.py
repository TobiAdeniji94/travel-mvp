import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog
from prometheus_fastapi_instrumentator import Instrumentator

from app.db.session import init_db, get_db_session, db_manager
from app.api import users, itinerary, auth, nlp, recommend, security, catalog, database
from app.middleware.logging import RequestLoggingMiddleware
import os
import json

# Configure structured logging with JSON output
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        # redact sensitive query params (e.g. Google API keys) from event dicts
        # this runs before JSONRenderer so file/console output never contains keys
        # processor implemented below
        # placeholder - actual processor function defined later in file
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Redaction processor to scrub API keys from any string values in the event dict
def redact_api_keys(logger, method_name, event_dict):
    import re

    def scrub(v):
        if isinstance(v, str):
            # redact Google/other API keys in query params
            v = re.sub(r'([?&]key=)[^&\s]+', r'\1REDACTED', v)
            # redact any obvious API key-looking tokens (short heuristic)
            v = re.sub(r'(AIza[0-9A-Za-z-_]{35})', 'REDACTED', v)
            return v
        if isinstance(v, list):
            return [scrub(x) for x in v]
        if isinstance(v, dict):
            return {k: scrub(vv) for k, vv in v.items()}
        return v

    for k, v in list(event_dict.items()):
        event_dict[k] = scrub(v)
    return event_dict

# Re-configure processors to insert redact_api_keys before rendering
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        redact_api_keys,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

# Configure standard library logging to output to file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',  # structlog handles formatting
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)

logger = structlog.get_logger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

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


# Build signed Google Place Photo URL at response time from stored photoreference
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def build_photo_url(photoref: str, maxwidth: int = 400) -> str:
    if not photoref:
        return photoref
    # photoref should be the token stored in DB; build signed URL at runtime
    if GOOGLE_MAPS_API_KEY:
        return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth={maxwidth}&photoreference={photoref}&key={GOOGLE_MAPS_API_KEY}"
    # Fallback: return a URL without a key (some environments may proxy requests)
    return f"https://maps.googleapis.com/maps/api/place/photo?maxwidth={maxwidth}&photoreference={photoref}"


@app.middleware("http")
async def photo_url_middleware(request: Request, call_next):
    resp = await call_next(request)
    content_type = resp.headers.get("content-type", "")
    if "application/json" in content_type.lower():
        try:
            # read response body
            body = b""
            async for chunk in resp.body_iterator:
                body += chunk
        except Exception:
            return resp

        try:
            data = json.loads(body)
        except Exception:
            # not JSON or failed to parse
            return resp

        def transform(obj):
            if isinstance(obj, dict):
                for k, v in list(obj.items()):
                    if k == "images" and isinstance(v, list):
                        new = []
                        for it in v:
                            if isinstance(it, str) and not it.startswith("http"):
                                new.append(build_photo_url(it))
                            else:
                                new.append(it)
                        obj[k] = new
                    else:
                        transform(v)
            elif isinstance(obj, list):
                for item in obj:
                    transform(item)

        transform(data)

        new_body = json.dumps(data).encode("utf-8")
        resp.body_iterator = iter([new_body])
        resp.headers["content-length"] = str(len(new_body))

    return resp

# Initialize Prometheus metrics instrumentation
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        error=str(exc),
        error_type=type(exc).__name__,
        path=request.url.path,
        method=request.method,
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
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

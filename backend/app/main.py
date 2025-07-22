import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.db.session import init_db, get_session
from app.api import users, itinerary, auth, nlp, recommend

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/")
def health_check():
    return {"status": "API active", "version": "0.1.0"}

prefix = "/api/v1"

# Include API routers
app.include_router(auth.router, prefix=prefix, tags=["auth"])
app.include_router(users.router, prefix=prefix, tags=["users"])
app.include_router(itinerary.router, prefix=prefix, tags=["itineraries"])
app.include_router(nlp.router, prefix=prefix, tags=["NLP"])
app.include_router(recommend.router, prefix=prefix, tags=["recommendations"])

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
        return {"db_status": "failed", "error": str(e)}

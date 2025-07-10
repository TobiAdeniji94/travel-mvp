import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.api import users, itinerary
from app.api.nlp import router as nlp_router

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "API active", "version": "0.1.0"}

# Include API routers
app.include_router(users.router)
app.include_router(itinerary.router)
app.include_router(nlp_router)

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

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

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

# -------------------------------------------------------------------
# Database connectivity test
# -------------------------------------------------------------------

# Read your database URL from the environment (set this in .env)
DB_URL = os.getenv("DB_URL", "postgresql://postgres:password@db:5432/traveldb")
engine = create_engine(DB_URL, echo=False, future=True)

@app.get("/test-db")
def test_db():
    try:
        with engine.connect() as conn:
            # simple query to verify connectivity
            conn.execute(text("SELECT 1"))
        return {"db_status": "connected"}
    except SQLAlchemyError as e:
        # return the error text so you can debug
        return {"db_status": "failed", "error": str(e)}

from sqlmodel import SQLModel, Session, create_engine
from app.core.settings import Settings

# Load settings (reads DB_URL from your .env)
settings = Settings()

# Create the SQLModel engine
engine = create_engine(settings.DB_URL, echo=True)

# Dependency for FastAPI: yields a SQLModel Session
def get_session():
    with Session(engine) as session:
        yield session

# Utility to create all tables (call at startup or in init script)
def init_db():
    SQLModel.metadata.create_all(engine)
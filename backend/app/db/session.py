from typing import AsyncGenerator
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.core.settings import Settings

# Load settings (reads DB_URL from .env)
settings = Settings()
database_url: str = settings.DB_URL

if database_url.startswith("postgresql://"):
    async_database_url = database_url.replace(
        "postgresql://", "postgresql+asyncpg://", 1
    )
else:
    async_database_url = database_url

# Create the SQLModel engine
engine: AsyncEngine = create_async_engine(
    async_database_url,
    echo=True,
    future=True,
)

async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

# Utility to create all tables (call at startup)
async def init_db() -> None:
    # runs SQLModel.metadata.create_all synchronously on the async engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

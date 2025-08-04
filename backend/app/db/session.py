"""
Enhanced database session management with connection pooling, health checks, and monitoring
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any
from urllib.parse import urlparse

from sqlmodel import SQLModel, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, DisconnectionError
from sqlalchemy import event

from app.core.settings import Settings

# Configure logging
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Enhanced database manager with connection pooling and health monitoring"""
    
    def __init__(self):
        self.settings = Settings()
        self.engine: Optional[AsyncEngine] = None
        self.async_session: Optional[async_sessionmaker] = None
        self._connection_stats = {
            "total_connections": 0,
            "active_connections": 0,
            "failed_connections": 0,
            "last_health_check": None,
            "health_status": "unknown"
        }
        
    def _prepare_database_url(self) -> str:
        """Prepare and validate database URL"""
        database_url = self.settings.DB_URL
        
        if not database_url:
            raise ValueError("DB_URL environment variable is required")
        
        # Parse URL to validate format
        try:
            parsed = urlparse(database_url)
            if not parsed.scheme:
                raise ValueError("Invalid database URL format")
        except Exception as e:
            logger.error(f"Invalid database URL: {e}")
            raise
        
        # Convert PostgreSQL URL for async support
        if database_url.startswith("postgresql://"):
            async_database_url = database_url.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        elif database_url.startswith("sqlite://"):
            # For SQLite, use aiosqlite
            async_database_url = database_url.replace(
                "sqlite://", "sqlite+aiosqlite://", 1
            )
        else:
            async_database_url = database_url
        
        logger.info(f"Database URL prepared: {parsed.scheme}://{parsed.hostname}:{parsed.port}/{parsed.path.lstrip('/')}")
        return async_database_url
    
    def _create_engine(self) -> AsyncEngine:
        """Create SQLAlchemy async engine with optimized settings"""
        database_url = self._prepare_database_url()
        
        # Engine configuration based on environment
        engine_config = {
            "url": database_url,
            "echo": self.settings.DB_ECHO,
            "future": True,
            "pool_pre_ping": True,  # Validate connections before use
            "pool_recycle": self.settings.DB_POOL_RECYCLE,  # Recycle connections
        }
        
        # Add connection pooling for PostgreSQL
        if "postgresql" in database_url:
            engine_config.update({
                # "poolclass": QueuePool,
                "pool_size": self.settings.DB_POOL_SIZE,
                "max_overflow": self.settings.DB_MAX_OVERFLOW,
                "pool_timeout": self.settings.DB_POOL_TIMEOUT,
                "pool_reset_on_return": "commit",
                "pool_recycle": self.settings.DB_POOL_RECYCLE,
            })
        
        # Create engine
        engine = create_async_engine(**engine_config)
        
        # Add event listeners for monitoring
        self._setup_event_listeners(engine)
        
        logger.info(f"Database engine created with pool_size={self.settings.DB_POOL_SIZE}")
        return engine
    
    def _setup_event_listeners(self, engine: AsyncEngine) -> None:
        """Setup SQLAlchemy event listeners for monitoring"""
        
        @event.listens_for(engine.sync_engine, "connect")
        def on_connect(dbapi_connection, connection_record):
            """Track new connections"""
            self._connection_stats["total_connections"] += 1
            self._connection_stats["active_connections"] += 1
            logger.debug("New database connection established")
        
        @event.listens_for(engine.sync_engine, "close")
        def on_close(dbapi_connection, connection_record):
            """Track closed connections"""
            self._connection_stats["active_connections"] = max(0, self._connection_stats["active_connections"] - 1)
            logger.debug("Database connection closed")
        
        @event.listens_for(engine.sync_engine, "handle_error")
        def on_error(exception_context):
            """Track connection errors"""
            self._connection_stats["failed_connections"] += 1
            logger.error(f"Database connection error: {exception_context.original_exception}")
    
    async def initialize(self) -> None:
        """Initialize database engine and session factory"""
        try:
            self.engine = self._create_engine()
            self.async_session = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False,
            )
            
            # Test initial connection
            await self.health_check()
            logger.info("Database manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {e}")
            raise
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with enhanced error handling"""
        if not self.async_session:
            raise RuntimeError("Database manager not initialized")
        
        start_time = time.time()
        session = None
        
        try:
            session = self.async_session()
            
            # Log session creation time
            creation_time = time.time() - start_time
            if creation_time > 1.0:  # Log slow session creation
                logger.warning(f"Slow session creation: {creation_time:.2f}s")
            
            yield session
            
        except DisconnectionError:
            # Handle database disconnection
            logger.error("Database disconnection detected, attempting recovery")
            self._connection_stats["failed_connections"] += 1
            
            if session:
                await session.rollback()
            raise
            
        except SQLAlchemyError as e:
            # Handle general SQLAlchemy errors
            logger.error(f"Database session error: {e}")
            self._connection_stats["failed_connections"] += 1
            
            if session:
                await session.rollback()
            raise
            
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected session error: {e}")
            
            if session:
                await session.rollback()
            raise
            
        finally:
            if session:
                await session.close()
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions with automatic rollback"""
        async with self.get_session() as session:
            try:
                async with session.begin():
                    yield session
                    # Commit happens automatically if no exception
            except Exception:
                # Rollback happens automatically if exception occurs
                logger.warning("Transaction rolled back due to error")
                raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive database health check"""
        health_info = {
            "status": "healthy",
            "timestamp": time.time(),
            "connection_stats": self._connection_stats.copy(),
            "checks": {}
        }
        
        try:
            # Test basic connectivity
            start_time = time.time()
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                result.scalar()
            
            connection_time = time.time() - start_time
            health_info["checks"]["connectivity"] = {
                "status": "pass",
                "response_time": f"{connection_time:.3f}s"
            }
            
            # Check connection pool status (PostgreSQL only)
            if self.engine and "postgresql" in str(self.engine.url):
                pool = self.engine.pool
                health_info["checks"]["connection_pool"] = {
                    "status": "pass",
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "invalidated": pool.invalidated()
                }
            
            # Update health status
            self._connection_stats["last_health_check"] = time.time()
            self._connection_stats["health_status"] = "healthy"
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health_info["status"] = "unhealthy"
            health_info["error"] = str(e)
            health_info["checks"]["connectivity"] = {
                "status": "fail",
                "error": str(e)
            }
            self._connection_stats["health_status"] = "unhealthy"
        
        return health_info
    
    async def init_db(self) -> None:
        """Initialize database tables with enhanced error handling"""
        if not self.engine:
            raise RuntimeError("Database engine not initialized")
        
        try:
            logger.info("Creating database tables...")
            async with self.engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)
            logger.info("Database tables created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    async def close(self) -> None:
        """Cleanup database connections"""
        if self.engine:
            logger.info("Closing database connections...")
            await self.engine.dispose()
            self.engine = None
            self.async_session = None
            logger.info("Database connections closed")
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get current connection statistics"""
        return self._connection_stats.copy()

# Global database manager instance
db_manager = DatabaseManager()

# Backward compatibility functions
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session (backward compatibility)"""
    async with db_manager.get_session() as session:
        yield session

async def init_db() -> None:
    """Initialize database (backward compatibility)"""
    if not db_manager.engine:
        await db_manager.initialize()
    await db_manager.init_db()

# Expose engine for direct access if needed
def get_engine() -> Optional[AsyncEngine]:
    """Get database engine"""
    return db_manager.engine

# Health check function
async def database_health_check() -> Dict[str, Any]:
    """Check database health"""
    return await db_manager.health_check()

# Connection stats function
def get_database_stats() -> Dict[str, Any]:
    """Get database connection statistics"""
    return db_manager.get_connection_stats()

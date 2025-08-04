"""
Database management API endpoints
Provides health checks, connection stats, and database administration
"""

import logging
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from app.db.session import db_manager, database_health_check, get_database_stats

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health",
    responses={
        200: {"description": "Database is healthy"},
        503: {"description": "Database is unhealthy"}
    },
    summary="Database health check",
    description="Check database connectivity and connection pool status"
)
async def get_database_health():
    """Get comprehensive database health information"""
    try:
        health_info = await database_health_check()
        
        # Return appropriate HTTP status based on health
        if health_info["status"] == "healthy":
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=health_info
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=health_info
            )
            
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "error": "Health check failed",
                "details": str(e)
            }
        )


@router.get("/stats",
    responses={
        200: {"description": "Database connection statistics"},
        500: {"description": "Failed to retrieve statistics"}
    },
    summary="Database statistics",
    description="Get database connection pool statistics and metrics"
)
async def get_database_statistics():
    """Get database connection statistics"""
    try:
        stats = get_database_stats()
        
        # Add additional computed metrics
        stats["computed_metrics"] = {
            "connection_utilization": (
                stats["active_connections"] / 10 * 100  # Assuming pool size of 10
                if stats["active_connections"] > 0 else 0
            ),
            "error_rate": (
                stats["failed_connections"] / max(stats["total_connections"], 1) * 100
                if stats["total_connections"] > 0 else 0
            )
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to retrieve database statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve database statistics"
        )


@router.post("/initialize",
    responses={
        200: {"description": "Database initialized successfully"},
        500: {"description": "Database initialization failed"}
    },
    summary="Initialize database",
    description="Initialize database tables and connections"
)
async def initialize_database():
    """Initialize database (admin endpoint)"""
    try:
        if not db_manager.engine:
            await db_manager.initialize()
        
        await db_manager.init_db()
        
        return {
            "message": "Database initialized successfully",
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database initialization failed: {str(e)}"
        )


@router.post("/close",
    responses={
        200: {"description": "Database connections closed"},
        500: {"description": "Failed to close connections"}
    },
    summary="Close database connections",
    description="Close all database connections (admin endpoint)"
)
async def close_database_connections():
    """Close database connections (admin endpoint)"""
    try:
        await db_manager.close()
        
        return {
            "message": "Database connections closed successfully",
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Failed to close database connections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to close database connections: {str(e)}"
        )


@router.get("/info",
    responses={
        200: {"description": "Database configuration information"},
        500: {"description": "Failed to retrieve information"}
    },
    summary="Database information",
    description="Get database configuration and connection information"
)
async def get_database_info():
    """Get database configuration information"""
    try:
        engine = db_manager.engine
        if not engine:
            return {
                "status": "not_initialized",
                "message": "Database not initialized"
            }
        
        # Get basic database info (without sensitive details)
        db_info = {
            "database_type": str(engine.url).split("://")[0],
            "pool_size": getattr(engine.pool, 'size', lambda: 'N/A')(),
            "pool_timeout": getattr(engine.pool, 'timeout', lambda: 'N/A')(),
            "echo_enabled": engine.echo,
            "connection_stats": get_database_stats(),
            "status": "initialized"
        }
        
        # Add pool-specific info for PostgreSQL
        if hasattr(engine.pool, 'checkedin'):
            db_info["pool_info"] = {
                "checked_in": engine.pool.checkedin(),
                "checked_out": engine.pool.checkedout(),
                "overflow": engine.pool.overflow(),
                "invalidated": engine.pool.invalidated()
            }
        
        return db_info
        
    except Exception as e:
        logger.error(f"Failed to retrieve database info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve database information"
        )
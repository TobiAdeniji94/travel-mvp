"""
Catalog API endpoints for statistics and seeding status
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models import Destination, Activity, Accommodation, Transportation
from app.api.schemas import CatalogStats, SeedingStatus

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/stats", 
    response_model=CatalogStats,
    responses={
        200: {"description": "Catalog statistics retrieved successfully"},
        500: {"description": "Database error"}
    },
    summary="Get catalog statistics",
    description="Retrieve statistics about the travel catalog including counts for all categories"
)
async def get_catalog_stats(
    session: AsyncSession = Depends(get_session)
):
    """Get comprehensive catalog statistics"""
    try:
        # Count all categories
        destinations_count = await session.scalar(
            func.count(Destination.id)
        )
        activities_count = await session.scalar(
            func.count(Activity.id)
        )
        accommodations_count = await session.scalar(
            func.count(Accommodation.id)
        )
        transportations_count = await session.scalar(
            func.count(Transportation.id)
        )
        
        total_items = destinations_count + activities_count + accommodations_count + transportations_count
        
        stats = CatalogStats(
            destinations_count=destinations_count or 0,
            activities_count=activities_count or 0,
            accommodations_count=accommodations_count or 0,
            transportations_count=transportations_count or 0,
            total_items=total_items,
            last_updated=datetime.utcnow()
        )
        
        logger.info(f"Catalog stats retrieved: {total_items} total items")
        return stats
        
    except Exception as e:
        logger.error(f"Error retrieving catalog stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve catalog statistics"
        )

@router.get("/seeding-status",
    response_model=SeedingStatus,
    responses={
        200: {"description": "Seeding status retrieved successfully"},
        500: {"description": "Database error"}
    },
    summary="Get seeding status",
    description="Check if the database has been seeded and get seeding statistics"
)
async def get_seeding_status(
    session: AsyncSession = Depends(get_session)
):
    """Get database seeding status and statistics"""
    try:
        # Count seeded items
        destinations_seeded = await session.scalar(
            func.count(Destination.id)
        )
        activities_seeded = await session.scalar(
            func.count(Activity.id)
        )
        accommodations_seeded = await session.scalar(
            func.count(Accommodation.id)
        )
        transportations_seeded = await session.scalar(
            func.count(Transportation.id)
        )
        
        total_seeded = (destinations_seeded or 0) + (activities_seeded or 0) + \
                      (accommodations_seeded or 0) + (transportations_seeded or 0)
        
        # Check if database is seeded (has at least some data)
        is_seeded = total_seeded > 0
        
        status_info = SeedingStatus(
            is_seeded=is_seeded,
            destinations_seeded=destinations_seeded or 0,
            activities_seeded=activities_seeded or 0,
            accommodations_seeded=accommodations_seeded or 0,
            transportations_seeded=transportations_seeded or 0,
            seeding_errors=0,  # Would need to track this separately
            last_seeding_time=None,  # Would need to track this separately
            seeding_log_file="seed_catalog.log" if is_seeded else None
        )
        
        logger.info(f"Seeding status: {total_seeded} items seeded, is_seeded={is_seeded}")
        return status_info
        
    except Exception as e:
        logger.error(f"Error retrieving seeding status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve seeding status"
        )

@router.get("/destinations/count",
    responses={
        200: {"description": "Destination count retrieved successfully"},
        500: {"description": "Database error"}
    },
    summary="Get destinations count",
    description="Get the total number of destinations in the catalog"
)
async def get_destinations_count(
    session: AsyncSession = Depends(get_session)
):
    """Get destinations count"""
    try:
        count = await session.scalar(func.count(Destination.id))
        return {"count": count or 0}
    except Exception as e:
        logger.error(f"Error retrieving destinations count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve destinations count"
        )

@router.get("/activities/count",
    responses={
        200: {"description": "Activities count retrieved successfully"},
        500: {"description": "Database error"}
    },
    summary="Get activities count",
    description="Get the total number of activities in the catalog"
)
async def get_activities_count(
    session: AsyncSession = Depends(get_session)
):
    """Get activities count"""
    try:
        count = await session.scalar(func.count(Activity.id))
        return {"count": count or 0}
    except Exception as e:
        logger.error(f"Error retrieving activities count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve activities count"
        )

@router.get("/accommodations/count",
    responses={
        200: {"description": "Accommodations count retrieved successfully"},
        500: {"description": "Database error"}
    },
    summary="Get accommodations count",
    description="Get the total number of accommodations in the catalog"
)
async def get_accommodations_count(
    session: AsyncSession = Depends(get_session)
):
    """Get accommodations count"""
    try:
        count = await session.scalar(func.count(Accommodation.id))
        return {"count": count or 0}
    except Exception as e:
        logger.error(f"Error retrieving accommodations count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve accommodations count"
        )

@router.get("/transportations/count",
    responses={
        200: {"description": "Transportations count retrieved successfully"},
        500: {"description": "Database error"}
    },
    summary="Get transportations count",
    description="Get the total number of transportations in the catalog"
)
async def get_transportations_count(
    session: AsyncSession = Depends(get_session)
):
    """Get transportations count"""
    try:
        count = await session.scalar(func.count(Transportation.id))
        return {"count": count or 0}
    except Exception as e:
        logger.error(f"Error retrieving transportations count: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve transportations count"
        ) 
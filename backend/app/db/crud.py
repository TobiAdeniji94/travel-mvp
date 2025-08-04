"""
Simplified CRUD operations that work with the existing database schema
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select, update, delete, and_, or_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    User, Itinerary, Destination, Activity, Accommodation, Transportation,
    Review, ItineraryDestination, ItineraryActivity, 
    ItineraryAccommodation, ItineraryTransportation
)

logger = logging.getLogger(__name__)

# ===== USER CRUD OPERATIONS =====

async def create_user(
    session: AsyncSession,
    username: str,
    email: str,
    password_hash: str,
    preferences: Optional[Dict[str, Any]] = None,
    travel_history: Optional[Dict[str, Any]] = None
) -> User:
    """Create a new user"""
    try:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            preferences=preferences or {},
            travel_history=travel_history or {}
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        logger.info(f"Created user: {username}")
        return user
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating user: {e}")
        raise

async def get_user_by_id(session: AsyncSession, user_id: UUID) -> Optional[User]:
    """Get user by ID"""
    try:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        return None

async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    """Get user by username"""
    try:
        result = await session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting user by username {username}: {e}")
        return None

async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Get user by email"""
    try:
        result = await session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting user by email {email}: {e}")
        return None

async def get_users(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> List[User]:
    """Get users with pagination"""
    try:
        result = await session.execute(
            select(User)
            .offset(skip)
            .limit(limit)
            .order_by(User.created_at)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return []

# ===== ITINERARY CRUD OPERATIONS =====

async def create_itinerary(
    session: AsyncSession,
    name: str,
    start_date: datetime,
    end_date: datetime,
    data: Dict[str, Any],
    user_id: UUID,
    status: str = "draft"
) -> Itinerary:
    """Create a new itinerary"""
    try:
        itinerary = Itinerary(
            name=name,
            start_date=start_date,
            end_date=end_date,
            status=status,
            data=data,
            user_id=user_id
        )
        session.add(itinerary)
        await session.commit()
        await session.refresh(itinerary)
        logger.info(f"Created itinerary: {name}")
        return itinerary
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating itinerary: {e}")
        raise

async def get_itinerary_by_id(session: AsyncSession, itinerary_id: UUID) -> Optional[Itinerary]:
    """Get itinerary by ID with user relationship"""
    try:
        result = await session.execute(
            select(Itinerary)
            .options(selectinload(Itinerary.user))
            .where(Itinerary.id == itinerary_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting itinerary {itinerary_id}: {e}")
        return None

# Legacy function names for compatibility
async def get_itinerary(session: AsyncSession, itinerary_id: UUID) -> Optional[Itinerary]:
    """Legacy function - redirects to get_itinerary_by_id"""
    return await get_itinerary_by_id(session, itinerary_id)

async def get_user_itineraries(
    session: AsyncSession,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100
) -> List[Itinerary]:
    """Get user's itineraries"""
    try:
        result = await session.execute(
            select(Itinerary)
            .where(Itinerary.user_id == user_id)
            .offset(skip)
            .limit(limit)
            .order_by(desc(Itinerary.created_at))
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting itineraries for user {user_id}: {e}")
        return []

# Legacy function name for compatibility
async def get_itineraries(
    session: AsyncSession,
    user_id: UUID,
    skip: int = 0,
    limit: int = 100
) -> List[Itinerary]:
    """Legacy function - redirects to get_user_itineraries"""
    return await get_user_itineraries(session, user_id, skip, limit)

async def update_itinerary(
    session: AsyncSession,
    itinerary_id: UUID,
    **kwargs
) -> Optional[Itinerary]:
    """Update itinerary fields"""
    try:
        await session.execute(
            update(Itinerary)
            .where(Itinerary.id == itinerary_id)
            .values(**kwargs)
        )
        await session.commit()
        
        # Return updated itinerary
        result = await session.execute(
            select(Itinerary).where(Itinerary.id == itinerary_id)
        )
        return result.scalar_one_or_none()
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating itinerary {itinerary_id}: {e}")
        return None

# Legacy function for compatibility
async def update_itinerary_status(
    session: AsyncSession,
    itinerary_id: UUID,
    status: str
) -> Optional[Itinerary]:
    """Legacy function - update itinerary status"""
    return await update_itinerary(session, itinerary_id, status=status)

# ===== CATALOG CRUD OPERATIONS =====

async def get_destinations(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> List[Destination]:
    """Get destinations with pagination"""
    try:
        result = await session.execute(
            select(Destination)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting destinations: {e}")
        return []

async def get_activities(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> List[Activity]:
    """Get activities with pagination"""
    try:
        result = await session.execute(
            select(Activity)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting activities: {e}")
        return []

async def get_accommodations(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> List[Accommodation]:
    """Get accommodations with pagination"""
    try:
        result = await session.execute(
            select(Accommodation)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting accommodations: {e}")
        return []

async def get_transportations(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> List[Transportation]:
    """Get transportations with pagination"""
    try:
        result = await session.execute(
            select(Transportation)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting transportations: {e}")
        return []

# ===== REVIEW CRUD OPERATIONS =====

async def create_review(
    session: AsyncSession,
    rating: int,
    item_id: str,
    user_id: UUID,
    text: Optional[str] = None
) -> Review:
    """Create a new review"""
    try:
        review = Review(
            rating=rating,
            text=text,
            item_id=item_id,
            user_id=user_id
        )
        session.add(review)
        await session.commit()
        await session.refresh(review)
        logger.info(f"Created review for item: {item_id}")
        return review
    except Exception as e:
        await session.rollback()
        logger.error(f"Error creating review: {e}")
        raise

async def get_item_reviews(
    session: AsyncSession,
    item_id: str,
    skip: int = 0,
    limit: int = 100
) -> List[Review]:
    """Get reviews for an item"""
    try:
        result = await session.execute(
            select(Review)
            .where(Review.item_id == item_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Error getting reviews for item {item_id}: {e}")
        return []

# ===== CATALOG STATS =====

async def get_catalog_stats(session: AsyncSession) -> Dict[str, int]:
    """Get catalog statistics"""
    try:
        # Count items in each table
        destinations_count = await session.scalar(select(func.count(Destination.id)))
        activities_count = await session.scalar(select(func.count(Activity.id)))
        accommodations_count = await session.scalar(select(func.count(Accommodation.id)))
        transportations_count = await session.scalar(select(func.count(Transportation.id)))
        
        return {
            "destinations": destinations_count or 0,
            "activities": activities_count or 0,
            "accommodations": accommodations_count or 0,
            "transportations": transportations_count or 0,
            "total": (destinations_count or 0) + (activities_count or 0) + 
                    (accommodations_count or 0) + (transportations_count or 0)
        }
    except Exception as e:
        logger.error(f"Error getting catalog stats: {e}")
        return {
            "destinations": 0,
            "activities": 0,
            "accommodations": 0,
            "transportations": 0,
            "total": 0
        }
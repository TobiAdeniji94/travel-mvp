from typing import List
from uuid import UUID

from fastapi import HTTPException, Depends
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.db.models import User, Itinerary

# USER CRUD
async def create_user(
    user: User,
    session: AsyncSession = Depends(get_session),
) -> User:
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user(
    user_id: UUID, 
    session: AsyncSession = Depends(get_session)
) -> User:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def list_users(
    session: AsyncSession = Depends(get_session)
) -> List[User]:
    result = await session.execute(select(User))
    return result.scalars().all()


# ITINERARY CRUD (example)
async def create_itinerary(
    itin: Itinerary,
    session: AsyncSession = Depends(get_session)
) -> Itinerary:
    session.add(itin)
    await session.commit()
    await session.refresh(itin)
    return itin


async def get_itinerary(
    itin_id: UUID,
    session: AsyncSession = Depends(get_session)
) -> Itinerary:
    itin = await session.get(Itinerary, itin_id)
    if not itin:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return itin

async def get_itineraries(
    session: AsyncSession = Depends(get_session)
) -> List[Itinerary]:
    result = await session.execute(select(Itinerary))
    return result.scalars().all()

async def update_itinerary_status(
    itin_id: UUID,
    status: str,
    session: AsyncSession = Depends(get_session)
) -> Itinerary:
    itin = await get_itinerary(itin_id, session)
    itin.status = status
    session.add(itin)
    await session.commit()
    await session.refresh(itin)
    return itin

async def delete_itinerary(
    itin_id: UUID,
    session: AsyncSession = Depends(get_session)
) -> None:
    itin = await get_itinerary(itin_id, session)
    await session.delete(itin)
    await session.commit()

from uuid import UUID
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import UserCreate, UserRead
from app.db.models import User
from app.db.crud import create_user, get_user, list_users
from app.core.security import get_password_hash, get_current_user
from app.db.session import get_session

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=UserRead)
async def create_user_endpoint(
    payload: UserCreate,
    session: AsyncSession = Depends(get_session)
):
    hashed = get_password_hash(payload.password)

    result = await session.execute(select(User).where(User.email == payload.email))
    if result.scalars().first():
        raise HTTPException(400, "Email already registered")
    
    new_user = User(
        username=payload.username, 
        email=payload.email, 
        password_hash=hashed
    )
    return await create_user(new_user, session)

@router.get("/", response_model=List[UserRead])
async def list_users_endpoint(session: AsyncSession = Depends(get_session)):
    return await list_users(session)

@router.get("/{user_id}", response_model=UserRead)
async def get_user_endpoint(
    user_id: UUID, 
    session: AsyncSession = Depends(get_session)
):
    return await get_user(user_id, session)

@router.patch("/me/preferences", response_model=UserRead, summary="Update user travel preferences")
async def update_preferences(
    prefs: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    current_user.preferences = prefs
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return current_user
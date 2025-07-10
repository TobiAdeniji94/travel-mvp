from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, Session
from typing import List

from app.db.session import get_session
from app.api.schemas import UserCreate
from app.db.models import User
from app.db.crud import create_user, get_user, list_users

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/", response_model=User)
def create_user_endpoint(
    payload: UserCreate,
    session: Session = Depends(get_session)
):
    new_user = User(
        username=payload.username, 
        email=payload.email, 
        password_hash=""
    )
    if not new_user.username or not new_user.email:
        raise HTTPException(status_code=400, detail="Username and email are required")
    if session.exec(select(User).where(User.email == new_user.email)).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    return create_user(new_user, session)

@router.get("/", response_model=List[User])
def list_users_endpoint(session: Session = Depends(get_session)):
    return list_users(session)

@router.get("/{user_id}", response_model=User)
def get_user_endpoint(
    user_id: UUID, 
    session: Session = Depends(get_session)
):
    return get_user(user_id, session)


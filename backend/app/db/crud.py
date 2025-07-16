from typing import List
from uuid import UUID
from fastapi import Depends, HTTPException
from sqlmodel import Session, select

from app.db.session import get_session
from app.db.models import User, Itinerary

# USER CRUD

def create_user(
    user: User, 
    session: Session = Depends(get_session)
) -> User:
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user(
    user_id: UUID, 
    session: Session = Depends(get_session)
) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def list_users(
    session: Session = Depends(get_session)
) -> List[User]:
    users = session.exec(select(User)).all()
    return users

# ITINERARY CRUD (example)

def create_itinerary(
    itin: Itinerary, 
    session: Session = Depends(get_session)
) -> Itinerary:
    session.add(itin)
    session.commit()
    session.refresh(itin)
    return itin


def get_itinerary(
    itin_id: UUID,
    session: Session = Depends(get_session)
) -> Itinerary:
    itin = session.get(Itinerary, itin_id)
    if not itin:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return itin

def update_itinerary_status(
    itin_id: UUID,
    status: str,
    session: Session = Depends(get_session)
) -> Itinerary:
    itin = get_itinerary(itin_id, session)
    itin.status = status
    session.add(itin)
    session.commit()
    session.refresh(itin)
    return itin

def delete_itinerary(
    itin_id: UUID,
    session: Session = Depends(get_session)
) -> None:
    itin = get_itinerary(itin_id, session)
    session.delete(itin)
    session.commit()

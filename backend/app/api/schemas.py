from typing import List
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3)
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters long")

class UserRead(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    preferences: dict | None = None
    travel_history: dict | None = None
    created_at: datetime

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    sub: str | None = None


class ItineraryCreate(BaseModel):
    text: str

class ItineraryUpdate(BaseModel):
    name: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = None

class DestinationRead(BaseModel):
    id: UUID
    name: str
    latitude: float
    longitude: float

    class Config:
        orm_mode = True

class ActivityRead(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    latitude: float
    longitude: float

    class Config:
        orm_mode = True

class ItineraryDestinationRead(BaseModel):
    order: int
    destination: DestinationRead

    class Config:
        orm_mode = True

class ItineraryActivityRead(BaseModel):
    order: int
    activity: ActivityRead
    class Config: orm_mode = True

class ItineraryRead(BaseModel):
    id: UUID
    name: str
    start_date: datetime
    end_date: datetime
    status: str
    data: dict
    
    dest_links: List[ItineraryDestinationRead]
    act_links:  List[ItineraryActivityRead]

    class Config:
        orm_mode = True


from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    username: str
    email:    EmailStr
    # password: str  # in a real app!

class ItineraryCreate(BaseModel):
    text: str  # free-text prompt

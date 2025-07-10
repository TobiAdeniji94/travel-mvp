from fastapi import APIRouter, Depends, HTTPException, Body
from uuid import UUID, uuid4
from datetime import datetime, timezone

from sqlmodel import Session

from app.db.session import get_session
from app.api.schemas import ItineraryCreate
from app.db.models import Itinerary
from app.db.crud import create_itinerary, get_itinerary
from app.core.nlp.parser import parse_travel_request


router = APIRouter(prefix="/itineraries", tags=["itineraries"])

@router.post("/generate", response_model=Itinerary)
async def generate_itinerary(
   payload: ItineraryCreate,
   session: Session = Depends(get_session)
):
   parsed = parse_travel_request(payload.text)

   new_itin = Itinerary(
      id=uuid4(),
      name=parsed["locations"][0] if parsed["locations"] else "My Trip",
      start_date=parsed["dates"][0] if parsed["dates"] else datetime.now(timezone.utc),
      end_date=parsed["dates"][-1]if parsed["dates"] else datetime.now(timezone.utc),
      status="generated",
      data=parsed,
      user_id=UUID("931a7c7e-e600-4148-867d-a729129bfbcb"),
   )
   
   return create_itinerary(new_itin, session)

@router.get("/{itinerary_id}", response_model=Itinerary)
async def read_itinerary(
   itinerary_id: UUID, 
   session: Session = Depends(get_session)
):
   return get_itinerary(itinerary_id, session)

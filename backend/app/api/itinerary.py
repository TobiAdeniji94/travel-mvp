from uuid import UUID, uuid4
from typing import List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, Itinerary
from app.api.schemas import ItineraryCreate, ItineraryUpdate
from app.db.session import get_session
from app.core.security import get_current_user
from app.db.crud import (
   create_itinerary, 
   get_itinerary,
   get_itineraries,
   update_itinerary_status,
   delete_itinerary
)
from app.core.nlp.parser import parse_travel_request


router = APIRouter(prefix="/itineraries", tags=["itineraries"])

@router.post("/generate", response_model=Itinerary)
async def generate_itinerary(
   payload: ItineraryCreate,
   current_user: User = Depends(get_current_user),
   session: AsyncSession = Depends(get_session)
):
   parsed = await run_in_threadpool(parse_travel_request, payload.text)

   new_itin = Itinerary(
      id=uuid4(),
      name=parsed["locations"][0] if parsed["locations"] else "My Trip",
      start_date=parsed["dates"][0] if parsed["dates"] else datetime.now(timezone.utc),
      end_date=parsed["dates"][-1]if parsed["dates"] else datetime.now(timezone.utc),
      status="generated",
      data=parsed,
      user_id=current_user.id
   )
   
   return await create_itinerary(new_itin, session)

@router.get("/{itinerary_id}", response_model=Itinerary)
async def read_itinerary(
   itinerary_id: UUID, 
   current_user: User = Depends(get_current_user),
   session: AsyncSession = Depends(get_session)
):
   itin = await get_itinerary(itinerary_id, session)
   if itin.user_id != current_user.id:
      raise HTTPException(status_code=403, detail="Not authorized to access this itinerary")
   
   return itin

@router.get("/", response_model=List[Itinerary])
async def list_itineraries(
   current_user: User = Depends(get_current_user),
   session: AsyncSession = Depends(get_session)
):
   itineraries = await get_itineraries(session)
   return [itin for itin in itineraries if itin.user_id == current_user.id]


@router.patch("/{itinerary_id}", response_model=Itinerary)
async def patch_itinerary_status(
   itinerary_id: UUID,
   payload: ItineraryUpdate,
   current_user: User = Depends(get_current_user),
   session: AsyncSession = Depends(get_session)
):
   itin = await get_itinerary(itinerary_id, session)
   if itin.user_id != current_user.id:
      raise HTTPException(status_code=403, detail="Not authorized to update this itinerary")
   return await update_itinerary_status(itinerary_id, payload.status, session)

@router.delete("/{itinerary_id}", status_code=204)
async def remove_itinerary(
   itinerary_id: UUID,
   current_user: User = Depends(get_current_user),
   session: AsyncSession = Depends(get_session)
):
   itin = await get_itinerary(itinerary_id, session)
   if itin.user_id != current_user.id:
      raise HTTPException(status_code=403, detail="Not authorized to delete this itinerary")
   await delete_itinerary(itinerary_id, session)
   return Response(status_code=204)


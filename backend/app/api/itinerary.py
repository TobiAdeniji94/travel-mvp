from uuid import UUID, uuid4
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

import pickle
import scipy.sparse
from sklearn.metrics.pairwise import cosine_similarity

from app.db.models import (
   User, 
   Itinerary, 
   ItineraryDestination, 
   Destination,
   Activity,
   ItineraryActivity
)
from app.core.itinerary_optimizer import DestCoord, greedy_route
from app.api.schemas import (
   ItineraryCreate, 
   ItineraryUpdate, 
   ItineraryRead
)
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

# Destination TF-IDF artifacts
DEST_VEC = "/app/models/tfidf_vectorizer_dest.pkl"
DEST_MAT = "/app/models/tfidf_matrix_dest.npz"
DEST_MAP = "/app/models/item_index_map_dest.pkl"
vectorizer    = pickle.load(open(DEST_VEC,   "rb"))
item_matrix   = scipy.sparse.load_npz(DEST_MAT)
DEST_ID_MAP   = pickle.load(open(DEST_MAP, "rb"))

async def get_destination_ids(interests: List[str], budget: Optional[float]):
   q      = " ".join(interests or []) + f" budget {budget or 0}"
   v      = vectorizer.transform([q])
   print(f"Destination Query vector: {v}")
   scores = cosine_similarity(v, item_matrix).flatten()
   print(f"Destination scores: {scores}")
   top    = scores.argsort()[::-1][:10]
   print(f"Top destination indices: {top}")
   return [DEST_ID_MAP[i] for i in top]

# Activity TF-IDF artifacts
ACT_VEC  = "/app/models/tfidf_vectorizer_act.pkl"
ACT_MAT  = "/app/models/tfidf_matrix_act.npz"
ACT_MAP  = "/app/models/item_index_map_act.pkl"
act_vectorizer = pickle.load(open(ACT_VEC,   "rb"))
act_matrix     = scipy.sparse.load_npz(ACT_MAT)
ACT_ID_MAP     = pickle.load(open(ACT_MAP, "rb"))


async def get_activity_ids(interests: List[str], budget: Optional[float]):
   q      = " ".join(interests or []) + f" budget {budget or 0}"
   # TODO: find out what this .transform() does?
   v      = act_vectorizer.transform([q])
   print(f"Activity Query vector: {v}")
   scores = cosine_similarity(v, act_matrix).flatten()
   print(f"Activity scores: {scores}")
   top    = scores.argsort()[::-1][:10]
   print(f"Top activity indices: {top}")
   rank = [ACT_ID_MAP[i] for i in top]
   return rank

@router.post("/generate", response_model=ItineraryRead)
async def generate_itinerary(
   payload: ItineraryCreate,
   current_user: User = Depends(get_current_user),
   session: AsyncSession = Depends(get_session)
):
   parsed = await run_in_threadpool(parse_travel_request, payload.text)

   dates      = parsed.get("dates") or [datetime.now(timezone.utc)]
   start_date = dates[0]
   end_date   = dates[-1]
   parsed["dates"] = [d.isoformat() for d in dates]
   locations  = parsed.get("locations") or ["My Trip"]
   name       = locations[0]
   interests = parsed.get("interests") or current_user.preferences.get("interests", [])
   budget    = parsed.get("budget") or current_user.preferences.get("budget")
   
   itin_id = uuid4()
   new_itin = Itinerary(
      id=itin_id,
      name=name,
      start_date=start_date,
      end_date=end_date,
      status="generated",
      data=parsed,
      user_id=current_user.id
   )
   session.add(new_itin)
   await session.commit()

   # Get top destinations based on interests and budget
   dest_ids = await get_destination_ids(interests, budget)
   stmt = select(Destination.id, Destination.latitude, Destination.longitude)\
           .where(Destination.id.in_(dest_ids))
   rows = (await session.execute(stmt)).all()
   dest_coords = [DestCoord(i, lat, lon) for i, lat, lon in rows]
   for idx, dc in enumerate(greedy_route(dest_coords), start=1):
      session.add(ItineraryDestination(
         itinerary_id=itin_id,
         destination_id=dc.id,
         order=idx,
      ))
   await session.commit()

   # Get top activities based on interests and budget
   act_ids = await get_activity_ids(interests, budget)
   stmt2 = select(Activity.id, Activity.latitude, Activity.longitude)\
            .where(Activity.id.in_(act_ids))
   rows2 = (await session.execute(stmt2)).all()
   act_coords = [DestCoord(i, lat, lon) for i, lat, lon in rows2]
   for idx, ac in enumerate(greedy_route(act_coords), start=1):
      session.add(ItineraryActivity(
         itinerary_id=itin_id,
         activity_id=ac.id,
         order=idx,
      ))
   await session.commit()

   stmt = (
      select(Itinerary).options(
         selectinload(Itinerary.dest_links)
         .selectinload(ItineraryDestination.destination),
         selectinload(Itinerary.act_links)
         .selectinload(ItineraryActivity.activity),
      )
      .where(Itinerary.id == itin_id)
   )
   full_itin = (await session.execute(stmt)).scalar_one()
   return full_itin

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


from uuid import UUID, uuid4
from typing import List, Optional
from datetime import datetime, timezone, time, timedelta
import logging
import time
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from fastapi.encoders import jsonable_encoder
from fastapi.concurrency import run_in_threadpool
from geoalchemy2 import Geography
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from slowapi import Limiter
from slowapi.util import get_remote_address

import pickle, scipy.sparse
from sklearn.metrics.pairwise import cosine_similarity

from app.db.models import (
   User, Itinerary, ItineraryDestination, Destination, Activity, 
   ItineraryActivity, Accommodation, ItineraryAccommodation, 
   Transportation, ItineraryTransportation
)
from app.core.itinerary_optimizer import DestCoord, POI, time_aware_greedy_route
from app.api.schemas import ItineraryCreate, ItineraryUpdate, ItineraryRead
from app.db.session import get_session
from app.core.security import get_current_user
from app.db.crud import (
   create_itinerary, 
   get_itinerary,
   get_itineraries,
   update_itinerary_status,
   update_itinerary
)
from app.core.nlp.parser import parse_travel_request

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/itineraries", tags=["itineraries"])

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Pace presets
PACING = {
    "relaxed":  {"daily_activities": 2, "max_hours": 4},
    "moderate": {"daily_activities": 4, "max_hours": 8},
    "intense":  {"daily_activities": 6, "max_hours": 12},
}

@asynccontextmanager
async def performance_timer(operation: str):
    """Context manager for timing operations"""
    start = time.time()
    try:
        yield
    finally:
        duration = time.time() - start
        logger.info(f"{operation} completed in {duration:.2f}s")

def parse_opening_hours(oh: str):
    """HH:MM-HH:MM" -> (time, time)"""
    try:
        o, c = oh.split("-")
        return time.fromisoformat(o), time.fromisoformat(c)
    except (ValueError, AttributeError) as e:
        logger.warning(f"Invalid opening hours format: {oh}, using default 9:00-17:00")
        return time(9, 0), time(17, 0)

# ML Model loading with error handling
def load_ml_models():
    """Load ML models with proper error handling"""
    try:
        # Destination TF-IDF artifacts
        dest_vectorizer = pickle.load(open("/app/models/tfidf_vectorizer_dest.pkl", "rb"))
        dest_matrix = scipy.sparse.load_npz("/app/models/tfidf_matrix_dest.npz")
        dest_id_map = pickle.load(open("/app/models/item_index_map_dest.pkl", "rb"))
        
        # Activity TF-IDF artifacts
        act_vectorizer = pickle.load(open("/app/models/tfidf_vectorizer_act.pkl", "rb"))
        act_matrix = scipy.sparse.load_npz("/app/models/tfidf_matrix_act.npz")
        act_id_map = pickle.load(open("/app/models/item_index_map_act.pkl", "rb"))
        
        # Accommodation TF-IDF artifacts
        acc_vectorizer = pickle.load(open("/app/models/tfidf_vectorizer_acc.pkl", "rb"))
        acc_matrix = scipy.sparse.load_npz("/app/models/tfidf_matrix_acc.npz")
        acc_id_map = pickle.load(open("/app/models/item_index_map_acc.pkl", "rb"))
        
        # Transportation TF-IDF artifacts
        trans_vectorizer = pickle.load(open("/app/models/tfidf_vectorizer_trans.pkl", "rb"))
        trans_matrix = scipy.sparse.load_npz("/app/models/tfidf_matrix_trans.npz")
        trans_id_map = pickle.load(open("/app/models/item_index_map_trans.pkl", "rb"))
        
        return {
            'dest': (dest_vectorizer, dest_matrix, dest_id_map),
            'act': (act_vectorizer, act_matrix, act_id_map),
            'acc': (acc_vectorizer, acc_matrix, acc_id_map),
            'trans': (trans_vectorizer, trans_matrix, trans_id_map)
        }
    except Exception as e:
        logger.error(f"Failed to load ML models: {e}")
        raise HTTPException(status_code=500, detail="ML service unavailable")

# Load ML models at module level
try:
    ML_MODELS = load_ml_models()
except Exception as e:
    logger.error(f"Failed to initialize ML models: {e}")
    ML_MODELS = None

async def get_destination_ids(interests: List[str], budget: Optional[float]):
    """Get destination recommendations using ML models"""
    if not ML_MODELS:
        raise HTTPException(status_code=500, detail="ML models not available")
    
    try:
        vectorizer, item_matrix, id_map = ML_MODELS['dest']
        q = " ".join(interests or []) + f" budget {budget or 0}"
        v = vectorizer.transform([q])
        scores = cosine_similarity(v, item_matrix).flatten()
        top = scores.argsort()[::-1][:10]
        
        logger.info("Destination recommendations generated", extra={
            "query": q,
            "top_scores": scores[top].tolist(),
            "top_indices": top.tolist()
        })
        
        return [id_map[i] for i in top]
    except Exception as e:
        logger.error(f"Error getting destination recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get destination recommendations")

async def get_activity_ids(interests: List[str], budget: Optional[float]):
    """Get activity recommendations using ML models"""
    if not ML_MODELS:
        raise HTTPException(status_code=500, detail="ML models not available")
    
    try:
        vectorizer, item_matrix, id_map = ML_MODELS['act']
        q = " ".join(interests or []) + f" budget {budget or 0}"
        v = vectorizer.transform([q])
        scores = cosine_similarity(v, item_matrix).flatten()
        top = scores.argsort()[::-1][:10]
        
        logger.info("Activity recommendations generated", extra={
            "query": q,
            "top_scores": scores[top].tolist(),
            "top_indices": top.tolist()
        })
        
        return [id_map[i] for i in top]
    except Exception as e:
        logger.error(f"Error getting activity recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get activity recommendations")

async def get_accommodation_ids(interests: List[str], budget: Optional[float]):
    """Get accommodation recommendations using ML models"""
    if not ML_MODELS:
        raise HTTPException(status_code=500, detail="ML models not available")
    
    try:
        vectorizer, item_matrix, id_map = ML_MODELS['acc']
        q = " ".join(interests or []) + f" budget {budget or 0}"
        v = vectorizer.transform([q])
        scores = cosine_similarity(v, item_matrix).flatten()
        top = scores.argsort()[::-1][:10]
        
        return [id_map[i] for i in top if scores[i] > 0]
    except Exception as e:
        logger.error(f"Error getting accommodation recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get accommodation recommendations")

async def get_transportation_ids(interests: List[str], budget: Optional[float]):
    """Get transportation recommendations using ML models"""
    if not ML_MODELS:
        raise HTTPException(status_code=500, detail="ML models not available")
    
    try:
        vectorizer, item_matrix, id_map = ML_MODELS['trans']
        q = " ".join(interests or []) + f" budget {budget or 0}"
        v = vectorizer.transform([q])
        scores = cosine_similarity(v, item_matrix).flatten()
        top = scores.argsort()[::-1][:10]
        
        return [id_map[i] for i in top if scores[i] > 0]
    except Exception as e:
        logger.error(f"Error getting transportation recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get transportation recommendations")

class ItineraryService:
    """Service class to handle itinerary generation logic"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def parse_travel_request(self, text: str):
        """Parse travel request with error handling"""
        try:
            text = text.replace("–", "-")
            parsed = await run_in_threadpool(parse_travel_request, text)
            logger.info("Travel request parsed successfully", extra={"parsed_data": parsed})
            return parsed
        except Exception as e:
            logger.error(f"Failed to parse travel request: {e}")
            raise HTTPException(status_code=400, detail="Invalid travel request format")
    
    async def process_dates(self, raw_dates: List):
        """Process and validate dates"""
        try:
            def ensure_dt(d):
                return d if isinstance(d, datetime) else datetime.fromisoformat(d)

            if len(raw_dates) == 2:
                start, end = ensure_dt(raw_dates[0]), ensure_dt(raw_dates[1])
                dates = [
                    (start + timedelta(days=i)).isoformat()
                    for i in range((end - start).days + 1)
                ]
            else:
                dates = [
                    (d.isoformat() if isinstance(d, datetime) else d)
                    for d in raw_dates
                ]
            
            return [datetime.fromisoformat(d) for d in dates]
        except Exception as e:
            logger.error(f"Failed to process dates: {e}")
            raise HTTPException(status_code=400, detail="Invalid date format")
    
    async def get_location_coordinates(self, dest_city: str, origin_city: Optional[str] = None):
        """Get coordinates for destination and origin cities"""
        try:
            dest_row = await self.session.scalar(select(Destination).where(Destination.name == dest_city))
            origin_row = await self.session.scalar(select(Destination).where(Destination.name == origin_city)) if origin_city else None
            
            if not dest_row:
                raise HTTPException(status_code=404, detail=f"Destination '{dest_city}' not found")
            if origin_city and not origin_row:
                raise HTTPException(status_code=404, detail=f"Origin '{origin_city}' not found")
            
            dest_center_lat, dest_center_lon = dest_row.latitude, dest_row.longitude
            origin_center_lat, origin_center_lon = origin_row.latitude, origin_row.longitude if origin_row else (None, None)
            
            logger.info("Location coordinates retrieved", extra={
                "dest_city": dest_city,
                "dest_coords": (dest_center_lat, dest_center_lon),
                "origin_city": origin_city,
                "origin_coords": (origin_center_lat, origin_center_lon) if origin_city else None
            })
            
            return {
                'dest': (dest_center_lat, dest_center_lon),
                'origin': (origin_center_lat, origin_center_lon) if origin_city else None
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get location coordinates: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve location coordinates")
    
    async def get_flight_options(self, origin_coords, dest_coords, start_date, end_date, radius_km=50):
        """Get flight options within specified radius"""
        try:
            if not origin_coords or not dest_coords:
                return []
            
            origin_lat, origin_lon = origin_coords
            dest_lat, dest_lon = dest_coords
            
            origin_pt = func.ST_SetSRID(
                func.ST_MakePoint(origin_lon, origin_lat), 4326
            ).cast(Geography)
            dest_pt = func.ST_SetSRID(
                func.ST_MakePoint(dest_lon, dest_lat), 4326
            ).cast(Geography)
            
            origin_radius_m = radius_km * 1000
            dest_radius_m = radius_km * 1000
            
            dep_geom = func.ST_SetSRID(
                func.ST_MakePoint(Transportation.departure_long, Transportation.departure_lat),
                4326
            ).cast(Geography)
            arr_geom = func.ST_SetSRID(
                func.ST_MakePoint(Transportation.arrival_long, Transportation.arrival_lat),
                4326
            ).cast(Geography)
            
            flight_start = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            flight_end = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            flight_stmt = (
                select(Transportation.id)
                .where(
                    func.ST_DWithin(dep_geom, origin_pt, origin_radius_m),
                    func.ST_DWithin(arr_geom, dest_pt, dest_radius_m),
                    Transportation.departure_time >= flight_start,
                    Transportation.arrival_time <= flight_end,
                ).limit(10)
            )
            
            result = await self.session.execute(flight_stmt)
            trans_ids = [row[0] for row in result.all()]
            
            logger.info(f"Found {len(trans_ids)} flight options")
            return trans_ids
        except Exception as e:
            logger.error(f"Failed to get flight options: {e}")
            return []
    
    async def build_poi_list(self, dest_ids, act_ids, acc_ids, trans_ids, start_date, center_pt, radius_m, budget):
        """Build list of Points of Interest for scheduling"""
        try:
            all_pois = []
            
            # Get destinations
            geom_dest = func.ST_SetSRID(
                func.ST_MakePoint(Destination.longitude, Destination.latitude),
                4326
            ).cast(Geography)
            dest_stmt = (
                select(Destination.id, Destination.latitude, Destination.longitude)
                .where(
                    Destination.id.in_(dest_ids),
                    func.ST_DWithin(geom_dest, center_pt, radius_m)
                )
            )
            dest_rows = (await self.session.execute(dest_stmt)).all()
            
            for _id, lat, lon in dest_rows:
                all_pois.append(POI(
                    id=_id, latitude=lat, longitude=lon,
                    opens=datetime.combine(start_date.date(), time(9, 0), tzinfo=start_date.tzinfo),
                    closes=datetime.combine(start_date.date(), time(17, 0), tzinfo=start_date.tzinfo),
                    duration=120, type="destination", price=None,
                ))
            
            # Get activities
            geom_act = func.ST_SetSRID(
                func.ST_MakePoint(Activity.longitude, Activity.latitude),
                4326
            ).cast(Geography)
            act_stmt = (
                select(Activity.id, Activity.latitude, Activity.longitude, 
                       Activity.opening_hours, Activity.price)
                .where(
                    Activity.id.in_(act_ids),
                    func.ST_DWithin(geom_act, center_pt, radius_m)
                )
            )
            act_rows = (await self.session.execute(act_stmt)).all()
            
            for _id, lat, lon, oh, price in act_rows:
                o, c = parse_opening_hours(oh or "")
                all_pois.append(POI(
                    id=_id, latitude=lat, longitude=lon,
                    opens=datetime.combine(start_date.date(), o, tzinfo=start_date.tzinfo),
                    closes=datetime.combine(start_date.date(), c, tzinfo=start_date.tzinfo),
                    duration=60, type="activity",
                    price=price if price is not None else 0.0,
                ))
            
            # Get accommodations
            geom_acc = func.ST_SetSRID(
                func.ST_MakePoint(Accommodation.longitude, Accommodation.latitude),
                4326
            ).cast(Geography)
            acc_stmt = (
                select(Accommodation.id, Accommodation.latitude, 
                       Accommodation.longitude, Accommodation.price)
                .where(
                    Accommodation.rating >= 3.5,
                    func.ST_DWithin(geom_acc, center_pt, radius_m)
                )
                .order_by(Accommodation.rating.desc())
                .limit(30)  # Increased limit for better selection
            )
            acc_rows = (await self.session.execute(acc_stmt)).all()
            
            for _id, lat, lon, price in acc_rows:
                all_pois.append(POI(
                    id=_id, latitude=lat, longitude=lon,
                    opens=datetime.combine(start_date.date(), time(0, 0), tzinfo=start_date.tzinfo),
                    closes=datetime.combine(start_date.date(), time(23, 59), tzinfo=start_date.tzinfo),
                    duration=0, type="accommodation",
                    price=price if price is not None else 0.0,
                ))
            
            # Get transportation
            if trans_ids:
                trans_stmt = select(
                    Transportation.id, Transportation.departure_lat, Transportation.departure_long,
                    Transportation.arrival_lat, Transportation.arrival_long,
                    Transportation.departure_time, Transportation.arrival_time,
                    Transportation.price
                ).where(Transportation.id.in_(trans_ids))
                
                trans_rows = (await self.session.execute(trans_stmt)).all()
                for (_id, dlat, dlon, alat, alon, dt, at, price) in trans_rows:
                    dur_min = int((at - dt).total_seconds() / 60)
                    all_pois.append(POI(
                        id=_id, latitude=dlat, longitude=dlon,
                        opens=dt.astimezone(start_date.tzinfo), 
                        closes=at.astimezone(start_date.tzinfo),
                        duration=dur_min, type="transportation",
                        price=price if price is not None else 0.0
                    ))
            
            # Filter by budget
            all_pois = [
                poi for poi in all_pois
                if not (poi.type == "activity" and poi.price is not None and poi.price > budget * 0.1)
            ]
            
            logger.info(f"Built POI list with {len(all_pois)} items")
            return all_pois
        except Exception as e:
            logger.error(f"Failed to build POI list: {e}")
            raise HTTPException(status_code=500, detail="Failed to build itinerary items")
    
    async def create_itinerary_schedule(self, all_pois, trip_days, start_date, pace):
        """Create day-by-day itinerary schedule"""
        try:
            base_loc = DestCoord(id=None, latitude=all_pois[0].latitude, longitude=all_pois[0].longitude)
            scheduled_items = []
            
            for day in range(trip_days):
                day_start = datetime.combine(start_date + timedelta(days=day), time(9, 0), tzinfo=start_date.tzinfo)
                day_end = day_start + timedelta(hours=pace["max_hours"])
                
                today = time_aware_greedy_route(
                    start_point=base_loc,
                    pois=all_pois,
                    day_start=day_start,
                    day_end=day_end
                )[:pace["daily_activities"]]
                
                scheduled_items.append(today)
                
                # Update base location and remove scheduled items
                scheduled = {p.id for p in today}
                all_pois = [p for p in all_pois if p.id not in scheduled]
                if today:
                    last = today[-1]
                    base_loc = DestCoord(last.id, last.latitude, last.longitude)
            
            logger.info(f"Created schedule for {trip_days} days")
            return scheduled_items
        except Exception as e:
            logger.error(f"Failed to create itinerary schedule: {e}")
            raise HTTPException(status_code=500, detail="Failed to create itinerary schedule")
    
    async def persist_itinerary(self, itin_id, scheduled_items, parsed_data, user_id):
        """Persist itinerary and its items to database"""
        try:
            # Create itinerary
            new_itin = Itinerary(
                id=itin_id,
                name=parsed_data.get("locations", ["My Trip"])[0],
                start_date=parsed_data["dates"][0],
                end_date=parsed_data["dates"][-1],
                status="generated",
                data=jsonable_encoder(parsed_data),
                user_id=user_id
            )
            self.session.add(new_itin)
            
            # Persist scheduled items
            for day_idx, day_items in enumerate(scheduled_items):
                for order, poi in enumerate(day_items, start=1):
                    if poi.type == "destination":
                        self.session.add(ItineraryDestination(
                            itinerary_id=itin_id, destination_id=poi.id, order=order
                        ))
                    elif poi.type == "activity":
                        self.session.add(ItineraryActivity(
                            itinerary_id=itin_id, activity_id=poi.id, order=order
                        ))
                    elif poi.type == "accommodation":
                        self.session.add(ItineraryAccommodation(
                            itinerary_id=itin_id, accommodation_id=poi.id, order=order
                        ))
                    else:  # transportation
                        self.session.add(ItineraryTransportation(
                            itinerary_id=itin_id, transportation_id=poi.id, order=order
                        ))
            
            await self.session.commit()
            
            # Return full itinerary with relationships
            full_itin = (await self.session.execute(
                select(Itinerary)
                .where(Itinerary.id == itin_id)
                .options(
                    selectinload(Itinerary.dest_links).selectinload(ItineraryDestination.destination),
                    selectinload(Itinerary.act_links).selectinload(ItineraryActivity.activity),
                    selectinload(Itinerary.accom_links).selectinload(ItineraryAccommodation.accommodation),
                    selectinload(Itinerary.trans_links).selectinload(ItineraryTransportation.transportation),
                )
            )).scalar_one()
            
            logger.info(f"Itinerary {itin_id} persisted successfully")
            return full_itin
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to persist itinerary: {e}")
            raise HTTPException(status_code=500, detail="Failed to save itinerary")

@router.post("/generate", 
    response_model=ItineraryRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid request format or parameters"},
        404: {"description": "No recommendations found for given criteria"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "ML service unavailable or internal error"}
    },
    summary="Generate personalized travel itinerary",
    description="Creates a complete travel itinerary based on natural language request"
)
@limiter.limit("5/minute")
async def generate_itinerary(
    request: Request,
    payload: ItineraryCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Generate a personalized travel itinerary"""
    async with performance_timer("itinerary_generation"):
        try:
            service = ItineraryService(session)
            
            # Parse travel request
            parsed = await service.parse_travel_request(payload.text)
            
            # Process dates
            raw_dates = parsed.get("dates", [])
            dates = await service.process_dates(raw_dates)
            start_date, end_date = dates[0], dates[-1]
            trip_days = len(dates)
            
            # Extract parameters
            locations = parsed.get("locations") or ["My Trip"]
            dest_city = locations[0]
            origin_city = locations[-2] if len(locations) >= 2 else None
            interests = parsed.get("interests") or current_user.preferences.get("interests", [])
            budget = parsed.get("budget") or current_user.preferences.get("budget", 1000)
            
            # Get pace settings
            pace_key = parsed.get("pace") or current_user.preferences.get("pace", "moderate")
            pace = PACING.get(pace_key, PACING["moderate"])
            
            # Get location coordinates
            coords = await service.get_location_coordinates(dest_city, origin_city)
            dest_center_lat, dest_center_lon = coords['dest']
            origin_coords = coords['origin']
            
            # Get recommendations
            dest_ids = await get_destination_ids(interests, budget)
            act_ids = await get_activity_ids(interests, budget)
            acc_ids = await get_accommodation_ids(interests, budget)
            
            # Get flight options
            trans_ids = await service.get_flight_options(
                origin_coords, coords['dest'], start_date, end_date
            )
            if not trans_ids:
                trans_ids = await get_transportation_ids(interests, budget)
            
            # Build POI list
            radius_km = parsed.get("radius_km", 20)
            radius_m = radius_km * 1000
            center_pt = func.ST_SetSRID(
                func.ST_MakePoint(dest_center_lon, dest_center_lat), 4326
            ).cast(Geography)
            
            all_pois = await service.build_poi_list(
                dest_ids, act_ids, acc_ids, trans_ids, start_date, center_pt, radius_m, budget
            )
            
            if not all_pois:
                raise HTTPException(
                    status_code=404,
                    detail="No itinerary items could be scheduled for these preferences."
                )
            
            # Create schedule
            scheduled_items = await service.create_itinerary_schedule(
                all_pois, trip_days, start_date, pace
            )
            
            # Persist itinerary
            itin_id = uuid4()
            full_itin = await service.persist_itinerary(itin_id, scheduled_items, parsed, current_user.id)
            
            logger.info(f"Successfully generated itinerary {itin_id} for user {current_user.id}")
            return full_itin
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in itinerary generation: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate itinerary")

@router.get("/{itinerary_id}", response_model=Itinerary)
@limiter.limit("60/minute")
async def read_itinerary(
    request: Request,
    itinerary_id: UUID, 
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    itin = await get_itinerary(itinerary_id, session)
    if itin.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this itinerary")
    
    return itin

@router.get("/", response_model=List[Itinerary])
@limiter.limit("30/minute")
async def list_itineraries(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    itineraries = await get_itineraries(session)
    return [itin for itin in itineraries if itin.user_id == current_user.id]


@router.patch("/{itinerary_id}", response_model=Itinerary)
@limiter.limit("30/minute")
async def patch_itinerary_status(
    request: Request,
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
@limiter.limit("10/minute")
async def remove_itinerary(
    request: Request,
    itinerary_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    itin = await get_itinerary(itinerary_id, session)
    if itin.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this itinerary")
    await delete_itinerary(itinerary_id, session)
    return Response(status_code=204)


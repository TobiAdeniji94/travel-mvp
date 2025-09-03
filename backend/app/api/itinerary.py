from uuid import UUID, uuid4
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from datetime import time as TimeOfDay
import time
import logging
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
from app.api.schemas import (
   ItineraryCreate, ItineraryUpdate, ItineraryRead,
   ReorderPreviewRequest, ReorderPreviewResponse,
   ItineraryDestinationRead, ItineraryActivityRead, 
   ItineraryAccommodationRead, ItineraryTransportationRead,
   RegenerateDayRequest, ShareLinkCreateResponse,
)
from app.db.session import get_db_session
from app.core.security import get_current_user
from app.db.crud import (
   create_itinerary, 
   get_itinerary,
   get_itineraries,
   get_user_itineraries,
   update_itinerary_status,
   update_itinerary
)
from app.core.nlp.parser import parse_travel_request
from app.core.settings import Settings
from app.ml.inference import reorder_pois

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/itineraries", tags=["itineraries"])

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# In-memory public share tokens (replace with DB in production)
_SHARE_LINKS: dict[str, dict] = {}

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
        return TimeOfDay.fromisoformat(o), TimeOfDay.fromisoformat(c)
    except (ValueError, AttributeError) as e:
        logger.warning(f"Invalid opening hours format: {oh}, using default 9:00-17:00")
        return TimeOfDay(9, 0), TimeOfDay(17, 0)

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
        # Try a case‐insensitive partial match for destination
        dest_stmt = (
            select(Destination)
            .where(Destination.name.ilike(f"%{dest_city}%"))
            .order_by(Destination.popularity_score.desc())  # choose most popular if many
            .limit(1)
        )
        dest_row = (await self.session.execute(dest_stmt)).scalar_one_or_none()
        if not dest_row:
            raise HTTPException(status_code=404, detail=f"No destination found matching '{dest_city}'")

        # Same for origin if provided
        origin_row = None
        if origin_city:
            origin_stmt = (
                select(Destination)
                .where(Destination.name.ilike(f"%{origin_city}%"))
                .order_by(Destination.popularity_score.desc())
                .limit(1)
            )
            origin_row = (await self.session.execute(origin_stmt)).scalar_one_or_none()
            if not origin_row:
                raise HTTPException(status_code=404, detail=f"No origin found matching '{origin_city}'")

        # Build coords dict
        coords = {
            'dest':   (dest_row.latitude, dest_row.longitude),
            'origin': (origin_row.latitude, origin_row.longitude) if origin_row else None
        }
        logger.info("Location coordinates retrieved", extra={"coords": coords})
        return coords
    
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
    
    async def build_poi_list(self, dest_ids, act_ids, acc_ids, trans_ids, start_date, center_lat, 
                             center_lon, radius_m, budget):
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
                    func.ST_DWithin(geom_dest, func.ST_SetSRID(func.ST_MakePoint(center_lon, center_lat), 4326)
                                    .cast(Geography), radius_m)
                )
            )
            dest_rows = (await self.session.execute(dest_stmt)).all()
            
            for _id, lat, lon in dest_rows:
                all_pois.append(POI(
                    id=_id, latitude=lat, longitude=lon,
                    opens=datetime.combine(start_date.date(), TimeOfDay(9, 0), tzinfo=start_date.tzinfo),
                    closes=datetime.combine(start_date.date(), TimeOfDay(17, 0), tzinfo=start_date.tzinfo),
                    duration=120, type="destination", price=None,
                ))
            
            # Get activities
            geom_act = func.ST_SetSRID(
                func.ST_MakePoint(Activity.longitude, Activity.latitude),
                4326
            ).cast(Geography)
            act_stmt = (
                select(
                    Activity.id,
                    Activity.name,
                    Activity.latitude,
                    Activity.longitude,
                    Activity.opening_hours,
                    Activity.price,
                )
                .where(
                    Activity.id.in_(act_ids),
                    func.ST_DWithin(
                        geom_act,
                        func.ST_SetSRID(func.ST_MakePoint(center_lon, center_lat), 4326).cast(Geography),
                        radius_m,
                    ),
                )
            )
            act_rows = (await self.session.execute(act_stmt)).all()
            logger.info(f"Recommended activity IDs: {act_ids}")
            logger.info(f"Fetched {len(act_rows)} activity rows: {[row[0] for row in act_rows]}")
            logger.info(f"Activity location filter: center=({center_lat},{center_lon}), radius_m={radius_m}")

            # Name/location-based dedup to avoid visually repeated activities with different IDs
            seen_activity_keys = set()
            for _id, name, lat, lon, oh, price in act_rows:
                name_norm = (name or "").strip().lower()
                loc_key = (round(lat or 0.0, 3), round(lon or 0.0, 3))  # ~100m grid
                dedup_key = (name_norm, loc_key)
                if name_norm:  # only apply when we actually have a name
                    if dedup_key in seen_activity_keys:
                        logger.info(
                            f"Skipping duplicate activity by name/loc: name='{name_norm}', lat={lat}, lon={lon}, id={_id}"
                        )
                        continue
                    seen_activity_keys.add(dedup_key)

                o, c = parse_opening_hours(oh or "")
                logger.info(f"Adding activity POI: id={_id}, name='{name}', lat={lat}, lon={lon}, price={price}")
                all_pois.append(POI(
                    id=_id, latitude=lat, longitude=lon,
                    opens=datetime.combine(start_date.date(), o, tzinfo=start_date.tzinfo),
                    closes=datetime.combine(start_date.date(), c, tzinfo=start_date.tzinfo),
                    duration=60, type="activity",
                    price=price if price is not None else 0.0,
                ))

            # Log before filtering by budget
            n_before_budget = len(all_pois)
            budget_limit = budget * 0.1
            filtered_pois = []
            for poi in all_pois:
                if poi.type == "activity" and poi.price is not None and poi.price > budget_limit:
                    logger.info(f"Excluding activity {poi.id} due to price {poi.price} > {budget_limit}")
                else:
                    filtered_pois.append(poi)
            all_pois = filtered_pois
            logger.info(f"Activities after budget filter: {len([p for p in all_pois if p.type == 'activity'])} (before: {n_before_budget})")

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
                    func.ST_DWithin(geom_acc, func.ST_SetSRID(func.ST_MakePoint(center_lon, center_lat), 4326).cast(Geography), radius_m)
                )
                .order_by(Accommodation.rating.desc())
                .limit(30)  # Increased limit for better selection
            )
            acc_rows = (await self.session.execute(acc_stmt)).all()
            
            for _id, lat, lon, price in acc_rows:
                all_pois.append(POI(
                    id=_id, latitude=lat, longitude=lon,
                    opens=datetime.combine(start_date.date(), TimeOfDay(0, 0), tzinfo=start_date.tzinfo),
                    closes=datetime.combine(start_date.date(), TimeOfDay(23, 59), tzinfo=start_date.tzinfo),
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

            if not any(p.type == "accommodation" for p in all_pois):
                logger.warning("No accommodations match budget/rating — relaxing to any rating")

            
            # Deduplicate POIs by (type, id) to avoid repeats in scheduling
            unique = {}
            for poi in all_pois:
                key = (poi.type, poi.id)
                if key not in unique:
                    unique[key] = poi
            deduped = list(unique.values())

            logger.info(f"Built POI list with {len(deduped)} unique items (from {len(all_pois)} raw)")
            return deduped
        except Exception as e:
            logger.exception("Failed to build POI list")
            # raise HTTPException(status_code=500, detail="Failed to build itinerary items")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def create_itinerary_schedule(self, all_pois, trip_days, start_date, pace, use_transformer: Optional[bool] = None):
        """Create day-by-day itinerary schedule with enriched entity details"""
        try:
            base_loc = DestCoord(id=None, latitude=all_pois[0].latitude, longitude=all_pois[0].longitude)
            scheduled_items = []
            
            for day in range(trip_days):
                day_start = datetime.combine(start_date + timedelta(days=day), TimeOfDay(9, 0), tzinfo=start_date.tzinfo)
                day_end = day_start + timedelta(hours=pace["max_hours"])
                
                # Optionally reorder activity POIs using Transformer to bias selection order
                try:
                    settings = Settings()
                    enabled_flag = use_transformer if use_transformer is not None else settings.ENABLE_TRANSFORMER
                    if enabled_flag:
                        act_ids = [str(p.id) for p in all_pois if getattr(p, "type", None) == "activity"]
                        if act_ids:
                            ordered_ids = reorder_pois(act_ids)
                            order_rank = {pid: i for i, pid in enumerate(ordered_ids)}
                            def sort_key(p):
                                if getattr(p, "type", None) == "activity":
                                    return (0, order_rank.get(str(p.id), len(order_rank)))
                                return (1, 0)
                            candidate_pois = sorted(all_pois, key=sort_key)
                        else:
                            candidate_pois = all_pois
                    else:
                        candidate_pois = all_pois
                except Exception as e:
                    logger.error(f"Transformer reorder failed, using original order: {e}")
                    candidate_pois = all_pois

                today = time_aware_greedy_route(
                    start_point=base_loc,
                    pois=candidate_pois,
                    day_start=day_start,
                    day_end=day_end
                )[:pace["daily_activities"]]
                
                # Enrich POI data with full entity details
                enriched_today = await self._enrich_pois_with_details(today)
                scheduled_items.append(enriched_today)
                
                # Update base location and remove scheduled items
                scheduled = {p.id for p in today}
                all_pois = [p for p in all_pois if p.id not in scheduled]
                if today:
                    last = today[-1]
                    base_loc = DestCoord(last.id, last.latitude, last.longitude)
            
            logger.info(f"Created schedule for {trip_days} days")
            logger.info(f"Scheduled items: {len(scheduled_items)} days with enriched details")
            return scheduled_items
        except Exception as e:
            logger.error(f"Failed to create itinerary schedule: {e}")
            raise HTTPException(status_code=500, detail="Failed to create itinerary schedule")

    async def _enrich_pois_with_details(self, pois):
        """Enrich POI objects with full entity details for frontend display"""
        enriched_pois = []
        
        for poi in pois:
            enriched_poi = {
                "id": str(poi.id),
                "type": poi.type,
                "latitude": poi.latitude,
                "longitude": poi.longitude,
                "price": float(poi.price) if poi.price is not None else None,
                "opens": poi.opens.isoformat() if poi.opens else None,
                "closes": poi.closes.isoformat() if poi.closes else None,
                "duration": poi.duration,
            }
            
            try:
                # Fetch full entity details based on type
                if poi.type == "destination":
                    dest = await self.session.get(Destination, poi.id)
                    if dest:
                        enriched_poi.update({
                            "name": dest.name,
                            "description": dest.description,
                            "rating": float(dest.rating) if dest.rating else None,
                            "popularity_score": float(dest.popularity_score) if dest.popularity_score else None,
                        })
                
                elif poi.type == "activity":
                    activity = await self.session.get(Activity, poi.id)
                    if activity:
                        enriched_poi.update({
                            "name": activity.name or f"Activity {str(poi.id)[:8]}",
                            "description": activity.description or "No description available",
                            "rating": float(activity.rating) if activity.rating else None,
                            "opening_hours": activity.opening_hours or "Hours not specified",
                            "price_display": f"${float(poi.price):.2f}" if poi.price is not None and poi.price > 0 else "Free",
                        })
                
                elif poi.type == "accommodation":
                    accommodation = await self.session.get(Accommodation, poi.id)
                    if accommodation:
                        enriched_poi.update({
                            "name": accommodation.name,
                            "description": accommodation.description,
                            "rating": float(accommodation.rating) if accommodation.rating else None,
                            "amenities": accommodation.amenities,
                        })
                
                elif poi.type == "transportation":
                    transport = await self.session.get(Transportation, poi.id)
                    if transport:
                        enriched_poi.update({
                            "name": f"{transport.transport_type} - {transport.departure_location} to {transport.arrival_location}",
                            "transport_type": transport.transport_type,
                            "departure_location": transport.departure_location,
                            "arrival_location": transport.arrival_location,
                            "departure_time": transport.departure_time.isoformat() if transport.departure_time else None,
                            "arrival_time": transport.arrival_time.isoformat() if transport.arrival_time else None,
                        })
                        
            except Exception as e:
                logger.warning(f"Failed to enrich POI {poi.id} of type {poi.type}: {e}")
                # Fallback to basic POI data
                enriched_poi["name"] = f"{poi.type.title()} {str(poi.id)[:8]}"
            
            enriched_pois.append(enriched_poi)
        
        return enriched_pois
    
    async def persist_itinerary(self, itin_id, scheduled_items, parsed_data, user_id, budget: Optional[float] = None):
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
                user_id=user_id,
                budget=budget if budget is not None else parsed_data.get("budget")
            )
            self.session.add(new_itin)
            
            # Persist scheduled items
            for day_idx, day_items in enumerate(scheduled_items):
                for order, poi in enumerate(day_items, start=1):
                    # Handle both POI objects and enriched dictionaries
                    poi_type = poi.get("type") if isinstance(poi, dict) else poi.type
                    poi_id = poi.get("id") if isinstance(poi, dict) else poi.id
                    
                    if poi_type == "destination":
                        self.session.add(ItineraryDestination(
                            itinerary_id=itin_id, destination_id=poi_id, order=order
                        ))
                    elif poi_type == "activity":
                        self.session.add(ItineraryActivity(
                            itinerary_id=itin_id, activity_id=poi_id, order=order
                        ))
                    elif poi_type == "accommodation":
                        self.session.add(ItineraryAccommodation(
                            itinerary_id=itin_id, accommodation_id=poi_id, order=order
                        ))
                    else:  # transportation
                        self.session.add(ItineraryTransportation(
                            itinerary_id=itin_id, transportation_id=poi_id, order=order
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
@limiter.limit(Settings().RATE_LIMIT_GENERATE if Settings().ENABLE_RATE_LIMITING else "1000/minute")
async def generate_itinerary(
    request: Request,
    payload: ItineraryCreate,
    current_user: User = Depends(get_current_user), # auth gate
    session: AsyncSession = Depends(get_db_session)
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
            user_prefs = current_user.preferences or {}
            interests = parsed.get("interests") or user_prefs.get("interests", [])
            budget = parsed.get("budget") or user_prefs.get("budget", 1000)
            
            # Get pace settings
            pace_key = parsed.get("pace") or user_prefs.get("pace", "moderate")
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
            
            # Adaptive radius: try increasing if too few activities found
            min_activities = 3
            radius_attempts = [radius_m, 50000, 100000]  # 20km, 50km, 100km
            all_pois = None
            center_lat = dest_center_lat
            center_lon = dest_center_lon
            for attempt, rad in enumerate(radius_attempts):
                logger.info(f"Attempting build_poi_list with radius_m={rad}")
                all_pois = await service.build_poi_list(
                    dest_ids, act_ids, acc_ids, trans_ids, start_date, center_lat, center_lon,
                     rad, budget
                )
                n_activities = len([p for p in all_pois if p.type == "activity"])
                logger.info(f"build_poi_list found {n_activities} activities with radius_m={rad}")
                if n_activities >= 3 or attempt == len(radius_attempts) - 1:
                    break

            if not any(p.type=="accommodation" for p in all_pois):
                logger.warning("No accommodations match budget/rating—relaxing to any rating")


            
            if not all_pois:
                raise HTTPException(
                    status_code=404,
                    detail="No itinerary items could be scheduled for these preferences."
                )
            
            # Create schedule
            scheduled_items = await service.create_itinerary_schedule(
                all_pois, trip_days, start_date, pace, use_transformer=payload.use_transformer
            )
            
            # Persist itinerary
            itin_id = uuid4()
            full_itin = await service.persist_itinerary(itin_id, scheduled_items, parsed, current_user.id, budget=budget)
            
            logger.info(f"Successfully generated itinerary {itin_id} for user {current_user.id}")
            return full_itin
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in itinerary generation: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate itinerary")

@router.get("/{itinerary_id}", response_model=ItineraryRead)
@limiter.limit("60/minute")
async def read_itinerary(
    request: Request,
    itinerary_id: UUID, 
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    itin = await get_itinerary(session, itinerary_id)
    if itin.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this itinerary")

    # --- PATCH: add scheduled_items to response ---
    # Extract POI IDs from itinerary links
    dest_ids = [dl.destination.id for dl in itin.dest_links]
    act_ids = [al.activity.id for al in itin.act_links]
    acc_ids = [al.accommodation.id for al in itin.accom_links]
    trans_ids = [tl.transportation.id for tl in itin.trans_links]

    # Use itinerary data to get schedule params
    parsed_data = itin.data or {}
    start_date = itin.start_date
    trip_days = itin.duration_days
    pace_key = parsed_data.get("pace", "moderate")
    pace = PACING.get(pace_key, PACING["moderate"])
    center_lat = itin.dest_links[0].destination.latitude if itin.dest_links else 0.0
    center_lon = itin.dest_links[0].destination.longitude if itin.dest_links else 0.0
    radius_m = 20000
    budget = float(itin.budget) if itin.budget else 10000.0

    service = ItineraryService(session)
    all_pois = await service.build_poi_list(dest_ids, act_ids, acc_ids, trans_ids, start_date, center_lat, center_lon, 
                                            radius_m, budget)
    scheduled_items = await service.create_itinerary_schedule(all_pois, trip_days, start_date, pace)

    # Prepare dict for ItineraryRead, ensuring all fields are serializable and required fields are present
    itin_dict = itin.__dict__.copy()
    itin_dict["scheduled_items"] = scheduled_items

    # Compute duration_days and is_active if not present
    if "duration_days" not in itin_dict or itin_dict["duration_days"] is None:
        itin_dict["duration_days"] = (itin.end_date - itin.start_date).days if itin.start_date and itin.end_date else 0
    if "is_active" not in itin_dict or itin_dict["is_active"] is None:
        itin_dict["is_active"] = getattr(itin, "is_active", True) if hasattr(itin, "is_active") else True

    # Convert ORM link objects to Pydantic schema
    
    itin_dict["dest_links"] = [ItineraryDestinationRead.model_validate(dl, from_attributes=True) 
                               for dl in getattr(itin, "dest_links", [])]
    itin_dict["act_links"]  = [ItineraryActivityRead.model_validate(al, from_attributes=True) 
                               for al in getattr(itin, "act_links", [])]
    itin_dict["accom_links"] = [ItineraryAccommodationRead.model_validate(acl, from_attributes=True) 
                                for acl in getattr(itin, "accom_links", [])]
    itin_dict["trans_links"] = [ItineraryTransportationRead.model_validate(tl, from_attributes=True) 
                                for tl in getattr(itin, "trans_links", [])]

    return ItineraryRead(**itin_dict)


@router.post("/{itinerary_id}/regenerate-day", response_model=ItineraryRead)
@limiter.limit("20/minute")
async def regenerate_day(
    request: Request,
    itinerary_id: UUID,
    payload: RegenerateDayRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Regenerate a specific day's schedule with optional constraints.
    This does NOT persist changes; it returns a preview with updated scheduled_items.
    """
    itin = await get_itinerary(session, itinerary_id)
    if itin.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to modify this itinerary")

    # Rebuild inputs similar to read_itinerary
    parsed_data = itin.data or {}
    start_date = itin.start_date
    trip_days = itin.duration_days
    if payload.day_index < 0 or payload.day_index >= trip_days:
        raise HTTPException(status_code=400, detail="day_index out of range")

    pace_key = parsed_data.get("pace", "moderate")
    base_pace = PACING.get(pace_key, PACING["moderate"]).copy()
    if payload.max_stops is not None:
        base_pace["daily_activities"] = max(1, min(payload.max_stops, 20))

    center_lat = itin.dest_links[0].destination.latitude if itin.dest_links else 0.0
    center_lon = itin.dest_links[0].destination.longitude if itin.dest_links else 0.0
    radius_m = 20000
    budget = float(itin.budget) if itin.budget else 10000.0

    # Collect IDs from links
    dest_ids = [dl.destination.id for dl in itin.dest_links]
    act_ids = [al.activity.id for al in itin.act_links]
    acc_ids = [al.accommodation.id for al in itin.accom_links]
    trans_ids = [tl.transportation.id for tl in itin.trans_links]

    service = ItineraryService(session)
    all_pois = await service.build_poi_list(dest_ids, act_ids, acc_ids, trans_ids, start_date, center_lat, center_lon, radius_m, budget)

    # Apply price constraint only to activities if provided
    if payload.max_price_per_activity is not None:
        max_price = float(payload.max_price_per_activity)
        for p in all_pois:
            if getattr(p, "type", None) == "activity" and getattr(p, "price", 0.0) is not None:
                if p.price > max_price:
                    p.price = max_price  # bias scheduler toward cheaper options

    scheduled_items = await service.create_itinerary_schedule(
        all_pois, trip_days, start_date, base_pace, use_transformer=payload.use_transformer
    )

    # Prepare ItineraryRead with updated scheduled_items only (no DB write)
    itin_dict = itin.__dict__.copy()
    itin_dict["scheduled_items"] = scheduled_items
    itin_dict["dest_links"] = [ItineraryDestinationRead.model_validate(dl, from_attributes=True) for dl in getattr(itin, "dest_links", [])]
    itin_dict["act_links"]  = [ItineraryActivityRead.model_validate(al, from_attributes=True) for al in getattr(itin, "act_links", [])]
    itin_dict["accom_links"] = [ItineraryAccommodationRead.model_validate(acl, from_attributes=True) for acl in getattr(itin, "accom_links", [])]
    itin_dict["trans_links"] = [ItineraryTransportationRead.model_validate(tl, from_attributes=True) for tl in getattr(itin, "trans_links", [])]
    if "duration_days" not in itin_dict or itin_dict["duration_days"] is None:
        itin_dict["duration_days"] = (itin.end_date - itin.start_date).days if itin.start_date and itin.end_date else 0
    if "is_active" not in itin_dict or itin_dict["is_active"] is None:
        itin_dict["is_active"] = getattr(itin, "is_active", True) if hasattr(itin, "is_active") else True
    return ItineraryRead(**itin_dict)


@router.post("/{itinerary_id}/share-link", response_model=ShareLinkCreateResponse)
@limiter.limit("5/minute")
async def create_share_link(
    request: Request,
    itinerary_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Create a tokenized public share link for an itinerary."""
    itin = await get_itinerary(session, itinerary_id)
    if itin.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to share this itinerary")

    token = uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    _SHARE_LINKS[token] = {
        "itinerary_id": str(itinerary_id),
        "user_id": str(current_user.id),
        "expires_at": expires_at,
    }
    base = str(request.base_url).rstrip("/")
    url = f"{base}/itineraries/shared/{token}"
    return ShareLinkCreateResponse(token=token, url=url, expires_at=expires_at)


@router.get("/shared/{token}", response_model=ItineraryRead)
@limiter.limit("120/minute")
async def read_shared_itinerary(
    request: Request,
    token: str,
    session: AsyncSession = Depends(get_db_session)
):
    """Public endpoint to read an itinerary shared via token."""
    link = _SHARE_LINKS.get(token)
    if not link:
        raise HTTPException(status_code=404, detail="Invalid or expired share link")
    if datetime.now(timezone.utc) > link["expires_at"]:
        _SHARE_LINKS.pop(token, None)
        raise HTTPException(status_code=410, detail="Share link has expired")

    itin = await get_itinerary(session, UUID(link["itinerary_id"]))

    # Build schedule as in read_itinerary
    dest_ids = [dl.destination.id for dl in itin.dest_links]
    act_ids = [al.activity.id for al in itin.act_links]
    acc_ids = [al.accommodation.id for al in itin.accom_links]
    trans_ids = [tl.transportation.id for tl in itin.trans_links]

    parsed_data = itin.data or {}
    start_date = itin.start_date
    trip_days = itin.duration_days
    pace_key = parsed_data.get("pace", "moderate")
    pace = PACING.get(pace_key, PACING["moderate"])
    center_lat = itin.dest_links[0].destination.latitude if itin.dest_links else 0.0
    center_lon = itin.dest_links[0].destination.longitude if itin.dest_links else 0.0
    radius_m = 20000
    budget = float(itin.budget) if itin.budget else 10000.0

    service = ItineraryService(session)
    all_pois = await service.build_poi_list(dest_ids, act_ids, acc_ids, trans_ids, start_date, center_lat, center_lon, radius_m, budget)
    scheduled_items = await service.create_itinerary_schedule(all_pois, trip_days, start_date, pace)

    itin_dict = itin.__dict__.copy()
    itin_dict["scheduled_items"] = scheduled_items
    itin_dict["dest_links"] = [ItineraryDestinationRead.model_validate(dl, from_attributes=True) for dl in getattr(itin, "dest_links", [])]
    itin_dict["act_links"]  = [ItineraryActivityRead.model_validate(al, from_attributes=True) for al in getattr(itin, "act_links", [])]
    itin_dict["accom_links"] = [ItineraryAccommodationRead.model_validate(acl, from_attributes=True) for acl in getattr(itin, "accom_links", [])]
    itin_dict["trans_links"] = [ItineraryTransportationRead.model_validate(tl, from_attributes=True) for tl in getattr(itin, "trans_links", [])]
    if "duration_days" not in itin_dict or itin_dict["duration_days"] is None:
        itin_dict["duration_days"] = (itin.end_date - itin.start_date).days if itin.start_date and itin.end_date else 0
    if "is_active" not in itin_dict or itin_dict["is_active"] is None:
        itin_dict["is_active"] = getattr(itin, "is_active", True) if hasattr(itin, "is_active") else True
    return ItineraryRead(**itin_dict)

@router.get("/", response_model=List[Itinerary])
@limiter.limit("30/minute")
async def list_itineraries(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    itineraries = await get_user_itineraries(session, user_id=current_user.id)
    return itineraries


@router.patch("/{itinerary_id}", response_model=Itinerary)
@limiter.limit("30/minute")
async def patch_itinerary_status(
    request: Request,
    itinerary_id: UUID,
    payload: ItineraryUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    itin = await get_itinerary(session, itinerary_id)
    if itin.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this itinerary")
    return await update_itinerary_status(itinerary_id, payload.status, session)

@router.delete("/{itinerary_id}", status_code=204)
@limiter.limit("10/minute")
async def remove_itinerary(
    request: Request,
    itinerary_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    itin = await get_itinerary(session, itinerary_id)
    if itin.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this itinerary")
    await delete_itinerary(itinerary_id, session)
    return Response(status_code=204)

@router.post("/reorder-preview", response_model=ReorderPreviewResponse)
@limiter.limit("10/minute")
async def reorder_preview(
    request: Request,
    payload: ReorderPreviewRequest,
):
    settings = Settings()
    if not settings.ENABLE_TRANSFORMER:
        # If transformer disabled, return identity order
        return ReorderPreviewResponse(input=payload.poi_ids, output=payload.poi_ids)
    try:
        ordered = reorder_pois(payload.poi_ids)
        return ReorderPreviewResponse(input=payload.poi_ids, output=ordered)
    except Exception as e:
        logger.error(f"/reorder-preview failed: {e}")
        # Fallback: return original order
        return ReorderPreviewResponse(input=payload.poi_ids, output=payload.poi_ids)

# from uuid import UUID, uuid4
# from typing import List, Optional
# from datetime import datetime, timezone, time, timedelta

# from fastapi import APIRouter, Depends, HTTPException
# from fastapi.concurrency import run_in_threadpool
# from fastapi.encoders import jsonable_encoder
# from geoalchemy2 import Geography
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, func, and_
# from sqlalchemy.orm import selectinload

# import pickle, scipy.sparse
# from sklearn.metrics.pairwise import cosine_similarity

# from app.db.models import (
#     User, Itinerary, ItineraryDestination, Destination, Activity,
#     ItineraryActivity, Accommodation, ItineraryAccommodation,
#     Transportation, ItineraryTransportation
# )
# from app.core.itinerary_optimizer import DestCoord, POI, time_aware_greedy_route
# from app.api.schemas import ItineraryCreate, ItineraryRead
# from app.db.session import get_db_session
# from app.core.security import get_current_user
# from app.core.nlp.parser import parse_travel_request


# router = APIRouter(prefix="/itineraries", tags=["itineraries"])

# # Pace presets
# PACING = {
#     "relaxed":  {"daily_activities": 2, "max_hours": 4},
#     "moderate": {"daily_activities": 4, "max_hours": 8},
#     "intense":  {"daily_activities": 6, "max_hours": 12},
# }

# def parse_opening_hours(oh: str):
#     """ "HH:MM-HH:MM" -> (time, time) """
#     try:
#         o, c = oh.split("-")
#         return time.fromisoformat(o), time.fromisoformat(c)
#     except:
#         return time(9, 0), time(17, 0)


# # --- TF-IDF helpers (unchanged) ---

# DEST_VEC, DEST_MAT, DEST_MAP = (
#     "/app/models/tfidf_vectorizer_dest.pkl",
#     "/app/models/tfidf_matrix_dest.npz",
#     "/app/models/item_index_map_dest.pkl",
# )
# vectorizer    = pickle.load(open(DEST_VEC, "rb"))
# item_matrix   = scipy.sparse.load_npz(DEST_MAT)
# DEST_ID_MAP   = pickle.load(open(DEST_MAP, "rb"))

# async def get_destination_ids(interests: List[str], budget: Optional[float]):
#     q      = " ".join(interests or []) + f" budget {budget or 0}"
#     v      = vectorizer.transform([q])
#     scores = cosine_similarity(v, item_matrix).flatten()
#     top    = scores.argsort()[::-1][:10]
#     return [DEST_ID_MAP[i] for i in top]

# ACT_VEC, ACT_MAT, ACT_MAP = (
#     "/app/models/tfidf_vectorizer_act.pkl",
#     "/app/models/tfidf_matrix_act.npz",
#     "/app/models/item_index_map_act.pkl",
# )
# act_vectorizer = pickle.load(open(ACT_VEC, "rb"))
# act_matrix     = scipy.sparse.load_npz(ACT_MAT)
# ACT_ID_MAP     = pickle.load(open(ACT_MAP, "rb"))

# async def get_activity_ids(interests: List[str], budget: Optional[float]):
#     q      = " ".join(interests or []) + f" budget {budget or 0}"
#     v      = act_vectorizer.transform([q])
#     scores = cosine_similarity(v, act_matrix).flatten()
#     top    = scores.argsort()[::-1][:10]
#     return [ACT_ID_MAP[i] for i in top]

# ACC_VEC, ACC_MAT, ACC_MAP = (
#     "/app/models/tfidf_vectorizer_acc.pkl",
#     "/app/models/tfidf_matrix_acc.npz",
#     "/app/models/item_index_map_acc.pkl",
# )
# acc_vectorizer = pickle.load(open(ACC_VEC, "rb"))
# acc_matrix     = scipy.sparse.load_npz(ACC_MAT)
# ACC_ID_MAP     = pickle.load(open(ACC_MAP, "rb"))

# async def get_accommodation_ids(interests: List[str], budget: Optional[float]):
#     q      = " ".join(interests or []) + f" budget {budget or 0}"
#     v      = acc_vectorizer.transform([q])
#     scores = cosine_similarity(v, acc_matrix).flatten()
#     top    = scores.argsort()[::-1][:10]
#     return [ACC_ID_MAP[i] for i in top if scores[i] > 0]

# TRANS_VEC, TRANS_MAT, TRANS_MAP = (
#     "/app/models/tfidf_vectorizer_trans.pkl",
#     "/app/models/tfidf_matrix_trans.npz",
#     "/app/models/item_index_map_trans.pkl",
# )
# trans_vectorizer = pickle.load(open(TRANS_VEC, "rb"))
# trans_matrix     = scipy.sparse.load_npz(TRANS_MAT)
# TRANS_ID_MAP     = pickle.load(open(TRANS_MAP, "rb"))

# async def get_transportation_ids(interests: List[str], budget: Optional[float]):
#     q      = " ".join(interests or []) + f" budget {budget or 0}"
#     v      = trans_vectorizer.transform([q])
#     scores = cosine_similarity(v, trans_matrix).flatten()
#     top    = scores.argsort()[::-1][:10]
#     return [TRANS_ID_MAP[i] for i in top if scores[i] > 0]


# @router.post("/generate", response_model=ItineraryRead)
# async def generate_itinerary(
#     payload: ItineraryCreate,
#     current_user: User = Depends(get_current_user),
#     session: AsyncSession = Depends(get_db_session),
# ):
#     # --- 1) Parse & expand dates ---
#     parsed = await run_in_threadpool(parse_travel_request, payload.text)
#     raw_dates = parsed.get("dates", [])
#     if len(raw_dates) == 2:
#         # assume ISO strings or datetimes
#         start = raw_dates[0] if isinstance(raw_dates[0], datetime) else datetime.fromisoformat(raw_dates[0])
#         end   = raw_dates[1] if isinstance(raw_dates[1], datetime) else datetime.fromisoformat(raw_dates[1])
#         parsed["dates"] = [
#             (start + timedelta(days=i)).isoformat()
#             for i in range((end - start).days + 1)
#         ]
#     else:
#         parsed["dates"] = [
#             d.isoformat() if isinstance(d, datetime) else d
#             for d in raw_dates
#         ]
#     dates = [datetime.fromisoformat(d) for d in parsed["dates"]]
#     start_date, end_date = dates[0], dates[-1]
#     trip_days = len(dates)

#     # --- 2) Extract locations, prefs ---
#     locs        = parsed.get("locations", ["My Trip"])
#     dest_city   = locs[0]
#     origin_city = locs[-2] if len(locs) >= 2 else None
#     interests   = parsed.get("interests") or current_user.preferences.get("interests", [])
#     budget      = parsed.get("budget") or current_user.preferences.get("budget")
#     pace_key    = parsed.get("pace") or current_user.preferences.get("pace", "moderate")
#     pace        = PACING.get(pace_key, PACING["moderate"])

#     # --- 3) Lookup seed destinations for centroids ---
#     dest_row   = await session.scalar(select(Destination).where(Destination.name == dest_city))
#     origin_row = await session.scalar(select(Destination).where(Destination.name == origin_city)) if origin_city else None
#     if dest_row is None or (origin_city and origin_row is None):
#         raise HTTPException(404, f"Unknown origin/destination: {origin_city} → {dest_city}")

#     dc_lat, dc_lon = dest_row.latitude, dest_row.longitude
#     oc_lat, oc_lon = (origin_row.latitude, origin_row.longitude) if origin_row else (None, None)

#     # --- 4) Build geography filters for flights ---
#     origin_pt = func.ST_SetSRID(func.ST_MakePoint(oc_lon, oc_lat), 4326).cast(Geography) if origin_city else None
#     dest_pt   = func.ST_SetSRID(func.ST_MakePoint(dc_lon, dc_lat), 4326).cast(Geography)
#     flight_radius_m = parsed.get("flight_radius_km", 20) * 1000

#     dep_geom = func.ST_SetSRID(func.ST_MakePoint(
#         Transportation.departure_long, Transportation.departure_lat), 4326).cast(Geography)
#     arr_geom = func.ST_SetSRID(func.ST_MakePoint(
#         Transportation.arrival_long, Transportation.arrival_lat), 4326).cast(Geography)

#     flight_stmt = (
#         select(Transportation.id)
#         .where(
#             and_(
#                 origin_city and func.ST_DWithin(dep_geom, origin_pt, flight_radius_m),
#                 func.ST_DWithin(arr_geom, dest_pt,   flight_radius_m),
#                 Transportation.departure_time >= start_date,
#                 Transportation.arrival_time   <= end_date + timedelta(days=1),
#             )
#         )
#         .limit(10)
#     )
#     trans_rows = await session.execute(flight_stmt)
#     trans_ids  = [r[0] for r in trans_rows.all()]
#     if not trans_ids:
#         # fallback to TF-IDF lookup
#         trans_ids = await get_transportation_ids(interests, budget)

#     # --- 5) Persist itinerary stub ---
#     json_data = jsonable_encoder(parsed)
#     itin_id = uuid4()
#     new_itin = Itinerary(
#         id=itin_id,
#         name=dest_city,
#         start_date=start_date,
#         end_date=end_date,
#         status="generated",
#         data=json_data,
#         user_id=current_user.id,
#     )
#     session.add(new_itin)
#     await session.commit()

#     # --- 6) TF-IDF candidates for POIs ---
#     dest_ids = await get_destination_ids(interests, budget)
#     act_ids  = await get_activity_ids(interests, budget)
#     acc_ids  = await get_accommodation_ids(interests, budget)

#     all_pois: List[POI] = []

#     # --- 7) Destinations (9–17, 120m) ---
#     radius_m = parsed.get("radius_km", 20) * 1000
#     geom_dest = func.ST_SetSRID(func.ST_MakePoint(
#         Destination.longitude, Destination.latitude), 4326).cast(Geography)

#     dest_stmt = (
#         select(Destination.id, Destination.latitude, Destination.longitude)
#         .where(
#             Destination.id.in_(dest_ids),
#             Destination.rating >= parsed.get("min_rating", 0.0),
#             func.ST_DWithin(geom_dest, dest_pt, radius_m),
#         )
#     )
#     dest_rows = (await session.execute(dest_stmt)).all()
#     if not dest_rows:
#         raise HTTPException(404, f"No destinations found within {radius_m/1000} km")

#     for _id, lat, lon in dest_rows:
#         all_pois.append(POI(
#             id=_id, latitude=lat, longitude=lon,
#             opens = datetime.combine(start_date.date(), time(9,0), tzinfo=start_date.tzinfo),
#             closes= datetime.combine(start_date.date(), time(17,0), tzinfo=start_date.tzinfo),
#             duration=120, type="destination", price=None,
#         ))

#     # --- 8) Activities (opening_hours, 60m) ---
#     geom_act = func.ST_SetSRID(func.ST_MakePoint(
#         Activity.longitude, Activity.latitude), 4326).cast(Geography)
#     act_stmt = (
#         select(Activity.id, Activity.latitude, Activity.longitude, Activity.opening_hours, Activity.price)
#         .where(
#             Activity.id.in_(act_ids),
#             func.ST_DWithin(geom_act, dest_pt, radius_m),
#         )
#     )
#     act_rows = (await session.execute(act_stmt)).all()
#     if not act_rows:
#         raise HTTPException(404, f"No activities found within {radius_m/1000} km")

#     for _id, lat, lon, oh, price in act_rows:
#         o, c = parse_opening_hours(oh or "")
#         all_pois.append(POI(
#             id=_id, latitude=lat, longitude=lon,
#             opens = datetime.combine(start_date.date(), o, tzinfo=start_date.tzinfo),
#             closes= datetime.combine(start_date.date(), c, tzinfo=start_date.tzinfo),
#             duration=60, type="activity", price=price or 0.0,
#         ))

#     # --- 9) Accommodations (full-day window) ---
#     geom_acc = func.ST_SetSRID(func.ST_MakePoint(
#         Accommodation.longitude, Accommodation.latitude), 4326).cast(Geography)
#     acc_stmt = (
#         select(Accommodation.id, Accommodation.latitude, Accommodation.longitude, Accommodation.price)
#         .where(
#             Accommodation.id.in_(acc_ids),
#             func.ST_DWithin(geom_acc, dest_pt, radius_m),
#         )
#         .order_by(Accommodation.rating.desc())
#         .limit(trip_days)
#     )
#     acc_rows = (await session.execute(acc_stmt)).all()
#     if not acc_rows:
#         raise HTTPException(404, f"No accommodations found within {radius_m/1000} km")

#     for _id, lat, lon, price in acc_rows:
#         all_pois.append(POI(
#             id=_id, latitude=lat, longitude=lon,
#             opens = datetime.combine(start_date.date(), time(0,0),   tzinfo=start_date.tzinfo),
#             closes= datetime.combine(start_date.date(), time(23,59), tzinfo=start_date.tzinfo),
#             duration=0, type="accommodation", price=price or 0.0,
#         ))

#     # --- 10) Flights (already have trans_ids) ---
#     trans_stmt = select(
#         Transportation.id, Transportation.departure_lat, Transportation.departure_long,
#         Transportation.arrival_lat,   Transportation.arrival_long,
#         Transportation.departure_time, Transportation.arrival_time,
#         Transportation.price
#     ).where(Transportation.id.in_(trans_ids))
#     for _id, dlat, dlon, alat, alon, dt, at, price in (await session.execute(trans_stmt)).all():
#         dur_min = int((at - dt).total_seconds() / 60)
#         all_pois.append(POI(
#             id=_id, latitude=dlat, longitude=dlon,
#             arrival_lat=alat, arrival_long=alon,
#             opens=dt.astimezone(start_date.tzinfo),
#             closes=at.astimezone(start_date.tzinfo),
#             duration=dur_min, type="transportation", price=price or 0.0,
#         ))

#     # --- 11) Price filter for activities ---
#     all_pois = [
#         p for p in all_pois
#         if not (p.type == "activity" and p.price > (budget or float("inf")) * 0.1)
#     ]
#     if not all_pois:
#         raise HTTPException(404, "No itinerary items fitted your preferences")

#     # --- 12) Schedule day-by-day ---
#     base_loc = DestCoord(id=None, latitude=all_pois[0].latitude, longitude=all_pois[0].longitude)
#     for day in range(trip_days):
#         ds = datetime.combine(start_date + timedelta(days=day), time(9,0), tzinfo=start_date.tzinfo)
#         de = ds + timedelta(hours=pace["max_hours"])
#         today = time_aware_greedy_route(base_loc, all_pois, day_start=ds, day_end=de)
#         for order, poi in enumerate(today[:pace["daily_activities"]], 1):
#             if poi.type == "destination":
#                 session.add(ItineraryDestination(itinerary_id=itin_id, destination_id=poi.id, order=order))
#             elif poi.type == "activity":
#                 session.add(ItineraryActivity(itinerary_id=itin_id, activity_id=poi.id, order=order))
#             elif poi.type == "accommodation":
#                 session.add(ItineraryAccommodation(itinerary_id=itin_id, accommodation_id=poi.id, order=order))
#             else:
#                 session.add(ItineraryTransportation(itinerary_id=itin_id, transportation_id=poi.id, order=order))
#         await session.commit()
#         # remove used POIs and update base
#         used = {p.id for p in today}
#         all_pois = [p for p in all_pois if p.id not in used]
#         if today:
#             last = today[-1]
#             base_loc = DestCoord(last.id, last.latitude, last.longitude)

#     # --- 13) Return full itinerary ---
#     full_itin = (await session.execute(
#         select(Itinerary)
#         .where(Itinerary.id == itin_id)
#         .options(
#             selectinload(Itinerary.dest_links).selectinload(ItineraryDestination.destination),
#             selectinload(Itinerary.act_links).selectinload(ItineraryActivity.activity),
#             selectinload(Itinerary.accom_links).selectinload(ItineraryAccommodation.accommodation),
#             selectinload(Itinerary.trans_links).selectinload(ItineraryTransportation.transportation),
#         )
#     )).scalar_one()

#     return full_itin

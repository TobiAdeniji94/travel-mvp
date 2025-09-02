from collections import namedtuple
from datetime import datetime, timedelta
from geopy.distance import geodesic
from typing import List, Union

# Simple start‐point with only coords
DestCoord = namedtuple("DestCoord", ["id", "latitude", "longitude"])

# Full POI with time windows and service duration
POI = namedtuple("POI", [
    "id",        # UUID or identifier
    "latitude", 
    "longitude",
    "price",
    "opens",     # datetime when it opens
    "closes",    # datetime when it closes
    "duration",  # minutes spent on site
    "type"       # one of "destination","activity","accommodation","transportation"
])

def time_aware_greedy_route(
    start_point: DestCoord,
    pois:          List[POI],
    day_start:     datetime,
    day_end:       datetime,
) -> List[POI]:
    """
    Single‐day greedy that interleaves all POI types, respecting:
     - travel times (geodesic / avg speed)
     - POI opening/closing windows
     - service duration
     - day end cutoff
     
    Returns an ordered sublist of `pois`.
    """
    if not pois:
        return []

    current_time = day_start
    current_loc  = start_point
    ordered      = []

    # Copy list so we can pop from it
    remaining = pois.copy()

    # assume 40 km/h average speed
    def travel_time_minutes(a: DestCoord, b: POI) -> float:
        dist_km = geodesic(
            (a.latitude, a.longitude),
            (b.latitude, b.longitude)
        ).km
        return (dist_km / 40) * 60

    while remaining and current_time < day_end:
        best = None
        best_finish = None
        best_score = None

        for poi in remaining:
            # travel time to poi
            tt = timedelta(minutes=travel_time_minutes(current_loc, poi))
            arrive = current_time + tt

            # if we arrive before it opens, we must wait
            # Ensure timezone consistency between poi.opens and arrive
            if poi.opens.tzinfo is not None and arrive.tzinfo is None:
                arrive = arrive.replace(tzinfo=poi.opens.tzinfo)
            elif poi.opens.tzinfo is None and arrive.tzinfo is not None:
                poi_opens = poi.opens.replace(tzinfo=arrive.tzinfo)
                wait = max(timedelta(0), poi_opens - arrive)
            else:
                wait = max(timedelta(0), poi.opens - arrive)
            start_service = arrive + wait
            finish_service = start_service + timedelta(minutes=poi.duration)

            # skip if we'd finish after closing or day_end
            # Ensure timezone consistency for poi.closes comparison
            poi_closes = poi.closes
            if poi.closes.tzinfo is not None and finish_service.tzinfo is None:
                finish_service = finish_service.replace(tzinfo=poi.closes.tzinfo)
            elif poi.closes.tzinfo is None and finish_service.tzinfo is not None:
                poi_closes = poi.closes.replace(tzinfo=finish_service.tzinfo)
            
            # Ensure timezone consistency for day_end comparison
            day_end_tz = day_end
            if finish_service.tzinfo is not None and day_end.tzinfo is None:
                day_end_tz = day_end.replace(tzinfo=finish_service.tzinfo)
            elif finish_service.tzinfo is None and day_end.tzinfo is not None:
                finish_service = finish_service.replace(tzinfo=day_end.tzinfo)
            
            if finish_service > poi_closes or finish_service > day_end_tz:
                continue

            # score = minimal wait, tie-break on shortest travel
            score = (wait.total_seconds(), tt.total_seconds())

            if best is None or score < best_score:
                best = poi
                best_finish = finish_service
                best_score = score

        if not best:
            break

        # accept best POI
        ordered.append(best)
        remaining.remove(best)

        # advance time & location
        current_time = best_finish
        current_loc = DestCoord(best.id, best.latitude, best.longitude)

    return ordered

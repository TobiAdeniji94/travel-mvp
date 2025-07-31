from typing import List
from geopy.distance import geodesic
from collections import namedtuple

# Define the simple tuple for routing
DestCoord = namedtuple("DestCoord", ["id", "latitude", "longitude"])

def greedy_route(dest_coords: List[DestCoord]) -> List[DestCoord]:
    """
    Given a list of DestCoord tuples, return them in a simple
    nearest-neighbor order.
    """
    if not dest_coords:
        return []
    ordered = [dest_coords.pop(0)]
    while dest_coords:
        last = ordered[-1]
        # pick the next tuple by minimum geodesic distance
        next_tc = min(
            dest_coords,
            key=lambda tc: geodesic(
                (last.latitude, last.longitude),
                (tc.latitude, tc.longitude),
            ).km
        )
        dest_coords.remove(next_tc)
        ordered.append(next_tc)
    
    print("greedy_route: ordered", ordered)
    return ordered
print("Greedy route function loaded successfully.")

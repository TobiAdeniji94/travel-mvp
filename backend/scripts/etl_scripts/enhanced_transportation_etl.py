import os
import csv
import uuid
import math
import requests
import pickle
from datetime import datetime, timedelta
from google.colab import files

# ─── CONFIG ────────────────────────────────────────────────────────────
CACHE_DIR      = '/content/drive/MyDrive/flight_etl_cache'
os.makedirs(CACHE_DIR, exist_ok=True)

AIRPORTS_URL    = 'https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat'
ROUTES_URL      = 'https://raw.githubusercontent.com/jpatokal/openflights/refs/heads/master/data/routes.dat'
AIRPORTS_FILE   = 'airports.csv'
ROUTES_FILE     = 'routes.dat'
AIRPORTS_CACHE = os.path.join(CACHE_DIR, 'airports.pkl')
ROUTES_CACHE   = os.path.join(CACHE_DIR, 'routes.pkl')
OUTPUT_CSV      = 'transportation_flights.csv'

# Major hubs
HUBS = ['ATL','PEK','DXB','LAX','HND','ORD','LHR','PVG','CDG','DFW','CAN','AMS','FRA','IST','JFK']

# Pricing: €0.10 per km
PRICE_PER_KM = 0.10
# Avg cruise speed: 800 km/h
CRUISE_SPEED_KMH = 800

# ─── NEW: AIRLINE PROVIDERS FOR REALISTIC DATA ────────────────────────
AIRLINE_PROVIDERS = [
    'Delta Air Lines', 'American Airlines', 'United Airlines', 'Lufthansa',
    'Air France', 'British Airways', 'Emirates', 'Singapore Airlines',
    'Japan Airlines', 'China Southern', 'KLM', 'Turkish Airlines'
]

# Aircraft capacity by type (realistic values)
AIRCRAFT_CAPACITIES = {
    'narrow_body': 180,    # A320, 737
    'wide_body': 350,      # A350, 777
    'jumbo': 550          # A380, 747
}

# ─── HELPERS ───────────────────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ     = math.radians(lat2 - lat1)
    Δλ     = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def download(url):
    return requests.get(url).content

def generate_booking_reference():
    """Generate realistic airline booking reference"""
    import random, string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def determine_aircraft_type(distance_km):
    """Determine aircraft type based on distance"""
    if distance_km < 2000:
        return 'narrow_body'
    elif distance_km < 8000:
        return 'wide_body'
    else:
        return 'jumbo'

def get_provider_for_route(src, dst):
    """Assign airline provider based on route"""
    import random
    # Set seed based on route for consistency
    random.seed(hash(f"{src}{dst}"))
    return random.choice(AIRLINE_PROVIDERS)

# ─── EXISTING AIRPORT/ROUTE LOADING ────────────────────────────────────
# 1) Fetch and parse airports
if os.path.exists(AIRPORTS_CACHE):
    with open(AIRPORTS_CACHE,'rb') as f:
        airports = pickle.load(f)
else:
    raw = download(AIRPORTS_URL).decode('utf-8').splitlines()
    airports = {}
    for line in raw:
        cols = [c.strip().strip('"') for c in line.split(',')]
        iata = cols[4]
        if iata in HUBS:
            airports[iata] = (float(cols[6]), float(cols[7]))
    with open(AIRPORTS_CACHE,'wb') as f:
        pickle.dump(airports, f)

# 2) Fetch & filter routes
if os.path.exists(ROUTES_CACHE):
    with open(ROUTES_CACHE,'rb') as f:
        routes = pickle.load(f)
else:
    raw = download(ROUTES_URL).decode('utf-8').splitlines()
    routes = {
        (row[2], row[4])
        for row in csv.reader(raw)
        if row[2] in HUBS and row[4] in HUBS and row[2]!=row[4]
    }
    with open(ROUTES_CACHE,'wb') as f:
        pickle.dump(routes, f)

# 3) Write synthetic CSV with ENHANCED FIELDS
base_dep = datetime.utcnow().replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)

with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
    # ─── ENHANCED FIELDNAMES ───────────────────────────────────────────
    writer = csv.DictWriter(f, fieldnames=[
        'id','type',
        'departure_lat','departure_long',
        'arrival_lat','arrival_long',
        'departure_time','arrival_time','price',
        # NEW FIELDS:
        'provider',
        'booking_reference', 
        'duration_minutes',
        'distance_km',
        'capacity'
    ])
    writer.writeheader()

    for src, dst in sorted(routes):
        lat1, lon1 = airports[src]
        lat2, lon2 = airports[dst]
        dist = haversine(lat1, lon1, lat2, lon2)              # km
        duration_h = dist / CRUISE_SPEED_KMH
        duration_min = int(duration_h * 60)                   # convert to minutes
        dep_time = base_dep
        arr_time = dep_time + timedelta(hours=duration_h)
        
        # ─── NEW FIELD CALCULATIONS ────────────────────────────────────
        aircraft_type = determine_aircraft_type(dist)
        capacity = AIRCRAFT_CAPACITIES[aircraft_type]
        provider = get_provider_for_route(src, dst)
        booking_ref = generate_booking_reference()

        writer.writerow({
            'id':             str(uuid.uuid4()),
            'type':           'flight',
            'departure_lat':  lat1,
            'departure_long': lon1,
            'arrival_lat':    lat2,
            'arrival_long':   lon2,
            'departure_time': dep_time.isoformat() + 'Z',
            'arrival_time':   arr_time.isoformat() + 'Z',
            'price':          round(dist * PRICE_PER_KM, 2),
            # NEW FIELDS:
            'provider':           provider,
            'booking_reference':  booking_ref,
            'duration_minutes':   duration_min,
            'distance_km':        round(dist, 2),
            'capacity':           capacity
        })

print(f"🚀 Written {len(routes)} enhanced synthetic flights to {OUTPUT_CSV}")
print("✅ New fields added: provider, booking_reference, duration_minutes, distance_km, capacity")

# ─── ONE-OFF DOWNLOAD ─────────────────────────────────────────────────────
files.download(OUTPUT_CSV)
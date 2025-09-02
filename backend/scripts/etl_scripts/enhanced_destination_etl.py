# ─── DEPENDENCIES & CONFIG ─────────────────────────────────────────────
import csv, json, uuid, time, pickle, math
import requests
from statistics import mean
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

INPUT_CSV   = '/content/drive/MyDrive/booking-listings.csv'
OUTPUT_CSV  = 'destinations.csv'
CACHE_FILE  = 'dest_geocode_cache.pkl'
TIMEZONE_CACHE = 'timezone_cache.pkl'
CLIMATE_CACHE = 'climate_cache.pkl'

# Only keep these 15 hubs:
HUB_CITIES = {
    'Atlanta', 'Beijing', 'Dubai', 'Los Angeles', 'Tokyo',
    'Chicago', 'London', 'Shanghai', 'Paris', 'Dallas',
    'Guangzhou', 'Amsterdam', 'Frankfurt', 'Istanbul', 'New York'
}

# Exact center coords for distance filtering:
HUB_COORDINATES = {
    'Atlanta':     (33.7490, -84.3880),
    'Beijing':     (39.9042, 116.4074),
    'Dubai':       (25.2048, 55.2708),
    'Los Angeles': (34.0522, -118.2437),
    'Tokyo':       (35.6895, 139.6917),
    'Chicago':     (41.8781, -87.6298),
    'London':      (51.5074, -0.1278),
    'Shanghai':    (31.2304, 121.4737),
    'Paris':       (48.8566, 2.3522),
    'Dallas':      (32.7767, -96.7970),
    'Guangzhou':   (23.1291, 113.2644),
    'Amsterdam':   (52.3676, 4.9041),
    'Frankfurt':   (50.1109, 8.6821),
    'Istanbul':    (41.0082, 28.9784),
    'New York':    (40.7128, -74.0060),
}

# ─── NEW: API CONFIGURATIONS ────────────────────────────────────────────
# Get API keys from Colab secrets
GOOGLE_API_KEY = userdata.get('GOOGLE_MAPS_API_KEY')
OPENWEATHER_API_KEY = userdata.get('OPENWEATHER_API_KEY')  # You'll need to add this

# ─── NEW: COUNTRY/REGION MAPPINGS ───────────────────────────────────────
CITY_TO_COUNTRY_REGION = {
    'Atlanta':     ('United States', 'Georgia'),
    'Beijing':     ('China', 'Beijing Municipality'),
    'Dubai':       ('United Arab Emirates', 'Dubai'),
    'Los Angeles': ('United States', 'California'),
    'Tokyo':       ('Japan', 'Tokyo Metropolis'),
    'Chicago':     ('United States', 'Illinois'),
    'London':      ('United Kingdom', 'England'),
    'Shanghai':    ('China', 'Shanghai Municipality'),
    'Paris':       ('France', 'Île-de-France'),
    'Dallas':      ('United States', 'Texas'),
    'Guangzhou':   ('China', 'Guangdong Province'),
    'Amsterdam':   ('Netherlands', 'North Holland'),
    'Frankfurt':   ('Germany', 'Hesse'),
    'Istanbul':    ('Turkey', 'Istanbul Province'),
    'New York':    ('United States', 'New York'),
}

# ─── LOAD / INIT CACHES ─────────────────────────────────────────────────
def load_cache(cache_file):
    try:
        with open(cache_file, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return {}

def save_cache(cache, cache_file):
    with open(cache_file, 'wb') as f:
        pickle.dump(cache, f)

geo_cache = load_cache(CACHE_FILE)
timezone_cache = load_cache(TIMEZONE_CACHE)
climate_cache = load_cache(CLIMATE_CACHE)

# ─── NEW: TIMEZONE API INTEGRATION ──────────────────────────────────────
def get_timezone(lat, lon, location_name):
    """Get timezone using Google Time Zone API"""
    cache_key = f"{lat},{lon}"
    
    if cache_key in timezone_cache:
        return timezone_cache[cache_key]
    
    if not GOOGLE_API_KEY:
        # Fallback to hardcoded timezones for major cities
        timezone_map = {
            'Atlanta': 'America/New_York',
            'Beijing': 'Asia/Shanghai',
            'Dubai': 'Asia/Dubai',
            'Los Angeles': 'America/Los_Angeles',
            'Tokyo': 'Asia/Tokyo',
            'Chicago': 'America/Chicago',
            'London': 'Europe/London',
            'Shanghai': 'Asia/Shanghai',
            'Paris': 'Europe/Paris',
            'Dallas': 'America/Chicago',
            'Guangzhou': 'Asia/Shanghai',
            'Amsterdam': 'Europe/Amsterdam',
            'Frankfurt': 'Europe/Berlin',
            'Istanbul': 'Europe/Istanbul',
            'New York': 'America/New_York',
        }
        tz = timezone_map.get(location_name, 'UTC')
        timezone_cache[cache_key] = tz
        save_cache(timezone_cache, TIMEZONE_CACHE)
        return tz
    
    try:
        import time
        timestamp = int(time.time())
        url = f"https://maps.googleapis.com/maps/api/timezone/json"
        params = {
            'location': f"{lat},{lon}",
            'timestamp': timestamp,
            'key': GOOGLE_API_KEY
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data['status'] == 'OK':
            tz = data['timeZoneId']
            timezone_cache[cache_key] = tz
            save_cache(timezone_cache, TIMEZONE_CACHE)
            return tz
        else:
            print(f"⚠️ Timezone API error for {location_name}: {data.get('status')}")
            return 'UTC'
    except Exception as e:
        print(f"⚠️ Timezone lookup failed for {location_name}: {e}")
        return 'UTC'

# ─── NEW: CLIMATE DATA API INTEGRATION ──────────────────────────────────
def get_climate_data(lat, lon, location_name):
    """Get climate data using OpenWeatherMap API"""
    cache_key = f"{lat},{lon}"
    
    if cache_key in climate_cache:
        return climate_cache[cache_key]
    
    if not OPENWEATHER_API_KEY:
        # Fallback to hardcoded climate data for major cities
        climate_map = {
            'Atlanta': {'avg_temp_c': 16, 'rainfall_mm': 1270, 'humidity': 69, 'season': 'temperate'},
            'Beijing': {'avg_temp_c': 12, 'rainfall_mm': 570, 'humidity': 56, 'season': 'continental'},
            'Dubai': {'avg_temp_c': 27, 'rainfall_mm': 97, 'humidity': 60, 'season': 'desert'},
            'Los Angeles': {'avg_temp_c': 18, 'rainfall_mm': 381, 'humidity': 64, 'season': 'mediterranean'},
            'Tokyo': {'avg_temp_c': 16, 'rainfall_mm': 1520, 'humidity': 63, 'season': 'humid_subtropical'},
            'Chicago': {'avg_temp_c': 10, 'rainfall_mm': 940, 'humidity': 65, 'season': 'continental'},
            'London': {'avg_temp_c': 11, 'rainfall_mm': 690, 'humidity': 75, 'season': 'oceanic'},
            'Shanghai': {'avg_temp_c': 16, 'rainfall_mm': 1166, 'humidity': 74, 'season': 'humid_subtropical'},
            'Paris': {'avg_temp_c': 12, 'rainfall_mm': 640, 'humidity': 74, 'season': 'oceanic'},
            'Dallas': {'avg_temp_c': 19, 'rainfall_mm': 950, 'humidity': 64, 'season': 'humid_subtropical'},
            'Guangzhou': {'avg_temp_c': 22, 'rainfall_mm': 1736, 'humidity': 77, 'season': 'humid_subtropical'},
            'Amsterdam': {'avg_temp_c': 10, 'rainfall_mm': 820, 'humidity': 76, 'season': 'oceanic'},
            'Frankfurt': {'avg_temp_c': 10, 'rainfall_mm': 640, 'humidity': 71, 'season': 'oceanic'},
            'Istanbul': {'avg_temp_c': 14, 'rainfall_mm': 810, 'humidity': 72, 'season': 'mediterranean'},
            'New York': {'avg_temp_c': 13, 'rainfall_mm': 1200, 'humidity': 62, 'season': 'humid_continental'},
        }
        
        climate_data = climate_map.get(location_name, {
            'avg_temp_c': 15, 'rainfall_mm': 800, 'humidity': 65, 'season': 'temperate'
        })
        climate_cache[cache_key] = climate_data
        save_cache(climate_cache, CLIMATE_CACHE)
        return climate_data
    
    try:
        # Use OpenWeatherMap's Climate Data API or Current Weather as proxy
        url = f"http://api.openweathermap.org/data/2.5/weather"
        params = {
            'lat': lat,
            'lon': lon,
            'appid': OPENWEATHER_API_KEY,
            'units': 'metric'
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if response.status_code == 200:
            climate_data = {
                'avg_temp_c': data['main']['temp'],
                'humidity': data['main']['humidity'],
                'description': data['weather'][0]['description'],
                'season': 'temperate'  # Would need seasonal data for accurate classification
            }
            climate_cache[cache_key] = climate_data
            save_cache(climate_cache, CLIMATE_CACHE)
            return climate_data
        else:
            print(f"⚠️ Climate API error for {location_name}: {data.get('message')}")
            return {'avg_temp_c': 15, 'humidity': 65, 'season': 'temperate'}
    except Exception as e:
        print(f"⚠️ Climate lookup failed for {location_name}: {e}")
        return {'avg_temp_c': 15, 'humidity': 65, 'season': 'temperate'}

# ─── NEW: POPULARITY SCORE CALCULATION ──────────────────────────────────
def calculate_popularity_score(location_name, num_properties, avg_rating, total_reviews=0):
    """Calculate popularity score based on various factors"""
    # Base score from number of properties (normalized to 0-40)
    property_score = min(40, (num_properties / 100) * 40)
    
    # Rating contribution (0-30)
    rating_score = (avg_rating / 5.0) * 30 if avg_rating else 15
    
    # Review volume contribution (0-30)
    review_score = min(30, (total_reviews / 1000) * 30)
    
    # City-specific bonus for major tourist destinations
    city_bonuses = {
        'Paris': 15, 'London': 15, 'New York': 15, 'Tokyo': 12,
        'Dubai': 10, 'Los Angeles': 8, 'Amsterdam': 8,
        'Istanbul': 6, 'Shanghai': 6, 'Beijing': 5,
        'Frankfurt': 4, 'Chicago': 4, 'Atlanta': 3,
        'Dallas': 2, 'Guangzhou': 2
    }
    
    city_bonus = city_bonuses.get(location_name, 0)
    
    total_score = property_score + rating_score + review_score + city_bonus
    return min(100, round(total_score, 1))

# ─── SET UP NOMINATIM (only for missing hubs) ────────────────────────
geolocator = Nominatim(user_agent="colab_dest_etl")
geocode = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=1,
    max_retries=3,
    error_wait_seconds=5,
    swallow_exceptions=True
)

# ─── FIRST PASS: BUILD DESTINATION AGGREGATES ───────────────────────
dests = {}  # loc → { name, coords_list, images_set, ratings_list, review_count }

with open(INPUT_CSV, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Only our hub cities
        try:
            loc = json.loads(row.get('full_location') or '{}').get('display_location')
        except:
            loc = None
        if not loc:
            loc = row['city']
        if not loc or loc not in HUB_CITIES:
            continue

        d = dests.setdefault(loc, {
            'name':         loc,
            'coords':       [],
            'images':       set(),
            'ratings':      [],
            'review_count': 0,
            'property_count': 0
        })

        # collect existing coords
        try:
            mc = json.loads(row.get('map_coordinates') or '{}')
            lat, lon = mc.get('lat'), mc.get('lon')
            if lat is not None and lon is not None:
                d['coords'].append((lat, lon))
        except:
            pass

        # first image only
        if row.get('image'):
            d['images'].add(row['image'])

        # rating and review data
        try:
            d['ratings'].append(float(row['review_score']))
        except:
            pass
        
        try:
            d['review_count'] += int(row.get('review_count', 0))
        except:
            pass
        
        d['property_count'] += 1

# ─── GEOCODE ANY HUBS WITHOUT REPORTED COORDS ────────────────────────
need = [loc for loc,data in dests.items() if not data['coords'] and loc not in geo_cache]
print(f"🔍 Need to geocode {len(need)} unique locations")

for loc in need:
    place = geocode(loc, timeout=10)
    if place:
        geo_cache[loc] = (place.latitude, place.longitude)
    else:
        geo_cache[loc] = (None, None)
    save_cache(geo_cache, CACHE_FILE)

# attach final lat/lon to each hub
for loc, data in dests.items():
    if data['coords']:
        data['lat'], data['lon'] = data['coords'][0]
    else:
        data['lat'], data['lon'] = geo_cache.get(loc, (None, None))

# ─── HELPER: great‐circle distance ─────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ     = math.radians(lat2 - lat1)
    Δλ     = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ─── WRITE OUT ENHANCED `destinations.csv` ──────────────────────────────
with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
    # ─── ENHANCED FIELDNAMES ───────────────────────────────────────────
    writer = csv.DictWriter(f, fieldnames=[
        'id','name','description','latitude','longitude','images','rating',
        # NEW FIELDS:
        'country',
        'region', 
        'timezone',
        'climate_data',
        'popularity_score'
    ])
    writer.writeheader()

    for loc, data in dests.items():
        lat, lon = data['lat'], data['lon']
        if lat is None or lon is None:
            continue

        # 20 km distance check
        hub_lat, hub_lon = HUB_COORDINATES[loc]
        if haversine(lat, lon, hub_lat, hub_lon) > 20:
            continue

        # ─── NEW FIELD CALCULATIONS ────────────────────────────────────
        # Get country and region
        country, region = CITY_TO_COUNTRY_REGION.get(loc, ('Unknown', 'Unknown'))
        
        # Get timezone
        timezone = get_timezone(lat, lon, loc)
        
        # Get climate data
        climate_data = get_climate_data(lat, lon, loc)
        
        # Calculate popularity score
        avg_rating = mean(data['ratings']) if data['ratings'] else None
        popularity_score = calculate_popularity_score(
            loc, 
            data['property_count'], 
            avg_rating,
            data['review_count']
        )

        writer.writerow({
            'id':          str(uuid.uuid4()),
            'name':        data['name'],
            'description': None,
            'latitude':    lat,
            'longitude':   lon,
            'images':      json.dumps(list(data['images'])[:1]),
            'rating':      round(avg_rating, 2) if avg_rating else '',
            # NEW FIELDS:
            'country':         country,
            'region':          region,
            'timezone':        timezone,
            'climate_data':    json.dumps(climate_data),
            'popularity_score': popularity_score
        })

print(f"✅ Wrote enhanced {OUTPUT_CSV}")
print("✅ New fields added: country, region, timezone, climate_data, popularity_score")
files.download(OUTPUT_CSV)
# ─── DEPENDENCIES & CONFIG ──────────────────────────────────────────────
import csv
import json
import uuid
import pickle
import re
from geopy.geocoders import GoogleV3
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderServiceError, GeocoderQueryError

INPUT_CSV    = '/content/drive/MyDrive/booking-listings.csv'
OUTPUT_CSV   = 'accommodations.csv'
CACHE_FILE   = 'geocode_accommodations_cache.pkl'

# Only keep properties in these "hub" cities
HUB_CITIES = {
    'Atlanta', 'Beijing', 'Dubai', 'Los Angeles', 'Tokyo',
    'Chicago', 'London', 'Shanghai', 'Paris', 'Dallas',
    'Guangzhou', 'Amsterdam', 'Frankfurt', 'Istanbul', 'New York'
}

# ─── NEW: ACCOMMODATION TYPE MAPPING ────────────────────────────────────
def determine_accommodation_type(title, property_type=None):
    """Extract accommodation type from title or property_type"""
    title_lower = (title or '').lower()
    prop_lower = (property_type or '').lower()
    
    # Check property_type first if available
    if 'hotel' in prop_lower or 'resort' in prop_lower:
        return 'hotel'
    elif 'apartment' in prop_lower or 'flat' in prop_lower:
        return 'apartment'
    elif 'hostel' in prop_lower:
        return 'hostel'
    elif 'villa' in prop_lower or 'house' in prop_lower:
        return 'house'
    elif 'b&b' in prop_lower or 'bed and breakfast' in prop_lower:
        return 'bed_and_breakfast'
    
    # Fallback to title analysis
    if any(word in title_lower for word in ['hotel', 'resort', 'inn']):
        return 'hotel'
    elif any(word in title_lower for word in ['apartment', 'flat', 'studio']):
        return 'apartment'
    elif 'hostel' in title_lower:
        return 'hostel'
    elif any(word in title_lower for word in ['villa', 'house', 'home']):
        return 'house'
    elif any(word in title_lower for word in ['b&b', 'bed and breakfast']):
        return 'bed_and_breakfast'
    else:
        return 'hotel'  # default

def extract_star_rating(title, tags=None):
    """Extract star rating from title or tags"""
    # Look for star patterns in title
    star_patterns = [
        r'(\d)\s*star',
        r'(\d)\*',
        r'★{1,5}',
        r'(\d)\s*stelle'  # Italian
    ]
    
    for pattern in star_patterns:
        match = re.search(pattern, (title or '').lower())
        if match:
            try:
                return min(int(match.group(1)), 5)
            except:
                pass
    
    # Check tags for star rating
    if tags:
        try:
            tag_list = json.loads(tags) if isinstance(tags, str) else tags
            for tag in tag_list:
                if 'star' in str(tag).lower():
                    numbers = re.findall(r'\d+', str(tag))
                    if numbers:
                        return min(int(numbers[0]), 5)
        except:
            pass
    
    return None  # No star rating found

def calculate_capacity(nb_bedrooms=None, nb_rooms=None, accommodates=None, title=None):
    """Calculate accommodation capacity from available data"""
    # Try accommodates field first
    if accommodates:
        try:
            return max(1, int(accommodates))
        except:
            pass
    
    # Calculate from bedrooms (assume 2 people per bedroom)
    if nb_bedrooms:
        try:
            bedrooms = int(nb_bedrooms)
            return max(2, bedrooms * 2)
        except:
            pass
    
    # Calculate from total rooms (assume 1.5 people per room)
    if nb_rooms:
        try:
            rooms = int(nb_rooms)
            return max(1, int(rooms * 1.5))
        except:
            pass
    
    # Extract from title
    if title:
        capacity_patterns = [
            r'(\d+)\s*guests?',
            r'sleeps?\s*(\d+)',
            r'accommodates?\s*(\d+)'
        ]
        for pattern in capacity_patterns:
            match = re.search(pattern, title.lower())
            if match:
                try:
                    return int(match.group(1))
                except:
                    pass
    
    return 2  # Default capacity

def get_checkin_checkout_times(property_type=None):
    """Get standard check-in/out times based on property type"""
    if property_type == 'hostel':
        return '15:00', '11:00'
    elif property_type in ['apartment', 'house', 'villa']:
        return '16:00', '10:00'
    else:  # hotel default
        return '15:00', '11:00'

def generate_contact_info(title, location=None):
    """Generate placeholder contact information"""
    import random
    
    # Generate a realistic phone number (placeholder)
    area_codes = ['202', '212', '213', '312', '415', '617', '713', '818']
    area_code = random.choice(area_codes)
    phone = f"+1-{area_code}-{random.randint(100,999)}-{random.randint(1000,9999)}"
    
    # Generate email based on property name
    name_part = re.sub(r'[^a-zA-Z0-9]', '', (title or 'property')[:20]).lower()
    email = f"info@{name_part}.com"
    
    return {
        "phone": phone,
        "email": email,
        "website": f"https://www.{name_part}.com"
    }

# Load Google Maps API key from Colab secrets
API_KEY = userdata.get('GOOGLE_MAPS_API_KEY')
if not API_KEY:
    raise RuntimeError("Please set GOOGLE_MAPS_API_KEY via `%env GOOGLE_MAPS_API_KEY YOUR_KEY`")

# ─── LOAD / INIT CACHE ────────────────────────────────────────────────
try:
    with open(CACHE_FILE, 'rb') as f:
        cache = pickle.load(f)
except FileNotFoundError:
    cache = {}

def save_cache():
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump(cache, f)

# ─── SET UP GEOCODER + RATE LIMITER ─────────────────────────────────
geolocator = GoogleV3(api_key=API_KEY, timeout=10)
geocode = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=0.2,
    max_retries=3,
    error_wait_seconds=10,
    swallow_exceptions=True
)

def safe_geocode(query: str):
    try:
        return geocode(query, timeout=10)
    except Exception as e:
        print(f"⚠️ Permanent geocode failure for {query!r}: {e}")
        return None

# ─── PRE-SCAN for UNIQUE MISSING ADDRESSES ──────────────────────────
to_lookup = set()
with open(INPUT_CSV, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        city = row.get('city')
        if city not in HUB_CITIES:
            continue

        coords = {}
        try:
            coords = json.loads(row.get('map_coordinates') or '{}')
        except json.JSONDecodeError:
            pass

        if not coords.get('lat') or not coords.get('lon'):
            parts = [row.get('address'), city, row.get('listing_country')]
            q = ', '.join(p for p in parts if p)
            if q and q not in cache:
                to_lookup.add(q)

print(f"🔍 {len(to_lookup)} unique addresses need geocoding")

# ─── ENHANCED CSV GENERATION ────────────────────────────────────────────
import math
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ     = math.radians(lat2 - lat1)
    Δλ     = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# Hub coordinates for 20 km filter:
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

with open(INPUT_CSV, newline='', encoding='utf-8') as fin, \
     open(OUTPUT_CSV,  'w', newline='', encoding='utf-8') as fout:

    reader = csv.DictReader(fin)
    # ─── ENHANCED FIELDNAMES ───────────────────────────────────────────
    writer = csv.DictWriter(fout, fieldnames=[
        'id','name','description','latitude','longitude',
        'images','price','rating','amenities',
        # NEW FIELDS:
        'type',
        'star_rating',
        'capacity',
        'check_in_time',
        'check_out_time',
        'contact_info'
    ])
    writer.writeheader()

    for row in reader:
        city = row.get('city')
        if city not in HUB_CITIES:
            continue

        # 1) Try the provided map_coordinates
        lat = lon = None
        try:
            mc = json.loads(row.get('map_coordinates') or '{}')
            lat, lon = mc.get('lat'), mc.get('lon')
        except:
            pass

        # 2) Fallback to our cache
        if not lat or not lon:
            parts = [row.get('address'), city, row.get('listing_country')]
            q = ', '.join(p for p in parts if p)
            lat, lon = cache.get(q, (None, None))

        # Skip if no coordinates found
        if not lat or not lon:
            continue

        # 3) Optional 20 km filter
        # hub_lat, hub_lon = HUB_COORDINATES[city]
        # if haversine(lat, lon, hub_lat, hub_lon) > 20:
        #     continue

        # 4) Build enhanced fields
        images = [row['image']] if row.get('image') else []
        amenities = []
        
        if row.get('tags'):
            try:
                amenities += json.loads(row['tags'])
            except:
                pass
        if row.get('property_sustainability'):
            try:
                ps = json.loads(row['property_sustainability'])
                amenities += ps.get('facilities') or []
            except:
                pass

        # ─── NEW FIELD CALCULATIONS ────────────────────────────────────
        property_type = determine_accommodation_type(
            row.get('title'), 
            row.get('property_type')
        )
        
        star_rating = extract_star_rating(
            row.get('title'), 
            row.get('tags')
        )
        
        capacity = calculate_capacity(
            row.get('nb_bedrooms'),
            row.get('nb_rooms'), 
            row.get('accommodates'),
            row.get('title')
        )
        
        check_in, check_out = get_checkin_checkout_times(property_type)
        
        contact_info = generate_contact_info(
            row.get('title'),
            city
        )

        writer.writerow({
            'id':          str(uuid.uuid4()),
            'name':        row['title'],
            'description': None,
            'latitude':    lat or '',
            'longitude':   lon or '',
            'images':      json.dumps(images),
            'price':       row['final_price'],
            'rating':      row['review_score'],
            'amenities':   json.dumps(amenities),
            # NEW FIELDS:
            'type':            property_type,
            'star_rating':     star_rating,
            'capacity':        capacity,
            'check_in_time':   check_in,
            'check_out_time':  check_out,
            'contact_info':    json.dumps(contact_info)
        })

print(f"✅ Wrote enhanced seed file → {OUTPUT_CSV}")
print("✅ New fields added: type, star_rating, capacity, check_in_time, check_out_time, contact_info")
files.download(OUTPUT_CSV)
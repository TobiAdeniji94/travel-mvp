# ─── IMPORTS & CONFIG ──────────────────────────────────────────────────
import os, csv, json, uuid, time, pickle
from statistics import mean
import googlemaps
import re

# Path to input csv
INPUT_CSV  = '/content/drive/MyDrive/booking-listings.csv'
OUTPUT_CSV = 'activities.csv'

# Cache every API lookup (place details & geocodes)
CACHE_FILE = 'places_cache.pkl'
try:
    with open(CACHE_FILE, 'rb') as f:
        cache = pickle.load(f)
except FileNotFoundError:
    cache = {}

def save_cache():
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump(cache, f)

# "Hub cities" to limit scope
HUBS = {
    'Atlanta':    (33.7490, -84.3880),
    'Beijing':    (39.9042, 116.4074),
    'Dubai':      (25.2048, 55.2708),
    'Los Angeles':(34.0522, -118.2437),
    'Tokyo':      (35.6895, 139.6917),
    'Chicago':    (41.8781, -87.6298),
    'London':     (51.5074, -0.1278),
    'Shanghai':   (31.2304, 121.4737),
    'Paris':      (48.8566, 2.3522),
    'Dallas':     (32.7767, -96.7970),
    'Guangzhou':  (23.1291, 113.2644),
    'Amsterdam':  (52.3676, 4.9041),
    'Frankfurt':  (50.1109, 8.6821),
    'Istanbul':   (41.0082, 28.9784),
    'New York':   (40.7128, -74.0060),
}

# ─── NEW: ACTIVITY TYPE MAPPING & ENRICHMENT ────────────────────────────
def map_google_place_type(place_types):
    """Map Google Places API types to our activity categories"""
    if not place_types:
        return 'attraction'
    
    # Priority mapping - first match wins
    type_mapping = {
        'museum': 'museum',
        'art_gallery': 'museum', 
        'zoo': 'zoo',
        'aquarium': 'aquarium',
        'amusement_park': 'theme_park',
        'park': 'park',
        'tourist_attraction': 'attraction',
        'church': 'religious_site',
        'mosque': 'religious_site',
        'synagogue': 'religious_site',
        'temple': 'religious_site',
        'shopping_mall': 'shopping',
        'stadium': 'sports_venue',
        'theater': 'entertainment',
        'movie_theater': 'entertainment',
        'night_club': 'nightlife',
        'bar': 'nightlife',
        'restaurant': 'dining',
        'spa': 'wellness',
        'gym': 'fitness',
        'library': 'cultural',
        'university': 'educational',
        'hospital': 'healthcare'
    }
    
    for place_type in place_types:
        if place_type in type_mapping:
            return type_mapping[place_type]
    
    return 'attraction'  # default fallback

def estimate_duration_minutes(activity_type, name=''):
    """Estimate activity duration based on type and name"""
    name_lower = name.lower()
    
    # Duration mapping by type (in minutes)
    duration_map = {
        'museum': 120,
        'art_gallery': 90,
        'zoo': 180,
        'aquarium': 120,
        'theme_park': 360,  # 6 hours
        'park': 90,
        'attraction': 90,
        'religious_site': 45,
        'shopping': 120,
        'sports_venue': 180,
        'entertainment': 150,
        'nightlife': 180,
        'dining': 90,
        'wellness': 120,
        'fitness': 60,
        'cultural': 90,
        'educational': 60,
        'healthcare': 30
    }
    
    base_duration = duration_map.get(activity_type, 90)
    
    # Adjust based on name hints
    if any(word in name_lower for word in ['tour', 'guided', 'walking']):
        return min(base_duration + 30, 240)
    elif any(word in name_lower for word in ['quick', 'express', 'brief']):
        return max(base_duration - 30, 30)
    elif any(word in name_lower for word in ['full day', 'all day']):
        return 480  # 8 hours
    elif any(word in name_lower for word in ['half day']):
        return 240  # 4 hours
    
    return base_duration

def determine_difficulty_level(activity_type, name=''):
    """Determine difficulty level based on activity type and name"""
    name_lower = name.lower()
    
    # Check name for difficulty indicators first
    if any(word in name_lower for word in ['easy', 'beginner', 'gentle', 'relaxed']):
        return 'easy'
    elif any(word in name_lower for word in ['challenging', 'difficult', 'advanced', 'expert']):
        return 'hard'
    elif any(word in name_lower for word in ['moderate', 'intermediate']):
        return 'moderate'
    
    # Default by activity type
    difficulty_map = {
        'museum': 'easy',
        'art_gallery': 'easy',
        'zoo': 'easy',
        'aquarium': 'easy',
        'theme_park': 'moderate',
        'park': 'easy',
        'attraction': 'easy',
        'religious_site': 'easy',
        'shopping': 'easy',
        'sports_venue': 'moderate',
        'entertainment': 'easy',
        'nightlife': 'easy',
        'dining': 'easy',
        'wellness': 'easy',
        'fitness': 'moderate',
        'cultural': 'easy',
        'educational': 'easy',
        'healthcare': 'easy'
    }
    
    return difficulty_map.get(activity_type, 'easy')

def determine_age_restrictions(activity_type, name=''):
    """Determine age restrictions based on activity type and name"""
    name_lower = name.lower()
    
    # Check name for age indicators
    if any(word in name_lower for word in ['adult only', '18+', '21+', 'adults only']):
        return '18+ only'
    elif any(word in name_lower for word in ['kids', 'children', 'family']):
        return 'All ages'
    elif 'bar' in name_lower or 'club' in name_lower:
        return '21+ for alcohol service'
    
    # Default by activity type
    restrictions_map = {
        'museum': 'All ages',
        'art_gallery': 'All ages',
        'zoo': 'All ages',
        'aquarium': 'All ages',
        'theme_park': 'Height restrictions may apply',
        'park': 'All ages',
        'attraction': 'All ages',
        'religious_site': 'All ages, modest dress required',
        'shopping': 'All ages',
        'sports_venue': 'Age varies by event',
        'entertainment': 'Age varies by show',
        'nightlife': '21+ for alcohol service',
        'dining': 'All ages',
        'wellness': '16+ recommended',
        'fitness': '16+ recommended',
        'cultural': 'All ages',
        'educational': 'All ages',
        'healthcare': 'Varies by service'
    }
    
    return restrictions_map.get(activity_type, 'All ages')

def determine_accessibility_info(activity_type, name=''):
    """Determine accessibility information"""
    name_lower = name.lower()
    
    # Check for accessibility mentions in name
    if any(word in name_lower for word in ['accessible', 'wheelchair', 'disabled']):
        return 'Wheelchair accessible, accessible facilities available'
    
    # Defaults by type
    accessibility_map = {
        'museum': 'Most areas wheelchair accessible, contact for specific needs',
        'art_gallery': 'Wheelchair accessible, audio guides available',
        'zoo': 'Wheelchair accessible paths, some terrain may be challenging',
        'aquarium': 'Fully wheelchair accessible',
        'theme_park': 'Accessibility varies by attraction, contact park for details',
        'park': 'Some paths wheelchair accessible, natural terrain varies',
        'attraction': 'Contact venue for accessibility information',
        'religious_site': 'Historic sites may have limited accessibility',
        'shopping': 'Wheelchair accessible, accessible restrooms available',
        'sports_venue': 'Wheelchair accessible seating available',
        'entertainment': 'Wheelchair accessible, assisted listening available',
        'nightlife': 'Accessibility varies, contact venue',
        'dining': 'Wheelchair accessible entrance and seating',
        'wellness': 'Accessible facilities, adaptive equipment available',
        'fitness': 'Wheelchair accessible, adaptive equipment available',
        'cultural': 'Most areas accessible, contact for specific accommodations',
        'educational': 'Wheelchair accessible, accommodations available',
        'healthcare': 'Fully accessible facilities'
    }
    
    return accessibility_map.get(activity_type, 'Contact venue for accessibility information')

# Initialize Google Maps client
API_KEY = userdata.get('GOOGLE_MAPS_API_KEY')
if not API_KEY:
    raise RuntimeError("Please set GOOGLE_MAPS_API_KEY via `%env` before running.")
gmaps   = googlemaps.Client(key=API_KEY)

# Helper to wrap any API call + cache by key - ENHANCED VERSION
def fetch_details(place_id):
    if place_id in cache:
        return cache[place_id]
    
    # ─── ENHANCED API CALL WITH MORE FIELDS ────────────────────────────
    res = gmaps.place(
        place_id=place_id,
        fields=[
            "name",
            "geometry",
            "photo",
            "price_level",
            "opening_hours",
            "rating",
            "editorial_summary",
            "formatted_address",  # NEW: For better location context
            "reviews"             # NEW: For content analysis
        ]
    )
    result = res.get("result", {})
    cache[place_id] = result
    save_cache()
    return result

# ─── ENHANCED ETL: scan hubs → nearby attractions → details → CSV ──────
with open(INPUT_CSV, newline='', encoding='utf-8') as fin, \
     open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as fout:

    reader = csv.DictReader(fin)
    # ─── ENHANCED FIELDNAMES ───────────────────────────────────────────
    writer = csv.DictWriter(fout, fieldnames=[
        "id",
        "name",
        "description",
        "latitude",
        "longitude",
        "images",
        "price",
        "opening_hours",
        "rating",
        # NEW FIELDS:
        "type",
        "duration_minutes",
        "difficulty_level",
        "age_restrictions",
        "accessibility_info"
    ])
    writer.writeheader()

    seen_place_ids = set()

    # 1) For each hub, pull up to 60 pages of nearby "tourist_attraction"
    for city, (lat, lng) in HUBS.items():
        print(f"🔍 Processing {city}...")
        
        page = gmaps.places_nearby(
            location=(lat, lng),
            radius=20_000,  # 20 km as mentioned in recommendations
            type="tourist_attraction"
        )
        
        while page:
            for p in page.get("results", []):
                pid = p["place_id"]
                if pid in seen_place_ids:
                    continue
                seen_place_ids.add(pid)

                # Get types from places_nearby response (already available)
                place_types = p.get("types", [])
                
                details = fetch_details(pid)
                loc     = details.get("geometry", {}).get("location", {})
                photos  = details.get("photos", [])
                
                # ─── NEW FIELD PROCESSING ──────────────────────────────
                activity_type = map_google_place_type(place_types)
                activity_name = details.get("name", "")
                
                duration = estimate_duration_minutes(activity_type, activity_name)
                difficulty = determine_difficulty_level(activity_type, activity_name)
                age_restrictions = determine_age_restrictions(activity_type, activity_name)
                accessibility = determine_accessibility_info(activity_type, activity_name)

                # Build image URLs (max 3)
                img_urls = [
                    f"https://maps.googleapis.com/maps/api/place/photo"
                    f"?maxwidth=400&photoreference={ph['photo_reference']}"
                    f"&key={API_KEY}"
                    for ph in photos[:3]
                ]

                writer.writerow({
                    "id":             str(uuid.uuid4()),
                    "name":           activity_name,
                    "description":    details.get("editorial_summary", {}).get("overview", ""),
                    "latitude":       loc.get("lat", ""),
                    "longitude":      loc.get("lng", ""),
                    "images":         json.dumps(img_urls),
                    "price":          details.get("price_level", ""),
                    "opening_hours":  json.dumps(details.get("opening_hours", {}).get("weekday_text", [])),
                    "rating":         details.get("rating", ""),
                    # NEW FIELDS:
                    "type":               activity_type,
                    "duration_minutes":   duration,
                    "difficulty_level":   difficulty,
                    "age_restrictions":   age_restrictions,
                    "accessibility_info": accessibility
                })
                
                # throttle a bit to avoid rate-limit spikes
                time.sleep(0.05)

            # fetch next page token
            token = page.get("next_page_token")
            if not token:
                break
            time.sleep(2)  # next_page_token needs a short delay
            page = gmaps.places_nearby(page_token=token)

print(f"✅ Wrote enhanced {OUTPUT_CSV}")
print("✅ New fields added: type, duration_minutes, difficulty_level, age_restrictions, accessibility_info")
files.download(OUTPUT_CSV)
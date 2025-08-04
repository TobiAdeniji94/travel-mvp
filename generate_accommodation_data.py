# ─── STANDALONE ACCOMMODATION DATA GENERATOR ─────────────────────────────
"""
Generate accommodation data without requiring external source files
Uses city coordinates and realistic data patterns
"""

import csv
import json
import uuid
import random
from typing import List, Dict, Any

# Hub cities with coordinates
HUB_CITIES = {
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

# Accommodation templates for realistic names
HOTEL_NAMES = [
    "{city} Grand Hotel", "Luxury {city} Resort", "{city} Business Center",
    "Downtown {city} Inn", "{city} Plaza Hotel", "The {city} Suite",
    "{city} Airport Hotel", "Historic {city} Hotel", "{city} City Center",
    "Premium {city} Lodge", "{city} Boutique Hotel", "Modern {city} Stay"
]

APARTMENT_NAMES = [
    "Cozy {city} Apartment", "Spacious {city} Flat", "Central {city} Studio",
    "Luxury {city} Loft", "Modern {city} Residence", "Downtown {city} Condo",
    "Charming {city} Home", "Executive {city} Suite", "Family {city} Apartment"
]

HOSTEL_NAMES = [
    "{city} Backpackers", "Budget {city} Hostel", "Young Travelers {city}",
    "Social {city} Hub", "Eco {city} Hostel", "Urban {city} Backpackers"
]

# Amenities by property type
HOTEL_AMENITIES = [
    "Free WiFi", "24-hour reception", "Room service", "Fitness center",
    "Business center", "Restaurant", "Bar", "Parking", "Airport shuttle",
    "Concierge service", "Laundry service", "Air conditioning"
]

APARTMENT_AMENITIES = [
    "Kitchen", "Free WiFi", "Washing machine", "Air conditioning",
    "Parking", "Balcony", "Dishwasher", "Microwave", "Private entrance",
    "Garden view", "City view", "Elevator"
]

HOSTEL_AMENITIES = [
    "Free WiFi", "Shared kitchen", "Common area", "Lockers",
    "Laundry facilities", "24-hour reception", "Luggage storage",
    "Tourist information", "Bicycle rental", "Air conditioning"
]

def generate_coordinates_near_city(city_lat: float, city_lon: float, count: int) -> List[tuple]:
    """Generate realistic coordinates near a city center"""
    coords = []
    for _ in range(count):
        # Generate points within ~20km radius
        lat_offset = random.uniform(-0.18, 0.18)  # ~20km in degrees
        lon_offset = random.uniform(-0.18, 0.18)
        
        lat = round(city_lat + lat_offset, 6)
        lon = round(city_lon + lon_offset, 6)
        coords.append((lat, lon))
    
    return coords

def generate_property_name(property_type: str, city: str) -> str:
    """Generate realistic property name"""
    if property_type == "hotel":
        template = random.choice(HOTEL_NAMES)
    elif property_type == "apartment":
        template = random.choice(APARTMENT_NAMES)
    elif property_type == "hostel":
        template = random.choice(HOSTEL_NAMES)
    else:
        template = "{city} " + random.choice(["Inn", "Lodge", "Place", "Stay"])
    
    return template.format(city=city)

def generate_amenities(property_type: str) -> List[str]:
    """Generate realistic amenities for property type"""
    if property_type == "hotel":
        base_amenities = HOTEL_AMENITIES
        count = random.randint(6, 12)
    elif property_type == "apartment":
        base_amenities = APARTMENT_AMENITIES
        count = random.randint(4, 8)
    elif property_type == "hostel":
        base_amenities = HOSTEL_AMENITIES
        count = random.randint(4, 7)
    else:
        base_amenities = HOTEL_AMENITIES
        count = random.randint(5, 9)
    
    return random.sample(base_amenities, min(count, len(base_amenities)))

def generate_pricing(property_type: str, city: str) -> float:
    """Generate realistic pricing based on property type and city"""
    # Base pricing by city (premium multiplier)
    city_multipliers = {
        'London': 1.8, 'Paris': 1.7, 'New York': 1.6, 'Tokyo': 1.5,
        'Dubai': 1.4, 'Amsterdam': 1.3, 'Los Angeles': 1.2,
        'Shanghai': 1.0, 'Beijing': 0.9, 'Istanbul': 0.8,
        'Frankfurt': 1.1, 'Chicago': 1.0, 'Dallas': 0.9,
        'Atlanta': 0.8, 'Guangzhou': 0.7
    }
    
    # Base prices by type (USD per night)
    base_prices = {
        'hotel': random.uniform(80, 300),
        'apartment': random.uniform(60, 200),
        'hostel': random.uniform(20, 60),
        'bed_and_breakfast': random.uniform(50, 150),
        'house': random.uniform(100, 400)
    }
    
    multiplier = city_multipliers.get(city, 1.0)
    base_price = base_prices.get(property_type, 100)
    
    return round(base_price * multiplier, 2)

def generate_accommodation_data(properties_per_city: int = 50) -> List[Dict[str, Any]]:
    """Generate comprehensive accommodation data"""
    accommodations = []
    
    for city, (city_lat, city_lon) in HUB_CITIES.items():
        print(f"🏨 Generating {properties_per_city} properties for {city}...")
        
        # Generate coordinates for this city
        coordinates = generate_coordinates_near_city(city_lat, city_lon, properties_per_city)
        
        for i, (lat, lon) in enumerate(coordinates):
            # Property type distribution (realistic ratios)
            property_type = random.choices(
                ['hotel', 'apartment', 'hostel', 'bed_and_breakfast', 'house'],
                weights=[40, 35, 10, 10, 5]  # Hotels and apartments most common
            )[0]
            
            # Generate all fields
            name = generate_property_name(property_type, city)
            price = generate_pricing(property_type, city)
            rating = round(random.uniform(3.0, 5.0), 1)
            amenities = generate_amenities(property_type)
            
            # Enhanced fields
            star_rating = None
            if property_type == "hotel":
                star_rating = random.choices([2, 3, 4, 5], weights=[10, 40, 35, 15])[0]
            
            capacity = {
                'hotel': random.randint(1, 4),
                'apartment': random.randint(2, 8),
                'hostel': random.randint(1, 12),
                'bed_and_breakfast': random.randint(1, 4),
                'house': random.randint(4, 12)
            }[property_type]
            
            check_in_times = {
                'hotel': '15:00',
                'apartment': '16:00',
                'hostel': '15:00',
                'bed_and_breakfast': '14:00',
                'house': '16:00'
            }
            
            check_out_times = {
                'hotel': '11:00',
                'apartment': '10:00',
                'hostel': '11:00',
                'bed_and_breakfast': '11:00',
                'house': '10:00'
            }
            
            # Generate contact info
            contact_info = {
                "phone": f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}",
                "email": f"info@{name.lower().replace(' ', '').replace(city.lower(), '')}{city.lower()}.com",
                "website": f"https://www.{name.lower().replace(' ', '')}.com"
            }
            
            accommodation = {
                'id': str(uuid.uuid4()),
                'name': name,
                'description': f"Comfortable {property_type} in {city}",
                'latitude': lat,
                'longitude': lon,
                'images': [f"https://example.com/images/{uuid.uuid4()}.jpg"],
                'price': price,
                'rating': rating,
                'amenities': amenities,
                'type': property_type,
                'star_rating': star_rating,
                'capacity': capacity,
                'check_in_time': check_in_times[property_type],
                'check_out_time': check_out_times[property_type],
                'contact_info': contact_info
            }
            
            accommodations.append(accommodation)
    
    return accommodations

def save_to_csv(accommodations: List[Dict[str, Any]], filename: str = "accommodations.csv"):
    """Save accommodation data to CSV"""
    fieldnames = [
        'id', 'name', 'description', 'latitude', 'longitude',
        'images', 'price', 'rating', 'amenities',
        'type', 'star_rating', 'capacity', 'check_in_time', 'check_out_time', 'contact_info'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for acc in accommodations:
            # Convert lists and dicts to JSON strings
            row = acc.copy()
            row['images'] = json.dumps(row['images'])
            row['amenities'] = json.dumps(row['amenities'])
            row['contact_info'] = json.dumps(row['contact_info'])
            
            writer.writerow(row)
    
    print(f"✅ Saved {len(accommodations)} accommodations to {filename}")

def main():
    """Generate accommodation data"""
    print("🏨 ACCOMMODATION DATA GENERATOR")
    print("=" * 50)
    
    # Generate 50 properties per city (750 total)
    accommodations = generate_accommodation_data(properties_per_city=50)
    
    # Save to CSV
    save_to_csv(accommodations, "backend/scripts/accomodation.csv")
    
    print(f"\n📊 GENERATION COMPLETE")
    print(f"Total accommodations: {len(accommodations)}")
    print(f"Cities covered: {len(HUB_CITIES)}")

if __name__ == "__main__":
    main()
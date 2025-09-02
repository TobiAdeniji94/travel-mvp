# ─── ACCOMMODATION ETL DIAGNOSTIC SCRIPT ──────────────────────────────
import csv
import json
import os
from pathlib import Path

# Check different possible input file locations
POSSIBLE_INPUT_PATHS = [
    '/content/drive/MyDrive/booking-listings.csv',  # Original Colab path
    'booking-listings.csv',                         # Current directory
    '../booking-listings.csv',                      # Parent directory
    'backend/scripts/booking-listings.csv',         # In scripts folder
    'scripts/booking-listings.csv'                  # Scripts subfolder
]

HUB_CITIES = {
    'Atlanta', 'Beijing', 'Dubai', 'Los Angeles', 'Tokyo',
    'Chicago', 'London', 'Shanghai', 'Paris', 'Dallas',
    'Guangzhou', 'Amsterdam', 'Frankfurt', 'Istanbul', 'New York'
}

def find_input_file():
    """Find the booking-listings.csv file"""
    print("🔍 Searching for booking-listings.csv file...")
    
    for path in POSSIBLE_INPUT_PATHS:
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"✅ Found: {path} ({size:,} bytes)")
            return path
        else:
            print(f"❌ Not found: {path}")
    
    print("\n⚠️ No booking-listings.csv file found!")
    print("Please ensure the original booking data file is available.")
    return None

def analyze_data_issues(input_file):
    """Analyze why records might be filtered out"""
    print(f"\n📊 Analyzing data in: {input_file}")
    
    stats = {
        'total_rows': 0,
        'hub_city_matches': 0,
        'has_coordinates': 0,
        'missing_coordinates': 0,
        'city_distribution': {},
        'coordinate_issues': []
    }
    
    try:
        with open(input_file, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            # Show available columns
            print(f"📋 Available columns: {list(reader.fieldnames)}")
            
            for i, row in enumerate(reader):
                stats['total_rows'] += 1
                
                # Check city
                city = row.get('city', '').strip()
                if city:
                    stats['city_distribution'][city] = stats['city_distribution'].get(city, 0) + 1
                    
                    if city in HUB_CITIES:
                        stats['hub_city_matches'] += 1
                        
                        # Check coordinates for hub cities
                        lat = lon = None
                        try:
                            mc = json.loads(row.get('map_coordinates') or '{}')
                            lat, lon = mc.get('lat'), mc.get('lon')
                        except:
                            pass
                        
                        if lat and lon:
                            stats['has_coordinates'] += 1
                        else:
                            stats['missing_coordinates'] += 1
                            if len(stats['coordinate_issues']) < 5:  # Show first 5 examples
                                stats['coordinate_issues'].append({
                                    'row': i + 1,
                                    'city': city,
                                    'title': row.get('title', 'N/A')[:50],
                                    'map_coordinates': row.get('map_coordinates', 'N/A')
                                })
                
                # Only check first 1000 rows for performance
                if i >= 999:
                    print("⚠️ Analysis limited to first 1000 rows")
                    break
    
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return None
    
    return stats

def print_analysis_results(stats):
    """Print the analysis results"""
    if not stats:
        return
    
    print(f"\n📊 DATA ANALYSIS RESULTS")
    print(f"{'='*50}")
    print(f"Total rows processed: {stats['total_rows']:,}")
    print(f"Hub city matches: {stats['hub_city_matches']:,}")
    print(f"Records with coordinates: {stats['has_coordinates']:,}")
    print(f"Records missing coordinates: {stats['missing_coordinates']:,}")
    
    if stats['hub_city_matches'] == 0:
        print(f"\n❌ CRITICAL ISSUE: No records match hub cities!")
        print(f"🔍 Cities found in data (top 10):")
        sorted_cities = sorted(stats['city_distribution'].items(), key=lambda x: x[1], reverse=True)[:10]
        for city, count in sorted_cities:
            status = "✅ HUB" if city in HUB_CITIES else "❌ NOT HUB"
            print(f"  {city}: {count:,} records {status}")
    
    if stats['missing_coordinates']:
        print(f"\n⚠️ COORDINATE ISSUES:")
        print(f"Records missing coordinates: {stats['missing_coordinates']:,}")
        print(f"Sample records with missing coordinates:")
        for issue in stats['coordinate_issues']:
            print(f"  Row {issue['row']}: {issue['city']} - {issue['title']}")
            print(f"    map_coordinates: {issue['map_coordinates']}")
    
    # Calculate expected output
    expected_records = stats['has_coordinates']
    print(f"\n🎯 EXPECTED OUTPUT: {expected_records:,} accommodation records")
    
    if expected_records == 0:
        print(f"\n💡 RECOMMENDATIONS:")
        if stats['hub_city_matches'] == 0:
            print("1. Check if city names in data match hub cities exactly")
            print("2. Consider adding more cities to HUB_CITIES")
        if stats['missing_coordinates']:
            print("3. Set up Google Maps API key for geocoding")
            print("4. Or provide pre-geocoded data with lat/lon coordinates")

def main():
    """Main diagnostic function"""
    print("🏨 ACCOMMODATION ETL DIAGNOSTIC TOOL")
    print("="*50)
    
    # Step 1: Find input file
    input_file = find_input_file()
    if not input_file:
        return
    
    # Step 2: Analyze data issues
    stats = analyze_data_issues(input_file)
    
    # Step 3: Print results and recommendations
    print_analysis_results(stats)

if __name__ == "__main__":
    main()
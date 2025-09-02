import asyncio
import csv
import os
import sys
from typing import List, Dict
from datetime import datetime

# Add the project root to the Python path to allow imports from 'app'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.api.itinerary import (
    get_activity_ids,
    get_destination_ids,
    get_accommodation_ids,
    get_transportation_ids,
    load_ml_models,
    ItineraryService,
)
from app.db.session import get_db_session, db_manager
from app.db.models import Activity, Destination, Accommodation, Transportation

async def generate_training_data(itinerary_service: ItineraryService, scenarios: List[Dict], output_file: str):
    """Generates and saves the training data by calling real services."""
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['input_pois', 'target_sequence'])

        for i, scenario in enumerate(scenarios):
            print(f"\n--- Processing Scenario {i+1}/{len(scenarios)}: {scenario['description']} ---")

            # 1. Get Unordered POI Recommendations
            dest_ids = await get_destination_ids(scenario['interests'], scenario.get('budget'))
            act_ids = await get_activity_ids(scenario['interests'], scenario.get('budget'))
            acc_ids = await get_accommodation_ids(scenario['interests'], scenario.get('budget'))
            trans_ids = await get_transportation_ids(scenario['interests'], scenario.get('budget'))

            # This is the INPUT for the Transformer
            # A flat list of all recommended POI IDs
            all_recommended_ids = dest_ids + act_ids + acc_ids + trans_ids
            if not all_recommended_ids:
                print("No recommendations found for this scenario, skipping.")
                continue

            # 2. Build the full POI objects needed for scheduling
            start_date = datetime.fromisoformat(scenario['start_date'])
            end_date = datetime.fromisoformat(scenario['end_date'])
            poi_objects = await itinerary_service.build_poi_list(
                dest_ids=dest_ids,
                act_ids=act_ids,
                acc_ids=acc_ids,
                trans_ids=trans_ids,
                start_date=start_date,
                center_lat=scenario['center_lat'],
                center_lon=scenario['center_lon'],
                radius_m=50000,  # 50km radius for data generation
                budget=scenario['budget']
            )

            # Check if we have enough POIs to create a meaningful itinerary
            if not poi_objects or len(poi_objects) < 2:
                print(f"⚠️  Skipping scenario - insufficient POIs found ({len(poi_objects) if poi_objects else 0} POIs)")
                continue

            # 3. Generate the Ordered Itinerary (Ground Truth)
            scheduled_items = await itinerary_service.create_itinerary_schedule(
                all_pois=poi_objects, 
                trip_days=scenario['duration_days'],
                start_date=start_date, 
                pace=scenario['pace']
            )

            # This is the TARGET for the Transformer
            target_sequence = [str(item["id"]) for day in scheduled_items for item in day]

            # 4. Save the data pair
            # We save them as space-separated strings of IDs
            writer.writerow([' '.join(map(str, all_recommended_ids)), ' '.join(target_sequence)])

    print(f"\nSuccessfully generated training data at {output_file}")

async def main():
    """Main function to set up and run the data generation.""" 
    print("Initializing database manager...")
    await db_manager.initialize()
    print("Database manager initialized.")

    print("Loading ML models...")
    load_ml_models()
    print("ML models loaded.")

    # Define a few diverse trip scenarios to generate data for
    trip_scenarios = [
    {
        "description": "A 3-day family trip to Atlanta",
        "interests": ["history", "museums", "family-friendly", "parks"],
        "duration_days": 3,
        "budget": 2000.0,
        "center_lat": 33.7490,
        "center_lon": -84.3880,
        "start_date": "2024-07-15",
        "end_date": "2024-07-17",
        "pace": {"max_hours": 8, "daily_activities": 4},
    },
    {
        "description": "A 5-day romantic getaway to Paris",
        "interests": ["art", "romance", "fine dining", "sightseeing"],
        "duration_days": 5,
        "budget": 5000.0,
        "center_lat": 48.8566,
        "center_lon": 2.3522,
        "start_date": "2024-08-20",
        "end_date": "2024-08-24",
        "pace": {"max_hours": 10, "daily_activities": 5},
    },
    {
        "description": "A 7-day solo backpacking trip through Shanghai",
        "interests": ["adventure", "nature", "budget-friendly", "culture"],
        "duration_days": 7,
        "budget": 1500.0,
        "center_lat": 31.2312707,
        "center_lon": 121.4700152,
        "start_date": "2024-09-05",
        "end_date": "2024-09-11",
        "pace": {"max_hours": 6, "daily_activities": 3},
    },
    {
        "description": "A 4-day business trip to New York",
        "interests": ["business", "museums", "fine dining", "theater"],
        "duration_days": 4,
        "budget": 3500.0,
        "center_lat": 40.7127281,
        "center_lon": -74.0060152,
        "start_date": "2024-10-15",
        "end_date": "2024-10-18",
        "pace": {"max_hours": 9, "daily_activities": 4},
    },
    {
        "description": "A 6-day cultural exploration in London",
        "interests": ["history", "museums", "art", "culture", "pubs"],
        "duration_days": 6,
        "budget": 4000.0,
        "center_lat": 51.5074456,
        "center_lon": -0.1277653,
        "start_date": "2024-11-01",
        "end_date": "2024-11-06",
        "pace": {"max_hours": 8, "daily_activities": 5},
    },
    {
        "description": "A 2-day weekend getaway to Chicago",
        "interests": ["architecture", "food", "jazz", "museums"],
        "duration_days": 2,
        "budget": 1200.0,
        "center_lat": 41.8755616,
        "center_lon": -87.6244212,
        "start_date": "2024-12-07",
        "end_date": "2024-12-08",
        "pace": {"max_hours": 10, "daily_activities": 6},
    },
    {
        "description": "A 8-day luxury vacation in Dubai",
        "interests": ["luxury", "shopping", "desert", "modern architecture"],
        "duration_days": 8,
        "budget": 8000.0,
        "center_lat": 25.0742823,
        "center_lon": 55.1885387,
        "start_date": "2024-12-20",
        "end_date": "2024-12-27",
        "pace": {"max_hours": 7, "daily_activities": 3},
    },
    {
        "description": "A 5-day foodie adventure in Tokyo",
        "interests": ["food", "culture", "temples", "technology", "anime"],
        "duration_days": 5,
        "budget": 3000.0,
        "center_lat": 35.6768601,
        "center_lon": 139.7638947,
        "start_date": "2025-01-10",
        "end_date": "2025-01-14",
        "pace": {"max_hours": 9, "daily_activities": 5},
    },
    {
        "description": "A 3-day art and canal tour in Amsterdam",
        "interests": ["art", "history", "cycling", "canals", "coffee shops"],
        "duration_days": 3,
        "budget": 1800.0,
        "center_lat": 52.3730796,
        "center_lon": 4.8924534,
        "start_date": "2025-02-14",
        "end_date": "2025-02-16",
        "pace": {"max_hours": 8, "daily_activities": 4},
    },
    {
        "description": "A 4-day historical journey through Istanbul",
        "interests": ["history", "architecture", "bazaars", "turkish baths", "mosques"],
        "duration_days": 4,
        "budget": 2200.0,
        "center_lat": 41.006381,
        "center_lon": 28.9758715,
        "start_date": "2025-03-05",
        "end_date": "2025-03-08",
        "pace": {"max_hours": 8, "daily_activities": 4},
    },
    {
        "description": "A 5-day tech and innovation tour in Los Angeles",
        "interests": ["technology", "entertainment", "beaches", "hollywood", "startups"],
        "duration_days": 5,
        "budget": 3500.0,
        "center_lat": 34.0536909,
        "center_lon": -118.242766,
        "start_date": "2025-03-20",
        "end_date": "2025-03-24",
        "pace": {"max_hours": 9, "daily_activities": 4},
    },
    {
        "description": "A 6-day manufacturing and trade exploration in Guangzhou",
        "interests": ["business", "manufacturing", "trade", "dim sum", "gardens"],
        "duration_days": 6,
        "budget": 2800.0,
        "center_lat": 23.1301964,
        "center_lon": 113.2592945,
        "start_date": "2025-04-10",
        "end_date": "2025-04-15",
        "pace": {"max_hours": 8, "daily_activities": 4},
    },
    {
        "description": "A 3-day cowboy culture experience in Dallas",
        "interests": ["western culture", "bbq", "rodeo", "museums", "country music"],
        "duration_days": 3,
        "budget": 1600.0,
        "center_lat": 32.7762719,
        "center_lon": -96.7968559,
        "start_date": "2025-05-01",
        "end_date": "2025-05-03",
        "pace": {"max_hours": 7, "daily_activities": 3},
    },
    ]

    output_csv_path = os.path.join(os.path.dirname(__file__), "transformer_training_data.csv")

    # Get a database session
    session_gen = get_db_session()
    db_session = await session_gen.__anext__()
    try:
        itinerary_service = ItineraryService(db_session)
        await generate_training_data(itinerary_service, trip_scenarios, output_csv_path)
    finally:
        await db_session.close()

if __name__ == "__main__":
    asyncio.run(main())

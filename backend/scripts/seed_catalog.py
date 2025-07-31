#!/usr/bin/env python3
import asyncio
import csv
import json
from pathlib import Path
from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel
from app.db.session import engine, async_session
from app.db.models import (
    Destination,
    Activity,
    Accommodation,
    Transportation,
)

BASE_DIR = Path(__file__).parent

def parse_float(value: str, field: str, row_id: str):
    """Safely parse float or return None."""
    val = (value or "").strip()
    if not val:
        print(f"Skipping row {row_id}: empty {field}")
        return None
    try:
        return float(val)
    except ValueError:
        print(f"Skipping row {row_id}: invalid {field} '{value}'")
        return None

async def seed():
    # ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session() as session:
        # -- Destinations --
        dest_file = BASE_DIR / "destination.csv"
        with open(dest_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_id = row.get("id", "<no-id>")
                lat = parse_float(row.get("latitude"), "latitude", row_id)
                lon = parse_float(row.get("longitude"), "longitude", row_id)
                if lat is None or lon is None:
                    continue  # skip rows without valid coords
                dest_id = UUID(row_id)
                exists = await session.get(Destination, dest_id)
                if not exists:
                    images = json.loads(row["images"]) if row.get("images", "").strip().startswith("[") else row["images"].split(",")
                    rating = parse_float(row.get("rating"), "rating", row_id)
                    session.add(
                        Destination(
                            id=dest_id,
                            name=row.get("name") or "",
                            description=row.get("description") or None,
                            latitude=lat,
                            longitude=lon,
                            images=images,
                            rating=rating,
                        )
                    )
                    print(f"Added destination: {row.get('name')}")

        # -- Activities --
        act_file = BASE_DIR / "activities.csv"
        with open(act_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_id = row.get("id", "<no-id>")
                lat = parse_float(row.get("latitude"), "latitude", row_id)
                lon = parse_float(row.get("longitude"), "longitude", row_id)
                if lat is None or lon is None:
                    continue
                act_id = UUID(row_id)
                exists = await session.get(Activity, act_id)
                if not exists:
                    images = json.loads(row["images"]) if row.get("images", "").strip().startswith("[") else row["images"].split(",")
                    price = parse_float(row.get("price"), "price", row_id)
                    rating = parse_float(row.get("rating"), "rating", row_id)
                    session.add(
                        Activity(
                            id=act_id,
                            name=row.get("name") or "",
                            description=row.get("description") or None,
                            latitude=lat,
                            longitude=lon,
                            images=images,
                            price=price,
                            opening_hours=row.get("opening_hours") or None,
                            rating=rating,
                        )
                    )
                    print(f"Added activity: {row.get('name')}")

        # -- Accommodations --
        acc_file = BASE_DIR / "accomodation.csv"
        with open(acc_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_id = row.get("id", "<no-id>")
                lat = parse_float(row.get("latitude"), "latitude", row_id)
                lon = parse_float(row.get("longitude"), "longitude", row_id)
                if lat is None or lon is None:
                    continue
                acc_id = UUID(row_id)
                exists = await session.get(Accommodation, acc_id)
                if not exists:
                    images = json.loads(row["images"]) if row.get("images", "").strip().startswith("[") else row["images"].split(",")
                    amenities = json.loads(row["amenities"]) if row.get("amenities", "").strip().startswith("[") else row["amenities"].split(",")
                    price = parse_float(row.get("price"), "price", row_id)
                    rating = parse_float(row.get("rating"), "rating", row_id)
                    session.add(
                        Accommodation(
                            id=acc_id,
                            name=row.get("name") or "",
                            description=row.get("description") or None,
                            latitude=lat,
                            longitude=lon,
                            images=images,
                            price=price,
                            rating=rating,
                            amenities=amenities,
                        )
                    )
                    print(f"Added accommodation: {row.get('name')}")

        # -- Transportations --
        trans_file = BASE_DIR / "transport.csv"
        with open(trans_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_id = row.get("id", "<no-id>")
                dep_lat = parse_float(row.get("departure_lat"), "departure_lat", row_id)
                dep_lon = parse_float(row.get("departure_long"), "departure_long", row_id)
                arr_lat = parse_float(row.get("arrival_lat"), "arrival_lat", row_id)
                arr_lon = parse_float(row.get("arrival_long"), "arrival_long", row_id)
                if None in (dep_lat, dep_lon, arr_lat, arr_lon):
                    continue
                tr_id = UUID(row_id)
                exists = await session.get(Transportation, tr_id)
                if not exists:
                    session.add(
                        Transportation(
                            id=tr_id,
                            type=row.get("type") or "",
                            departure_lat=dep_lat,
                            departure_long=dep_lon,
                            arrival_lat=arr_lat,
                            arrival_long=arr_lon,
                            departure_time=datetime.fromisoformat(row["departure_time"]),
                            arrival_time=datetime.fromisoformat(row["arrival_time"]),
                            price=parse_float(row.get("price"), "price", row_id),
                        )
                    )
                    print(f"Added transportation: {row_id}")

        await session.commit()
        print("Seeding completed.")

if __name__ == "__main__":
    asyncio.run(seed())


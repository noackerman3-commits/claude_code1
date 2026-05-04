"""
Debug: show what raw_text was captured for each saved listing.
Run this to see if amenity keywords appear in the scraped text.
"""
import sqlite3, os, sys

db_path = os.path.join(os.path.dirname(__file__), 'data', 'listings.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

rows = conn.execute(
    "SELECT listing_id, location, price, rooms, has_mamad, has_parking, "
    "has_balcony, has_elevator, has_ac, raw_text FROM listings LIMIT 5"
).fetchall()

for row in rows:
    print("=" * 70)
    print(f"ID       : {row['listing_id']}")
    print(f"Location : {row['location']}")
    print(f"Price    : {row['price']}  Rooms: {row['rooms']}")
    print(f"Amenities: mamad={row['has_mamad']} parking={row['has_parking']} "
          f"balcony={row['has_balcony']} elevator={row['has_elevator']} ac={row['has_ac']}")
    print(f"RAW TEXT :\n{row['raw_text']}")
    print()

conn.close()

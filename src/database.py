"""
SQLite database operations for managing rental listings.
"""
import os
import sqlite3
from datetime import datetime
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def init_db(self):
        """Create database and tables if they don't exist."""
        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS listings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT,
                    title TEXT,
                    price INTEGER,
                    rooms REAL,
                    location TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(listing_id, source)
                )
            """)

            conn.commit()
            conn.close()
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise

    def listing_exists(self, listing_id: str, source: str) -> bool:
        """Check if listing already exists in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id FROM listings WHERE listing_id = ? AND source = ?",
                (listing_id, source)
            )

            result = cursor.fetchone()
            conn.close()

            return result is not None
        except Exception as e:
            logger.error(f"Error checking listing existence: {e}")
            return False

    def add_listing(self, listing_data: Dict) -> bool:
        """Add new listing to database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO listings (listing_id, source, url, title, price, rooms, location)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                listing_data.get('listing_id'),
                listing_data.get('source'),
                listing_data.get('url'),
                listing_data.get('title'),
                listing_data.get('price'),
                listing_data.get('rooms'),
                listing_data.get('location')
            ))

            conn.commit()
            conn.close()
            logger.info(f"Added listing {listing_data.get('listing_id')} from {listing_data.get('source')}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Listing {listing_data.get('listing_id')} already exists")
            return False
        except Exception as e:
            logger.error(f"Error adding listing: {e}")
            return False

    def get_listing_count(self) -> int:
        """Get total number of listings in database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM listings")
            count = cursor.fetchone()[0]

            conn.close()
            return count
        except Exception as e:
            logger.error(f"Error getting listing count: {e}")
            return 0

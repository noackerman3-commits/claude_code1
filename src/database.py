"""
SQLite database for rental listings.

Schema includes all fields needed for professional output:
amenities (mamad, parking, balcony, elevator, AC), floor, size, neighborhood.

_migrate() safely adds new columns to existing databases so old data
is never lost when upgrading.
"""
import sqlite3
import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init_db(self):
        conn = self._connect()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS listings (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    listing_id   TEXT    NOT NULL,
                    source       TEXT    NOT NULL,
                    url          TEXT,
                    title        TEXT,
                    price        INTEGER,
                    rooms        REAL,
                    floor        INTEGER,
                    size_sqm     REAL,
                    location     TEXT,
                    neighborhood TEXT,
                    has_parking  INTEGER DEFAULT 0,
                    has_mamad    INTEGER DEFAULT 0,
                    has_balcony  INTEGER DEFAULT 0,
                    has_elevator INTEGER DEFAULT 0,
                    has_ac       INTEGER DEFAULT 0,
                    description  TEXT,
                    image_url    TEXT,
                    raw_text     TEXT,
                    first_seen   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(listing_id, source)
                )
            """)
            conn.commit()
            self._migrate(conn)
            logger.info(f"Database ready at {self.db_path}")
        finally:
            conn.close()

    def _migrate(self, conn):
        """Add new columns to existing databases without losing data."""
        new_columns = [
            ('floor',        'INTEGER'),
            ('size_sqm',     'REAL'),
            ('neighborhood', 'TEXT'),
            ('has_parking',  'INTEGER DEFAULT 0'),
            ('has_mamad',    'INTEGER DEFAULT 0'),
            ('has_balcony',  'INTEGER DEFAULT 0'),
            ('has_elevator', 'INTEGER DEFAULT 0'),
            ('has_ac',       'INTEGER DEFAULT 0'),
            ('description',  'TEXT'),
            ('image_url',    'TEXT'),
            ('raw_text',     'TEXT'),
        ]
        for col, coltype in new_columns:
            try:
                conn.execute(f"ALTER TABLE listings ADD COLUMN {col} {coltype}")
                conn.commit()
                logger.info(f"DB migration: added column '{col}'")
            except sqlite3.OperationalError:
                pass  # column already exists

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def listing_exists(self, listing_id: str, source: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT id FROM listings WHERE listing_id = ? AND source = ?",
                (listing_id, source),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def add_listing(self, data: Dict) -> bool:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO listings (
                    listing_id, source, url, title,
                    price, rooms, floor, size_sqm,
                    location, neighborhood,
                    has_parking, has_mamad, has_balcony, has_elevator, has_ac,
                    description, image_url, raw_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get('listing_id'),
                    data.get('source'),
                    data.get('url'),
                    data.get('title'),
                    data.get('price'),
                    data.get('rooms'),
                    data.get('floor'),
                    data.get('size_sqm'),
                    data.get('location'),
                    data.get('neighborhood'),
                    int(bool(data.get('has_parking'))),
                    int(bool(data.get('has_mamad'))),
                    int(bool(data.get('has_balcony'))),
                    int(bool(data.get('has_elevator'))),
                    int(bool(data.get('has_ac'))),
                    data.get('description'),
                    data.get('image_url'),
                    # raw_text supersedes the old full_text key
                    data.get('raw_text') or data.get('full_text'),
                ),
            )
            conn.commit()
            logger.info(f"Saved listing {data.get('listing_id')} [{data.get('source')}]")
            return True
        except sqlite3.IntegrityError:
            logger.debug(f"Duplicate listing {data.get('listing_id')} — skipped")
            return False
        except Exception as e:
            logger.error(f"Error saving listing: {e}")
            return False
        finally:
            conn.close()

    def get_listing_count(self) -> int:
        conn = self._connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

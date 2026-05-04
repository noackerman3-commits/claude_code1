"""
Single source of truth for listing filter logic.
Replaces the duplicated filter_listing() that existed in main.py,
scheduler.py, and bot_listener.py.
"""
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class FilterEngine:
    def __init__(self, search_params: dict):
        price = search_params.get('price_range', {})
        self.min_price: int = price.get('min', 0)
        self.max_price: int = price.get('max', 999999)
        self.min_rooms: float | None = search_params.get('min_rooms')
        self.locations: list[str] = [
            loc.lower() for loc in search_params.get('locations', [])
        ]
        self.must_have: list[str] = [
            kw.lower() for kw in search_params.get('must_have_keywords', [])
        ]
        self.exclude: list[str] = [
            kw.lower() for kw in search_params.get('exclude_keywords', [])
        ]

    def matches(self, listing: dict) -> Tuple[bool, str]:
        """
        Returns (passes, rejection_reason).
        rejection_reason is '' when passes=True.
        """
        price = listing.get('price')
        if price:
            if not (self.min_price <= price <= self.max_price):
                return False, f"price {price} outside {self.min_price}-{self.max_price}"

        rooms = listing.get('rooms')
        if self.min_rooms is not None and rooms is not None:
            if rooms < self.min_rooms:
                return False, f"{rooms} rooms < min {self.min_rooms}"

        location = (listing.get('location') or '').lower()
        if self.locations and location:
            if not any(loc in location for loc in self.locations):
                return False, f"location '{location}' not in allowed list"

        text = (
            (listing.get('raw_text') or listing.get('full_text') or '') +
            ' ' +
            (listing.get('title') or '')
        ).lower()

        if self.must_have:
            missing = [kw for kw in self.must_have if kw not in text]
            if missing:
                return False, f"missing keywords: {missing}"

        if self.exclude:
            found = [kw for kw in self.exclude if kw in text]
            if found:
                return False, f"excluded keyword found: {found}"

        return True, ""

"""
Utility functions for the rental agent.
"""
import logging
import re
import os
from datetime import datetime
from typing import Dict, List, Optional


def setup_logging(log_dir: str = "logs"):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, f"scraper_{datetime.now().strftime('%Y%m%d')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(),
        ],
    )
    logging.getLogger(__name__).info("Logging initialized")


# ------------------------------------------------------------------
# Keyword matching (used by FilterEngine)
# ------------------------------------------------------------------

def matches_keywords(text: str, keywords: List[str]) -> bool:
    """True if text contains ALL keywords (case-insensitive)."""
    if not keywords:
        return True
    if not text:
        return False
    text_lower = text.lower()
    return all(kw.lower() in text_lower for kw in keywords)


def excludes_keywords(text: str, keywords: List[str]) -> bool:
    """True if text contains ANY of the exclude keywords."""
    if not keywords or not text:
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


# ------------------------------------------------------------------
# Price
# ------------------------------------------------------------------

def normalize_price(price_str: str) -> Optional[int]:
    """'4,500 ₪' → 4500"""
    if not price_str:
        return None
    price_str = (
        price_str.replace('₪', '').replace('ILS', '')
        .replace('שקל', '').replace('שח', '')
        .replace(',', '').replace(' ', '').strip()
    )
    match = re.search(r'\d+', price_str)
    if match:
        try:
            return int(match.group())
        except ValueError:
            return None
    return None


def extract_price_from_text(text: str) -> Optional[int]:
    """Extract rental price from free text (Hebrew + English)."""
    if not text:
        return None
    patterns = [
        r'(\d{1,3}(?:,\d{3})*)\s*₪',
        r'(\d{1,3}(?:,\d{3})*)\s*שקל',
        r'(\d{1,3}(?:,\d{3})*)\s*שח',
        r'(\d{1,3}(?:,\d{3})*)\s*ILS',
        r'₪\s*(\d{1,3}(?:,\d{3})*)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                price = int(match.group(1).replace(',', ''))
                if 1000 <= price <= 30000:
                    return price
            except ValueError:
                continue
    return None


# ------------------------------------------------------------------
# Rooms
# ------------------------------------------------------------------

def normalize_rooms(rooms_str: str) -> Optional[float]:
    """'3 חדרים' → 3.0"""
    if not rooms_str:
        return None
    rooms_str = (
        rooms_str.replace('חדרים', '').replace('חדר', '')
        .replace('rooms', '').replace('room', '')
        .replace('BR', '').replace('br', '').strip()
    )
    match = re.search(r'\d+\.?\d*', rooms_str)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def extract_rooms_from_text(text: str) -> Optional[float]:
    """Extract room count from free text."""
    if not text:
        return None
    patterns = [
        r'(\d+\.?\d*)\s*חדרים',
        r'(\d+\.?\d*)\s*חדר',
        r'(\d+\.?\d*)\s*rooms',
        r'(\d+\.?\d*)\s*room',
        r'(\d+\.?\d*)\s*BR',
        r'(\d+\.?\d*)\s*br',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                rooms = float(match.group(1))
                if 1 <= rooms <= 10:
                    return rooms
            except ValueError:
                continue
    return None


# ------------------------------------------------------------------
# Size (square metres)
# ------------------------------------------------------------------

def extract_size_from_text(text: str) -> Optional[float]:
    """Extract apartment size in m² from free text."""
    if not text:
        return None
    patterns = [
        r'(\d+)\s*מ["״]ר',   # מ"ר / מ״ר
        r'(\d+)\s*מטר(?:\s*רבוע)?',
        r'(\d+)\s*sqm',
        r'(\d+)\s*m²',
        r'(\d+)\s*מ²',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                size = float(match.group(1))
                if 20 <= size <= 500:
                    return size
            except ValueError:
                continue
    return None


# ------------------------------------------------------------------
# Floor
# ------------------------------------------------------------------

def extract_floor_from_text(text: str) -> Optional[int]:
    """Extract floor number from free text. קרקע = ground floor (0)."""
    if not text:
        return None
    # Ground floor keywords
    if re.search(r'קומה\s*(?:‎)?קרקע', text, re.IGNORECASE):
        return 0
    patterns = [
        r'קומה\s*(?:‎)?(\d+)',
        r'(?:floor|fl\.?)\s*(\d+)',
        r'(\d+)(?:st|nd|rd|th)\s*floor',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                floor = int(match.group(1))
                if 0 <= floor <= 50:
                    return floor
            except ValueError:
                continue
    return None


def extract_property_type_from_text(text: str) -> Optional[str]:
    """Extract property type from Yad2 card text (e.g. דירת גן, בית פרטי)."""
    types = [
        'דירת גן', 'דירת פנטהאוז', 'פנטהאוז',
        'בית פרטי', 'קוטג\'', 'דו משפחתי',
        'דירה', 'סטודיו', 'לופט',
    ]
    for t in types:
        if t in text:
            return t
    return None


def extract_neighborhood_from_yad2_text(text: str) -> Optional[str]:
    """
    Extract neighborhood from Yad2 card text.
    The third line follows the pattern: TYPE, NEIGHBORHOOD, CITY
    """
    if not text:
        return None
    for line in text.split('\n'):
        line = line.strip()
        parts = [p.strip() for p in line.split(',')]
        if len(parts) == 3:
            # Middle part is the neighborhood
            neighborhood = parts[1].strip()
            if neighborhood and len(neighborhood) > 2:
                return neighborhood
    return None


def extract_parking_count_from_text(text: str) -> int:
    """Extract number of parking spots mentioned in text."""
    if not text:
        return 0
    patterns = [
        r'(\d+)\s*חניות',
        r'(\d+)\s*מקומות?\s*חניה',
        r'(\d+)\s*parking',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                n = int(match.group(1))
                if 1 <= n <= 5:
                    return n
            except ValueError:
                continue
    # Single parking mentioned
    if any(kw in text for kw in ['חניה', 'חנייה', 'parking']):
        return 1
    return 0


# ------------------------------------------------------------------
# Amenities
# ------------------------------------------------------------------

def extract_amenities_from_text(text: str) -> Dict[str, bool]:
    """
    Return a dict of boolean amenity flags extracted from listing text.
    Used by both Yad2 and Facebook scrapers.
    """
    if not text:
        return _empty_amenities()

    t = text.lower()

    return {
        'has_mamad':    _any(t, ['ממ"ד', 'ממד', "ממ'ד", 'mamad', 'safe room', 'shelter']),
        'has_parking':  _any(t, ['חניה', 'חנייה', 'חנייה פרטית', 'parking', 'garage']),
        'has_balcony':  _any(t, ['מרפסת', 'balcony', 'terrace', 'טרס', 'patio']),
        'has_elevator': _any(t, ['מעלית', 'elevator', 'lift']),
        'has_ac':       _any(t, ['מזגן', 'מיזוג', 'air condition', 'מיזוג אוויר', 'ac']),
    }


def _any(text: str, keywords: List[str]) -> bool:
    return any(kw.lower() in text for kw in keywords)


def _empty_amenities() -> Dict[str, bool]:
    return {
        'has_mamad': False,
        'has_parking': False,
        'has_balcony': False,
        'has_elevator': False,
        'has_ac': False,
    }

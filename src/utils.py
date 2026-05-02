"""
Utility functions for the rental agent.
"""
import logging
import re
from typing import List, Optional
import os
from datetime import datetime


def setup_logging(log_dir: str = "logs"):
    """Configure file and console logging."""
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, f"scraper_{datetime.now().strftime('%Y%m%d')}.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info("Logging initialized")


def matches_keywords(text: str, keywords: List[str]) -> bool:
    """Check if text contains all must-have keywords."""
    if not keywords:
        return True

    if not text:
        return False

    text_lower = text.lower()
    return all(keyword.lower() in text_lower for keyword in keywords)


def excludes_keywords(text: str, keywords: List[str]) -> bool:
    """Check if text contains any exclude keywords."""
    if not keywords:
        return False

    if not text:
        return False

    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in keywords)


def normalize_price(price_str: str) -> Optional[int]:
    """Convert price string to integer (e.g., '4,500 ₪' -> 4500)."""
    if not price_str:
        return None

    # Remove common currency symbols and text
    price_str = price_str.replace('₪', '').replace('ILS', '').replace('שקל', '').replace('שח', '')
    price_str = price_str.replace(',', '').replace(' ', '').strip()

    # Extract digits
    match = re.search(r'\d+', price_str)
    if match:
        try:
            return int(match.group())
        except ValueError:
            return None

    return None


def normalize_rooms(rooms_str: str) -> Optional[float]:
    """Convert room string to float (e.g., '3 חדרים' -> 3.0)."""
    if not rooms_str:
        return None

    # Remove common words
    rooms_str = rooms_str.replace('חדרים', '').replace('חדר', '').replace('rooms', '').replace('room', '')
    rooms_str = rooms_str.replace('BR', '').replace('br', '').strip()

    # Extract number (including decimals like 3.5)
    match = re.search(r'\d+\.?\d*', rooms_str)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None

    return None


def extract_price_from_text(text: str) -> Optional[int]:
    """Extract price from free text (handles Hebrew and English)."""
    if not text:
        return None

    # Pattern for price: number followed by currency indicator
    patterns = [
        r'(\d{1,3}(?:,\d{3})*)\s*₪',  # 4,500 ₪
        r'(\d{1,3}(?:,\d{3})*)\s*שקל',  # 4,500 שקל
        r'(\d{1,3}(?:,\d{3})*)\s*שח',  # 4,500 שח
        r'(\d{1,3}(?:,\d{3})*)\s*ILS',  # 4,500 ILS
        r'₪\s*(\d{1,3}(?:,\d{3})*)',  # ₪ 4,500
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            price_str = match.group(1).replace(',', '')
            try:
                price = int(price_str)
                # Sanity check: rental prices typically between 1000-20000
                if 1000 <= price <= 20000:
                    return price
            except ValueError:
                continue

    return None


def extract_rooms_from_text(text: str) -> Optional[float]:
    """Extract room count from free text (handles Hebrew and English)."""
    if not text:
        return None

    # Pattern for rooms: number followed by room indicator
    patterns = [
        r'(\d+\.?\d*)\s*חדרים',  # 3 חדרים
        r'(\d+\.?\d*)\s*חדר',  # 3 חדר
        r'(\d+\.?\d*)\s*rooms',  # 3 rooms
        r'(\d+\.?\d*)\s*room',  # 3 room
        r'(\d+\.?\d*)\s*BR',  # 3 BR
        r'(\d+\.?\d*)\s*br',  # 3 br
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                rooms = float(match.group(1))
                # Sanity check: room count typically between 1-10
                if 1 <= rooms <= 10:
                    return rooms
            except ValueError:
                continue

    return None

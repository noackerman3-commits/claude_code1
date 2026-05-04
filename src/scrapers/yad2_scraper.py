"""
Yad2 scraper for rental listings.

scrape_one(search_config) — scrapes a single URL defined in search_config.
scrape()                   — backward-compat wrapper that reads searches
                             from config and calls scrape_one for each.

ScrapingManager always calls scrape_one directly and manages the browser
lifecycle (initialize_browser / close_browser) itself so that one browser
session is reused across all 50 searches instead of starting Playwright 50×.
"""
import hashlib
import logging
from typing import Dict, List, Optional
from urllib.parse import urlencode

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class Yad2Scraper(BaseScraper):
    def __init__(self, config: dict):
        super().__init__(config)
        yad2_cfg = config.get('sources', {}).get('yad2', {})
        self._default_base_url = yad2_cfg.get(
            'base_url', 'https://www.yad2.co.il/realestate/rent'
        )

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def scrape_one(self, search_config: dict) -> List[Dict]:
        """
        Scrape a single search URL.
        search_config keys:
          name (str)  — display name for logging
          url  (str)  — full Yad2 search URL (use this if present)
        Browser must already be initialized by the caller.
        """
        url = search_config.get('url') or self._build_url_from_config()
        listings = []

        try:
            if not self.page:
                self.initialize_browser()

            logger.info(f"Yad2 → {url}")
            self.page.goto(url, wait_until='networkidle', timeout=30000)
            self.random_delay()

            try:
                self.page.wait_for_selector('.feed_list', timeout=10000)
            except Exception:
                pass

            elements = self._find_listing_elements()
            if not elements:
                logger.warning(f"No listings found at {url}")
                return listings

            for element in elements[:20]:
                try:
                    listing = self._extract(element)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.error(f"Error extracting listing: {e}")

            logger.info(f"Yad2 scraped {len(listings)} listings from {url}")

        except Exception as e:
            logger.error(f"Yad2 error for {url}: {e}")

        return listings

    def scrape(self) -> List[Dict]:
        """Backward-compat: iterate all searches in config."""
        searches = (
            self.config.get('sources', {})
            .get('yad2', {})
            .get('searches', [])
        )
        if not searches:
            searches = [{'name': 'Default', 'url': self._build_url_from_config()}]

        if not self.page:
            self.initialize_browser()

        all_listings: List[Dict] = []
        for search_cfg in searches:
            all_listings.extend(self.scrape_one(search_cfg))
        return all_listings

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_url_from_config(self) -> str:
        search_params = self.config.get('search_parameters', {})
        price_range = search_params.get('price_range', {})
        params: Dict[str, str] = {}

        if price_range.get('min'):
            params['priceOnly'] = '1'
            params['price'] = f"{price_range['min']}-{price_range.get('max', 99999)}"
        if search_params.get('min_rooms'):
            params['rooms'] = f"{search_params['min_rooms']}-99"

        if params:
            return f"{self._default_base_url}?{urlencode(params)}"
        return self._default_base_url

    def _find_listing_elements(self):
        for selector in ['.feeditem', '[data-testid="feed-item"]', '.feed_item', 'article']:
            try:
                elements = self.page.query_selector_all(selector)
                if elements:
                    logger.debug(f"Yad2: found elements with selector '{selector}'")
                    return elements
            except Exception:
                continue
        return None

    def _extract(self, element) -> Optional[Dict]:
        try:
            # URL + ID
            link = element.query_selector('a[href*="/item/"]') or element.query_selector('a')
            url = link.get_attribute('href') if link else None
            if url and not url.startswith('http'):
                url = f"https://www.yad2.co.il{url}"

            listing_id = self._generate_id(url, element.inner_text())

            # Title
            title = self._first_text(element, ['.title', '[data-testid="title"]', 'h3', 'h2'])

            # Price
            price_text = self._first_text(element, ['.price', '[data-testid="price"]', '[class*="price"]'])
            price = self.extract_price(price_text) if price_text else None

            # Rooms
            rooms_text = self._first_text(element, ['.rooms', '[data-testid="rooms"]', '[class*="room"]'])
            rooms = self.extract_rooms(rooms_text) if rooms_text else None
            if not rooms:
                from utils import extract_rooms_from_text
                rooms = extract_rooms_from_text(element.inner_text())

            # Location
            location = self._first_text(
                element,
                ['.city', '[data-testid="city"]', '[class*="location"]', '[class*="city"]'],
            )

            # Image
            image_url = None
            for sel in ['img', '[class*="image"] img']:
                img = element.query_selector(sel)
                if img:
                    image_url = img.get_attribute('src')
                    break

            raw_text = element.inner_text()

            # Amenities + extra fields from raw text
            from utils import (
                extract_amenities_from_text,
                extract_size_from_text,
                extract_floor_from_text,
            )
            amenities = extract_amenities_from_text(raw_text)
            size_sqm = extract_size_from_text(raw_text)
            floor = extract_floor_from_text(raw_text)

            return {
                'listing_id': listing_id,
                'source': 'yad2',
                'url': url,
                'title': title,
                'price': price,
                'rooms': rooms,
                'floor': floor,
                'size_sqm': size_sqm,
                'location': location,
                'image_url': image_url,
                'raw_text': raw_text,
                **amenities,
            }

        except Exception as e:
            logger.error(f"Error extracting Yad2 listing: {e}")
            return None

    def _first_text(self, element, selectors: List[str]) -> Optional[str]:
        for sel in selectors:
            el = element.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if text:
                    return text
        return None

    def _generate_id(self, url: Optional[str], text: str) -> str:
        if url and '/item/' in url:
            parts = url.split('/item/')
            if len(parts) > 1:
                item_id = parts[1].split('?')[0].split('/')[0]
                return f"yad2_{item_id}"
        return f"yad2_{hashlib.md5(text.encode('utf-8')).hexdigest()[:12]}"

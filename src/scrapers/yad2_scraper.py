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
            self.page.goto(url, wait_until='domcontentloaded', timeout=60000)
            # Allow time for JS rendering and for the user to solve any CAPTCHA
            import time; time.sleep(8)

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
        # 1. Cards that contain a direct listing link — most reliable
        try:
            all_cards = self.page.query_selector_all('[class*="Card"],[class*="card"]')
            listing_cards = [c for c in all_cards if c.query_selector('a[href*="/item/"]')]
            if listing_cards:
                logger.debug(f"Yad2: {len(listing_cards)} listing cards found via [class*=Card]")
                return listing_cards
        except Exception:
            pass

        # 2. Feed item selectors (older Yad2 HTML)
        for selector in [
            '[class*="FeedItem"]', '[class*="feeditem"]', '[class*="feed-item"]',
            '[class*="feedItem"]', '.feeditem', '[data-testid="feed-item"]', 'article',
        ]:
            try:
                elements = self.page.query_selector_all(selector)
                if elements:
                    logger.debug(f"Yad2: {len(elements)} elements via '{selector}'")
                    return elements
            except Exception:
                continue

        return None

    def _extract(self, element) -> Optional[Dict]:
        try:
            # URL + ID — always from the /item/ link
            link = element.query_selector('a[href*="/item/"]')
            url = link.get_attribute('href') if link else None
            if url and not url.startswith('http'):
                url = f"https://www.yad2.co.il{url}"

            raw_text = element.inner_text().strip()
            if not raw_text:
                return None

            listing_id = self._generate_id(url, raw_text)

            # All structured data extracted from raw text — works regardless of
            # which CSS classes Yad2 uses internally
            from utils import (
                extract_price_from_text,
                extract_rooms_from_text,
                extract_amenities_from_text,
                extract_size_from_text,
                extract_floor_from_text,
                extract_property_type_from_text,
                extract_neighborhood_from_yad2_text,
                extract_parking_count_from_text,
            )
            price         = extract_price_from_text(raw_text)
            rooms         = extract_rooms_from_text(raw_text)
            size_sqm      = extract_size_from_text(raw_text)
            floor         = extract_floor_from_text(raw_text)
            amenities     = extract_amenities_from_text(raw_text)
            property_type = extract_property_type_from_text(raw_text)
            neighborhood  = extract_neighborhood_from_yad2_text(raw_text)
            parking_count = extract_parking_count_from_text(raw_text)

            # Location — try selector first, fall back to first non-numeric line
            location = self._first_text(
                element,
                ['[class*="city"]', '[class*="location"]', '[class*="address"]',
                 '[data-testid="city"]', '[data-testid="address"]'],
            )
            if not location:
                for line in raw_text.split('\n'):
                    line = line.strip()
                    if line and not any(c.isdigit() for c in line[:3]) and len(line) > 3:
                        location = line
                        break

            # Title — first meaningful line
            title = raw_text.split('\n')[0][:120].strip()

            # Image
            image_url = None
            img = element.query_selector('img')
            if img:
                image_url = img.get_attribute('src')

            return {
                'listing_id':   listing_id,
                'source':       'yad2',
                'url':          url,
                'title':        title,
                'price':        price,
                'rooms':        rooms,
                'floor':        floor,
                'size_sqm':     size_sqm,
                'location':     location,
                'neighborhood': neighborhood,
                'property_type': property_type,
                'parking_count': parking_count,
                'image_url':    image_url,
                'raw_text':     raw_text,
                **amenities,
            }

        except Exception as e:
            logger.error(f"Error extracting Yad2 listing: {e}")
            return None

    def enrich_from_detail_page(self, listing: dict) -> None:
        """
        Visit the listing detail page and update amenity fields in-place.
        The card text has no amenity keywords; the detail page does.
        """
        url = listing.get('url')
        if not url or not self.page:
            return
        try:
            import time
            self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(3)
            body_text = self.page.inner_text('body')

            from utils import extract_amenities_from_text, extract_parking_count_from_text
            amenities     = extract_amenities_from_text(body_text)
            parking_count = extract_parking_count_from_text(body_text)

            listing.update(amenities)
            listing['parking_count'] = parking_count
            if parking_count > 0:
                listing['has_parking'] = True

            # Append detail text so keyword filters can match amenity terms
            card_text = listing.get('raw_text') or ''
            listing['raw_text'] = card_text + '\n' + body_text[:3000]

            logger.info(f"Enriched {listing.get('listing_id')}: {amenities}, parking={parking_count}")
        except Exception as e:
            logger.warning(f"Detail enrichment failed for {url}: {e}")

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
            # URL format: /item/CITY/LISTING-ID or /item/LISTING-ID
            # Always take the LAST non-empty path segment after /item/
            after = url.split('/item/', 1)[1].split('?')[0]
            parts = [p for p in after.split('/') if p]
            if parts:
                return f"yad2_{parts[-1]}"
        return f"yad2_{hashlib.md5(text.encode('utf-8')).hexdigest()[:12]}"

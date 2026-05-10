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
        """
        Return a list of unique link elements (<a href="/item/...">) from the
        actual search-results feed (not the recommendations sidebar).
        Deduplication is done here by listing ID so _extract is never called
        twice for the same property.
        """
        try:
            feed = self.page.query_selector('[data-testid="feed-list"]')
            scope = feed if feed else self.page
            scope_name = 'feed-list' if feed else 'page'

            links = scope.query_selector_all('a[href*="/item/"]')
            seen_ids, unique_links = set(), []
            for link in links:
                href = link.get_attribute('href') or ''
                if '/item/' not in href:
                    continue
                after = href.split('/item/', 1)[1].split('?')[0]
                parts = [p for p in after.split('/') if p]
                item_id = parts[-1] if parts else None
                if not item_id or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                unique_links.append(link)

            if unique_links:
                logger.debug(f"Yad2: {len(unique_links)} unique links in {scope_name}")
                return unique_links
        except Exception as e:
            logger.debug(f"Link-based element search failed: {e}")

        # Legacy fallback
        for selector in [
            '[class*="FeedItem"]', '[class*="feeditem"]', '[class*="feed-item"]',
            '[class*="feedItem"]', '.feeditem', 'article',
        ]:
            try:
                els = self.page.query_selector_all(selector)
                if els:
                    return els
            except Exception:
                continue
        return None

    def _extract(self, element) -> Optional[Dict]:
        try:
            # Support both <a> link elements (new) and card elements (fallback).
            is_link = element.evaluate('el => el.tagName === "A"')
            if is_link:
                href = element.get_attribute('href') or ''
                url = f"https://www.yad2.co.il{href}" if not href.startswith('http') else href
                raw_text = self._get_container_text(element)
            else:
                link = element.query_selector('a[href*="/item/"]')
                if not link:
                    return None  # no listing link → not a real listing element
                href = link.get_attribute('href') or ''
                url = f"https://www.yad2.co.il{href}" if not href.startswith('http') else href
                raw_text = element.inner_text().strip()

            if not url or '/item/' not in url or not raw_text:
                return None

            listing_id = self._generate_id(url, raw_text)

            from utils import (
                extract_price_from_text,
                extract_rooms_from_text,
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
            property_type = extract_property_type_from_text(raw_text)
            neighborhood  = extract_neighborhood_from_yad2_text(raw_text)
            parking_count = extract_parking_count_from_text(raw_text)
            # Amenities intentionally NOT extracted from card text — card text never
            # contains amenity keywords. They are set to None (unknown) here and
            # populated by enrich_from_detail_page() for new listings.

            # Location: skip region/district labels (מחוז) and overly long lines
            location = None
            for line in raw_text.split('\n'):
                line = line.strip()
                if (line and 3 < len(line) < 60
                        and 'מחוז' not in line
                        and not line.startswith('₪')
                        and not any(c.isdigit() for c in line[:2])):
                    location = line
                    break

            title = raw_text.split('\n')[0][:120].strip()

            image_url = None
            container = element if not is_link else None
            if container:
                img = container.query_selector('img[src]')
                if img:
                    src = img.get_attribute('src') or ''
                    if src and not src.startswith('data:'):
                        image_url = src

            return {
                'listing_id':    listing_id,
                'source':        'yad2',
                'url':           url,
                'title':         title,
                'price':         price,
                'rooms':         rooms,
                'floor':         floor,
                'size_sqm':      size_sqm,
                'location':      location,
                'neighborhood':  neighborhood,
                'property_type': property_type,
                'parking_count': parking_count,
                'image_url':     image_url,
                'raw_text':      raw_text,
                # amenity fields absent → formatter skips them (no ❌ spam)
            }

        except Exception as e:
            logger.error(f"Error extracting Yad2 listing: {e}")
            return None

    def _get_container_text(self, link_element) -> str:
        """Walk up from a link element to the nearest card container for full text."""
        try:
            text = link_element.evaluate("""link => {
                let el = link.parentElement;
                for (let i = 0; i < 8; i++) {
                    if (!el) break;
                    const tid = el.dataset && el.dataset.testid;
                    if (tid && (tid.includes('item') || tid.includes('platinum') || tid.includes('agency'))) {
                        return el.innerText;
                    }
                    const cls = typeof el.className === 'string' ? el.className : '';
                    if (cls.includes('property-ad-card') || cls.includes('item-card')) {
                        return el.innerText;
                    }
                    el = el.parentElement;
                }
                return link.innerText;
            }""")
            return (text or '').strip()
        except Exception:
            return ''

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

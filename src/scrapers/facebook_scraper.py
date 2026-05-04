"""
Facebook Groups scraper for rental listings.

scrape_group(url, name) — scrape a single group (browser must be initialized).
scrape()                 — backward-compat: iterates groups from config.

ScrapingManager initializes the browser once, then calls scrape_group()
for each of the ~20 configured groups.
"""
import hashlib
import logging
import re
from typing import Dict, List, Optional

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Minimal set of Hebrew/English keywords that signal a rental post.
_RENTAL_KEYWORDS = [
    'להשכרה', 'להשכיר', 'דירה', 'for rent', 'apartment', 'flat', 'rental',
]


class FacebookScraper(BaseScraper):
    def __init__(self, config: dict):
        super().__init__(config)
        self._groups = config.get('sources', {}).get('facebook', {}).get('groups', [])

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def scrape(self) -> List[Dict]:
        """Backward-compat: iterate all groups from config."""
        all_listings: List[Dict] = []
        if not self.page:
            self.initialize_browser()
        for group in self._groups:
            try:
                listings = self.scrape_group(group.get('url', ''), group.get('name', ''))
                all_listings.extend(listings)
            except Exception as e:
                logger.error(f"Error scraping group {group.get('name')}: {e}")
            self.random_delay()
        logger.info(f"Facebook total: {len(all_listings)} listings")
        return all_listings

    def scrape_group(self, group_url: str, group_name: str) -> List[Dict]:
        """
        Scrape a single group.
        Browser must already be initialized by the caller.
        """
        listings: List[Dict] = []
        if not group_url:
            logger.warning(f"No URL for group '{group_name}' — skipping")
            return listings

        try:
            logger.info(f"Facebook → {group_name} ({group_url})")
            self.page.goto(group_url, wait_until='networkidle', timeout=30000)
            self.random_delay()

            scroll_count = self.config.get('scraping', {}).get('scroll_count', 10)
            self.scroll_page(scroll_count)

            try:
                self.page.wait_for_selector('[role="article"]', timeout=10000)
            except Exception:
                logger.warning(f"FB '{group_name}': article selector not found")

            post_elements = self._find_post_elements()
            if not post_elements:
                logger.warning(f"FB '{group_name}': no posts found")
                return listings

            for element in post_elements[:30]:
                try:
                    listing = self._extract_post(element, group_name)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.error(f"Error extracting post: {e}")

            logger.info(f"FB '{group_name}': {len(listings)} listings extracted")

        except Exception as e:
            logger.error(f"FB '{group_name}' error: {e}")

        return listings

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _find_post_elements(self):
        for selector in [
            '[role="article"]',
            '[data-ad-preview="message"]',
            'div[data-pagelet*="FeedUnit"]',
        ]:
            try:
                elements = self.page.query_selector_all(selector)
                if elements:
                    return elements
            except Exception:
                continue
        return None

    def _extract_post(self, element, group_name: str) -> Optional[Dict]:
        try:
            # --- Text ---
            post_text = None
            for selector in [
                '[data-ad-preview="message"]',
                '[data-ad-comet-preview="message"]',
                'div[dir="auto"]',
                '[role="article"] div',
            ]:
                els = element.query_selector_all(selector)
                if els:
                    combined = ' '.join(
                        el.inner_text().strip() for el in els if el.inner_text().strip()
                    )
                    if len(combined) > 50:
                        post_text = combined
                        break

            if not post_text:
                return None

            # Discard non-rental posts early
            if not any(kw.lower() in post_text.lower() for kw in _RENTAL_KEYWORDS):
                return None

            # --- Structured fields ---
            from utils import (
                extract_price_from_text,
                extract_rooms_from_text,
                extract_size_from_text,
                extract_floor_from_text,
                extract_amenities_from_text,
            )

            price = extract_price_from_text(post_text)
            rooms = extract_rooms_from_text(post_text)
            size_sqm = extract_size_from_text(post_text)
            floor = extract_floor_from_text(post_text)
            amenities = extract_amenities_from_text(post_text)
            location = self._extract_location(post_text)

            # --- URL ---
            url = None
            for link in element.query_selector_all('a[href*="/posts/"], a[href*="/permalink/"]'):
                href = link.get_attribute('href')
                if href and ('/posts/' in href or '/permalink/' in href):
                    url = href if href.startswith('http') else f"https://www.facebook.com{href}"
                    break

            # --- Image ---
            image_url = None
            for img in element.query_selector_all('img'):
                src = img.get_attribute('src')
                if src and 'scontent' in src and not any(
                    x in src for x in ['emoji', 'icon', 'static']
                ):
                    image_url = src
                    break

            listing_id = self._generate_id(url, post_text)
            title = post_text.split('\n')[0][:100]

            return {
                'listing_id': listing_id,
                'source': f'facebook_{group_name}',
                'url': url,
                'title': title,
                'price': price,
                'rooms': rooms,
                'floor': floor,
                'size_sqm': size_sqm,
                'location': location,
                'image_url': image_url,
                'raw_text': post_text,
                **amenities,
            }

        except Exception as e:
            logger.error(f"Error extracting FB post: {e}")
            return None

    def _extract_location(self, text: str) -> Optional[str]:
        cities = [
            'תל אביב', 'תל-אביב', 'Tel Aviv', 'TLV',
            'רמת גן', 'Ramat Gan',
            'גבעתיים', 'Givatayim',
            'פתח תקווה', 'Petah Tikva',
            'חולון', 'Holon',
            'בת ים', 'Bat Yam',
            'ירושלים', 'Jerusalem',
            'חיפה', 'Haifa',
            'באר שבע', 'Beer Sheva',
            'נתניה', 'Netanya',
            'ראשון לציון', 'Rishon LeZion',
            'אשדוד', 'Ashdod',
            'הרצליה', 'Herzliya',
            'רעננה', "Ra'anana",
            'כפר סבא', 'Kfar Saba',
            'מודיעין', "Modi'in",
        ]
        text_lower = text.lower()
        for city in cities:
            if city.lower() in text_lower:
                return city
        return None

    def _generate_id(self, url: Optional[str], text: str) -> str:
        if url:
            match = re.search(r'/(posts|permalink)/(\d+)', url)
            if match:
                return f"fb_{match.group(2)}"
        return f"fb_{hashlib.md5(text.encode('utf-8')).hexdigest()[:12]}"

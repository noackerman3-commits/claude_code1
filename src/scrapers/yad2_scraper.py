"""
Yad2 scraper for rental listings.
"""
import logging
from typing import List, Dict, Optional
from .base_scraper import BaseScraper
import hashlib

logger = logging.getLogger(__name__)


class Yad2Scraper(BaseScraper):
    def __init__(self, config: dict):
        super().__init__(config)
        self.base_url = config.get('sources', {}).get('yad2', {}).get('base_url',
            'https://www.yad2.co.il/realestate/rent')

    def build_search_url(self) -> str:
        """Build search URL from config parameters."""
        # base_url is expected to already be a fully filtered Yad2 search URL
        # (area/price/rooms encoded as query params in config.yaml), so use it
        # as-is rather than appending a second, conflicting query string.
        return self.base_url

    def scrape(self) -> List[Dict]:
        """Scrape Yad2 listings."""
        listings = []

        try:
            if not self.page:
                self.initialize_browser()

            search_url = self.build_search_url()
            logger.info(f"Navigating to Yad2: {search_url}")

            self.page.goto(search_url, wait_until='networkidle', timeout=30000)
            self.random_delay()

            # Wait for listings to load
            try:
                self.page.wait_for_selector('.feed_list', timeout=10000)
            except:
                logger.warning("Feed list not found, trying alternative selectors")

            # Extract listing cards - using multiple selectors as fallback
            selectors = [
                '.feeditem',
                '[data-testid="feed-item"]',
                '.feed_item',
                'article'
            ]

            listing_elements = None
            for selector in selectors:
                try:
                    listing_elements = self.page.query_selector_all(selector)
                    if listing_elements:
                        logger.info(f"Found {len(listing_elements)} listings using selector: {selector}")
                        break
                except:
                    continue

            if not listing_elements:
                logger.warning("No listings found on Yad2")
                return listings

            for element in listing_elements[:20]:  # Limit to first 20 listings
                try:
                    listing = self.extract_listing_data(element)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.error(f"Error extracting listing: {e}")
                    continue

            logger.info(f"Successfully scraped {len(listings)} listings from Yad2")

        except Exception as e:
            logger.error(f"Error scraping Yad2: {e}")

        return listings

    def extract_listing_data(self, element) -> Optional[Dict]:
        """Extract data from a single listing element."""
        try:
            # Extract URL and listing ID
            link_element = element.query_selector('a[href*="/item/"]')
            if not link_element:
                link_element = element.query_selector('a')

            url = link_element.get_attribute('href') if link_element else None
            if url and not url.startswith('http'):
                url = f"https://www.yad2.co.il{url}"

            # Generate listing ID from URL or element hash
            listing_id = self.generate_listing_id(url, element.inner_text())

            # Extract title
            title_selectors = ['.title', '[data-testid="title"]', 'h3', 'h2']
            title = None
            for selector in title_selectors:
                title_element = element.query_selector(selector)
                if title_element:
                    title = title_element.inner_text().strip()
                    break

            # Extract price
            price_selectors = ['.price', '[data-testid="price"]', '[class*="price"]']
            price = None
            for selector in price_selectors:
                price_element = element.query_selector(selector)
                if price_element:
                    price_text = price_element.inner_text().strip()
                    price = self.extract_price(price_text)
                    break

            # Extract rooms
            rooms_selectors = ['.rooms', '[data-testid="rooms"]', '[class*="room"]']
            rooms = None
            for selector in rooms_selectors:
                rooms_element = element.query_selector(selector)
                if rooms_element:
                    rooms_text = rooms_element.inner_text().strip()
                    rooms = self.extract_rooms(rooms_text)
                    break

            # If rooms not found in specific element, try to extract from full text
            if not rooms:
                full_text = element.inner_text()
                from utils import extract_rooms_from_text
                rooms = extract_rooms_from_text(full_text)

            # Extract location
            location_selectors = ['.city', '[data-testid="city"]', '[class*="location"]', '[class*="city"]']
            location = None
            for selector in location_selectors:
                location_element = element.query_selector(selector)
                if location_element:
                    location = location_element.inner_text().strip()
                    break

            # Extract image
            image_selectors = ['img', '[class*="image"] img']
            image_url = None
            for selector in image_selectors:
                image_element = element.query_selector(selector)
                if image_element:
                    image_url = image_element.get_attribute('src')
                    break

            listing = {
                'listing_id': listing_id,
                'source': 'yad2',
                'url': url,
                'title': title,
                'price': price,
                'rooms': rooms,
                'location': location,
                'image_url': image_url,
                'full_text': element.inner_text()
            }

            return listing

        except Exception as e:
            logger.error(f"Error extracting listing data: {e}")
            return None

    def generate_listing_id(self, url: str, text: str) -> str:
        """Generate unique listing ID."""
        if url and '/item/' in url:
            # Extract item ID from URL
            parts = url.split('/item/')
            if len(parts) > 1:
                item_id = parts[1].split('?')[0].split('/')[0]
                return f"yad2_{item_id}"

        # Fallback: hash of text content
        hash_obj = hashlib.md5(text.encode('utf-8'))
        return f"yad2_{hash_obj.hexdigest()[:12]}"

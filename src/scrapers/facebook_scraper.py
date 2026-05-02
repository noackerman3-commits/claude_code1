"""
Facebook Groups scraper for rental listings.
"""
import logging
from typing import List, Dict, Optional
from .base_scraper import BaseScraper
import hashlib
import re

logger = logging.getLogger(__name__)


class FacebookScraper(BaseScraper):
    def __init__(self, config: dict):
        super().__init__(config)
        self.groups = config.get('sources', {}).get('facebook', {}).get('groups', [])

    def scrape(self) -> List[Dict]:
        """Scrape Facebook group posts."""
        all_listings = []

        try:
            if not self.page:
                self.initialize_browser()

            for group in self.groups:
                group_name = group.get('name')
                group_url = group.get('url')

                logger.info(f"Scraping Facebook group: {group_name}")

                try:
                    listings = self.scrape_group(group_url, group_name)
                    all_listings.extend(listings)
                except Exception as e:
                    logger.error(f"Error scraping group {group_name}: {e}")
                    continue

                self.random_delay()

            logger.info(f"Successfully scraped {len(all_listings)} listings from Facebook")

        except Exception as e:
            logger.error(f"Error scraping Facebook: {e}")

        return all_listings

    def scrape_group(self, group_url: str, group_name: str) -> List[Dict]:
        """Scrape a single Facebook group."""
        listings = []

        try:
            logger.info(f"Navigating to: {group_url}")
            self.page.goto(group_url, wait_until='networkidle', timeout=30000)
            self.random_delay()

            # Scroll to load posts
            scroll_count = self.config.get('scraping', {}).get('scroll_count', 10)
            self.scroll_page(scroll_count)

            # Wait for posts to load
            try:
                self.page.wait_for_selector('[role="article"]', timeout=10000)
            except:
                logger.warning("Articles not found, trying alternative approach")

            # Extract post elements
            post_selectors = [
                '[role="article"]',
                '[data-ad-preview="message"]',
                'div[data-pagelet*="FeedUnit"]'
            ]

            post_elements = None
            for selector in post_selectors:
                try:
                    post_elements = self.page.query_selector_all(selector)
                    if post_elements:
                        logger.info(f"Found {len(post_elements)} posts using selector: {selector}")
                        break
                except:
                    continue

            if not post_elements:
                logger.warning(f"No posts found in group: {group_name}")
                return listings

            for element in post_elements[:30]:  # Limit to first 30 posts
                try:
                    listing = self.extract_post_data(element, group_name)
                    if listing:
                        listings.append(listing)
                except Exception as e:
                    logger.error(f"Error extracting post: {e}")
                    continue

            logger.info(f"Extracted {len(listings)} listings from {group_name}")

        except Exception as e:
            logger.error(f"Error scraping group {group_name}: {e}")

        return listings

    def extract_post_data(self, element, group_name: str) -> Optional[Dict]:
        """Extract data from a single Facebook post."""
        try:
            # Extract post text
            text_selectors = [
                '[data-ad-preview="message"]',
                '[data-ad-comet-preview="message"]',
                'div[dir="auto"]',
                '[role="article"] div'
            ]

            post_text = None
            for selector in text_selectors:
                text_elements = element.query_selector_all(selector)
                if text_elements:
                    # Combine all text elements
                    texts = [el.inner_text().strip() for el in text_elements if el.inner_text().strip()]
                    post_text = ' '.join(texts)
                    if len(post_text) > 50:  # Minimum text length
                        break

            if not post_text:
                return None

            # Check if post is relevant (contains rental keywords)
            rental_keywords = ['להשכרה', 'להשכיר', 'דירה', 'for rent', 'apartment', 'flat']
            if not any(keyword.lower() in post_text.lower() for keyword in rental_keywords):
                return None

            # Extract price
            from utils import extract_price_from_text
            price = extract_price_from_text(post_text)

            # Extract rooms
            from utils import extract_rooms_from_text
            rooms = extract_rooms_from_text(post_text)

            # Extract post URL
            url = None
            link_elements = element.query_selector_all('a[href*="/posts/"], a[href*="/permalink/"]')
            for link in link_elements:
                href = link.get_attribute('href')
                if href and ('/posts/' in href or '/permalink/' in href):
                    url = href if href.startswith('http') else f"https://www.facebook.com{href}"
                    break

            # Extract location from text (basic extraction)
            location = self.extract_location(post_text)

            # Extract image
            image_url = None
            img_elements = element.query_selector_all('img')
            for img in img_elements:
                src = img.get_attribute('src')
                # Avoid profile pictures and icons
                if src and 'scontent' in src and not any(x in src for x in ['emoji', 'icon', 'static']):
                    image_url = src
                    break

            # Generate listing ID
            listing_id = self.generate_listing_id(url, post_text)

            # Create title from first line or summary
            title = post_text.split('\n')[0][:100] if post_text else "Facebook Listing"

            listing = {
                'listing_id': listing_id,
                'source': f'facebook_{group_name}',
                'url': url,
                'title': title,
                'price': price,
                'rooms': rooms,
                'location': location,
                'image_url': image_url,
                'full_text': post_text
            }

            return listing

        except Exception as e:
            logger.error(f"Error extracting post data: {e}")
            return None

    def extract_location(self, text: str) -> Optional[str]:
        """Extract location from post text."""
        # Common cities in Israel
        cities = [
            'תל אביב', 'תל-אביב', 'Tel Aviv', 'TLV',
            'רמת גן', 'Ramat Gan',
            'גבעתיים', 'Givatayim',
            'חולון', 'Holon',
            'בת ים', 'Bat Yam',
            'ירושלים', 'Jerusalem',
            'חיפה', 'Haifa',
            'באר שבע', 'Beer Sheva'
        ]

        text_lower = text.lower()
        for city in cities:
            if city.lower() in text_lower:
                return city

        return None

    def generate_listing_id(self, url: str, text: str) -> str:
        """Generate unique listing ID."""
        if url and ('/posts/' in url or '/permalink/' in url):
            # Extract post ID from URL
            match = re.search(r'/(posts|permalink)/(\d+)', url)
            if match:
                return f"fb_{match.group(2)}"

        # Fallback: hash of text content
        hash_obj = hashlib.md5(text.encode('utf-8'))
        return f"fb_{hash_obj.hexdigest()[:12]}"

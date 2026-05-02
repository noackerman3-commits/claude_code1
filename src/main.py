"""
Main orchestration script for the rental agent.
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from database import Database
from scrapers.yad2_scraper import Yad2Scraper
from scrapers.facebook_scraper import FacebookScraper
from notifier import TelegramNotifier
from utils import setup_logging, matches_keywords, excludes_keywords
import logging

logger = logging.getLogger(__name__)


def filter_listing(listing: dict, search_params: dict) -> bool:
    """Check if listing matches search criteria."""

    # Check price range
    price_range = search_params.get('price_range', {})
    if listing.get('price'):
        min_price = price_range.get('min', 0)
        max_price = price_range.get('max', 999999)

        if not (min_price <= listing['price'] <= max_price):
            logger.debug(f"Listing filtered: price {listing['price']} not in range {min_price}-{max_price}")
            return False

    # Check minimum rooms
    min_rooms = search_params.get('min_rooms')
    if min_rooms and listing.get('rooms'):
        if listing['rooms'] < min_rooms:
            logger.debug(f"Listing filtered: {listing['rooms']} rooms < {min_rooms}")
            return False

    # Check location if specified
    locations = search_params.get('locations', [])
    if locations and listing.get('location'):
        location_match = any(
            loc.lower() in listing['location'].lower()
            for loc in locations
        )
        if not location_match:
            logger.debug(f"Listing filtered: location {listing['location']} not in {locations}")
            return False

    # Check must-have keywords
    must_have = search_params.get('must_have_keywords', [])
    full_text = listing.get('full_text', '') + ' ' + listing.get('title', '')

    if must_have and not matches_keywords(full_text, must_have):
        logger.debug(f"Listing filtered: missing must-have keywords")
        return False

    # Check exclude keywords
    exclude = search_params.get('exclude_keywords', [])
    if exclude and excludes_keywords(full_text, exclude):
        logger.debug(f"Listing filtered: contains exclude keywords")
        return False

    return True


def main():
    """Main execution function."""

    # Setup logging
    setup_logging()
    logger.info("=== Rental Agent Starting ===")

    try:
        # Load configuration
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        config_manager = ConfigManager(config_path)
        config = config_manager.load_config()

        if not config_manager.validate_config():
            logger.error("Invalid configuration, exiting")
            return

        # Initialize database
        db_path = config.get('database', {}).get('path', './data/listings.db')
        # Convert relative path to absolute
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)

        db = Database(db_path)
        db.init_db()

        # Initialize Telegram notifier
        telegram_config = config.get('telegram', {})
        notifier = TelegramNotifier(
            telegram_config['bot_token'],
            telegram_config['chat_id']
        )

        # Get search parameters
        search_params = config.get('search_parameters', {})
        sources_config = config.get('sources', {})

        new_listings_count = 0
        total_scraped = 0

        # Scrape Yad2
        if sources_config.get('yad2', {}).get('enabled', True):
            logger.info("Starting Yad2 scraper...")
            try:
                yad2_scraper = Yad2Scraper(config)
                yad2_listings = yad2_scraper.scrape()
                total_scraped += len(yad2_listings)

                for listing in yad2_listings:
                    # Filter listing
                    if not filter_listing(listing, search_params):
                        continue

                    # Check if already exists
                    if db.listing_exists(listing['listing_id'], listing['source']):
                        logger.debug(f"Listing {listing['listing_id']} already exists")
                        continue

                    # Send notification
                    logger.info(f"New listing found: {listing['listing_id']}")
                    notifier.send_listing(listing)

                    # Save to database
                    db.add_listing(listing)
                    new_listings_count += 1

                yad2_scraper.close_browser()

            except Exception as e:
                logger.error(f"Error in Yad2 scraper: {e}")

        # Scrape Facebook
        if sources_config.get('facebook', {}).get('enabled', True):
            logger.info("Starting Facebook scraper...")
            try:
                fb_scraper = FacebookScraper(config)
                fb_listings = fb_scraper.scrape()
                total_scraped += len(fb_listings)

                for listing in fb_listings:
                    # Filter listing
                    if not filter_listing(listing, search_params):
                        continue

                    # Check if already exists
                    if db.listing_exists(listing['listing_id'], listing['source']):
                        logger.debug(f"Listing {listing['listing_id']} already exists")
                        continue

                    # Send notification
                    logger.info(f"New listing found: {listing['listing_id']}")
                    notifier.send_listing(listing)

                    # Save to database
                    db.add_listing(listing)
                    new_listings_count += 1

                fb_scraper.close_browser()

            except Exception as e:
                logger.error(f"Error in Facebook scraper: {e}")

        # Summary
        logger.info(f"=== Scraping Complete ===")
        logger.info(f"Total listings scraped: {total_scraped}")
        logger.info(f"New listings found: {new_listings_count}")
        logger.info(f"Total in database: {db.get_listing_count()}")

    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

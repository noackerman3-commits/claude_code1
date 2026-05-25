"""
Scheduler for automated apartment scraping.
Runs daily at 14:00 Jerusalem time.
"""
import sys
import os
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

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
            return False

    # Check minimum rooms
    min_rooms = search_params.get('min_rooms')
    if min_rooms and listing.get('rooms'):
        if listing['rooms'] < min_rooms:
            return False

    # Check location if specified
    locations = search_params.get('locations', [])
    if locations and listing.get('location'):
        location_match = any(
            loc.lower() in listing['location'].lower()
            for loc in locations
        )
        if not location_match:
            return False

    # Check must-have keywords
    must_have = search_params.get('must_have_keywords', [])
    full_text = listing.get('full_text', '') + ' ' + listing.get('title', '')

    if must_have and not matches_keywords(full_text, must_have):
        return False

    # Check exclude keywords
    exclude = search_params.get('exclude_keywords', [])
    if exclude and excludes_keywords(full_text, exclude):
        return False

    return True


def send_aggregated_notification(notifier: TelegramNotifier, new_listings: list, total_scraped: int = 0):
    """Send a single notification with all new listings, or a 'no new listings' summary."""

    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')

    if not new_listings:
        message = (
            f"🔍 *Daily Scan Complete*\n"
            f"⏰ {timestamp}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"No new listings found.\n"
            f"_Scanned {total_scraped} listings total._"
        )
        notifier.send_message(message)
        logger.info("Sent 'no new listings' notification")
        return

    message = f"🏠 *New Apartments Found: {len(new_listings)}*\n"
    message += f"⏰ {timestamp}\n"
    message += "━━━━━━━━━━━━━━━━━━━━━\n\n"

    for i, listing in enumerate(new_listings[:10], 1):
        message += f"*{i}. {listing.get('title', 'Apartment')[:50]}*\n"

        if listing.get('location'):
            message += f"📍 {listing['location']}\n"

        if listing.get('price'):
            message += f"💰 ₪{listing['price']:,}\n"

        if listing.get('rooms'):
            message += f"🛏 {listing['rooms']} rooms\n"

        if listing.get('url'):
            message += f"🔗 [View Listing]({listing['url']})\n"

        message += f"_Source: {listing.get('source', 'Unknown')}_\n\n"

    if len(new_listings) > 10:
        message += f"\n_+ {len(new_listings) - 10} more listings in database_"

    notifier.send_message(message)
    logger.info(f"Sent aggregated notification with {len(new_listings)} listings")


def run_scraping_job():
    """Main scraping job - runs at scheduled times."""

    try:
        logger.info("=" * 60)
        logger.info(f"Starting scheduled scrape at {datetime.now()}")
        logger.info("=" * 60)

        # Load configuration
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        config_manager = ConfigManager(config_path)
        config = config_manager.load_config()

        # Initialize database
        db_path = config.get('database', {}).get('path', './data/listings.db')
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

        # Collect all new listings
        new_listings = []
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
                        continue

                    # Add to new listings and save to database
                    new_listings.append(listing)
                    db.add_listing(listing)

                yad2_scraper.close_browser()
                logger.info(f"Yad2: Found {len(new_listings)} new listings")

            except Exception as e:
                logger.error(f"Error in Yad2 scraper: {e}")

        # Scrape Facebook
        if sources_config.get('facebook', {}).get('enabled', True):
            logger.info("Starting Facebook scraper...")
            try:
                fb_scraper = FacebookScraper(config)
                fb_listings = fb_scraper.scrape()
                total_scraped += len(fb_listings)

                fb_new_count = len(new_listings)

                for listing in fb_listings:
                    # Filter listing
                    if not filter_listing(listing, search_params):
                        continue

                    # Check if already exists
                    if db.listing_exists(listing['listing_id'], listing['source']):
                        continue

                    # Add to new listings and save to database
                    new_listings.append(listing)
                    db.add_listing(listing)

                fb_scraper.close_browser()
                logger.info(f"Facebook: Found {len(new_listings) - fb_new_count} new listings")

            except Exception as e:
                logger.error(f"Error in Facebook scraper: {e}")

        # Send aggregated notification
        send_aggregated_notification(notifier, new_listings, total_scraped)

        # Summary
        logger.info("=" * 60)
        logger.info(f"Scraping complete!")
        logger.info(f"Total listings scraped: {total_scraped}")
        logger.info(f"New listings found: {len(new_listings)}")
        logger.info(f"Total in database: {db.get_listing_count()}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Fatal error in scraping job: {e}", exc_info=True)


def main():
    """Main scheduler entry point."""

    # Setup logging
    setup_logging()

    # Define Israel timezone
    israel_tz = pytz.timezone('Asia/Jerusalem')

    logger.info("=" * 60)
    logger.info("Rental Agent Scheduler Starting")
    logger.info("=" * 60)
    logger.info(f"Timezone: {israel_tz}")
    logger.info("Schedule: 14:00 daily (Jerusalem time)")
    logger.info("=" * 60)

    # Create scheduler
    scheduler = BlockingScheduler(timezone=israel_tz)

    # Single daily job at 14:00 Jerusalem time
    scheduler.add_job(
        run_scraping_job,
        CronTrigger(hour=14, minute=0, timezone=israel_tz),
        id='daily_scrape',
        name='Daily Scrape (14:00)',
        replace_existing=True
    )

    # Log next run times
    jobs = scheduler.get_jobs()
    logger.info("\nScheduled jobs:")
    for job in jobs:
        next_run = job.next_run_time
        logger.info(f"  - {job.name}: Next run at {next_run}")

    logger.info("\n" + "=" * 60)
    logger.info("Scheduler is running. Press Ctrl+C to stop.")
    logger.info("=" * 60)

    try:
        # Start scheduler (blocks)
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        scheduler.shutdown()


if __name__ == "__main__":
    main()

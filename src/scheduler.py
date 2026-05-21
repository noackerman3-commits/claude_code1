"""
Scheduler for automated apartment scraping.
Runs daily at 14:00 Israel time.
"""
import sys
import os
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

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
    price_range = search_params.get('price_range', {})
    if listing.get('price'):
        min_price = price_range.get('min', 0)
        max_price = price_range.get('max', 999999)
        if not (min_price <= listing['price'] <= max_price):
            return False

    min_rooms = search_params.get('min_rooms')
    if min_rooms and listing.get('rooms'):
        if listing['rooms'] < min_rooms:
            return False

    locations = search_params.get('locations', [])
    if locations and listing.get('location'):
        if not any(loc.lower() in listing['location'].lower() for loc in locations):
            return False

    must_have = search_params.get('must_have_keywords', [])
    full_text = listing.get('full_text', '') + ' ' + listing.get('title', '')
    if must_have and not matches_keywords(full_text, must_have):
        return False

    exclude = search_params.get('exclude_keywords', [])
    if exclude and excludes_keywords(full_text, exclude):
        return False

    return True


def run_scraping_job():
    """Main scraping job — runs at the configured daily time."""
    try:
        logger.info("=" * 60)
        logger.info(f"Starting scheduled scrape at {datetime.now()}")
        logger.info("=" * 60)

        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        config_manager = ConfigManager(config_path)
        config = config_manager.load_config()

        db_path = config.get('database', {}).get('path', './data/listings.db')
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)

        db = Database(db_path)
        db.init_db()

        telegram_config = config.get('telegram', {})
        notifier = TelegramNotifier(telegram_config['bot_token'], telegram_config['chat_id'])

        search_params = config.get('search_parameters', {})
        sources_config = config.get('sources', {})

        new_listings = []
        total_scraped = 0

        # Scrape Yad2
        if sources_config.get('yad2', {}).get('enabled', True):
            logger.info("Starting Yad2 scraper...")
            try:
                yad2_scraper = Yad2Scraper(config)
                yad2_listings = yad2_scraper.scrape()
                total_scraped += len(yad2_listings)
                yad2_new = 0

                for listing in yad2_listings:
                    if not filter_listing(listing, search_params):
                        continue
                    if db.listing_exists(listing['listing_id'], listing['source']):
                        continue
                    new_listings.append(listing)
                    db.add_listing(listing)
                    yad2_new += 1

                yad2_scraper.close_browser()
                logger.info(f"Yad2: {yad2_new} new listings out of {len(yad2_listings)} scraped")

            except Exception as e:
                logger.error(f"Error in Yad2 scraper: {e}")

        # Scrape Facebook
        if sources_config.get('facebook', {}).get('enabled', False):
            logger.info("Starting Facebook scraper...")
            try:
                fb_scraper = FacebookScraper(config)
                fb_listings = fb_scraper.scrape()
                total_scraped += len(fb_listings)
                fb_new = 0

                for listing in fb_listings:
                    if not filter_listing(listing, search_params):
                        continue
                    if db.listing_exists(listing['listing_id'], listing['source']):
                        continue
                    new_listings.append(listing)
                    db.add_listing(listing)
                    fb_new += 1

                fb_scraper.close_browser()
                logger.info(f"Facebook: {fb_new} new listings out of {len(fb_listings)} scraped")

            except Exception as e:
                logger.error(f"Error in Facebook scraper: {e}")

        # Always send scan summary via Telegram
        notifier.send_scan_summary(
            new_listings=new_listings,
            total_scraped=total_scraped,
            total_in_db=db.get_listing_count()
        )

        logger.info("=" * 60)
        logger.info(f"Scraping complete! {len(new_listings)} new / {total_scraped} scraped / {db.get_listing_count()} in DB")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Fatal error in scraping job: {e}", exc_info=True)


def main():
    """Main scheduler entry point."""
    setup_logging()

    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
    config_manager = ConfigManager(config_path)
    config = config_manager.load_config()

    schedule_cfg = config.get('schedule', {})
    scan_hour = schedule_cfg.get('scan_hour', 14)
    scan_minute = schedule_cfg.get('scan_minute', 0)
    tz_name = schedule_cfg.get('timezone', 'Asia/Jerusalem')
    israel_tz = pytz.timezone(tz_name)

    logger.info("=" * 60)
    logger.info("Rental Agent Scheduler Starting")
    logger.info(f"Timezone: {tz_name}")
    logger.info(f"Schedule: daily at {scan_hour:02d}:{scan_minute:02d}")
    logger.info("=" * 60)

    scheduler = BlockingScheduler(timezone=israel_tz)

    scheduler.add_job(
        run_scraping_job,
        CronTrigger(hour=scan_hour, minute=scan_minute, timezone=israel_tz),
        id='daily_scrape',
        name=f'Daily Scrape ({scan_hour:02d}:{scan_minute:02d})',
        replace_existing=True
    )

    for job in scheduler.get_jobs():
        logger.info(f"Scheduled: {job.name} — next run at {job.next_run_time}")

    logger.info("Scheduler running. Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        scheduler.shutdown()


if __name__ == "__main__":
    main()

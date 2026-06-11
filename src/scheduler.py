"""
Scheduler for automated rental URL scanning.
Runs daily at 14:00 Jerusalem time.
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
from utils import setup_logging
import logging

logger = logging.getLogger(__name__)


def send_scan_notification(notifier: TelegramNotifier, new_listings: list, total_scraped: int):
    """Send Telegram notification with daily scan results."""
    israel_tz = pytz.timezone('Asia/Jerusalem')
    now = datetime.now(israel_tz)
    time_str = now.strftime('%d/%m/%Y %H:%M')

    if not new_listings:
        message = (
            f"🔍 *Daily Scan Complete*\n"
            f"⏰ {time_str}\n"
            f"📊 Scanned: {total_scraped} listings\n"
            f"✅ No new listings found"
        )
        notifier.send_message(message)
        logger.info("Sent scan notification: no new listings")
        return

    message = (
        f"🏠 *{len(new_listings)} New Listing{'s' if len(new_listings) > 1 else ''} Found!*\n"
        f"⏰ {time_str}\n"
        f"📊 Scanned: {total_scraped} total\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

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
        message += f"\n_+ {len(new_listings) - 10} more listings saved to database_"

    notifier.send_message(message)
    logger.info(f"Sent notification with {len(new_listings)} new listings")


def run_scanning_job():
    """Scan all configured pre-filtered URLs and notify via Telegram."""
    try:
        logger.info("=" * 60)
        logger.info(f"Starting daily scan at {datetime.now()}")
        logger.info("=" * 60)

        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        config_manager = ConfigManager(config_path)
        config = config_manager.load_config()

        db_path = config.get('database', {}).get('path', './data/listings.db')
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        db = Database(db_path)
        db.init_db()

        telegram_config = config.get('telegram', {})
        notifier = TelegramNotifier(
            telegram_config['bot_token'],
            telegram_config['chat_id']
        )

        scan_urls = config.get('scan_urls', [])
        enabled_urls = [u for u in scan_urls if u.get('enabled', True)]

        if not enabled_urls:
            logger.warning("No enabled scan_urls in config.yaml — nothing to scan")
            return

        new_listings = []
        total_scraped = 0

        yad2_urls = [u for u in enabled_urls if u.get('source') == 'yad2']
        facebook_urls = [u for u in enabled_urls if u.get('source') == 'facebook']

        # Scan Yad2 URLs (single browser instance for all URLs)
        if yad2_urls:
            try:
                yad2_scraper = Yad2Scraper(config)
                for url_config in yad2_urls:
                    name = url_config.get('name', url_config['url'])
                    logger.info(f"Scanning: {name}")
                    listings = yad2_scraper.scrape(url=url_config['url'])
                    total_scraped += len(listings)
                    for listing in listings:
                        if not db.listing_exists(listing['listing_id'], listing['source']):
                            new_listings.append(listing)
                            db.add_listing(listing)
                yad2_scraper.close_browser()
                yad2_new = sum(1 for l in new_listings if l.get('source', '').startswith('yad2'))
                logger.info(f"Yad2: {yad2_new} new listings")
            except Exception as e:
                logger.error(f"Error scanning Yad2 URLs: {e}", exc_info=True)

        # Scan Facebook group URLs (single browser instance for all groups)
        if facebook_urls:
            try:
                fb_scraper = FacebookScraper(config)
                for url_config in facebook_urls:
                    name = url_config.get('name', url_config['url'])
                    url = url_config['url']
                    logger.info(f"Scanning Facebook: {name}")
                    listings = fb_scraper.scrape_group(url, name)
                    total_scraped += len(listings)
                    for listing in listings:
                        if not db.listing_exists(listing['listing_id'], listing['source']):
                            new_listings.append(listing)
                            db.add_listing(listing)
                fb_scraper.close_browser()
                fb_new = sum(1 for l in new_listings if l.get('source', '').startswith('facebook'))
                logger.info(f"Facebook: {fb_new} new listings")
            except Exception as e:
                logger.error(f"Error scanning Facebook URLs: {e}", exc_info=True)

        send_scan_notification(notifier, new_listings, total_scraped)

        logger.info("=" * 60)
        logger.info(f"Scan complete — scraped: {total_scraped}, new: {len(new_listings)}, "
                    f"total in DB: {db.get_listing_count()}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Fatal error in scanning job: {e}", exc_info=True)


def main():
    """Start the scheduler."""
    setup_logging()

    israel_tz = pytz.timezone('Asia/Jerusalem')

    logger.info("=" * 60)
    logger.info("Rental URL Scanner Starting")
    logger.info("Schedule: 14:00 daily (Jerusalem time)")
    logger.info("=" * 60)

    scheduler = BlockingScheduler(timezone=israel_tz)

    scheduler.add_job(
        run_scanning_job,
        CronTrigger(hour=14, minute=0, timezone=israel_tz),
        id='daily_scan',
        name='Daily Scan (14:00 Jerusalem)',
        replace_existing=True
    )

    jobs = scheduler.get_jobs()
    logger.info("\nScheduled jobs:")
    for job in jobs:
        logger.info(f"  - {job.name}: Next run at {job.next_run_time}")

    logger.info("\nScheduler is running. Press Ctrl+C to stop.")
    logger.info("=" * 60)

    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
        scheduler.shutdown()


if __name__ == "__main__":
    main()

"""
Daily rental scan — entry point for Claude Code scheduled sessions (14:00 Jerusalem).

State is persisted in data/seen_listings.json so repeated runs across ephemeral
containers only notify about genuinely new listings.
"""
import sys
import os
import json
import logging
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config_manager import ConfigManager
from scrapers.yad2_scraper import Yad2Scraper
from scrapers.facebook_scraper import FacebookScraper
from notifier import TelegramNotifier
from scheduler import filter_listing, send_aggregated_notification
from utils import setup_logging

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
SEEN_FILE = os.path.join(DATA_DIR, 'seen_listings.json')

logger = logging.getLogger(__name__)


def load_seen_ids() -> set:
    """Load previously seen listing IDs from JSON file."""
    if not os.path.exists(SEEN_FILE):
        return set()
    try:
        with open(SEEN_FILE, 'r') as f:
            data = json.load(f)
            return set(data.get('seen_ids', []))
    except Exception as e:
        logger.error(f"Error loading seen IDs: {e}")
        return set()


def save_seen_ids(seen_ids: set):
    """Save seen listing IDs to JSON file for next run."""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(SEEN_FILE, 'w') as f:
            json.dump(
                {
                    'seen_ids': sorted(seen_ids),
                    'last_updated': datetime.now().isoformat(),
                    'count': len(seen_ids),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        logger.info(f"Saved {len(seen_ids)} seen IDs to {SEEN_FILE}")
    except Exception as e:
        logger.error(f"Error saving seen IDs: {e}")


def run():
    """Execute the daily scraping job and return a summary dict."""
    setup_logging()
    logger.info("=" * 60)
    logger.info(f"Daily Rental Scan — {datetime.now().strftime('%d/%m/%Y %H:%M')} (Jerusalem)")
    logger.info("=" * 60)

    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    config_manager = ConfigManager(config_path)
    config = config_manager.load_config()

    telegram_config = config.get('telegram', {})
    notifier = TelegramNotifier(telegram_config['bot_token'], telegram_config['chat_id'])

    search_params = config.get('search_parameters', {})
    sources_config = config.get('sources', {})

    seen_ids = load_seen_ids()
    logger.info(f"Loaded {len(seen_ids)} previously seen listing IDs")

    new_listings = []
    total_scraped = 0
    errors = []

    # --- Yad2 ---
    if sources_config.get('yad2', {}).get('enabled', True):
        logger.info("Starting Yad2 scraper...")
        try:
            yad2_scraper = Yad2Scraper(config)
            yad2_listings = yad2_scraper.scrape()
            total_scraped += len(yad2_listings)

            for listing in yad2_listings:
                if not filter_listing(listing, search_params):
                    continue
                key = f"{listing['source']}:{listing['listing_id']}"
                if key not in seen_ids:
                    new_listings.append(listing)
                    seen_ids.add(key)

            yad2_scraper.close_browser()
            logger.info(f"Yad2: scraped {len(yad2_listings)}, {len(new_listings)} new so far")
        except Exception as e:
            logger.error(f"Yad2 scraper error: {e}", exc_info=True)
            errors.append(f"Yad2: {e}")

    # --- Facebook ---
    if sources_config.get('facebook', {}).get('enabled', False):
        logger.info("Starting Facebook scraper...")
        try:
            fb_before = len(new_listings)
            fb_scraper = FacebookScraper(config)
            fb_listings = fb_scraper.scrape()
            total_scraped += len(fb_listings)

            for listing in fb_listings:
                if not filter_listing(listing, search_params):
                    continue
                key = f"{listing['source']}:{listing['listing_id']}"
                if key not in seen_ids:
                    new_listings.append(listing)
                    seen_ids.add(key)

            fb_scraper.close_browser()
            logger.info(f"Facebook: scraped {len(fb_listings)}, {len(new_listings) - fb_before} new")
        except Exception as e:
            logger.error(f"Facebook scraper error: {e}", exc_info=True)
            errors.append(f"Facebook: {e}")

    # Send aggregated Telegram notification (handles empty list gracefully)
    send_aggregated_notification(notifier, new_listings)

    # Persist updated seen IDs so the next run skips these
    save_seen_ids(seen_ids)

    summary = {
        'new': len(new_listings),
        'total_scraped': total_scraped,
        'total_seen': len(seen_ids),
        'errors': errors,
        'timestamp': datetime.now().isoformat(),
    }

    logger.info("=" * 60)
    logger.info(f"Scan complete — {summary['new']} new / {summary['total_scraped']} scraped")
    if errors:
        logger.warning(f"Errors: {errors}")
    logger.info("=" * 60)

    return summary


if __name__ == "__main__":
    result = run()
    print()
    print("=" * 60)
    print(f"DONE — New listings: {result['new']} / Scraped: {result['total_scraped']}")
    if result['errors']:
        print(f"Errors: {result['errors']}")
    print("Check Telegram for notifications.")
    print("=" * 60)

"""
Daily rental scan — runs once per invocation (designed for Claude Code scheduled sessions).

State persistence: data/seen_ids.json is committed to git after each run so that
new listings are not re-notified on subsequent daily runs.
"""
import sys
import os
import json
import subprocess
import logging
from datetime import datetime
import pytz

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config_manager import ConfigManager
from scrapers.yad2_scraper import Yad2Scraper
from scrapers.facebook_scraper import FacebookScraper
from notifier import TelegramNotifier
from utils import setup_logging, matches_keywords, excludes_keywords

logger = logging.getLogger(__name__)

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
SEEN_IDS_PATH = os.path.join(REPO_ROOT, 'data', 'seen_ids.json')


def load_seen_ids() -> set:
    try:
        with open(SEEN_IDS_PATH, 'r') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen_ids(seen_ids: set):
    os.makedirs(os.path.dirname(SEEN_IDS_PATH), exist_ok=True)
    with open(SEEN_IDS_PATH, 'w') as f:
        json.dump(sorted(seen_ids), f, indent=2)


def commit_seen_ids():
    """Commit and push the updated seen_ids.json to persist state between runs."""
    try:
        subprocess.run(['git', 'add', '-f', 'data/seen_ids.json'], cwd=REPO_ROOT, check=True)
        result = subprocess.run(
            ['git', 'diff', '--cached', '--quiet'],
            cwd=REPO_ROOT
        )
        if result.returncode != 0:
            subprocess.run(
                ['git', 'commit', '-m', f'chore: update seen listings ({datetime.now().strftime("%Y-%m-%d %H:%M")})'],
                cwd=REPO_ROOT, check=True
            )
            subprocess.run(
                ['git', 'push', '-u', 'origin', 'HEAD'],
                cwd=REPO_ROOT, check=True
            )
            logger.info("Committed and pushed seen_ids.json")
        else:
            logger.info("No new listings to commit")
    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e}")


def filter_listing(listing: dict, search_params: dict) -> bool:
    price_range = search_params.get('price_range', {})
    if listing.get('price'):
        if not (price_range.get('min', 0) <= listing['price'] <= price_range.get('max', 999999)):
            return False

    min_rooms = search_params.get('min_rooms')
    if min_rooms and listing.get('rooms') and listing['rooms'] < min_rooms:
        return False

    locations = search_params.get('locations', [])
    if locations and listing.get('location'):
        if not any(loc.lower() in listing['location'].lower() for loc in locations):
            return False

    full_text = listing.get('full_text', '') + ' ' + listing.get('title', '')
    must_have = search_params.get('must_have_keywords', [])
    if must_have and not matches_keywords(full_text, must_have):
        return False

    exclude = search_params.get('exclude_keywords', [])
    if exclude and excludes_keywords(full_text, exclude):
        return False

    return True


def send_summary(notifier: TelegramNotifier, new_listings: list, total_scraped: int):
    israel_tz = pytz.timezone('Asia/Jerusalem')
    now = datetime.now(israel_tz)

    if not new_listings:
        msg = (
            f"🔍 *Daily Rental Scan — {now.strftime('%d/%m/%Y %H:%M')}*\n"
            f"No new listings found (scanned {total_scraped} total)."
        )
        notifier.send_message(msg)
        return

    msg = (
        f"🏠 *{len(new_listings)} New Listing(s) Found!*\n"
        f"⏰ {now.strftime('%d/%m/%Y %H:%M')} (IL)\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    for i, listing in enumerate(new_listings[:10], 1):
        msg += f"*{i}. {(listing.get('title') or 'Apartment')[:50]}*\n"
        if listing.get('location'):
            msg += f"📍 {listing['location']}\n"
        if listing.get('price'):
            msg += f"💰 ₪{listing['price']:,}\n"
        if listing.get('rooms'):
            msg += f"🛏 {listing['rooms']} rooms\n"
        if listing.get('url'):
            msg += f"🔗 [View Listing]({listing['url']})\n"
        msg += f"_Source: {listing.get('source', 'Unknown')}_\n\n"

    if len(new_listings) > 10:
        msg += f"_+ {len(new_listings) - 10} more — check the full scan log_"

    notifier.send_message(msg)


def main():
    setup_logging(os.path.join(REPO_ROOT, 'logs'))
    israel_tz = pytz.timezone('Asia/Jerusalem')
    now = datetime.now(israel_tz)
    logger.info(f"=== Daily Rental Scan starting at {now.strftime('%Y-%m-%d %H:%M %Z')} ===")

    config_path = os.path.join(REPO_ROOT, 'config.yaml')
    config_manager = ConfigManager(config_path)
    config = config_manager.load_config()

    if not config_manager.validate_config():
        logger.error("Invalid configuration, aborting")
        sys.exit(1)

    telegram_cfg = config.get('telegram', {})
    notifier = TelegramNotifier(telegram_cfg['bot_token'], telegram_cfg['chat_id'])
    search_params = config.get('search_parameters', {})
    sources_config = config.get('sources', {})

    seen_ids = load_seen_ids()
    logger.info(f"Loaded {len(seen_ids)} previously seen listing IDs")

    new_listings = []
    total_scraped = 0

    if sources_config.get('yad2', {}).get('enabled', True):
        logger.info("Scraping Yad2...")
        try:
            scraper = Yad2Scraper(config)
            listings = scraper.scrape()
            total_scraped += len(listings)

            for listing in listings:
                lid = f"{listing.get('source')}:{listing.get('listing_id')}"
                if lid in seen_ids:
                    continue
                if not filter_listing(listing, search_params):
                    continue
                new_listings.append(listing)
                seen_ids.add(lid)

            scraper.close_browser()
            logger.info(f"Yad2: {len(listings)} scraped, {len(new_listings)} new after filter")
        except Exception as e:
            logger.error(f"Yad2 scraper error: {e}")

    if sources_config.get('facebook', {}).get('enabled', False):
        logger.info("Scraping Facebook...")
        try:
            scraper = FacebookScraper(config)
            listings = scraper.scrape()
            total_scraped += len(listings)
            before = len(new_listings)

            for listing in listings:
                lid = f"{listing.get('source')}:{listing.get('listing_id')}"
                if lid in seen_ids:
                    continue
                if not filter_listing(listing, search_params):
                    continue
                new_listings.append(listing)
                seen_ids.add(lid)

            scraper.close_browser()
            logger.info(f"Facebook: {len(listings)} scraped, {len(new_listings) - before} new after filter")
        except Exception as e:
            logger.error(f"Facebook scraper error: {e}")

    logger.info(f"Total scraped: {total_scraped} | New listings: {len(new_listings)}")

    send_summary(notifier, new_listings, total_scraped)

    save_seen_ids(seen_ids)
    commit_seen_ids()

    logger.info("=== Scan complete ===")
    return len(new_listings), total_scraped


if __name__ == "__main__":
    main()

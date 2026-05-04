"""
Automated scheduler — runs scraping twice daily at 10:00 AM and 6:00 PM
Israel time and sends an aggregated Telegram notification.

Uses ScrapingManager so the logic stays in one place.
"""
import logging
import os
import sys

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from utils import setup_logging

logger = logging.getLogger(__name__)

ISRAEL_TZ = pytz.timezone('Asia/Jerusalem')


def run_scraping_job():
    """Called by APScheduler at each scheduled time."""
    logger.info("=" * 60)
    logger.info("Scheduled scrape starting")
    logger.info("=" * 60)

    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        config = ConfigManager(config_path).load_config()

        from scraping_manager import ScrapingManager
        manager = ScrapingManager(config)
        result = manager.run()

        if result.new_listings:
            manager.notifier.send_message(_build_summary(result))

        logger.info(
            f"Scheduled scrape done — "
            f"{result.total_scraped} scraped | "
            f"{len(result.new_listings)} new | "
            f"{len(result.errors)} error(s)"
        )

    except Exception as e:
        logger.error(f"Scheduled scrape failed: {e}", exc_info=True)


def _build_summary(result) -> str:
    from datetime import datetime
    lines = [
        f"🏠 *{len(result.new_listings)} new apartment(s)*",
        f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"📊 Scanned: {result.total_scraped}",
        "━━━━━━━━━━━━━━━━━━━━━\n",
    ]
    for i, lst in enumerate(result.new_listings[:10], 1):
        lines.append(f"*{i}. {(lst.get('title') or 'Apartment')[:50]}*")
        if lst.get('location'):
            lines.append(f"📍 {lst['location']}")
        if lst.get('price'):
            lines.append(f"💰 ₪{lst['price']:,}")
        if lst.get('rooms'):
            lines.append(f"🛏 {lst['rooms']} rooms")
        if lst.get('url'):
            lines.append(f"🔗 [View]({lst['url']})")
        lines.append(f"_Source: {lst.get('source', '?')}_\n")

    if len(result.new_listings) > 10:
        lines.append(f"_+ {len(result.new_listings) - 10} more in database_")

    return '\n'.join(lines)


def main():
    setup_logging()

    logger.info("=" * 60)
    logger.info("Rental Agent Scheduler starting")
    logger.info(f"Timezone : {ISRAEL_TZ}")
    logger.info("Schedule : 10:00 AM and 6:00 PM daily")
    logger.info("=" * 60)

    scheduler = BlockingScheduler(timezone=ISRAEL_TZ)

    scheduler.add_job(
        run_scraping_job,
        CronTrigger(hour=10, minute=0, timezone=ISRAEL_TZ),
        id='morning_scrape',
        name='Morning Scrape (10:00)',
        replace_existing=True,
    )
    scheduler.add_job(
        run_scraping_job,
        CronTrigger(hour=18, minute=0, timezone=ISRAEL_TZ),
        id='evening_scrape',
        name='Evening Scrape (18:00)',
        replace_existing=True,
    )

    for job in scheduler.get_jobs():
        logger.info(f"  {job.name} — next run: {job.next_run_time}")

    logger.info("Scheduler running. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")
        scheduler.shutdown()


if __name__ == "__main__":
    main()

"""
CLI entry-point — runs a one-shot scrape and prints a summary.
For scheduled runs use scheduler.py; for interactive use run bot_listener.py.

Usage:
  python src/main.py                          # uses config.yaml
  python src/main.py --config config.routine.yaml   # Routine / CI mode
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from utils import setup_logging

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Rental Agent — one-shot scrape")
    parser.add_argument('--config', default=None, help="Path to config YAML (default: config.yaml next to repo root)")
    args = parser.parse_args()

    setup_logging()
    logger.info("=== Rental Agent — manual run ===")

    if args.config:
        config_path = os.path.abspath(args.config)
    else:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
    config = ConfigManager(config_path).load_config()

    from scraping_manager import ScrapingManager
    manager = ScrapingManager(config)
    result = manager.run(progress_callback=lambda msg: print(msg))

    print("\n" + "=" * 50)
    print(f"Total scraped : {result.total_scraped}")
    print(f"New listings  : {len(result.new_listings)}")
    print(f"Errors        : {len(result.errors)}")
    if result.errors:
        for err in result.errors:
            print(f"  ✗ {err}")
    print(f"DB total      : {manager.db.get_listing_count()}")
    print("=" * 50)


if __name__ == "__main__":
    main()

"""
One-shot daily scan entrypoint — called by the 14:00 Jerusalem-time schedule.
Runs the scrape job once and exits. Use scheduler.py for a persistent process.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from scheduler import run_scraping_job
from utils import setup_logging
import logging

if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("=== Daily Rental Scan (14:00 Jerusalem time) ===")
    run_scraping_job()
    logger.info("=== Scan complete ===")

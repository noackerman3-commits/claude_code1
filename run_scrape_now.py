"""
Run a scraping job immediately (for testing).
"""
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Fix encoding for Windows
if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except:
        pass

from scheduler import run_scraping_job
from utils import setup_logging

if __name__ == "__main__":
    print("=" * 60)
    print("Running scraping job NOW (test mode)")
    print("=" * 60)
    print()

    setup_logging()
    run_scraping_job()

    print()
    print("=" * 60)
    print("Test scrape complete! Check Telegram for results.")
    print("=" * 60)

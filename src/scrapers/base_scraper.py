"""
Base scraper class with shared functionality.
"""
import glob
import logging
import os
import time
import random
from typing import Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class BaseScraper:
    def __init__(self, config: dict):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None

    def _find_chromium_executable(self) -> Optional[str]:
        """Locate a usable Chromium binary from known Playwright cache paths."""
        search_dirs = [
            '/opt/pw-browsers',
            os.path.expanduser('~/.cache/ms-playwright'),
        ]
        for base in search_dirs:
            # Prefer regular chromium over headless-shell for broader compatibility
            for pattern in ['chromium-*/chrome-linux/chrome', 'chromium_headless_shell-*/chrome-linux/headless_shell']:
                matches = sorted(glob.glob(os.path.join(base, pattern)))
                if matches:
                    return matches[-1]  # newest revision
        return None

    def initialize_browser(self):
        """Setup Playwright with persistent context."""
        try:
            self.playwright = sync_playwright().start()

            browser_config = self.config.get('browser', {})
            scraping_config = self.config.get('scraping', {})

            persistent_path = browser_config.get('persistent_context_path', './browser_data')
            # Force headless when no display is available (cloud/CI environments)
            headless = browser_config.get('headless', False)
            if not headless and not os.environ.get('DISPLAY') and os.name != 'nt':
                headless = True
                logger.info("No DISPLAY detected — forcing headless mode")
            user_agent = scraping_config.get('user_agent',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

            # Auto-detect executable if the default Playwright binary is missing
            executable_path = browser_config.get('executable_path') or self._find_chromium_executable()
            if executable_path:
                logger.info(f"Using Chromium binary: {executable_path}")

            launch_kwargs = dict(
                headless=headless,
                user_agent=user_agent,
                viewport={'width': 1920, 'height': 1080},
                locale='he-IL',
                timezone_id='Asia/Jerusalem',
                ignore_https_errors=True,
            )
            if executable_path:
                launch_kwargs['executable_path'] = executable_path

            # Launch browser with persistent context
            self.context = self.playwright.chromium.launch_persistent_context(
                persistent_path,
                **launch_kwargs
            )

            self.page = self.context.new_page()
            logger.info("Browser initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing browser: {e}")
            raise

    def close_browser(self):
        """Close browser and cleanup."""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()

            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    def random_delay(self):
        """Sleep with random duration for anti-detection."""
        scraping_config = self.config.get('scraping', {})
        delay_min = scraping_config.get('delay_min', 2)
        delay_max = scraping_config.get('delay_max', 5)

        delay = random.uniform(delay_min, delay_max)
        time.sleep(delay)

    def scroll_page(self, count: int = 10):
        """Smooth scrolling for loading dynamic content."""
        try:
            for i in range(count):
                # Random scroll distance (500-1500 pixels)
                scroll_distance = random.randint(500, 1500)

                self.page.evaluate(f"""
                    window.scrollBy({{
                        top: {scroll_distance},
                        behavior: 'smooth'
                    }});
                """)

                # Random delay between scrolls
                time.sleep(random.uniform(1, 3))

            logger.info(f"Scrolled page {count} times")
        except Exception as e:
            logger.error(f"Error scrolling page: {e}")

    def extract_price(self, text: str) -> Optional[int]:
        """Extract price from text."""
        from utils import normalize_price
        return normalize_price(text)

    def extract_rooms(self, text: str) -> Optional[float]:
        """Extract room count from text."""
        from utils import normalize_rooms
        return normalize_rooms(text)

    def scrape(self):
        """Override this method in child classes."""
        raise NotImplementedError("Scrape method must be implemented by child class")

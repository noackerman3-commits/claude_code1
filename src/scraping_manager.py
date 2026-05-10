"""
Central orchestrator: runs all Yad2 searches and Facebook groups,
filters results, deduplicates, and saves to the database.

Key design decisions:
- One browser instance per source type (not one per search/group) —
  avoids the overhead of launching Playwright 50+ times.
- Synchronous Playwright is kept synchronous; callers that need async
  (e.g. bot_listener) run this in a ThreadPoolExecutor.
- progress_callback(msg) is optional; the scheduler omits it while the
  bot passes a function that edits a Telegram status message.
"""
import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScrapingResult:
    total_scraped: int = 0
    new_listings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    source_stats: dict = field(default_factory=dict)  # name -> {scraped, new}


class ScrapingManager:
    def __init__(self, config: dict):
        from database import Database
        from notifier import TelegramNotifier
        from filter_engine import FilterEngine

        self.config = config

        db_path = config.get('database', {}).get('path', './data/listings.db')
        if not os.path.isabs(db_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, db_path)

        self.db = Database(db_path)
        self.db.init_db()

        telegram = config.get('telegram', {})
        self.notifier = TelegramNotifier(telegram['bot_token'], telegram['chat_id'])

        self.filter = FilterEngine(config.get('search_parameters', {}))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, progress_callback: Optional[Callable[[str], None]] = None,
            sources: Optional[str] = None) -> ScrapingResult:
        """
        Run configured scrapers.

        sources: None → run everything
                 'yad2'     → Yad2 only  (on-demand via Telegram)
                 'facebook' → Facebook only  (scheduled)
        """
        result = ScrapingResult()
        cfg_sources = self.config.get('sources', {})

        def progress(msg: str):
            logger.info(msg)
            if progress_callback:
                try:
                    progress_callback(msg)
                except Exception as e:
                    logger.debug(f"progress_callback error: {e}")

        run_yad2 = sources in (None, 'yad2')
        run_fb   = sources in (None, 'facebook')

        # --- Yad2 ---
        yad2_cfg = cfg_sources.get('yad2', {})
        if run_yad2 and yad2_cfg.get('enabled', True):
            searches = yad2_cfg.get('searches', [])
            if not searches:
                base_url = yad2_cfg.get('base_url', 'https://www.yad2.co.il/realestate/rent')
                searches = [{'name': 'Yad2 Default', 'url': base_url}]
            progress(f"🏠 Yad2: {len(searches)} search(es) queued")
            self._run_yad2(searches, result, progress)

        # --- Facebook ---
        fb_cfg = cfg_sources.get('facebook', {})
        if run_fb and fb_cfg.get('enabled', True):
            groups = fb_cfg.get('groups', [])
            progress(f"📘 Facebook: {len(groups)} group(s) queued")
            self._run_facebook(groups, result, progress)

        progress(
            f"✅ Done — {result.total_scraped} scraped | "
            f"{len(result.new_listings)} new | "
            f"{len(result.errors)} error(s)"
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_yad2(self, searches: list, result: ScrapingResult, progress: Callable):
        from scrapers.yad2_scraper import Yad2Scraper

        enrich = self.config.get('scraping', {}).get('enrich_details', False)
        scraper = Yad2Scraper(self.config)
        try:
            scraper.initialize_browser()
            total = len(searches)
            for i, search_cfg in enumerate(searches, 1):
                name = search_cfg.get('name', f'Search {i}')
                progress(f"  Yad2 [{i}/{total}] {name}")
                try:
                    listings = scraper.scrape_one(search_cfg)
                    if enrich:
                        self._enrich_new_yad2(scraper, listings, progress)
                    new_n = self._process(listings, result)
                    result.source_stats[name] = {'scraped': len(listings), 'new': new_n}
                    result.total_scraped += len(listings)
                    logger.info(f"  Yad2 '{name}': {len(listings)} scraped, {new_n} new")
                except Exception as e:
                    err = f"Yad2 '{name}': {e}"
                    logger.error(err, exc_info=True)
                    result.errors.append(err)
        finally:
            scraper.close_browser()

    def _enrich_new_yad2(self, scraper, listings: list, progress: Callable):
        """Visit detail page for each listing that is new and passes the filter."""
        candidates = [
            lst for lst in listings
            if self.filter.matches(lst)[0]
            and not self.db.listing_exists(lst['listing_id'], lst['source'])
        ]
        if not candidates:
            return
        progress(f"  🔍 Enriching {len(candidates)} new listing(s)…")
        for lst in candidates:
            scraper.enrich_from_detail_page(lst)

    def _run_facebook(self, groups: list, result: ScrapingResult, progress: Callable):
        from scrapers.facebook_scraper import FacebookScraper

        scraper = FacebookScraper(self.config)
        try:
            scraper.initialize_browser()
            total = len(groups)
            for i, group in enumerate(groups, 1):
                name = group.get('name', f'Group {i}')
                url = group.get('url', '')
                progress(f"  FB [{i}/{total}] {name}")
                try:
                    listings = scraper.scrape_group(url, name)
                    new_n = self._process(listings, result)
                    result.source_stats[name] = {'scraped': len(listings), 'new': new_n}
                    result.total_scraped += len(listings)
                    logger.info(f"  FB '{name}': {len(listings)} scraped, {new_n} new")
                except Exception as e:
                    err = f"Facebook '{name}': {e}"
                    logger.error(err, exc_info=True)
                    result.errors.append(err)
        finally:
            scraper.close_browser()

    def _process(self, listings: list, result: ScrapingResult) -> int:
        """Filter, deduplicate, and save listings. Returns count of new ones."""
        new_count = 0
        for listing in listings:
            passes, reason = self.filter.matches(listing)
            if not passes:
                logger.debug(f"Filtered {listing.get('listing_id')}: {reason}")
                continue
            if self.db.listing_exists(listing['listing_id'], listing['source']):
                continue
            self.db.add_listing(listing)
            result.new_listings.append(listing)
            new_count += 1
        return new_count

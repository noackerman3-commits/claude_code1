"""
Telegram bot — interactive control panel for the Rental Agent.

Key design:
- ScrapingManager (Playwright, synchronous) runs in a ThreadPoolExecutor
  so it never blocks the asyncio event loop.
- A live "status" message is edited in-place during the scan so the user
  sees progress without being spammed.
- /parameter changes are written to config.yaml and picked up on the
  next /find_homes call (ScrapingManager is created fresh each time).
"""
import asyncio
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from database import Database
from utils import setup_logging

logger = logging.getLogger(__name__)


class ListingBot:
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load_config()

        telegram_cfg = self.config.get('telegram', {})
        self.bot_token = telegram_cfg['bot_token']
        self.allowed_chat_id = str(telegram_cfg['chat_id'])

        db_path = self.config.get('database', {}).get('path', './data/listings.db')
        if not os.path.isabs(db_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, db_path)
        self.db = Database(db_path)
        self.db.init_db()

        # Single-slot executor: only one scraping job at a time
        self._executor = ThreadPoolExecutor(max_workers=1)

    # ------------------------------------------------------------------
    # Auth helper
    # ------------------------------------------------------------------

    def _is_authorized(self, update: Update) -> bool:
        return str(update.effective_chat.id) == self.allowed_chat_id

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🏠 *Rental Agent Bot*\n\n"
            "Commands:\n"
            "/find\\_homes — scan all sources NOW\n"
            "/stats — database statistics\n"
            "/parameter — view or change search settings\n"
            "/help — usage guide",
            parse_mode='Markdown',
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📖 *Help*\n\n"
            "*Search settings:*\n"
            "`/parameter view`\n"
            "`/parameter price 3000-7000`\n"
            "`/parameter rooms 2`\n"
            "`/parameter location Tel Aviv`\n"
            "`/parameter must מעלית`\n"
            "`/parameter exclude שותפים`\n\n"
            "*Manual listing:*\n"
            "Send any Yad2 or Facebook URL directly — I'll save it.\n\n"
            "*Start a scan:*\n"
            "`/find_homes`",
            parse_mode='Markdown',
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return
        count = self.db.get_listing_count()
        sources_cfg = self.config.get('sources', {})
        yad2_searches = len(sources_cfg.get('yad2', {}).get('searches', []))
        fb_groups = len(sources_cfg.get('facebook', {}).get('groups', []))
        await update.message.reply_text(
            f"📊 *Statistics*\n\n"
            f"Listings in DB: *{count}*\n"
            f"Yad2 searches configured: *{yad2_searches}*\n"
            f"Facebook groups configured: *{fb_groups}*",
            parse_mode='Markdown',
        )

    async def find_homes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return

        # Reload config so /parameter changes are picked up
        self.config = self.config_manager.load_config()

        sources = self.config.get('sources', {})
        n_yad2 = len(sources.get('yad2', {}).get('searches', []))
        n_fb = len(sources.get('facebook', {}).get('groups', []))

        status_msg = await update.message.reply_text(
            f"🔍 Starting scan…\n"
            f"Yad2: {n_yad2} searches | Facebook: {n_fb} groups",
        )

        loop = asyncio.get_event_loop()
        progress_lines: list[str] = []

        async def edit_status(line: str):
            progress_lines.append(line)
            # Keep only the last 12 lines so the message stays readable
            snippet = '\n'.join(progress_lines[-12:])
            try:
                await status_msg.edit_text(snippet)
            except Exception:
                pass

        def sync_progress(msg: str):
            asyncio.run_coroutine_threadsafe(edit_status(msg), loop)

        config_snapshot = self.config  # capture before running in thread

        def run_scraping():
            from scraping_manager import ScrapingManager
            manager = ScrapingManager(config_snapshot)
            return manager.run(progress_callback=sync_progress)

        try:
            result = await loop.run_in_executor(self._executor, run_scraping)
        except Exception as e:
            logger.error(f"/find_homes error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Scan failed:\n{e}")
            return

        await self._send_results(update, result)

    # ------------------------------------------------------------------
    # /parameter
    # ------------------------------------------------------------------

    async def parameter_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return

        args = context.args or []

        if not args or args[0].lower() == 'view':
            await self._send_current_settings(update)
            return

        cmd = args[0].lower()
        rest = args[1:]

        if cmd == 'price':
            await self._set_price(update, rest)
        elif cmd == 'rooms':
            await self._set_rooms(update, rest)
        elif cmd == 'location':
            await self._add_location(update, rest)
        elif cmd == 'must':
            await self._add_must(update, rest)
        elif cmd == 'exclude':
            await self._add_exclude(update, rest)
        else:
            await update.message.reply_text(
                "❌ Unknown parameter.\n\n"
                "Options: `view`, `price`, `rooms`, `location`, `must`, `exclude`",
                parse_mode='Markdown',
            )

    async def _send_current_settings(self, update: Update):
        sp = self.config.get('search_parameters', {})
        pr = sp.get('price_range', {})
        await update.message.reply_text(
            "⚙️ *Current Settings*\n\n"
            f"💰 Price: ₪{pr.get('min', 0):,} – ₪{pr.get('max', 0):,}\n"
            f"🛏 Min rooms: {sp.get('min_rooms', 'not set')}\n"
            f"📍 Locations: {', '.join(sp.get('locations', [])) or 'any'}\n"
            f"✅ Must have: {', '.join(sp.get('must_have_keywords', [])) or 'none'}\n"
            f"🚫 Exclude: {', '.join(sp.get('exclude_keywords', [])) or 'none'}",
            parse_mode='Markdown',
        )

    async def _set_price(self, update: Update, args: list):
        if not args or '-' not in args[0]:
            await update.message.reply_text("Usage: `/parameter price 3000-7000`", parse_mode='Markdown')
            return
        try:
            lo, hi = args[0].split('-')
            self.config['search_parameters']['price_range'] = {
                'min': int(lo), 'max': int(hi)
            }
            self.config_manager.save_config(self.config)
            await update.message.reply_text(f"✅ Price set to ₪{int(lo):,} – ₪{int(hi):,}")
        except Exception:
            await update.message.reply_text("❌ Format: `/parameter price 3000-7000`", parse_mode='Markdown')

    async def _set_rooms(self, update: Update, args: list):
        if not args:
            await update.message.reply_text("Usage: `/parameter rooms 2`", parse_mode='Markdown')
            return
        try:
            rooms = float(args[0])
            self.config['search_parameters']['min_rooms'] = rooms
            self.config_manager.save_config(self.config)
            await update.message.reply_text(f"✅ Min rooms set to {rooms}")
        except Exception:
            await update.message.reply_text("❌ Invalid number")

    async def _add_location(self, update: Update, args: list):
        if not args:
            await update.message.reply_text("Usage: `/parameter location Tel Aviv`", parse_mode='Markdown')
            return
        loc = ' '.join(args)
        locs: list = self.config['search_parameters'].setdefault('locations', [])
        if loc not in locs:
            locs.append(loc)
            self.config_manager.save_config(self.config)
            await update.message.reply_text(f"✅ Added location: {loc}\nAll: {', '.join(locs)}")
        else:
            await update.message.reply_text(f"ℹ️ '{loc}' already in list")

    async def _add_must(self, update: Update, args: list):
        if not args:
            await update.message.reply_text("Usage: `/parameter must מעלית`", parse_mode='Markdown')
            return
        kw = ' '.join(args)
        kws: list = self.config['search_parameters'].setdefault('must_have_keywords', [])
        if kw not in kws:
            kws.append(kw)
            self.config_manager.save_config(self.config)
            await update.message.reply_text(f"✅ Must-have added: {kw}")
        else:
            await update.message.reply_text(f"ℹ️ '{kw}' already required")

    async def _add_exclude(self, update: Update, args: list):
        if not args:
            await update.message.reply_text("Usage: `/parameter exclude שותפים`", parse_mode='Markdown')
            return
        kw = ' '.join(args)
        kws: list = self.config['search_parameters'].setdefault('exclude_keywords', [])
        if kw not in kws:
            kws.append(kw)
            self.config_manager.save_config(self.config)
            await update.message.reply_text(f"✅ Exclude added: {kw}")
        else:
            await update.message.reply_text(f"ℹ️ '{kw}' already excluded")

    # ------------------------------------------------------------------
    # Manual URL handling
    # ------------------------------------------------------------------

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return

        text = update.message.text or ''
        urls = re.findall(r'https?://[^\s]+', text)

        if not urls:
            await update.message.reply_text(
                "❌ No URL found.\n\nSend a Yad2 or Facebook listing URL."
            )
            return

        for url in urls:
            await self._save_manual_url(update, url, text)

    async def _save_manual_url(self, update: Update, url: str, full_text: str):
        try:
            if 'yad2.co.il' in url:
                source = 'yad2'
                match = re.search(r'/item/([^/?]+)', url)
                listing_id = f"yad2_{match.group(1)}" if match else f"yad2_{hash(url) % 1_000_000}"
            elif 'facebook.com' in url:
                source = 'facebook_manual'
                match = re.search(r'/(posts|permalink)/(\d+)', url)
                listing_id = f"fb_{match.group(2)}" if match else f"fb_{hash(url) % 1_000_000}"
            else:
                source = 'manual'
                listing_id = f"manual_{hash(url) % 1_000_000}"

            if self.db.listing_exists(listing_id, source):
                await update.message.reply_text(f"ℹ️ Already saved — ID: `{listing_id}`", parse_mode='Markdown')
                return

            from utils import extract_price_from_text, extract_rooms_from_text
            listing = {
                'listing_id': listing_id,
                'source': source,
                'url': url,
                'title': f"Manual listing ({source})",
                'price': extract_price_from_text(full_text),
                'rooms': extract_rooms_from_text(full_text),
                'raw_text': full_text,
            }
            self.db.add_listing(listing)

            resp = f"✅ *Saved!*\nSource: `{source}`\nID: `{listing_id}`"
            if listing['price']:
                resp += f"\n💰 ₪{listing['price']:,}"
            if listing['rooms']:
                resp += f"\n🛏 {listing['rooms']} rooms"
            resp += f"\n🔗 [View]({url})"
            await update.message.reply_text(resp, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Manual URL error: {e}")
            await update.message.reply_text(f"❌ Error: {e}")

    # ------------------------------------------------------------------
    # Results formatter (placeholder — will be replaced with professional
    # real-estate format in the next phase)
    # ------------------------------------------------------------------

    async def _send_results(self, update: Update, result):
        if not result.new_listings:
            await update.message.reply_text(
                f"✅ *Scan complete*\n\n"
                f"Scanned {result.total_scraped} listings — no new matches.\n"
                f"Errors: {len(result.errors)}",
                parse_mode='Markdown',
            )
            return

        from datetime import datetime
        header = (
            f"🏠 *{len(result.new_listings)} new apartment(s) found!*\n"
            f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
            f"📊 Scanned: {result.total_scraped}\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        blocks = []
        for i, lst in enumerate(result.new_listings[:10], 1):
            title = (lst.get('title') or 'Apartment')[:50]
            block = f"*{i}. {title}*\n"
            if lst.get('location'):
                block += f"📍 {lst['location']}\n"
            if lst.get('price'):
                block += f"💰 ₪{lst['price']:,}\n"
            if lst.get('rooms'):
                block += f"🛏 {lst['rooms']} rooms\n"
            if lst.get('url'):
                block += f"🔗 [View]({lst['url']})\n"
            block += f"_Source: {lst.get('source', '?')}_\n"
            blocks.append(block)

        body = '\n'.join(blocks)
        if len(result.new_listings) > 10:
            body += f"\n_+ {len(result.new_listings) - 10} more in database_"

        await update.message.reply_text(header + body, parse_mode='Markdown')

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def run(self):
        logger.info("Starting Telegram bot…")
        app = Application.builder().token(self.bot_token).build()

        app.add_handler(CommandHandler("start",       self.start_command))
        app.add_handler(CommandHandler("help",        self.help_command))
        app.add_handler(CommandHandler("find_homes",  self.find_homes_command))
        app.add_handler(CommandHandler("stats",       self.stats_command))
        app.add_handler(CommandHandler("parameter",   self.parameter_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        logger.info("Bot running. Press Ctrl+C to stop.")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    setup_logging()
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
    try:
        bot = ListingBot(config_path)
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Fatal: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

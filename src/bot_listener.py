"""
Telegram bot listener for manual URL submission.
Run this to allow sending URLs directly to your bot.
"""
import sys
import os
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Add src directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from database import Database
from notifier import TelegramNotifier
import logging

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class ListingBot:
    def __init__(self, config_path="config.yaml"):
        # Save config path for later updates
        self.config_path = config_path

        # Load config
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.load_config()

        # Initialize database
        db_path = self.config.get('database', {}).get('path', './data/listings.db')
        if not os.path.isabs(db_path):
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
        self.db = Database(db_path)

        # Get Telegram config
        telegram_config = self.config.get('telegram', {})
        self.bot_token = telegram_config['bot_token']
        self.allowed_chat_id = telegram_config['chat_id']

        # Initialize notifier
        self.notifier = TelegramNotifier(self.bot_token, self.allowed_chat_id)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        await update.message.reply_text(
            "🏠 *Rental Agent Bot*\n\n"
            "I'll help you find apartments!\n\n"
            "Commands:\n"
            "/find_homes - Scan all sources NOW\n"
            "/url - Add URLs manually\n"
            "/parameter - Configure search settings\n"
            "/stats - Show statistics\n"
            "/help - Show help",
            parse_mode='Markdown'
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command."""
        count = self.db.get_listing_count()
        await update.message.reply_text(
            f"📊 *Statistics*\n\n"
            f"Total listings in database: {count}",
            parse_mode='Markdown'
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        await update.message.reply_text(
            "📖 *Help*\n\n"
            "*How to use:*\n"
            "1. Send me a listing URL\n"
            "2. I'll save it and show you the details\n\n"
            "*Supported formats:*\n"
            "• https://www.yad2.co.il/...\n"
            "• https://www.facebook.com/...\n"
            "• Any other URL\n\n"
            "*Manual format:*\n"
            "```\n"
            "URL: https://example.com\n"
            "Price: 4500\n"
            "Rooms: 3\n"
            "Location: Tel Aviv\n"
            "Notes: Nice apartment with balcony\n"
            "```\n\n"
            "*Commands:*\n"
            "/url - Add URLs step-by-step\n"
            "/parameter price 2000-6000 - Set price range\n"
            "/parameter location Tel Aviv - Add location\n"
            "/parameter rooms 2 - Set minimum rooms\n"
            "/parameter view - View current settings",
            parse_mode='Markdown'
        )

    async def url_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /url command for adding URLs."""
        await update.message.reply_text(
            "📎 *Add URL*\n\n"
            "Send me the apartment URL now.\n\n"
            "Example:\n"
            "`https://www.yad2.co.il/item/abc123`\n\n"
            "Or send multiple URLs (one per line):",
            parse_mode='Markdown'
        )

    async def find_homes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /find_homes command - trigger scraping job."""
        # Check if message is from allowed user
        if str(update.effective_chat.id) != self.allowed_chat_id:
            await update.message.reply_text("⛔ Unauthorized")
            return

        await update.message.reply_text(
            "🔍 *Starting apartment search...*\n\n"
            "Scanning:\n"
            "• Yad2\n"
            "• Facebook Groups\n\n"
            "This may take 1-2 minutes...",
            parse_mode='Markdown'
        )

        try:
            # Import scraping modules
            from scrapers.yad2_scraper import Yad2Scraper
            from scrapers.facebook_scraper import FacebookScraper
            from utils import matches_keywords, excludes_keywords

            # Reload config (in case it was updated)
            self.config_manager = ConfigManager(self.config_path)
            self.config = self.config_manager.load_config()

            search_params = self.config.get('search_parameters', {})
            sources_config = self.config.get('sources', {})

            new_listings = []
            total_scraped = 0

            # Scrape Yad2
            if sources_config.get('yad2', {}).get('enabled', True):
                try:
                    yad2_scraper = Yad2Scraper(self.config)
                    yad2_listings = yad2_scraper.scrape()
                    total_scraped += len(yad2_listings)

                    for listing in yad2_listings:
                        if not self._filter_listing(listing, search_params):
                            continue
                        if self.db.listing_exists(listing['listing_id'], listing['source']):
                            continue

                        new_listings.append(listing)
                        self.db.add_listing(listing)

                    yad2_scraper.close_browser()
                except Exception as e:
                    logger.error(f"Yad2 error: {e}")

            # Scrape Facebook
            if sources_config.get('facebook', {}).get('enabled', True):
                try:
                    fb_scraper = FacebookScraper(self.config)
                    fb_listings = fb_scraper.scrape()
                    total_scraped += len(fb_listings)

                    for listing in fb_listings:
                        if not self._filter_listing(listing, search_params):
                            continue
                        if self.db.listing_exists(listing['listing_id'], listing['source']):
                            continue

                        new_listings.append(listing)
                        self.db.add_listing(listing)

                    fb_scraper.close_browser()
                except Exception as e:
                    logger.error(f"Facebook error: {e}")

            # Send aggregated results
            await self._send_aggregated_results(update, new_listings, total_scraped)

        except Exception as e:
            logger.error(f"Error in find_homes: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Error during search:\n{str(e)}\n\nCheck logs for details."
            )

    def _filter_listing(self, listing: dict, search_params: dict) -> bool:
        """Check if listing matches search criteria."""
        from utils import matches_keywords, excludes_keywords

        # Check price range
        price_range = search_params.get('price_range', {})
        if listing.get('price'):
            min_price = price_range.get('min', 0)
            max_price = price_range.get('max', 999999)
            if not (min_price <= listing['price'] <= max_price):
                return False

        # Check minimum rooms
        min_rooms = search_params.get('min_rooms')
        if min_rooms and listing.get('rooms'):
            if listing['rooms'] < min_rooms:
                return False

        # Check location
        locations = search_params.get('locations', [])
        if locations and listing.get('location'):
            location_match = any(
                loc.lower() in listing['location'].lower()
                for loc in locations
            )
            if not location_match:
                return False

        # Check must-have keywords
        must_have = search_params.get('must_have_keywords', [])
        full_text = listing.get('full_text', '') + ' ' + listing.get('title', '')
        if must_have and not matches_keywords(full_text, must_have):
            return False

        # Check exclude keywords
        exclude = search_params.get('exclude_keywords', [])
        if exclude and excludes_keywords(full_text, exclude):
            return False

        return True

    async def _send_aggregated_results(self, update: Update, new_listings: list, total_scraped: int):
        """Send aggregated results message."""
        if not new_listings:
            await update.message.reply_text(
                f"✅ *Scan Complete*\n\n"
                f"Scanned {total_scraped} listings\n"
                f"No new apartments found matching your criteria.\n\n"
                f"All listings already in database.",
                parse_mode='Markdown'
            )
            return

        # Build summary message
        from datetime import datetime
        message = f"🏠 *Found {len(new_listings)} New Apartment{'s' if len(new_listings) > 1 else ''}!*\n"
        message += f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        message += f"📊 Scanned {total_scraped} total listings\n"
        message += "━━━━━━━━━━━━━━━━━━━━━\n\n"

        for i, listing in enumerate(new_listings[:10], 1):
            title = listing.get('title', 'Apartment')
            if len(title) > 50:
                title = title[:47] + "..."

            message += f"*{i}. {title}*\n"

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
            message += f"\n_+ {len(new_listings) - 10} more in database_"

        await update.message.reply_text(message, parse_mode='Markdown')
        logger.info(f"Sent results: {len(new_listings)} new listings")

    async def parameter_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /parameter command for configuration."""
        # Check if message is from allowed user
        if str(update.effective_chat.id) != self.allowed_chat_id:
            await update.message.reply_text("⛔ Unauthorized")
            return

        # Parse arguments
        args = context.args

        if not args or args[0] == 'view':
            # Show current configuration
            search_params = self.config.get('search_parameters', {})
            price_range = search_params.get('price_range', {})
            locations = search_params.get('locations', [])
            min_rooms = search_params.get('min_rooms', 'Not set')
            must_have = search_params.get('must_have_keywords', [])
            exclude = search_params.get('exclude_keywords', [])

            response = "⚙️ *Current Settings*\n\n"
            response += f"*Price Range:* ₪{price_range.get('min', 0):,} - ₪{price_range.get('max', 0):,}\n"
            response += f"*Locations:* {', '.join(locations) if locations else 'None'}\n"
            response += f"*Min Rooms:* {min_rooms}\n"
            response += f"*Must Have:* {', '.join(must_have) if must_have else 'None'}\n"
            response += f"*Exclude:* {', '.join(exclude) if exclude else 'None'}\n\n"
            response += "*Usage:*\n"
            response += "`/parameter price 2000-5000`\n"
            response += "`/parameter location Tel Aviv`\n"
            response += "`/parameter rooms 2`\n"
            response += "`/parameter must elevator`\n"
            response += "`/parameter exclude shared`"

            await update.message.reply_text(response, parse_mode='Markdown')
            return

        param_type = args[0].lower()

        if param_type == 'price':
            # Set price range: /parameter price 2000-5000
            if len(args) < 2:
                await update.message.reply_text("Usage: `/parameter price 2000-5000`", parse_mode='Markdown')
                return

            price_str = args[1]
            if '-' in price_str:
                try:
                    min_price, max_price = price_str.split('-')
                    min_price = int(min_price.strip())
                    max_price = int(max_price.strip())

                    self.config['search_parameters']['price_range'] = {
                        'min': min_price,
                        'max': max_price
                    }
                    self.config_manager.save_config(self.config)

                    await update.message.reply_text(
                        f"✅ Price range updated:\n₪{min_price:,} - ₪{max_price:,}"
                    )
                except:
                    await update.message.reply_text("❌ Invalid format. Use: `/parameter price 2000-5000`", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Use format: `/parameter price 2000-5000`", parse_mode='Markdown')

        elif param_type == 'location':
            # Add location: /parameter location Tel Aviv
            if len(args) < 2:
                await update.message.reply_text("Usage: `/parameter location Tel Aviv`", parse_mode='Markdown')
                return

            location = ' '.join(args[1:])
            locations = self.config['search_parameters'].get('locations', [])

            if location not in locations:
                locations.append(location)
                self.config['search_parameters']['locations'] = locations
                self.config_manager.save_config(self.config)

                await update.message.reply_text(
                    f"✅ Added location: {location}\n\n"
                    f"Current locations: {', '.join(locations)}"
                )
            else:
                await update.message.reply_text(f"ℹ️ Location '{location}' already in list")

        elif param_type == 'rooms':
            # Set minimum rooms: /parameter rooms 2
            if len(args) < 2:
                await update.message.reply_text("Usage: `/parameter rooms 2`", parse_mode='Markdown')
                return

            try:
                min_rooms = float(args[1])
                self.config['search_parameters']['min_rooms'] = min_rooms
                self.config_manager.save_config(self.config)

                await update.message.reply_text(f"✅ Minimum rooms set to: {min_rooms}")
            except:
                await update.message.reply_text("❌ Invalid number")

        elif param_type == 'must':
            # Add must-have keyword: /parameter must elevator
            if len(args) < 2:
                await update.message.reply_text("Usage: `/parameter must elevator`", parse_mode='Markdown')
                return

            keyword = ' '.join(args[1:])
            must_have = self.config['search_parameters'].get('must_have_keywords', [])

            if keyword not in must_have:
                must_have.append(keyword)
                self.config['search_parameters']['must_have_keywords'] = must_have
                self.config_manager.save_config(self.config)

                await update.message.reply_text(
                    f"✅ Added must-have keyword: {keyword}\n\n"
                    f"Must have: {', '.join(must_have)}"
                )
            else:
                await update.message.reply_text(f"ℹ️ Keyword '{keyword}' already in list")

        elif param_type == 'exclude':
            # Add exclude keyword: /parameter exclude shared
            if len(args) < 2:
                await update.message.reply_text("Usage: `/parameter exclude shared`", parse_mode='Markdown')
                return

            keyword = ' '.join(args[1:])
            exclude = self.config['search_parameters'].get('exclude_keywords', [])

            if keyword not in exclude:
                exclude.append(keyword)
                self.config['search_parameters']['exclude_keywords'] = exclude
                self.config_manager.save_config(self.config)

                await update.message.reply_text(
                    f"✅ Added exclude keyword: {keyword}\n\n"
                    f"Excluding: {', '.join(exclude)}"
                )
            else:
                await update.message.reply_text(f"ℹ️ Keyword '{keyword}' already in list")

        else:
            await update.message.reply_text(
                "❌ Unknown parameter type.\n\n"
                "Use: price, location, rooms, must, exclude\n\n"
                "Example: `/parameter price 2000-5000`",
                parse_mode='Markdown'
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages with URLs."""
        # Check if message is from allowed user
        if str(update.effective_chat.id) != self.allowed_chat_id:
            await update.message.reply_text("⛔ Unauthorized")
            return

        text = update.message.text

        # Extract URLs from message
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, text)

        if not urls:
            await update.message.reply_text(
                "❌ No URL found in message.\n\n"
                "Send me a listing URL or use /help for more info."
            )
            return

        # Process each URL
        for url in urls:
            await self.process_url(update, url, text)

    async def process_url(self, update: Update, url: str, full_text: str):
        """Process a single URL."""
        try:
            # Determine source
            if 'yad2.co.il' in url:
                source = 'yad2'
                listing_id = self.extract_yad2_id(url)
            elif 'facebook.com' in url:
                source = 'facebook'
                listing_id = self.extract_fb_id(url)
            else:
                source = 'manual'
                listing_id = f"manual_{hash(url) % 1000000}"

            # Check if already exists
            if self.db.listing_exists(listing_id, source):
                await update.message.reply_text(
                    f"ℹ️ Already saved!\n\n"
                    f"Source: {source}\n"
                    f"ID: {listing_id}"
                )
                return

            # Extract info from text
            price = self.extract_price_from_text(full_text)
            rooms = self.extract_rooms_from_text(full_text)
            location = self.extract_location_from_text(full_text)

            # Create listing
            listing = {
                'listing_id': listing_id,
                'source': source,
                'url': url,
                'title': f"Manual listing from {source}",
                'price': price,
                'rooms': rooms,
                'location': location,
                'full_text': full_text
            }

            # Save to database
            self.db.add_listing(listing)

            # Send confirmation
            response = f"✅ *Listing Saved!*\n\n"
            response += f"🔗 Source: {source}\n"
            if price:
                response += f"💰 Price: ₪{price:,}\n"
            if rooms:
                response += f"🛏 Rooms: {rooms}\n"
            if location:
                response += f"📍 Location: {location}\n"
            response += f"\n[View Listing]({url})"

            await update.message.reply_text(response, parse_mode='Markdown')
            logger.info(f"Saved manual listing: {listing_id}")

        except Exception as e:
            logger.error(f"Error processing URL: {e}")
            await update.message.reply_text(f"❌ Error processing URL: {str(e)}")

    def extract_yad2_id(self, url: str) -> str:
        """Extract Yad2 listing ID from URL."""
        match = re.search(r'/item/([^/?]+)', url)
        if match:
            return f"yad2_{match.group(1)}"
        return f"yad2_{hash(url) % 1000000}"

    def extract_fb_id(self, url: str) -> str:
        """Extract Facebook post ID from URL."""
        match = re.search(r'/(posts|permalink)/(\d+)', url)
        if match:
            return f"fb_{match.group(2)}"
        return f"fb_{hash(url) % 1000000}"

    def extract_price_from_text(self, text: str) -> int:
        """Extract price from text."""
        patterns = [
            r'(?:price|מחיר|Price):\s*(\d+)',
            r'(\d{4,5})\s*₪',
            r'₪\s*(\d{4,5})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except:
                    continue
        return None

    def extract_rooms_from_text(self, text: str) -> float:
        """Extract rooms from text."""
        patterns = [
            r'(?:rooms|חדרים|Rooms):\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*(?:rooms|חדרים)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except:
                    continue
        return None

    def extract_location_from_text(self, text: str) -> str:
        """Extract location from text."""
        patterns = [
            r'(?:location|מיקום|Location):\s*([^\n]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Common cities
        cities = ['תל אביב', 'Tel Aviv', 'רמת גן', 'Ramat Gan', 'גבעתיים', 'Givatayim']
        for city in cities:
            if city.lower() in text.lower():
                return city

        return None

    def run(self):
        """Start the bot."""
        logger.info("Starting Telegram bot listener...")

        # Create application
        app = Application.builder().token(self.bot_token).build()

        # Add handlers
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("find_homes", self.find_homes_command))
        app.add_handler(CommandHandler("url", self.url_command))
        app.add_handler(CommandHandler("parameter", self.parameter_command))
        app.add_handler(CommandHandler("stats", self.stats_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Start bot
        logger.info("Bot is running. Press Ctrl+C to stop.")
        app.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main entry point."""
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        bot = ListingBot(config_path)
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

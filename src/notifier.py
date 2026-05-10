"""
Telegram notification handler for rental listings.
"""
import logging
import requests
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_listing(self, listing: Dict) -> bool:
        """Send listing notification via Telegram."""
        try:
            message = self.format_message(listing)
            image_url = listing.get('image_url')

            if image_url:
                # Try to send with photo
                success = self.send_photo(image_url, message)
                if success:
                    return True

            # Fallback to text-only message
            return self.send_message(message)

        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            return False

    def format_message(self, listing: Dict) -> str:
        """Format listing data as Telegram message."""
        title = listing.get('title', 'New Apartment')
        location = listing.get('location', 'N/A')
        price = listing.get('price')
        rooms = listing.get('rooms')
        url = listing.get('url', '')
        source = listing.get('source', 'Unknown')

        # Build message with Markdown formatting
        message_parts = ["🏠 *New Apartment Found!*\n"]

        if location and location != 'N/A':
            message_parts.append(f"📍 Location: {location}")

        if price:
            message_parts.append(f"💰 Price: ₪{price:,}")

        if rooms:
            message_parts.append(f"🛏 Rooms: {rooms}")

        if url:
            message_parts.append(f"🔗 [View Listing]({url})")

        message_parts.append(f"\n_Source: {source}_")

        # Add excerpt from title/description if available
        if title and len(title) > 10:
            excerpt = title[:200] + "..." if len(title) > 200 else title
            message_parts.append(f"\n📝 {excerpt}")

        return "\n".join(message_parts)

    def send_photo(self, photo_url: str, caption: str) -> bool:
        """Send message with photo."""
        try:
            url = f"{self.base_url}/sendPhoto"
            data = {
                'chat_id': self.chat_id,
                'photo': photo_url,
                'caption': caption,
                'parse_mode': 'Markdown'
            }

            response = requests.post(url, data=data, timeout=10)

            if response.status_code == 200:
                logger.info("Photo message sent successfully")
                return True
            else:
                logger.warning(f"Failed to send photo: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending photo: {e}")
            return False

    def send_message(self, text: str) -> bool:
        """Send text-only message."""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': False
            }

            response = requests.post(url, data=data, timeout=10)

            if response.status_code == 200:
                logger.info("Message sent successfully")
                return True
            else:
                logger.error(f"Failed to send message: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    def send_scan_summary(self, new_listings: list, total_scraped: int, total_in_db: int) -> bool:
        """Send daily scan summary regardless of whether new listings were found."""
        from datetime import datetime
        timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')

        if new_listings:
            header = f"🏠 *New Apartments Found: {len(new_listings)}*\n"
            header += f"⏰ Daily scan — {timestamp}\n"
            header += "━━━━━━━━━━━━━━━━━━━━━\n\n"

            for i, listing in enumerate(new_listings[:10], 1):
                header += f"*{i}. {listing.get('title', 'Apartment')[:50]}*\n"
                if listing.get('location'):
                    header += f"📍 {listing['location']}\n"
                if listing.get('price'):
                    header += f"💰 ₪{listing['price']:,}\n"
                if listing.get('rooms'):
                    header += f"🛏 {listing['rooms']} rooms\n"
                if listing.get('url'):
                    header += f"🔗 [View Listing]({listing['url']})\n"
                header += f"_Source: {listing.get('source', 'Unknown')}_\n\n"

            if len(new_listings) > 10:
                header += f"_+ {len(new_listings) - 10} more listings saved to database_\n\n"

            header += f"📊 Scanned: {total_scraped} | New: {len(new_listings)} | Total saved: {total_in_db}"
            return self.send_message(header)
        else:
            message = (
                f"✅ *Daily Scan Complete*\n"
                f"⏰ {timestamp}\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"No new listings found today.\n\n"
                f"📊 Scanned: {total_scraped} | Total saved: {total_in_db}"
            )
            return self.send_message(message)

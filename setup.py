"""
Setup script for first-time initialization of the rental agent.
"""
import sys
import os
import subprocess
import yaml

# Fix encoding for Windows console
if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except:
        pass

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config_manager import ConfigManager
from database import Database


def check_python_version():
    """Check if Python version is 3.8+."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ required. Current version: {version.major}.{version.minor}")
        return False
    print(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
    return True


def install_dependencies():
    """Install required Python packages."""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False


def install_playwright_browsers():
    """Install Playwright browsers."""
    print("\n🌐 Installing Playwright browsers...")
    try:
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        print("✅ Playwright browsers installed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install Playwright browsers")
        return False


def create_directories():
    """Create necessary directories."""
    print("\n📁 Creating directories...")
    dirs = ['data', 'logs', 'browser_data']
    for dir_name in dirs:
        os.makedirs(dir_name, exist_ok=True)
        print(f"  ✅ Created {dir_name}/")
    return True


def initialize_database():
    """Initialize SQLite database."""
    print("\n💾 Initializing database...")
    try:
        db = Database("./data/listings.db")
        db.init_db()
        print("✅ Database initialized")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize database: {e}")
        return False


def configure_telegram():
    """Prompt user for Telegram configuration."""
    print("\n📱 Telegram Configuration")
    print("=" * 50)
    print("\nTo get your Telegram bot token:")
    print("1. Open Telegram and search for @BotFather")
    print("2. Send /newbot and follow the instructions")
    print("3. Copy the bot token you receive")
    print("\nTo get your chat ID:")
    print("1. Search for @userinfobot in Telegram")
    print("2. Send /start to the bot")
    print("3. Copy the ID number it shows")
    print("=" * 50)

    bot_token = input("\n🤖 Enter your Telegram bot token: ").strip()
    chat_id = input("💬 Enter your Telegram chat ID: ").strip()

    if not bot_token or not chat_id:
        print("❌ Bot token and chat ID are required")
        return None, None

    return bot_token, chat_id


def configure_search_parameters():
    """Prompt user for search parameters."""
    print("\n🔍 Search Parameters Configuration")
    print("=" * 50)

    try:
        min_price = int(input("💰 Minimum price (₪): ").strip() or "2000")
        max_price = int(input("💰 Maximum price (₪): ").strip() or "5000")
        min_rooms = float(input("🛏 Minimum rooms: ").strip() or "2")

        print("\n📍 Enter locations (comma-separated, e.g., 'Tel Aviv, Ramat Gan'):")
        locations_input = input("Locations: ").strip() or "Tel Aviv, Ramat Gan"
        locations = [loc.strip() for loc in locations_input.split(',')]

        return {
            'price_range': {'min': min_price, 'max': max_price},
            'min_rooms': min_rooms,
            'locations': locations,
            'must_have_keywords': [],
            'exclude_keywords': []
        }
    except ValueError:
        print("❌ Invalid input, using defaults")
        return None


def update_config(bot_token, chat_id, search_params):
    """Update config.yaml with user inputs."""
    print("\n⚙️ Updating configuration...")
    try:
        config_manager = ConfigManager("config.yaml")
        config = config_manager.load_config()

        # Update Telegram config
        config['telegram']['bot_token'] = bot_token
        config['telegram']['chat_id'] = chat_id

        # Update search parameters if provided
        if search_params:
            config['search_parameters'] = search_params

        config_manager.save_config(config)
        print("✅ Configuration updated")
        return True
    except Exception as e:
        print(f"❌ Failed to update configuration: {e}")
        return False


def configure_facebook_groups():
    """Prompt user for Facebook groups."""
    print("\n📘 Facebook Groups Configuration")
    print("=" * 50)
    print("You can add Facebook groups later by editing config.yaml")
    print("Example group URL: https://www.facebook.com/groups/SecretTLV")

    add_groups = input("\nDo you want to add Facebook groups now? (y/n): ").strip().lower()

    if add_groups != 'y':
        return None

    groups = []
    while True:
        group_name = input("\nGroup name (or press Enter to finish): ").strip()
        if not group_name:
            break

        group_url = input("Group URL: ").strip()
        if not group_url:
            break

        groups.append({'name': group_name, 'url': group_url})
        print(f"✅ Added {group_name}")

    return groups


def launch_browser_for_login():
    """Launch browser for manual login."""
    print("\n🌐 Browser Login Setup")
    print("=" * 50)
    print("A browser will open for you to log into Facebook and Yad2.")
    print("After logging in, close the browser window.")
    print("Your login session will be saved for future runs.")
    print("=" * 50)

    proceed = input("\nReady to open browser? (y/n): ").strip().lower()
    if proceed != 'y':
        print("⏭️ Skipping browser login (you can do this later)")
        return False

    try:
        from playwright.sync_api import sync_playwright

        print("\n🌐 Opening browser...")
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                "./browser_data",
                headless=False,
                viewport={'width': 1920, 'height': 1080}
            )

            page = context.new_page()

            # Open Facebook
            print("\n📘 Opening Facebook...")
            page.goto("https://www.facebook.com")
            input("\nPress Enter after you've logged into Facebook...")

            # Open Yad2
            print("\n🏠 Opening Yad2...")
            page.goto("https://www.yad2.co.il")
            input("\nPress Enter after you've logged into Yad2 (if needed)...")

            context.close()

        print("✅ Browser session saved")
        return True
    except Exception as e:
        print(f"❌ Error launching browser: {e}")
        return False


def main():
    """Main setup flow."""
    print("=" * 50)
    print("🏠 Rental Agent Setup")
    print("=" * 50)

    # Check Python version
    if not check_python_version():
        return

    # Install dependencies
    if not install_dependencies():
        print("\n⚠️ Failed to install dependencies. Please run manually:")
        print("  pip install -r requirements.txt")
        return

    # Install Playwright browsers
    if not install_playwright_browsers():
        print("\n⚠️ Failed to install Playwright. Please run manually:")
        print("  playwright install chromium")
        return

    # Create directories
    create_directories()

    # Initialize database
    if not initialize_database():
        return

    # Configure Telegram
    bot_token, chat_id = configure_telegram()
    if not bot_token:
        print("\n⚠️ Setup incomplete. Please edit config.yaml manually.")
        return

    # Configure search parameters
    search_params = configure_search_parameters()

    # Configure Facebook groups
    facebook_groups = configure_facebook_groups()

    # Update configuration
    if not update_config(bot_token, chat_id, search_params):
        return

    # Update Facebook groups if provided
    if facebook_groups:
        try:
            config_manager = ConfigManager("config.yaml")
            config = config_manager.load_config()
            config['sources']['facebook']['groups'] = facebook_groups
            config_manager.save_config(config)
            print("✅ Facebook groups updated")
        except Exception as e:
            print(f"⚠️ Failed to update Facebook groups: {e}")

    # Launch browser for login
    launch_browser_for_login()

    print("\n" + "=" * 50)
    print("✅ Setup Complete!")
    print("=" * 50)
    print("\nNext steps:")
    print("1. Review config.yaml and adjust settings if needed")
    print("2. Run the scraper manually to test:")
    print("   python src/main.py")
    print("3. Set up Windows Task Scheduler for automated runs:")
    print("   - See README.md for instructions")
    print("=" * 50)


if __name__ == "__main__":
    main()

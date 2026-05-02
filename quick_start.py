"""
Quick start script - non-interactive setup.
"""
import sys
import os

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

from database import Database


def main():
    print("=" * 60)
    print("Rental Agent - Quick Start")
    print("=" * 60)

    # Create directories
    print("\n[1/2] Creating directories...")
    dirs = ['data', 'logs', 'browser_data']
    for dir_name in dirs:
        os.makedirs(dir_name, exist_ok=True)
        print(f"  OK: {dir_name}/")

    # Initialize database
    print("\n[2/2] Initializing database...")
    try:
        db = Database("./data/listings.db")
        db.init_db()
        print("  OK: Database initialized")
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)

    print("\n**IMPORTANT: Configure Telegram Before Running**\n")
    print("Edit config.yaml and replace:")
    print("  1. YOUR_BOT_TOKEN - Get from @BotFather on Telegram")
    print("  2. YOUR_CHAT_ID - Get from @userinfobot on Telegram")

    print("\nHow to get Telegram credentials:")
    print("-" * 60)
    print("1. Bot Token:")
    print("   - Open Telegram, search for @BotFather")
    print("   - Send /newbot and follow instructions")
    print("   - Copy the token")
    print("")
    print("2. Chat ID:")
    print("   - Search for @userinfobot on Telegram")
    print("   - Send /start")
    print("   - Copy your ID number")
    print("-" * 60)

    print("\nNext Steps:")
    print("1. Edit config.yaml with your Telegram credentials")
    print("2. Adjust search parameters in config.yaml (price, location, etc.)")
    print("3. Run: python src\\main.py")
    print("   - A browser will open for Facebook/Yad2 login")
    print("   - Log in and close the browser")
    print("   - Your session will be saved")
    print("4. Run again to scrape: python src\\main.py")
    print("5. Check logs\\ folder for activity")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

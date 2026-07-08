# Rental Real Estate Agent

Autonomous apartment search agent that scrapes Yad2 and Facebook Groups, filters results, and sends Telegram notifications.

## Features

- 🏠 Scrapes Yad2 rental listings
- 📘 Scrapes Facebook group posts for rentals
- 🔍 Advanced filtering (price, rooms, location, keywords)
- 💾 SQLite database for deduplication
- 📱 Telegram notifications with photos
- 🤖 Automated scheduling with Windows Task Scheduler
- 🔐 Persistent browser sessions (no re-login needed)

## Requirements

- Python 3.8+
- Windows 10/11
- Telegram account

## Installation

### 1. Quick Setup

Run the interactive setup script:

```bash
python setup.py
```

This will:
- Install dependencies
- Initialize database
- Configure Telegram
- Set up browser sessions
- Guide you through all settings

### 2. Manual Setup

If you prefer manual setup:

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Create directories
mkdir data logs browser_data

# Edit config.yaml with your settings
```

## Configuration

Edit `config.yaml` to customize your search:

### Search Parameters

```yaml
search_parameters:
  price_range:
    min: 2000        # Minimum price in ₪
    max: 5000        # Maximum price in ₪
  locations:
    - "Tel Aviv"
    - "Ramat Gan"
  min_rooms: 2
  must_have_keywords:
    - "מעלית"        # Elevator
    - "מרפסת"        # Balcony
  exclude_keywords:
    - "דירת חלוקה"   # Shared apartment
```

### Telegram Setup

1. **Create a Telegram Bot:**
   - Open Telegram and search for `@BotFather`
   - Send `/newbot` and follow instructions
   - Copy the bot token

2. **Get Your Chat ID:**
   - Search for `@userinfobot` in Telegram
   - Send `/start`
   - Copy your chat ID

3. **Update config.yaml:**
   ```yaml
   telegram:
     bot_token: "YOUR_BOT_TOKEN"
     chat_id: "YOUR_CHAT_ID"
   ```

### Facebook Groups

Add groups to `config.yaml`:

```yaml
sources:
  facebook:
    enabled: true
    groups:
      - name: "SecretTLV"
        url: "https://www.facebook.com/groups/SecretTLV"
      - name: "דירות להשכרה תל אביב"
        url: "https://www.facebook.com/groups/GROUP_ID"
```

## Usage

### Manual Run

Test the scraper manually:

```bash
python src/main.py
```

### Automated Scheduling

#### Windows Task Scheduler Setup

1. **Open Task Scheduler:**
   - Press `Win + R`
   - Type `taskschd.msc`
   - Press Enter

2. **Create New Task:**
   - Click "Create Task" (not "Create Basic Task")
   - Name: `Rental Agent`
   - Description: `Scrape rental listings`

3. **Triggers Tab:**
   - Click "New..."
   - Set daily at 14:00

4. **Actions Tab:**
   - Click "New..."
   - Action: `Start a program`
   - Program: `python.exe` (or full path like `C:\Python310\python.exe`)
   - Arguments: `src\main.py`
   - Start in: `C:\Users\itayg\Desktop\rental-agent`

5. **Conditions Tab:**
   - Check "Wake the computer to run this task"

6. **Settings Tab:**
   - Check "Run task as soon as possible after a scheduled start is missed"
   - Uncheck "Stop the task if it runs longer than"

7. **Click OK** and enter your Windows password if prompted

#### Test the Scheduled Task

Right-click the task and select "Run" to test it works correctly.

## First-Time Login

The first time you run the scraper:

1. Set `headless: false` in `config.yaml`
2. Run `python src/main.py`
3. Browser will open automatically
4. Log into Facebook and Yad2 in the browser
5. Close the browser
6. Your session is saved in `browser_data/`
7. Set `headless: true` for future automated runs

## Project Structure

```
rental-agent/
├── src/
│   ├── main.py                  # Main orchestrator
│   ├── config_manager.py        # Config handler
│   ├── database.py              # SQLite operations
│   ├── notifier.py              # Telegram integration
│   ├── utils.py                 # Utilities
│   └── scrapers/
│       ├── base_scraper.py      # Base class
│       ├── yad2_scraper.py      # Yad2 scraper
│       └── facebook_scraper.py  # Facebook scraper
├── data/
│   └── listings.db              # SQLite database
├── browser_data/                # Persistent browser context
├── logs/                        # Activity logs
├── config.yaml                  # Configuration
├── requirements.txt             # Dependencies
├── setup.py                     # Setup script
└── README.md                    # This file
```

## Logs

Logs are saved in `logs/scraper_YYYYMMDD.log`:

- Check logs if notifications aren't received
- Verify scraping is working correctly
- Debug errors

View recent logs:

```bash
type logs\scraper_20260502.log
```

## Troubleshooting

### No notifications received

1. Check Telegram bot token and chat ID in config.yaml
2. Send a message to your bot to start the conversation
3. Check logs for errors

### Facebook scraping not working

1. Make sure you're logged in (run with `headless: false`)
2. Check group URLs are correct
3. Facebook structure may have changed - check logs

### Yad2 scraping not working

1. Check if Yad2 website structure changed
2. Try disabling Yad2 and using only Facebook
3. Check logs for specific errors

### Browser won't open

1. Make sure Playwright is installed: `playwright install chromium`
2. Check browser_data/ directory exists
3. Try deleting browser_data/ and logging in again

### Scheduler not running

1. Verify task is enabled in Task Scheduler
2. Check "Last Run Result" in Task Scheduler
3. Make sure Python path is correct in task action
4. Check Windows Event Viewer for errors

## Advanced Configuration

### Anti-Detection Settings

Adjust delays in `config.yaml`:

```yaml
scraping:
  scroll_count: 10     # More scrolls = more posts (slower)
  delay_min: 2         # Minimum delay in seconds
  delay_max: 5         # Maximum delay in seconds
```

### Database Management

View database contents:

```bash
sqlite3 data/listings.db "SELECT * FROM listings;"
```

Clear database (start fresh):

```bash
del data\listings.db
python src/main.py  # Will recreate database
```

## Privacy & Security

- All data stored locally (no cloud services)
- Browser sessions encrypted by Playwright
- Telegram bot tokens should be kept secret
- Never commit `config.yaml` with real tokens to Git

## Limitations

- Facebook structure changes may break scraper
- Rate limiting may occur with excessive requests
- Requires Windows for Task Scheduler (use cron on Linux/Mac)
- Headless mode may trigger CAPTCHAs (use persistent context)

## Contributing

This is a personal project, but suggestions welcome!

## License

MIT License - use freely

## Support

For issues:
1. Check logs in `logs/` directory
2. Verify configuration in `config.yaml`
3. Test manually with `python src/main.py`
4. Check Telegram bot is working

## Future Enhancements

- Web UI for configuration
- Price trend analysis
- WhatsApp integration
- Machine learning for apartment scoring
- Multi-user support

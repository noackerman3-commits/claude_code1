# Rental Agent - Automated Scheduler

## How It Works

The rental agent runs **automatically** at a scheduled time:
- **14:00 (2:00 PM)** - Daily scrape

### What Happens at Each Scheduled Time:

1. **Scrapes all sources:**
   - Yad2 rental listings
   - Configured Facebook groups

2. **Filters listings:**
   - Price range
   - Location
   - Number of rooms
   - Must-have keywords
   - Exclude keywords

3. **Saves new listings:**
   - Checks database for duplicates
   - Saves only NEW listings

4. **Sends ONE aggregated notification:**
   - Summary of all new listings found
   - Up to 10 listings per message
   - Includes: location, price, rooms, link

## Installation

### 1. Install APScheduler

```bash
cd C:\Users\itayg\Desktop\rental-agent
pip install apscheduler pytz
```

Or:
```bash
pip install -r requirements.txt
```

### 2. Configure Settings

Edit `config.yaml`:
- Set Telegram credentials
- Configure search parameters (price, location, rooms)
- Add Facebook groups URLs
- Enable/disable Yad2 and Facebook

### 3. First-Time Browser Login

Run once to log into Facebook and Yad2:
```bash
python run_scrape_now.py
```

A browser will open:
- Log into Facebook
- Log into Yad2
- Close browser when done
- Session is saved for future automated runs

## Running the Scheduler

### Start Automated Scheduler

```bash
cd C:\Users\itayg\Desktop\rental-agent
python src/scheduler.py
```

The scheduler will:
- ✅ Run continuously in the background
- ✅ Execute at 14:00 (2:00 PM) Israel time
- ✅ Send Telegram notifications with results
- ✅ Log all activity to `logs/` folder

**Keep this terminal open** or run as a background service.

### Test Scraping Manually

Run a scrape immediately (for testing):
```bash
python run_scrape_now.py
```

This runs the same scraping job but RIGHT NOW instead of waiting for scheduled time.

## Running as Background Service

### Option 1: pythonw (Hidden Window)

```bash
pythonw src/scheduler.py
```

Runs in background without console window.

### Option 2: Windows Task Scheduler

Create a task that runs at startup:
- **Program:** `python.exe`
- **Arguments:** `src\scheduler.py`
- **Start in:** `C:\Users\itayg\Desktop\rental-agent`
- **Trigger:** At startup
- **Run whether user is logged on or not**

### Option 3: NSSM (Non-Sucking Service Manager)

Install as Windows service:
```bash
nssm install RentalAgent "C:\Python\python.exe" "C:\Users\itayg\Desktop\rental-agent\src\scheduler.py"
nssm start RentalAgent
```

## Notification Format

When new listings are found, you'll receive ONE message like:

```
🏠 New Apartments Found: 5
⏰ 03/05/2026 10:00
━━━━━━━━━━━━━━━━━━━━━

1. 3 rooms apartment in Tel Aviv
📍 Tel Aviv
💰 ₪4,500
🛏 3 rooms
🔗 View Listing
Source: yad2

2. Beautiful 2BR with balcony
📍 Ramat Gan
💰 ₪3,800
🛏 2 rooms
🔗 View Listing
Source: facebook_Group1

...
```

## Configuration via Bot

You can still use the bot to update settings:

```bash
# Keep scheduler running in one terminal
python src/scheduler.py

# In another terminal, run the bot
python src/bot_listener.py
```

Then use bot commands:
- `/parameter price 3000-7000` - Update price range
- `/parameter location Givatayim` - Add location
- `/parameter view` - See current settings

Changes take effect on next scheduled run.

## Logs

All activity is logged to `logs/scraper_YYYYMMDD.log`:
- Scraping start/end times
- Number of listings found
- Errors and warnings
- Notification delivery

View recent logs:
```bash
type logs\scraper_20260503.log
```

## Timezone

The scheduler uses **Asia/Jerusalem** timezone automatically.

Times are in Israel time:
- 14:00 = 2:00 PM Israel time

## Troubleshooting

### Scheduler not running at correct time
- Check system time is correct
- Verify timezone in logs
- Check for errors in log file

### No notifications received
- Verify Telegram credentials in config.yaml
- Check logs for errors
- Test with: `python run_scrape_now.py`

### Browser login expired
- Run: `python run_scrape_now.py`
- Set `headless: false` in config.yaml
- Log in again when browser opens

### Facebook scraping fails
- Facebook structure may have changed
- Check logs for specific errors
- Disable Facebook temporarily: `facebook: enabled: false`

## Monitoring

Check if scheduler is running:

**Windows:**
```bash
tasklist | findstr python
```

**Check next run time:**
Look at scheduler startup logs - shows next scheduled times.

## Stopping the Scheduler

Press `Ctrl+C` in the terminal running the scheduler.

Or kill the process:
```bash
taskkill /F /IM python.exe
```

## Best Practices

1. **Test first:** Run `python run_scrape_now.py` to verify everything works
2. **Monitor logs:** Check logs after first few scheduled runs
3. **Keep browser logged in:** Run with headless=false initially
4. **Adjust schedule:** Edit scheduler.py to change times if needed
5. **Backup database:** Periodically backup `data/listings.db`

## Schedule Customization

To change the scraping time, edit `src/scheduler.py`:

```python
# Change from 14:00 to your preferred time
scheduler.add_job(
    run_scraping_job,
    CronTrigger(hour=9, minute=30, timezone=israel_tz),  # 9:30 AM
    ...
)
```

Restart scheduler after changes.

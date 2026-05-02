# Telegram Bot Listener - Manual URL Submission

This bot allows you to manually send apartment listing URLs directly to your Telegram bot.

## Features

- 📨 Send URLs directly to the bot
- 💾 Automatically saves to database
- 🔍 Extracts price, rooms, location from your message
- 📊 View statistics with `/stats`
- ⚡ Prevents duplicates

## Setup

1. **Configure Telegram** (if not done already):
   - Edit `config.yaml` with your bot token and chat ID
   - See main README.md for details

2. **Run the bot listener**:
   ```bash
   cd C:\Users\itayg\Desktop\rental-agent
   python src\bot_listener.py
   ```

   The bot will start and wait for messages.

## Usage

### Basic URL Submission

Just send a URL to your bot:
```
https://www.yad2.co.il/item/abc123
```

The bot will save it and confirm.

### URL with Details

Send additional info with the URL:
```
https://www.yad2.co.il/item/abc123
Price: 4500
Rooms: 3
Location: Tel Aviv
```

The bot will extract and save the details.

### Multiple URLs

Send multiple URLs in one message:
```
Check these out:
https://www.yad2.co.il/item/abc123
https://www.facebook.com/groups/123/posts/456
```

### Commands

- `/start` - Show welcome message
- `/stats` - Show database statistics
- `/help` - Show help and examples

## Format Examples

### Facebook Post
```
https://www.facebook.com/groups/1663070923962851/posts/123456
Price: 4200
Rooms: 2.5
Location: Ramat Gan
Notes: Nice balcony
```

### Yad2 Listing
```
https://www.yad2.co.il/realestate/item/abc123
Price: 5000
Rooms: 3
Location: Tel Aviv
```

### Any URL
```
https://example.com/apartment
Price: 3800
Rooms: 2
Location: Givatayim
Notes: Great location, elevator
```

## Running Alongside Main Scraper

You can run both scripts simultaneously:

**Terminal 1** - Automated scraper (scheduled):
```bash
python src\main.py
```

**Terminal 2** - Bot listener (always running):
```bash
python src\bot_listener.py
```

## Running as Background Service

### Option 1: Windows Task Scheduler (Recommended)

Create a task that runs at startup:
- Program: `python.exe`
- Arguments: `src\bot_listener.py`
- Start in: `C:\Users\itayg\Desktop\rental-agent`
- Trigger: At startup
- Run whether user is logged on or not

### Option 2: pythonw (Hidden Window)

```bash
pythonw src\bot_listener.py
```

Runs in background without console window.

## Security

- Bot only responds to your chat ID (configured in config.yaml)
- Other users will get "Unauthorized" message
- All data stored locally

## Troubleshooting

### Bot not responding
- Check bot is running: `python src\bot_listener.py`
- Verify bot token in config.yaml
- Check chat ID is correct
- Send `/start` to initialize conversation

### URLs not saving
- Check database is initialized
- Verify URL format is correct
- Check logs for errors

### Duplicate detection
- URLs are deduplicated by listing ID
- Sending same URL again will show "Already saved!"

## Tips

1. **Send URLs from your phone**: Forward listing URLs from browsing
2. **Bulk import**: Paste multiple URLs at once
3. **Add notes**: Include price/location for better tracking
4. **Check stats**: Use `/stats` to see total listings saved

## Example Workflow

1. Browsing Facebook/Yad2 on your phone
2. See interesting apartment
3. Copy URL and send to your bot
4. Bot saves it and confirms
5. Later, review all listings in database
6. Bot prevents duplicate notifications

## Integration with Main Scraper

The bot listener and main scraper share the same database:
- Manual URLs saved by bot
- Automated listings saved by scraper
- All tracked in one place
- Duplicate prevention across both

Both can run simultaneously without conflicts.

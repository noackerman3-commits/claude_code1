# Rental Agent — Claude Code Context

## What this project does
Autonomous Israeli apartment rental agent. Scrapes **Yad2** (on-demand) and **Facebook Groups** (scheduled), filters by user preferences, and sends **Telegram cards** with photo, price, rooms, floor, size, and amenity status.

## Architecture

| File | Role |
|---|---|
| `src/bot_listener.py` | Telegram bot — `/find_homes` (Yad2 only), `/find_all` (both), `/parameter`, `/stats` |
| `src/scheduler.py` | APScheduler — Facebook only, 10:00 + 18:00 Asia/Jerusalem |
| `src/scraping_manager.py` | Orchestrator — `run(sources='yad2'\|'facebook'\|None)` |
| `src/scrapers/yad2_scraper.py` | Playwright scraper — feed-list scoped, link-based dedup, `enrich_from_detail_page()` |
| `src/scrapers/facebook_scraper.py` | Playwright scraper — Facebook group feed |
| `src/scrapers/base_scraper.py` | Shared Playwright browser lifecycle (persistent context) |
| `src/filter_engine.py` | Single source of truth for all listing filtering |
| `src/database.py` | SQLite — auto-migration on startup, `(listing_id, source)` unique |
| `src/formatter.py` | Telegram card — `reply_photo` + caption, amenity line hidden when unknown (None) |
| `src/config_manager.py` | YAML loader + env var overrides |
| `src/utils.py` | Text extraction: price, rooms, floor, size, amenities, neighborhood, property type |
| `src/main.py` | CLI — `python src/main.py [--config path]` |

## Hard constraints

- **Yad2 blocks cloud/server IPs** — must run from user's home Windows machine. Never suggest cloud execution for Yad2.
- **`config.yaml` is gitignored** — contains bot token + chat ID. Never commit it. When searches/groups change, tell the user to update it manually.
- **Branch**: `claude/rental-agent-implementation-JuKlc` — all commits go here.
- **Telegram UI is in Hebrew** — listing cards, bot replies, error messages.
- **Amenity fields default to `None`** (unknown), not `False`. The formatter hides `None` fields. Only `enrich_from_detail_page()` sets them to `True`/`False`.

## Config shape (`config.yaml`)

```yaml
search_parameters:
  price_range: {min: 6000, max: 11000}
  min_rooms: 3.0
  locations: []           # ANY must appear in listing text
  must_have_keywords: []  # ALL must appear
  exclude_keywords: []    # ANY match rejects listing

scraping:
  enrich_details: true    # visit Yad2 detail page per new listing for amenity data

sources:
  yad2:
    enabled: true
    searches:             # N URLs — run sequentially, one browser session
      - name: "Search name"
        url: "https://www.yad2.co.il/realestate/rent/..."
  facebook:
    enabled: true
    groups:               # M groups — scheduler only
      - name: "Group name"
        url: "https://www.facebook.com/groups/..."

telegram:
  bot_token: "..."        # override with RENTAL_BOT_TOKEN env var
  chat_id: "..."          # override with RENTAL_CHAT_ID env var

browser:
  headless: false         # false on Windows for CAPTCHA solving; true on cloud
  persistent_context_path: ./browser_data

database:
  path: ./data/listings.db
```

## Skills & tools to use

- **Playwright sync API** — browser automation, persistent context in `./browser_data`
- **FilterEngine** (`src/filter_engine.py`) — always use this for filtering, never duplicate logic
- **`enrich_from_detail_page(listing)`** — call for new Yad2 listings when `enrich_details: true`
- **`extract_*_from_text()`** in `src/utils.py` — reuse these, don't write new regex
- **`Database._migrate()`** — add columns here when extending schema, never drop/recreate
- **`ScrapingManager.run(sources=...)`** — pass `'yad2'` or `'facebook'` to scope the run

## Memory management

The bot reloads `config.yaml` on every `/find_homes` call — no restart needed after `/parameter` changes. Search parameters, locations, must-have keywords, and exclude keywords are all live-editable via Telegram:

```
/parameter view
/parameter price 6000-11000
/parameter rooms 3
/parameter location כפר סבא
/parameter must מעלית
/parameter exclude שותפים
```

Listing deduplication is handled by `(listing_id, source)` in SQLite plus an in-batch `seen_ids` set in `_process()`. Never add dedup logic elsewhere.

## Common tasks

```bash
# Manual scrape (uses config.yaml)
python src/main.py

# Manual scrape with cloud config (no secrets)
python src/main.py --config config.routine.yaml

# Start Telegram bot (Yad2 on-demand via /find_homes)
python src/bot_listener.py

# Start auto-scheduler (Facebook, twice daily)
python src/scheduler.py

# Start both together (Windows)
start_agent.bat

# Inspect DB
python debug_db.py

# Reset DB for clean test run
del data\listings.db
```

## Commit convention

```bash
git add <files>
git commit -m "type: description"
git push -u origin claude/rental-agent-implementation-JuKlc
```

Always push immediately after committing. Remind user to `git pull` and update `config.yaml` manually for any search/group changes.

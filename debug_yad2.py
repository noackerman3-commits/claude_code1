"""
Debug script — opens Yad2, waits for you to solve any CAPTCHA,
then saves the page HTML so we can find the right selectors.
"""
import sys, time, yaml
sys.path.insert(0, 'src')
from scrapers.base_scraper import BaseScraper

with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Force headless off so you can see + solve CAPTCHA
config['browser']['headless'] = False

s = BaseScraper(config)
s.initialize_browser()

url = (
    "https://www.yad2.co.il/realestate/rent/center-and-sharon"
    "?minPrice=6000&maxPrice=11000&minRooms=3&maxRooms=4"
    "&multiNeighborhood=344%2C808%2C1501"
)

print("Opening Yad2... solve CAPTCHA if it appears.")
s.page.goto(url, wait_until='domcontentloaded', timeout=60000)
print("Page loaded. Waiting 15 seconds (solve CAPTCHA now if needed)...")
time.sleep(15)

# Save full HTML
html = s.page.content()
with open('debug_yad2.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f"HTML saved to debug_yad2.html ({len(html):,} chars)")

# Try every candidate selector and report counts
selectors = [
    '[class*="feed"]',
    '[class*="Feed"]',
    '[class*="item"]',
    '[class*="Item"]',
    '[class*="listing"]',
    '[class*="Listing"]',
    '[class*="card"]',
    '[class*="Card"]',
    'article',
    'li[class*="item"]',
    'li[class*="feed"]',
    '[data-testid]',
    '[data-nagish]',
]

print("\nSelector scan:")
for sel in selectors:
    try:
        els = s.page.query_selector_all(sel)
        if els:
            sample = els[0].inner_text()[:80].replace('\n', ' ')
            print(f"  {len(els):3d}  {sel}   →  \"{sample}\"")
    except Exception as e:
        print(f"  ERR  {sel}  ({e})")

print("\nPage title:", s.page.title())
print("Page URL:  ", s.page.url)

s.close_browser()
print("\nDone. Paste the output above back to Claude.")

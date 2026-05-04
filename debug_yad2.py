"""
Debug script — find the exact class names for Yad2 listing cards.
"""
import sys, time, yaml
sys.path.insert(0, 'src')
from scrapers.base_scraper import BaseScraper

with open('config.yaml') as f:
    config = yaml.safe_load(f)

config['browser']['headless'] = False

s = BaseScraper(config)
s.initialize_browser()

url = (
    "https://www.yad2.co.il/realestate/rent/center-and-sharon"
    "?minPrice=6000&maxPrice=11000&minRooms=3&maxRooms=4"
    "&multiNeighborhood=344%2C808%2C1501"
)

print("Opening Yad2...")
s.page.goto(url, wait_until='domcontentloaded', timeout=60000)
print("Waiting 15 seconds (solve CAPTCHA if needed)...")
time.sleep(15)

# Print the class names + text of each Card element
cards = s.page.query_selector_all('[class*="Card"]')
print(f"\nFound {len(cards)} [class*=Card] elements\n")

for i, card in enumerate(cards[:15], 1):
    cls = card.get_attribute('class') or ''
    text = card.inner_text()[:120].replace('\n', ' | ')
    # Check if it has a link
    link = card.query_selector('a')
    href = link.get_attribute('href') if link else 'no link'
    print(f"[{i:02d}] class: {cls[:80]}")
    print(f"      href : {href}")
    print(f"      text : {text}")
    print()

# Also check data-testid values on card-like elements
print("\n--- data-testid values on feed items ---")
testids = s.page.query_selector_all('[data-testid]')
seen = set()
for el in testids:
    tid = el.get_attribute('data-testid') or ''
    if tid and tid not in seen and any(w in tid.lower() for w in ['feed','item','card','listing','result']):
        seen.add(tid)
        text = el.inner_text()[:80].replace('\n', ' | ')
        print(f"  data-testid={tid!r:40s}  →  {text}")

s.close_browser()
print("\nDone. Paste everything above back to Claude.")

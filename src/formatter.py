"""
Professional real-estate formatter for Telegram messages.
Produces output that looks like an agent's listing card.
"""
from datetime import datetime
from typing import Optional


def format_listing(listing: dict) -> str:
    """
    Returns a Markdown-formatted Telegram message for a single listing.
    All fields are optional — the formatter degrades gracefully when data
    is missing (e.g. Facebook posts that don't mention the floor).
    """
    rooms         = listing.get('rooms')
    price         = listing.get('price')
    location      = listing.get('location') or ''
    neighborhood  = listing.get('neighborhood') or ''
    property_type = listing.get('property_type') or ''
    floor         = listing.get('floor')
    size          = listing.get('size_sqm')
    url           = listing.get('url') or ''
    source        = listing.get('source') or ''
    raw_text      = listing.get('raw_text') or listing.get('title') or ''

    # --- Header ---
    rooms_str = f"{rooms:.0f}" if rooms and rooms == int(rooms) else str(rooms) if rooms else '?'
    city = _extract_city(location, raw_text)
    header = f"🏠 *{rooms_str} חדרים"
    if property_type:
        header = f"🏠 *{property_type}"
    if city:
        header += f" | {city}"
    header += "*"

    lines = [header, ""]

    # --- Address / neighborhood line ---
    if location:
        addr = location
        if neighborhood and neighborhood not in location:
            addr = f"{location} ({neighborhood})"
        lines.append(f"📍 {addr}")

    # --- Price / rooms / floor / size ---
    details = []
    if price:
        details.append(f"💰 ₪{price:,} לחודש")
    specs = []
    if rooms:
        specs.append(f"🛏 {rooms_str} חד'")
    if floor is not None:
        specs.append(f"🏢 קומה {floor}")
    if size:
        specs.append(f"📐 {size:.0f} מ\"ר")
    if specs:
        details.append(" | ".join(specs))
    lines.extend(details)

    # --- Amenities ---
    amenity_line = _build_amenity_line(listing)
    if amenity_line:
        lines.append("")
        lines.append(amenity_line)

    # --- Link ---
    if url:
        lines.append("")
        lines.append(f"🔗 [לצפייה במודעה]({url})")

    # --- Footer ---
    source_label = _source_label(source)
    lines.append(f"_{source_label} • {datetime.now().strftime('%d/%m/%Y')}_")

    return "\n".join(lines)


def format_summary_header(new_count: int, total_scraped: int) -> str:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    return (
        f"🏠 *נמצאו {new_count} דירות חדשות\\!*\n"
        f"⏰ {now}\n"
        f"📊 נסרקו: {total_scraped} מודעות\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _build_amenity_line(listing: dict) -> str:
    """
    Builds a compact amenity row.
    Shows ✅/❌ only when the field is known (not None).
    Parking shows count when > 1.
    """
    parts = []

    # Mamad
    mamad = listing.get('has_mamad')
    if mamad is not None:
        parts.append(f"{'✅' if mamad else '❌'} 🛡️ ממ\"ד")

    # Parking — show count when enriched
    parking_count = listing.get('parking_count')
    has_parking   = listing.get('has_parking')
    if parking_count is not None and parking_count > 1:
        parts.append(f"✅ 🅿️ {parking_count} חניות")
    elif has_parking is not None:
        parts.append(f"{'✅' if has_parking else '❌'} 🅿️ חניה")

    # Balcony
    balcony = listing.get('has_balcony')
    if balcony is not None:
        parts.append(f"{'✅' if balcony else '❌'} 🌿 מרפסת")

    # Elevator
    elevator = listing.get('has_elevator')
    if elevator is not None:
        parts.append(f"{'✅' if elevator else '❌'} 🛗 מעלית")

    # AC
    ac = listing.get('has_ac')
    if ac is not None:
        parts.append(f"{'✅' if ac else '❌'} ❄️ מיזוג")

    return "  ".join(parts)


def _extract_city(location: str, raw_text: str) -> Optional[str]:
    """Best-effort city extraction."""
    cities = [
        'הרצליה', 'Herzliya',
        'רעננה', "Ra'anana",
        'כפר סבא', 'Kfar Saba',
        'הוד השרון', 'Hod HaSharon',
        'תל אביב', 'Tel Aviv',
        'רמת גן', 'Ramat Gan',
        'גבעתיים', 'Givatayim',
        'פתח תקווה', 'Petah Tikva',
        'נתניה', 'Netanya',
        'ראשון לציון', 'Rishon LeZion',
        'תל מונד', 'Tel Mond',
        'שוהם', 'Shoham',
        'בית אריה', 'Beit Arye',
    ]
    combined = (location + ' ' + raw_text[:300]).lower()
    for city in cities:
        if city.lower() in combined:
            return city
    return None


def _source_label(source: str) -> str:
    if 'yad2' in source.lower():
        return 'יד2'
    if 'facebook' in source.lower():
        name = source.replace('facebook_', '').replace('facebook', 'Facebook')
        return f'פייסבוק — {name}' if name else 'פייסבוק'
    return source

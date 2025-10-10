# generate_calendar.py
import os
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event

BASE_LIST = "https://www.maryhalvorson.com/upcoming-dates"
OUTPUT_FILE = "docs/mary.ics"

# e.g., "Oct 23, 2025, 8:30 PM"
DATE_FMT = "%b %d, %Y, %I:%M %p"
DATE_RE = re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}, \d{1,2}:\d{2} [AP]M$")

def fetch_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")

def get_event_links() -> list[str]:
    """Collect unique /event-details/... links from the listing page."""
    soup = fetch_soup(BASE_LIST)
    links = []
    seen = set()
    for a in soup.select('a[href*="/event-details/"]'):
        href = urljoin(BASE_LIST, a.get("href", ""))
        if href and href not in seen:
            seen.add(href)
            links.append(href)
    print(f"[info] Found {len(links)} event detail links")
    return links

def parse_event_page(url: str):
    """Return dict with name, dt_start (datetime), venue, url — or None."""
    s = fetch_soup(url)

    # Title: the big H1 at the top of the page
    h1 = s.find(["h1", "h2"])
    title = (h1.get_text(strip=True) if h1 else "").strip()
    if not title:
        return None

    # The page has a "Time & Location" section with two lines:
    #   Oct 10, 2025, 7:00 PM
    #   Revue Stage, 1601 Johnston St, Vancouver, ...
    # We'll search for a line that matches the date format, then take the next line as venue.
    all_text = [t.strip() for t in s.stripped_strings]
    date_line = None
    venue_line = ""
    for i, t in enumerate(all_text):
        if DATE_RE.match(t):
            date_line = t
            if i + 1 < len(all_text):
                venue_line = all_text[i + 1]
            break
    if not date_line:
        print(f"[warn] No date found on {url}")
        return None

    try:
        dt = datetime.strptime(date_line, DATE_FMT)  # naive/floating time
    except Exception as e:
        print(f"[warn] Could not parse date '{date_line}' on {url}: {e}")
        return None

    return {
        "title": title,
        "begin": dt,
        "venue": venue_line,
        "url": url,
    }

def main():
    detail_links = get_event_links()
    if not detail_links:
        print("[error] No events found on listing page.")
        return 2

    cal = Calendar()
    added = 0
    for link in detail_links:
        info = parse_event_page(link)
        if not info:
            continue
        e = Event()
        e.name = info["title"]
        e.begin = info["begin"]            # naive time; calendar apps treat as local
        e.duration = {"hours": 2}          # default duration; tweak as needed
        e.location = info["venue"]
        e.url = info["url"]
        cal.events.add(e)
        added += 1

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(cal.serialize())

    print(f"[success] Wrote {added} events to {OUTPUT_FILE}")
    return 0 if added > 0 else 2

if __name__ == "__main__":
    raise SystemExit(main())

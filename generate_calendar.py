# generate_calendar.py
import os
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from ics import Calendar, Event

BASE_PAGE = "https://www.maryhalvorson.com/upcoming-dates"
OUTPUT_FILE = "docs/mary.ics"

DATE_RE = re.compile(r"^[A-Z][a-z]{2} \d{1,2}, \d{4}, \d{1,2}:\d{2} [AP]M$")  # e.g., "Oct 23, 2025, 8:30 PM"

def fetch_event_blocks(url: str):
    """Yield dicts with title, datetime string, venue, and details URL."""
    print(f"[info] Fetching: {url}")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Strategy: each event has a title link to /event-details/..., followed by two text lines (date/time, venue)
    for a in soup.select('a[href*="/event-details/"]'):
        title = a.get_text(strip=True)
        if not title:
            continue

        # Walk forward through siblings to capture the next two meaningful text lines
        date_str, venue, details_url = None, None, urljoin(url, a.get("href"))
        texts_found = []

        for sib in a.parent.next_siblings:
            # skip whitespace / empty nodes
            if getattr(sib, "get_text", None):
                t = sib.get_text(strip=True)
            else:
                t = str(sib).strip()
            if not t:
                continue
            # stop when another "Learn more" or next event title shows up
            if t.lower() == "learn more":
                break
            texts_found.append(t)
            if len(texts_found) >= 2:
                break

        # Assign the two lines if they look like date → venue
        if texts_found:
            if DATE_RE.match(texts_found[0]):
                date_str = texts_found[0]
                venue = texts_found[1] if len(texts_found) > 1 else ""

        if date_str:
            yield {
                "title": title,
                "date_str": date_str,
                "venue": venue,
                "url": details_url,
            }

def parse_naive_local(dt_str: str) -> datetime:
    # Example: "Oct 23, 2025, 8:30 PM"
    return datetime.strptime(dt_str, "%b %d, %Y, %I:%M %p")

def build_calendar(blocks):
    cal = Calendar()
    added = 0
    for b in blocks:
        try:
            start = parse_naive_local(b["date_str"])
        except Exception as e:
            print(f"[warn] Could not parse date '{b['date_str']}' for {b['title']}: {e}")
            continue

        e = Event()
        e.name = b["title"]
        e.begin = start  # naive local time (floating). Calendar apps will treat it as local to the viewer.
        e.duration = {"hours": 2}  # default guess; adjust if you prefer
        e.location = b["venue"]
        e.url = b["url"]
        cal.events.add(e)
        added += 1
    print(f"[info] Built calendar with {added} events")
    return cal

def main():
    blocks = list(fetch_event_blocks(BASE_PAGE))
    if not blocks:
        print("[error] No events found; page structure may have changed.")
        return 2

    cal = build_calendar(blocks)
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(cal.serialize())
    print(f"[success] Wrote {len(cal.events)} events to {OUTPUT_FILE}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

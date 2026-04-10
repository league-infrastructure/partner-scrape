#!/usr/bin/env python3
"""
Build a demo-quality dataset from merged events.
Produces clean JSON suitable for a calendar UI / client demo.

Two sections:
  1. "calendar_events" - events with real dates, sorted chronologically
  2. "program_listings" - programs/classes/camps with good descriptions but no specific dates

Outputs: dev/output/demo_events.json
"""

import html as html_lib
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.relevance import score_event

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def clean_text(text: str) -> str:
    """Clean up HTML entities, extra whitespace, and encoding artifacts."""
    if not text:
        return ""
    # Decode HTML entities
    text = html_lib.unescape(text)
    # Remove leftover HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove common junk prefixes
    text = re.sub(r"^(Skip to content|Menu|Close)\s*", "", text)
    return text


def clean_title(title: str) -> str:
    """Clean title, remove site name suffixes."""
    title = clean_text(title)
    # Remove " - Site Name" or " | Site Name" suffixes
    title = re.split(r"\s*[|–—]\s*(?=[A-Z])", title)[0].strip()
    # Remove trailing " - " artifacts
    title = title.rstrip(" -–—").strip()
    return title


def truncate_description(desc: str, max_len: int = 500) -> str:
    """Truncate description at a sentence boundary."""
    desc = clean_text(desc)
    if len(desc) <= max_len:
        return desc
    # Find last sentence end before max_len
    truncated = desc[:max_len]
    last_period = truncated.rfind(". ")
    if last_period > max_len // 2:
        return truncated[:last_period + 1]
    return truncated.rsplit(" ", 1)[0] + "..."


def load_partners() -> dict:
    """Load partner metadata keyed by domain."""
    import csv
    from urllib.parse import urlparse
    partners = {}
    csv_path = DATA_DIR / "partners_viable.csv"
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            website = row.get("website", "").strip().rstrip("/")
            if website:
                domain = urlparse(website).netloc
                if domain:
                    partners[domain] = row
    return partners


def is_junk_event(e: dict) -> bool:
    """Filter out low-value entries."""
    title = (e.get("title") or "").lower()
    desc = (e.get("description") or "").lower()

    # Skip archive/listing/category pages
    junk_titles = ["archives", "events calendar", "events from", "events for",
                   "all events", "event list", "categories", "uncategorized",
                   "author at", "page not found", "404"]
    if any(j in title for j in junk_titles):
        return True

    # Skip very short descriptions that are just navigation
    if len(desc) < 30:
        return True

    # Skip pages that are clearly not events
    if title in ("events", "programs", "classes", "calendar"):
        return True

    return False


def build_calendar_event(e: dict, partners: dict) -> dict | None:
    """Build a clean calendar event record."""
    title = clean_title(e.get("title", ""))
    if not title or len(title) < 5:
        return None

    desc = truncate_description(e.get("description", ""))
    if not desc or len(desc) < 20:
        # Try excerpt for TEC API events
        desc = truncate_description(e.get("excerpt", ""))

    start_date = e.get("start_date", "")
    end_date = e.get("end_date", "")

    # Parse time from date_text if available
    start_time = ""
    end_time = ""
    date_text = e.get("date_text", "")
    time_match = re.search(r"(\d{1,2}:\d{2}\s*[ap]m)", date_text, re.I)
    if time_match:
        start_time = time_match.group(1).strip()
        # Look for end time after "to" or "-"
        end_match = re.search(r"(?:to|[-–])\s*(\d{1,2}:\d{2}\s*[ap]m)", date_text, re.I)
        if end_match:
            end_time = end_match.group(1).strip()

    # For TEC API events, extract time from datetime
    if not start_time and " " in start_date:
        parts = start_date.split(" ")
        if len(parts) == 2:
            start_date = parts[0]
            start_time = parts[1]
    if not end_time and end_date and " " in end_date:
        parts = end_date.split(" ")
        if len(parts) == 2:
            end_date = parts[0]
            end_time = parts[1]

    # Build location
    location = clean_text(e.get("location", "") or e.get("venue", ""))

    # Registration
    reg_url = e.get("registration_url", "")
    if reg_url and not reg_url.startswith("http"):
        # Relative URL - try to make absolute
        page_url = e.get("page_url", "")
        if page_url:
            from urllib.parse import urljoin
            reg_url = urljoin(page_url, reg_url)

    # Get partner metadata
    domain = e.get("domain", "")
    partner = partners.get(domain, {})
    org_type = partner.get("organization_type", "")
    org_website = partner.get("website", "")

    # Determine event category
    event_type = e.get("event_type", "event")
    categories = e.get("categories", [])
    tags = e.get("tags", [])

    return {
        "title": title,
        "organization": e.get("organization", ""),
        "organization_type": org_type,
        "organization_website": org_website,
        "description": desc,
        "start_date": start_date[:10] if start_date else "",
        "end_date": end_date[:10] if end_date else "",
        "start_time": start_time,
        "end_time": end_time,
        "all_day": e.get("all_day", False),
        "location": location,
        "event_type": event_type,
        "categories": categories if isinstance(categories, list) else [],
        "tags": tags if isinstance(tags, list) else [],
        "page_url": e.get("page_url", ""),
        "registration_url": reg_url,
        "image_url": e.get("image_url", ""),
        "cost": clean_text(e.get("cost", "")),
        "source": e.get("source_method", ""),
        "confidence": e.get("confidence", 0),
    }


def build_program_listing(e: dict, partners: dict) -> dict | None:
    """Build a clean program listing record (no specific date)."""
    title = clean_title(e.get("title", ""))
    if not title or len(title) < 5:
        return None

    desc = truncate_description(e.get("description", ""))
    if not desc or len(desc) < 40:
        return None

    domain = e.get("domain", "")
    partner = partners.get(domain, {})

    return {
        "title": title,
        "organization": e.get("organization", ""),
        "organization_type": partner.get("organization_type", ""),
        "organization_website": partner.get("website", ""),
        "description": desc,
        "event_type": e.get("event_type", "program"),
        "page_url": e.get("page_url", ""),
        "registration_url": e.get("registration_url", ""),
        "image_url": e.get("image_url", ""),
        "source": e.get("source_method", ""),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    partners = load_partners()
    # Also build a name-based lookup for relevance scoring
    partners_by_name = {}
    for domain, row in partners.items():
        name = row.get("name", "")
        if name:
            partners_by_name[name] = row

    events = json.loads((OUTPUT_DIR / "events_merged.json").read_text())
    print(f"Input events: {len(events)}")

    calendar_events = []
    program_listings = []
    seen_titles = defaultdict(set)  # per-org dedup

    filtered_out = 0
    for e in events:
        if is_junk_event(e):
            continue

        org = e.get("organization", "")
        org_type = partners_by_name.get(org, {}).get("organization_type", "")

        # STEM-for-kids relevance filter
        relevance = score_event(
            title=e.get("title", ""),
            description=e.get("description", ""),
            org=org,
            org_type=org_type,
            audience=e.get("audience", ""),
            url=e.get("page_url", ""),
        )
        if not relevance["relevant"]:
            filtered_out += 1
            continue
        title_key = clean_title(e.get("title", "")).lower()

        has_real_date = (e.get("start_date")
                         and not e.get("date_text", "").startswith("modified:"))

        if has_real_date:
            # Dedup: same title + same date for same org
            date_key = f"{title_key}|{e.get('start_date', '')[:10]}"
            if date_key in seen_titles[org]:
                continue
            seen_titles[org].add(date_key)

            rec = build_calendar_event(e, partners)
            if rec:
                calendar_events.append(rec)
        else:
            # Dedup: same title for same org
            if title_key in seen_titles[org]:
                continue
            seen_titles[org].add(title_key)

            rec = build_program_listing(e, partners)
            if rec:
                program_listings.append(rec)

    # Sort calendar events by date
    calendar_events.sort(key=lambda e: (e["start_date"], e["organization"]))

    # Sort program listings by org
    program_listings.sort(key=lambda e: (e["organization"], e["title"]))

    # Build org summary
    org_summary = {}
    for e in calendar_events + program_listings:
        org = e["organization"]
        if org not in org_summary:
            org_summary[org] = {
                "name": org,
                "type": e.get("organization_type", ""),
                "website": e.get("organization_website", ""),
                "calendar_events": 0,
                "program_listings": 0,
            }
    for e in calendar_events:
        org_summary[e["organization"]]["calendar_events"] += 1
    for e in program_listings:
        org_summary[e["organization"]]["program_listings"] += 1

    orgs_list = sorted(org_summary.values(), key=lambda o: -(o["calendar_events"] + o["program_listings"]))

    # Build demo output
    demo = {
        "_metadata": {
            "generated": "2026-04-09",
            "description": "STEM events and programs from San Diego partner organizations",
            "total_organizations": len(orgs_list),
            "total_calendar_events": len(calendar_events),
            "total_program_listings": len(program_listings),
            "data_sources": [
                "Tribe Events Calendar REST API (5 sites, highest quality)",
                "WordPress sitemap + HTML extraction (100+ sites)",
                "Wix sitemap metadata (3 sites)",
                "Directory scan + HTML extraction (23 sites)",
            ],
            "notes": "Calendar events have specific dates. Program listings describe recurring programs/classes without specific dates.",
        },
        "organizations": orgs_list,
        "calendar_events": calendar_events,
        "program_listings": program_listings,
    }

    # Write main demo JSON
    demo_path = OUTPUT_DIR / "demo_events.json"
    with open(demo_path, "w") as f:
        json.dump(demo, f, indent=2, ensure_ascii=False)
    print(f"\nWritten to {demo_path}")

    # Also write a flat CSV of just the calendar events for easy viewing
    import csv
    csv_path = OUTPUT_DIR / "demo_calendar.csv"
    csv_fields = ["start_date", "start_time", "end_time", "title", "organization",
                  "organization_type", "location", "event_type", "cost",
                  "description", "page_url", "registration_url"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for rec in calendar_events:
            writer.writerow(rec)
    print(f"Written calendar CSV to {csv_path}")

    # Summary
    print(f"\n{'='*60}")
    print(f"DEMO OUTPUT SUMMARY")
    print(f"{'='*60}")
    print(f"Organizations:      {len(orgs_list)}")
    print(f"Calendar events:    {len(calendar_events)}")
    print(f"Program listings:   {len(program_listings)}")
    print(f"Filtered (not STEM/kids): {filtered_out}")
    print(f"{'='*60}")

    # Calendar event stats
    with_time = sum(1 for e in calendar_events if e["start_time"])
    with_loc = sum(1 for e in calendar_events if e["location"])
    with_reg = sum(1 for e in calendar_events if e["registration_url"])
    with_img = sum(1 for e in calendar_events if e["image_url"])
    with_cost = sum(1 for e in calendar_events if e["cost"])

    print(f"\nCalendar event quality:")
    print(f"  With time:         {with_time}/{len(calendar_events)} ({100*with_time//max(len(calendar_events),1)}%)")
    print(f"  With location:     {with_loc}/{len(calendar_events)} ({100*with_loc//max(len(calendar_events),1)}%)")
    print(f"  With registration: {with_reg}/{len(calendar_events)} ({100*with_reg//max(len(calendar_events),1)}%)")
    print(f"  With image:        {with_img}/{len(calendar_events)} ({100*with_img//max(len(calendar_events),1)}%)")
    print(f"  With cost:         {with_cost}/{len(calendar_events)} ({100*with_cost//max(len(calendar_events),1)}%)")

    # Date range
    dates = [e["start_date"] for e in calendar_events if e["start_date"]]
    if dates:
        print(f"\n  Date range: {min(dates)} to {max(dates)}")
        upcoming = [d for d in dates if d >= "2026-04"]
        print(f"  Upcoming (Apr 2026+): {len(upcoming)}")

    # Top orgs
    print(f"\nTop organizations by calendar events:")
    for org in orgs_list[:15]:
        total = org["calendar_events"] + org["program_listings"]
        print(f"  {org['name'][:45]:45} {org['calendar_events']:4} cal / {org['program_listings']:4} prog")

    # Show a few sample events
    print(f"\n--- Sample Calendar Events ---")
    upcoming_events = [e for e in calendar_events if e["start_date"] >= "2026-04"]
    for e in upcoming_events[:8]:
        print(f"  {e['start_date']} {e['start_time']:8} | {e['organization'][:25]:25} | {e['title'][:45]}")
        if e['location']:
            print(f"{'':42} Location: {e['location'][:50]}")
        if e['cost']:
            print(f"{'':42} Cost: {e['cost']}")


if __name__ == "__main__":
    main()

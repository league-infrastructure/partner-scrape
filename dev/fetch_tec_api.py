#!/usr/bin/env python3
"""
Fetch events from Tribe Events Calendar REST API for sites that support it.
This gets clean structured JSON data - much more reliable than HTML parsing.

Outputs: dev/output/tec_api_events.json
"""

import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# TEC API endpoints discovered from mirror meta.json headers
TEC_SITES = [
    {
        "domain": "coastalrootsfarm.org",
        "organization": "Coastal Roots Farm",
        "api_base": "https://coastalrootsfarm.org/wp-json/tribe/events/v1/events/",
    },
    {
        "domain": "www.thelivingcoast.org",
        "organization": "The Living Coast Discovery Center",
        "api_base": "https://www.thelivingcoast.org/wp-json/tribe/events/v1/events/",
    },
    {
        "domain": "www.eefkids.org",
        "organization": "EastLake Educational Foundation",
        "api_base": "https://eefkids.org/wp-json/tribe/events/v1/events/",
    },
    {
        "domain": "www.ilacsd.org",
        "organization": "I Love A Clean San Diego",
        "api_base": "https://www.cleansd.org/wp-json/tribe/events/v1/events/",
    },
    {
        "domain": "www.oceanconnectors.org",
        "organization": "Ocean Connectors",
        "api_base": "https://oceanconnectors.org/wp-json/tribe/events/v1/events/",
    },
    {
        # sdcdm.org redirects to visitcmod.org; domain kept as sdcdm.org to
        # match the website column in data/partners_viable.csv
        "domain": "sdcdm.org",
        "organization": "San Diego Children's Discovery Museum",
        "api_base": "https://visitcmod.org/wp-json/tribe/events/v1/events/",
    },
]


def fetch_json(url: str, timeout: int = 30) -> dict | None:
    """Fetch a JSON URL with a polite user agent."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "STEM-Calendar-Bot/1.0 (educational research)",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"  Error fetching {url}: {e}")
        return None


def fetch_site_events(site: dict) -> list[dict]:
    """Fetch all events from a TEC site, paginating through results."""
    api_base = site["api_base"]
    all_events = []
    page = 1
    per_page = 50

    while True:
        url = f"{api_base}?per_page={per_page}&page={page}&status=publish"
        print(f"  Fetching page {page}: {url}")
        data = fetch_json(url)

        if data is None:
            break

        events = data.get("events", [])
        if not events:
            break

        for event in events:
            record = {
                "organization": site["organization"],
                "domain": site["domain"],
                "title": event.get("title", ""),
                "description": strip_html(event.get("description", "")),
                "excerpt": strip_html(event.get("excerpt", "")),
                "start_date": event.get("start_date", ""),
                "end_date": event.get("end_date", ""),
                "start_date_details": event.get("start_date_details", {}),
                "end_date_details": event.get("end_date_details", {}),
                "all_day": event.get("all_day", False),
                "timezone": event.get("timezone", ""),
                "cost": event.get("cost", ""),
                "cost_details": event.get("cost_details", {}),
                "url": event.get("url", ""),
                "website": event.get("website", ""),
                "image_url": (event.get("image", {}) or {}).get("url", ""),
                "venue": extract_venue(event.get("venue", {})),
                "organizer": extract_organizer(event.get("organizer", [])),
                "categories": [c.get("name", "") for c in event.get("categories", [])],
                "tags": [t.get("name", "") for t in event.get("tags", [])],
                "api_id": event.get("id", ""),
                "modified_date": event.get("modified_date", ""),
                "source": "tec_api",
            }
            all_events.append(record)

        total_pages = data.get("total_pages", 1)
        print(f"    Got {len(events)} events (page {page}/{total_pages})")

        if page >= total_pages:
            break
        page += 1
        time.sleep(1)  # Be polite

    return all_events


def strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Decode common HTML entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&#8217;", "'").replace("&#8220;", '"').replace("&#8221;", '"')
    text = text.replace("&nbsp;", " ").replace("&#8211;", "-")
    return text


def extract_venue(venue_data) -> dict:
    """Extract venue information."""
    if not venue_data or not isinstance(venue_data, dict):
        return {}
    return {
        "name": venue_data.get("venue", ""),
        "address": venue_data.get("address", ""),
        "city": venue_data.get("city", ""),
        "state": venue_data.get("state", ""),
        "zip": venue_data.get("zip", ""),
        "country": venue_data.get("country", ""),
        "url": venue_data.get("url", ""),
    }


def extract_organizer(organizer_data) -> list[dict]:
    """Extract organizer information."""
    if not organizer_data:
        return []
    if isinstance(organizer_data, dict):
        organizer_data = [organizer_data]
    organizers = []
    for org in organizer_data:
        if isinstance(org, dict):
            organizers.append({
                "name": org.get("organizer", ""),
                "email": org.get("email", ""),
                "phone": org.get("phone", ""),
                "website": org.get("website", ""),
            })
    return organizers


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_events = []

    for site in TEC_SITES:
        print(f"\nFetching events for {site['organization']} ({site['domain']})...")
        events = fetch_site_events(site)
        all_events.extend(events)
        print(f"  Total: {len(events)} events")

    # Write output
    output_path = OUTPUT_DIR / "tec_api_events.json"
    with open(output_path, "w") as f:
        json.dump(all_events, f, indent=2)
    print(f"\nWritten {len(all_events)} events to {output_path}")

    # Summary
    print(f"\n--- TEC API Fetch Summary ---")
    for site in TEC_SITES:
        domain = site["domain"]
        count = sum(1 for e in all_events if e["domain"] == domain)
        with_dates = sum(1 for e in all_events if e["domain"] == domain and e["start_date"])
        with_venue = sum(1 for e in all_events if e["domain"] == domain and e.get("venue", {}).get("name"))
        with_cost = sum(1 for e in all_events if e["domain"] == domain and e.get("cost"))
        print(f"  {domain}: {count} events, {with_dates} dated, {with_venue} with venue, {with_cost} with cost")

    # Show some examples
    print(f"\n--- Sample Events ---")
    for e in all_events[:5]:
        print(f"  {e['organization']}: {e['title']}")
        print(f"    Date: {e['start_date']} to {e['end_date']}")
        print(f"    Venue: {e.get('venue', {}).get('name', 'N/A')}")
        print(f"    Cost: {e.get('cost', 'N/A')}")
        print(f"    URL: {e['url']}")
        print()


if __name__ == "__main__":
    main()

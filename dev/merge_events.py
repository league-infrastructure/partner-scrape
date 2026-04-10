#!/usr/bin/env python3
"""
Merge events from HTML extraction and TEC API fetch into a single dataset.
TEC API data takes priority (higher quality) over HTML-extracted data.

Outputs: dev/output/events_merged.json, dev/output/events_merged.csv
"""

import csv
import json
import re
from pathlib import Path
from collections import defaultdict

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def normalize_url(url: str) -> str:
    """Normalize URL for dedup matching."""
    url = url.strip().rstrip("/").lower()
    # Remove trailing date path segments for recurring events
    url = re.sub(r"/\d{4}-\d{2}-\d{2}$", "", url)
    return url


def main():
    # Load HTML-extracted events
    html_events = json.loads((OUTPUT_DIR / "events_all.json").read_text())
    print(f"HTML-extracted events: {len(html_events)}")

    # Load TEC API events
    tec_path = OUTPUT_DIR / "tec_api_events.json"
    tec_events = json.loads(tec_path.read_text()) if tec_path.exists() else []
    print(f"TEC API events: {len(tec_events)}")

    # Convert TEC events to unified format
    tec_converted = []
    for te in tec_events:
        # Extract just the date portion from datetime
        start_date = te.get("start_date", "")[:10] if te.get("start_date") else ""
        end_date = te.get("end_date", "")[:10] if te.get("end_date") else ""

        venue = te.get("venue", {})
        venue_parts = [venue.get("name", "")]
        if venue.get("city"):
            venue_parts.append(venue.get("city"))
        if venue.get("state"):
            venue_parts.append(venue.get("state"))
        venue_str = ", ".join(p for p in venue_parts if p)

        tec_converted.append({
            "organization": te["organization"],
            "domain": te["domain"],
            "title": te["title"],
            "description": te.get("description", "") or te.get("excerpt", ""),
            "start_date": start_date,
            "end_date": end_date,
            "date_text": f"{te.get('start_date', '')} to {te.get('end_date', '')}",
            "location": venue_str,
            "venue": venue_str,
            "registration_url": te.get("website", "") or te.get("url", ""),
            "page_url": te.get("url", ""),
            "event_type": "event",
            "source_method": "tec_api",
            "image_url": te.get("image_url", ""),
            "api_url": "",
            "lastmod": te.get("modified_date", ""),
            "confidence": 1.0,
            "cost": te.get("cost", ""),
            "categories": te.get("categories", []),
            "tags": te.get("tags", []),
            "all_day": te.get("all_day", False),
            "timezone": te.get("timezone", ""),
        })

    # Build a set of TEC API URLs for dedup
    tec_urls = set()
    for te in tec_converted:
        tec_urls.add(normalize_url(te["page_url"]))

    # Filter HTML events: remove those that overlap with TEC API data
    # and remove events where date is only from modified_time fallback
    html_filtered = []
    deduped = 0
    for he in html_events:
        norm = normalize_url(he.get("page_url", ""))
        if norm in tec_urls:
            deduped += 1
            continue
        html_filtered.append(he)

    print(f"HTML events after dedup: {len(html_filtered)} (removed {deduped} TEC API overlaps)")

    # Combine: TEC API events first (highest quality), then HTML
    merged = tec_converted + html_filtered
    print(f"Total merged: {len(merged)}")

    # Write JSON
    json_path = OUTPUT_DIR / "events_merged.json"
    with open(json_path, "w") as f:
        json.dump(merged, f, indent=2)

    # Write CSV (flat fields only)
    csv_path = OUTPUT_DIR / "events_merged.csv"
    csv_fields = ["organization", "domain", "title", "description", "start_date",
                  "end_date", "date_text", "location", "venue", "registration_url",
                  "page_url", "event_type", "source_method", "image_url",
                  "confidence", "cost"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for rec in merged:
            writer.writerow(rec)

    print(f"Written to {json_path} and {csv_path}")

    # Summary stats
    print(f"\n--- Merged Dataset Summary ---")
    total = len(merged)
    with_date = sum(1 for e in merged if e.get("start_date"))
    with_real_date = sum(1 for e in merged if e.get("start_date") and
                         not (e.get("date_text", "").startswith("modified:")))
    with_desc = sum(1 for e in merged if e.get("description"))
    with_reg = sum(1 for e in merged if e.get("registration_url"))
    from_api = sum(1 for e in merged if e.get("source_method") == "tec_api")
    from_html = total - from_api

    print(f"Total events:        {total}")
    print(f"  From TEC API:      {from_api}")
    print(f"  From HTML scrape:  {from_html}")
    print(f"  With any date:     {with_date} ({100*with_date//max(total,1)}%)")
    print(f"  With real date:    {with_real_date} ({100*with_real_date//max(total,1)}%)")
    print(f"  With description:  {with_desc} ({100*with_desc//max(total,1)}%)")
    print(f"  With registration: {with_reg} ({100*with_reg//max(total,1)}%)")

    # By source
    sources = defaultdict(int)
    for e in merged:
        sources[e.get("source_method", "unknown")] += 1
    print(f"\nBy source method:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")

    # Show upcoming events (2026-04 and later) with good data
    upcoming = [e for e in merged
                if e.get("start_date", "") >= "2026-04"
                and e.get("description")
                and not e.get("date_text", "").startswith("modified:")]
    print(f"\nUpcoming events (April 2026+) with description: {len(upcoming)}")
    for e in sorted(upcoming, key=lambda x: x["start_date"])[:15]:
        print(f"  {e['start_date']} | {e['organization'][:30]:30} | {e['title'][:50]}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Classify each mirror domain into a tier based on how extractable their
event/program content is. Detects CMS platform and event plugins.

Depends on: dev/output/sitemap_inventory.csv (from inventory_sitemaps.py)
"""

import csv
import json
import re
from pathlib import Path
from collections import defaultdict

MIRRORS_DIR = Path(__file__).resolve().parent.parent / "data" / "mirrors"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Event-related sitemap categories
EVENT_SITEMAP_CATS = {"event"}
PROGRAM_SITEMAP_CATS = {"program", "product"}

# URL path patterns indicating event/program content
EVENT_PATH_PATTERNS = re.compile(
    r"/(events?|tribe_events|public-events?|science-events?|calendar)(/|$)", re.I
)
PROGRAM_PATH_PATTERNS = re.compile(
    r"/(programs?|courses?|camps?|classes|workshops?|training|lessons?|sessions?)(/|$)", re.I
)


def load_sitemap_inventory():
    """Load the sitemap inventory CSV into a dict keyed by domain."""
    inventory = defaultdict(list)
    csv_path = OUTPUT_DIR / "sitemap_inventory.csv"
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            inventory[row["domain"]].append(row)
    return inventory


def load_partners():
    """Load partners_viable.csv into a dict keyed by domain."""
    partners = {}
    csv_path = DATA_DIR / "partners_viable.csv"
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            website = row.get("website", "").strip().rstrip("/")
            if website:
                from urllib.parse import urlparse
                domain = urlparse(website).netloc
                if domain:
                    partners[domain] = row
    return partners


def detect_platform(domain: str) -> str:
    """Detect CMS platform by checking the index page HTML."""
    index_path = MIRRORS_DIR / domain / "_index" / "content.html"
    if not index_path.exists():
        # Try other common entry points
        for alt in ["_index/content.html", "index.html"]:
            alt_path = MIRRORS_DIR / domain / alt
            if alt_path.exists():
                index_path = alt_path
                break

    if not index_path.exists():
        return "unknown"

    try:
        html = index_path.read_text(errors="replace")[:50000]  # First 50KB
    except Exception:
        return "unknown"

    html_lower = html.lower()
    if "wp-content" in html_lower or "wordpress" in html_lower:
        return "wordpress"
    if "wixstatic.com" in html_lower or "wix.com" in html_lower:
        return "wix"
    if "squarespace" in html_lower:
        return "squarespace"
    if "drupal" in html_lower:
        return "drupal"
    if "sites.google.com" in domain:
        return "google_sites"
    return "other"


def detect_event_plugin(domain: str) -> str:
    """Detect event plugins by checking HTML for telltale CSS/JS references."""
    # Check a few pages for plugin indicators
    plugins_found = set()

    for html_path in list((MIRRORS_DIR / domain).rglob("content.html"))[:10]:
        try:
            html = html_path.read_text(errors="replace")[:30000]
        except Exception:
            continue

        html_lower = html.lower()
        if "tribe-events" in html_lower or "the-events-calendar" in html_lower:
            plugins_found.add("tribe_events_calendar")
        if "stec-" in html_lower or "starter-templates-events" in html_lower:
            plugins_found.add("stec")
        if "ajde_evcal" in html_lower or "eventon" in html_lower:
            plugins_found.add("eventon")
        if "events-manager" in html_lower:
            plugins_found.add("events_manager")
        if "wp-json/tribe" in html_lower:
            plugins_found.add("tribe_events_calendar")

    return ",".join(sorted(plugins_found)) if plugins_found else "none"


def scan_mirror_dirs(domain: str) -> dict:
    """Scan mirror filesystem for event/program-related directories."""
    mirror_path = MIRRORS_DIR / domain
    event_dirs = []
    program_dirs = []

    if not mirror_path.exists():
        return {"event_dirs": 0, "program_dirs": 0, "event_dir_examples": [], "program_dir_examples": []}

    for d in mirror_path.iterdir():
        if not d.is_dir():
            continue
        name_lower = d.name.lower()
        if any(p in name_lower for p in ["event", "calendar"]):
            event_dirs.append(d.name)
        if any(p in name_lower for p in ["program", "course", "camp", "class",
                                          "workshop", "training", "lesson"]):
            program_dirs.append(d.name)

    return {
        "event_dirs": len(event_dirs),
        "program_dirs": len(program_dirs),
        "event_dir_examples": event_dirs[:5],
        "program_dir_examples": program_dirs[:5],
    }


def classify_domain(domain: str, sitemaps: list, partners: dict) -> dict:
    """Classify a single domain into a tier."""
    partner_info = partners.get(domain, {})

    # Count event and program sitemaps
    event_sitemaps = [s for s in sitemaps if s["category"] in EVENT_SITEMAP_CATS]
    program_sitemaps = [s for s in sitemaps if s["category"] in PROGRAM_SITEMAP_CATS]
    total_event_urls = sum(int(s.get("event_url_count", 0)) for s in sitemaps)
    total_program_urls = sum(int(s.get("program_url_count", 0)) for s in sitemaps)

    platform = detect_platform(domain)
    event_plugin = detect_event_plugin(domain)
    dir_scan = scan_mirror_dirs(domain)

    # Determine tier
    has_event_sitemaps = len(event_sitemaps) > 0
    has_program_sitemaps = len(program_sitemaps) > 0
    has_event_urls_in_sitemaps = total_event_urls > 0
    has_program_urls_in_sitemaps = total_program_urls > 0
    has_event_dirs = dir_scan["event_dirs"] > 0
    has_program_dirs = dir_scan["program_dirs"] > 0
    has_sitemaps = len(sitemaps) > 0

    if has_event_sitemaps and event_plugin != "none":
        tier = "1A"
        strategy = f"event_sitemap+{event_plugin}"
    elif has_event_sitemaps and platform == "wix":
        tier = "1C"
        strategy = "wix_event_sitemap"
    elif has_event_sitemaps:
        tier = "1A"
        strategy = "event_sitemap+generic"
    elif has_program_sitemaps:
        tier = "1B"
        strategy = "program_sitemap"
    elif has_event_urls_in_sitemaps or has_program_urls_in_sitemaps:
        tier = "2"
        strategy = "filtered_general_sitemap"
    elif has_sitemaps and (has_event_dirs or has_program_dirs):
        tier = "2"
        strategy = "sitemap+dir_scan"
    elif has_event_dirs or has_program_dirs:
        tier = "3"
        strategy = "dir_scan_only"
    elif has_sitemaps:
        tier = "4"
        strategy = "sitemap_keyword_search"
    else:
        tier = "4"
        strategy = "full_scan"

    return {
        "domain": domain,
        "partner_name": partner_info.get("name", ""),
        "organization_type": partner_info.get("organization_type", ""),
        "tier": tier,
        "platform": platform,
        "event_plugin": event_plugin,
        "strategy": strategy,
        "event_sitemap_count": len(event_sitemaps),
        "program_sitemap_count": len(program_sitemaps),
        "event_url_count": total_event_urls,
        "program_url_count": total_program_urls,
        "event_dirs": dir_scan["event_dirs"],
        "program_dirs": dir_scan["program_dirs"],
        "event_dir_examples": "; ".join(dir_scan["event_dir_examples"]),
        "program_dir_examples": "; ".join(dir_scan["program_dir_examples"]),
        "total_sitemaps": len(sitemaps),
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading sitemap inventory...")
    inventory = load_sitemap_inventory()

    print("Loading partners list...")
    partners = load_partners()

    # Get all mirror domains
    all_domains = sorted(d.name for d in MIRRORS_DIR.iterdir() if d.is_dir())
    print(f"Processing {len(all_domains)} domains...")

    results = []
    for i, domain in enumerate(all_domains):
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(all_domains)}...")
        sitemaps = inventory.get(domain, [])
        result = classify_domain(domain, sitemaps, partners)
        results.append(result)

    # Write CSV
    output_path = OUTPUT_DIR / "site_classification.csv"
    fieldnames = ["domain", "partner_name", "organization_type", "tier",
                  "platform", "event_plugin", "strategy",
                  "event_sitemap_count", "program_sitemap_count",
                  "event_url_count", "program_url_count",
                  "event_dirs", "program_dirs",
                  "event_dir_examples", "program_dir_examples",
                  "total_sitemaps"]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\nWritten to {output_path}")

    # Summary
    tier_counts = defaultdict(int)
    tier_domains = defaultdict(list)
    platform_counts = defaultdict(int)
    plugin_counts = defaultdict(int)

    for r in results:
        tier_counts[r["tier"]] += 1
        tier_domains[r["tier"]].append(r["domain"])
        platform_counts[r["platform"]] += 1
        if r["event_plugin"] != "none":
            plugin_counts[r["event_plugin"]] += 1

    print(f"\n--- Tier Distribution ---")
    for tier in sorted(tier_counts.keys()):
        print(f"  Tier {tier}: {tier_counts[tier]} sites")
        for d in tier_domains[tier]:
            r = next(x for x in results if x["domain"] == d)
            print(f"    {d} [{r['strategy']}] {r['partner_name']}")

    print(f"\n--- Platform Distribution ---")
    for plat, count in sorted(platform_counts.items(), key=lambda x: -x[1]):
        print(f"  {plat}: {count}")

    print(f"\n--- Event Plugins Detected ---")
    for plug, count in sorted(plugin_counts.items(), key=lambda x: -x[1]):
        print(f"  {plug}: {count}")


if __name__ == "__main__":
    main()

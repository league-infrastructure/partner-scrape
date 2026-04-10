#!/usr/bin/env python3
"""
Walk all mirror directories, find every XML sitemap file, classify by type,
count URLs, and output a comprehensive inventory CSV.
"""

import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

MIRRORS_DIR = Path(__file__).resolve().parent.parent / "data" / "mirrors"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# Classification patterns for sitemap filenames
EVENT_PATTERNS = re.compile(
    r"(tribe_events|tribe_event_series|tribe_events_cat|tribe_venue|tribe_organizer"
    r"|tec_recurring|ajde_events|stec_event|event|events)", re.I
)
PROGRAM_PATTERNS = re.compile(r"(program|course|workshop|camp|class|training)", re.I)
POST_PATTERNS = re.compile(r"(post|blog|news|article|press)", re.I)
PAGE_PATTERNS = re.compile(r"(page)", re.I)
CATEGORY_PATTERNS = re.compile(r"(category|tag|taxonomy|cat)", re.I)
AUTHOR_PATTERNS = re.compile(r"(author|user)", re.I)
PRODUCT_PATTERNS = re.compile(r"(product|store)", re.I)


def classify_sitemap(filename: str) -> str:
    """Classify a sitemap filename into a category."""
    name = filename.lower().replace(".xml", "")
    if EVENT_PATTERNS.search(name):
        return "event"
    if PROGRAM_PATTERNS.search(name):
        return "program"
    if PRODUCT_PATTERNS.search(name):
        return "product"
    if POST_PATTERNS.search(name):
        return "post"
    if CATEGORY_PATTERNS.search(name):
        return "category"
    if AUTHOR_PATTERNS.search(name):
        return "author"
    if PAGE_PATTERNS.search(name):
        return "page"
    if "sitemap_index" in name or "sitemap-index" in name:
        return "index"
    return "other"


def parse_sitemap(xml_path: Path) -> dict:
    """Parse a sitemap XML and return type + stats."""
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return {"sitemap_type": "parse_error", "url_count": 0,
                "oldest_lastmod": "", "newest_lastmod": "", "urls": []}

    root = tree.getroot()
    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    if tag == "sitemapindex":
        sitemaps = root.findall("sm:sitemap", NS)
        locs = [s.findtext("sm:loc", "", NS) for s in sitemaps]
        lastmods = [s.findtext("sm:lastmod", "", NS) for s in sitemaps]
        lastmods = sorted([lm for lm in lastmods if lm])
        return {
            "sitemap_type": "index",
            "url_count": len(sitemaps),
            "oldest_lastmod": lastmods[0] if lastmods else "",
            "newest_lastmod": lastmods[-1] if lastmods else "",
            "urls": locs,
        }
    elif tag == "urlset":
        urls_el = root.findall("sm:url", NS)
        locs = [u.findtext("sm:loc", "", NS) for u in urls_el]
        lastmods = [u.findtext("sm:lastmod", "", NS) for u in urls_el]
        lastmods = sorted([lm for lm in lastmods if lm])
        return {
            "sitemap_type": "urlset",
            "url_count": len(urls_el),
            "oldest_lastmod": lastmods[0] if lastmods else "",
            "newest_lastmod": lastmods[-1] if lastmods else "",
            "urls": locs,
        }
    else:
        return {"sitemap_type": "unknown", "url_count": 0,
                "oldest_lastmod": "", "newest_lastmod": "", "urls": []}


def find_sitemaps(mirrors_dir: Path):
    """Find all XML sitemap files across all mirror directories."""
    results = []
    for xml_file in sorted(mirrors_dir.rglob("*.xml")):
        # Sitemaps are stored at {domain}/{sitemap-name}/{sitemap-name}
        # The XML file is inside a directory with the same name
        if not xml_file.is_file():
            continue

        # Extract domain: it's the first directory under mirrors/
        rel = xml_file.relative_to(mirrors_dir)
        domain = rel.parts[0]

        info = parse_sitemap(xml_file)
        category = classify_sitemap(xml_file.name)

        # Check if any URLs in this sitemap point to event-like paths
        event_url_count = 0
        program_url_count = 0
        for url in info.get("urls", []):
            url_lower = url.lower()
            if any(p in url_lower for p in ["/event/", "/events/", "/tribe_events/",
                                             "/public-event/", "/science-event/"]):
                event_url_count += 1
            if any(p in url_lower for p in ["/program/", "/programs/", "/course/",
                                             "/camp/", "/class/", "/workshop/",
                                             "/training/"]):
                program_url_count += 1

        results.append({
            "domain": domain,
            "sitemap_path": str(rel),
            "sitemap_file": xml_file.name,
            "category": category,
            "sitemap_type": info["sitemap_type"],
            "url_count": info["url_count"],
            "event_url_count": event_url_count,
            "program_url_count": program_url_count,
            "oldest_lastmod": info["oldest_lastmod"],
            "newest_lastmod": info["newest_lastmod"],
        })

    return results


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Scanning {MIRRORS_DIR} for sitemaps...")
    results = find_sitemaps(MIRRORS_DIR)
    print(f"Found {len(results)} sitemap files across {len(set(r['domain'] for r in results))} domains")

    # Write CSV
    output_path = OUTPUT_DIR / "sitemap_inventory.csv"
    fieldnames = ["domain", "sitemap_path", "sitemap_file", "category",
                  "sitemap_type", "url_count", "event_url_count",
                  "program_url_count", "oldest_lastmod", "newest_lastmod"]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"Written to {output_path}")

    # Summary stats
    domains_with_sitemaps = set(r["domain"] for r in results)
    all_domains = set(d.name for d in MIRRORS_DIR.iterdir() if d.is_dir())
    domains_without = all_domains - domains_with_sitemaps

    categories = {}
    for r in results:
        cat = r["category"]
        categories[cat] = categories.get(cat, 0) + 1

    event_domains = set(r["domain"] for r in results
                        if r["category"] == "event" or r["event_url_count"] > 0)
    program_domains = set(r["domain"] for r in results
                          if r["category"] == "program" or r["program_url_count"] > 0)

    print(f"\n--- Summary ---")
    print(f"Total mirror domains: {len(all_domains)}")
    print(f"Domains with sitemaps: {len(domains_with_sitemaps)} ({100*len(domains_with_sitemaps)//len(all_domains)}%)")
    print(f"Domains without sitemaps: {len(domains_without)}")
    print(f"\nSitemap categories:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    print(f"\nDomains with event-related sitemaps/URLs: {len(event_domains)}")
    for d in sorted(event_domains):
        print(f"  {d}")
    print(f"\nDomains with program/course/camp sitemaps/URLs: {len(program_domains)}")
    for d in sorted(program_domains):
        print(f"  {d}")
    print(f"\nDomains without sitemaps:")
    for d in sorted(domains_without):
        print(f"  {d}")


if __name__ == "__main__":
    main()

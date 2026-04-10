#!/usr/bin/env python3
"""
For each tier/plugin combination, sample event pages and test extraction
selectors. Outputs extraction_patterns.json and sample_events.json.

Depends on: dev/output/site_classification.csv (from classify_sites.py)
"""

import csv
import json
import re
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from lxml import html as lxml_html
import xml.etree.ElementTree as ET

MIRRORS_DIR = Path(__file__).resolve().parent.parent / "data" / "mirrors"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# Reuse _url_to_relpath from mirror_spider.py
_UNSAFE_CHARS_RE = re.compile(r'[<>:"|\\*\x00-\x1f]')


def _url_to_relpath(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        path = "_index"
    if parsed.query:
        qhash = hashlib.sha256(parsed.query.encode()).hexdigest()[:8]
        path = f"{path}__q_{qhash}"
    segments = [
        _UNSAFE_CHARS_RE.sub("_", seg)[:200]
        for seg in path.split("/")
        if seg
    ]
    return "/".join(segments) if segments else "_index"


def resolve_url_to_local(domain: str, url: str) -> Path | None:
    """Map a URL to its local content.html path in the mirror."""
    relpath = _url_to_relpath(url)
    content_path = MIRRORS_DIR / domain / relpath / "content.html"
    if content_path.exists():
        return content_path
    # Also try without content.html (some are stored differently)
    alt = MIRRORS_DIR / domain / relpath
    if alt.exists() and alt.is_file():
        return alt
    return None


def get_meta(content_path: Path) -> dict:
    """Load meta.json companion file."""
    meta_path = content_path.parent / "meta.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text())
        except Exception:
            pass
    return {}


def find_event_urls_from_sitemaps(domain: str) -> list[dict]:
    """Find event-related URLs from a domain's sitemaps."""
    event_urls = []
    domain_dir = MIRRORS_DIR / domain

    for xml_path in domain_dir.rglob("*.xml"):
        if not xml_path.is_file():
            continue
        try:
            tree = ET.parse(xml_path)
        except ET.ParseError:
            continue

        root = tree.getroot()
        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

        if tag != "urlset":
            continue

        sitemap_name = xml_path.name
        for url_el in root.findall("sm:url", NS):
            loc = url_el.findtext("sm:loc", "", NS)
            lastmod = url_el.findtext("sm:lastmod", "", NS)
            if loc:
                event_urls.append({
                    "url": loc,
                    "lastmod": lastmod,
                    "sitemap": sitemap_name,
                })

    return event_urls


def find_event_dirs(domain: str) -> list[Path]:
    """Find content.html files in event-related directories."""
    domain_dir = MIRRORS_DIR / domain
    results = []
    event_patterns = ["event", "events", "public-event", "science-event",
                      "program", "programs", "course", "courses",
                      "camp", "camps", "workshop", "workshops",
                      "class", "classes", "training"]

    for d in domain_dir.iterdir():
        if d.is_dir() and d.name.lower() in event_patterns:
            for content in d.rglob("content.html"):
                results.append(content)
    return results


def extract_tribe_events(content_path: Path, meta: dict) -> dict | None:
    """Extract event data from Tribe Events Calendar pages."""
    try:
        tree = lxml_html.parse(str(content_path))
    except Exception:
        return None

    result = {"extractor": "tribe_events"}

    # Title
    for h1 in tree.iter("h1"):
        cls = h1.get("class") or ""
        if "entry-title" in cls or "tribe-events" in cls:
            result["title"] = h1.text_content().strip()
            break
    if "title" not in result:
        title_el = tree.find(".//title")
        if title_el is not None:
            result["title"] = title_el.text_content().strip().split(" - ")[0].strip()

    # Date/time from crf-event-details or tribe-events-schedule
    for el in tree.iter():
        cls = el.get("class") or ""
        text = (el.text or "").strip()
        if "crf-event-details" in cls or "tribe-events-schedule" in cls:
            full_text = el.text_content().strip()
            result["date_text"] = full_text[:200]
            break
        # Also check direct text for date patterns
        if any(m in text for m in ["January", "February", "March", "April", "May",
                                    "June", "July", "August", "September",
                                    "October", "November", "December"]):
            if "date_text" not in result:
                result["date_text"] = text[:200]

    # Venue
    for el in tree.iter():
        cls = el.get("class") or ""
        if "tribe-venue" in cls:
            result["venue"] = el.text_content().strip()[:200]
            break

    # Description from entry-content
    for el in tree.iter():
        cls = el.get("class") or ""
        if cls == "entry-content" or "tribe-events-content" in cls:
            result["description"] = el.text_content().strip()[:500]
            break

    # Registration links
    for a in tree.iter("a"):
        href = a.get("href") or ""
        text = a.text_content().strip().lower()
        if any(k in text for k in ["register", "sign up", "rsvp", "tickets", "book"]):
            result["registration_url"] = href
            result["registration_text"] = a.text_content().strip()
            break

    # API URL from meta.json headers
    headers = meta.get("headers", {})
    api_root = headers.get("X-Tec-Api-Root", headers.get("x-tec-api-root"))
    if api_root:
        if isinstance(api_root, list):
            api_root = api_root[0]
        result["api_url"] = api_root

    # OG metadata
    for meta_el in tree.iter("meta"):
        prop = meta_el.get("property") or ""
        content = meta_el.get("content") or ""
        if prop == "og:description" and "og_description" not in result:
            result["og_description"] = content[:500]
        if prop == "og:image":
            result["image_url"] = content
        if prop == "article:modified_time":
            result["modified_time"] = content

    result["page_url"] = meta.get("url", "")
    return result


def extract_yoast_custom_post(content_path: Path, meta: dict) -> dict | None:
    """Extract event data from WordPress + Yoast custom post type pages."""
    try:
        tree = lxml_html.parse(str(content_path))
    except Exception:
        return None

    result = {"extractor": "yoast_custom_post"}

    # Title from og:title or <title>
    for meta_el in tree.iter("meta"):
        prop = meta_el.get("property") or ""
        content = meta_el.get("content") or ""
        if prop == "og:title":
            result["title"] = content.split(" - ")[0].strip()
        if prop == "og:description":
            result["og_description"] = content[:500]
        if prop == "og:image":
            result["image_url"] = content
        if prop == "article:modified_time":
            result["modified_time"] = content

    if "title" not in result:
        title_el = tree.find(".//title")
        if title_el is not None:
            result["title"] = title_el.text_content().strip().split(" - ")[0].strip()

    # Body content
    for el in tree.iter():
        cls = el.get("class") or ""
        if "entry-content" in cls or "post-content" in cls or "article-content" in cls:
            text = el.text_content().strip()[:500]
            if text:
                result["description"] = text
                # Look for dates in the content
                date_match = re.search(
                    r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*\d{4}',
                    text
                )
                if date_match:
                    result["date_text"] = date_match.group()
                break

    # Registration links
    for a in tree.iter("a"):
        href = a.get("href") or ""
        text = a.text_content().strip().lower()
        if any(k in text for k in ["register", "sign up", "rsvp", "tickets", "book"]):
            result["registration_url"] = href
            break

    result["page_url"] = meta.get("url", "")
    return result


def extract_wix(content_path: Path, meta: dict) -> dict | None:
    """Extract what we can from Wix pages (mostly limited due to client rendering)."""
    try:
        tree = lxml_html.parse(str(content_path))
    except Exception:
        return None

    result = {"extractor": "wix"}

    # Wix pages often have title and description in meta tags
    for meta_el in tree.iter("meta"):
        prop = meta_el.get("property") or meta_el.get("name") or ""
        content = meta_el.get("content") or ""
        if prop == "og:title":
            result["title"] = content
        if prop in ("og:description", "description"):
            result["og_description"] = content[:500]
        if prop == "og:image":
            result["image_url"] = content

    if "title" not in result:
        title_el = tree.find(".//title")
        if title_el is not None:
            result["title"] = title_el.text_content().strip()

    # Try to extract date from URL slug
    url = meta.get("url", "")
    # Pattern like: event-name-2026-04-11-10-00
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', url)
    if date_match:
        result["date_from_url"] = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"

    result["page_url"] = url
    result["note"] = "Wix pages are client-rendered; HTML content is minimal"
    return result


def extract_generic(content_path: Path, meta: dict) -> dict | None:
    """Generic HTML extraction for unclassified sites."""
    try:
        tree = lxml_html.parse(str(content_path))
    except Exception:
        return None

    result = {"extractor": "generic"}

    # Title
    for meta_el in tree.iter("meta"):
        prop = meta_el.get("property") or ""
        content = meta_el.get("content") or ""
        if prop == "og:title":
            result["title"] = content.split(" - ")[0].strip()
        if prop == "og:description":
            result["og_description"] = content[:500]
        if prop == "og:image":
            result["image_url"] = content

    if "title" not in result:
        for h1 in tree.iter("h1"):
            result["title"] = h1.text_content().strip()
            break
    if "title" not in result:
        title_el = tree.find(".//title")
        if title_el is not None:
            result["title"] = title_el.text_content().strip()

    # Description
    for el in tree.iter():
        cls = el.get("class") or ""
        if any(k in cls for k in ["entry-content", "post-content", "content-area",
                                    "article-content", "field-content"]):
            result["description"] = el.text_content().strip()[:500]
            break

    # Date search in body text
    body = tree.find(".//body")
    if body is not None:
        body_text = body.text_content()
        date_match = re.search(
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*\d{0,4}',
            body_text
        )
        if date_match:
            result["date_text"] = date_match.group()

    # Registration links
    for a in tree.iter("a"):
        href = a.get("href") or ""
        text = a.text_content().strip().lower()
        if any(k in text for k in ["register", "sign up", "rsvp", "tickets", "book"]):
            result["registration_url"] = href
            break

    result["page_url"] = meta.get("url", "")
    return result


def load_classification() -> list[dict]:
    csv_path = OUTPUT_DIR / "site_classification.csv"
    with open(csv_path) as f:
        return list(csv.DictReader(f))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    classifications = load_classification()

    extraction_patterns = {}
    sample_events = []
    max_samples_per_group = 5

    # Group sites by strategy for sampling
    strategy_groups = {}
    for site in classifications:
        tier = site["tier"]
        strategy = site["strategy"]
        key = f"{tier}_{strategy}"
        strategy_groups.setdefault(key, []).append(site)

    for group_key, sites in sorted(strategy_groups.items()):
        print(f"\n=== {group_key} ({len(sites)} sites) ===")
        group_samples = []

        for site in sites[:max_samples_per_group]:
            domain = site["domain"]
            print(f"  Sampling {domain}...")

            # Find event pages to sample
            content_files = []

            # Strategy 1: Use event sitemaps
            if "event_sitemap" in site["strategy"] or "program_sitemap" in site["strategy"]:
                sitemap_urls = find_event_urls_from_sitemaps(domain)
                # Filter to event/program URLs
                for su in sitemap_urls[:10]:
                    url = su["url"]
                    local = resolve_url_to_local(domain, url)
                    if local:
                        content_files.append((local, url))

            # Strategy 2: Use directory scan
            if not content_files:
                event_files = find_event_dirs(domain)
                for f in event_files[:10]:
                    meta = get_meta(f)
                    url = meta.get("url", "")
                    content_files.append((f, url))

            if not content_files:
                print(f"    No event content found")
                continue

            # Sample up to 3 pages per site
            for content_path, url in content_files[:3]:
                meta = get_meta(content_path)

                # Choose extractor based on strategy
                if "tribe_events" in site.get("event_plugin", ""):
                    extracted = extract_tribe_events(content_path, meta)
                elif site["platform"] == "wix":
                    extracted = extract_wix(content_path, meta)
                elif site["tier"] in ("1A", "1B"):
                    extracted = extract_yoast_custom_post(content_path, meta)
                else:
                    extracted = extract_generic(content_path, meta)

                if extracted:
                    extracted["domain"] = domain
                    extracted["partner_name"] = site["partner_name"]
                    extracted["tier"] = site["tier"]
                    extracted["strategy"] = site["strategy"]
                    group_samples.append(extracted)

                    title = extracted.get("title", "?")[:60]
                    date = extracted.get("date_text", extracted.get("date_from_url", "no date"))
                    print(f"    ✓ {title} | {date}")

        if group_samples:
            # Record extraction patterns for this group
            extractors_used = set(s.get("extractor", "?") for s in group_samples)
            has_dates = sum(1 for s in group_samples if "date_text" in s or "date_from_url" in s)
            has_desc = sum(1 for s in group_samples if "description" in s or "og_description" in s)
            has_reg = sum(1 for s in group_samples if "registration_url" in s)
            has_api = sum(1 for s in group_samples if "api_url" in s)

            extraction_patterns[group_key] = {
                "site_count": len(sites),
                "samples": len(group_samples),
                "extractors": list(extractors_used),
                "has_dates": f"{has_dates}/{len(group_samples)}",
                "has_description": f"{has_desc}/{len(group_samples)}",
                "has_registration": f"{has_reg}/{len(group_samples)}",
                "has_api_url": f"{has_api}/{len(group_samples)}",
                "example_domains": [s["domain"] for s in group_samples[:3]],
            }
            sample_events.extend(group_samples)

    # Write outputs
    patterns_path = OUTPUT_DIR / "extraction_patterns.json"
    with open(patterns_path, "w") as f:
        json.dump(extraction_patterns, f, indent=2)
    print(f"\nWritten extraction patterns to {patterns_path}")

    samples_path = OUTPUT_DIR / "sample_events.json"
    with open(samples_path, "w") as f:
        json.dump(sample_events, f, indent=2)
    print(f"Written {len(sample_events)} sample events to {samples_path}")

    # Summary
    print(f"\n--- Extraction Quality Summary ---")
    total = len(sample_events)
    with_title = sum(1 for s in sample_events if s.get("title"))
    with_date = sum(1 for s in sample_events if s.get("date_text") or s.get("date_from_url"))
    with_desc = sum(1 for s in sample_events if s.get("description") or s.get("og_description"))
    with_reg = sum(1 for s in sample_events if s.get("registration_url"))
    with_api = sum(1 for s in sample_events if s.get("api_url"))

    print(f"Total samples: {total}")
    print(f"  With title:        {with_title}/{total} ({100*with_title//max(total,1)}%)")
    print(f"  With date:         {with_date}/{total} ({100*with_date//max(total,1)}%)")
    print(f"  With description:  {with_desc}/{total} ({100*with_desc//max(total,1)}%)")
    print(f"  With registration: {with_reg}/{total} ({100*with_reg//max(total,1)}%)")
    print(f"  With API URL:      {with_api}/{total} ({100*with_api//max(total,1)}%)")


if __name__ == "__main__":
    main()

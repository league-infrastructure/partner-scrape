#!/usr/bin/env python3
"""
Main event extraction pipeline. Processes all mirror domains, extracts
event/class/camp/workshop/program information, and outputs structured data.

Depends on: dev/output/site_classification.csv
"""

import csv
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from urllib.parse import urlparse
from lxml import html as lxml_html

# Add dev/ to path for lib imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.url_resolver import resolve, url_to_relpath
from lib.sitemap_parser import get_event_urls, get_domain_sitemaps, parse_sitemap_file

MIRRORS_DIR = Path(__file__).resolve().parent.parent / "data" / "mirrors"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Known event-specific sitemap filename patterns
EVENT_SITEMAP_PATTERNS = re.compile(
    r"(tribe_events|tribe_event_series|ajde_events|stec_event|"
    r"event-pages|event-sitemap|events-sitemap|public-event|science-event)", re.I
)
PROGRAM_SITEMAP_PATTERNS = re.compile(
    r"(program-sitemap|course-sitemap|product-sitemap|store-products)", re.I
)

# Sites where dates are embedded in the title (e.g. "Event Name (March 5th, 2026 – 10AM)")
TITLE_DATE_SITES = {
    "www.olivewoodgardens.org",
}

# Domains that use BiblioCommons for events
BIBLIOCOMMONS_DOMAINS = {
    "sdcl.org",
}

# URL path patterns for event content
EVENT_DIR_PATTERNS = ["event", "events", "public-event", "science-event",
                      "program", "programs", "course", "courses",
                      "camp", "camps", "workshop", "workshops",
                      "class", "classes", "training", "calendar",
                      "series", "sessions", "lessons"]


@dataclass
class EventRecord:
    organization: str = ""
    domain: str = ""
    title: str = ""
    description: str = ""
    start_date: str = ""
    end_date: str = ""
    date_text: str = ""
    location: str = ""
    venue: str = ""
    registration_url: str = ""
    page_url: str = ""
    event_type: str = ""  # event/class/camp/workshop/program
    source_method: str = ""  # sitemap-tribe/sitemap-wix/dir-scan/etc
    image_url: str = ""
    api_url: str = ""
    lastmod: str = ""
    confidence: float = 0.0


def load_meta(content_path: Path) -> dict:
    meta_path = content_path.parent / "meta.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text())
        except Exception:
            pass
    return {}


def parse_html(content_path: Path):
    """Parse HTML file, return lxml tree or None."""
    try:
        return lxml_html.parse(str(content_path))
    except Exception:
        return None


def classify_event_type(url: str, title: str = "") -> str:
    """Guess the event type from URL and title."""
    text = (url + " " + title).lower()
    if any(k in text for k in ["camp", "summer camp", "day camp"]):
        return "camp"
    if any(k in text for k in ["class", "lesson"]):
        return "class"
    if any(k in text for k in ["workshop"]):
        return "workshop"
    if any(k in text for k in ["course", "training"]):
        return "course"
    if any(k in text for k in ["program"]):
        return "program"
    return "event"


def parse_date_text(text: str) -> tuple[str, str]:
    """Try to parse a date string into ISO start/end dates. Returns (start, end)."""
    import re
    from datetime import datetime

    MONTHS = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    MONTH_PAT = r"(January|February|March|April|May|June|July|August|September|October|November|December)"

    text = text.strip()
    # Default year: assume current/next year for undated events
    default_year = 2026

    # 1. "Month DD, YYYY"  e.g. "May 13, 2026"
    m = re.search(MONTH_PAT + r"\s+(\d{1,2}),?\s+(\d{4})", text, re.I)
    if m:
        try:
            dt = datetime(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
            return (dt.strftime("%Y-%m-%d"), "")
        except ValueError:
            pass

    # 2. "Weekday(s), Month DD @ time" or "Weekday, Month DD - Month DD"
    m = re.search(
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)s?,?\s+"
        + MONTH_PAT + r"\s+(\d{1,2})",
        text, re.I,
    )
    if m:
        try:
            dt = datetime(default_year, MONTHS[m.group(1).lower()], int(m.group(2)))
            return (dt.strftime("%Y-%m-%d"), "")
        except ValueError:
            pass

    # 3. "Month DD @ time" (no weekday, no year)  e.g. "May 13 @ 3:00 pm"
    m = re.search(MONTH_PAT + r"\s+(\d{1,2})\s*@", text, re.I)
    if m:
        try:
            dt = datetime(default_year, MONTHS[m.group(1).lower()], int(m.group(2)))
            return (dt.strftime("%Y-%m-%d"), "")
        except ValueError:
            pass

    # 4. "Month DD" alone (no year, no @)  e.g. "May 9", "September 26"
    m = re.match(MONTH_PAT + r"\s+(\d{1,2})\s*,?\s*$", text, re.I)
    if m:
        day = int(m.group(2))
        if 1 <= day <= 31:
            try:
                dt = datetime(default_year, MONTHS[m.group(1).lower()], day)
                return (dt.strftime("%Y-%m-%d"), "")
            except ValueError:
                pass

    # 5. "Month YYYY" (month only, no day)  e.g. "February 2026"
    m = re.search(MONTH_PAT + r"\s+(\d{4})", text, re.I)
    if m:
        year = int(m.group(2))
        if 2020 <= year <= 2030:
            return (f"{year}-{MONTHS[m.group(1).lower()]:02d}-01", "")

    # 6. ISO date: YYYY-MM-DD
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return (m.group(0), "")

    # 7. Range: "Month DD - Month DD" or "Month DD - DD"
    m = re.search(MONTH_PAT + r"\s+(\d{1,2})\s*[-–]\s*" + MONTH_PAT + r"\s+(\d{1,2})", text, re.I)
    if m:
        try:
            start = datetime(default_year, MONTHS[m.group(1).lower()], int(m.group(2)))
            end = datetime(default_year, MONTHS[m.group(3).lower()], int(m.group(4)))
            return (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        except ValueError:
            pass

    m = re.search(MONTH_PAT + r"\s+(\d{1,2})\s*[-–]\s*(\d{1,2})", text, re.I)
    if m:
        try:
            month = MONTHS[m.group(1).lower()]
            start = datetime(default_year, month, int(m.group(2)))
            end = datetime(default_year, month, int(m.group(3)))
            return (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        except ValueError:
            pass

    return ("", "")


# ─── Extractors ───────────────────────────────────────────────────────────────

def extract_tribe_events(tree, meta: dict) -> dict:
    """Extract from WordPress + The Events Calendar plugin."""
    data = {}

    # Title
    for h1 in tree.iter("h1"):
        cls = h1.get("class") or ""
        if "entry-title" in cls:
            data["title"] = h1.text_content().strip()
            break

    # Date from crf-event-details or tribe-events-schedule
    for el in tree.iter():
        cls = el.get("class") or ""
        direct_text = (el.text or "").strip()
        if "crf-event-details" in cls or "tribe-events-schedule" in cls:
            data["date_text"] = el.text_content().strip()[:200]
            break
        if any(m in direct_text for m in ["January", "February", "March", "April", "May",
                                           "June", "July", "August", "September",
                                           "October", "November", "December"]):
            if "date_text" not in data and len(direct_text) < 200:
                data["date_text"] = direct_text

    # Venue
    for el in tree.iter():
        cls = el.get("class") or ""
        if "tribe-venue" in cls:
            data["venue"] = el.text_content().strip()[:200]
            break

    # Description
    for el in tree.iter():
        cls = el.get("class") or ""
        if cls == "entry-content" or "tribe-events-content" in cls:
            text = el.text_content().strip()
            if len(text) > 20:
                data["description"] = text[:1000]
                break

    # Registration links
    for a in tree.iter("a"):
        href = a.get("href") or ""
        text = a.text_content().strip().lower()
        if any(k in text for k in ["register", "sign up", "rsvp", "tickets", "book now",
                                    "reserve", "enroll"]):
            data["registration_url"] = href
            break

    # API URL from headers
    headers = meta.get("headers", {})
    api_root = headers.get("X-Tec-Api-Root") or headers.get("x-tec-api-root")
    if api_root:
        data["api_url"] = api_root[0] if isinstance(api_root, list) else api_root

    return data


def extract_wordpress_generic(tree, meta: dict) -> dict:
    """Extract from generic WordPress pages (custom post types, Yoast)."""
    data = {}

    # OG metadata
    for meta_el in tree.iter("meta"):
        prop = meta_el.get("property") or ""
        content = meta_el.get("content") or ""
        if prop == "og:title" and "title" not in data:
            data["title"] = content.split(" - ")[0].strip()
        if prop == "og:description":
            data["og_description"] = content[:500]
        if prop == "og:image":
            data["image_url"] = content
        if prop == "article:modified_time":
            data["modified_time"] = content

    # Title fallback
    if "title" not in data:
        for h1 in tree.iter("h1"):
            text = h1.text_content().strip()
            if text and len(text) > 3:
                data["title"] = text
                break
    if "title" not in data:
        title_el = tree.find(".//title")
        if title_el is not None:
            data["title"] = title_el.text_content().strip().split(" - ")[0].strip()

    # Body content
    for el in tree.iter():
        cls = el.get("class") or ""
        if any(k in cls for k in ["entry-content", "post-content", "article-content",
                                    "field-content", "page-content"]):
            text = el.text_content().strip()
            if len(text) > 20:
                data["description"] = text[:1000]
                # Look for dates
                date_match = re.search(
                    r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s*\d{0,4}',
                    text[:500]
                )
                if date_match:
                    data["date_text"] = date_match.group()
                break

    # Registration links
    for a in tree.iter("a"):
        href = a.get("href") or ""
        text = a.text_content().strip().lower()
        if any(k in text for k in ["register", "sign up", "rsvp", "tickets", "book now",
                                    "reserve", "enroll"]):
            data["registration_url"] = href
            break

    return data


def extract_wix(tree, meta: dict) -> dict:
    """Extract from Wix pages (limited due to client-side rendering)."""
    data = {}

    for meta_el in tree.iter("meta"):
        prop = meta_el.get("property") or meta_el.get("name") or ""
        content = meta_el.get("content") or ""
        if prop == "og:title":
            data["title"] = content
        if prop in ("og:description", "description"):
            data["description"] = content[:500]
        if prop == "og:image":
            data["image_url"] = content

    if "title" not in data:
        title_el = tree.find(".//title")
        if title_el is not None:
            data["title"] = title_el.text_content().strip()

    # Try date from URL
    url = meta.get("url", "")
    date_match = re.search(r'(\d{4})-(\d{2})-(\d{2})', url)
    if date_match:
        data["date_text"] = date_match.group(0)

    return data


def extract_generic(tree, meta: dict) -> dict:
    """Fallback extraction for any HTML page. Tries multiple strategies."""
    data = {}

    # 1. Try JSON-LD Event schema first (highest quality)
    ld_event = extract_json_ld(tree)
    if ld_event:
        data["title"] = ld_event.get("name", "")
        data["description"] = ld_event.get("description", "")[:1000]
        if ld_event.get("startDate"):
            data["date_text"] = ld_event["startDate"]
        if ld_event.get("endDate"):
            data["end_date_iso"] = ld_event["endDate"]
        loc = ld_event.get("location", {})
        if isinstance(loc, dict):
            data["venue"] = loc.get("name", "")
            addr = loc.get("address", {})
            if isinstance(addr, dict):
                data["venue"] += f", {addr.get('addressLocality', '')}"
        if ld_event.get("image"):
            img = ld_event["image"]
            data["image_url"] = img if isinstance(img, str) else img[0] if isinstance(img, list) else img.get("url", "")
        if ld_event.get("offers"):
            offers = ld_event["offers"]
            if isinstance(offers, dict):
                data["cost"] = offers.get("price", "")
            elif isinstance(offers, list) and offers:
                data["cost"] = offers[0].get("price", "")
        # If JSON-LD gave us good data, return early
        if data.get("title") and data.get("date_text"):
            data["page_url"] = meta.get("url", "")
            return data

    # 2. Try <time datetime="..."> elements
    time_elements = extract_time_elements(tree)
    if time_elements and "date_text" not in data:
        data["date_text"] = time_elements[0]
        if len(time_elements) >= 2:
            data["end_time_iso"] = time_elements[1]

    # 3. OG metadata
    for meta_el in tree.iter("meta"):
        prop = meta_el.get("property") or meta_el.get("name") or ""
        content = meta_el.get("content") or ""
        if prop == "og:title" and "title" not in data:
            data["title"] = content.split(" - ")[0].strip()
        if prop in ("og:description", "description") and "description" not in data:
            data["description"] = content[:500]
        if prop == "og:image" and "image_url" not in data:
            data["image_url"] = content

    # 4. Title fallback
    if "title" not in data:
        for h1 in tree.iter("h1"):
            text = h1.text_content().strip()
            if text:
                data["title"] = text
                break
    if "title" not in data:
        title_el = tree.find(".//title")
        if title_el is not None:
            data["title"] = title_el.text_content().strip()

    # 5. Try to extract date from title (pattern: "Event (Month DD, YYYY)")
    if "date_text" not in data and data.get("title"):
        title_date = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?",
            data["title"]
        )
        if title_date:
            year = title_date.group(3) or "2026"
            data["date_text"] = f"{title_date.group(1)} {title_date.group(2)}, {year}"

    # 6. Body content
    body = tree.find(".//body")
    if body is not None and "description" not in data:
        for el in body.iter():
            cls = el.get("class") or ""
            if any(k in cls for k in ["entry-content", "post-content", "article-content",
                                        "article-body", "main-content", "field--name-body",
                                        "node__content", "event-description"]):
                text = el.text_content().strip()
                if len(text) > 30:
                    data["description"] = text[:1000]
                    break

    # 7. Date search in body text (last resort)
    if body is not None and "date_text" not in data:
        body_text = body.text_content()[:3000]
        # Try full date first: "Weekday, Month DD, YYYY"
        date_match = re.search(
            r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
            r"(January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+\d{1,2},?\s*\d{4}",
            body_text
        )
        if not date_match:
            # Try just "Month DD, YYYY"
            date_match = re.search(
                r"(January|February|March|April|May|June|July|August|September|October|November|December)"
                r"\s+\d{1,2},?\s*\d{4}",
                body_text
            )
        if not date_match:
            # Try "Month DD" (no year)
            date_match = re.search(
                r"(January|February|March|April|May|June|July|August|September|October|November|December)"
                r"\s+\d{1,2}(?:st|nd|rd|th)?(?:\s|,|$)",
                body_text
            )
        if date_match:
            data["date_text"] = date_match.group().strip().rstrip(",")

    # 8. Registration links
    for a in tree.iter("a"):
        href = a.get("href") or ""
        text = a.text_content().strip().lower()
        if any(k in text for k in ["register", "sign up", "rsvp", "tickets", "book now",
                                    "reserve", "enroll"]):
            data["registration_url"] = href
            break

    data["page_url"] = meta.get("url", "")
    return data


# ─── Site-specific extractors ─────────────────────────────────────────────────

def extract_bibliocommons(tree, meta: dict) -> dict:
    """Extract from BiblioCommons library event pages (sdcl.org, etc.)."""
    data = {}

    # Title: prefer the clean print title, then strip breadcrumb from h1
    for el in tree.iter():
        cls = el.get("class") or ""
        if "event-summary-title" in cls:
            # Check for visible-print child with clean title
            for child in el.getparent() if el.getparent() is not None else []:
                ccls = child.get("class") or ""
                if "visible-print" in ccls:
                    text = child.text_content().strip()
                    if text:
                        data["title"] = text
                        break
            break
    if "title" not in data:
        for el in tree.iter():
            cls = el.get("class") or ""
            if "event-title" in cls:
                text = el.text_content().strip()
                # Strip "Events ›" breadcrumb prefix
                if "›" in text:
                    text = text.split("›")[-1].strip()
                data["title"] = text
                break

    # Date and time from <time datetime="..."> elements
    times = []
    for t in tree.iter("time"):
        dt = t.get("datetime", "")
        if dt:
            times.append(dt)
    if times:
        # First time is start, second is end
        data["date_text"] = times[0]
        if len(times) >= 2:
            data["end_time_iso"] = times[1]

    # Time text from event-time
    for el in tree.iter():
        cls = el.get("class") or ""
        if "event-time" in cls.split() or cls == "event-time":
            data["time_text"] = el.text_content().strip()
            break

    # Location from event-location
    for el in tree.iter():
        cls = el.get("class") or ""
        if "event-location" in cls:
            data["venue"] = el.text_content().strip()
            break

    # Description from event-description-content
    for el in tree.iter():
        cls = el.get("class") or ""
        if "event-description-content" in cls:
            data["description"] = el.text_content().strip()[:1000]
            break

    # Age/audience from event-facets
    for el in tree.iter():
        cls = el.get("class") or ""
        if "event-facets" in cls:
            data["audience"] = el.text_content().strip()[:300]
            break

    # OG metadata fallback
    for meta_el in tree.iter("meta"):
        prop = meta_el.get("property") or ""
        content = meta_el.get("content") or ""
        if prop == "og:title" and "title" not in data:
            data["title"] = content
        if prop == "og:description" and "description" not in data:
            data["description"] = content[:500]
        if prop == "og:image":
            data["image_url"] = content

    data["page_url"] = meta.get("url", "")
    return data


def extract_drupal_event(tree, meta: dict) -> dict:
    """Extract from Drupal event pages (sandiego.gov, etc.)."""
    data = {}

    # Date from URL query string: ?event-date=Friday,%20April%2024,%202026,%208:15%20-%2011:30am
    url = meta.get("url", "")
    from urllib.parse import parse_qs, urlparse as _urlparse
    parsed = _urlparse(url)
    qs = parse_qs(parsed.query)
    if "event-date" in qs:
        data["date_text"] = qs["event-date"][0]

    # Date from <time datetime="..."> elements
    for t in tree.iter("time"):
        dt = t.get("datetime", "")
        if dt:
            data.setdefault("date_text", dt)
            break

    # Title: find the right h1 — skip visually-hidden and department headings
    for h1 in tree.iter("h1"):
        cls = h1.get("class") or ""
        text = h1.text_content().strip()
        # Skip hidden/site-wide h1s
        if "visually-hidden" in cls:
            continue
        # Skip department-level headings (e.g., "Parks & Recreation")
        if text.lower() in ("parks & recreation", "city of san diego official website"):
            continue
        if text and len(text) > 3:
            data["title"] = text
            break

    # Date/description from node__content
    for el in tree.iter():
        cls = el.get("class") or ""
        if "node__content" in cls or "field--name-body" in cls:
            text = el.text_content().strip()[:1000]
            lines = [l.strip() for l in text.split("\n") if l.strip()]

            # The second line often has the date
            if "date_text" not in data:
                for line in lines[:5]:
                    date_match = re.search(
                        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
                        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
                        r"\s+\d{1,2},?\s*\d{4}",
                        line
                    )
                    if date_match:
                        data["date_text"] = date_match.group()
                        break

            if text and len(text) > 20:
                data["description"] = text[:1000]
                break

    # Title fallback: extract from URL slug
    if "title" not in data:
        path = parsed.path.strip("/")
        if "/" in path:
            slug = path.split("/")[-1]
            slug = re.sub(r"-\d+$", "", slug)
            slug = re.sub(r"__q_[a-f0-9]+$", "", slug)
            data["title"] = slug.replace("-", " ").title()

    # OG metadata fallback
    for meta_el in tree.iter("meta"):
        prop = meta_el.get("property") or ""
        content = meta_el.get("content") or ""
        if prop == "og:title" and "title" not in data:
            data["title"] = content.split(" | ")[0].strip()
        if prop == "og:description" and "description" not in data:
            data["description"] = content[:500]
        if prop == "og:image":
            data["image_url"] = content

    # Registration links
    for a in tree.iter("a"):
        href = a.get("href") or ""
        text = a.text_content().strip().lower()
        if any(k in text for k in ["register", "sign up", "rsvp", "tickets", "book now"]):
            data["registration_url"] = href
            break

    return data


def extract_title_date(tree, meta: dict) -> dict:
    """
    Extract events where the date is embedded in the title/og:title.
    Pattern: "Event Name (Month DDth, YYYY – TIME)" or similar.
    Used by olivewoodgardens.org and similar sites.
    """
    data = {}

    # Get og:title which often has the full event name with date
    og_title = ""
    for meta_el in tree.iter("meta"):
        prop = meta_el.get("property") or ""
        content = meta_el.get("content") or ""
        if prop == "og:title":
            og_title = content
            break

    # Also check h1
    h1_title = ""
    for h1 in tree.iter("h1"):
        h1_title = h1.text_content().strip()
        break

    # Use the longer/more detailed title
    full_title = og_title if len(og_title) > len(h1_title) else h1_title
    if not full_title:
        full_title = og_title or h1_title

    # Try to extract date from title
    # Patterns: "(February 14th, 2026 – 10AM)", "(March 5, 2026 - 9:30AM)"
    date_in_title = re.search(
        r"\(?\s*(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?\s*(?:[–—-]\s*(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm)?))?\s*\)?",
        full_title
    )
    if date_in_title:
        month_str = date_in_title.group(1)
        day = date_in_title.group(2)
        year = date_in_title.group(3) or "2026"
        time_str = date_in_title.group(4) or ""
        data["date_text"] = f"{month_str} {day}, {year}"
        if time_str:
            data["date_text"] += f" {time_str}"

        # Clean title: remove the date portion
        clean = full_title[:date_in_title.start()].strip().rstrip("(").rstrip(" -–—").strip()
        if clean:
            data["title"] = clean.split(" - ")[0].strip()

    # If no date from title, try URL slug: /events/open-gardens-2026-02-21/
    if "date_text" not in data:
        url = meta.get("url", "")
        url_date = re.search(r"(\d{4})-(\d{2})-(\d{2})", url)
        if url_date:
            data["date_text"] = f"{url_date.group(1)}-{url_date.group(2)}-{url_date.group(3)}"

    if "title" not in data:
        # Remove site name suffix
        data["title"] = full_title.split(" - ")[0].strip()

    # OG description
    for meta_el in tree.iter("meta"):
        prop = meta_el.get("property") or ""
        content = meta_el.get("content") or ""
        if prop == "og:description":
            data["description"] = content[:500]
        if prop == "og:image":
            data["image_url"] = content

    # Body content fallback for description
    if "description" not in data:
        for el in tree.iter():
            cls = el.get("class") or ""
            if "entry-content" in cls or "post-content" in cls:
                text = el.text_content().strip()
                if len(text) > 30:
                    data["description"] = text[:1000]
                    break

    # Registration links
    for a in tree.iter("a"):
        href = a.get("href") or ""
        text = a.text_content().strip().lower()
        if any(k in text for k in ["register", "sign up", "rsvp", "tickets", "book now",
                                    "reserve", "enroll"]):
            data["registration_url"] = href
            break

    return data


# ─── Enhanced generic extraction helpers ──────────────────────────────────────

def extract_json_ld(tree) -> dict | None:
    """Extract Event data from JSON-LD script tags."""
    for script in tree.iter("script"):
        stype = script.get("type") or ""
        if "ld+json" not in stype:
            continue
        try:
            ld = json.loads(script.text_content() or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle both single objects and arrays
        if isinstance(ld, list):
            for item in ld:
                if isinstance(item, dict) and item.get("@type") == "Event":
                    return item
        elif isinstance(ld, dict):
            if ld.get("@type") == "Event":
                return ld
    return None


def extract_time_elements(tree) -> list[str]:
    """Extract ISO datetimes from <time datetime="..."> elements."""
    times = []
    for t in tree.iter("time"):
        dt = t.get("datetime", "")
        if dt and re.match(r"\d{4}-\d{2}-\d{2}", dt):
            times.append(dt)
    return times


# ─── Skip heuristics ─────────────────────────────────────────────────────────

def is_listing_page(url: str, title: str) -> bool:
    """Detect archive/listing pages that aren't individual events."""
    url_lower = url.lower()
    title_lower = title.lower()

    # Archive pages
    if any(k in url_lower for k in ["/page/", "?paged=", "/category/",
                                     "/tag/", "/author/", "/feed/"]):
        return True
    if any(k in title_lower for k in ["archives", "events from ", "events for ",
                                       "all events", "event list"]):
        return True
    return False


def is_valid_event(rec: EventRecord) -> bool:
    """Check if an extracted record looks like a real event/program."""
    if not rec.title or len(rec.title) < 3:
        return False
    if is_listing_page(rec.page_url, rec.title):
        return False
    # Skip author pages, category pages
    if any(k in rec.page_url.lower() for k in ["/author/", "/category/", "/tag/"]):
        return False
    return True


# ─── Main pipeline ────────────────────────────────────────────────────────────

def load_classification() -> list[dict]:
    csv_path = OUTPUT_DIR / "site_classification.csv"
    with open(csv_path) as f:
        return list(csv.DictReader(f))


def load_partners() -> dict:
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


def get_event_sitemap_names(domain: str) -> list[str]:
    """Identify event-specific sitemaps for a domain."""
    sitemaps = get_domain_sitemaps(MIRRORS_DIR, domain)
    event_maps = []
    for name in sitemaps:
        if EVENT_SITEMAP_PATTERNS.search(name) or PROGRAM_SITEMAP_PATTERNS.search(name):
            event_maps.append(name)
    return event_maps


def find_event_content_by_dirs(domain: str) -> list[tuple[Path, str]]:
    """Find event content by walking event-related directories."""
    domain_dir = MIRRORS_DIR / domain
    results = []

    for d in domain_dir.iterdir():
        if d.is_dir() and d.name.lower() in EVENT_DIR_PATTERNS:
            for content in d.rglob("content.html"):
                meta = load_meta(content)
                url = meta.get("url", "")
                results.append((content, url))

    return results


def process_domain(site: dict, partners: dict) -> list[EventRecord]:
    """Process a single domain and extract all event records."""
    domain = site["domain"]
    partner = partners.get(domain, {})
    org_name = partner.get("name", domain)
    tier = site["tier"]
    plugin = site.get("event_plugin", "none")
    platform = site.get("platform", "unknown")

    records = []
    content_urls = []  # list of (content_path, url, lastmod, source_method)

    # Phase 1: Get URLs from event-specific sitemaps
    event_sitemaps = get_event_sitemap_names(domain)
    if event_sitemaps:
        for sm_name in event_sitemaps:
            sitemaps = get_domain_sitemaps(MIRRORS_DIR, domain)
            if sm_name in sitemaps:
                entries = parse_sitemap_file(sitemaps[sm_name])
                for entry in entries:
                    local = resolve(MIRRORS_DIR, domain, entry.url)
                    if local:
                        content_urls.append((local, entry.url, entry.lastmod, f"sitemap-{sm_name}"))

    # Phase 2: Get URLs from filtered general sitemaps
    if not content_urls or tier == "2":
        filtered = get_event_urls(MIRRORS_DIR, domain)
        for entry in filtered:
            local = resolve(MIRRORS_DIR, domain, entry.url)
            if local:
                already = {cu[1] for cu in content_urls}
                if entry.url not in already:
                    content_urls.append((local, entry.url, entry.lastmod, "sitemap-filtered"))

    # Phase 3: Directory scan fallback
    if not content_urls or tier == "3":
        dir_content = find_event_content_by_dirs(domain)
        already = {cu[1] for cu in content_urls}
        for path, url in dir_content:
            if url not in already:
                content_urls.append((path, url, "", "dir-scan"))

    # Now extract from each content file
    for content_path, url, lastmod, source_method in content_urls:
        meta = load_meta(content_path)
        tree = parse_html(content_path)
        if tree is None:
            continue

        # Choose extractor — site-specific first, then platform-based, then generic
        page_url = url or meta.get("url", "")

        if "bibliocommons.com" in page_url or domain in BIBLIOCOMMONS_DOMAINS:
            data = extract_bibliocommons(tree, meta)
        elif domain in TITLE_DATE_SITES:
            data = extract_title_date(tree, meta)
        elif platform == "drupal" and "/event" in page_url.lower():
            data = extract_drupal_event(tree, meta)
        elif "tribe_events" in plugin:
            data = extract_tribe_events(tree, meta)
        elif platform == "wix":
            data = extract_wix(tree, meta)
        elif platform == "wordpress":
            data = extract_wordpress_generic(tree, meta)
        else:
            data = extract_generic(tree, meta)

        # Build record
        title = data.get("title", "")
        date_text = data.get("date_text", "")
        start_date, end_date = parse_date_text(date_text) if date_text else ("", "")

        # Fallback: try extracting date from URL path  e.g. /event/name/2026-04-22/
        if not start_date:
            page_url = url or meta.get("url", "")
            url_date = re.search(r'/(\d{4})-(\d{2})-(\d{2})/?', page_url)
            if url_date:
                start_date = url_date.group(0).strip("/")
            else:
                # Try /YYYY/MM/DD/ pattern
                url_date = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', page_url)
                if url_date:
                    start_date = f"{url_date.group(1)}-{url_date.group(2)}-{url_date.group(3)}"

        # Fallback: try article:modified_time from OG data
        if not start_date and data.get("modified_time"):
            mt = re.search(r'(\d{4})-(\d{2})-(\d{2})', data["modified_time"])
            if mt:
                start_date = mt.group(0)
                date_text = date_text or f"modified:{mt.group(0)}"

        rec = EventRecord(
            organization=org_name,
            domain=domain,
            title=title,
            description=data.get("description", data.get("og_description", "")),
            start_date=start_date,
            end_date=end_date,
            date_text=date_text,
            location=data.get("venue", ""),
            venue=data.get("venue", ""),
            registration_url=data.get("registration_url", ""),
            page_url=url or meta.get("url", ""),
            event_type=classify_event_type(url, title),
            source_method=source_method,
            image_url=data.get("image_url", ""),
            api_url=data.get("api_url", ""),
            lastmod=lastmod,
            confidence=compute_confidence(data, source_method),
        )

        if is_valid_event(rec):
            records.append(rec)

    return records


def compute_confidence(data: dict, source_method: str) -> float:
    """Compute a confidence score 0-1 based on data quality."""
    score = 0.0
    if data.get("title"):
        score += 0.2
    if data.get("date_text"):
        score += 0.3
    if data.get("description") or data.get("og_description"):
        score += 0.15
    if data.get("registration_url"):
        score += 0.15
    if data.get("api_url"):
        score += 0.1
    if "sitemap" in source_method:
        score += 0.1
    return min(score, 1.0)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading classification and partners...")
    classifications = load_classification()
    partners = load_partners()

    # Only process tiers 1A, 1B, 1C, 2, 3 (skip tier 4 for now)
    processable = [s for s in classifications if s["tier"] in ("1A", "1B", "1C", "2", "3")]
    print(f"Processing {len(processable)} domains (tiers 1A-3, skipping tier 4)...")

    all_records = []
    domain_stats = []

    for i, site in enumerate(processable):
        domain = site["domain"]
        records = process_domain(site, partners)
        all_records.extend(records)

        if records:
            with_dates = sum(1 for r in records if r.start_date)
            with_desc = sum(1 for r in records if r.description)
            with_reg = sum(1 for r in records if r.registration_url)
            domain_stats.append({
                "domain": domain,
                "tier": site["tier"],
                "total": len(records),
                "with_dates": with_dates,
                "with_desc": with_desc,
                "with_reg": with_reg,
            })

        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(processable)} domains... ({len(all_records)} records)")

    print(f"\nTotal records extracted: {len(all_records)}")

    # Write JSON
    json_path = OUTPUT_DIR / "events_all.json"
    with open(json_path, "w") as f:
        json.dump([asdict(r) for r in all_records], f, indent=2)
    print(f"Written to {json_path}")

    # Write CSV
    csv_path = OUTPUT_DIR / "events_all.csv"
    if all_records:
        fieldnames = list(asdict(all_records[0]).keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for rec in all_records:
                writer.writerow(asdict(rec))
    print(f"Written to {csv_path}")

    # Summary
    print(f"\n--- Extraction Summary ---")
    total = len(all_records)
    with_title = sum(1 for r in all_records if r.title)
    with_date = sum(1 for r in all_records if r.start_date)
    with_desc = sum(1 for r in all_records if r.description)
    with_reg = sum(1 for r in all_records if r.registration_url)
    with_api = sum(1 for r in all_records if r.api_url)

    print(f"Total events: {total}")
    print(f"  With title:        {with_title} ({100*with_title//max(total,1)}%)")
    print(f"  With date:         {with_date} ({100*with_date//max(total,1)}%)")
    print(f"  With description:  {with_desc} ({100*with_desc//max(total,1)}%)")
    print(f"  With registration: {with_reg} ({100*with_reg//max(total,1)}%)")
    print(f"  With API URL:      {with_api} ({100*with_api//max(total,1)}%)")

    # Tier breakdown
    tier_stats = {}
    for r in all_records:
        # Find tier from classification
        site = next((s for s in classifications if s["domain"] == r.domain), None)
        tier = site["tier"] if site else "?"
        tier_stats.setdefault(tier, {"total": 0, "with_date": 0, "with_desc": 0})
        tier_stats[tier]["total"] += 1
        if r.start_date:
            tier_stats[tier]["with_date"] += 1
        if r.description:
            tier_stats[tier]["with_desc"] += 1

    print(f"\nBy tier:")
    for tier in sorted(tier_stats.keys()):
        s = tier_stats[tier]
        print(f"  Tier {tier}: {s['total']} events, {s['with_date']} with dates, {s['with_desc']} with descriptions")

    # Top domains by record count
    print(f"\nTop domains by event count:")
    for ds in sorted(domain_stats, key=lambda x: -x["total"])[:20]:
        print(f"  {ds['domain']} (Tier {ds['tier']}): {ds['total']} events, "
              f"{ds['with_dates']} dated, {ds['with_desc']} described, {ds['with_reg']} with registration")


if __name__ == "__main__":
    main()

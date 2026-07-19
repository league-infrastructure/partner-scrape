#!/usr/bin/env python3
"""
Export demo_events.json to the stem-ecosystem site's opportunities.json schema.

Reads:  dev/output/demo_events.json          (built by build_demo.py)
        <site>/src/data/partners.json        (for partner id/logo/geo joins)
Writes: <site>/src/data/opportunities.json   (upcoming events, site schema)
        <site>/src/data/scrape-meta.json     ({"last_updated": ...})

Only upcoming calendar events are exported. Recurring events (same org +
title) are collapsed into a single record spanning first-to-last date, with
the repeat count noted in `availability`.

Usage:
    python dev/export_site.py [--site-dir ../stem-ecosystem] [--dry-run]
"""

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DEFAULT_SITE_DIR = Path(__file__).resolve().parents[2] / "stem-ecosystem"

# TZ offset used when embedding times so the site's Date parsing displays the
# correct calendar day in San Diego. Dates are display-only on the site.
TZ = "-07:00"

AREA_KEYWORDS = [
    (r"\b(marine|ocean|aquarium|shark|whale|dolphin|turtle|fish|tide\s*pool|bird|wildlife|animal|insect|bug|reptile|zoo)\b",
     "Biology / LifeSciences"),
    (r"\b(ecolog|environment|conservation|climate|recycl|compost|watershed|garden|farm|nature|habitat|creek|lagoon|river)\b",
     "Earth Science/Ecology"),
    (r"\b(coding|code|program(?:ming)?|computer|robot|scratch|python|minecraft|cyber|video game)\b",
     "Coding/Computer Science/Cyber Security"),
    (r"\b(engineer|maker|build|lego|3d print|circuit|invention|design challenge)\b",
     "Engineering"),
    (r"\b(astronomy|planetarium|telescope|space|rocket|star|planet)\b",
     "Physical Science"),
    (r"\b(math|algebra|geometry)\b", "Mathematics"),
    (r"\b(chemistry|chemical)\b", "Chemistry"),
    (r"\b(physics)\b", "Physics"),
]

AGE_KEYWORDS = [
    (r"\b(famil(?:y|ies)|all ages)\b", "Family"),
    (r"\b(toddler|preschool|pre-k|ages? [0-5]\b)\b", "Pre-K"),
    (r"\b(teen|high school|grades? 9)\b", "Grades 9-12"),
    (r"\b(middle school|tween|grades? 6)\b", "Grades 6-8"),
    (r"\b(adult)\b", "Adult"),
]


def slugify(text: str) -> str:
    return re.sub(r"^_+|_+$", "", re.sub(r"[^a-z0-9]+", "_", text.lower()))


def norm_name(name: str) -> str:
    """Normalize an org name for matching ("The Living Coast..." == "Living Coast...")."""
    n = re.sub(r"[^a-z0-9 ]", "", name.lower())
    n = re.sub(r"^the ", "", n.strip())
    return re.sub(r"\s+", " ", n)


def load_site_partners(site_dir: Path) -> dict:
    partners = json.loads((site_dir / "src/data/partners.json").read_text())
    by_norm = {}
    for p in partners:
        by_norm.setdefault(norm_name(p.get("name", "")), p)
    return by_norm


def map_cost(cost_text: str) -> str:
    """Map free-text cost to the site's cost_range taxonomy where possible."""
    if not cost_text:
        return ""
    t = cost_text.strip().lower()
    if "free" in t or t in ("$0", "0", "$0.00"):
        return "Free"
    amounts = [float(a) for a in re.findall(r"\$\s*(\d+(?:\.\d{1,2})?)", cost_text)]
    if amounts:
        low = min(amounts)
        if low == 0:
            return "Free"
        for cap, label in [(25, "Less than $25"), (50, "Less than $50"),
                           (100, "Less than $100"), (200, "Less than $200")]:
            if low < cap:
                return label
        return "Greater than $200"
    # Unparseable but short enough to display as-is ("Included with admission")
    return cost_text if len(cost_text) <= 40 else ""


def map_time_of_day(start_time: str, all_day: bool) -> list:
    if all_day:
        return ["All Day"]
    m = re.match(r"(\d{1,2})(?::(\d{2}))?(?::\d{2})?\s*([ap]m)?", (start_time or "").strip(), re.I)
    if not m:
        return []
    hour = int(m.group(1))
    ampm = (m.group(3) or "").lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    if hour < 12:
        return ["Morning"]
    if hour < 17:
        return ["Afternoon"]
    return ["Evening"]


def tag_by_keywords(text: str, rules: list) -> list:
    found = []
    for pattern, label in rules:
        if re.search(pattern, text, re.I) and label not in found:
            found.append(label)
    return found


def iso_datetime(day: str, time_text: str) -> str:
    """Combine a YYYY-MM-DD day and optional '9:00 am' time into ISO with offset."""
    hour, minute = 12, 0  # noon keeps date-only values on the right calendar day
    m = re.match(r"(\d{1,2}):(\d{2})(?::\d{2})?\s*([ap]m)?", (time_text or "").strip(), re.I)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        ampm = (m.group(3) or "").lower()
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
    return f"{day}T{hour:02d}:{minute:02d}:00{TZ}"


def collapse_recurring(events: list) -> list:
    """Merge instances of the same (org, title) into one record with a date range."""
    groups = defaultdict(list)
    for e in events:
        groups[(e["organization"], norm_name(e["title"]))].append(e)

    collapsed = []
    for instances in groups.values():
        instances.sort(key=lambda e: e["start_date"])
        base = max(instances, key=lambda e: len(e.get("description", "")))
        rec = dict(base)
        rec["start_date"] = instances[0]["start_date"]
        rec["start_time"] = instances[0].get("start_time", "")
        last = max(e.get("end_date") or e["start_date"] for e in instances)
        rec["end_date"] = last if last != rec["start_date"] else instances[0].get("end_date", "")
        rec["_repeat_count"] = len(instances)
        collapsed.append(rec)
    return collapsed


def build_opportunity(e: dict, partners_by_norm: dict, today: str) -> dict:
    partner = partners_by_norm.get(norm_name(e.get("organization", ""))) or {}
    partner_name = partner.get("name") or e.get("organization", "")

    text = " ".join([e.get("title", ""), e.get("description", ""),
                     " ".join(e.get("categories", []) or []),
                     " ".join(e.get("tags", []) or [])])

    times = " – ".join(t for t in [e.get("start_time"), e.get("end_time")] if t)
    availability_parts = [times] if times else []
    if e.get("_repeat_count", 1) > 1:
        availability_parts.append(f"Repeats {e['_repeat_count']} times through {e.get('end_date') or e['start_date']}")

    return {
        "slug": f"{slugify(e.get('organization', ''))[:40]}_{slugify(e.get('title', ''))[:60]}_{e['start_date'].replace('-', '')}",
        "title": e.get("title", ""),
        "partner_name": partner_name,
        "partner_id": partner.get("id"),
        "description": e.get("description", ""),
        "link": e.get("registration_url") or e.get("page_url", ""),
        "availability": "; ".join(availability_parts),
        "date_start": iso_datetime(e["start_date"], e.get("start_time")),
        "date_end": iso_datetime(e["end_date"], e.get("end_time")) if e.get("end_date") else "",
        "age_grade_level": tag_by_keywords(text, AGE_KEYWORDS),
        "cost_range": map_cost(e.get("cost", "")),
        "time_of_day": map_time_of_day(e.get("start_time", ""), e.get("all_day", False)),
        "opportunity_type": "Out-of-school Programs",
        "areas_of_interest": tag_by_keywords(text, AREA_KEYWORDS) or ["General Science"],
        "specific_attention": [],
        "financial_support": "No",
        "ngss_aligned": "No",
        "location": e.get("location") or partner.get("location", ""),
        "latitude": str(partner.get("latitude", "")) if not e.get("latitude") else str(e["latitude"]),
        "longitude": str(partner.get("longitude", "")) if not e.get("longitude") else str(e["longitude"]),
        "contact_name": "",
        "contact_email": "",
        "contact_phone": "",
        "logo_src": partner.get("logo_src", ""),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, default=DEFAULT_SITE_DIR)
    parser.add_argument("--dry-run", action="store_true", help="Print summary, write nothing")
    args = parser.parse_args()

    demo = json.loads((OUTPUT_DIR / "demo_events.json").read_text())
    partners_by_norm = load_site_partners(args.site_dir)
    today = date.today().isoformat()

    upcoming = [e for e in demo["calendar_events"]
                if (e.get("end_date") or e.get("start_date", "")) >= today]
    print(f"Calendar events: {len(demo['calendar_events'])} total, {len(upcoming)} upcoming")

    collapsed = collapse_recurring(upcoming)
    print(f"After collapsing recurring: {len(collapsed)}")

    opportunities = [build_opportunity(e, partners_by_norm, today) for e in collapsed]
    opportunities.sort(key=lambda o: o["date_start"])

    # De-duplicate slugs (same org+title on the same day from different sources)
    seen = {}
    for o in opportunities:
        if o["slug"] in seen:
            seen[o["slug"]] += 1
            o["slug"] += f"_{seen[o['slug']]}"
        else:
            seen[o["slug"]] = 1

    matched = sum(1 for o in opportunities if o["partner_id"])
    orgs = sorted({o["partner_name"] for o in opportunities})
    print(f"Opportunities: {len(opportunities)} from {len(orgs)} orgs "
          f"({matched} linked to site partners)")
    for org in orgs:
        n = sum(1 for o in opportunities if o["partner_name"] == org)
        print(f"  {org}: {n}")

    if args.dry_run:
        return

    out_path = args.site_dir / "src/data/opportunities.json"
    out_path.write_text(json.dumps(opportunities, indent=1, ensure_ascii=False))
    print(f"\nWrote {out_path}")

    meta_path = args.site_dir / "src/data/scrape-meta.json"
    meta_path.write_text(json.dumps(
        {"last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}))
    print(f"Wrote {meta_path}")


if __name__ == "__main__":
    main()

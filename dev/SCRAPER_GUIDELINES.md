# Production Scraper Guidelines & Discoveries

## Overview

This document captures what we learned analyzing 144 partner website mirrors (~40GB)
and extracting 7,000+ event/program records. It provides a roadmap for building an
incremental production scraper that can maintain a live STEM events calendar.

### Current Extraction Results (as of 2026-04-09)

| Metric | Count |
|--------|-------|
| Total events extracted | 7,083 |
| Calendar events (with real dates) | 2,196 |
| Program listings (undated) | 1,136 |
| Upcoming events (Apr 2026+) | 1,768 |
| Organizations represented | 65 |
| Date extraction rate | 57% |
| Description coverage | 81% |

---

## 1. Site Landscape

### Platform Distribution (144 sites)

| Platform   | Count | Notes |
|-----------|-------|-------|
| WordPress | 49    | Most valuable — plugins give structured data |
| Other/Custom | 44 | Mix of static sites, custom CMSes |
| Unknown   | 18    | Couldn't detect from index page |
| Drupal    | 13    | Standard patterns, OK to scrape |
| Squarespace | 10  | Good meta tags, limited sitemaps |
| Wix       | 9     | Client-rendered HTML — mostly empty in mirrors |
| Google Sites | 1  | Minimal content |

### Tier Classification

| Tier | Sites | Events Found | Strategy |
|------|-------|-------------|----------|
| 1A — Event sitemaps + plugins | 14 | 619 | Best: use plugin APIs or parse event sitemaps |
| 1B — Program/course sitemaps | 9 | 757 | Parse program sitemaps, generic extraction |
| 1C — Wix event sitemaps | 3 | 58 | Limited: sitemap metadata + URL slugs |
| 2 — Events in general sitemaps | 67 | 2,480 | Filter sitemap URLs by path pattern |
| 3 — No sitemaps, dir scan | 23 | 2,495 | Walk filesystem for event-like directories |
| 4 — No obvious events | 28 | skipped | Needs keyword search or manual review |

### Key Discovery: 72% of sites have sitemaps

100 of 144 mirrors contain XML sitemaps. These are small (KB-sized) files that
list every page on the site with lastmod timestamps. **Sitemaps should be the
primary discovery mechanism** — fetch them first, diff against previous versions,
and only re-scrape pages that changed.

---

## 2. High-Value Data Sources

### Tribe Events Calendar REST API (5 sites, 428 events)

**This is the single best data source.** Five WordPress sites use The Events Calendar
plugin, which exposes a public REST API:

```
GET /wp-json/tribe/events/v1/events/?per_page=50&page=1&status=publish
```

**Sites with TEC API:**
| Domain | API Base | Events |
|--------|----------|--------|
| coastalrootsfarm.org | `https://coastalrootsfarm.org/wp-json/tribe/events/v1/events/` | 15 |
| www.thelivingcoast.org | `https://www.thelivingcoast.org/wp-json/tribe/events/v1/events/` | 345 |
| eefkids.org | `https://eefkids.org/wp-json/tribe/events/v1/events/` | 1 |
| www.cleansd.org (ilacsd) | `https://www.cleansd.org/wp-json/tribe/events/v1/events/` | 50 |
| oceanconnectors.org | `https://oceanconnectors.org/wp-json/tribe/events/v1/events/` | 17 |

**API returns clean JSON with:**
- `title`, `description`, `excerpt`
- `start_date`, `end_date` (ISO datetime with timezone)
- `start_date_details`, `end_date_details` (year, month, day, hour, minute)
- `venue` (name, address, city, state, zip, country, lat/lng)
- `organizer` (name, email, phone, website)
- `cost`, `cost_details`
- `categories`, `tags`
- `image` (url, sizes)
- `url` (canonical page URL)
- `all_day` flag

**How to detect TEC sites:** Check `X-Tec-Api-Root` response header on any page.
It appears on every page of a TEC-enabled site (e.g., even the homepage). The
header value is the API URL for that specific page's event. The base API URL is
everything up to the event ID.

**Pagination:** The API returns `total`, `total_pages`, and supports `?page=N`.
Always paginate with `per_page=50` to get all events.

**Recommended approach for TEC sites:**
1. Probe `https://{domain}/wp-json/tribe/events/v1/events/?per_page=1` to check availability
2. Paginate through all events
3. Store as structured JSON — no HTML parsing needed
4. Re-fetch on a schedule (weekly?) to catch new events
5. Use `?start_date=now` to get only future events

### WordPress REST API (broader, ~49 sites)

Many WordPress sites expose `/wp-json/wp/v2/` even without TEC. This gives
access to posts, pages, and custom post types:

```
GET /wp-json/wp/v2/posts?per_page=100
GET /wp-json/wp/v2/pages?per_page=100
```

This is less structured than TEC (no date/venue fields) but still better than
HTML parsing. Worth probing for all WordPress sites.

### Sitemap-Based Discovery (100 sites)

For sites without APIs, sitemaps are the next best thing:

1. **Fetch sitemap_index.xml** (or sitemap.xml) — typically < 50KB
2. **Identify event-related child sitemaps** by filename pattern:
   - `tribe_events-sitemap.xml` → The Events Calendar
   - `event-sitemap.xml`, `events-sitemap.xml` → Custom event post types
   - `event-pages-sitemap.xml` → Wix events
   - `program-sitemap.xml`, `course-sitemap.xml` → Program/course listings
   - `ajde_events-sitemap.xml` → EventON plugin
   - `wp-sitemap-posts-stec_event-1.xml` → STEC plugin
3. **Extract URLs** from event sitemaps — each `<url><loc>` is an event page
4. **Diff against previous sitemap** — only fetch new/changed URLs based on `<lastmod>`

---

## 3. Site-Specific Extractors Built

We built dedicated extractors for the highest-volume site types. Each one targets
the specific DOM structure of that platform.

### BiblioCommons (sdcl.org) — 1,173 events, 100% dated

San Diego County Library uses BiblioCommons for event listings. Key selectors:

| Field | Source | Notes |
|-------|--------|-------|
| Title | `.event-summary-title .visible-print` | Clean title without breadcrumb |
| Date | `<time datetime="2026-12-09T13:30">` | ISO datetime in `time` elements |
| Time | `.event-time` | "1:30 PM – 3:30 PM" |
| Location | `.event-location` | Library branch name |
| Description | `.event-description-content` | Clean text |
| Audience | `.event-facets` | "Adults", "Teens", "Older Adults 55+" |

**Note:** The `.event-date` div is empty (JavaScript-rendered), but `<time>` elements
have ISO datetimes server-side. Always prefer `<time datetime>` over CSS class text.

### Drupal Events (sandiego.gov) — 140 events, 100% dated

City of San Diego uses Drupal. Key extraction strategy:

| Field | Source | Notes |
|-------|--------|-------|
| Title | Third `h1` (skip `visually-hidden` and department headings) | First h1 is "City of San Diego", second is department |
| Date | URL query string `?event-date=Saturday,%20April%204,%202026` | 114 of 140 events have this |
| Date fallback | Body text pattern "Weekday, Month DD, YYYY, time" | In `.node__content` |
| Description | `.node__content` | First few lines of content |

### Title-Date Sites (olivewoodgardens.org) — 644 dated of 1,532

Some sites embed dates in the event title or URL slug:
- Title pattern: `"Chefcitos (February 14th, 2026 – 10AM)"`
- URL slug pattern: `/events/open-gardens-2026-02-21/`

The extractor parses dates from both sources and cleans the title by removing
the date portion.

### Generic Extractor (all other sites)

The fallback extractor tries strategies in priority order:
1. **JSON-LD Event schema** (`<script type="application/ld+json">`) — highest quality
2. **`<time datetime="...">`** elements — ISO datetimes
3. **OG meta tags** — `og:title`, `og:description`, `og:image`
4. **Title-embedded dates** — regex for "Month DDth, YYYY" patterns
5. **Body text CSS classes** — `.entry-content`, `.node__content`, etc.
6. **Body text date regex** — scanning first 3000 chars for date patterns
7. **URL path dates** — `/event/name/2026-04-22/` patterns
8. **Registration link detection** — anchor text matching "register", "sign up", etc.

---

## 4. HTML Extraction Patterns (WordPress)

### WordPress + The Events Calendar (HTML fallback)

CSS selectors that work across TEC sites:

| Field | Selector | Notes |
|-------|----------|-------|
| Title | `h1.entry-title` | Reliable across all TEC themes |
| Date/Time | `div.crf-event-details` | Site-specific class (coastalrootsfarm) |
| Date/Time | `.tribe-events-schedule` | Standard TEC class |
| Venue | `.tribe-venue` | Standard TEC class |
| Description | `.entry-content` | Standard WordPress |
| Registration | `a` containing "register"/"sign up"/"rsvp"/"tickets" | Link text search |

**Date format:** TEC renders dates as text like "Sunday, January 18 @ 1:00 pm to 2:30 pm".
Note: year is often missing. Infer from sitemap `<lastmod>` or `article:modified_time`.

### WordPress + Yoast SEO (generic)

All Yoast-enabled sites have consistent `<meta>` tags:

```html
<meta property="og:title" content="Event Title - Site Name" />
<meta property="og:description" content="Event description..." />
<meta property="og:image" content="https://..." />
<meta property="article:modified_time" content="2026-03-13T21:20:21+00:00" />
```

These are reliable for title, description, and image. `article:modified_time` is
NOT the event date — it's when the page was last edited. Don't use it as event date
unless there's no alternative (and mark confidence low).

### Wix Sites

**Problem:** Wix renders content client-side with JavaScript. Mirrored HTML has
nearly empty `<body>` tags — the actual content is in JSON blobs that get hydrated.

**What works:**
- `<title>` and `<meta>` tags (og:title, description) are server-rendered
- Sitemap `<image:title>` attributes contain event names
- URL slugs sometimes encode dates: `bill-the-bug-guy-2026-04-11-10-00`

**For production:** Consider using a headless browser (Playwright/Puppeteer) for
the 9 Wix sites, or check if Wix's server-side rendering mode can be triggered
with specific User-Agent headers.

### Generic HTML

For sites without known plugins, extract in priority order:
1. `<meta property="og:title">` → title
2. `<meta property="og:description">` or `<meta name="description">` → description
3. `h1` → title (fallback)
4. `.entry-content`, `.post-content`, `.article-content` → body text
5. Links with text matching "register"/"sign up"/"tickets" → registration URL
6. Body text regex for month+day patterns → dates (low confidence)

---

## 5. Date Extraction Challenges

Date extraction is the biggest quality gap. Current results:

| Source | Events | With Real Date | Rate |
|--------|--------|---------------|------|
| TEC API | 428 | 428 | 100% |
| HTML text parsing | ~1,000 | ~670 | 67% |
| URL date patterns | ~300 | ~300 | 100% |
| All others | ~5,000 | ~0 | 0% |

### Date formats encountered (in order of reliability)

1. **ISO datetime from API** — `2026-04-22 16:00:00` — perfect
2. **URL path dates** — `/event/name/2026-04-22/` — reliable
3. **"Month DD, YYYY"** — "May 13, 2026" — reliable
4. **"Weekday, Month DD @ time"** — "Sunday, January 18 @ 1:00 pm" — good but missing year
5. **"Month DD" (no year)** — "May 9" — needs year inference
6. **"Month YYYY" (no day)** — "February 2026" — low precision

### Year inference strategy

When a date has no year (patterns 4-5 above):
- Check sitemap `<lastmod>` — if the page was modified in 2026, the event is likely 2026
- Check URL path — `/2026/` or `/2025/` in the URL
- Check `article:modified_time` meta tag
- Default to current year or next occurrence of that month

### Recommendations for improving date extraction

1. **LLM extraction pass:** For the ~5,000 events with descriptions but no parsed
   dates, use an LLM (Claude) to extract dates from the description text. Many
   descriptions contain dates in narrative form: "Join us on May 13th for..."
   Cost estimate: ~$2-5 for the full corpus at Haiku pricing.

2. **JSON-LD parsing:** Some sites embed `<script type="application/ld+json">`
   with Event schema. We don't currently parse these — should be added.

3. **iCal feeds:** Line 47 of coastalrootsfarm.org's HTML reveals an iCal feed:
   `<link rel="alternate" type="text/calendar" href=".../?ical=1" />`
   These may exist on other TEC sites and provide structured event data.

---

## 6. Production Architecture

### Recommended scraping pipeline

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  1. Probe APIs  │────▶│ 2. Fetch Sitemaps │────▶│ 3. Diff Sitemaps │
│  (TEC, WP REST) │     │  (100 sites)      │     │  (new/changed)   │
└─────────────────┘     └──────────────────┘     └──────────────────┘
                                                          │
                              ┌────────────────────────────┘
                              ▼
                    ┌──────────────────┐     ┌──────────────────┐
                    │ 4. Fetch Changed │────▶│ 5. Extract Data  │
                    │    Pages Only    │     │  (per-site rules) │
                    └──────────────────┘     └──────────────────┘
                                                      │
                              ┌────────────────────────┘
                              ▼
                    ┌──────────────────┐     ┌──────────────────┐
                    │ 6. LLM Enrichment│────▶│ 7. Merge & Dedup │
                    │  (optional)      │     │  (output JSON/CSV)│
                    └──────────────────┘     └──────────────────┘
```

### Step details

**Step 1 — Probe APIs (5 min, 5 sites)**
- Hit TEC API endpoints for 5 known sites
- Optionally probe `/wp-json/wp/v2/` for all WordPress sites
- Get structured JSON — no HTML parsing needed
- This covers 428+ events with 100% quality

**Step 2 — Fetch sitemaps (10 min, 100 sites)**
- For each domain with sitemaps, fetch only `sitemap_index.xml` or `sitemap.xml`
- Total bandwidth: ~5MB (sitemaps are small XML files)
- Parse and store locally

**Step 3 — Diff sitemaps (seconds)**
- Compare new sitemaps against stored versions
- Identify URLs with new/changed `<lastmod>` dates
- Focus on event-related sitemaps and URL patterns

**Step 4 — Fetch changed pages only (variable)**
- Only fetch the pages that changed since last run
- This is the key efficiency win: instead of 40GB full mirrors, fetch maybe 1-10MB
- Respect robots.txt and rate limits (1 req/sec per domain)

**Step 5 — Extract data (seconds)**
- Apply per-site extraction rules based on tier/plugin classification
- Use the appropriate extractor (tribe_events, wix, generic, etc.)

**Step 6 — LLM enrichment (optional, ~$2-5)**
- For events missing dates/details, send description to Claude Haiku
- Ask for structured extraction: title, date, time, location, registration info
- Only process new/changed events to keep costs low

**Step 7 — Merge & dedup**
- Merge API + HTML extraction results
- Dedup by URL and title+date+org
- Output to JSON/CSV for the calendar frontend

### Scheduling

- **Daily:** TEC API fetch (lightweight, highest-quality data)
- **Weekly:** Full sitemap refresh + diff + selective page fetch
- **Monthly:** Full mirror refresh for sites without sitemaps (Tier 3-4)

### Bandwidth estimates

| Operation | Frequency | Bandwidth |
|-----------|-----------|-----------|
| TEC API fetch (5 sites) | Daily | ~500KB |
| Sitemap refresh (100 sites) | Weekly | ~5MB |
| Changed page fetch | Weekly | ~10-50MB |
| Full mirror (Tier 3-4) | Monthly | ~2-5GB |

---

## 7. Incremental Improvement Roadmap

### Phase 1 — Ship MVP (done)
- [x] TEC API integration (5 sites, 428 events)
- [x] Sitemap-based HTML extraction (100+ sites)
- [x] BiblioCommons extractor (sdcl.org, 1173 events with dates)
- [x] Drupal event extractor (sandiego.gov, 140 events with dates)
- [x] Title-date extraction (olivewoodgardens, 644 dated events)
- [x] JSON-LD Event schema parsing in generic extractor
- [x] `<time datetime>` element parsing
- [x] Demo output (2,196 calendar events, 1,136 programs, 65 orgs)
- [ ] Deploy as scheduled job (daily API, weekly sitemap)

### Phase 2 — Expand date coverage
- [ ] Add iCal feed discovery and parsing
- [ ] LLM extraction pass for events with descriptions but no dates (~3,900 remaining)
- [ ] Probe WordPress REST API on all 49 WordPress sites
- Target: 4,000+ dated events

### Phase 3 — Expand site coverage
- [ ] Headless browser for 9 Wix sites
- [ ] Manual review of Tier 4 sites (28 sites) — some may not have events
- [ ] Add new partner sites as they're onboarded
- Target: 100+ organizations with events

### Phase 4 — Quality & freshness
- [ ] Automatic stale event detection (remove past events)
- [ ] Event deduplication across organizations (co-hosted events)
- [ ] Cost/price extraction improvement
- [ ] Age/grade level extraction ("grades 3-5", "ages 8-12")
- [ ] Geographic enrichment (geocode venue addresses)
- [ ] Category taxonomy (camps, classes, workshops, field trips, etc.)

---

## 8. Per-Site Notes

### Sites requiring special handling

| Domain | Issue | Workaround |
|--------|-------|------------|
| www.challenge-island.com | ~60 franchise locations with separate sitemaps | Filter to San Diego Coastal location only |
| www.cleansd.org / www.ilacsd.org | Different domains (redirect) | API uses cleansd.org, mirror uses ilacsd.org |
| www.thelivingcoast.org | 345 events, many are daily recurring presentations | Dedup by title, show as recurring |
| www.thermofisher.com | Huge citation sitemaps (1000s of XML files) | Skip — corporate site, not event-focused |
| www.viasat.com | Multi-locale sitemaps (es-mx, pt-br, etc.) | Filter to English only |
| www.olivewoodgardens.org | 1500+ "event" pages, many are blog posts | Needs better filtering — not all are events |
| www.barnesandnoble.com | No sitemaps, corporate site | Skip — B&N storefront, not an event source |

### Highest-value sites to prioritize

1. **coastalrootsfarm.org** — TEC API, 15 upcoming events, farm/nature education
2. **www.thelivingcoast.org** — TEC API, 345 events, wildlife education
3. **www.ilacsd.org / cleansd.org** — TEC API, 50 events, environmental cleanups
4. **oceanconnectors.org** — TEC API, 17 events with cost data, marine science
5. **www.fleetscience.org** — Fleet Science Center, no sitemap but likely has events (Tier 4)
6. **sandiegoairandspace.org** — Air & Space Museum, 272 program pages, no dates yet
7. **www.sdnhm.org** — Natural History Museum, some dated events
8. **www.jointheleague.org** — LEAGUE of Amazing Programmers, coding classes with dates

---

## 9. Key Files Reference

| File | Purpose |
|------|---------|
| `dev/inventory_sitemaps.py` | Inventory all sitemaps across mirrors |
| `dev/classify_sites.py` | Classify domains into tiers |
| `dev/sample_event_pages.py` | Test extraction selectors |
| `dev/extract_events.py` | Main HTML extraction pipeline |
| `dev/fetch_tec_api.py` | TEC REST API fetcher |
| `dev/merge_events.py` | Merge API + HTML data |
| `dev/build_demo.py` | Build demo-quality output |
| `dev/lib/url_resolver.py` | URL-to-mirror-path mapping |
| `dev/lib/sitemap_parser.py` | Local sitemap XML parsing |
| `dev/output/demo_events.json` | Demo output (calendar + programs) |
| `dev/output/demo_calendar.csv` | Calendar events as flat CSV |
| `dev/output/site_classification.csv` | All 144 domains classified |
| `dev/output/tec_api_events.json` | Raw TEC API event data |
| `scraper/spiders/mirror_spider.py` | Original full-mirror spider |
| `data/partners_viable.csv` | Partner organization list |

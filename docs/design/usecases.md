# Use Cases — San Diego STEM Ecosystem Event Engine

Actors:
- **Engine** — the automated scraping/normalization/export pipeline (this repo).
- **Operator** — the League maintainer running or scheduling the engine.
- **Visitor** — an end user (family, student, educator) browsing the site.
- **Fleet** — the Fleet Science Center as host/decision-maker.

---

## UC-001 — Ingest events from a structured API (TEC / Localist)

- **Actor:** Engine
- **Preconditions:** A source is registered with an API adapter type and base
  URL; network available.
- **Main flow:**
  1. Probe the API endpoint (e.g. `…/wp-json/tribe/events/v1/events/?per_page=1`).
  2. Paginate through all events, requesting only future events where the API
     supports it.
  3. Map API fields (title, start/end, venue, organizer, cost, categories,
     image, url) directly into internal event records.
  4. Write raw response to the scrape cache.
- **Postconditions:** Structured, dated event records exist for the source
  with no HTML parsing.
- **Error flows:** API absent → mark source for sitemap/HTML fallback. Rate
  limited → back off and retry. Schema drift → log and skip malformed items.

## UC-002 — Discover changed pages via sitemap diff

- **Actor:** Engine
- **Preconditions:** Source exposes an XML sitemap; a previous sitemap
  snapshot exists in the cache.
- **Main flow:**
  1. Fetch `sitemap_index.xml` / `sitemap.xml`.
  2. Identify event/program URLs by path and filename patterns.
  3. Diff against the previous snapshot by `<lastmod>`.
  4. Enqueue only new/changed URLs for fetching.
- **Postconditions:** Only changed pages are fetched; bandwidth stays small.
- **Error flows:** No prior snapshot → treat all event URLs as new. Malformed
  sitemap → fall back to full directory scan (Tier 3).

## UC-003 — Extract an event from a mirrored HTML page

- **Actor:** Engine
- **Preconditions:** A cached HTML page for a candidate event URL exists.
- **Main flow:**
  1. Select the extractor by detected platform (BiblioCommons, Drupal,
     TEC-HTML, title/URL-date, generic).
  2. Extract title, date(s), description, location, registration link, image
     in the extractor's priority order (JSON-LD → `<time>` → OG meta → URL
     date → body regex).
  3. Emit an internal event record with a per-field confidence.
- **Postconditions:** A candidate event record, possibly missing a date.
- **Error flows:** No date found → route to UC-004. Not actually an event
  (blog post) → drop by filter.

## UC-004 — Recover missing dates/fields via LLM extraction

- **Actor:** Engine
- **Preconditions:** An event record has a description but no reliable parsed
  date (or other missing structured fields).
- **Main flow:**
  1. Send description text to an LLM with a structured-extraction prompt.
  2. Parse returned date/time/location/registration/age/cost fields.
  3. Merge with existing record; mark provenance = LLM, confidence
     accordingly. Process only new/changed records to control cost.
- **Postconditions:** More records have usable dates and structured fields.
- **Error flows:** LLM returns nothing usable → leave undated (excluded from
  calendar export, may still appear as an undated program listing).

## UC-005 — Normalize a record into the site opportunity schema

- **Actor:** Engine
- **Preconditions:** An internal event record exists.
- **Main flow:**
  1. Map to the `opportunities.json` schema (§5 of specification).
  2. Derive `areas_of_interest`, `age_grade_level`, `time_of_day`,
     `cost_range` (keyword rules today; LLM later).
  3. Join to `partners.json` by normalized org name for id/logo/geo.
  4. Collapse recurring (org, title) instances into one dated range.
- **Postconditions:** A site-ready opportunity record.
- **Error flows:** No partner match → keep org name, no logo/geo. Unparseable
  cost → display raw or blank.

## UC-006 — Export upcoming opportunities to the site

- **Actor:** Engine / Operator
- **Preconditions:** Normalized records exist; site repo path known.
- **Main flow:**
  1. Filter to current + upcoming only.
  2. Deduplicate by slug (org + title + date).
  3. Write `opportunities.json` and bump `scrape-meta.json` last_updated in
     the site repo.
- **Postconditions:** Site data reflects the latest scrape; historical data
  excluded.
- **Error flows:** Site path missing → fail loudly. Zero upcoming events for
  a normally-productive source → warn (likely a broken adapter).

## UC-007 — Run the scheduled self-updating loop

- **Actor:** Operator (via scheduler)
- **Preconditions:** Automation configured with credentials to publish.
- **Main flow:**
  1. On schedule: API pulls (frequent) + sitemap diff/selective fetch
     (weekly).
  2. Extract → LLM-enrich → normalize → export (UC-001..006).
  3. Rebuild the static site and deploy.
  4. Update the visible "last updated" stamp; prune past events.
- **Postconditions:** The site is fresh with no per-event human effort.
- **Error flows:** A source fails → the run continues with the rest and
  reports the failure; the site never goes empty on one bad source.

## UC-008 — Add a new partner source

- **Actor:** Operator
- **Preconditions:** A new/updated partner org with a website.
- **Main flow:**
  1. Classify the site (platform, API, sitemap presence) into a tier.
  2. Register it with the right adapter and taxonomy defaults.
  3. Run once, validate output, add to the schedule.
- **Postconditions:** The source contributes events on subsequent runs.
- **Error flows:** No usable event data → mark Tier 4 for manual review.

## UC-009 — Fix the flagship-source gaps (Fleet, Birch Aquarium)

- **Actor:** Operator/Engine
- **Preconditions:** Fleet Science Center and Birch Aquarium currently yield
  zero events.
- **Main flow:**
  1. Build the Fleet event adapter (identify its events source/format).
  2. Complete the Birch/UCSD Localist adapter.
  3. Verify the host org's own events now appear in the directory.
- **Postconditions:** The Fleet's and Birch's events publish on the site.
- **Error flows:** Source format unsupported → escalate for a bespoke adapter.

## UC-010 — Feature League content and advertising

- **Actor:** Operator
- **Preconditions:** The League is registered as a partner org; site supports
  a sidebar ad slot.
- **Main flow:**
  1. Ensure League events are scraped and appear in the directory.
  2. Place League-owned advertising in the site's sidebar slot.
- **Postconditions:** League content and ads are present on the live site.
- **Error flows:** Ad slot not yet implemented in the site → track as a site
  repo requirement.

## UC-011 — Discover STEM company events and internships (extension)

- **Actor:** Engine/Operator
- **Preconditions:** A curated list of San Diego STEM companies exists.
- **Main flow:**
  1. For each company site, detect public events (open houses, tours, talks,
     career fairs) via the generic/HTML path.
  2. Detect internships/early-career roles (often on ATS platforms:
     Greenhouse, Lever, Workday).
  3. Map to the opportunity schema with an internship-aware
     `opportunity_type` and deadline-vs-event date semantics.
- **Postconditions:** Company events and internships appear as opportunities.
- **Error flows:** No structured source → skip rather than scrape noise.
- **Note:** Sourcing, detection, and schema changes for this use case are
  **open design questions** (specification §8, §10).

## UC-012 — Visitor finds a relevant opportunity

- **Actor:** Visitor
- **Preconditions:** The site is published with current data.
- **Main flow:**
  1. Visitor opens the Opportunities directory.
  2. Filters by area of interest, age/grade, cost, time of day, date.
  3. Opens a detail page and follows the registration link.
- **Postconditions:** The visitor reaches the partner's registration/info.
- **Error flows:** Stale/past event shown → pruning (UC-007) should prevent
  this; dead registration link → flag source for re-scrape.

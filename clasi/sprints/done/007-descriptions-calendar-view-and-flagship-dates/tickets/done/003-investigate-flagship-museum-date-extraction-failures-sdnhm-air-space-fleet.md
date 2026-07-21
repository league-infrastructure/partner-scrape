---
id: '003'
title: Investigate flagship museum date-extraction failures (SDNHM, Air & Space, Fleet)
status: done
use-cases:
- SUC-003
depends-on: []
github-issue: ''
issue: 14-flagship-museum-date-extraction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Investigate flagship museum date-extraction failures (SDNHM, Air & Space, Fleet)

## Description

Implements the investigation half of issue
`14-flagship-museum-date-extraction.md` and sprint 007's SUC-003. This
ticket produces a **diagnosis only** — no production code changes are
expected (a throwaway/exploratory script is fine if it helps, but must
not be committed). Ticket 004 (depends on this one) implements the fix.

**Why a separate investigation ticket**: a live, read-only diagnostic
run during sprint planning (2026-07-20, `curl` against the real sites,
no code changes) found that "date extraction fails" is **not one
uniform cause** — see sprint.md's Problem section and Architecture
Design Rationale for full detail. Confirm or refute each hypothesis
below against the actual pipeline behavior (not just raw `curl`) before
ticket 004 picks a fix mechanism.

**Starting hypotheses** (from planning-time diagnostics — confirm these
against real pipeline runs, don't just trust them):

- **Air & Space Museum** (`partner_scrape/registry/sources/sandiego-air-space.toml`,
  `generic_html`): `sitemap.xml`, `sitemap_index.xml`, `sitemap-index.xml`,
  and `wp-sitemap.xml` all returned HTTP 200 with the site's homepage
  HTML (soft-404/catch-all), not real sitemap XML, in a planning-time
  check. `partner_scrape/discovery/sitemap.py`'s root-element validation
  (`_SITEMAP_ROOT_TAGS`, sprint 005 hardening) should reject all of
  these — confirm by running Discovery for this source with logging
  and checking whether it resolves any candidate URLs at all. If it
  resolves zero, this is a Discovery problem, not a ladder problem —
  check whether a real sitemap exists at a non-standard path, or
  whether this source should move to `listing_html` (mirroring
  `fleet-science-center.toml`) off a real `/events`-style page.
- **SDNHM** (`sdnhm.toml`, `generic_html`): its `sitemap.xml` is real
  (892 URLs at planning time) and surfaces `/calendar/...` pages
  matching `discovery/sitemap.py`'s `EVENT_PATH_RE` — consistent with
  the issue's "39 raw events found." A sampled page
  (`/calendar/summer-camp/`) was a program/category landing page (not a
  single dated event instance): no JSON-LD, two bare `<time>` tags of
  unconfirmed attribute format, and body text mixing a genuine upcoming
  date with unrelated older dates. Confirm which ladder rung (if any)
  fires on pages like this via `partner_scrape/extract/ladder.py`'s
  `extract_fields()`, and what value it produces — is the body-regex
  rung (`_extract_body_regex`, first date match within the first 3000
  characters) grabbing a wrong/stale date on this kind of multi-date
  page?
- **Fleet Science Center** (`fleet-science-center.toml`,
  `listing_html`): a sampled page (`/events/camps`) had 20 valid ISO
  `<time datetime="...">` tags with real future dates — which
  `_extract_time_tags` (rung 2) should already parse — contradicting
  this TOML's own comment that Fleet's detail pages "carry no JSON-LD
  or `<time>` markup." Confirm whether this page (and others like it)
  actually exports correctly today, and whether the other ~10
  discovered URLs (e.g. `/events/candlelight-concerts`, which had zero
  `<time>` tags at planning time) are genuinely undated evergreen
  program pages (correctly excluded) or need different handling.

**Method**: run the pipeline per-source with logging
(`uv run partner-scrape --source sdnhm --no-enrich --dry-run -v`,
substituting `sandiego-air-space` / `fleet-science-center`) and inspect
what Discovery resolves and what the ladder extracts. Add temporary
logging/prints as needed; do not leave debug scaffolding in committed
code.

## Acceptance Criteria

- [x] For each of SDNHM, Air & Space, and Fleet, the "Findings" section
      below is filled in with: what Discovery actually resolves (URL
      count and whether they're real event/instance pages), what the
      ladder actually extracts (which rung fires, what value), and
      which fix mechanism applies — `fetch_strategy = "headless"`
      (JS-rendering hides the date from raw fetch), a Discovery
      config/pattern/adapter-type change (wrong or zero candidate
      URLs), a targeted ladder heuristic fix (wrong rung selection on a
      multi-date page), or "already correct, no fix needed."
- [x] No production code is committed by this ticket (diagnosis only)
      — any exploratory script used is discarded, not committed.
- [x] `uv run pytest` still passes (trivially — no production changes
      expected).

## Findings

*(Filled in 2026-07-20/21 via live pipeline runs — `uv run partner-scrape
--source <id> --no-enrich --dry-run -v` — plus a throwaway diagnostic
script that called `discovery.sitemap.discover_changed_urls` /
`discovery.listing.discover_via_listing` and `extract.ladder.
extract_fields` directly against real fetched pages, using the same
`PoliteFetcher`/cache the pipeline uses. Script was discarded per this
ticket's Acceptance Criteria, not committed.)*

**Cross-source pattern (the actual root cause for all three sources'
missed-but-real dates)**: `extract/ladder.py`'s `_extract_body_regex`
(rung 6) computes `tree.find(".//body").text_content()[:3000]` and
searches only that 3000-character prefix. Two compounding problems with
this on real pages: (1) `lxml`'s `text_content()` does **not** exclude
`<style>`/`<script>` element text, so inline CSS emitted before the page
content (common on all three sites' templates) burns a large chunk of
the 3000-char budget on invisible rule text; (2) each site repeats a
large boilerplate nav/header block on every page. On every page sampled
where a genuine, correctly-formatted "Month DD, YYYY" date was present
in the live body text, it landed at an offset of **3274–3806
characters** — just past the rung's fixed cutoff, every time:

| Source | URL | Real date found | Offset |
|---|---|---|---|
| Air & Space | `/calendar/event/kit-model-aviation-collectible-swap-meet-2026` | "SATURDAY June 13, 2026" | 8548 |
| SDNHM | `/calendar/summer-camp/` | "June 8–August 7, 2026" | 3725 |
| SDNHM | `/calendar/for-adults/` | "Friday, February 13, 2026" | 3758 |
| Fleet | `/events/annual-gala` | "Saturday, April 11, 2026" | 3274 |
| Fleet | `/events/sky-tonight` | "August 29, 2026" | 3806 |

Five independent pages, three different sites/CMSes, same failure shape.
This **refutes** the sprint's original body-regex hypothesis ("grabs a
wrong/stale date on a multi-date page") — on every sampled page the
rung found **nothing at all**, not a wrong value; the genuine date was
simply never inside its scan window. None of the three sites needed
headless rendering to see these dates — every date above was present in
the plain server-rendered HTML fetched by the ordinary (non-JS)
`PoliteFetcher`.

### SDNHM
- **Discovery result**: Correct, no fix needed. `sitemap_index.xml`
  returns HTTP 200 but fails XML/root-tag validation (logged: "returned
  status 200 but did not parse as sitemap XML (recognized root
  element); trying next candidate"); `sitemap.xml` succeeds and yields
  **39** URLs under `/calendar/...`, matching `EVENT_PATH_RE` — exactly
  the issue's reported "39 raw events found." Confirmed via live
  `--source sdnhm --no-enrich --dry-run -v` (`found=39`) and the
  diagnostic script (`Discovery resolved 39 URLs for sdnhm`).
- **Ladder result**: **0/39 pages produce a `start` field at all** —
  confirmed by running `extract_fields()` on every one of the 39 fetched
  pages (`has_start=0`). Root causes split into three groups:
  1. **The sprint's `<time>`-tag hypothesis is refuted.** The sampled
     `/calendar/summer-camp/` page does contain two
     `<time datetime="2015-03-29">` tags with stale dates ("March 9,
     2015", "August 29, 2014") — but they live inside an HTML
     **comment** (a dead "From the blog" widget block,
     `<!--<aside class="widget widget_recent_entries">...`). `lxml`
     correctly does not parse comment content as elements
     (`tree.iter("time")` returns 0 matches on this page, confirmed
     directly) — rung 2 never sees them, so there is no "wrong rung
     fires on a multi-date page" happening here at all.
  2. **The real, current+upcoming date is truncated by the 3000-char
     window** (see cross-source table above) on at least
     `/calendar/summer-camp/` ("June 8–August 7, 2026" at offset 3725,
     inside an `<h2>`) and `/calendar/for-adults/` ("Friday, February
     13, 2026" at offset 3758). No JSON-LD, no live `<time>` tag, and no
     `og:` date field exists on these pages — `og:title`/`og:description`
     are present and correct for title/description (rung 3 fires
     correctly for those fields), but OpenGraph carries no date field by
     design (per `_extract_opengraph`'s own docstring), so the body-regex
     rung is the *only* rung that could recover `start` here, and it's
     defeated by truncation, not by picking a wrong value.
  3. **Most of the 39 are genuinely undated, evergreen program landing
     pages** — sampled `/calendar/camp-o-saurus/`, `/calendar/nat-at-night/`,
     `/calendar/brunch/`, `/calendar/fossil-week/`,
     `/calendar/family-programs/family-days/`,
     `/calendar/family-programs/camps/`, `/calendar/public-programs/`,
     `/calendar/museum-month/` ("during the month of February", no
     specific day) — none contain a "Month DD, YYYY" pattern anywhere in
     the full body text (not just the 3000-char window). These are
     correctly excluded today and need no fix (SUC-003's Alternate
     Flow). One secondary, lower-confidence gap noted in passing:
     `/calendar/december-nights/` states "Friday, December 5 and
     Saturday, December 6" with no year token adjacent to the day
     (the year is implied, never stated near the date) — the current
     regex requires a 4-digit year immediately after the day, so this
     page would stay undated even after a window fix. Flagged for
     ticket 004's awareness, not counted as part of the primary fix.
- **Recommended fix mechanism**: **targeted ladder heuristic fix** to
  `_extract_body_regex` (not Discovery, not `fetch_strategy=headless`,
  not per-site selectors) — see "Cross-source recommendation" below.
  Discovery needs no change for this source.

### Air & Space Museum
- **Discovery result**: The sprint's specific hypothesis ("sitemaps
  return HTTP 200 serving the homepage, a soft-404") is **refuted by a
  live re-check**: `sitemap_index.xml`, `sitemap.xml`, `sitemap-index.xml`,
  and `wp-sitemap.xml` all return a clean **HTTP 404** today (verified
  via `curl -o /dev/null -w "%{http_code}"` on all four), not HTTP 200
  with catch-all HTML. `robots.txt` has no `Sitemap:` directive
  (confirmed). The **conclusion still holds** though the mechanism
  differs: `discovery.sitemap.discover_changed_urls` returns zero URLs
  either way ("No reachable sitemap for source 'sandiego-air-space'...")
  and the live pipeline run confirms **0 events found**
  (`--source sandiego-air-space --no-enrich --dry-run -v` →
  `found=0`). This is a pure Discovery-layer gap for the currently
  configured `generic_html`/sitemap-only adapter — the ladder is never
  reached at all today.
  A real, working alternative exists: `https://sandiegoairandspace.org/calendar`
  returns HTTP 200 and is a genuine events listing page linking to real
  per-event detail pages, e.g. `/calendar/event/kit-model-aviation-collectible-swap-meet-2026`
  and `/calendar/event/summer-camps-registration` — both match
  `discovery/sitemap.py`'s `EVENT_PATH_RE` (via the `calendar` and
  `event`/`events?` alternatives) and would be picked up by
  `discovery.listing.discover_via_listing` if this source were
  reconfigured as `listing_html` with `listing_urls = ["/calendar"]`,
  mirroring `fleet-science-center.toml`'s pattern exactly.
- **Ladder result**: Even *after* a hypothetical Discovery fix, the
  ladder would still fail on these detail pages as extraction currently
  works — confirmed directly (not merely inferred) by fetching both
  sampled event pages and running `extract_fields()`. Neither page has
  JSON-LD, a `<time>` tag, or a real `og:title`/`og:description` (the
  page instead has generic-site `name="title"`/`name="description"`
  meta tags with the museum's own name/description, not the event's —
  so the OpenGraph rung and title-fallback rung both recover the wrong,
  generic site title/description, not event-specific ones). The genuine
  event date **is** present in plain body text on both sampled pages
  ("SATURDAY June 13, 2026" at offset 8548 on the swap-meet page;
  "February 15, 2026" near offset 9357 on the summer-camps-registration
  page) but both are far past the body-regex rung's 3000-char window —
  confirmed no date-pattern match anywhere in the first 3000 characters
  of either page's body text, which is consumed almost entirely by the
  site's large repeated navigation menu (a single top-nav block with
  ~80 links, common to every page on this site).
- **Recommended fix mechanism**: **two changes, both required** — (1) a
  **Discovery config/adapter-type change**: switch
  `sandiego-air-space.toml` from `adapter_type = "generic_html"` to
  `adapter_type = "listing_html"` with `config.listing_urls =
  ["/calendar"]` (no sitemap exists at any conventional path or
  `robots.txt`-declared location); **and** (2) the same **targeted
  ladder heuristic fix** to `_extract_body_regex` described below — a
  Discovery fix alone recovers 0 events for this source, since its
  detail pages carry no other date signal the ladder could use instead.

### Fleet Science Center
- **Discovery result**: Correct, no fix needed. `discover_via_listing`
  against `config.listing_urls = ["/events"]` resolves **10** distinct
  detail-page URLs today (issue reported "11 raw" at planning time — a
  1-URL difference plausibly ordinary site content churn since then, not
  a bug; not investigated further as it doesn't change the diagnosis).
  Confirmed via live `--source fleet-science-center --no-enrich
  --dry-run -v` (`found=10`) and the diagnostic script.
- **Ladder result**: **1/10 already exports correctly** —
  `/events/camps` ("STEM Camps") has **20 real, valid ISO
  `<time datetime="2026-07-24T09:00:00-07:00" class="datetime">`-style**
  tags (confirmed directly via `grep`/parse), rung 2 (`_extract_time_tags`,
  confidence 0.8) fires correctly, and the resulting date is upcoming —
  this **directly contradicts** `fleet-science-center.toml`'s existing
  comment claiming Fleet's detail pages "carry no JSON-LD or `<time>`
  markup"; that comment is stale/inaccurate for at least this page and
  should be corrected (a doc-only fix, not a behavior change) when
  ticket 004 touches this file. Of the remaining 9 URLs:
  - **2 are recoverable with the same body-regex-window fix**:
    `/events/annual-gala` ("2026 Fleet Science Center Gala" — real
    title, but date "Saturday, April 11, 2026" sits at body offset 3274,
    past the 3000-char cutoff, no JSON-LD/`<time>`/`og:` date present)
    and `/events/sky-tonight` ("August 29, 2026" at offset 3806, same
    shape). Both confirmed via direct fetch + `extract_fields()`/regex
    probing.
  - **The listing page itself (`/events`) and 6 others** (`/events/ball-pool`,
    `/events/suds-science`, `/events/senior-mondays`,
    `/events/sharp-minds`, `/events/candlelight-concerts`,
    `/events/accessibility-mornings`) have **no** "Month DD, YYYY"
    pattern anywhere in their full body text (not just the 3000-char
    window) and no JSON-LD/`<time>`/`og:` date field — consistent with
    the ticket's own hypothesis that `candlelight-concerts`-style pages
    are genuinely undated, evergreen program pages, correctly excluded
    today (SUC-003's Alternate Flow). Not exhaustively hand-verified for
    every possible non-standard date format on all 7, but the pattern is
    consistent across every one checked.
- **Recommended fix mechanism**: **already correct for Discovery and for
  `/events/camps`; no fix needed there.** The same **targeted ladder
  heuristic fix** to `_extract_body_regex` (below) would additionally
  recover `/events/annual-gala` and `/events/sky-tonight`, raising this
  source's realistic yield from 1/10 to 3/10. No `fetch_strategy =
  "headless"` need anywhere on this source — every date found above was
  in the plain server-rendered HTML.

### Cross-source recommendation: the one ladder fix that generalizes

All three sources' recoverable-but-missed dates (5 pages, 3 sites) fail
for the identical reason, at nearly the identical offset range
(3274–3806 chars). The narrowest fix that addresses all of them without
touching per-site config is a **targeted heuristic adjustment inside
`extract/ladder.py`'s existing `_extract_body_regex` rung** (sprint.md's
Scope explicitly allows this; it is not a new rung, not a rung-priority
change, and not a per-site scraper):

1. Strip `<script>`/`<style>` element text before computing the body
   text the rung scans (`lxml.html.HtmlElement.text_content()` includes
   both by default — confirmed directly: the SDNHM `summer-camp` page's
   first ~700 characters of "body text" are raw inline CSS rule bodies
   like `.btnlinks { background: #249a8c; ... }`, never visible to a
   real reader).
2. Widen and/or make content-aware the scan window — stripping
   `<script>`/`<style>` alone may not be sufficient on every page (large
   nav menus alone, with no inline CSS, already push real content past
   3000 characters on Air & Space's pages); the observed real-date
   offsets (up to ~9357 chars on Air & Space) suggest either a
   substantially larger fixed window or scanning the full body text
   (dropping the cap entirely, now that script/style noise is excluded)
   is worth ticket 004 evaluating against the existing test suite for
   regressions.

This must be verified not to regress the ~10 other `generic_html`/
`listing_html` sources already relying on this rung (sprint.md's Impact
on Existing Components) — `tests/test_extract_ladder.py` already has
targeted coverage of `_extract_body_regex` (including a boundary-offset
assertion at line 133) that ticket 004 should extend, not replace.

Neither `fetch_strategy = "headless"` nor any bespoke per-site selector
is recommended for any of the three sources — every genuine date found
during this investigation was present in plain, non-JS-rendered,
server-side HTML.

## Testing

- **Existing tests to run**: `uv run pytest` (full suite, ~845 tests)
  — must still pass since no production code should change.
- **New tests to write**: none (investigation only).
- **Verification command**: `uv run pytest`.
- **Documentation**: the Findings section above *is* this ticket's
  deliverable — ticket 004 reads it directly, so fill it in
  concretely enough (actual counts, actual rung names, actual
  recommendation) that ticket 004 can start without re-investigating.

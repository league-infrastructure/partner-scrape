---
status: pending
---

# Improve discovery of volunteer opportunities (third-party platforms + per-org links)

We should do a better job of *finding* volunteer opportunities. Many
partner organizations don't publish volunteer openings on their own
event calendars — they list them through third-party volunteer services
(VolunteerMatch, Idealist, Galaxy Digital / GivePulse, JustServe,
HandsOn San Diego, etc.). Today's pipeline mostly ingests events from an
org's own site (The Events Calendar / WordPress / iCal / generic_html —
see `partner_scrape/adapters/`), so those externally-hosted volunteer
listings are invisible to us.

**Approach:** start with **Strategy A** (scrape the platforms). Fall
back to **Strategy B** (per-org link) for any organization or platform
where scraping isn't viable — no clean feed/API, or ToS/robots forbid
it. B is the graceful degradation, not a competing effort.

## Strategy A — scrape the third-party volunteer platforms (primary)

Treat the volunteer platforms themselves as sources/hubs and pull the
opportunities partner orgs post there.

- These platforms fit the existing **Hub Registry** model
  (`partner_scrape/registry/hubs/*.toml`, `hub_schema.py`) — a curated
  external site Hub Scan crawls for lead candidates — and/or warrant a
  dedicated **adapter** per platform (like `localist.py` /
  `bibliocommons.py`) if they expose a clean feed or API.
- Anything ingested is normalized with `opportunity_type =
  "Volunteering"` (taxonomy already supports it;
  `partner_scrape/normalize/taxonomy.py`). Coordinates with issue 13
  (reliable `opportunity_type` classification).
- **ToS / robots gate:** the seed-hub notes already flag this — do not
  point a scanner at a real platform without confirming its
  robots.txt/ToS permit automated browsing/lead-gen.

## Strategy B — central per-organization link ("org profile", fallback)

Where Strategy A can't ingest an org's volunteer listings, fall back to
a curated per-org entry. Instead of ingesting individual volunteer events,
maintain a curated per-org entry that describes what the organization is
and what kinds of volunteer opportunities it offers, and **links out**
to wherever those opportunities live (the org's VolunteerMatch page,
their "get involved" page, etc.).

- This is a lighter-weight, link-based model rather than event
  ingestion — good for orgs whose openings are ongoing/rolling rather
  than dated events.
- Needs a decision on where this lives: an extension of the Source
  Registry (`registry/sources/*.toml` already carry `org_name` +
  `site_url`), a new field/section, or a distinct "org profile" record
  the site renders as a linked card.

## Open questions

- Which specific volunteer platforms do our partner orgs actually use?
  (Survey needed before picking scrape targets.)
- For Strategy B, what does the site render — a card that links out, vs.
  a synthesized listing? How does it sit alongside dated opportunities?
- Per-platform ToS: which of these permit scraping at all, vs. must be
  link-only?

## Supersedes

Replaces the earlier "separate filter-gated volunteer section" idea
(deleted) — the stakeholder decided the priority is *finding* more
volunteer opportunities, not special-casing how they display.
</content>

---
id: '003'
title: Listing-page discovery for no-sitemap sites
status: done
use-cases:
- SUC-014
depends-on: []
github-issue: ''
issue: 06-flagship-adapters-fleet-birch.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Listing-page discovery for no-sitemap sites

## Description

Build a new discovery module, `partner_scrape/discovery/listing.py`,
resolving a source's configured listing page(s) into event/program URLs
by crawling and pattern-matching anchor links — a second discovery
strategy alongside `discovery/sitemap.py`'s sitemap-diff discovery, for
sites confirmed to have no sitemap (see sprint.md's Architecture >
Listing-Page Discovery). This module is a sibling of `discovery/sitemap.py`,
not a modification of it — that file stays untouched.

This is standalone infrastructure: it depends only on the `Fetcher`
protocol, `Config`, `registry.schema.SourceConfig`, and
`adapters.base.EventRef` — mirroring `discovery/sitemap.py`'s existing
dependency shape exactly (never the `Adapter` protocol or dispatch
table). It does not compose into a working adapter itself — that's
ticket 004's job, which depends on this ticket.

Concrete target this module must handle (confirmed live during
planning): Fleet Science Center's `/events` page is a single,
non-paginating Drupal Views listing (`?page=1` returned the identical 10
links as the base page) containing 10 outbound links matching
`/events/{slug}`, e.g. `/events/candlelight-concerts`,
`/events/sky-tonight`. No JSON-LD, no `<time>` tags on the listing page
itself — this module only needs `<a href>` targets, not date signal.

**Design constraint, deliberate — do not add diffing**: unlike
`discovery/sitemap.py`, this module does NO incremental (changed-only)
diffing. A listing page carries no `<lastmod>`-equivalent signal to diff
against. Every link matching the event-path pattern on every configured
listing page is returned as an `EventRef` on every call — no persisted
snapshot, no `SCRAPE_CACHE_DIR` write. This is a deliberate scope
decision (see sprint.md's Design Rationale and Open Question 2) — at
Fleet's ~10-page scale, always-full-recrawl costs nothing meaningful, and
building a diffing scheme with no real signal to anchor it to would be
speculative generality. Do not add one in this ticket.

Config shape: `source.config["listing_urls"]` — a list of paths or full
URLs (Fleet's is `["/events"]`, resolved against `source.config["site_url"]`
the same way `discovery/sitemap.py` resolves `site_url`). Link matching:
reuse `discovery/sitemap.py`'s `EVENT_PATH_RE` pattern (imported, not
duplicated) as the default, unless a source-specific override is needed
— Fleet's `/events/{slug}` links already match that existing pattern, so
no new pattern should be required for this ticket's concrete target.

## Acceptance Criteria

- [x] `discover_via_listing(source, fetcher) -> list[EventRef]` (or
      equivalently named function) fetches each URL in
      `source.config["listing_urls"]` via the injected `Fetcher`.
- [x] Given a fixture listing page HTML with several `<a href="/events/...">`
      links, the function yields one `EventRef` per link matching the
      event-path pattern (reusing `discovery.sitemap.EVENT_PATH_RE`).
- [x] Links that don't match the event-path pattern (e.g. a nav link to
      `/about` or `/donate`) are excluded.
- [x] An unreachable (non-200) listing page yields zero `EventRef`s for
      that page and a logged warning, not an exception — and does not
      prevent other configured listing pages on the same source from
      still being processed (per-page isolation).
- [x] Calling the function twice in a row against an unchanged fixture
      listing page returns the same `EventRef`s both times (confirms the
      deliberate no-diffing behavior — this is a "don't regress into
      diffing" check, not a performance test).
- [x] No new file is written under `SCRAPE_CACHE_DIR` by this module
      (confirms no snapshot/diffing state was introduced).
- [x] Zero changes to `discovery/sitemap.py`.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_discovery_sitemap.py`
  (confirm the sibling module is untouched and its tests still pass).
- **New tests to write**: `tests/test_discovery_listing.py` — fixture
  listing-page HTML (a synthesized page modeled on Fleet's real
  `/events` structure: multiple `/events/{slug}` links plus at least one
  non-matching nav link), an unreachable-page case, and a
  repeated-call-same-result case.
- **Verification command**: `uv run pytest`

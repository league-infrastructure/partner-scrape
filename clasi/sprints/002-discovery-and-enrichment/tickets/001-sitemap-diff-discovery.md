---
id: '001'
title: Sitemap-diff discovery
status: done
use-cases:
- SUC-009
depends-on: []
github-issue: ''
issue: 03-sitemap-discovery-generic-extractor.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sitemap-diff discovery

## Description

Implement the Sitemap Discovery module (sprint.md Architecture > Sitemap
Discovery, SUC-009): resolve a source's sitemap into the set of event URLs
that are new or changed since the last run. This is the first real
implementation of `Adapter.discover()`'s deferred seam (sprint 001) — no
change to `adapters/base.py` is needed or expected.

Scope:
- Fetch `sitemap_index.xml` or `sitemap.xml` via the injected `Fetcher`
  (never `urllib` directly — same seam ticket 003 of sprint 001 already
  established).
- Recurse into a sitemap index: identify event/program-related child
  sitemaps by filename pattern (port `dev/inventory_sitemaps.py`'s
  `EVENT_PATTERNS`/`PROGRAM_PATTERNS` regexes as a starting point, not a
  dependency — `dev/` stays untouched) and by URL-path pattern for sites
  with no dedicated event sitemap.
- Parse `<url><loc>`/`<lastmod>` pairs via stdlib `xml.etree.ElementTree`
  (matching `dev/inventory_sitemaps.py`'s proven approach — zero new
  dependency).
- Diff the current `(url, lastmod)` set against a persisted snapshot for
  this `source_id`, stored under `SCRAPE_CACHE_DIR` (via
  `Config.get_scrape_cache_dir()`, e.g.
  `{cache_dir}/sitemap_snapshots/{source_id}.json`). Only new or
  `<lastmod>`-changed URLs are returned as `EventRef`s; the snapshot is
  updated to the current full state after the diff.
- No prior snapshot (first run for this source) → every event-pattern-
  matching URL is new.

## Acceptance Criteria

- [x] Given a fixture sitemap with all-unchanged `<lastmod>` values
      against a stored snapshot fixture, discovery yields zero
      `EventRef`s.
- [x] Given a fixture sitemap with one bumped `<lastmod>` (and others
      unchanged), discovery yields exactly that one `EventRef`.
- [x] A first-run source (no snapshot file on disk) yields every
      event-pattern-matching URL from the sitemap.
- [x] A fixture `sitemap_index.xml` referencing one event-named child
      sitemap and one unrelated child sitemap (e.g. a page/post sitemap)
      only pulls URLs from the event-named child.
- [x] A malformed/unparseable sitemap fixture yields zero `EventRef`s and
      a logged warning, not an exception that would propagate up through
      the adapter's `discover()`.
- [x] The snapshot file is written/updated after a successful diff so the
      *next* call against the same fixture (unchanged) yields zero
      `EventRef`s (round-trip test).

## Implementation Plan

### Approach

A small, dependency-light module: something like
`discover_changed_urls(source: SourceConfig, fetcher: Fetcher) ->
list[EventRef]` as the module's one public entry point, backed by private
helpers for sitemap-index parsing, event-pattern classification, and
snapshot read/write. Keep the snapshot format dead simple (a flat JSON
`{url: lastmod}` map) — there is no need for anything richer than
`dev/inventory_sitemaps.py` already proved sufficient for classification.
This module has no dependency on `partner_scrape/adapters/` — ticket 002's
`generic_html` adapter calls into this module, not the other way around
(see sprint.md's dependency-direction check).

### Files to Create/Modify

- `partner_scrape/discovery/__init__.py`
- `partner_scrape/discovery/sitemap.py`
- `tests/test_discovery_sitemap.py`
- `tests/fixtures/sitemaps/sitemap_index.xml`,
  `tests/fixtures/sitemaps/events_sitemap.xml`,
  `tests/fixtures/sitemaps/pages_sitemap.xml` (non-event, to verify
  filtering), `tests/fixtures/sitemaps/malformed.xml`

### Documentation Updates

None required this ticket.

## Testing

- **Existing tests to run**: `uv run pytest` (full sprint 001 suite — no
  regressions expected, nothing existing imports this new module).
- **New tests to write**: `tests/test_discovery_sitemap.py` covering every
  Acceptance Criterion above, using a fixture `Fetcher` (the same
  `FixtureFetcher` pattern `tests/test_adapters_tec.py` already
  established) so no real HTTP occurs, and a `tmp_path`-based
  `SCRAPE_CACHE_DIR` (monkeypatched, matching sprint 001's Fetch & Cache
  test convention) so snapshot read/write is exercised without touching
  the real cache directory.
- **Verification command**: `uv run pytest`

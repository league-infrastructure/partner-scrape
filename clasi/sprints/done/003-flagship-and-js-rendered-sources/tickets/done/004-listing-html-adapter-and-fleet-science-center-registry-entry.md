---
id: '004'
title: listing_html adapter and Fleet Science Center registry entry
status: done
use-cases:
- SUC-014
depends-on:
- '003'
github-issue: ''
issue: 06-flagship-adapters-fleet-birch.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# listing_html adapter and Fleet Science Center registry entry

## Description

Build a new `listing_html` adapter type
(`partner_scrape/adapters/listing_html.py`), composing ticket 003's
Listing-Page Discovery with sprint 002's existing, unchanged extraction
ladder (`extract/ladder.py`) — structurally parallel to `generic_html.py`
(same `fetch()`, same `extract.ladder.extract_fields` call, same `Event`
construction), differing only in `discover()`, which delegates to ticket
003's discovery function instead of `discovery.sitemap.discover_changed_urls`.
This is thin glue, matching sprint 002's Design Rationale for why the
adapter, discovery, and extraction concerns stay in separate modules.
Register `ADAPTERS["listing_html"] = ListingHtmlAdapter` in
`adapters/__init__.py` (one line, matching the existing pattern). Zero
changes to `adapters/base.py`, `adapters/generic_html.py`, or
`extract/ladder.py`.

Register the real `fleet-science-center.toml` source under
`partner_scrape/registry/sources/`, using values confirmed live during
sprint planning:
- `org_name = "Fleet Science Center"`
- `adapter_type = "listing_html"`
- `config.site_url = "https://www.fleetscience.org"`
- `config.listing_urls = ["/events"]`

**Context confirmed live, worth knowing before implementing**:
`fleetscience.org` is a server-rendered Drupal 9 site (not client-
rendered — no headless fetch needed here) with no sitemap at any
conventional path (`sitemap_index.xml`, `sitemap.xml`, `/sitemap`,
`/sitemaps/sitemap.xml` all 404). Its `/events` listing page has 10
outbound `/events/{slug}` links. Its individual event/program detail
pages (e.g. `/events/candlelight-concerts`) have **no JSON-LD and no
`<time>` tag** — so in practice the extraction ladder's OpenGraph,
title-fallback, and body-regex rungs are what will fire for Fleet, not
the top JSON-LD/`<time>` rungs. Fleet's events will frequently be
undated at extraction time; sprint 002's existing LLM Enricher (already
wired into the default CLI pipeline) is what recovers dates where
possible — no new enrichment logic is needed or in scope here.

## Acceptance Criteria

- [x] `ListingHtmlAdapter` implements the `Adapter` protocol
      (`discover`/`fetch`/`extract`) and is registered as
      `ADAPTERS["listing_html"]`.
- [x] `discover()` delegates entirely to ticket 003's discovery function
      — no discovery logic duplicated in this adapter.
- [x] `fetch()`/`extract()` reuse `extract.ladder.extract_fields`
      unchanged (same call shape as `generic_html.py`'s).
- [x] Given a fixture detail page with no JSON-LD and no `<time>` tag
      (mirroring Fleet's confirmed real page shape), the adapter still
      emits an Event via a lower ladder rung (OpenGraph or title
      fallback) — not a dropped record.
- [x] A non-200 fetch or a page with no usable title in any ladder rung
      is dropped (logged, skipped), matching `generic_html`'s existing
      per-record isolation convention.
- [x] `fleet-science-center.toml` is added under
      `partner_scrape/registry/sources/`, loads successfully via
      `SourceConfig.from_toml`, and round-trips through
      `registry.load_active_sources()`.

## Testing

- **Existing tests to run**: `uv run pytest
  tests/test_adapters_generic_html.py tests/test_extract_ladder.py
  tests/test_registry.py` (confirm the patterns this ticket mirrors, and
  the unchanged extraction ladder, still pass).
- **New tests to write**: `tests/test_adapters_listing_html.py` —
  fixture-based tests composing ticket 003's discovery fixtures with a
  synthesized Fleet-style detail page fixture (no JSON-LD, no `<time>`,
  relying on OpenGraph/title-fallback rungs), plus the non-200/no-title
  drop cases. Extend `tests/test_registry.py` to confirm
  `fleet-science-center.toml` loads.
- **Verification command**: `uv run pytest`

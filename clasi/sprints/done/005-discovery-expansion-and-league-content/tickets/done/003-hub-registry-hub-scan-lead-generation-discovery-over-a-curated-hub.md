---
id: '003'
title: 'Hub Registry + Hub Scan: lead-generation discovery over a curated hub'
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: 09-aggregator-as-discovery-not-source.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Hub Registry + Hub Scan: lead-generation discovery over a curated hub

## Description

Build the core lead-generation capability issue 09 asks for: scan a
curated external hub for candidate organizations we don't yet cover,
without ever treating the hub's own content as our data.

Two new modules, mirroring this codebase's existing schema/loader vs.
scanning-strategy split (`registry/` vs. `discovery/`):

1. **`partner_scrape/registry/hub_schema.py`** — a `HubConfig` dataclass
   (`hub_id` derived from the TOML filename stem, `hub_name`,
   `page_urls: list[str]`, optional free-form `config` dict for
   hub-specific scan hints) plus `load_hubs(directory) ->
   list[HubConfig]`, structurally parallel to `registry/schema.py` +
   `registry/loader.py`. Hub TOML files live under a new
   `partner_scrape/registry/hubs/` directory — physically separate from
   `registry/sources/`, so `registry/loader.py`'s `DEFAULT_SOURCES_DIR`
   scan is completely untouched by this ticket.
2. **`partner_scrape/discovery/hub_scan.py`** — an `OrgCandidate`
   dataclass (`org_name`, `candidate_url`, `evidence_text`, `hub_id`) and
   `scan_hub(hub: HubConfig, fetcher: Fetcher) -> list[OrgCandidate]`.
   For each of the hub's `page_urls`: check `fetch/robots.py`'s
   `is_allowed()` first (skip the page, logged, if disallowed); fetch it;
   extract outbound `<a href>` links to a *different* domain than the
   hub's own, along with nearby text (e.g. the anchor's own text plus
   its containing block's text, similar to
   `discovery/listing.py`'s anchor-extraction approach) as `evidence_text`
   and a best-effort `org_name` guess from the link text/title. Then
   filter out any candidate whose domain or `normalize.partners
   .normalize_org_name(org_name)` already matches an existing source:
   call `registry.load_sources()` (the Registry's own public loader —
   **do not** re-parse `registry/sources/*.toml` directly, per
   sprint.md's Design Quality self-review note on avoiding feature envy)
   and compare each `SourceConfig`'s `config.get("site_url")`/
   `config.get("api_base")` domain and `normalize_org_name(org_name)`
   against each candidate.

This ticket produces candidates only — it does not filter by relevance
(ticket 004's job) or persist them anywhere (ticket 004's job). It is a
pure, offline-testable scan.

Also add one seed hub definition,
`partner_scrape/registry/hubs/example-regional-calendar.toml`, clearly
commented as an illustrative template (not a live, investigated hub —
see sprint.md's Open Question 1: populating the real roster, e.g. a
Balboa Park-style calendar, needs the same kind of live-site
investigation performed for jointheleague.org, deferred to operator
backlog).

## Acceptance Criteria

- [x] `registry/hub_schema.py`'s `load_hubs()` parses a directory of hub
      TOML files the same way `registry/loader.py` does for sources — a
      malformed file is logged and skipped, never fatal to the rest of
      the directory.
- [x] `discovery/hub_scan.py`'s `scan_hub()` respects robots.txt per page
      (a disallowed page is skipped, not fetched).
- [x] Given a fixture hub listing page with event blurbs for orgs whose
      domain/name already matches an existing `registry/sources/*.toml`
      entry, those orgs are filtered out of the returned candidates.
- [x] Given a fixture hub listing page with event blurbs for genuinely
      new orgs, those orgs are surfaced as `OrgCandidate`s with
      `org_name`, `candidate_url`, `evidence_text`, and `hub_id` all
      populated.
- [x] `scan_hub()` never constructs a `partner_scrape.model.Event` and
      never calls anything in `normalize/` or `export/`.
- [x] `registry/hubs/example-regional-calendar.toml` exists, is clearly
      commented as a template/proof-of-concept (not a live hub), and
      loads successfully via `load_hubs()`.
- [x] The dedup check calls `registry.load_sources()` (or
      `load_active_sources()`) rather than parsing TOML files itself.

## Testing

- **Existing tests to run**: `tests/test_registry.py`,
  `tests/test_normalize_partners.py` (for `normalize_org_name` reuse),
  `tests/test_fetch_cache.py` (robots.txt behavior precedent).
- **New tests to write**:
  - `tests/test_registry_hub_schema.py` — parses a fixture hub-TOML
    directory, including one malformed file (asserts log-and-skip, not
    fatal).
  - `tests/test_discovery_hub_scan.py` — a fixture hub HTML page
    (`tests/fixtures/hubs/example_hub.html`) with several event-style
    blurbs, some linking to domains matching a fixture registry's
    existing sources (must be filtered) and some to new domains (must
    surface); a fixture registry directory with 2-3 `SourceConfig` TOMLs
    to dedup against; a fixture `Fetcher` whose robots.txt disallows one
    of the hub's configured pages (asserts that page is skipped).
- **Verification command**: `uv run pytest`

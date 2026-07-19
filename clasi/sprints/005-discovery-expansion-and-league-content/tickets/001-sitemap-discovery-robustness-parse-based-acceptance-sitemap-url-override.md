---
id: '001'
title: 'Sitemap discovery robustness: parse-based acceptance + sitemap_url override'
status: done
use-cases:
- SUC-005
depends-on: []
github-issue: ''
issue:
- 12-league-content-and-advertising.md
- 09-aggregator-as-discovery-not-source.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sitemap discovery robustness: parse-based acceptance + sitemap_url override

## Description

`discovery/sitemap.py`'s `_fetch_root_sitemap` currently accepts the
**first** `_ROOT_SITEMAP_FILENAMES` candidate (`sitemap_index.xml`, then
`sitemap.xml`) that returns HTTP 200, then hands its body to
`_resolve_event_urls`, which fails (logs a warning, returns `None`) if
that body doesn't parse as sitemap XML — it never falls through to try
the next candidate filename.

This is a real, live-confirmed bug, not a hypothetical: jointheleague.org
(ticket 002's target) returns HTTP 200 with its own "not found" HTML page
for *every* path, including `/sitemap_index.xml` — its real sitemap is
at `/sitemap-index.xml` (hyphenated), which is never even tried today.
The same failure mode will recur for any future issue-09-promoted
candidate whose site has this kind of misconfiguration (a common one:
many static-site generators serve a catch-all 200 page instead of a
real 404).

Fix, per sprint.md's Architecture > Design Rationale:
1. Broaden `_ROOT_SITEMAP_FILENAMES` to also include `sitemap-index.xml`.
2. Change the accept condition from "first HTTP 200" to "first candidate
   whose body actually parses as sitemap XML with a recognized root
   element (`<urlset>` or `<sitemapindex>`)" — on a 200 response that
   fails to parse or has the wrong root element, log and continue to the
   next candidate instead of stopping. Only return `None` (existing error
   flow, unchanged) once every candidate is exhausted.
3. Add an optional `config.sitemap_url` key (inside the existing
   free-form `SourceConfig.config` dict — no dataclass field change) that,
   when set, skips probing entirely and fetches that exact URL as the
   root sitemap.

This is foundational infrastructure work — do it before ticket 002 so
League's registration can rely on it (and set `config.sitemap_url`
explicitly as a belt-and-suspenders confirmation of the exact URL this
planning pass verified live).

## Acceptance Criteria

- [x] `_ROOT_SITEMAP_FILENAMES` includes `sitemap-index.xml` in addition
      to the existing `sitemap_index.xml` and `sitemap.xml`.
- [x] `_fetch_root_sitemap` (or its replacement logic) tries each
      candidate in order and accepts the first one whose body parses as
      valid sitemap XML with a recognized root element — a 200 response
      with a non-parseable or wrong-root-element body is logged and
      skipped, not treated as final.
- [x] `SourceConfig.config.get("sitemap_url")`, when present, is fetched
      directly and probing is skipped entirely.
- [x] Only when every candidate (or the explicit override) fails does
      `_resolve_event_urls` return `None` with a logged warning — the
      existing error-flow contract, unchanged.
- [x] Every existing registered source's discovery behavior is
      unchanged (regression-tested).

## Testing

- **Existing tests to run**: `tests/test_discovery_sitemap.py`,
  `tests/test_adapters_generic_html.py`, `tests/test_pipeline_e2e.py` —
  must pass unchanged (no regression for the six currently-registered
  sources).
- **New tests to write** (in `tests/test_discovery_sitemap.py`):
  - A fixture `Fetcher` where `sitemap_index.xml` and `sitemap.xml` both
    return HTTP 200 with a non-XML (HTML) body, and `sitemap-index.xml`
    returns HTTP 200 with a real `<sitemapindex>` body — asserts
    discovery falls through the first two candidates and succeeds on the
    third.
  - A fixture where the same false-200 pattern applies to every
    conventional filename, but `config.sitemap_url` is set to a URL that
    returns a real sitemap — asserts probing is skipped and the override
    is used directly.
  - A fixture where every candidate (including any override) fails to
    parse — asserts the existing `None`-return, logged-warning contract
    still holds.
- **Verification command**: `uv run pytest`

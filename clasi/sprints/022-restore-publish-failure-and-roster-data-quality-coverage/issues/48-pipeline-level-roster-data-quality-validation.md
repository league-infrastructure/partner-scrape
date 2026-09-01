---
status: in-progress
sprint: '022'
tickets:
- 022-002
- 022-003
- 022-004
---

# Pipeline-level data-quality validation for the partner roster (recover lost regression guards)

## Description

Sprint 019 ticket 002 (converting `site/` to a build-time-only checkout)
had to delete 24 tests that hardcoded reads against `partner-scrape/site/`
paths, which no longer exist as a tracked directory in this repo (that
content lives exclusively in stem-ecosystem now):

- `tests/test_roster_housekeeping.py` (16 tests) — real regression value:
  a bare-California-centroid guard (36.778261,-119.417932, the Google
  geocoder's fallback for the string "California" — caught 7 real bad
  entries in sprint 018), an in-bounding-box-or-empty coordinate guard,
  a hijacked-domain guard (documented as protecting against a real
  historical incident — `batiquitosfoundation.org`), and a registry
  org_name ↔ partners.json join-integrity guard.
- `tests/directory/test_dataset_validity.py` (2 tests) — validates
  `directory/data/places.toml`'s hand-curated `related_partner_id`
  values actually resolve against the roster.

The other 22 (`tests/test_site_teams_pages.py`) plus 6
(`tests/test_site_data_access_page.py`) test Astro page/schema content
that now lives exclusively in stem-ecosystem — genuinely not
partner-scrape's concern anymore, not proposed for recovery here.

## Cause

These checks were written against a live, ~211-row checked-out
`partners.json` that happened to sit inside this repo. Once `site/`
became a build-time-only CI checkout (never a persistent local
directory), there's no file left in partner-scrape for a hermetic test
to read. Re-copying `partners.json` back into partner-scrape just to
keep these tests passing would recreate the exact two-copies-of-the-
same-file problem the whole site consolidation exists to eliminate —
rejected on that basis, not attempted.

## Proposed fix

Move the *logic* these tests protect into the pipeline itself, as
fixture-testable validation that runs on every real run (not dependent
on a checked-out `site/`) — likely a small `partner_scrape/registry/
validate_roster.py`-shaped module, called from wherever
`normalize/partners.py` loads `partners.json` (or from `cli.py` right
after `--site-dir` resolves), that raises loudly on: a bare-California
centroid, an out-of-bounding-box (or malformed) coordinate, a known-
hijacked domain, a non-unique slugified partner name (see issue 46 —
the 2026-08-31 incident this guards against was two exact-duplicate
rows under different ids, not near-duplicate names; fixed content-wise
by the 211-row roster, but nothing stopped it recurring), or (for the
join-integrity check) an active registry source whose `org_name`
resolves to zero roster entries. Regression
tests use small, hand-crafted fixture `partners.json` snippets (one bad
row each) — exactly the kind of test that doesn't need a real checked-
out site at all, and is stronger than the tests it replaces: it fails a
real pipeline run with bad data, not just a `pytest` invocation someone
happens to run against a stale local checkout.

The `places.toml` join-integrity check can live directly in
`partner_scrape/directory/` (which already owns `places.toml`), using
the same validation primitive against whatever `partners.json` the
pipeline run resolved.

## Verification

Fixture tests per bad-data case above; a full pipeline run against a
crafted bad roster fails loudly with an actionable message, not
silently.

## Related

Sprint 019 ticket 002 (the deletion that motivates this); sprint 018
tickets 002-005 (where these checks originated, including the real
`batiquitosfoundation.org` hijacked-domain finding and the 7-entry
bare-California-centroid fix).

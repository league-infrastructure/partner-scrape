---
id: '007'
title: 'Site export: current+upcoming filter and opportunities.json write'
status: done
use-cases:
- SUC-007
depends-on:
- '006'
github-issue: ''
issue: 05-normalize-dedup-site-export.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Site export: current+upcoming filter and opportunities.json write

## Description

Build the Site Export module (sprint architecture): publish the live
opportunity set into the sibling `stem-ecosystem` repo's data contract,
matching `dev/export_site.py`'s existing behavior and the schema in
`stem-ecosystem/docs/site-implementation-spec.md`.

Scope:
- Filter `Opportunity` records to current + upcoming only (end date, or
  start date if no end date, is today or later). Historical data must
  never reach the written file.
- A defensive slug-uniqueness pass: if two records land on the same
  `slug` after normalize (ticket 006 already dedupes by
  title+date+venue, but slug collisions can still happen for distinct
  records, e.g. same org+title on different but nearby dates truncated
  the same way) — append a disambiguating numeric suffix, matching
  `dev/export_site.py`'s existing `seen`-dict approach.
- Write `{site_dir}/src/data/opportunities.json` (the filtered,
  slug-unique list) and `{site_dir}/src/data/scrape-meta.json`
  (`{"last_updated": <UTC ISO 8601 timestamp>}`) on every run.
- `site_dir` resolves from `Config`'s default (`../stem-ecosystem`) but
  is overridable (CLI flag, wired in ticket 008).
- A missing or unwritable `site_dir` must fail loudly (raise), never
  silently skip the write — matching SUC-007's explicit error flow.

## Acceptance Criteria

- [x] A past-only `Opportunity` (end date before today, or start date
      before today with no end date) is excluded from the written
      file.
- [x] An `Opportunity` whose end date is today or later is included.
- [x] Two input records that would otherwise share the same `slug`
      after mapping are disambiguated with a suffix; neither is
      silently dropped.
- [x] `opportunities.json` is written with the exact field set and
      types documented in
      `stem-ecosystem/docs/site-implementation-spec.md`'s Opportunities
      table.
- [x] `scrape-meta.json`'s `last_updated` changes on every export run
      (even if the opportunity data is otherwise unchanged).
- [x] A `site_dir` that does not exist (or isn't writable) raises a
      clear error rather than exiting silently with nothing written.

## Implementation Plan

### Approach

Keep this module a thin writer over already-normalized data — it
should not re-derive or re-map any field `normalize` (ticket 006)
already produced; its only logic is filtering, slug disambiguation,
and JSON serialization. This mirrors `dev/export_site.py`'s own shape
and keeps the "what does the site actually receive" logic isolated
from "how did we decide what an opportunity contains" (see sprint.md
Design Rationale on why Normalize and Export are separate modules).

### Files to Create/Modify

- `partner_scrape/export/__init__.py`
- `partner_scrape/export/writer.py`
- `tests/test_export.py`

### Documentation Updates

None required this ticket.

## Testing

- **Existing tests to run**: `uv run pytest` (tickets 001-006's
  suites).
- **New tests to write**: `tests/test_export.py` covering past-only
  exclusion, current/upcoming inclusion, slug-collision
  disambiguation, exact field-set/type conformance against the site
  spec, `scrape-meta.json` timestamp refresh, and the missing/unwritable
  `site_dir` error path — writing into a `tmp_path` fixture standing in
  for the site repo, never a real sibling checkout.
- **Verification command**: `uv run pytest`

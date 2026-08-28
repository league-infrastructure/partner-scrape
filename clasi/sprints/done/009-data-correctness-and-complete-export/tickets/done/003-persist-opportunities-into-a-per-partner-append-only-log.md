---
id: '003'
title: Persist opportunities into a per-partner append-only log
status: done
use-cases:
- SUC-005
depends-on:
- '002'
github-issue: ''
issue: 15-publish-complete-self-describing-data-export.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Persist opportunities into a per-partner append-only log

## Description

Today's `opportunities.json` is a single flat file, overwritten every
run — past events are silently lost, and there is no history. This
ticket introduces the new, persistent, per-partner, append-only
accumulation layer issue 15 requires: a new `export/partner_log.py`
module, `record(opportunities, ...)`, called from `pipeline.run()`
alongside the existing `export_opportunities`/`export_ads` calls so
every real run accumulates.

For each `Opportunity`, resolve its partner slug from the
already-resolved `partner_name`/`partner_id` (the existing partner
join `normalize/` performs — **not** raw scraper `source_id`, since one
`Opportunity` can carry several contributing `source_id`s via
cross-source dedup but always resolves to exactly one partner). Compute
`published_content_hash(opportunity)` over the published schema fields
(title, description, dates, location, cost_range, opportunity_type,
age_grade_level, areas_of_interest, time_of_day, link — excluding
identity/bookkeeping fields). Read that partner's existing
`opportunities.jsonl` (if any); skip if `(slug, content_hash)` already
exists; otherwise append a new line. Never rewrite an existing line.

See `design/export-DESIGN.md` for the full rationale, including why
this is a new module rather than a reuse of the unwired
`store/event_store.py` (different identity concept, different record
type, different purpose).

## Acceptance Criteria

- [x] New `partner_scrape/export/partner_log.py` module with
      `record(opportunities: Iterable[Opportunity], *, log_dir=None,
      partners_path=None, dry_run=False) -> None` and
      `published_content_hash(opportunity: Opportunity) -> str`.
- [x] `log_dir` defaults to `{config.get_scrape_cache_dir()}/partner_log/`
      — no new environment variable is added; this follows
      `enrich/cache.py`'s and `store/event_store.py`'s existing
      "subdirectory of `SCRAPE_CACHE_DIR`" convention.
- [x] Partner slug is computed via the shared `model.slugify(partner_name)`
      (the same primitive ticket 002 promotes for event slugs), applied
      to the Opportunity's already-resolved `partner_name` — reuses
      `normalize.partners`'s existing join result, does not re-derive
      it from `source_id`.
- [x] Directory layout: `{log_dir}/<partner-slug>/partner.json` (the
      curated partner record, written/refreshed from
      `normalize.partners.load_partners`) and
      `{log_dir}/<partner-slug>/opportunities.jsonl` (append-only; each
      line is the `Opportunity`'s fields as JSON, `sources` included
      as a plain list — not the site-schema-filtered shape — plus
      `slug` and `content_hash`).
- [x] `opportunities.jsonl`'s filename is a module-level constant
      (`_JSONL_FILENAME` or similar), importable by ticket 004's
      `publish.py` — see `design/export-DESIGN.md`'s note that
      `publish.py` must depend on this constant rather than
      re-guessing it, one-way (`partner_log.py` never imports
      `publish.py`).
- [x] Append/skip decision: a scraped `(slug, content_hash)` pair
      already present as a line → skip (no write). New `slug`, or
      matching `slug` with a different `content_hash` → append a new
      line. An existing line is **never** edited or removed by this
      function.
- [x] `record(..., dry_run=True)` computes what it would do without any
      disk write, matching every other export function's `dry_run`
      contract.
- [x] A partner with no match in the curated `partners.json` still
      accumulates normally (keeps the org name as its "partner name",
      matching `find_partner`'s existing non-fatal behavior).
- [x] Wired into `pipeline.run()`: called with this run's `Opportunity`
      list, alongside the existing `export_opportunities`/`export_ads`
      calls, skipped under `dry_run` the same way those already are.

## Implementation Plan

**Approach**: A new, self-contained module with no dependency on
`writer.py`/`ads.py`/`images.py`/`mirror.py`; its only intra-package
dependencies are `normalize.partners` (the read-only join) and
`model.slugify`. Wire it into `pipeline.run()` last, once the module's
own tests pass in isolation.

**Files to create**:
- `partner_scrape/export/partner_log.py`
- `tests/export/test_partner_log.py` (or matching the repo's existing
  per-module test-file convention)

**Files to modify**:
- `partner_scrape/pipeline.py` — call `partner_log.record(...)`
  alongside the existing export calls.

## Testing

- **Existing tests to run**: `uv run pytest` (confirm no regression to
  `pipeline.py`'s existing export-call tests).
- **New tests to write** (`tests/export/test_partner_log.py`):
  - Directory layout: `partner.json` and `opportunities.jsonl` are
    created under the right partner-slug directory.
  - Three-way decision table: new slug → append; same slug + same hash
    → skip (no write, file unchanged); same slug + different hash →
    append (old line still present afterward).
  - Strict append-only: a second call never rewrites or removes an
    existing line (assert by reading the file's exact prior lines
    before and after).
  - `dry_run=True` writes nothing to disk.
  - Unmatched partner (no `partners.json` match) still accumulates,
    keyed by `slugify(org_name)`.
- **Verification command**: `uv run pytest`

## Documentation updates

None beyond this sprint's `design/export-DESIGN.md` and root
`design/DESIGN.md` overlays (already written).

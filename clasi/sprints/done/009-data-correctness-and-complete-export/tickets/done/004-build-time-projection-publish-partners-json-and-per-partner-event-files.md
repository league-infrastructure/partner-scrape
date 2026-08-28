---
id: '004'
title: 'Build-time projection: publish partners.json and per-partner event files'
status: done
use-cases:
- SUC-006
- SUC-008
depends-on:
- '003'
github-issue: ''
issue: 15-publish-complete-self-describing-data-export.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Build-time projection: publish partners.json and per-partner event files

## Description

Ticket 003 accumulates every partner's opportunities into a durable,
append-only `.jsonl` log. This ticket adds the build-time projection
that turns that accumulated state into the actual public data contract
issue 15 asks for: a new `export/publish.py` module, `project(...)`,
that collapses each partner's log to one record per event slug
(last line wins), splits current/upcoming from past, and writes the
published `public/data/partners.json` (every curated partner, with
reference paths to its own files) plus each partner's
`public/data/partners/<slug>/events.json` and `.../past-events.json`.

Unlike ticket 003's `record()` (which only needs *this run's*
Opportunities), `project()` must read *every* partner's full
accumulated history to produce a correct split — so, like
`mirror_site_data`, it is **not** called from inside `pipeline.run()`;
it is wired into `cli.py`, after `run()` returns, before the mirror
step (ticket 005). This keeps a `--source`/`--limit`-scoped invocation
from ever regenerating the published tree from a partial view of the
data.

The published `public/data/` tree is **additive**: `src/data/opportunities.json`
(written by the existing, unchanged `export_opportunities`) keeps
shipping every run exactly as it does today. See
`design/export-DESIGN.md` for the full rationale, including why this
lives under `public/` (runtime-fetchable) rather than `src/data/`
(Astro's own build input, not itself servable).

## Acceptance Criteria

- [x] New `partner_scrape/export/publish.py` module with
      `project(site_dir=None, *, log_dir=None, partners_path=None,
      today=None, dry_run=False) -> dict` (returns a summary — partner
      count, event counts — of what it wrote or would have written).
      Raises on an unwritable `site_dir`, matching
      `export_opportunities`'s loud-failure contract.
- [x] For **every** partner in the curated `partners.json` (not only
      ones with an accumulated log), resolves its slug the same way
      ticket 003 does (`model.slugify(partner_name)`) and looks up
      whether `{log_dir}/<slug>/opportunities.jsonl` exists.
- [x] If it exists: collapse to one record per event slug, **last line
      wins**. If not: that partner publishes with empty
      `events.json`/`past-events.json` — it still appears in
      `partners.json`.
- [x] Current/upcoming vs. past split reuses `writer.py`'s
      `is_current_or_upcoming` (promoted from `_is_current_or_upcoming`
      — see below), including its `Work-based Learning` exception,
      rather than reimplementing the judgment.
- [x] Published per-partner event records use the same field set as
      today's `opportunities.json` entries: `writer.py`'s
      `_SITE_SCHEMA_FIELDS`/`_to_json_dict` are promoted to
      `SITE_SCHEMA_FIELDS`/`to_json_dict` (non-underscore, shared) and
      reused verbatim by `publish.py` — `sources` excluded, same as
      today.
- [x] `publish.py` imports `partner_log.py`'s `.jsonl` filename constant
      to locate each partner's log — does not re-guess or duplicate the
      filename string.
- [x] Writes `{site_dir}/public/data/partners.json`: every curated
      partner's full curated record plus two reference paths (e.g.
      `events_url`, `past_events_url`) pointing at its own files.
- [x] Writes `{site_dir}/public/data/partners/<slug>/events.json` and
      `.../past-events.json` per partner.
- [x] `src/data/opportunities.json` (written by `export_opportunities`)
      is untouched by this ticket — `writer.py`'s own behavior is
      unchanged beyond the two promotions above.
- [x] `project(..., dry_run=True)` computes without writing, matching
      the existing `dry_run` contract.
- [x] Wired into `cli.py`, called after `run()` returns and before the
      mirror step, skipped under `--dry-run` the same way mirroring
      already is.

## Implementation Plan

**Approach**: Promote the three `writer.py` helpers first (small,
mechanical, no behavior change — just de-underscoring three names and
updating `writer.py`'s own internal call sites), then build `publish.py`
against the promoted, shared versions.

**Files to create**:
- `partner_scrape/export/publish.py`
- `tests/export/test_publish.py` (or matching convention)

**Files to modify**:
- `partner_scrape/export/writer.py` — rename `_is_current_or_upcoming`
  → `is_current_or_upcoming`, `_SITE_SCHEMA_FIELDS` →
  `SITE_SCHEMA_FIELDS`, `_to_json_dict` → `to_json_dict`; update
  `writer.py`'s own internal references. No behavior change.
- `partner_scrape/cli.py` — call `publish.project(...)` after `run()`
  returns, before the existing mirror-step block.

## Testing

- **Existing tests to run**: `uv run pytest`, with attention to
  `writer.py`'s existing tests (renamed symbols — update imports/
  references, no behavioral assertion should need to change).
- **New tests to write** (`tests/export/test_publish.py`):
  - Last-line-wins collapse over a multi-line `.jsonl` fixture.
  - Current/past split — parameterize the same `today` cases
    `writer.py`'s existing `is_current_or_upcoming` tests already
    cover, including the Work-based Learning exception, to confirm
    agreement rather than duplicating the rule's own test coverage.
  - Join against a fixture `partners.json`: an unmatched-in-source
    partner (empty event files) and a partner with events both appear
    correctly.
  - `dry_run=True` writes nothing.
  - `src/data/opportunities.json` is unaffected by a `project()` call
    (integration-level check against `writer.py`'s existing output).
- **Verification command**: `uv run pytest`

## Documentation updates

None beyond this sprint's `design/export-DESIGN.md` overlay (already
written).

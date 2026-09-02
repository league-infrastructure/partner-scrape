---
id: '002'
title: Per-region yield measurement in observability and scrape-meta.json
status: open
use-cases: [SUC-064]
depends-on: ['001']
github-issue: ''
issue: 34-audience-gaps-spanish-regional-accessibility.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Per-region yield measurement in observability and scrape-meta.json

## Description

Issue 34's core ask beyond the flags: "add the measurement" for regional
coverage, the same way `observability/`'s existing per-source yield report
already makes source-level regressions visible. South Bay had 8 records and
East County had 0 as of the issue's 2026-08-30 writing; nothing today would
show if East County regressed further or if a future sprint's regional-source
work (County Parks ICS, Tijuana Estuary, etc. — out of this sprint's own
scope) actually moved the number.

Depends on ticket 001 (`Opportunity.region`, produced by
`normalize/taxonomy.derive_region()`). This ticket only *consumes* that
already-classified value — no classification logic lives here.

Two independent surfaces, both additive, no new module:

1. `observability/yield_report.py` gains a `RegionYield` dataclass (count,
   previous_count, delta, zero — see the design overlay's Design Rationale
   for why this is a lighter shape than `SourceYield`, with no found/dated
   split and no cliff-percentage alert at this sprint's small-count scale).
   `compute_yield_report()` tallies the final `Opportunity` list by
   `getattr(opportunity, "region", "")` — no new import, preserving
   `observability/`'s documented "never imports `normalize.run.Opportunity`"
   decoupling. `YieldReport` gains `.regions: list[RegionYield]`.
   `snapshot.py` persists this run's region counts under one reserved
   top-level key, `"__regions__"` (collision-safe: real `source_id`s never
   use double-underscore wrapping), so the next run's `previous_snapshot`
   carries a baseline. `render.py` gains a "Regional coverage" section after
   the existing per-source detail.
2. `export/writer.py`'s `export_opportunities()` computes the same tally
   (a plain `Counter` over the exported current/upcoming payload's
   `.region` values — not a re-derivation, `region` already arrived
   finished from `normalize/`) and writes it into `scrape-meta.json`'s new
   `"regions"` key, alongside the existing `last_updated`.

See `clasi/sprints/033-audience-and-equity-coverage/design/observability-DESIGN.md`
and `.../design/export-DESIGN.md` for the full design and rejected
alternatives (a bare side-table instead of `RegionYield`; a nested snapshot
restructuring instead of the reserved key).

## Acceptance Criteria

- [ ] `observability/yield_report.py` gains `RegionYield` (`region: str`,
      `count: int`, `previous_count: int | None`, `delta: int | None`,
      `zero: bool`) and a region-tallying function, called from
      `compute_yield_report()`. `YieldReport.regions` is populated in the
      same order regions are first encountered, plus a final
      `"unclassified"` entry for `region == ""`.
- [ ] `zero` is set when a region had a positive `previous_count` and this
      run's `count` is 0 — the direct per-region analogue of
      `SourceYield.zero_yield`. No `previous_count` entry (first-ever run
      for that region) is not itself flagged `zero`, matching
      `_compute_source_yield`'s existing first-run-is-baseline convention.
- [ ] `snapshot.py`'s `save_snapshot()` writes this run's region counts
      under `"__regions__"`; `load_snapshot()` requires no change (it
      already returns whatever top-level keys are present). An old
      snapshot file with no `"__regions__"` key is read as "no previous
      region baseline" for every region, not an error.
- [ ] `render.py`'s `render_text()` gains a "Regional coverage" section
      (after the existing "Per-source detail" section) listing each
      region's count, delta, and a `[ZERO]` marker when `zero` is set.
- [ ] `export/writer.py`'s `export_opportunities()` writes a `"regions"`
      key into `scrape-meta.json` — `dict[str, int]`, one entry per region
      (including `"unclassified"`) — computed over the same `current`
      list already used for `opportunities.json`, after dedup/slug
      handling. Verify with `dry_run=True` too (no disk write, but the
      returned/computed shape is still correct if the function is
      refactored to expose it — check current signature before deciding
      whether `dry_run` needs to also return the meta payload, or only the
      opportunities payload as today).
- [ ] Existing `scrape-meta.json` consumers (tests asserting its exact
      shape) are updated to expect the new key; the addition does not
      change `last_updated`'s existing behavior.

## Testing

- **Existing tests to run**: `uv run pytest tests/observability/
  tests/test_export.py` (adjust paths to match actual test layout — grep
  `tests/` for `yield_report`/`scrape-meta` first) plus the full suite.
- **New tests to write**: per-region unit tests in
  `observability/yield_report.py`'s existing test module (first-run
  baseline, delta computation, zero-flag transition — mirroring
  `SourceYield`'s existing test shapes), a `snapshot.py` round-trip test for
  the `"__regions__"` key, a `render_text()` output test for the new
  section, and an `export/writer.py` test asserting `scrape-meta.json`'s
  `"regions"` key and counts for a small fixture `Opportunity` list
  spanning multiple regions plus one unclassified record.
- **Verification command**: `uv run pytest`

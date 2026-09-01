---
id: '003'
title: Remove the site_dir write from Opportunity and Ad export
status: in-progress
use-cases:
- SUC-029
depends-on:
- '002'
github-issue: ''
issue: stop-writing-to-stem-ecosystem-checkout.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Remove the site_dir write from Opportunity and Ad export

## Description

`export/writer.py`'s `export_opportunities()` and `export/ads.py`'s
`export_ads()` each currently write into both `{site_dir}/src/data/...`
and `own_data_dir` (sprint 020's dual-write pattern). Remove the
`{site_dir}/...` half of each — `own_data_dir` becomes the sole write
target. Both functions are invoked from the same two adjacent lines in
`pipeline.py`'s `run()`, which is why they're grouped in one ticket.
Depends on ticket 002 landing first (both tickets touch `pipeline.py`'s
`run()`; sequencing avoids rework).

## Acceptance Criteria

- [x] `export_opportunities()` no longer accepts a `site_dir` parameter
      and never writes `opportunities.json`/`scrape-meta.json` under
      `{site_dir}/...`. Its `own_data_dir` write is unchanged in shape.
- [x] `export_ads()` no longer accepts a `site_dir` parameter and never
      writes `ads.json` under `{site_dir}/...`. Its `own_data_dir` write
      is unchanged in shape.
- [x] `pipeline.py`'s `run()` no longer passes `site_dir` to either
      call. `run()`'s own `site_dir` parameter is unchanged (still
      resolves `partners_path` for the roster-validation read).
- [x] `is_current_or_upcoming()` and every other function in
      `export/writer.py` not related to the write target is unchanged.
- [x] Existing `TestTargetDirIsolation`-style tests (or equivalent) in
      `tests/test_export.py` and `tests/test_export_ads.py` are updated
      to assert the `{site_dir}/...` path is never created/written,
      rather than asserting it is.
- [x] `uv run pytest -q` is green.

## Implementation Plan

**Approach**: mechanical removal — delete the `site_dir` parameter and
the `try/except OSError` block that writes to it from each function;
keep the `own_data_dir` block untouched (rename any "second write"/
"third write" comments that no longer apply, e.g. "the same payload,
written a second time" language that assumed a `site_dir` write came
first).

1. `export/writer.py`: remove `export_opportunities()`'s `site_dir`
   parameter and the `resolved_site_dir`-based write block (the
   `data_dir = resolved_site_dir / "src" / "data"` section and its
   `try/except`). Keep `resolved_own_data_dir` and its write exactly as
   today, just no longer described as "the same payload, written a
   second time" (it's now the only write).
2. `export/ads.py`: the same, for `export_ads()`.
3. `pipeline.py`'s `run()`: change
   `export_opportunities(opportunities, site_dir=resolved_site_dir,
   today=today, dry_run=dry_run)` to drop `site_dir=...`; same for the
   `export_ads(...)` call.
4. Update both modules' docstrings (the "## The two write targets are
   not symmetric" / "the same already-computed payload is also written
   a second time" framing) to describe the new, simpler single-target
   contract.

**Files to modify**: `export/writer.py`; `export/ads.py`; `pipeline.py`.

**Testing plan**: update every test that constructs a `tmp_path`-backed
`site_dir` and passes it to `export_opportunities()`/`export_ads()` to
either (a) drop the now-invalid keyword argument, or (b) where the test
specifically exists to prove the site_dir write happens, invert it to
prove the write does *not* happen (a `tmp_path` passed as
`own_data_dir`, with no `site_dir` kwarg at all, and an assertion that
no unexpected files appear anywhere else). Run
`uv run pytest tests/test_export.py tests/test_export_ads.py
tests/test_pipeline_e2e.py tests/test_pipeline_e2e_ads.py
tests/test_pipeline_e2e_enrichment.py tests/test_cli.py -q` and fix
every failure this surfaces — this is expected to be the largest test
churn in the sprint (measured during planning: hundreds of `site_dir`
references across these files), but mechanical.

**Documentation updates**: `export/writer.py`'s and `export/ads.py`'s
module docstrings (see step 4 above).

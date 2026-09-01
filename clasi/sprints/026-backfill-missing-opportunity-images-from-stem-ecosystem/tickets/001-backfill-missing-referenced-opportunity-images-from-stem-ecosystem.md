---
id: '001'
title: Backfill missing referenced opportunity images from stem-ecosystem
status: in-progress
use-cases: []
depends-on: []
github-issue: ''
issue: backfill-missing-referenced-opportunity-images.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Backfill missing referenced opportunity images from stem-ecosystem

## Description

Sprint 025 redirected `EventImageDownloader`'s write target to
`data/images/opportunities/`. The first real production run populated it
with 375 images — a snapshot of that run's *current* opportunities, not
the accumulated history `export/publish.py`'s `project()` publishes via
`data/partners/<slug>/events.json` and `.../past-events.json` (which
reflect every opportunity ever seen for that partner, via the persistent
per-partner log under `SCRAPE_CACHE_DIR`). Diffing every `image_src`
filename referenced across `data/partners/*/{events,past-events}.json`
against `data/images/opportunities/`'s actual contents turns up **172
referenced-but-missing filenames** (out of 449 distinct filenames
referenced total) — confirmed independently three times (stem-ecosystem
peer session, team-lead, sprint-planner), all in agreement. All 172 were
also confirmed to exist, unresized, at
`../stem-ecosystem/public/images/opportunities/` on this same machine.
`data/opportunities.json`'s own image references are a separate,
already-passing control: 143 referenced, all 143 present.

Team-lead's decision (settled, not open for this ticket to
re-litigate): seed ONLY the 172 currently-referenced-but-missing images,
copied by exact filename from
`../stem-ecosystem/public/images/opportunities/` — not all 631 images in
that directory, and not resized/re-encoded (they stay pre-resize
originals until a future re-fetch naturally replaces them). See
sprint.md's Problem/Solution for the full reasoning, and issue
`backfill-missing-referenced-opportunity-images.md` for the original
gap report.

## Implementation Plan

**Approach**: write one new standalone script,
`dev/backfill_missing_images.py`, matching
`dev/refresh_school_directories.py`'s established convention exactly:
stdlib only (no import of `partner_scrape.*` — computes `REPO_ROOT` via
`Path(__file__).resolve().parent.parent`, the same pattern
`refresh_school_directories.py` uses for its own output paths), never
imported by runtime code, run by hand, with a module docstring stating
when/why to re-run it. Read `dev/refresh_school_directories.py` in full
first for the exact style/structure to mirror (shebang, docstring
framing, `if __name__ == "__main__":` entry point, argument handling).

1. **Referenced-filename derivation** (`_referenced_image_filenames(data_dir: Path) -> dict[str, set[Path]]`
   or similar): glob `data_dir / "partners" / "*" / "events.json"` and
   `.../past-events.json`; for each, `json.loads()` and pull
   `event["image_src"]` for every entry in `events` (skip falsy values —
   matches `EventImageDownloader.download()`'s existing "empty string
   means no image" contract). Separately do the same for
   `data_dir / "opportunities.json"` (top-level shape: check the actual
   file — confirm whether it's a bare list or an envelope dict with an
   `opportunities`/similar key — and extract each record's `image_src`)
   as an independent control set, kept separate from the partners-derived
   set so the two checks can be reported independently.
2. **Diff against existing files**: `existing = {p.name for p in
   (data_dir / "images" / "opportunities").glob("*")}`; `missing =
   referenced - existing`, for both the partners-derived set and the
   opportunities.json-derived set, reported separately.
3. **Check-only mode** (default, no `--source-dir`): print a summary —
   referenced count, existing count, missing count, and (if any) the
   full list of missing filenames — for both checks. Exit code 0 if both
   checks show zero missing, non-zero otherwise (makes the script usable
   as a future integrity-check gate, not just an interactive report).
4. **Backfill mode** (`--source-dir <path>` given): for each filename in
   the partners-derived missing set, check whether it exists in
   `--source-dir`; if so, `shutil.copy2()` it into
   `data_dir / "images" / "opportunities"` (preserves mtime; the write is
   exact-byte, no re-encode — `copy2`, not a re-save through any image
   library). If a referenced filename is missing from *both*
   `data/images/opportunities/` and `--source-dir`, log it clearly as
   "not found in source either" and continue (do not fail the whole run
   over one, but do report it prominently, and it will still show up as
   `missing` in Step 5's post-copy re-check). After copying, re-run the
   Step 2/3 diff and print the after-counts, so a single invocation shows
   before → copied → after in one run.
5. **CLI surface**: `argparse` with `--data-dir` (default: repo-root-
   relative `data/`), `--source-dir` (optional; omitted = check-only),
   `--dry-run` (when combined with `--source-dir`, report what *would* be
   copied without writing) — mirrors this project's existing `dry_run`
   convention named in `export/DESIGN.md` even though this script is
   outside the pipeline.
6. **Live execution** (this ticket, not deferred): run the script for
   real — `uv run python dev/backfill_missing_images.py --source-dir
   ../stem-ecosystem/public/images/opportunities` — against the actual
   `data/` tree and the actual sibling checkout. Record the exact
   before/after output (referenced/existing/missing counts, before and
   after) in this ticket's Notes section once run.
7. **Post-copy verification**: re-run the script in check-only mode
   (`uv run python dev/backfill_missing_images.py`) and confirm both
   checks report zero missing. Confirm via `git status
   data/images/opportunities/` that exactly 172 new files were added and
   nothing existing was modified or removed.

**Files to create**: `dev/backfill_missing_images.py`.

**Files modified by the live run (data, not code)**: 172 new files under
`data/images/opportunities/` (byte-identical copies from
`../stem-ecosystem/public/images/opportunities/`).

**No files under `partner_scrape/` are touched** — this ticket adds no
pipeline code and changes no runtime import graph.

## Acceptance Criteria

- [ ] `dev/backfill_missing_images.py` exists, is stdlib-only (no import
      of `partner_scrape.*`), and is never imported by anything under
      `partner_scrape/` or `tests/`.
- [ ] Running the script with no `--source-dir` (check-only mode)
      against the real `data/` tree correctly reports the current
      referenced/existing/missing counts for both the
      `data/partners/*` check and the `data/opportunities.json` check,
      and exits non-zero while any missing filename remains.
- [ ] Running the script with `--source-dir
      ../stem-ecosystem/public/images/opportunities` performs a real,
      non-dry-run backfill: every one of the 172 referenced-but-missing
      filenames present in that source directory is copied byte-
      identically into `data/images/opportunities/`.
- [ ] Any referenced filename missing from *both* `data/images/opportunities/`
      and `--source-dir` is reported clearly and does not silently pass
      as success (expected count: zero, based on this sprint's planning-
      time verification, but the script must not assume that holds at
      execution time).
- [ ] After the backfill, re-running the script in check-only mode shows
      **zero** missing for both checks.
- [ ] `data/opportunities.json`'s referenced-image check remains
      unchanged at 143/143 present after the backfill (confirms the copy
      didn't disturb this already-passing contract).
- [ ] `git status` shows exactly 172 new files added under
      `data/images/opportunities/`, and no existing file under that
      directory (or anywhere else under `data/` or `partner_scrape/`)
      modified or removed.
- [ ] This ticket's Notes section records the exact before/after counts
      from the live run (referenced/existing/missing, before and after
      the copy).
- [ ] `uv run pytest -q` is green.

## Testing

- **Existing tests to run**: `uv run pytest -q` (full suite — this
  ticket adds no pipeline code, so this is a regression check, not a
  targeted one).
- **New tests to write**: none. See sprint.md's Test Strategy for the
  reasoning — this repo's own `dev/refresh_school_directories.py`
  precedent (a comparably-sized standalone provisioning script) has no
  dedicated pytest module either; it's run by hand and its output
  reviewed by diff. This script's core logic (scan JSON for a field,
  set-difference against directory contents, copy by exact filename) is
  straight-line I/O with no branching complex enough to justify a
  separate hermetic harness, and the live re-verification pass (Step 7
  above / this ticket's own acceptance criteria) is a stronger, more
  direct correctness proof for a data-repair operation than a fixture
  asserting the internal function's behavior on synthetic inputs would
  be.
- **Verification command**: `uv run pytest` (regression check), plus the
  script's own check-only invocation as the actual correctness proof for
  this ticket's specific change (see Acceptance Criteria).

## Notes

(To be filled in by the ticket executor after the live run: exact
before/after referenced/existing/missing counts for both checks, and the
count of files actually copied.)

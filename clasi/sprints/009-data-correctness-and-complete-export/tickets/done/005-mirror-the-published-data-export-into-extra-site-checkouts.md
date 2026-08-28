---
id: '005'
title: Mirror the published data export into extra site checkouts
status: done
use-cases:
- SUC-007
depends-on:
- '004'
github-issue: ''
issue: 15-publish-complete-self-describing-data-export.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Mirror the published data export into extra site checkouts

## Description

Ticket 004's `publish.project(...)` writes the new `public/data/` tree
into the primary `site_dir`. Today's `export/mirror.py` only knows how
to copy a flat allowlist of files (`MIRRORED_DATA_FILES`) plus one
images directory into extra site checkouts (e.g. this repo's own
`site/`, the beta checkout `just dev` serves) — it has no notion of
copying a directory tree. This ticket extends `mirror_site_data` to
also recursively copy `public/data/` into each target, using the same
additive, byte-identical-skip semantics the existing image mirror
(`_mirror_images`) already establishes, and sequences the CLI call
order so a mirrored checkout always receives an already-projected,
complete tree.

See `design/export-DESIGN.md` for the full rationale (why this is
additive-only, matching the existing image-mirroring precedent, and
why `publish.project()` must run before `mirror_site_data()`).

## Acceptance Criteria

- [x] `mirror_site_data` recursively copies `{primary_site_dir}/public/data/`
      into `{target}/public/data/` for each target, in addition to its
      existing `MIRRORED_DATA_FILES` + `public/images/opportunities/`
      copy — same function, extended, not a new entry point.
- [x] A target with no pre-existing `public/data/` directory receives
      the full tree.
- [x] A target with a byte-identical file already present is not
      rewritten (same size/mtime skip check `_mirror_images` already
      uses).
- [x] A target missing `src/data/` entirely is still skipped with a
      warning, unchanged from today's existing behavior (the
      `public/data/` copy does not introduce a new failure mode for
      that case).
- [x] `dry_run=True` logs what would be copied for the new tree too,
      writing nothing — matching the existing contract.
- [x] `cli.py`'s call order is: `run()` returns → `publish.project(...)`
      → `mirror_site_data(...)` — both skipped under `--dry-run`,
      matching the existing mirror step's gating.

## Implementation Plan

**Approach**: Extend `mirror.py`'s existing per-file copy loop with a
second, small recursive-copy pass for the `public/data/` tree, reusing
the same byte-identical-skip helper pattern `_mirror_images` already
implements (generalize it, or add a directly analogous
`_mirror_directory_tree` helper — implementer's judgment, whichever
keeps `_mirror_images` itself unchanged and readable).

**Files to modify**:
- `partner_scrape/export/mirror.py` — add the `public/data/` recursive
  copy to `mirror_site_data`.
- `partner_scrape/cli.py` — insert the `publish.project(...)` call
  (from ticket 004) immediately before the existing `mirror_site_data`
  call, both still gated by `not args.dry_run`.

**No files to create**, unless the implementer chooses a separate
helper module for the recursive-copy logic (not required).

## Testing

- **Existing tests to run**: `uv run pytest`, with attention to
  `mirror.py`'s existing test module (flat-file and image-mirroring
  behavior must be unaffected).
- **New tests to write**:
  - A target checkout with no `public/data/` receives the full tree
    from the primary.
  - A target with an unchanged file already present is not rewritten
    (assert via mtime/content, matching the existing image-mirror
    test's pattern).
  - A target missing `src/data/` is still skipped with a warning; the
    `public/data/` copy is not attempted for it.
  - `dry_run=True` writes nothing for the new tree.
  - CLI-level (or a thin integration test): `publish.project()` output
    is present in the target checkout after a full `cli.main()` run
    with a configured mirror target.
- **Verification command**: `uv run pytest`

## Documentation updates

None beyond this sprint's `design/export-DESIGN.md` overlay (already
written).

---
id: '001'
title: Remove the MIRROR_SITE_DIRS mirroring mechanism
status: in-progress
use-cases:
- SUC-002
depends-on: []
github-issue: ''
issue: consolidate-partner-scrape-s-beta-site-into-stem-ecosystem-production.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Remove the MIRROR_SITE_DIRS mirroring mechanism

## Description

`export/mirror.py`'s `mirror_site_data()` exists solely to copy a
finished pipeline export into extra site checkouts so they stay in step
with the primary `SITE_DIR` write target. Sprint 019 makes
`stem-ecosystem` the one canonical site codebase (ticket 002 converts
`partner-scrape/site/` — previously the mirror's default target — into a
build-time-only CI checkout, no longer a second git-tracked, locally
mirrored-into directory). With no second checkout left, this mechanism
has nothing to do. Remove it in full, not just its default target.

This is a removal-only ticket: delete code and tests, do not replace the
mechanism with anything.

**Files to change:**

- `partner_scrape/config.py` — remove `MIRROR_SITE_DIRS_ENV_VAR`,
  `DEFAULT_MIRROR_SITE_DIR`, and `get_mirror_site_dirs()` entirely.
  `SITE_DIR_ENV_VAR`/`DEFAULT_SITE_DIR`/`get_site_dir()` are unaffected
  in *value* — `DEFAULT_SITE_DIR` still resolves to `../stem-ecosystem`
  — but its docstring currently reads: "matching the layout
  `dev/export_site.py` already assumes" and exists alongside
  `DEFAULT_MIRROR_SITE_DIR`'s own docstring, which frames
  `DEFAULT_SITE_DIR` implicitly as "the one *other* than the mirror
  target." Rewrite `DEFAULT_SITE_DIR`'s docstring so it stands alone:
  the sibling `stem-ecosystem` checkout used for local interactive runs
  and by default in CI, overridable via `SITE_DIR`, with no reference to
  `dev/export_site.py` (a file ticket 003 archives — don't leave a
  dangling reference regardless of that ticket's exact timing) or to any
  mirror relationship.
- `partner_scrape/export/mirror.py` — delete the file entirely.
- `partner_scrape/cli.py` — remove:
  - the `from partner_scrape.config import get_mirror_site_dirs, ...`
    import (keep `get_site_dir`) and the
    `from partner_scrape.export.mirror import mirror_site_data` import;
  - the `--mirror-site-dir` argument (main parser) and every
    `--no-mirror` argument (main parser, `teams` subparser, `directory`
    subparser);
  - the three mirroring code blocks that call `mirror_site_data(...)`
    after `run`/`teams`/`directory` complete (in `main()`, `_run_teams()`,
    `_run_directory()`) — including their guard conditions
    (`if not args.dry_run and not args.no_mirror: ...`) and the
    docstrings/comments that describe "keep every other checkout of the
    site in step."
- `tests/test_export_mirror.py` — delete the file entirely (28 tests;
  this is the mechanism's own dedicated test module, with nothing left
  to test once `mirror.py` is gone).
- `tests/test_cli.py`, `tests/test_cli_teams.py`,
  `tests/test_cli_directory.py` — remove every test that exercises
  `--mirror-site-dir`, `--no-mirror`, `mirror_site_data`, or
  `get_mirror_site_dirs`. `grep -n mirror` against each file first (this
  ticket's investigation already did — see the reference line ranges
  below) to make sure nothing is missed:
  - `test_cli.py`: `test_publish_project_runs_even_under_no_mirror`,
    `test_publish_project_is_sequenced_before_mirror_site_data`,
    `test_published_tree_reaches_a_configured_mirror_target`,
    `test_default_run_path_invokes_mirror_site_data_when_config_unset`,
    `test_mirror_still_runs_when_publish_project_raises`, plus any
    `monkeypatch.setattr(cli, "mirror_site_data", ...)` /
    `monkeypatch.setattr(cli, "get_mirror_site_dirs", ...)` left in
    other tests' setup.
  - `test_cli_teams.py`: the `--no-mirror` help-text assertion
    (`assert "--no-mirror" in out`),
    `test_mirror_is_called_when_not_dry_run_and_not_no_mirror`,
    `test_no_mirror_flag_skips_mirroring`, `test_dry_run_skips_mirroring`
    (confirm it tests only mirror-skip behavior before deleting — if it
    also asserts something about `--dry-run` unrelated to mirroring,
    trim rather than delete), `test_no_mirror_targets_configured_skips_mirror_call`.
  - `test_cli_directory.py`: the same shape as `test_cli_teams.py` —
    `--no-mirror` help-text assertion,
    `test_mirror_is_called_when_not_dry_run_and_not_no_mirror`,
    `test_no_mirror_flag_skips_mirroring`, `test_dry_run_skips_mirroring`
    (same caution as above), `test_no_mirror_targets_configured_skips_mirror_call`.
  - **Do not delete whole tests that conflate mirror assertions with
    core write-path coverage.** `test_cli_teams.py`'s
    `test_real_run_writes_teams_json_and_mirrors_to_a_target` and
    `test_cli_directory.py`'s
    `test_real_run_writes_places_json_and_mirrors_to_a_target` (and its
    matching `test_no_mirror_flag_leaves_the_target_untouched`) each
    verify a real, non-mirror-related behavior (`teams.json`/`places.json`
    actually gets written correctly) alongside the mirror assertion.
    Trim these down to keep the write-path coverage and drop only the
    mirror-specific portion — don't lose that coverage by deleting the
    whole test.
- Subsystem docs that document this mechanism — update, don't just
  leave stale:
  - `partner_scrape/export/DESIGN.md` — remove `mirror.py`'s entire
    Orientation bullet, its Design-section rationale paragraph ("Why
    `mirror.py` exists..."), its Interfaces entry, its mermaid diagram's
    `MIRROR`/`TARGET` nodes and the edge into them, and its
    `MIRRORED_DATA_FILES`-related Constraints/Invariants bullets. Note in
    a short addition that the mechanism was removed in sprint 019 once
    `partner-scrape` stopped tracking a second site checkout — matching
    this doc's existing convention of noting *when* something changed,
    not just what the current state is.
  - `partner_scrape/DESIGN.md` — remove the `--mirror-site-dir`/
    `--no-mirror` CLI flag mentions and the `MIRROR_SITE_DIRS`
    environment-variable mention.
  - `partner_scrape/teams/DESIGN.md` — remove the `[--no-mirror]` CLI
    usage-string fragments, the `export.mirror_site_data()` call-site
    description in the `teams` pipeline diagram/text, and the
    `config.get_mirror_site_dirs()` mention in its own Consumes-style
    listing. Leave the surrounding "mirrors, never imports `enrich/`"
    language alone — that is a different, unrelated use of the word
    "mirrors" (describing `teams/`'s LLM-cache module shape, not this
    mechanism) and must not be touched.

## Acceptance Criteria

- [x] `export/mirror.py` no longer exists.
- [x] `config.MIRROR_SITE_DIRS_ENV_VAR`, `config.DEFAULT_MIRROR_SITE_DIR`,
      and `config.get_mirror_site_dirs()` no longer exist;
      `config.DEFAULT_SITE_DIR`'s value is unchanged
      (`../stem-ecosystem`), only its docstring is rewritten.
- [x] `cli.py` has no `--mirror-site-dir` or `--no-mirror` flag on any
      subcommand, and no import of `partner_scrape.export.mirror` or
      `get_mirror_site_dirs`.
- [x] `tests/test_export_mirror.py` is deleted.
- [x] No test in `test_cli.py`/`test_cli_teams.py`/`test_cli_directory.py`
      references `mirror_site_data`, `get_mirror_site_dirs`,
      `--mirror-site-dir`, or `--no-mirror`; the write-path coverage in
      the two "real run ... and mirrors" tests is preserved (trimmed,
      not deleted).
- [x] `export/DESIGN.md`, `partner_scrape/DESIGN.md`, and
      `teams/DESIGN.md` no longer describe the mirror mechanism as live;
      each notes it was removed in sprint 019.
- [x] `git grep -n MIRROR_SITE_DIRS` and `git grep -n mirror_site_data`
      return nothing outside `clasi/` (sprint/issue history) and the
      three `DESIGN.md` "removed in sprint 019" notes.
- [x] Full `uv run pytest -q` is green.

## Testing

- **Existing tests to run**: `uv run pytest -q` (full suite — this
  ticket deletes tests, so a full run is the only way to confirm nothing
  else broke).
- **New tests to write**: none — this is a removal ticket; the
  mechanism being removed has no replacement to test.
- **Verification command**: `uv run pytest -q`, plus
  `git grep -n "MIRROR_SITE_DIRS\|mirror_site_data\|get_mirror_site_dirs\|mirror-site-dir\|no-mirror"`
  to confirm no stray reference remains outside the documented
  `DESIGN.md` history notes.

---
id: '001'
title: Fix the run-command mirror step
status: open
use-cases:
- SUC-003
depends-on: []
github-issue: ''
issue: 43-run-command-mirror-step-did-not-fire.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix the run-command mirror step

## Description

After the 2026-08-31 post-016 production run (plain `uv run
partner-scrape`, exit 0, wrote 350 opportunities to `../stem-ecosystem`),
this repo's beta `site/src/data/opportunities.json` was still the prior
312-record snapshot. The mirror block at `cli.py:477-485` should have
fired (no `--dry-run`, no `--no-mirror`, `MIRROR_SITE_DIRS` unset →
default `site/`). A manual `mirror_site_data('../stem-ecosystem',
['site'])` immediately afterward worked, so the copy machinery itself
(`export/mirror.py`) is fine — this is specific to how the default
`run` path reaches (or fails to reach) that block.

The same day, the structurally identical `teams` subcommand's own
mirror block (`cli.py:347`, `_run_teams`) fired correctly. Both blocks
share the same shape (`if not args.dry_run and not args.no_mirror:
targets = get_mirror_site_dirs(); ... mirror_site_data(primary,
targets)`), so the bug is specific to the default (no-subcommand) path,
not to `mirror_site_data()` or `get_mirror_site_dirs()` themselves —
confirmed during sprint planning that `get_mirror_site_dirs()` and
`DEFAULT_MIRROR_SITE_DIR` resolve via `Path(__file__)`-anchored
`_REPO_ROOT`, not CWD, so a CWD-relative path bug is an unlikely root
cause; investigate the other two hypotheses from the issue instead:

- An exception inside the mirror block (or inside
  `publish.project()`, which runs immediately before it) that gets
  swallowed before the final "wrote N opportunities" line — the run's
  stdout tail showed no mirror log lines at all, which is also
  consistent with the block simply never being reached.
- Something about the default/no-subcommand code path specifically
  (rather than the `run` command in the abstract) that skips past
  `cli.py:477`, despite `argparse` wiring appearing correct.

## Acceptance Criteria

- [ ] The actual root cause of the 2026-08-31 failure is identified
      and recorded in this ticket's Notes — not just worked around.
- [ ] A regression test asserts the default (no-subcommand) `main()`
      path invokes `mirror_site_data()` when `MIRROR_SITE_DIRS` is
      unset and neither `--dry-run` nor `--no-mirror` is passed
      (mock/spy `mirror_site_data`, don't touch a real filesystem
      checkout).
- [ ] A live re-run with `-v` shows mirror log lines in stdout
      (`export/mirror.py`'s existing `logger.info("Mirrored the export
      into %s", target)` line), unlike the 2026-08-31 run's silent
      tail.
- [ ] No change to `export/mirror.py`'s copy logic itself — the issue's
      own finding is that the copy machinery works; only the
      caller-side wiring in `cli.py` is suspect.
- [ ] Full test suite stays green.

## Testing

- **Existing tests to run**: `uv run pytest`, focusing on any existing
  `tests/test_cli.py` coverage of the default `run` path and the
  `teams` subcommand's mirror behavior (use the latter as the working
  reference case).
- **New tests to write**: a regression test (see Acceptance Criteria)
  asserting the default path calls `mirror_site_data()` under the
  documented default conditions; if the root cause turns out to be an
  exception-swallowing bug, add a test asserting that exception is no
  longer swallowed (surfaces as a non-zero exit or a logged error,
  matching this codebase's existing error-isolation conventions rather
  than a bare silent pass).
- **Verification command**: `uv run pytest`, plus a live `-v` run
  against a real (or test-fixture) mirror target to visually confirm
  the log lines this ticket's AC requires.

## Implementation Plan

**Approach**: Systematic debugging — reproduce with `-v` first (per
the issue's own instruction), form a hypothesis from the actual
stdout/log evidence, then fix the narrowest thing that explains it.
Do not restructure `cli.py`'s subcommand dispatch or `mirror.py`'s copy
logic beyond what the root cause requires.

**Files to modify**:
- `partner_scrape/cli.py` — the default `run` path's mirror block
  (around line 477) and/or `publish.project()` call immediately before
  it, depending on root cause.
- `tests/test_cli.py` (or wherever existing CLI tests live) — new
  regression test.

**Testing plan**: see Testing above.

**Documentation updates**: if the root cause reveals a real gap in
`export/mirror.py`'s or `cli.py`'s own docstrings (e.g. an
undocumented failure mode), update the relevant docstring — but only
to describe what was actually found, not speculatively.

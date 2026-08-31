---
id: '001'
title: Fix the run-command mirror step
status: done
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

- [x] The actual root cause of the 2026-08-31 failure is identified
      and recorded in this ticket's Notes — not just worked around.
- [x] A regression test asserts the default (no-subcommand) `main()`
      path invokes `mirror_site_data()` when `MIRROR_SITE_DIRS` is
      unset and neither `--dry-run` nor `--no-mirror` is passed
      (mock/spy `mirror_site_data`, don't touch a real filesystem
      checkout).
- [x] A live re-run with `-v` shows mirror log lines in stdout
      (`export/mirror.py`'s existing `logger.info("Mirrored the export
      into %s", target)` line), unlike the 2026-08-31 run's silent
      tail.
- [x] No change to `export/mirror.py`'s copy logic itself — the issue's
      own finding is that the copy machinery works; only the
      caller-side wiring in `cli.py` is suspect.
- [x] Full test suite stays green.

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

## Notes

**Root cause (confirmed, not hypothesized):** the mirror block's own
condition/target-resolution logic at `cli.py:477-485` was never wrong.
The actual failing 2026-08-31 run log survived in this session's
scratchpad (`run-post-016.log`) and ends in an *uncaught* traceback:

```
File "partner_scrape/cli.py", line 469, in main
    publish.project(...)
File "partner_scrape/export/publish.py", line 262, in project
    collapsed = [_to_opportunity(entry) for entry in _collapse_last_line_wins(jsonl_path)]
File "partner_scrape/export/publish.py", line 132, in _to_opportunity
    kwargs: dict[str, Any] = {name: entry[name] for name in _OPPORTUNITY_FIELD_NAMES}
KeyError: 'eligibility'
```

`publish.project()` (called at `cli.py:469`, immediately before the
mirror block) reads *every* line ever appended to a partner's
append-only `.jsonl` accumulation log (`export/partner_log.py`) and
reconstructs each as an `Opportunity` by dict-subscripting every
current dataclass field name out of the stored entry
(`_to_opportunity`, `publish.py:132`). `eligibility` was added to
`Opportunity` in sprint 015 (`git log -S eligibility` ->
`b0570aa 015-008: add eligibility field end-to-end`), but the log is
append-only and never migrated/rewritten — any line recorded before
that sprint lacks the key. Reconstructing one such legacy line raises
`KeyError('eligibility')`.

`main()` had no `try`/`except` anywhere in this path, so that
exception propagated straight out of the console-script entry point
and crashed the whole process — **before** the mirror block at
`cli.py:477` was ever reached. That is the entire explanation for "no
mirror-related lines at all" in the run's stdout: the code that would
have logged them never executed. It also means the run's true exit
code was non-zero (a crash), not `0` — the "exited 0 / wrote 350
opportunities" belief in this ticket's own Description/issue 43 was an
inference from the 350 records already sitting in `../stem-ecosystem`
(written directly by `pipeline.run()`, earlier in `main()` and
independent of `publish.project()`), not from the CLI's own summary
line, which is printed even later (`cli.py:489`) and also never ran.

Every hypothesis this ticket's Description/issue 43 raised about the
mirror block or `get_mirror_site_dirs()`/CWD-relative resolution was
checked directly and ruled out by live reproduction (in-process,
via a real `uv run partner-scrape` subprocess against fixture
site-dirs, and — once, deliberately, with `site/` reverted via
`git checkout -- site/` immediately after — against this repo's real
default mirror target) before the JSONL-schema-drift theory was
found: in every case, with `publish.project()` stubbed or succeeding,
the existing mirror block already worked correctly. The bug was never
in the block the ticket named; it was in whether execution ever
reached it.

**Fix:** `cli.py`'s `publish.project()` call is now wrapped in
`try`/`except Exception`, logged via a new module-level
`logger.exception(...)` (matching `pipeline._run_one_source`'s
existing per-source error-isolation convention — logged loudly, never
silently caught) rather than left to crash `main()`. Execution then
continues to the mirror block unconditionally (mirroring never
depended on `publish.project()` succeeding: `opportunities.json` /
`teams.json` / `scrape-meta.json` / `ads.json` are all written by
`run()` directly, earlier and independently). `main()`'s return value
changes from an unconditional `0` to `1` whenever `publish.project()`
failed, so the failure is visible on the exit code, not only in the
log — this is the "surfaced, not silently swallowed" shape the
ticket's own Testing section anticipated for this exact scenario.

**Live verification (AC3):** reproduced the *exact* historical
failure end-to-end — a real `uv run partner-scrape -v` subprocess
against fixture `--site-dir`/`--mirror-site-dir` checkouts, with a
partner_log `.jsonl` line built via the real `partner_log.record()`
and then stripped of its `eligibility` key (simulating a genuine
pre-sprint-015 legacy line). Output: `ERROR partner_scrape.cli:
publish.project() failed; ...` with the identical `KeyError:
'eligibility'` traceback, immediately followed by `INFO
partner_scrape.export.mirror: Mirrored the export into <target>`, and
exit code `1`. The mirror target's `opportunities.json` was confirmed
byte-identical to the primary's. This is the fixed code visibly doing
what the 2026-08-31 run did not.

**Out of scope, flagged for follow-up:** the underlying
`KeyError`-on-legacy-data defect in `publish.py`'s `_to_opportunity()`
(schema drift in the append-only `.jsonl` log whenever an `Opportunity`
field is added after entries already exist) is not fixed here — this
ticket's own Implementation Plan scoped file changes to `cli.py` and
`test_cli.py`, and AC4 already establishes that only cli.py's
caller-side wiring was suspect. `publish.project()` will keep failing
on this same partner's history until that JSONL-reconstruction gap is
fixed (e.g. defaulting missing fields from `Opportunity`'s own
dataclass defaults) — recommend a follow-up ticket. Until then, this
fix guarantees that failure degrades to "public/data/ stays stale,
loudly, with a non-zero exit" instead of "the entire run silently
fails to mirror."

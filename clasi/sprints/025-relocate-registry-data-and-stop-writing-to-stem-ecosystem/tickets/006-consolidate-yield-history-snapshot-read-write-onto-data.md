---
id: '006'
title: Consolidate yield-history snapshot read/write onto data/
status: in-progress
use-cases:
- SUC-029
depends-on: []
github-issue: ''
issue: stop-writing-to-stem-ecosystem-checkout.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Consolidate yield-history snapshot read/write onto data/

## Description

`cli.py`'s `main()` currently reads the *previous* run's yield-history
snapshot from `{resolved_site_dir}/src/data/yield-history.json` (via
`load_snapshot()`, used to compute this run's found/dropped delta)
before `run()` executes, and writes the new snapshot to that same path
plus a second, independent `own_data_dir` copy (sprint 020 ticket 007).

Found during this sprint's own investigation, not in Eric's original
enumeration: removing only the *write* half (as literally listed) would
leave the *read* pointed at a file that stops being updated — freezing
every future delta computation against a stale snapshot forever. Both
the read and the write must move to `own_data_dir` together. See
sprint.md's Design Rationale ("consolidate `cli.py`'s yield-history read
*and* write...") for the full reasoning.

## Acceptance Criteria

- [ ] `yield_history_path`'s default (used when `--yield-history` is
      not given) resolves to `{own_data_dir}/yield-history.json`, not
      `{resolved_site_dir}/src/data/yield-history.json`.
- [ ] `main()` calls `load_snapshot()` once, against this new default
      (or the explicit `--yield-history` override), and `save_snapshot()`
      once, against the same path — not two `save_snapshot()` calls.
- [ ] `--yield-history` remains available as an explicit override,
      unchanged in behavior.
- [ ] The first run after this change, with no pre-existing snapshot at
      the new default location, produces an empty-baseline delta report
      (`load_snapshot()`'s existing "first run ever" contract) rather
      than an error.
- [ ] `uv run pytest -q` is green.

## Implementation Plan

**Approach**: this is entirely inside `cli.py`'s `main()`, in the
`if not args.no_report:` block — no change to `observability/
snapshot.py` itself (its `load_snapshot`/`save_snapshot` are already
plain-path, no `Config` coupling, per that module's own docstring).

1. In `main()`, change:
   ```
   resolved_site_dir = args.site_dir if args.site_dir is not None else get_site_dir()
   yield_history_path = (
       args.yield_history
       if args.yield_history is not None
       else resolved_site_dir / "src" / "data" / "yield-history.json"
   )
   ```
   to default against `get_own_data_dir()` instead of
   `resolved_site_dir`. Confirm whether `resolved_site_dir` is still
   needed elsewhere in `main()` (it is — `publish.project()`'s call
   below still needs it) before deciding whether to keep or restructure
   that local variable; don't remove it if another call site still
   depends on it.
2. Remove the second `save_snapshot(get_own_data_dir() / "yield-history.json",
   report)` call added by sprint 020 ticket 007 — it's now redundant
   with the (single) call at `yield_history_path`, which already
   defaults there.

**Files to modify**: `cli.py`.

**Testing plan**: update `tests/test_cli.py`'s yield-history assertions
to expect the `own_data_dir`-based default path for both the pre-run
`load_snapshot()` read and the post-run `save_snapshot()` write, and to
confirm exactly one `save_snapshot()` call happens (not two). Add a
regression case: a previously-written snapshot at the new default
location is picked up by the next run's delta computation (read and
write agree on the same file). Run `uv run pytest tests/test_cli.py -q`.

**Documentation updates**: none required beyond inline comments at the
call site explaining why read and write share one default now.

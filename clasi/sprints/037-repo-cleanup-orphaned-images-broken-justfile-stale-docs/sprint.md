---
id: '037'
title: 'Repo cleanup: orphaned images, broken justfile, stale docs'
status: executing
branch: sprint/037-repo-cleanup-orphaned-images-broken-justfile-stale-docs
use-cases: []
issues:
- 48-repo-cleanup-stale-cruft.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 037: Repo cleanup: orphaned images, broken justfile, stale docs

## Goals

Work through issue 48's seven verified cleanup items: prune orphaned
opportunity images, remove the broken/dangerous `justfile`, rewrite the
README's stale publishing section, reword two stale cross-references,
close three `.gitignore` gaps, remove a redundant `.gitkeep`, and
resolve the four empty `config/` files (delete or document why they
stay).

## Problem

Issue 48 is a verified survey (approved 2026-09-04) of small pieces of
cruft accumulated since sprint 019 moved the site out of this repo and
since publishing was disabled 2026-09-03: an orphaned-image set, a
`justfile` that both no longer works (`site/` doesn't exist here) and
still contains a recipe that pushes `master` and dispatches a disabled
Pages workflow, docs describing publishing that's turned off, two
comments citing deleted files, ungitignored sqlite/pytest-cache
artifacts, a no-op `.gitkeep`, and four zero-byte config files of
uncertain provenance.

## Solution

Three tickets, ordered by risk and by which pieces must land together:

1. Add a `--prune` mode to the existing `dev/backfill_missing_images.py`
   (issue item 1) — it already computes the referenced-filename set for
   its check mode, so pruning is the set-difference in the other
   direction.
2. Retire the `justfile` (removing `pub` outright, since it pushes
   `master` under a push freeze and dispatches a disabled workflow) and
   rewrite the README's beta-preview section to match — these two must
   change together so they stay consistent (issue items 2 and 3).
3. Tidy the remaining small items as one batch: reword the two stale
   `dev/inventory_sitemaps.py` / `dev/lib/sitemap_parser.py`
   cross-references as historical provenance, close the three
   `.gitignore` gaps, remove `docs/design/.gitkeep`, and resolve the
   four empty `config/` files — verifying against `dotconfig`'s deploy
   layout before deleting any of them (issue items 4-7).

## Success Criteria

- `dev/backfill_missing_images.py`'s check mode reports 0 missing after
  the prune runs.
- No `justfile` recipe pushes `master` or dispatches `pages.yml`.
- `just --list` (if a `justfile` still exists at all) runs clean with no
  recipe pointing at a path that doesn't exist; README's publishing
  section matches actual repo state.
- `.gitignore` covers the three named artifacts; `git status` shows them
  clean on a fresh checkout that has generated them.
- The four empty `config/` files are either removed or explicitly kept
  with a recorded reason in issue 48.
- Full test suite green (baseline 2531 passing) with no test touching
  the live network, the live Anthropic API, or writing into the
  `stem-ecosystem` checkout.

## Scope

### In Scope

All seven numbered items in issue 48: orphaned opportunity images,
`justfile`, README's publishing section, two stale file
cross-references, three `.gitignore` gaps, `docs/design/.gitkeep`, and
the four empty `config/` files.

### Out of Scope

Per issue 48: `dev/refresh_school_directories.py` and
`dev/backfill_missing_images.py` themselves as scripts (only the latter
gains a mode — neither is deleted or relocated); the 241 unreviewed
`registry/candidates/` stubs; the 26 byte-identical files shared by
`.agents/` and `.claude/`. Also out of scope: any change to the actual
`pages.yml` workflow file (it is already disabled; this sprint only
removes the repo-local recipe that dispatches it) and any decision about
whether publishing is ever turned back on.

## Test Strategy

No new subsystem or data-model change means no new unit-test surface
beyond the image-prune mode. That mode gets direct tests against a
fixture data directory (never the real `data/` tree — see the
`get_own_data_dir()` hazard noted below) covering: files referenced by
`opportunities.json` are kept, files referenced only by a partner's
`events.json`/`past-events.json` are kept, files referenced by neither
are pruned, and a `--dry-run` pass reports without deleting. The
existing check-mode tests (if any) must continue passing unchanged. The
full suite must stay green with no network access, no
`ANTHROPIC_API_KEY` usage, and no writes outside a pytest `tmp_path` —
in particular, any test that reaches an export function must pin
`get_own_data_dir()` to `tmp_path` rather than let it resolve to the
real repo path. Non-code items (justfile, README, gitignore, stale
comments, config files) are verified by inspection and by running `just
--list` / `git status` against a real checkout, not by automated tests.

## Architecture

Trivial — no new module, no cross-module dependency, no data-model
change. The only change touching runtime code is an additive `--prune`
flag on `dev/backfill_missing_images.py`, a standalone hand-run script
that is explicitly out of scope as a *subsystem* (issue 48 lists it
under "not cruft, explicitly out of scope"); its existing purpose,
boundary, and non-import-by-runtime-code convention are unchanged, only
its argument surface grows. Every other item is a docs, `justfile`,
`.gitignore`, or `config/` housekeeping edit with no runtime behavior at
all. This sprint follows the same precedent as sprint 035: no `design/`
overlay is seeded, because no subsystem's design changes.

### Architecture Overview

N/A — no components are added, removed, or rewired. See Solution above
for the three tickets' groupings.

### Design Rationale

**Decision: extend `dev/backfill_missing_images.py` rather than write a
throwaway prune command.**
Context: issue 48 flags that the script already computes the referenced
set for its check mode.
Alternatives considered: a one-off script or inline shell command to
delete orphaned files.
Why this choice: the referenced-set computation is the expensive/fiddly
part and already exists and is tested; a `--prune` mode is the
set-difference in the other direction and stays repeatable rather than
a one-time manual sweep, consistent with the file's own "future
integrity-check" framing.
Consequences: the script's argument surface grows by one flag; its
existing check-only default behavior is unchanged, so nothing about its
current CI-gate-readiness regresses.

**Decision: delete the `justfile`'s `pub` recipe outright rather than
neuter it.**
Context: `pub` pushes `master` (under a deliberate push freeze) and
dispatches `pages.yml` (disabled 2026-09-03).
Alternatives considered: comment it out; leave it but add a guard/prompt;
point it at a no-op.
Why this choice: issue 48 is explicit that `pub` "must not survive in
any form that pushes master or dispatches a Pages deploy" — a
commented-out or guarded version is still a landmine for a future
`just pub` invocation or a copy-paste. Outright removal is the only form
that satisfies the constraint unambiguously.
Consequences: publishing from this repo, if ever re-enabled, needs a new
recipe written fresh against whatever the publishing story is at that
time — acceptable, since this repo does not currently publish anything.

### Migration Concerns

None. All changes are additive (new script flag) or subtractive
(removing dead/dangerous recipes, stale comments, unreferenced files,
an unused `.gitkeep`) with no data migration, no backward-compatibility
surface, and no deployment sequencing — except the one explicit
verification gate on the four empty `config/` files, which must be
checked against `dotconfig`'s deploy-layout expectations before removal
(see Ticket 003) and may legitimately end in "kept, here's why" rather
than deletion.

## Use Cases

N/A — trivial. This is repository hygiene (dead code, stale docs, unused
config, ungitignored artifacts) with no new or changed user-facing or
system behavior. The one behavior change — `dev/backfill_missing_images.py`
gaining a `--prune` mode — is an additive capability on an already
out-of-scope hand-run maintenance script, not a new use case; its
correctness is covered directly by Ticket 001's acceptance criteria and
tests rather than a sprint-level use case.

## GitHub Issues

(None — tracked via local issue `48-repo-cleanup-stale-cruft.md`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [x] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Prune orphaned opportunity images via `backfill_missing_images.py --prune` | — |
| 002 | Retire the broken/dangerous `justfile` and rewrite README's publishing section | — |
| 003 | Tidy stale references, `.gitignore` gaps, and empty config files | — |

Tickets execute serially in the order listed. None of the three depend
on each other's output (each touches a disjoint set of files), but they
are sequenced to keep the diff reviewable one concern at a time, per
issue 48's own item ordering.

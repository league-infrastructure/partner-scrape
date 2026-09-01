---
id: '026'
title: Backfill Missing Opportunity Images from Stem-Ecosystem
status: done
branch: sprint/026-backfill-missing-opportunity-images-from-stem-ecosystem
use-cases: []
issues:
- backfill-missing-referenced-opportunity-images.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 026: Backfill Missing Opportunity Images from Stem-Ecosystem

## Goals

1. Backfill the 172 opportunity images that `data/partners/*/events.json`
   and `data/partners/*/past-events.json` reference but that are missing
   from `data/images/opportunities/`, copied by exact filename from the
   sibling `../stem-ecosystem/public/images/opportunities/` checkout.
2. Re-derive referential integrity after the copy and confirm zero
   missing images remain, across both the per-partner projection and
   `data/opportunities.json`.

## Problem

Sprint 025 redirected every partner-scrape write target to this repo's
own `data/` directory, including `data/images/opportunities/` (populated
by `EventImageDownloader`, which as of sprint 025 ticket 002 resizes
newly-downloaded images on fetch — see `partner_scrape/export/images.py`).
The first real production run under the new architecture populated
`data/images/opportunities/` with 375 images — a snapshot of that one
run's *current* opportunities, not an accumulated history.

`export/publish.py`'s `project()` writes a richer, per-partner contract
(`data/partners/<slug>/events.json` and `.../past-events.json`) that
reflects *every* opportunity ever seen for that partner, accumulated over
many historical runs via the persistent per-partner log under
`SCRAPE_CACHE_DIR` (`export/partner_log.py`) — not just the current run's
snapshot `data/images/opportunities/` was seeded from. This mismatch
between "one run's current images" and "the full accumulated history's
referenced images" is what produces the gap.

This gap was surfaced during the stem-ecosystem peer session's
cross-verification of sprint 025's output, not from a pre-existing filed
issue — captured as issue
`backfill-missing-referenced-opportunity-images.md`. Diffing every
`image_src` filename referenced across
`data/partners/*/{events,past-events}.json` against
`data/images/opportunities/`'s actual contents: 449 distinct filenames
referenced, 375 present, **172 missing**. This count was independently
confirmed three times — by the stem-ecosystem peer session, by
team-lead, and again by sprint-planner during this sprint's own planning
pass — all in agreement. All 172 missing filenames were also confirmed
to exist, unresized (pre-resize originals — sprint 025 ticket 002's
resize-on-fetch only applies to newly-downloaded images, not this
historical accumulation), at
`../stem-ecosystem/public/images/opportunities/` on this same machine.
As a control, `data/opportunities.json`'s own image references were
checked separately: 143 referenced, all 143 present — that contract
already has perfect referential integrity and is not part of this gap.

The stem-ecosystem side declined to write into partner-scrape's own
checkout themselves — correctly, matching the exact cross-repo-write
boundary sprint 025 just established (just pointed the other direction)
— and left it to partner-scrape to pull from their tree.

## Solution

**Team-lead has already decided this (communicated to the peer session,
settled, not open for this sprint to re-litigate):** seed ONLY the 172
currently-referenced-but-missing images into `data/images/opportunities/`,
copied by exact filename from
`../stem-ecosystem/public/images/opportunities/` — not all 631 images in
that directory. This keeps `data/` lean, matches the point of sprint
025's resize work (avoid re-accumulating unresized bloat), and the 172
are exactly what the current published contract actually needs — nothing
dead riding along. Exact-filename copy only: no resize/re-encode/
re-derive in this pass — the 172 images stay pre-resize originals until
they naturally age out of the published contract via a future re-fetch.
This is a one-time backfill; going forward `data/`'s own accumulated
history stays complete on its own (each real run's image download only
ever adds, content-hash deduped, never overwrites, and the directory
persists across runs, git-committed).

**Where this logic lives.** This repo already has an established
convention for exactly this shape of work: `dev/refresh_school_directories.py`
is a standalone, hand-run, output-committed provisioning script — never
imported by runtime code, run manually, reviewed by diff. This sprint
adds one sibling script, `dev/backfill_missing_images.py`, rather than
inventing a new `scripts/` convention (none exists in this repo) or
burying the logic as an unrecorded ad hoc shell one-liner in a ticket's
Notes. The situation this script addresses — a snapshot-vs-accumulated-
history image gap, or simply wanting to re-verify referential integrity
— is plausible to recur (a future re-seed after another architecture
change, or a routine integrity check), so a small, reusable, parametrized
script is worth keeping over a throwaway command. Matching
`dev/refresh_school_directories.py`'s own convention exactly, the new
script stays fully standalone (stdlib only, no import of
`partner_scrape.*`) — it is provisioning tooling, not pipeline code, and
is never imported by anything under `partner_scrape/`.

The script supports two modes: a check-only mode (no `--source-dir`
given) that just re-derives referenced-vs-present and reports any gap —
this is the reusable "verify referential integrity" half of the ask —
and a backfill mode (`--source-dir` given) that additionally copies each
missing-but-source-available file by exact filename, byte-for-byte, no
transformation. Both modes scan `data/partners/*/events.json` +
`data/partners/*/past-events.json` for referenced `image_src` filenames,
and separately check `data/opportunities.json`'s own `image_src`
references as a control (confirming the existing 143/143 stays clean).

## Success Criteria

- `data/images/opportunities/` contains all 172 previously-missing
  filenames, byte-identical to their source copies in
  `../stem-ecosystem/public/images/opportunities/`.
- Re-deriving referenced-image filenames from every
  `data/partners/*/events.json` and `data/partners/*/past-events.json`
  after the copy shows **zero** missing.
- `data/opportunities.json`'s own referenced-image check still shows
  143/143 present (unchanged, confirms the copy didn't disturb this
  already-passing contract).
- `git status` under `data/images/opportunities/` shows only new file
  additions (exactly 172 new files) — no existing file modified or
  removed.
- No other file under `data/` or `partner_scrape/` is touched by this
  sprint.
- `uv run pytest -q` stays green (this sprint adds no pipeline code, so
  no regression is expected, but the suite is run to confirm).

## Scope

### In Scope

- New standalone script `dev/backfill_missing_images.py`: derives
  referenced-image filenames from `data/partners/*/{events,past-events}.json`
  and `data/opportunities.json`, diffs against `data/images/opportunities/`,
  and (when a source directory is given) copies missing-but-available
  files across by exact filename.
- One live, real (non-dry-run) execution of that script against
  `../stem-ecosystem/public/images/opportunities/` as the source,
  backfilling the 172 files.
- Live re-verification pass (the script's check-only mode) after the
  copy, with before/after counts recorded in the ticket's Notes.
- The 172 new files being git-added under `data/images/opportunities/`
  (committed the same way this directory's contents already are,
  per sprint 025's convention — actual commit is the ticket executor's
  normal end-of-ticket commit, not a separate step).

### Out of Scope

- Copying any of the other 459 images in
  `../stem-ecosystem/public/images/opportunities/` (631 total minus the
  172 being backfilled) — whether unreferenced entirely, or referenced
  but already present in `data/images/opportunities/` from the sprint-025
  production run — team-lead's explicit decision (see Solution).
- Resizing, re-encoding, or otherwise transforming any of the 172
  backfilled images — they stay pre-resize originals; re-encoding them
  is explicitly deferred to whenever they next get re-fetched by a real
  run (out of this sprint's authority to decide when that happens).
- Any change to `partner_scrape/export/images.py`, `export/publish.py`,
  `pipeline.py`, or any other pipeline module — this is pure data
  repair using a standalone provisioning script, not a pipeline code
  change. No runtime import graph is touched.
- Any change to how `data/images/opportunities/` is populated going
  forward — sprint 025's existing content-hash-dedup, additive-only
  behavior already keeps this directory's history complete on its own;
  this sprint fixes the one historical gap left by the sprint-025
  cutover, it does not change the ongoing mechanism.
- Any stem-ecosystem-side change — the peer session already declined to
  write into partner-scrape's checkout, matching the sprint-025
  boundary; this sprint is the partner-scrape-side pull that boundary
  implies. Nothing in `../stem-ecosystem` is modified.

## Test Strategy

No dedicated hermetic pytest suite for `dev/backfill_missing_images.py`,
matching this repo's own established convention for standalone `dev/`
provisioning scripts: `dev/refresh_school_directories.py` — a
comparably-sized script with real parsing/filtering logic — has no
dedicated test module either; it is run by hand and its output reviewed
directly (see its own docstring: "Re-run it, diff the four files it
writes, and review the diff like any other code change before
committing"). This sprint follows the same pattern: the script is
exercised live against the real `data/` tree and the real sibling
`../stem-ecosystem` checkout, and its own check-only mode *is* the
verification step — re-deriving the full referenced-image set from the
real, current `data/partners/*` files and confirming zero missing is a
stronger, more direct correctness proof for a data-repair operation than
a fixture asserting the internal copy logic behaves as written on
synthetic inputs. The core logic itself (scan JSON for a field, set-
difference against directory contents, copy by exact filename) is
straight-line I/O with no branching complex enough to be worth a
separate hermetic harness, unlike sprint 025 ticket 002's resize step
(aspect-preserving thumbnailing, format-dependent re-encode, alpha-
channel detection), which had genuine algorithmic behavior justifying
fixture-based tests.

**Required live verification** (this repo's established convention,
matching sprint 025 ticket 008's live-verify pattern): the ticket's own
acceptance criteria require running the script for real against the real
`data/` tree and the real sibling checkout, and recording the exact
before/after counts (referenced/present/missing, before and after) in
the ticket's Notes — not a simulated or fixture-backed run.

## Architecture

**Trivial** — a one-time data-repair backfill implemented as a single
standalone `dev/` provisioning script (matching the existing
`dev/refresh_school_directories.py` convention), never imported by
runtime code. No `partner_scrape/` module is touched, no pipeline
dependency graph changes, no data model changes (the 172 files are
copied byte-for-byte, unresized, into an existing directory whose shape
is unchanged). `dev/` is explicitly outside this repo's subsystem map
(`docs/design/design.md` §2: "Not a dependency of the package; logic
was ported, not imported") — adding one more script matching an already-
established pattern in that directory is not a new architectural
component in the sense the effort-decision tiers are gauging, so this
does not rise to the "compact" tier's "one new or changed module."

### Architecture Overview

N/A — trivial (see above; no component, dependency, or data-model
changes to diagram).

### Design Rationale

N/A — trivial. The two real decisions this sprint makes (script vs.
one-off command; live-verified vs. hermetic-tested) are recorded in
`sprint.md`'s Solution and Test Strategy sections above, not here — they
are scoping/tooling-convention decisions, not architectural ones (no
module boundary, dependency direction, or data model is at stake).

### Migration Concerns

None. This sprint adds files to `data/images/opportunities/` only —
existing files in that directory are never modified or removed, and no
other data file's shape changes. The 172 backfilled images remain
pre-resize originals (see Out of Scope); they naturally get replaced
with a resized copy only if and when a future real run re-fetches the
same source URL, which is the same self-healing behavior sprint 025
already established for every other image in this directory — no
special-cased migration path is needed for these 172.

## Use Cases

N/A — trivial. This is a one-time operational data-repair task performed
via a standalone script, not a new or changed product-facing use case —
no actor-facing flow, precondition, or acceptance criterion changes as a
result of this sprint. The single ticket's own acceptance criteria (see
`tickets/001-*.md`) carry the concrete, checkable outcomes instead.

## GitHub Issues

(None filed — this sprint originates from a same-session cross-repo
peer-verification finding, captured as one local CLASI issue; see this
sprint's `issues:` frontmatter.)

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
| 001 | Backfill missing referenced opportunity images from stem-ecosystem | — |

Tickets execute serially in the order listed (a single ticket here).

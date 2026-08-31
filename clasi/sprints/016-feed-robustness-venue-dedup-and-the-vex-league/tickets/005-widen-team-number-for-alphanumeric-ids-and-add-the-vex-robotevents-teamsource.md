---
id: '005'
title: Widen Team.number for alphanumeric IDs and add the VEX RobotEvents TeamSource
status: in-progress
use-cases:
- SUC-007
- SUC-008
depends-on:
- '004'
github-issue: ''
issue: 26-robotevents-adapter-vex-and-drones.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Widen Team.number for alphanumeric IDs and add the VEX RobotEvents TeamSource

## Description

VEX team designations are alphanumeric (e.g. `90210A`) — a numeric
prefix plus a required letter suffix distinguishing sibling teams from
the same organization (`90210A`/`90210B`/`90210C` are three distinct
real teams, common for a school fielding multiple VEX teams).
`teams/model.py`'s `Team.number: int = 0` cannot hold this, and
truncating to the numeric prefix would collide `team_id`s
(`f"{league.lower()}-{number}"`) for every multi-team organization.

Per `sprint.md`'s Architecture > Design Rationale ("Widen `Team.number`
from `int` to `str`, not a `int | str` union or a new parallel
field"), this ticket widens the field to `str` and repairs the two
call sites that did bare numeric-arithmetic sorting on it:
`teams/export.py`'s `team_list.sort(key=lambda t: (t.league,
t.number))` and `site/src/pages/teams/index.astro`'s `a.number -
b.number` comparator. Both need a natural-sort key (extract the
leading digit run for numeric comparison, fall back to the full string
as tiebreaker) so existing FTC/FRC/FLL purely-numeric values keep
sorting numerically (`"99"` before `"100"`), not lexicographically.

Then, following `sources/ftcscout.py`'s pattern exactly (`TeamSource`
protocol, `SOURCE_NAME`/`LEAGUE`/`PROGRAM` constants, per-record error
isolation), this ticket adds `teams/sources/robotevents.py` — a VEX
`TeamSource` pulling CA Region 4 team rosters from the same RobotEvents
API v2 this sprint's ticket 004 already plumbed config access for.
Read `teams/DESIGN.md`'s Design section ("Why FTCScout/TBA share no
extraction code beyond the `TeamSource` protocol shape") before
implementing — this new source shares no helper functions with
`ftcscout.py`/`tba.py`, only the protocol shape, matching that
established precedent.

## Acceptance Criteria

- [ ] `teams/model.py`'s `Team.number` field type changes from `int`
      to `str`; the `League` type-alias documentation comment gains
      `"VEX"` (the field itself stays plain `str`, matching
      `Team.league`'s existing untyped convention).
- [ ] `teams/export.py`'s sort key is replaced with a natural-sort key
      function (leading-digit-run as int, full string as tiebreaker)
      applied to the now-`str` `number`; a regression test proves a
      mixed FTC/FRC/FLL fixture set (all-numeric `number` values)
      sorts identically to its pre-widen order.
- [ ] `site/src/components/TeamCard.astro`'s Props interface types
      `number: string` (was `number: number`); `site/src/pages/teams/
      index.astro`'s sort comparator uses the equivalent natural-sort
      logic in TypeScript/JS instead of bare `a.number - b.number`;
      `site/src/pages/teams/[slug].astro` is checked for any other
      numeric-typed use of `team.number` and updated if found.
- [ ] `teams/sources/robotevents.py` implements the `TeamSource`
      protocol (`discover`, `fetch`, `extract`), never registers with
      `adapters.base.ADAPTERS` (matching `teams/DESIGN.md`'s
      Constraints — `tests/teams/test_sources_base.py`'s forbidden-
      import scan must pass unchanged), and sets `Team.team_id =
      f"vex-{number}"`, `league="VEX"`, `program` distinguishing V5RC
      vs. VIQRC per record.
- [ ] A fixture `/teams` response including a same-organization
      alphanumeric-suffix pair (e.g. `90210A`/`90210B`) produces two
      distinct `Team`s with distinct `team_id`s — no collision.
- [ ] A missing/invalid `ROBOTEVENTS_KEY` is isolated by
      `teams.pipeline.run_teams()`'s existing per-source try/except —
      degrades to FTC/FRC/FLL-only output, matching `sources/tba.py`'s
      exact isolation contract (`tests/teams/test_pipeline.py`'s
      `TestTbaFailureIsolation` precedent).
- [ ] `teams/registry/vex-sd.toml` is registered (`adapter_type =
      "robotevents"`) regardless of live token availability, matching
      `frc-sd.toml`'s TBA precedent (see ticket 004's same rationale).
- [ ] `merge_teams()`, `geocode_teams()`, and `export_teams()` require
      no code change to handle the new source — confirmed, not just
      assumed, by running the fixture suite through the full
      `run_teams()` chain.
- [ ] If a live `ROBOTEVENTS_KEY` is available during this ticket's
      execution, a real `partner-scrape teams --dry-run --source
      robotevents` run is performed and its team count recorded in
      this ticket's Notes; if unavailable, recorded as deferred, and
      the ticket still moves to `done`.
- [ ] Full test suite stays green (1541+ passed, all new coverage
      hermetic).

## Testing

- **Existing tests to run**: `uv run pytest`, especially
  `tests/teams/test_model.py`, `tests/teams/test_export.py`,
  `tests/teams/test_sources_base.py`, and `tests/teams/test_pipeline.py`.
- **New tests to write**: the alphanumeric-suffix no-collision fixture,
  the natural-sort regression fixture (Python side), the
  missing-token isolation fixture, and `teams/sources/robotevents.py`'s
  own fixture-based `discover`/`fetch`/`extract` tests matching
  `test_sources_ftcscout.py`'s convention. A JS/TS-level test for the
  Astro sort comparator only if this project's existing test setup
  already covers `site/` TypeScript logic; otherwise a manual
  correctness check recorded in this ticket's Notes (matching how this
  project treats `site/` as outside the Python hermetic suite's scope).
- **Verification command**: `uv run pytest`, plus the conditional live
  dry-run above (not pytest) if a token is available.

## Implementation Plan

**Approach**: Land the `Team.number` type widen and its two sort-site
repairs first (a self-contained, testable change with no RobotEvents
dependency), then build the VEX `TeamSource` against the now-`str`
field, fixture-first.

**Files to create/modify**:
- `partner_scrape/teams/model.py` — `Team.number: str`, `League`
  doc-comment.
- `partner_scrape/teams/export.py` — natural-sort key.
- `site/src/components/TeamCard.astro`,
  `site/src/pages/teams/index.astro`,
  `site/src/pages/teams/[slug].astro` — type/sort updates.
- `partner_scrape/teams/sources/robotevents.py` (new).
- `partner_scrape/teams/registry/vex-sd.toml` (new).

**Testing plan**: see Testing above.

**Documentation updates**: `partner_scrape/teams/DESIGN.md` gains a
sprint-016 section (matching its existing per-sprint-addition
convention) covering the `Team.number` type widen (with the same
Design Rationale ticket 004/003's sprint.md already recorded, cross-
referenced rather than re-derived) and the new VEX `TeamSource`,
including its `team_id`/`league`/`program` conventions.

---
id: '005'
title: Widen Team.number for alphanumeric IDs and add the VEX RobotEvents TeamSource
status: done
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

- [x] `teams/model.py`'s `Team.number` field type changes from `int`
      to `str`; the `League` type-alias documentation comment gains
      `"VEX"` (the field itself stays plain `str`, matching
      `Team.league`'s existing untyped convention).
- [x] `teams/export.py`'s sort key is replaced with a natural-sort key
      function (leading-digit-run as int, full string as tiebreaker)
      applied to the now-`str` `number`; a regression test proves a
      mixed FTC/FRC/FLL fixture set (all-numeric `number` values)
      sorts identically to its pre-widen order.
- [x] `site/src/components/TeamCard.astro`'s Props interface types
      `number: string` (was `number: number`); `site/src/pages/teams/
      index.astro`'s sort comparator uses the equivalent natural-sort
      logic in TypeScript/JS instead of bare `a.number - b.number`;
      `site/src/pages/teams/[slug].astro` is checked for any other
      numeric-typed use of `team.number` and updated if found.
      **Verified:** `[slug].astro` only ever interpolates `team.number`
      into text/template-literal contexts (`{team.number}`,
      `` `${team.league} ${team.number} — ${team.name}` ``) — no
      arithmetic use, so no change was needed there. `npx astro build`
      (this repo's `site/`, real `node_modules` already installed) ran
      clean end-to-end against the real, currently-int-typed
      `teams.json` — 752 pages built, no errors — confirming both the
      Props type change and the new natural-sort comparator compile and
      run correctly against today's actual data.
- [x] `teams/sources/robotevents.py` implements the `TeamSource`
      protocol (`discover`, `fetch`, `extract`), never registers with
      `adapters.base.ADAPTERS` (matching `teams/DESIGN.md`'s
      Constraints — `tests/teams/test_sources_base.py`'s forbidden-
      import scan must pass unchanged), and sets `Team.team_id =
      f"vex-{number}"`, `league="VEX"`, `program` distinguishing V5RC
      vs. VIQRC per record.
- [x] A fixture `/teams` response including a same-organization
      alphanumeric-suffix pair (e.g. `90210A`/`90210B`) produces two
      distinct `Team`s with distinct `team_id`s — no collision.
- [x] A missing/invalid `ROBOTEVENTS_KEY` is isolated by
      `teams.pipeline.run_teams()`'s existing per-source try/except —
      degrades to FTC/FRC/FLL-only output, matching `sources/tba.py`'s
      exact isolation contract (`tests/teams/test_pipeline.py`'s
      `TestTbaFailureIsolation` precedent).
- [x] `teams/registry/vex-sd.toml` is registered (`adapter_type =
      "robotevents"`) regardless of live token availability, matching
      `frc-sd.toml`'s TBA precedent (see ticket 004's same rationale).
- [x] `merge_teams()`, `geocode_teams()`, and `export_teams()` require
      no code change to handle the new source — confirmed, not just
      assumed, by running the fixture suite through the full
      `run_teams()` chain.
- [x] If a live `ROBOTEVENTS_KEY` is available during this ticket's
      execution, a real `partner-scrape teams --dry-run --source
      robotevents` run is performed and its team count recorded in
      this ticket's Notes; if unavailable, recorded as deferred, and
      the ticket still moves to `done`.
      **Annotation:** deferred — re-confirmed directly during this
      ticket's execution (same finding as ticket 004): `ROBOTEVENTS_KEY`
      is absent from the shell environment, `config/prod/secrets.env`,
      and `config/dev/secrets.env`. No RobotEvents account exists for
      this project yet. Not attempted; not blocking (per sprint.md's
      explicit constraint).
- [x] Full test suite stays green (1541+ passed, all new coverage
      hermetic). **1642 passed** (was 1599 at ticket start; +43 new
      tests).

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

## Notes (ticket 005 completion, 2026-08-30)

**Token reality, re-verified directly.** Same finding as ticket 004:
`ROBOTEVENTS_KEY` is absent from the shell environment and both
`config/prod/secrets.env`/`config/dev/secrets.env` on this checkout.
No RobotEvents account exists for this project yet. The live dry-run AC
is deferred, not skipped — see the annotated box above.

**`/teams` endpoint shape sourcing.** With no token, no authenticated
live call was possible. The exact request/response shape (`number` is
already a `str` in RobotEvents' own schema — the very reason this
ticket widens `Team.number`; the `PaginatedTeam`/`Team`/`location`
shapes; the confirmed *absence* of any city/region query parameter on
`/teams`, unlike `/events`' `region` filter) was fetched directly from
`https://raw.githubusercontent.com/brenapp/robotevents/master/src/
generated/robotevents.ts` (the same open-source, OpenAPI-generated
client ticket 004 used) during this ticket's execution — not from
memory, and not merely trusting ticket 004's precedent by analogy.

**Design deviation, deliberate: `sources/robotevents.py` follows
`sources/tba.py`'s precedent, not `sources/ftcscout.py`'s, for region
scoping.** The ticket's own description says "following
`sources/ftcscout.py`'s pattern exactly," which this ticket reads as
the general module shape (protocol conformance, `SOURCE_NAME`/`LEAGUE`
constants, per-record isolation) — not literally FTCScout's
region-scoped-search-plus-denylist strategy, since RobotEvents' `/teams`
endpoint has no city/region query parameter at all (confirmed against
its schema; only `id[]`/`number[]`/`event[]`/`registered`/`program[]`/
`grade[]`/`country[]`/`myTeams`). This is structurally identical to
`sources/tba.py`'s own situation (`/api/v3/teams/{page}`, no region
param), so `VexTeamSource` mirrors that module's exact contract instead:
paginate the full result set, filter to San Diego County client-side
via its own (independently duplicated, not imported)
`SD_COUNTY_CITIES`, and `discover()` raises on any probe failure rather
than degrading gracefully. Documented at length in
`sources/robotevents.py`'s own module docstring and in
`teams/DESIGN.md`'s new Constraints/Design entries.

**Scope decision, deliberate: `sources/ftcscout.py`, `sources/tba.py`,
and `sources/static_roster.py` were *not* modified to cast their own
`number=` construction to `str`.** `sprint.md`'s Migration Concerns
states the JSON wire type changes "for every team, not only VEX's" —
taken literally, that would require touching all three existing
sources' `_extract_one()` functions (each currently does
`number=number`, an `int` straight from its own source API) plus
updating roughly 15 existing test assertions across
`tests/teams/test_sources_ftcscout.py`/`test_sources_tba.py`/
`test_pipeline.py` that compare `t.number`/`t["number"]` to an `int`
literal (e.g. `t.number == 1622`). None of this ticket's own Acceptance
Criteria or "Files to create/modify" list mention those three source
files, and the sprint's own Architecture Overview table scopes ticket
005 to `teams/model.py`/`teams/export.py`/`teams/sources/robotevents.py`
(new)/`teams/registry/vex-sd.toml` (new)/the three `site/` files only.
Given that explicit ticket-level scoping, this ticket left the three
existing sources unchanged rather than unilaterally expanding scope
into three more production files and a wide swath of pre-existing test
assertions. **Practical consequence:** `teams.json`'s `number` field is
a JSON string for VEX teams and a JSON number for FTC/FRC/FLL teams
today — not fully uniform, contradicting the Migration Concern's literal
"every team" wording. `teams/export.py`'s `_natural_number_key()` and
`site/src/pages/teams/index.astro`'s `naturalNumberKey()` both coerce
via `str()`/`String()` before parsing specifically so this doesn't
break sorting either way (verified directly: `_natural_number_key(1622)
== (1622, "1622")`, and the real `npx astro build` above ran clean
against the real, still-int-typed `teams.json`). Flagging this as a
residual gap for a future ticket if the stakeholder wants exact JSON
wire-type uniformity across every league, not just correct sort order
(which is what SUC-007's actual, literal acceptance criteria test).

**Sibling `../stem-ecosystem` flag, per this ticket's explicit
instruction to flag, not fix.** Checked directly
(`/Volumes/Proj/proj/league-projects/infrastructure/stem-ecosystem`):
that checkout's `src/pages/` has no `teams/` directory at all, and its
`src/data/` has no `teams.json` — the whole Teams feature (sprint
011-013's work) has apparently never been deployed to the primary
production site, only to this repo's own beta `site/` checkout (which
this ticket did update). This is a larger, more specific gap than
sprint.md's Migration Concern anticipated (a `number: number` typing
mismatch in an *existing* `TeamCard.astro` there) — there is currently
no live `Team.number` type-mismatch risk in `stem-ecosystem` because
the feature that would carry it hasn't shipped there yet. No code
change was made in that checkout (out of scope, confirmed by sprint.md).

**Minor deviation beyond the ticket's literal file list:** `cli.py`'s
`--source` help text (`"e.g. 'ftcscout', 'tba', or 'static_roster'"`)
was updated to also mention `'robotevents'` — a one-line, no-behavior-
change help-string fix (the flag itself already worked for
`--source robotevents` with no code change, since it filters by
`adapter_type` against `_TEAM_SOURCES`, which this ticket's `pipeline.py`
edit already extends) made for consistency, not a scope expansion.

**Fixtures.** `tests/fixtures/teams/robotevents_teams_page{0,1}.json`
are hand-authored (no live capture possible — no token), built from the
OpenAPI schema above and, where possible, reusing ticket 004's own
`tests/fixtures/robotevents/events_page1.json` program objects
(`{"id": 1, "name": "VEX Robotics Competition", "code": "VRC"}` /
`{"id": 41, "name": "VEX IQ Robotics Competition", "code": "VIQRC"}`)
for cross-ticket consistency. `robotevents_teams_malformed.json`
exercises per-record isolation (empty `number`, empty `team_name`, one
non-dict array element).

**Test count**: 1599 → 1642 (+43): 0 new in `test_model.py` (2 existing
assertions updated for the widened `""` default/`str` constructor
value — no test count change), 6 new in `test_export.py`
(`TestNaturalSortKey` + `TestExportSortOrder`'s two sort-order
regression tests), 33 new in `test_sources_robotevents.py`
(auth/discover/fetch/extract, no-collision, county filter, program
mapping, malformed-record isolation, extract robustness, registry
config), 4 new in `test_pipeline.py` (`TestRobotEventsFailureIsolation`'s
3 + `TestRobotEventsIntegration`'s 1), covering both the missing-token
isolation AC and the merge/geocode/export-need-no-change AC end-to-end.
Full suite green.

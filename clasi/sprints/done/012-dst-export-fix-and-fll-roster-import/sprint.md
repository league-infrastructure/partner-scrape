---
id: '012'
title: DST export fix and FLL roster import
status: done
branch: sprint/012-dst-export-fix-and-fll-roster-import
use-cases: []
issues: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 012: DST export fix and FLL roster import

## Goals

Two small-to-moderate corrective/completion items left over from the
009-011 arc, bundled because both are independent, self-contained, and
neither should block the other:

1. **Fix the hard-coded `-07:00` export timezone offset** (issue 19).
   `partner_scrape/normalize/run.py`'s `_iso()` appends a constant
   Pacific-Daylight offset to every naive datetime, which is wrong for
   roughly four months a year (early November - mid-March, Pacific
   Standard Time is `-08:00`). Replace the constant with a real
   `zoneinfo.ZoneInfo("America/Los_Angeles")` resolution per datetime, so
   the correct offset falls out of the calendar date itself.
2. **Import the 48 FLL teams as a static roster** (issue 20). Sprint 011
   shipped `/teams` with 230 live, refreshable FTC/FRC teams and
   deliberately deferred the third league, First LEGO League, because
   there is no public FLL API or third-party aggregator — the only
   source is a hand-maintained, dated export
   (`../robot-team-analysis/fll/sd-fll-teams-contact-list.md`) that
   carries contact information this project must never publish. Add a
   `static_roster` `TeamSource` that reads a committed, contact-stripped
   roster file, marks its records' provenance as static, and warns
   loudly once the season it describes (`2026-27`, FLL's last-ever
   season) has passed.

Both are corrective/completion work, not new capability: 19 fixes a
latent correctness bug in a path shipped in an earlier sprint; 20
completes the teams directory sprint 011 explicitly deferred. Neither
depends on the other's code, registry entries, or data files — they
are sequenced together here purely for scheduling convenience, and
either can slip without blocking the other or being blocked by it.

## Problem

**Issue 19.** `_TZ_OFFSET = "-07:00"` in `normalize/run.py` is Pacific
Daylight Time, applied unconditionally to every naive datetime the
pipeline produces (no adapter sets `tzinfo`, so every event's
`date_start`/`date_end` goes through this path). From early November to
mid-March, San Diego is on Pacific Standard Time (`-08:00`), so every
event exported during that window carries an offset one hour off from
true local time — a stamped-wrong data-correctness bug shipped since the
constant was written, in a month when it happened to be correct, and
explicitly deferred out of sprint 009 as orthogonal to that sprint's
scope.

**Issue 20.** Sprint 011 shipped FTC (FTCScout, live) and FRC (The Blue
Alliance, live) but has no FLL coverage — the third of San Diego's three
FIRST robotics leagues, 48 teams, is entirely absent from `/teams`. There
is no live source to pull from (probed and confirmed: no FLL API, no
third-party aggregator), so the only path is a one-time, dated import of
a hand-maintained roster that also carries data this project has an
explicit structural policy against ever publishing (`model.Team` has no
`email` field by design).

## Solution

**Issue 19.** Resolve each naive datetime's UTC offset from a real
`zoneinfo.ZoneInfo("America/Los_Angeles")` instance instead of a
constant string, so `-07:00`/`-08:00` falls out of whichever side of the
DST boundary the date lands on. Adopt an explicit, documented convention
for the DST transition's two edge cases (the repeated 1am-2am hour in
November, the skipped hour in March) using the stdlib `fold` mechanism
rather than leaving the behavior implicit. Leave every other aspect of
`_iso()` and the "naive San Diego wall clock" convention (`normalize/
DESIGN.md`) unchanged — an aware datetime's own offset is still left
untouched, matching current behavior.

**Issue 20.** Add `partner_scrape/teams/sources/static_roster.py`, a
`TeamSource` implementation that reads a committed, contact-stripped
roster (derived from the upstream hand-maintained export, with contact
fields dropped at import time rather than carried into the module and
filtered later) and never calls the injected `Fetcher`. Register it in
`teams.pipeline._TEAM_SOURCES` under a new `teams/registry/fll-sd.toml`
entry carrying `sunset_season = "2026-27"`; `run_teams()` logs a loud
WARNING once the current date passes that season. FLL records feed
through the existing `merge_teams()`/`geocode_teams()` stages unchanged
— family/home teams map to `organization=""` (the same
`Family/Community` sentinel pattern FTCScout already uses) so they never
falsely group, and city-only location data resolves through the existing
offline ladder at city precision at best (rung 7's "never guess" rule
applies unchanged).

## Success Criteria

- A July-dated event exports with `-07:00`; a January-dated event
  exports with `-08:00`; both DST-transition edge cases have documented,
  tested behavior; `is_current_or_upcoming` still partitions correctly
  across the boundary.
- `/teams` carries all 278 teams (230 existing + 48 FLL) after a real
  `partner-scrape teams` run against the live registry — not just the
  fixture-based test suite — with zero email addresses anywhere in
  `teams.json` and a `sunset_season` warning that fires once verified
  past `2026-27` (simulated in tests).
- Full existing test suite (~1190 tests) stays green; no existing test
  needs to change for either fix.

## Scope

### In Scope

- `partner_scrape/normalize/run.py`: replace `_TZ_OFFSET` with
  `zoneinfo`-based per-datetime offset resolution in `_iso()`; document
  the fold convention for the two DST-transition edge cases.
- `partner_scrape/teams/sources/static_roster.py`: new `TeamSource`.
- A committed, contact-stripped FLL roster data file under
  `partner_scrape/teams/data/` (derived from the sibling repo's
  hand-maintained export; contact fields stripped at import, never
  carried into the module).
- `partner_scrape/teams/registry/fll-sd.toml`: new Team Registry entry,
  `adapter_type = "static_roster"`, carrying `sunset_season = "2026-27"`.
- `partner_scrape/teams/pipeline.py`: one new `_TEAM_SOURCES` entry; a
  sunset-season staleness warning in `run_teams()`.
- Tests for both fixes, per Test Strategy below.
- `design/` overlay updates to `docs/design/design.md` (resolve the
  "DST is unhandled" open question) and the co-located
  `partner_scrape/normalize/DESIGN.md` / `partner_scrape/teams/DESIGN.md`
  subsystem docs.

### Out of Scope

- Any change to `export/writer.py`'s code. Confirmed by inspection:
  `is_current_or_upcoming` and every other date-based filter in
  `export/` compares only the date portion (`date_str[:10]`) of the ISO
  string, never the offset suffix, so the DST fix changes no `export/`
  behavior — only its output's correctness. `export/` is verified by a
  new regression test, not modified.
- Building support for whatever program succeeds FLL. LEGO declined to
  renew its FIRST partnership (2026-03-19), making 2026-27 FLL's last
  season, but the successor program has no name, hardware, or vendor yet
  — nothing to build against. This sprint imports the FLL roster as-is
  and adds the loud sunset warning; adapting to a successor program is a
  future sprint's concern once one exists.
- Joining `teams.json` to the curated partner directory, or any other
  cross-cutting teams-subsystem change beyond adding the third source —
  unchanged from sprint 011's own Out of Scope, still not this sprint's
  decision to make.
- A general historical/legacy-data-import mechanism. This sprint imports
  exactly one static roster (FLL); it does not build a reusable
  "static source" framework beyond what `TeamSource`'s existing protocol
  shape already provides.

## Test Strategy

Both changes are fixture-based and hermetic, matching the project's
existing convention — with one explicit exception carried forward from a
sprint 011 defect (see below).

- **Issue 19 — unit tests** in `tests/normalize/test_run.py` (or
  equivalent): a July-dated naive datetime serializes with `-07:00`; a
  January-dated one serializes with `-08:00`; the documented fold
  convention is exercised for both DST-transition edge cases (the
  repeated November hour, the skipped March hour); an already-aware
  datetime's own offset is left untouched (regression, existing
  behavior). A new test in `tests/export/test_writer.py` confirms
  `is_current_or_upcoming` still partitions correctly for a record dated
  right at a DST boundary — this is verification of already-correct
  behavior (Scope), not a code change.
- **Issue 20 — unit tests**: `tests/teams/test_sources_static_roster.py`
  asserts the source never calls the injected `Fetcher` (a double that
  raises on any call, matching `test_sources_base.py`'s forbidden-import
  scan precedent structurally, though this is a runtime-call assertion
  rather than an AST scan); a fixture-based extraction test covering a
  school-affiliated record, a family/home record (`organization=""`,
  never grouped), and the contact-field-stripping guarantee (no email
  survives into a `Team`, even if the source roster row happens to carry
  one). A test asserts `run_teams()` logs the sunset warning once
  simulated "today" passes `2026-27` and stays silent before it. The
  existing `tests/teams/test_export.py` no-email-pattern regression test
  is re-run against a `teams.json` that includes FLL records (extending,
  not replacing, its existing fixture set) to confirm the structural
  no-`email`-field guarantee holds with the third source present.
- **The sprint 011 lesson, applied directly.** Ticket 011-003 originally
  filtered TBA records against a hand-authored fixture using `"CA"`,
  which passed every test while the real API returned `"California"` for
  the majority of matching records — the fixture didn't match reality,
  and the defect shipped past a green test suite. This sprint adds one
  new external-data source (the FLL roster); its fixture must be a
  direct excerpt of the real committed roster file's actual rows, not a
  hand-authored approximation of what its shape is expected to be.
  Before this sprint closes, run `partner-scrape teams --dry-run -v`
  against the real (non-fixture) registry and confirm the reported
  totals are 278 teams overall (152 FTC + 78 FRC + 48 FLL) and that
  `meta.by_league["FLL"] == 48` — matching Success Criteria above. This
  is a stated pre-close verification step, not merely a test to write.
- **Regression**: `uv run pytest` — full existing suite (~1190 tests)
  stays green. Neither change touches an existing module's public
  interface, so no existing test should need modification.

## Architecture

**Compact** — this sprint bundles two independent, unrelated changes,
each confined to exactly one module: `partner_scrape/normalize/run.py`'s
`_iso()` (issue 19, a corrected offset calculation, not a new component)
and a new `partner_scrape/teams/sources/static_roster.py` module (issue
20, one new `TeamSource` implementation reusing every other stage of the
existing `teams/` pipeline unchanged). Neither introduces a new
cross-module dependency (issue 19 touches nothing outside `normalize/`;
issue 20 only adds one more entry to `teams.pipeline._TEAM_SOURCES`, the
same extension point `sources/tba.py` used in sprint 011), neither
changes dependency direction, and neither changes the data model
(`Opportunity`'s fields are unchanged — only `_iso()`'s computed string
value is more correct; `Team`'s `League` literal already includes
`"FLL"` from sprint 011, and provenance is carried by the existing
`Team.sources` list rather than a new field — see Design Rationale
below). Combined module count is 2, below the 3+ signal that would make
this substantial, and no other substantial trigger (new external
integration, dependency-direction change) applies to either change — a
static roster file is not a live integration. Each change is written up
in compact style (no diagrams — a one-module change has nothing a
diagram would clarify beyond the purpose statement below) as its own
overlay document rather than combined into one narrative, since they are
unrelated.

This project has opted into the persistent per-subsystem design-doc set
(`design_docs` enabled), so per `architecture-authoring`'s Mode 2a, the
full write-up for both changes lives in this sprint's `design/` overlay,
not in this section:

- `design.md` (system doc) — resolves Sec. 6's "DST is unhandled" open
  question.
- `normalize-DESIGN.md` (`partner_scrape/normalize/DESIGN.md`) — documents
  the `zoneinfo`-based offset resolution replacing `_TZ_OFFSET`, the fold
  convention for the two DST-transition edge cases, and updates the
  matching Open Questions/Known Limitations entry.
- `teams-DESIGN.md` (`partner_scrape/teams/DESIGN.md`) — documents the
  new `static_roster` source, its sunset-warning mechanism, and updates
  the doc's own status line (increments 1-4 complete, increment 5
  deferred → all five increments complete).

This section is the pointer and summary; the overlay is the source of
truth tickets are derived from.

**What changed, in one paragraph, per issue:**

*Issue 19.* `_iso()` resolves each naive datetime's UTC offset from
`zoneinfo.ZoneInfo("America/Los_Angeles")` at serialization time instead
of appending the constant `-07:00` unconditionally — the offset now
falls out of which side of the DST boundary the date lands on, correct
for the roughly four months a year (Standard Time) the old constant was
wrong. An aware datetime's own offset is still left untouched, matching
current behavior exactly. See the overlay's `normalize-DESIGN.md` for
the fold-convention decision on the two DST-transition edge cases.

*Issue 20.* A new `static_roster.py` `TeamSource` reads a committed,
contact-stripped roster file and never calls the injected `Fetcher`
(`discover()` returns a single local-file `TeamRef`; `fetch()` reads
that file from disk). Registered in `teams.pipeline._TEAM_SOURCES`
alongside `ftcscout`/`tba` via a new `teams/registry/fll-sd.toml` entry
carrying `sunset_season = "2026-27"` in its `config` dict (no schema
change to `SourceConfig`, whose `config` field is already a free-form
dict per source — see `registry/schema.py`). `run_teams()` gains one
staleness check: log a WARNING once `date.today()` passes the parsed
sunset date. Every other stage — `merge_teams()`, `geocode_teams()`,
`export_teams()` — runs unchanged; FLL records simply flow through the
same pipeline FTC/FRC records already do.

### Architecture Overview

See the overlay documents (above) for the full per-module Purpose,
Boundary, and Design Rationale write-up. Summary table:

| Module | Change | Use case served |
|---|---|---|
| `partner_scrape/normalize/run.py` | `_iso()`: constant offset → `zoneinfo`-resolved offset | SUC-001 |
| `partner_scrape/teams/sources/static_roster.py` (new) | New `TeamSource`: reads committed roster, never touches `Fetcher` | SUC-002 |
| `partner_scrape/teams/registry/fll-sd.toml` (new) | New Team Registry entry, `adapter_type = "static_roster"`, `sunset_season` config key | SUC-002 |
| `partner_scrape/teams/pipeline.py` | `_TEAM_SOURCES` gains one entry; `run_teams()` gains a sunset-date staleness warning | SUC-002 |

No component diagram (2 modules, no new cross-module dependency — see
sizing note above). No entity-relationship diagram (no data-model
change). No dependency graph (no dependency direction or fan-out
change — `static_roster.py` sits at the same position in the graph
`sources/ftcscout.py`/`sources/tba.py` already occupy).

### Design Rationale

- **Decision: resolve the offset via `zoneinfo`, not a second hard-coded
  constant for Standard Time.** *Context:* the bug is exactly "one
  constant, two real values depending on the calendar." *Alternatives
  considered:* a manual DST-boundary date table, refreshed yearly by
  hand — rejected as exactly the kind of hand-maintained drift risk that
  caused the original bug; `pytz` — rejected, an unnecessary dependency
  when `zoneinfo` (stdlib since Python 3.9) does the same job and this
  project already keeps dependencies deliberately minimal
  (`docs/design/design.md` Sec. 5). *Why this choice:* correct by
  construction for any date, including future DST rule changes IANA's
  tzdata publishes, with no ongoing maintenance. *Consequences:* none —
  `zoneinfo` requires no new dependency on a system with an IANA tzdata
  install, which every supported deployment target already has.
- **Decision: `Team` provenance for the static roster reuses the
  existing `Team.sources` field rather than adding a new
  `provenance`/`static` field.** *Context:* issue 20 asks that "a
  consumer can tell live data from a dated snapshot." *Alternatives
  considered:* a new boolean or enum field on `Team` — rejected because
  `Team.sources` (a list of contributing source ids, e.g. `["ftcscout"]`
  or `["ftcscout", "tba"]` after a merge) already answers exactly this
  question: a record whose `sources == ["static_roster"]` is
  static-only, by construction, with zero schema change. *Why this
  choice:* keeps this sprint at zero data-model changes (Architecture
  sizing above), and `sources` was designed in sprint 011 precisely as
  cross-source acquisition bookkeeping — this is a new source using an
  existing mechanism, not a new mechanism. *Consequences:* a consumer
  checking "is this static" must inspect list membership rather than
  read one boolean field — a minor ergonomic cost, documented in
  `teams-DESIGN.md`'s overlay copy.
- **Decision: `sunset_season` lives in the registry TOML's `config` dict,
  not a new `SourceConfig` field.** *Context:* `SourceConfig.config` is
  already a free-form per-`adapter_type` dict (`registry/schema.py`'s own
  documented rationale: "different adapter_types need different shapes
  ... over-typing it now would need revisiting the moment a fourth
  adapter type arrives" — a fifth here). *Alternatives considered:* a
  first-class `SourceConfig.sunset_season` field — rejected as exactly
  the over-typing that module's own docstring warns against, for a
  concept only one `adapter_type` (`static_roster`) needs at all. *Why
  this choice:* zero schema change, consistent with the
  existing convention every other `adapter_type`-specific key
  (`region`, `api_base`) already follows. *Consequences:* none.

### Migration Concerns

None in the data/schema sense for either change — no existing file's
schema changes, no backfill, no version bump beyond the normal
`close_sprint` cadence.

One correctness note for issue 19: any already-exported `opportunities.json`/
per-partner `.jsonl` log entries written before this fix carry the old,
sometimes-wrong offset. This sprint does not rewrite historical exports —
the next scheduled `partner-scrape run` naturally re-exports every
current/upcoming record with the corrected offset, and
`export/partner_log.py`'s append-only log is keyed by slug, not by
offset, so no reconciliation step is needed.

One sequencing note for issue 20: `partner-scrape teams` must be run at
least once against the real registry before `/teams` reflects 278
teams — the same bootstrap requirement sprint 011's own Migration
Concerns already documented for the first FTC/FRC run, now extended to
FLL. Per Test Strategy, this is a stated pre-close verification step for
this sprint, not merely a future operational concern.

## Use Cases

Both SUCs below parent to the closest existing UC by shape, matching
sprint 010's and sprint 011's precedent for new capability without a
matching existing UC (`docs/design/usecases.md`'s twelve UCs predate
both the DST/timezone concern and the `teams/` subsystem). Each is
sized to the compact tier — a brief flow, not full substantial-tier
narrative treatment.

### SUC-001: Export a record with the DST-correct UTC offset
Parent: UC-005

- **Actor**: Engine
- **Preconditions**: A naive `datetime` reaches `normalize.run.
  _to_opportunity` (i.e., no adapter set `tzinfo` — the common case for
  every adapter today).
- **Main Flow**:
  1. `_iso()` receives the naive `datetime`.
  2. It resolves the correct UTC offset for that specific date via
     `zoneinfo.ZoneInfo("America/Los_Angeles")` (`-07:00` in Daylight
     Time, `-08:00` in Standard Time).
  3. The `Opportunity.date_start`/`date_end` string carries the
     resolved offset.
- **Postconditions**: Every exported date's offset matches true San
  Diego local time year-round, not just during Daylight Time.
- **Acceptance Criteria**:
  - [ ] A July-dated naive datetime serializes with `-07:00`.
  - [ ] A January-dated naive datetime serializes with `-08:00`.
  - [ ] Both DST-transition edge cases (repeated November hour, skipped
        March hour) have documented, tested behavior via `fold`.
  - [ ] An already-aware datetime's own offset is left untouched
        (regression, unchanged from current behavior).
  - [ ] `is_current_or_upcoming` still partitions correctly for a record
        dated at a DST boundary (verification, not a code change — see
        Scope).

### SUC-002: Publish the FLL static roster as part of the teams directory
Parent: UC-001

- **Actor**: Engine
- **Preconditions**: `teams/registry/fll-sd.toml` is registered; the
  committed, contact-stripped FLL roster file exists under `teams/data/`.
- **Main Flow**:
  1. `partner-scrape teams` (or `--source static_roster`) calls
     `teams.pipeline.run_teams()`.
  2. `teams.sources.static_roster` reads the committed roster file
     (never the `Fetcher`) and maps each row to a `Team`, with
     `sources=["static_roster"]` and contact fields already absent
     (stripped at import, never carried into the module).
  3. The FLL `Team`s merge, geocode (city precision at best — rung 7's
     "never guess" rule applies to any FLL record the ladder cannot
     resolve), and export through the existing, unmodified pipeline
     stages alongside FTC/FRC.
  4. If `date.today()` is past the parsed `sunset_season` ("2026-27"),
     `run_teams()` logs a WARNING once per run.
- **Postconditions**: `teams.json` carries 278 teams (230 existing + 48
  FLL); no key or value anywhere in the file matches an email-address
  pattern; a consumer can identify a static-only record via
  `Team.sources == ["static_roster"]`.
- **Error Flows**: A malformed roster row → logged and skipped, matching
  every other source's per-record isolation convention. A missing
  roster file → `static_roster.py` raises at `discover()`/`fetch()` time
  (a missing committed data file is a build-time defect, matching
  `teams.geo.SchoolIndex`'s precedent for a missing geocoding data
  file), isolated by `run_teams()`'s existing per-source try/except so
  the rest of the run (FTC, FRC) still publishes.
- **Acceptance Criteria**:
  - [ ] `partner-scrape teams --dry-run -v` against fixtures reports 48
        FLL teams with no network call and no `Fetcher` call.
  - [ ] No key or value in the written `teams.json` matches an
        email-address pattern, verified with FLL records present.
  - [ ] A family/home FLL record (`organization=""`) is never grouped
        with another team by `merge_teams()`.
  - [ ] A simulated "today" past `2026-27` produces the sunset WARNING;
        a simulated "today" before it does not.
  - [ ] A real (non-fixture) `partner-scrape teams --dry-run` run before
        this sprint closes reports 278 teams overall, `meta.by_league`
        showing `"FLL": 48` (Test Strategy's stated pre-close
        verification step).

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [ ] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | DST-aware export timezone offset | — |
| 002 | FLL static roster team source | — |

Both tickets are independent (neither depends on the other's code,
registry entries, or data files — see Goals) and execute serially in
the order listed only for scheduling convenience; either could run
first, or in a parallel worktree, without affecting the other.

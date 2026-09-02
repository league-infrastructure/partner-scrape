---
id: '032'
title: Remaining club-type rosters
status: done
branch: sprint/032-remaining-club-type-rosters
use-cases:
- SUC-061
- SUC-062
issues:
- 35b-standing-entities-remaining-club-rosters.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 032: Remaining club-type rosters

## Goals

Populate the sprint-018 `directory/` module's `Club` model with the six
remaining club types issue 35b names: CyberPatriot teams, Science
Olympiad school teams, 4-H clubs, Girls Who Code clubs, Civil Air
Patrol squadrons, and Sea Cadets units — following the Hack Club
chapters precedent sprint 018 already delivered as the proof of
concept.

## Problem

Sprint 018 deliberately populated only one club type (Hack Club
chapters) as a proof of concept, splitting the remaining six types into
issue 35b because each needs its own curated-list research pass — this
is genuine content-research work, not just applying an already-proven
pattern. That research has not yet been done for any of the six
remaining types.

## Solution

For each of the six club types, research and assemble a curated,
trustworthy roster (mirroring `teams/sources/static_roster.py`'s
FLL-roster precedent and its documented lesson that real curated data
is messier than it looks on paper), then register each as a
static-roster source against the existing `Club` model — no model or
pipeline changes, this is purely content population against the
already-built `directory/` module. CyberPatriot has a partial starting
point (Del Norte, Scripps Ranch as national finalists) but needs a
fuller list. San Diego Math Circle and SDAA are explicitly excluded per
sprint 018's own resolution — they are single orgs belonging to the
partner roster / event registry, not this `Club` model — and VEX teams
are excluded because they already arrive via the RobotEvents adapter
(sprint 016).

## Success Criteria

- All six remaining club types (CyberPatriot, Science Olympiad, 4-H,
  Girls Who Code, Civil Air Patrol, Sea Cadets) have at least a starter
  curated roster registered against the `Club` model.
- No San Diego Math Circle, SDAA, or VEX-team entries are added to the
  `Club` model (already covered elsewhere, per sprint 018's resolution).
- Every new `club_id` is unique and non-blank, guarded by a new
  dataset-validity check (sprint 022's roster-validation precedent,
  extended to `Club`).
- Full hermetic test suite stays green; new data files pass the
  existing registry-loader tests.

## Scope

### In Scope

- Curated-roster research and registration for: CyberPatriot teams,
  Science Olympiad school teams, 4-H clubs, Girls Who Code clubs, Civil
  Air Patrol squadrons, Sea Cadets units.

### Out of Scope

- Any change to the `directory/` module's `Club` model, shared geocoding
  ladder, or static-roster source pattern — this sprint is pure content
  population against sprint 018's existing design.
- San Diego Math Circle, SDAA (belong in the partner roster / event
  registry, not `Club`) and VEX teams (already via RobotEvents) — do
  not re-register any of these three.
- Live scraping for any club type — per issue 35's original instruction
  (carried forward from sprint 018), clubs are curated, static-roster
  datasets by design.

### Scope Correction (detail planning, 2026-09-02)

The roadmap's "no change to ... the static-roster source pattern" bullet
above does not survive contact with the actual model: `Club.club_type`
is validated against `ClubType`/`VALID_CLUB_TYPES`
(`directory/model.py`), currently `Literal["hack-club"]`. Registering
any of the six new club types without widening that Literal would make
every new roster row fail `_extract_one()`'s own validation — the
roadmap's "pure content population, no model change" framing
conflated "no new field/schema" (still true) with "the `ClubType`
Literal never needs another value" (false, and not what sprint 018's
own design intended: `directory/DESIGN.md`'s Open Questions section
explicitly asks whether the six remaining types should widen
`ClubType`'s Literal and reuse the existing `_CLUB_SOURCES` dispatch,
leaving the answer to "that future sprint's own research and
implementation judgment"). Detail planning resolves that open question:
widen `ClubType` (no new field, no schema change — see Architecture,
below) and generalize the existing Hack-Club-only static-roster source
into a reusable one, rather than write six near-duplicate copies of
already-generic code. This is a minimal, single-module rename, not a
redesign — see Architecture's Design Rationale for the full
alternatives-considered writeup. Corrected scope: "no *new* module, no
new cross-module dependency, no new field on `Club`" — not "the
`ClubType` Literal and static-roster module are frozen."

## Test Strategy

Registry-loader parsing tests for each new curated-source data file,
following sprint 018's existing pattern for `directory/` static-roster
sources. This is primarily data-only work (per sprint 018's own
precedent for roster/data tickets not requiring new hermetic test
scaffolding beyond existing loader tests, unless a genuinely new
parsing shape appears). One genuine addition: a `Club`-side
`club_id`-uniqueness/non-blank dataset-validity check, extending
`tests/directory/test_dataset_validity.py`'s existing Place-only
`TestUniqueIds` pattern to `Club` — following sprint 022's roster
data-quality precedent, scoped to this module's own existing test file
(not a new validation-primitives module; `registry/validate_roster.py`
is for `partners.json` cross-referencing, a different concern from this
dataset's own internal id-uniqueness).

## Architecture

**Compact** — one changed module (`directory/`'s existing curated
static-roster `ClubSource`, generalized from Hack-Club-only to
any-club-type) plus content-only additions (six new curated TSV
rosters, six new registry entries, one widened `Literal` on an
already-generic field). No new module, no new cross-module dependency,
no dependency-direction change, and no structural data-model change —
`Club` gains no new field; `ClubType` widens exactly as sprint 018's
own design anticipated ("kept general enough ... not to block on the
answer," per `directory/DESIGN.md`'s Open Questions). See the roadmap
Scope Correction, above, for why this is a correction to the roadmap's
"no changes to the static-roster source pattern" framing, not a
departure from it.

### Architecture Overview

**What Changed**

- `directory/model.py`: `ClubType` widens from `Literal["hack-club"]`
  to `Literal["hack-club", "cyberpatriot", "science-olympiad", "4-h",
  "girls-who-code", "civil-air-patrol", "sea-cadets"]`. `VALID_CLUB_TYPES`
  (already derived via `get_args()`) picks up the six new values with
  no further change. No new field, no new dataclass.
- `directory/sources/hack_club_static_roster.py` generalizes in place
  (ticket 001 renames the file to `club_static_roster.py`, the class to
  `ClubStaticRosterSource`) to serve any curated club-type roster, not
  just Hack Club. The code was already generic — `_extract_one()`
  already reads `club_type`/`status` from each TSV row and validates
  against the model's own `VALID_CLUB_TYPES`/`VALID_CLUB_STATUSES`
  rather than hard-coding Hack Club anywhere in its logic. The one real
  change: `SOURCE_NAME` (stamped onto every `Club.sources` entry for
  provenance) becomes per-registry-entry — read from
  `SourceConfig.source_id` — instead of one hard-coded literal, so a
  CyberPatriot roster's provenance never reads `"hack_club_static_roster"`.
- `directory/pipeline.py`'s `_CLUB_SOURCES` dispatch table's one key
  changes from `"hack_club_static_roster"` to `"club_static_roster"`;
  `directory/registry/hack-club-sd.toml`'s `adapter_type` field is
  updated to match, in the same ticket, so the dispatch table and its
  one existing registry entry never disagree mid-change.
- Six new curated TSV files under `directory/data/` (one per club
  type: `cyberpatriot-sd.tsv`, `civil-air-patrol-sd.tsv`,
  `sea-cadets-sd.tsv`, `4-h-sd.tsv`, `science-olympiad-sd.tsv`,
  `girls-who-code-sd.tsv`), each following `hack-club-sd.tsv`'s exact
  ten-column shape (`club_id`, `name`, `club_type`, `host_school`,
  `city`, `postal_code`, `website`, `meeting_note`, `status`,
  `status_note`) — reused unchanged, not redesigned, per row-shape
  precedent.
- Six new registry entries under `directory/registry/`, each
  `adapter_type = "club_static_roster"` with its own `roster_path`.
- `tests/directory/test_dataset_validity.py` gains a `Club`-side
  `club_id`-uniqueness/non-blank check, extending the existing
  Place-only `TestUniqueIds` pattern (sprint 022 precedent).

**Why**

Issue 35b's six remaining club types were deliberately deferred by
sprint 018 as content-research work, not a design gap — the `Club`
model, `ClubSource` protocol, and `_CLUB_SOURCES` dispatch table were
already built general enough to take a new type without a redesign
(`directory/DESIGN.md` §5's own Open Question anticipates exactly this
sprint). The one real implementation decision this sprint makes is
*how* six new curated sources share that already-general pattern — see
Design Rationale, below.

**Impact on Existing Components**

Additive except for one deliberate rename. The four existing curated
Hack Club chapters (`hack-club-sd.tsv`) are untouched in content; only
their registry entry's `adapter_type` string and their `Club.sources`
provenance value change (from `"hack_club_static_roster"` to a
`club_static_roster`-sourced value), landing atomically with the module
rename in ticket 001 so no run ever sees a dangling dispatch-table key.
No other `directory/` artifact (`Place`, `Offering`, their sources,
`export.py`, the shared `geo_ladder.GeoLadder`) is touched.

**Migration Concerns**

The `hack-club-sd.toml` registry-entry rename and the module rename
must land in the same commit/ticket (001) — a partial rename (module
renamed, registry entry not updated, or vice versa) would make
`run_directory()` log a spurious "no ClubSource registered" warning for
the existing Hack Club registry entry and silently drop it from a run.
Ticket 001's acceptance criteria pin this: the four existing Hack Club
chapters must parse and geocode identically before and after the
rename. No published `clubs.json` schema changes; the `sources`
provenance string on already-published Hack Club rows is a
documentation-only value, not part of any consumer's contract.

**Geocoding note (not every new club type is school-hosted).**
`Club.host_school` is unchanged and still the argument
`_apply_club_geocoding()` passes to `GeoLadder.locate()`. CyberPatriot,
Science Olympiad, and most Girls Who Code chapters are genuinely
school-hosted, so the shared ladder's CDE/NCES school-matching rungs
(1-4) apply to them as directly as they do to Hack Club. Civil Air
Patrol squadrons, Sea Cadets units, and many 4-H clubs typically meet
at their own facilities (armories, training centers, extension
offices), not K-12 campuses — for those, rungs 1-4 are expected to miss
cleanly (a squadron/unit name shares essentially no tokens with a
school-directory name, so a spurious Jaccard-threshold match is not a
realistic risk) and the ladder honestly falls through to the zip/city
rungs (5-6), exactly the same degrade `Place` already relies on for
its own non-school venues. Each population ticket should expect (not
fight) `location_precision` landing at `"zip"`/`"city"` rather than
`"school"` for a non-school-hosted entry — that is correct behavior,
not a defect to chase.

### Design Rationale

**Decision**: generalize and rename the existing
`hack_club_static_roster.py` into a reusable `club_static_roster.py`
serving any curated club type, rather than writing one new
near-duplicate source module per club type.

**Context**: the existing module's code is already generic — nothing
in `discover()`/`fetch()`/`extract()` is Hack-Club-specific except its
file name, its class name, its hard-coded `SOURCE_NAME`, and its
default roster path (all four are naming/defaults, not logic).

**Alternatives considered**:
(a) Six new near-identical `*_static_roster.py` modules (one per club
type), leaving `hack_club_static_roster.py` untouched — rejected: pure
duplication of already-generic code (a real "shotgun surgery" risk the
next club type would repeat), and it would leave the *existing*
module's name permanently misdescribing what it can serve.
(b) Leave the module's name/`adapter_type`/`SOURCE_NAME` unchanged and
just point six new registry entries at it — rejected: every non-Hack-Club
`Club.sources` entry would then carry the literal string
`"hack_club_static_roster"`, a misleading provenance/audit trail for a
CyberPatriot or Sea Cadets record.

**Why this choice**: one rename, reused seven times (the existing Hack
Club registration plus six new ones), keeps `Club.sources` provenance
honest per club type and leaves a future eighth club type needing only
a new TSV + registry entry — no code.

**Consequences**: `hack-club-sd.toml`'s `adapter_type` value changes as
a one-line edit alongside the rename (see Migration Concerns); every
test importing the old module path/class name updates in the same
ticket.

## Use Cases

### SUC-061: The curated static-roster ClubSource generalizes to serve any club type, not just Hack Club
Parent: UC-008 (Add a new partner source)

- **Actor**: `directory` pipeline, on behalf of the generalized
  `club_static_roster` source.
- **Preconditions**: A `directory/registry/` entry sets
  `adapter_type = "club_static_roster"` and a `roster_path` pointing at
  a curated TSV under `directory/data/` following `hack-club-sd.tsv`'s
  column shape.
- **Main Flow**:
  1. `discover()` resolves the configured `roster_path` (relative paths
     resolve under `directory/data/`) to a single `ClubRef`.
  2. `fetch()` reads the file straight off disk — the injected
     `Fetcher` is never called, matching the existing
     `TestNeverTouchesFetcher` structural guarantee.
  3. `extract()` validates each row's `club_type`/`status` against the
     model's widened `VALID_CLUB_TYPES`/`VALID_CLUB_STATUSES` and
     stamps this registry entry's own `source_id` as provenance.
  4. `directory.pipeline.run_directory()`'s existing `_CLUB_SOURCES`
     dispatch (keyed by `adapter_type`, unchanged in shape) routes the
     entry to this one source implementation, whatever club type it
     curates.
- **Postconditions**: Any club type — Hack Club or any of issue 35b's
  six — can register a curated roster through one shared source
  implementation; no new Python module is needed to add an eighth type
  later.
- **Acceptance Criteria**:
  - [ ] `hack-club-sd.toml`'s `adapter_type` is `club_static_roster`,
        and the four existing Hack Club chapters parse and geocode
        identically to before the rename (same `location_precision`,
        same `needs_review` outcomes, Helix Charter still flagged).
  - [ ] Registering a new club type requires only a new TSV file and a
        new `directory/registry/*.toml` entry with
        `adapter_type = "club_static_roster"` — no new Python module.
  - [ ] No `Club.sources` entry for a non-Hack-Club club ever contains
        the literal string `"hack_club_static_roster"`.
  - [ ] `TestNeverTouchesFetcher`-style coverage still passes for the
        renamed module.

### SUC-062: Curated, live-verified starter rosters exist for issue 35b's six remaining club types
Parent: UC-008 (Add a new partner source)

- **Actor**: Operator/programmer, curating each roster by hand against
  a live-verified public source (per this project's cross-sprint
  verification standard: live-verify every roster source before
  recording it, record what the source actually says today, never
  transcribe the issue's own research as if pre-verified).
- **Preconditions**: SUC-061's generalized source and widened
  `ClubType` exist.
- **Main Flow**: For each of the six club types, in descending order of
  how likely a public roster exists (CyberPatriot, Civil Air Patrol,
  Sea Cadets, 4-H, Science Olympiad, Girls Who Code — see Tickets,
  below): research a live, currently-published roster; curate a TSV
  following `hack-club-sd.tsv`'s column shape; register it via a new
  `directory/registry/` entry; run `directory` (dry-run) to confirm
  each entry's geocoding outcome; flag any fuzzy/rung-3-4 match honestly
  via `needs_review` rather than force-resolving it (mirroring Helix
  Charter's own precedent); if a type's curated list turns out not to
  exist publicly, record that as a documented finding in the ticket
  rather than fabricating entries.
- **Postconditions**: Each of CyberPatriot, Civil Air Patrol, Sea
  Cadets, 4-H, Science Olympiad, and Girls Who Code either has a
  curated, live-verified starter roster registered against the `Club`
  model, or has an honest, documented finding explaining why no public
  roster was found.
- **Acceptance Criteria**:
  - [ ] CyberPatriot: at least Del Norte and Scripps Ranch (the issue's
        named national finalists) plus any additional San Diego team
        confirmed via a live-verified public source (e.g. AFA
        CyberPatriot's own results/finalist pages).
  - [ ] Civil Air Patrol: squadrons 144 and 201 and Group 8 registered
        with live-verified meeting locations from CAP's own California
        Wing unit locator.
  - [ ] Sea Cadets: San Diego-area units registered from the U.S. Naval
        Sea Cadet Corps' own national unit locator.
  - [ ] 4-H: San Diego County 4-H clubs registered from UC ANR's own
        county 4-H roster.
  - [ ] Science Olympiad: San Diego-area school teams registered from a
        live-verified California Science Olympiad regional/state
        results or roster page.
  - [ ] Girls Who Code: San Diego-area clubs registered from the
        official Girls Who Code club locator, or a documented finding
        if no public San Diego listing is exposed.
  - [ ] No San Diego Math Circle, SDAA, or VEX-team entry is added
        (already covered elsewhere per sprint 018's resolution).
  - [ ] Every new `club_id` is unique and non-blank (guarded by
        SUC-061's `TestUniqueIds`-style `Club` coverage).
  - [ ] Full hermetic test suite stays green; no test in this sprint's
        tickets reaches a real network call (live verification happens
        during ticket research/execution, never inside a test).

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [x] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Issue |
|---|-------|------------|-------|
| 001 | Generalize club static-roster source, widen ClubType, add club_id data-quality check | — | 35b |
| 002 | Curate and register CyberPatriot teams roster | 001 | 35b |
| 003 | Curate and register Civil Air Patrol squadrons roster | 001 | 35b |
| 004 | Curate and register Sea Cadets units roster | 001 | 35b |
| 005 | Curate and register 4-H clubs roster | 001 | 35b |
| 006 | Curate and register Science Olympiad school teams roster | 001 | 35b |
| 007 | Curate and register Girls Who Code clubs roster | 001 | 35b |

Tickets execute serially in the order listed. 001 is the sole
foundation ticket every other ticket depends on; 002-007 each touch
disjoint files (their own TSV + registry entry) and have no dependency
on one another beyond 001 — the order above sequences them by
descending likelihood of a findable public roster (CyberPatriot > Civil
Air Patrol > Sea Cadets > 4-H > Science Olympiad > Girls Who Code), not
by a structural dependency, so this sprint's own default serial
execution runs them in that narrative order.

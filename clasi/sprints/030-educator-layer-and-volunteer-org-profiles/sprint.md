---
id: '030'
title: Educator layer and volunteer org profiles
status: executing
branch: sprint/030-educator-layer-and-volunteer-org-profiles
use-cases:
- SUC-049
- SUC-050
- SUC-051
- SUC-052
- SUC-053
issues:
- 33-educator-programs-layer.md
- 14-improve-volunteer-opportunity-discovery.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 030: Educator layer and volunteer org profiles

## Goals

Deliver two content gaps that share one underlying record shape: an
undated standing "offering" record — org, what it is, eligibility, age
minimums, how to book / where to apply, link out, last-verified. Serve
issue 33's educator-program layer (free/Title I school programs: Zoo
FREE field trips, the Nat's Museum Access Fund, Living Coast Title 1
aid, Birch financial aid, Fleet discounted trips/Science to
Go/Family Science Nights, Qualcomm Thinkabit Lab, Biocom Life Science
Station/Innov8Ed) and issue 14's volunteer org profiles (Strategy B:
Fleet 18+, SDZWA 18+, Birch 16+, the Nat, ILACSD, San Diego River Park
Foundation) with the same shape, plus issue 33 part 1's curated
educator-PD program pages (SDCOE-adjacent static pages, UCSD CREATE,
SD Science Project, UCSD Math Project, Code.org regional partner,
CSTA-SD, SDSU CRMSE, Fleet educator workshops, Salk STEM Educators
Summit, Zoo teacher workshops) via Sprint A's (027) program-page
extractor, typed `Professional Development / Conferences`.

## Problem

Educators are a named audience of the site and currently get nothing.
Separately, issue 14's research (2026-08-30 update) closed out
Strategy A (scraping third-party volunteer platforms) as dead — ToS
forbid it on the major platforms, and our STEM partners don't post to
aggregators anyway; they use private, login-gated volunteer-management
portals with no public feed. What both issues actually need is the
same thing: a standing, undated "here's what this org offers and how
to get it" record, which the current `Opportunity`/`Event` model
(dated, event-shaped) cannot represent — the same structural gap sprint
011 already solved once for robot teams and sprint 018 solved again for
places/clubs via the `directory/` module.

## Solution

Design **one record shape** serving both concerns and extend the
`directory/` module (sprint 018) rather than re-designing it — the
`directory/` module already exists precisely to house standing,
undated entities (`Place`, `Club`) with a curated static-roster source
pattern; this record type follows the same precedent rather than
inventing a third module. Populate it with:
- **Volunteer org profiles** (issue 14 Strategy B): org, what
  volunteers do, age minimums (explicitly: Fleet 18+, SDZWA 18+, Birch
  16+), link to their portal.
- **Free/Title I school-program records** (issue 33 part 2): org,
  program, eligibility, how to book, last-verified.
- **Curated educator-PD program pages** (issue 33 part 1) via Sprint
  A's program-page extractor — these are dated (a workshop has a date),
  so they flow through Sprint A's mechanism and the existing
  `Opportunity` model with `Professional Development / Conferences`
  typing, not through the new standing-entity record.

Issue 14's Strategy A is not revisited — it is dead per the issue's own
2026-08-30 research update. No scraping of VolunteerMatch, Idealist,
ActivityHero, JustServe, HandsOn San Diego, or Points of Light Engage
is planned.

## Success Criteria

- A single new standing-entity record type exists in `directory/`
  serving both volunteer org profiles and free/Title I school programs,
  with org, eligibility/age-minimum, how-to-book, link-out, and
  last-verified fields.
- Fleet, SDZWA, Birch, the Nat, and ILACSD volunteer profiles are
  populated with correct age minimums.
- The Nat's Museum Access Fund, Zoo FREE field trips, Living Coast
  Title 1 aid, Birch financial aid, Fleet discounted-trip programs,
  Qualcomm Thinkabit Lab, and Biocom Life Science Station/Innov8Ed are
  populated as free/Title-I program records.
- At least the majority of the named educator-PD program pages are
  registered via Sprint A's extractor and yield correctly-dated
  `Professional Development / Conferences` records.
- `offerings.json` publishes to this repo's `data/` directory as the
  data contract for the new `Offering` records (see Scope Correction,
  below, for why "a site page renders them" is no longer this sprint's
  own success criterion).
- Full hermetic test suite stays green.

### Scope Correction (detail planning, 2026-09-02)

The roadmap plan above named "a site page renders the new
standing-entity records, following the `places`/`clubs` page precedent
from sprint 018" as both a Success Criterion and an In-Scope item. That
precedent no longer holds: sprint 019 converted this repo's `site/`
from an independently-tracked Astro checkout (the one sprint 018 added
`site/src/pages/places/`/`clubs/` to) into a build-time-only checkout of
the separate `stem-ecosystem` repository — gitignored, populated only
at CI build time, not present in this checkout at all (`site/` does not
exist on disk here today). There is no site-page code left in this
repo's write scope to add a page to, and this repo cannot write
rendering code into a sibling repo it does not control. This sprint's
actual deliverable is the `offerings.json` data contract; rendering it
is `stem-ecosystem`'s own follow-up, outside this repo (matching the
hard constraint already given for this sprint: "stem-ecosystem
consuming it is their concern, not this sprint's"). Success Criteria
and Scope below reflect this correction; see `design/directory-
DESIGN.md`'s sprint 030 Revision and `design/design.md`'s sprint 030
addition for the full architectural write-up.

## Scope

### In Scope

- One new standing-entity record shape in `directory/`, extending that
  module's existing `Place`/`Club` pattern.
- Volunteer org profile data population (issue 14 Strategy B).
- Free/Title I school-program record population (issue 33 part 2).
- Educator-PD program-page registration via Sprint A's (027) extractor,
  extended with a new extraction profile purpose-built for the genre
  (see `design/adapters-DESIGN.md`'s sprint 030 Revision — reusing
  sprint 029's `"competition"` or the original `"program"` profile
  verbatim was evaluated and rejected; see that doc for why).
- Verifying issue 14's already-registered dated volunteer-event sources
  (UCSD Localist Volunteer type, Coastkeeper TEC, Surfrider SD Google
  Calendar, ILACSD) are still correctly enabled/yielding — not
  re-registering them.

### Out of Scope

- Any volunteer-platform scraping (issue 14 Strategy A) — dead per the
  issue's own research; not revisited.
- SDCOE PD registrations on k12oms.org — robots.txt disallows all
  scraping; already excluded in `registry/DO_NOT_SCRAPE.md`, explicitly
  not attempted.
- Grants/speakers content with no live source (SDG&E closed,
  DonorsChoose robots-restricted, Pathful licensed) — noted, skipped.
- Any redesign of the `directory/` module's existing `Place`/`Club`
  models or its shared geocoding ladder — `Offering` deliberately adds
  no geocoding of its own (see `design/directory-DESIGN.md`'s sprint 030
  Revision).
- **Rendering `offerings.json` as a site page.** See the Scope
  Correction under Success Criteria, above — `site/` is a build-time-
  only checkout of the separate `stem-ecosystem` repository as of
  sprint 019; this repo cannot write rendering code into it.
  `stem-ecosystem`'s own consumption of `offerings.json` is tracked
  there, not here.
- **Fixing `ProgramExtractionCache`'s cache key not including
  `profile`.** A real, pre-existing gap (present since sprint 027, not
  introduced by this sprint) flagged in `design/adapters-DESIGN.md`'s
  sprint 030 Revision as an Open Question — recommend a follow-up issue
  rather than fixing it here, since no URL registered by this sprint or
  any prior one has ever been cached under a different profile (the
  actual failure mode requires a source's `opportunity_type` override
  to change after a cache entry already exists, which has not happened).

## Test Strategy

Fixture-based tests for the new standing-entity model and its
static-roster source pattern, following `directory/`'s existing
per-module test convention from sprint 018. Educator-PD program-page
tests reuse Sprint A's extractor test pattern (saved fixtures, no live
network). Registry-loader parsing tests for the new curated data files.

## Architecture

**Substantial** — three `partner_scrape/` modules touched
(`directory/`, `adapters/`, `registry/`), a new standing-entity data
model (`Offering`), and a new cross-module composition (a third
`ProgramLLMClient` extraction profile selected by `adapters/
program_page.py` from registry-carried data, mirroring — but not
reusing verbatim — sprint 029's `profile="competition"` precedent for a
third genre). Per this project's design-doc opt-in, the full write-up
lives in this sprint's `design/` overlay, not in this section —
see `architecture-authoring`'s Mode 2a. This section is a pointer,
not a restatement.

The affected canonical docs and their overlay copies:

- `partner_scrape/directory/DESIGN.md` (overlay:
  `design/directory-DESIGN.md`) — the new `Offering` standing-entity
  model, `OfferingSource` protocol, `offering_static_roster.py`,
  `_OFFERING_SOURCES` pipeline dispatch, and `offerings.json` export,
  extending the module's existing `Place`/`Club` pattern to a third
  entity type. Covers both issue 14 Strategy B and issue 33 part 2.
- `partner_scrape/adapters/DESIGN.md` (overlay:
  `design/adapters-DESIGN.md`) — a third `ProgramLLMClient` extraction
  profile, `profile="pd"`, for educator-PD workshop/conference pages
  (issue 33 part 1), alongside the existing `"program"` (application-
  window) and `"competition"` (sprint 029) profiles. Documents why
  reusing either existing profile verbatim was rejected, learning
  directly from sprint 029's own Revision.
- `partner_scrape/registry/DESIGN.md` (overlay:
  `design/registry-DESIGN.md`) — the new `offerings-sd.toml` Directory
  Registry entry and the new educator-PD `program_page`/
  `program_page_multi`/`program_listing` registrations
  (`config.opportunity_type = "Professional Development / Conferences"`),
  plus a note on issue 14's dated-volunteer-event verification pass.
- `docs/design/design.md` (overlay: `design/design.md`) — a short
  "Sprint 030 addition" paragraph in §3's pipeline narrative, plus a
  missing `directory/DESIGN.md` subsystem-map link fixed as part of
  this sprint's substantial extension of that subsystem.

Architecture review: **APPROVE** (full five-category self-review,
recorded via `record_gate_result`). See that gate's notes for the
summary; see the overlay `.diff.md` files for the reviewed content
itself.

### Architecture Overview

See the `design/` overlay's edited copies for the full write-up. In
outline: one `Offering` record (org, title, `offering_type`
discriminator, description, eligibility, first-class `age_minimum`,
how-to-book, link-out, last-verified, optional hand-verified
`related_partner_id`) serves both issues rather than two models;
`Offering` deliberately carries no location/geocoding fields (a real
scope narrowing versus `Place`/`Club`, not an oversight — an offering
isn't a place to travel to); educator-PD pages route through the
*existing* `program_page`/`program_page_multi`/`program_listing`
mechanism with a new `profile="pd"` extraction prompt, not a new
adapter or model.

### Design Rationale

See the `design/` overlay's edited copies for the full Decision /
Context / Alternatives / Consequences entries — most notably: one
`Offering` model for both issues (`directory-DESIGN.md`); no
geocoding/location fields on `Offering`, and what a future map view
would require if ever requested (`directory-DESIGN.md`); a new
`"pd"` profile rather than reusing `"competition"` or `"program"`
(`adapters-DESIGN.md`); and why `age_minimum` is a first-class typed
field rather than folded into free-text eligibility (`directory-
DESIGN.md`).

### Migration Concerns

Additive only — no existing source, adapter, model field, or
`Opportunity` consumer changes behavior. `ProgramExtractionCache`'s
on-disk shape and `_CACHE_SCHEMA_VERSION` are unchanged (the `pd`
profile adds no new `ProgramExtractionResult` field). See the Scope
Correction under Success Criteria, above, for the one roadmap-plan
claim ("a site page renders the new records") that detail planning
found to no longer be true, and why — full architectural reasoning in
`design/directory-DESIGN.md`'s and `design/design.md`'s sprint 030
sections.

## Use Cases

### SUC-049: A registered educator-PD program page yields a dated "Professional Development / Conferences" record via a purpose-built extraction profile
Parent: UC-011 (Discover STEM company events and internships (extension))

- **Actor**: Pipeline, on behalf of a registered educator-PD
  `program_page`/`program_page_multi`/`program_listing` source (e.g.
  UCSD CREATE, Salk STEM Educators Summit, Fleet educator workshops).
- **Preconditions**: A source TOML registers one educator-PD page (or
  listing) with `config.program_kind = "program"` and
  `config.opportunity_type = "Professional Development / Conferences"`.
- **Main Flow**:
  1. `program_page.py`'s `_resolve_extraction_profile()` resolves
     `profile="pd"` from the source's `opportunity_type` override.
  2. The adapter fetches the page, reduces it via
     `extract.reduce_html_to_text()`, and calls `ProgramLLMClient.
     extract_program()`/`extract_programs()` with `profile="pd"`.
  3. The `pd` system prompt extracts the workshop/summit/conference's
     own date (not an application window), any stated registration
     deadline, and an educator-audience eligibility description.
  4. `_map_result_to_event()` maps the result onto an `Event`, forced
     to `opportunity_type = "Professional Development / Conferences"`
     by the config override.
- **Postconditions**: One `Event` per registered educator-PD page/card,
  correctly dated to the event's own date (never conflated with a
  registration deadline), typed `Professional Development /
  Conferences`.
- **Acceptance Criteria**:
  - [ ] Each of UCSD CREATE, SD Science Project, UCSD Math Project,
        Code.org regional partner, CSTA-SD, SDSU CRMSE, Fleet educator
        workshops, Salk STEM Educators Summit, and Zoo teacher
        workshops is either registered `enabled = true` and
        live-verified to yield a correctly-dated
        `Professional Development / Conferences` record, or registered
        `enabled = false` with a reason comment (sprint 027/028/029
        precedent) if blocked.
  - [ ] k12oms.org (SDCOE's own PD registration system) is confirmed
        excluded per `registry/DO_NOT_SCRAPE.md` — not registered.
  - [ ] `profile="pd"` is exercised by at least one `FixtureProgramLLMClient`-backed
        test distinct from the `"program"`/`"competition"` profile
        tests, proving the three profiles select independently.

### SUC-050: A curated volunteer org profile surfaces an org's volunteer opportunity with a first-class age minimum
Parent: UC-008 (Add a new partner source)

- **Actor**: `directory` pipeline, on behalf of the
  `offering_static_roster` source.
- **Preconditions**: `directory/registry/offerings-sd.toml` registers
  `adapter_type = "offering_static_roster"`; `directory/data/
  offerings.toml` carries one or more `[[offering]]` rows with
  `offering_type = "volunteer"`.
- **Main Flow**:
  1. `OfferingStaticRosterSource.discover()`/`fetch()`/`extract()`
     reads `offerings.toml` off disk (never the injected `Fetcher`).
  2. Each row is validated (required fields present; `status_note`
     required whenever `status != "active"`) and mapped to an
     `Offering`.
  3. `directory.pipeline.run_directory()`'s `_OFFERING_SOURCES`
     dispatch collects every `Offering`; no geocoding stage runs.
  4. `export_directory()` writes `offerings.json` to `data/`.
- **Postconditions**: Fleet (18+), SDZWA (18+), Birch (16+), the Nat,
  ILACSD, and San Diego River Park Foundation each have an `Offering`
  row with a correct, typed `age_minimum` (or `None` where the org
  states no minimum) and a working link to their volunteer portal.
- **Acceptance Criteria**:
  - [ ] All six named volunteer orgs are present in `offerings.toml`
        with `offering_type = "volunteer"`.
  - [ ] Fleet and SDZWA's `age_minimum` is `18`; Birch's is `16`,
        matching issue 14's own research verbatim.
  - [ ] `offerings.json`'s `"offerings"` array includes all six rows
        with non-empty `link_url`.

### SUC-051: A curated free/Title I school-program record surfaces an org's undated, bookable offering with eligibility and how-to-book info
Parent: UC-008 (Add a new partner source)

- **Actor**: `directory` pipeline, on behalf of the same
  `offering_static_roster` source as SUC-050.
- **Preconditions**: `offerings.toml` carries one or more `[[offering]]`
  rows with `offering_type = "free_program"`.
- **Main Flow**: Identical to SUC-050's Main Flow — one source, one
  extraction path, differing only in which `offering_type` value and
  which fields (`eligibility`, `how_to_book`, no `age_minimum`) a given
  curated row populates.
- **Postconditions**: The Nat's Museum Access Fund, Zoo FREE field
  trips, Living Coast Title 1 + CVESD free transport, Birch financial
  aid, Fleet discounted trips/Science to Go/Family Science Nights,
  Qualcomm Thinkabit Lab, and Biocom Life Science Station/Innov8Ed each
  have an `Offering` row with eligibility and how-to-book information a
  Title I coordinator or teacher can act on directly.
- **Acceptance Criteria**:
  - [ ] All seven named free/Title I programs are present in
        `offerings.toml` with `offering_type = "free_program"`.
  - [ ] Every row's `eligibility` and `how_to_book` fields are
        non-empty and reflect that program's own published terms (e.g.
        the Zoo's 4-week lead time, the Nat's Title I framing).
  - [ ] `last_verified` is set to the date each row was actually
        checked against the org's own current page — never guessed or
        left as a placeholder.

### SUC-052: The Offering directory publishes as `offerings.json`, the data contract for both volunteer profiles and free/Title I programs
Parent: UC-006 (Export upcoming opportunities to the site)

- **Actor**: `directory` pipeline / `export_directory()`.
- **Preconditions**: `run_directory()` has acquired zero or more
  `Offering` records (from `offering_static_roster` or any future
  `OfferingSource`).
- **Main Flow**:
  1. `export_directory()` receives an `offerings` argument (`None` =
     don't touch the file; a list, possibly empty, = write it).
  2. Records are sorted (matching `places.json`/`clubs.json`'s own
     `(type, name)` convention: `(offering_type, name)`).
  3. `offerings.json` is written to `config.get_own_data_dir()`
     (`data/`) only — never into a `site_dir`/`stem-ecosystem`
     checkout, matching sprint 025's "one publish, one path" rule.
  4. The written file's own `meta` records `generated`, `total`, and a
     `by_offering_type` breakdown, mirroring `places.json`/
     `clubs.json`'s self-describing shape.
- **Postconditions**: `data/offerings.json` exists, is well-formed, and
  is independently fresh-datable from `places.json`/`clubs.json`/
  `opportunities.json`/`teams.json` — none of those four files are
  touched by this export.
- **Acceptance Criteria**:
  - [ ] `export_directory(places, clubs=None, offerings=[...])` writes
        `offerings.json` to `own_data_dir` and leaves `places.json`,
        `clubs.json`, `opportunities.json`, `scrape-meta.json`, and
        `teams.json` byte-identical to before the call (a dedicated
        regression test, matching `tests/directory/test_export.py`'s
        existing `TestHardInvariants` pattern, extended to cover
        `offerings.json`'s own hard invariants).
  - [ ] A test pins `get_own_data_dir()` to `tmp_path` (per this
        sprint's hard constraint) for every test that reaches
        `export_directory()`/`run_directory()` with a real `offerings`
        argument — no test writes into the real repo's `data/`.
  - [ ] `offerings=None` (the default, every pre-existing call site)
        leaves `offerings.json` untouched — not written, not deleted.

### SUC-053: Issue 14's already-registered dated volunteer-event sources are confirmed correctly enabled and yielding
Parent: UC-011 (Discover STEM company events and internships (extension))

- **Actor**: Sprint-planner/programmer, verifying (not re-registering)
  existing registry state.
- **Preconditions**: UCSD Localist's Volunteer event type, Coastkeeper
  TEC, Surfrider SD Google Calendar, and ILACSD are each already
  registered under whichever pre-existing `adapter_type` each one uses
  (`localist`/`tec_rest`/`ical`/`generic_html`) — not new registrations,
  per issue 14's own 2026-08-30 research conclusion.
- **Main Flow**:
  1. For each of the four sources, confirm its current `enabled` state
     and its `opportunity_type`/`Volunteering` typing (taxonomy already
     supports it, per `normalize/taxonomy.py`).
  2. Where feasible without violating this sprint's live-network/API
     hard constraints, dry-run each source and confirm a non-zero
     `Volunteering`-typed yield.
  3. Where a source is found disabled, misconfigured, or zero-yield for
     a reason within this ticket's scope to fix (a config edit, not a
     new adapter), fix it; otherwise document the gap and leave a
     dated comment, matching sprint 027/028/029's own disabled-source
     comment precedent.
- **Postconditions**: Each of the four sources' current state (enabled/
  disabled, yield) is confirmed and recorded in this ticket's own Notes
  — no source is left in an unknown state.
- **Acceptance Criteria**:
  - [ ] UCSD Localist's Volunteer event type is confirmed registered
        and yielding `Volunteering`-typed records, or its gap is
        documented with a reason.
  - [ ] Coastkeeper TEC is confirmed registered and yielding.
  - [ ] Surfrider SD Google Calendar is confirmed registered and
        yielding.
  - [ ] ILACSD is confirmed registered and yielding.
  - [ ] No new source registration is created by this ticket — only
        config edits to already-existing TOML files, if needed.

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
| 001 | Offering standing-entity model, registry dispatch, and offerings.json export | — | 33, 14 |
| 002 | Populate volunteer org profiles (issue 14 Strategy B) | 001 | 14 |
| 003 | Populate free/Title I school-program records (issue 33 part 2) | 001 | 33 |
| 004 | Add pd extraction profile for educator-PD pages to program_llm.py and program_page.py | — | 33 |
| 005 | Register and live-verify curated educator-PD program pages (issue 33 part 1) | 004 | 33 |
| 006 | Verify issue 14's existing dated volunteer-event source registrations | — | 14 |

Tickets execute serially in the order listed. 001-003 (the `directory/`
track) and 004-005 (the `adapters/` track) have no dependency on each
other — they are ordered this way for narrative clarity, not because
004/005 must follow 001-003. 006 is independent of every other ticket
and could run at any point in the sequence.

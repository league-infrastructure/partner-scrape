---
id: '032'
title: Remaining club-type rosters
status: roadmap
branch: sprint/032-remaining-club-type-rosters
use-cases: []
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

## Test Strategy

Registry-loader parsing tests for each new curated-source data file,
following sprint 018's existing pattern for `directory/` static-roster
sources. This is primarily data-only work (per sprint 018's own
precedent for roster/data tickets not requiring new hermetic test
scaffolding beyond existing loader tests, unless a genuinely new
parsing shape appears).

## Architecture

(Likely **trivial/small** — pure content population against an
existing, unmodified model and pipeline stage, with no new module,
cross-module dependency, or data-model change. The detail-planning
sprint-planner should confirm this at detail-planning time; if any club
type turns out to need a genuinely new parsing shape or field, revise
the sizing accordingly.)

### Architecture Overview

(Deferred to detail planning — expected N/A given the trivial/small
sizing above.)

### Design Rationale

(Deferred to detail planning.)

### Migration Concerns

(Deferred to detail planning.)

## Use Cases

(Deferred to detail planning — roadmap phase does not include full use
cases.)

### SUC-001: (Title)
Parent: UC-XXX

- **Actor**: (Who)
- **Preconditions**: (What must be true before)
- **Main Flow**:
  1. (Step)
- **Postconditions**: (What is true after)
- **Acceptance Criteria**:
  - [ ] (Criterion)

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

Tickets execute serially in the order listed.

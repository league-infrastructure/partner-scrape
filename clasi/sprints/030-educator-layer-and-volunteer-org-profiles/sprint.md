---
id: '030'
title: Educator layer and volunteer org profiles
status: roadmap
branch: sprint/030-educator-layer-and-volunteer-org-profiles
use-cases: []
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
- A site page renders the new standing-entity records (following the
  `places`/`clubs` page precedent from sprint 018).
- Full hermetic test suite stays green.

## Scope

### In Scope

- One new standing-entity record shape in `directory/`, extending that
  module's existing `Place`/`Club` pattern.
- Volunteer org profile data population (issue 14 Strategy B).
- Free/Title I school-program record population (issue 33 part 2).
- Educator-PD program-page registration via Sprint A's (027) extractor
  (issue 33 part 1).
- A site directory page for the new record type.

### Out of Scope

- Any volunteer-platform scraping (issue 14 Strategy A) — dead per the
  issue's own research; not revisited.
- SDCOE PD registrations on k12oms.org — robots.txt disallows all
  scraping; explicitly not attempted.
- Grants/speakers content with no live source (SDG&E closed,
  DonorsChoose robots-restricted, Pathful licensed) — noted, skipped.
- Any redesign of the `directory/` module's existing `Place`/`Club`
  models or its shared geocoding ladder.

## Test Strategy

Fixture-based tests for the new standing-entity model and its
static-roster source pattern, following `directory/`'s existing
per-module test convention from sprint 018. Educator-PD program-page
tests reuse Sprint A's extractor test pattern (saved fixtures, no live
network). Registry-loader parsing tests for the new curated data files.

## Architecture

(To be sized and written at detail-planning time. Likely **compact to
substantial** — the record shape is new but explicitly extends the
existing `directory/` module rather than introducing a new subsystem;
the detail-planning sprint-planner should make its own sizing call,
weighing whether adding a third entity type to `directory/` counts as
one module change or touches enough of that module's shared machinery
to be substantial.)

### Architecture Overview

(Deferred to detail planning.)

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

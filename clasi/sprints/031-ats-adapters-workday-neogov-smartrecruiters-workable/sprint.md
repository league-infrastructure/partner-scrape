---
id: '031'
title: 'ATS adapters: Workday, NEOGOV, SmartRecruiters, Workable'
status: roadmap
branch: sprint/031-ats-adapters-workday-neogov-smartrecruiters-workable
use-cases: []
issues:
- 31-ats-adapters-workday-neogov-smartrecruiters.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 031: ATS adapters: Workday, NEOGOV, SmartRecruiters, Workable

## Goals

Add college/early-career internship coverage for the career-pathway
story via four new ATS adapters: Workday (Northrop Grumman including
its HS Internship Program req, Cubic, Illumina, Dexcom, likely ResMed
and Sempra/SDG&E), NEOGOV/governmentjobs.com (County of SD, City of SD,
SANDAG, Port of SD as one adapter, four agencies), SmartRecruiters
(ServiceNow), and Workable (SD County Regional Airport Authority).
Also register Sony Interactive Entertainment against the existing
Greenhouse adapter.

## Problem

The site has no college/early-career internship coverage from major
San Diego employers' applicant-tracking systems. Each ATS vendor has
its own API/scraping shape (Workday needs browser-like headers via
POST to `/wday/cxs/{tenant}/{site}/jobs`; NEOGOV is one shape across
four agency instances; SmartRecruiters and Workable both expose public
JSON). This is self-contained work, independent of the record-shape and
extraction-mechanism work in Sprints A-D.

## Solution

Build four adapters in the order named, reusing the existing
`ats_filters` (internship + STEM + San Diego filtering) and the routing
convention already established for the existing greenhouse/lever
adapters (Work-based Learning type). Add Sony Interactive Entertainment
(board `sonyinteractiveentertainmentglobal`, verified 200) to the
existing Greenhouse adapter's registered boards as a small additive
registration alongside the new adapter work. Probe, but do not build
bespoke adapters for, the unconfirmed-ATS employers (Qualcomm,
Solar Turbines, Teradata, BAE, General Atomics, Intuit) — if a probe
finds a clean shape, that is future work, not this sprint's.
Expect long stretches of zero matching postings from any given
adapter — internship reqs are seasonal and rare relative to total
postings — that is signal, not error, matching this codebase's existing
tolerance for source-level sparsity.

## Success Criteria

- Workday, NEOGOV, SmartRecruiters, and Workable adapters are built, in
  that order, and each registers at least the employer(s) named above.
- Sony Interactive Entertainment is registered against the existing
  Greenhouse adapter.
- All four new adapters route matching postings as Work-based Learning,
  filtered through `ats_filters`.
- Full hermetic test suite stays green, with fixture-based tests for
  each new adapter (no live network).

## Scope

### In Scope

- Workday adapter (Northrop Grumman, Cubic, Illumina, Dexcom; ResMed
  and Sempra/SDG&E if confirmed during implementation).
- NEOGOV/governmentjobs.com adapter (County of SD, City of SD, SANDAG,
  Port of SD).
- SmartRecruiters adapter (ServiceNow).
- Workable adapter (SD County Regional Airport Authority).
- Sony Interactive Entertainment registration on the existing
  Greenhouse adapter.

### Out of Scope

- Bespoke adapters for unconfirmed-ATS employers (Qualcomm, Solar
  Turbines, Teradata, BAE, General Atomics, Intuit) — probe only if
  time allows; building one is future work.
- Any change to `ats_filters`' filtering logic itself, beyond what's
  needed to route the new adapters' output through it.
- Any of the other sprints' record shapes or extraction mechanisms —
  this sprint is self-contained and has no dependency on Sprints A-D.

## Test Strategy

Fixture-based tests for each new adapter (Workday, NEOGOV,
SmartRecruiters, Workable), following the existing per-adapter test
convention (saved API-response fixtures, no live network). A dry-run
check confirms each registered employer yields correctly-filtered,
correctly-typed Work-based Learning records before being wired into
the default run. Explicit test coverage for the zero-postings case
(an adapter that runs cleanly and yields nothing is a pass, not a
failure).

## Architecture

(To be sized and written at detail-planning time. Likely **compact** —
four adapters following an existing, well-established adapter pattern,
no new cross-module dependency or data-model change — but the
detail-planning sprint-planner should make its own sizing call once the
actual code shape is scoped.)

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

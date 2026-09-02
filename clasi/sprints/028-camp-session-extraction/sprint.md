---
id: 028
title: Camp session extraction
status: roadmap
branch: sprint/028-camp-session-extraction
use-cases: []
issues:
- 29-camp-session-extraction.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 028: Camp session extraction

## Goals

Make camps visible on the site — currently the category most families
search for first, and entirely absent, including our own partners'
camps (Fleet ran 27 topics over 10 weeks for 787 campers in 2025).
Deliver marketing-page session extraction for the ~10 verified
providers that publish full session dates and prices in plain HTML
(San Diego Zoo, Air & Space Museum, Living Coast, Coastal Roots Farm,
Elementary Institute of Science, SD Model Railroad Museum, Camp
Galileo SD, Camp Invention, CMOD, Helen Woodward, Southwestern College
Y.E.S., Birch via its newsroom page, Fleet's seasonal marketing page),
plus platform adapters in the issue's stated priority order:
`campscui.active.com` (ActiveNet), CampBrain, then the Pike13 API.

## Problem

Registration platforms mostly block bots, so camp session data — dates,
prices, availability — is largely invisible to the current pipeline.
Unlike the event calendars the pipeline already ingests, camp session
listings are marketing pages, not structured feeds; the ~10 verified
providers above are the exception, publishing plain HTML with dates and
prices scrapable today.

## Solution

Marketing-page extraction for the ~10 verified providers, reusing the
extraction ladder (`extract/`) and, where the LLM must recover
structured session fields (dates, price, sold-out flags) from prose,
the same LLM-extraction pattern Sprint A (027) builds for program
pages. Then platform adapters, built in the issue's stated order:
`campscui.active.com` first (covers Air & Space, Helen Woodward, likely
more), then CampBrain (Coastal Roots, Watersports Camp), then the
Pike13 API (developer.pike13.com — the League's own camps; the
cleanest API of any provider). Depends on the `Camps` opportunity_type,
already delivered by sprint 015's taxonomy work.

**Scope decision carried over from the stakeholder's issue text:**
institutional/nonprofit camps only. Commercial chains (Code Ninjas, iD
Tech, Galileo [the studio brand, not to be confused with "Camp Galileo
SD location page" above which is one of our verified nonprofit-adjacent
sources], Mathnasium, RSM) are competitors of the League's own classes
and are explicitly deferred — the issue itself flags this as an
unresolved stakeholder decision as of 2026-08-30. This sprint does not
plan any work toward them; the decision is simply noted here as
deferred, not re-litigated.

Sources still blocked by JS rendering (Gateway Galaxy webstores,
SeaWorld, YMCA Salesforce, Code Ninjas, Mad Science, Challenge Island
portal, RoboThink, iD Tech) need issue 23's browser path and are out of
scope for this sprint regardless of the commercial-chain question.

## Success Criteria

- All ~10 verified marketing-page providers yield camp session records
  with correct dates and prices, typed `Camps`.
- The `campscui.active.com`, CampBrain, and Pike13 adapters are built,
  in that order, and register at least the sources the issue names for
  each.
- A season-ahead view is possible: a camp registered this sprint whose
  registration opens later (e.g. Fleet, in-season-only marketing page)
  is scheduled for a seasonal re-check rather than silently stale.
- No commercial-chain camp is registered this sprint.
- Full hermetic test suite stays green, with fixture-based tests for
  the new adapters (no live network).

## Scope

### In Scope

- Marketing-page session extraction for the ~10 verified institutional/
  nonprofit providers named in issue 29.
- `campscui.active.com` adapter.
- CampBrain adapter.
- Pike13 API adapter.
- Seasonal re-check scheduling for in-season-only marketing pages
  (e.g. Fleet).

### Out of Scope

- Commercial camp chains (Code Ninjas, iD Tech, Galileo, Mathnasium,
  RSM) — open stakeholder decision, not made this sprint.
- JS-rendered/blocked platforms requiring issue 23's browser path
  (Gateway Galaxy, SeaWorld, YMCA Salesforce, Mad Science, Challenge
  Island, RoboThink) regardless of commercial-chain status.
- Any change to the `Opportunity`/taxonomy schema — sprint 015 already
  delivered the `Camps` type.

## Test Strategy

Fixture-based tests for each new adapter (`campscui.active.com`,
CampBrain, Pike13), following the existing per-adapter test convention
(saved page/API-response fixtures, no live network). Marketing-page
extraction tests use saved HTML fixtures for each of the ~10 verified
providers. A dry-run check confirms registered sources yield
correctly-dated, correctly-priced session records before being wired
into the default run.

## Architecture

(To be sized and written at detail-planning time. Likely **substantial**
given three new platform adapters plus a marketing-page extraction path
— but the detail-planning sprint-planner should make its own sizing
call once the actual code shape is scoped. Depends on Sprint 027 (the
program-page extraction mechanism) having landed if marketing-page LLM
extraction reuses that mechanism's shape.)

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

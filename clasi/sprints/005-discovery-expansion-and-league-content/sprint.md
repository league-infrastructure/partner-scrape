---
id: '005'
title: Discovery expansion and League content
status: roadmap
branch: sprint/005-discovery-expansion-and-league-content
worktree: false
use-cases: []
issues:
- 09-aggregator-as-discovery-not-source.md
- 12-league-content-and-advertising.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 005: Discovery expansion and League content

## Goals

Two threads: growing the source list, and wiring in the business model
that funds this whole project. A discovery crawl scans curated regional
hubs (Balboa Park calendar, county library systems, regional STEM
networks such as the Barrio Logan/Southeastern SD Cureo network,
university calendars) to surface organizations and events not yet
covered — then source-back acquisition registers each discovered org and
acquires from its own site/feed. We are the aggregator; other
aggregators are discovery leads only, never a data source to republish
(issue 09). Separately, League content and advertising (issue 12) wires
in the return on the League's investment: jointheleague.org registered as
a source so League events flow into the directory like any partner's,
and a League-owned sidebar ad slot on the site (cross-repo with
`stem-ecosystem`).

**Dependencies**: issue 09 depends on the Source Registry (sprint 001)
and the relevance gate (sprint 002/issue 04) — the gate is precisely what
makes ingesting noisy, discovery-sourced orgs safe rather than flooding
the site. Issue 12's League-source piece is a normal registry addition
(a lightweight case of 001/002's existing source-onboarding path); its
ad-slot piece is cross-repo work in `stem-ecosystem` and can proceed in
parallel with detail planning here.

## Problem

(What problem does this sprint address?)

## Solution

(High-level description of the approach.)

## Success Criteria

(How will we know the sprint succeeded?)

## Scope

### In Scope

- Discovery crawl over curated regional hubs to surface uncovered
  orgs/events; respects each hub's robots/ToS (issue 09).
- Source-back acquisition: register discovered orgs, fetch from their own
  site/feed, record "discovered via" provenance — never ingest a hub's
  own aggregated records as our data (issue 09).
- League (jointheleague.org) registered as a source; League events flow
  into the directory (issue 12).
- League-owned sidebar ad slot requirement, coordinated with the
  `stem-ecosystem` site repo (issue 12).

### Out of Scope

Detailed module/ticket breakdown is deferred to this sprint's detail
planning pass. Companies/internships (issue 11) is a later sprint.

## Test Strategy

(Describe the overall testing approach for this sprint: what types of tests,
what areas need coverage, any integration or system-level testing needed.)

## Architecture

(Architecture for this sprint's change, sized to the change — a
one-paragraph note for a trivial sprint, a fuller write-up with
component/data-model detail for a substantial one. May read "N/A —
trivial" when the change has no architectural impact.)

### Architecture Overview

(High-level structure and component relationships, if applicable.)

### Design Rationale

(Significant decisions with alternatives considered and reasoning, if
applicable.)

### Migration Concerns

(Data migration, backward compatibility, deployment sequencing — or
"None" if not applicable.)

## Use Cases

(Use cases sized to the change — may read "N/A — trivial" for small
sprints that don't warrant new or updated use cases.)

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

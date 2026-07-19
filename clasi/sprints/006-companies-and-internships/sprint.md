---
id: '006'
title: Companies and internships
status: roadmap
branch: sprint/006-companies-and-internships
worktree: false
use-cases: []
issues:
- 11-company-events-and-internships.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 006: Companies and internships

## Goals

Extend the aggregator beyond nonprofit/education partners to San Diego
STEM employers (issue 11): a curated seed list of ~50-100 companies
(sourced from SD Regional EDC, BIOCOM, CONNECT, anchor firms, Fleet
corporate sponsors — curated, not web-crawled); ATS adapters for
Greenhouse and Lever's public JSON board APIs, filtered to
internship/early-career + local + STEM roles; a new Internship
opportunity-kind with deadline/term-date semantics (application deadline,
"Summer 2027") rather than the event datetime model, likely its own site
section/filter; and opportunistic company public-events capture via the
generic extractor (open houses, career fairs, hackathons) — low yield,
not a place to over-invest. Career pathways are mission-aligned and
fundable (e.g. NBCUniversal's youth-pathways grant), strengthening both
the product and the case to keep the site alive.

**Dependencies**: depends on the Source Registry (sprint 001), the
relevance gate (sprint 002/issue 04), and a schema/kind extension to
Normalize & Export (sprint 001/issue 05's lineage) to support Internship
as a distinct opportunity kind with its own date semantics. Company
public-events capture reuses the generic extractor from sprint 002. This
is a parallel track to the partner-event work, not a blocking dependency
of any other sprint in this roadmap; sequencing vs. depth is explicitly a
stakeholder call per issue 11.

## Problem

(What problem does this sprint address?)

## Solution

(High-level description of the approach.)

## Success Criteria

(How will we know the sprint succeeded?)

## Scope

### In Scope

- Curated company seed list (~50-100 San Diego STEM employers).
- Greenhouse/Lever ATS adapters for public board APIs, filtered to
  internships/early-career + local + STEM.
- Internship opportunity-kind: deadline/term-date semantics, "apply" CTA,
  HS/college audience.
- Opportunistic company public-events capture via the generic extractor.

### Out of Scope

Detailed module/ticket breakdown is deferred to this sprint's detail
planning pass. Workday/iCIMS ATS integration is explicitly deferred per
issue 11 ("later").

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

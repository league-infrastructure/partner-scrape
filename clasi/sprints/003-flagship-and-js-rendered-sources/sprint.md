---
id: '003'
title: Flagship and JS-rendered sources
status: roadmap
branch: sprint/003-flagship-and-js-rendered-sources
worktree: false
use-cases: []
issues:
- 06-flagship-adapters-fleet-birch.md
- 10-js-rendered-site-support.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 003: Flagship and JS-rendered sources

## Goals

Close the two most visible source gaps and add a fetch path for
client-rendered sites. Build the Fleet Science Center adapter and the
Birch Aquarium / UCSD Localist API adapter (issue 06) — a Fleet-hosted
directory with zero Fleet events is the first thing the Fleet will
notice, and Localist also unlocks other UCSD/campus sources. Add a
headless-browser fetch strategy (issue 10), selectable per source in the
registry, for the ~9 known Wix-style sites whose mirrored HTML is
effectively empty, feeding the same generic extractor from sprint 002.

**Dependencies**: Birch is a straightforward Localist structured adapter.
Fleet's approach is not yet known — it may resolve via the generic
extractor (sprint 002) alone, or may require the headless fetch path
built in this same sprint; investigate fleetscience.org's actual
publishing mechanism first. Headless/JS support depends on the Fetch
layer (sprint 001) and generic extractor (sprint 002); issue 10 itself
flags it as lower priority, to land after the structured and sitemap
tiers are in place. High priority overall for the stakeholder demo; can
run in parallel with sprint 004's automation work.

## Problem

(What problem does this sprint address?)

## Solution

(High-level description of the approach.)

## Success Criteria

(How will we know the sprint succeeded?)

## Scope

### In Scope

- Fleet Science Center adapter, once its publishing mechanism (page
  structure, feed, or platform) is identified (issue 06).
- Birch Aquarium / UCSD Localist API adapter (issue 06).
- Headless-browser fetch strategy, selectable per source in the registry,
  for JS-rendered (Wix-style) sites (issue 10).
- Verify both flagship sources appear in exported opportunities.

### Out of Scope

Detailed module/ticket breakdown is deferred to this sprint's detail
planning pass. Automation (07), observability (08), discovery-as-leads
(09), companies/internships (11), and League content/advertising (12)
are later sprints.

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

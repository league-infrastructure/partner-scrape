---
id: '004'
title: Automation and observability
status: roadmap
branch: sprint/004-automation-and-observability
worktree: false
use-cases: []
issues:
- 07-self-updating-scheduled-loop.md
- 08-source-yield-observability.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 004: Automation and observability

## Goals

Make the engine run unattended, which is the core of the whole pitch. An
orchestrator runs adapters on a per-source cadence (frequent API pulls,
weekly sitemap diffs, monthly full mirror for API-less sites) with
failure isolation, so one broken source never empties the site or aborts
the run. The full scheduled loop — scrape → enrich → normalize → export →
site rebuild → deploy — runs with a visible "last updated" stamp and
automatic pruning of past events (issue 07), and a decision on the
automation home (GitHub Actions in this repo vs. the League's Docker
host, and how cross-repo publish is authenticated). Per-source yield
observability (issue 08) reports counts found/dated/new/dropped with
deltas per run, and flags zero-yield/cliff sources — cheap insurance
against the exact silent-breakage failure that let Fleet and Birch sit at
zero events unnoticed.

**Dependencies**: depends on Site Export (sprint 001) and needs sprints
002 and 003 actually producing data for the loop to be meaningful. Issue
08 explicitly depends on 07's orchestrator/run loop existing first to
report against, so within this sprint 07 is the foundation and 08 builds
on it. This sprint enables the "run clean unattended for a week or two,
then re-engage Fleet" plan.

## Problem

(What problem does this sprint address?)

## Solution

(High-level description of the approach.)

## Success Criteria

(How will we know the sprint succeeded?)

## Scope

### In Scope

- Orchestrator running adapters on per-source cadence with failure
  isolation (issue 07).
- Scheduled loop: scrape → enrich → normalize → export → site rebuild →
  deploy, with a "last updated" stamp and past-event pruning (issue 07).
- Decision on automation home and cross-repo publish authentication
  (issue 07).
- Per-run, per-source yield report with deltas vs. previous run, plus
  zero-yield/cliff alerts (issue 08).

### Out of Scope

Detailed module/ticket breakdown is deferred to this sprint's detail
planning pass. Discovery-as-leads (09), companies/internships (11), and
League content/advertising (12) are later sprints.

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

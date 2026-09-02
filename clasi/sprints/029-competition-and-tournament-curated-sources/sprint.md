---
id: 029
title: Competition and tournament curated sources
status: roadmap
branch: sprint/029-competition-and-tournament-curated-sources
use-cases: []
issues:
- 30-competition-sources-without-feeds.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 029: Competition and tournament curated sources

## Goals

Publish San Diego's static-page competition and tournament calendar —
the events beyond the feed-backed ones already covered (cafirst.org TEC
via issue 25, RobotEvents via issue 26). These are few, high-value, and
slow-changing (Science Olympiad, SDFTC league play, SeaPerch, MATHCOUNTS,
SD Math Circle, DOE National Science Bowl, Garibaldi Bowl, SD Brain Bee,
CyberPatriot/Cyber Cup, HS hackathons, Botball, Congressional App
Challenge, GSDSEF and the SD Festival of Science & Engineering / EXPO Day
dated entries, SDCEC's curated youth STEM event list) — a listing/
curated approach with annual review, not sitemap discovery.

## Problem

These competition sources have no feed or API; they live on static
pages that change slowly (once a year, around a fixed annual cycle).
Forcing them through the generic discovery/sitemap path would be
wasted machinery for content that a curated, annually-reviewed list
handles better.

## Solution

Reuse Sprint A's (027) curated-source-plus-LLM-date-extraction
mechanism, applied here to the static-page competition calendar rather
than program pages: either registry entries with `listing_html` and
generous extraction for pages with several events (e.g.
lovestemsd.org's per-event festival-week pages, sdmathcircle.org's
public Google Sheet), or a small curated-source file (org, URL,
expected month, last-verified) the pipeline re-checks annually and the
LLM extracts dates from for single-event pages. Depends on the
`Competitions` taxonomy value, already delivered by sprint 015. Also
registers SDCEC (sandiegoengineers.org/stem) as an org, using its
curated list as a discovery cross-check rather than a primary source.

This sprint is sequenced after Sprint A specifically because it reuses
Sprint A's extraction mechanism rather than building a new one.

## Success Criteria

- All named static-page competition sources are registered and yield
  dated `Competitions`-typed records with correct annual dates.
- GSDSEF and the SD Festival of Science & Engineering / EXPO Day dates
  surface correctly (explicit ask from the issue: "make sure these
  dates surface").
- SDCEC is registered as an org and its curated list is wired in as a
  cross-check.
- Full hermetic test suite stays green, with fixture-based tests for
  the new curated-source extraction.

## Scope

### In Scope

- Registry/curated-source entries for every static-page competition
  named in issue 30.
- Annual re-check scheduling for the curated-source file.
- SDCEC org registration and its list as a discovery cross-check.

### Out of Scope

- The already feed-backed competition sources (cafirst.org TEC, issue
  25; RobotEvents, issue 26) — unaffected, not revisited this sprint.
- Any change to the `Opportunity`/taxonomy schema — sprint 015 already
  delivered the `Competitions` type.
- Building a new extraction mechanism — this sprint reuses Sprint A's
  (027) curated-source + LLM date-extraction mechanism as-is.

## Test Strategy

Fixture-based tests for the curated-source loader and its LLM
date-extraction, reusing Sprint A's test pattern (saved page fixtures,
`FixtureLLMClient`, no live network). A dry-run/annual-review check
confirms each registered source yields the expected annual date before
being wired into the default run.

## Architecture

(To be sized and written at detail-planning time. Likely **compact** —
this sprint is explicitly scoped as reuse of Sprint A's mechanism
against new curated data, not a new pipeline stage — but the
detail-planning sprint-planner should make its own sizing call once the
actual code shape is scoped, and should revise upward if reuse turns
out to require real changes to Sprint A's mechanism.)

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

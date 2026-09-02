---
id: '033'
title: Audience and equity coverage
status: roadmap
branch: sprint/033-audience-and-equity-coverage
use-cases: []
issues:
- 34-audience-gaps-spanish-regional-accessibility.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 033: Audience and equity coverage

## Goals

Make the site's equity story ("particularly for underserved
communities") measurable and partly addressable: add a
bilingual/Spanish-available flag with export-time translation for
flagged records, add a sensory-friendly/accessibility flag plus a site
filter, and add per-region counts (South Bay, East County, etc.) to the
yield report / site meta so regional coverage regressions are visible
the same way per-source yield already is.

## Problem

South Bay has 8 records, East County has 0, nothing is in Spanish, and
accessibility programming (Fleet Accessibility Mornings, Nat ASD
Mornings, CMOD Sensory Friendly Mornings) is nearly absent — currently
only 1 of the county's 3 known accessibility offerings surfaces. None of
this is visible today because nothing measures it — there's no
regional-count metric analogous to per-source yield, and no flag
scheme for bilingual or accessibility content. This sprint is
sequenced last of the content sprints because it measures and flags
records the earlier sprints (A-F) produce; measuring before that
content exists would show a permanently-empty baseline.

## Solution

- **Bilingual/Spanish flag**: add a `bilingual` flag to the record
  schema, backed by known hooks (CMOD's already-captured "Bilingual"
  events, SHPE's Noche de Ciencias, Fleet's San Ysidro STEM Fair), plus
  export-time LLM translation of flagged records' descriptions to
  Spanish (cheap, reusing the existing `enrich/llm_client.py` pattern).
- **Accessibility flag**: add a sensory-friendly/accessibility flag,
  ensure all three known offerings (Fleet Accessibility Mornings, Nat
  ASD Mornings, CMOD Sensory Friendly Mornings) are flagged and
  surfacing, and add a corresponding site filter.
- **Regional yield measurement**: add a per-region count to
  `observability/`'s existing yield report and to site meta, following
  the same per-source yield-accounting precedent already established
  there — this is additive instrumentation, not a new reporting
  subsystem.

**Explicitly out of scope, an unresolved stakeholder decision**: whether
to list El Trompo (the Tijuana children's science museum) as a
binational entry. Not decided as of the issue's 2026-08-30 writing;
this sprint does not resolve it and plans no work toward it. Casa de
Amistad, MAAC, and BLCI partner outreach for program data, and the
unresolved tribal-youth/military-family/foster-youth programming gaps,
are recorded as open but not actioned this sprint — they depend on
outreach outcomes outside this project's control.

## Success Criteria

- Records carry a `bilingual` flag and flagged records get a translated
  Spanish description at export time.
- Records carry a sensory-friendly/accessibility flag; all three known
  accessibility offerings (Fleet, the Nat, CMOD) surface with it set,
  and a site filter exists for it.
- The yield report and site meta carry a per-region count, so a
  regional-coverage regression (e.g. East County dropping back to 0)
  would be visible the same way a per-source yield drop is today.
- El Trompo is not listed; no work is done toward the binational
  listing decision.
- Full hermetic test suite stays green.

## Scope

### In Scope

- `bilingual` flag on the record schema + export-time Spanish
  translation for flagged records.
- Sensory-friendly/accessibility flag + site filter.
- Per-region count in the yield report and site meta.
- Verifying and, if needed, fixing why 2 of 3 known accessibility
  offerings aren't currently surfacing.

### Out of Scope

- El Trompo / binational listing — unresolved stakeholder decision, not
  made this sprint.
- Casa de Amistad, MAAC, BLCI partner outreach for program data —
  depends on outreach outcomes, not engineering work.
- Tribal youth programming, Navy/military-family K-12 STEM, and foster
  youth programming — recorded as open gaps, not actioned; no scrapable
  source was found for any of them as of the issue's research.
- Any new source registration to actually fill the South Bay/East
  County regional gap — most of that arrives via other issues/sprints
  per the issue's own text (County Parks ICS, Tijuana Estuary, Chula
  Vista library, EAA Young Eagles, VEX/Sweetwater, Eastlake FLL,
  Mission Trails, Mount Laguna, Wolf Center, Botball at West Hills);
  this sprint adds the *measurement*, not new regional sources.

## Test Strategy

Unit tests for the new flags' schema fields and the export-time
translation call (via a fixture LLM client, no live network). Tests for
the per-region yield-counting logic, following `observability/`'s
existing per-source yield-accounting test pattern. A verification check
that all three known accessibility offerings surface with the flag set
correctly.

## Architecture

(To be sized and written at detail-planning time. Likely **compact** —
additive flags on the existing schema plus additive instrumentation on
an existing reporting module, no new module or cross-module dependency
— but the detail-planning sprint-planner should make its own sizing
call, particularly around whether export-time translation introduces a
new dependency edge worth diagramming.)

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

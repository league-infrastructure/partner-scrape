---
id: '010'
title: Discovery surfaces
status: roadmap
branch: sprint/010-discovery-surfaces
use-cases: []
issues:
- 16-llms-txt-and-agent-discovery-pages.md
- 17-partner-event-publishing-strategy.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 010: Discovery surfaces

## Goals

Make the data sprint 009 publishes easy for both machines and partner
organizations to find and use — two connected discovery surfaces, both
depending on sprint 009's export having landed first.

1. **`llms.txt` and agent discovery pages** (issue 16). Add a
   well-known discovery layer so an LLM/agent landing on the site can
   find the published `partners.json` / per-partner `events.json` /
   past-events files (issue 15, sprint 009) without guessing: an
   `llms.txt` at the site root pointing straight at the data files, a
   human-and-agent-readable "how to consume our data" page documenting
   shape and the "given `partners.json` + a partner's event files you
   can fully reconstruct the site" contract, and a page authored
   specifically for LLM consumption that `llms.txt` links to.
2. **Multi-pronged event-publishing strategy for partners** (issue 17).
   Publish a human- and LLM-readable page telling a partner how to make
   their events easy for the scraper to ingest, offering several
   standard publishing methods a partner can pick from — ordered
   easiest-adoption first: a `.well-known` discovery pointer file (A),
   sitemap + schema.org `Event` JSON-LD (B), an already-supported iCal
   feed (C, pure documentation — the `ical` adapter already ingests
   these), OpenActive as a stretch goal (D), and our own documented JSON
   in the issue-15 schema as a universal fallback (E). Every method
   harmonizes with the existing Adapter framework
   (`partner_scrape/adapters/`) rather than inventing a bespoke
   pipeline, and everything ingested this way lands in sprint 009's
   append-only per-partner store.

Sequencing rationale: issue 17 states explicitly that it builds on issue
16 (the page `llms.txt` points at) and on issue 15's schema (the fields
a published event must carry) — both discovery-surface issues therefore
depend on sprint 009's export landing first, which is why this sprint
follows it. Within this sprint, 16 (the discovery entry points) and 17
(the partner-facing publishing page) are two halves of one surface: 16's
`llms.txt` / LLM page must link to 17's page once it exists, and 17's
page is written for the same agent audience 16's discovery layer
targets — the two are sequenced/reviewed together rather than treated as
fully independent.

Note for detail planning: `docs/design/design.md` (plus per-subsystem
`DESIGN.md`) is being bootstrapped concurrently and `design_docs` is now
`enabled`. This sprint's issue 17 work touches `partner_scrape/adapters/`
(a likely-documented subsystem, if a new JSON-LD extraction rung or a
new `.well-known`/schema-JSON adapter is added) — expect a `design/`
overlay at detail-planning time; no overlay is created now.

## Scope

### In Scope

- `site/public/llms.txt` (or the site's equivalent public root) pointing
  at sprint 009's published data files (issue 16).
- A human/agent-readable "how to consume our data" page documenting the
  export shape and reconstruction contract (issue 16).
- A dedicated LLM-consumption page, linked from `llms.txt` (issue 16).
- A published page documenting the event schema and the A–E
  publishing-method menu for partners (issue 17), prioritizing B
  (schema.org JSON-LD) and C (iCal) per issue 17's own proposed
  first-build order, with A (`.well-known` pointer) to tie discovery
  together.
- Wiring `llms.txt` / the LLM page to link to the future
  publication-workflow page once issue 17's page exists (issue 16's
  explicit scope).

### Out of Scope

- D (OpenActive/RPDE) and E (our-schema JSON fallback) as
  fully-built adapters — issue 17 proposes these as later/stretch work,
  not first-build scope; this sprint may document them on the page
  without shipping the adapters.
- The separate future issue covering how the publication *workflow*
  itself works (the mechanism a partner or agent follows to actually
  publish/consume) — issue 16 only requires linking to that page once it
  exists, not building it now.
- Any change to sprint 009's export shape or storage model — this sprint
  consumes that contract as given; if a mismatch surfaces, it is a
  cross-sprint exception, not silent scope creep here.
- Robot teams work (issue `robot-teams-...`) — entirely independent,
  sprint 011.

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

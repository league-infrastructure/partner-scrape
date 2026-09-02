---
id: '027'
title: 'Program-page extraction: HS internships and research programs'
status: executing
branch: sprint/027-program-page-extraction-hs-internships-and-research-programs
use-cases:
- SUC-031
- SUC-032
- SUC-033
- SUC-034
- SUC-035
issues:
- 28-hs-internship-program-page-extractor.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 027: Program-page extraction: HS internships and research programs

## Goals

Build a reusable **curated-program-page extraction** mechanism: fetch a
registered program page, LLM-extract {program name, audience/grades,
date range, application window/deadline, paid/cost, eligibility,
open/closed status}, and emit deadline-first records that bypass the
recurring-collapse and event-dedup logic built for calendar events (the
same way internships already do). Use it to deliver the site's first
HS-internship and research-program content: the UCSD Summer Program
Finder as a listing source, the SIO research-internships table, and the
~15 individual named program pages cataloged in issue 28 (Salk, SDSC
REHS, Sanford Burnham SPARK, LJI, Scripps SRTI/REACH, UCSD
OPTIMUS/ENLACE/COSMOS, NIWC SEAP/NREIP, NOAA Hutton, SDZWA fellowships,
SDSU ExpandAI, Illumina/SD2, Biocom, SD Foundation Community
Scholarship).

This sprint is deliberately foundational: sprints C (competitions) and
D (educator PD pages) both name this same extraction mechanism as
something they reuse rather than rebuild, so it must land first.

## Problem

The site publishes zero internships. Sprint 006's ATS-adapter bet
missed the target — San Diego's high-value HS programs are paid summer
research placements published as prose program pages on lab and
university sites, not through any ATS. Deadlines cluster Dec-Mar for
Jun-Aug programs, so a record shape that isn't deadline-first
(open/closed status, application window) misrepresents them. Nothing in
the current pipeline extracts dated application-window semantics from a
curated, non-calendar page; `enrich/`'s LLM layer today recovers fields
from already-adapter-extracted events, it doesn't drive fetch+extract
for a whole page from scratch against a bespoke schema.

## Solution

Add a program-page extraction path: a curated registry of program page
URLs (mirroring the existing `registry/sources/*.toml` pattern), a
fetch step reusing `fetch/`'s `PoliteFetcher`/`PlaywrightFetcher`, and a
new LLM extraction call (reusing `enrich/llm_client.py`'s structured
JSON-schema pattern) that returns the program-page-specific field set
rather than the existing `Event` recovery fields. Extracted records are
tagged `kind='internship'`/`'program'`, bypass the relevance gate as
curated/trusted, and route around `normalize/`'s recurring-collapse and
event-dedup stages — following the precedent already set for
internships in the schema (issue 15's taxonomy/schema extension).
Records for closed application windows are either withheld or rendered
as "opens ~X", per the source page's own stated cycle.

Taxonomy support (Camps/Competitions/deadlines/eligibility fields)
already landed in sprint 015 — this sprint builds the extraction
mechanism on top of that schema, it does not redesign the schema.

## Success Criteria

- The UCSD Summer Program Finder and SIO research-internships table are
  registered as program-page listing sources and yield HS-eligible
  program records with correct application windows.
- At least the majority of the ~15 named individual program pages in
  issue 28 are registered and yield a program record with deadline-first
  fields (open/closed status, date range, eligibility).
- The San Diego Foundation Community Scholarship is registered as a
  `Funding Opportunities`-typed record.
- Extracted program records do not get silently collapsed or
  deduplicated by the calendar-event logic (`normalize/`'s recurring
  collapse and dedup stages).
- Full hermetic test suite stays green, with new fixture-based tests
  for the program-page extractor (no live network/LLM calls).

## Scope

### In Scope

- New program-page curated registry pattern and fetch/extract/LLM
  pipeline stage for program pages.
- UCSD Summer Program Finder listing source.
- SIO research-internships table source.
- The named individual program pages cataloged in issue 28.
- San Diego Foundation Community Scholarship registration.
- Routing program records around recurring-collapse/dedup; deadline-first
  display semantics (closed-window handling).

### Out of Scope

- ATS adapters (Workday, NEOGOV, SmartRecruiters, Workable — issue 31,
  Sprint E).
- Competition/tournament curated sources (issue 30, Sprint C) — reuses
  this sprint's mechanism but is planned separately.
- Educator PD program pages (issue 33 part 1, Sprint D) — reuses this
  sprint's mechanism but is planned separately.
- Any change to the `Opportunity`/taxonomy schema itself — sprint 015
  already delivered that; this sprint only consumes it.

## Test Strategy

Fixture-based tests for the new program-page fetch/extract/LLM stage,
following this codebase's existing adapter-test convention (saved page
fixtures, `FixtureLLMClient`, no live network). Registry-loader parsing
tests for the new curated-source TOML shape. A dry-run verification
that registered pages actually produce correctly-shaped program records
before being wired into the default run, matching sprint 014/016's
precedent for new source registration.

## Architecture

### Revision (2026-09-02 — ticket 006 exception cycle)

Ticket 006's own required live-verification found that `ProgramListingAdapter.
discover()`'s sole discovery signal (`EVENT_PATH_RE` path-pattern matching) fits neither
of this sprint's two headline listing sources' real markup — UCSD's HS-eligible cards
link cross-domain with no `/program(s)?`-shaped path, and SIO's page is not a
cards-to-detail-pages listing at all, but one page whose programs are inline sections.
The exception was thrown `surface: user-visible`; the team-lead reclassified it
`internal` before dispatching this revision, since the gap is entirely inside
`ProgramListingAdapter.discover()`'s implementation strategy, not a renegotiation of
SUC-032's Main Flow (which never specifies *how* a card link is identified). Full
finding, reclassification rationale, and the resulting design — a configurable
`config.link_selector` discovery strategy alongside `EVENT_PATH_RE`, and a new
`program_page_multi` adapter type for one-page/N-record extraction, both designed for
reuse by sprints 029/030 — are recorded in `design/adapters-DESIGN.md`'s own Revision
note (canonical source: `adapters/DESIGN.md`). This revision also newly seeds and edits
`design/discovery-DESIGN.md` (not part of this sprint's original affected-doc list),
since the new `discover_via_selector` function lives in `discovery/listing.py`; and adds
a small addendum to `design/registry-DESIGN.md` for the new `adapter_type` value and
`config.link_selector` key. `design/design.md`'s adapter-count line is refreshed from
thirteen to fourteen. See the replacement tickets (008, and rewritten 006) in this
sprint's `## Tickets` table below.

### Original sizing decision (unchanged)

**Substantial** — this sprint introduces a new adapter family (two new
`adapter_type`s: `program_page`, `program_listing`) with its own LLM
extraction client and cache (a new cross-module capability inside
`adapters/`, never previously needed there), touches 4+ modules with
real code changes (`model.py`, `adapters/`, `enrich/enricher.py`,
`normalize/run.py`), and generalizes an existing kind-based bypass
mechanism that two later sprints (029 competitions, 030 educator
programs) are explicitly expected to reuse. This clears the substantial
bar on module count and new-cross-module-dependency grounds alone.

Because this project has opted into the persistent per-subsystem design
doc set (`design_docs: enabled`), the full architecture write-up lives
in this sprint's `design/` overlay (`clasi/sprints/027-.../design/`),
not in this section — see `architecture-authoring`'s Mode 2a. Affected
canonical docs, each carrying a "Sprint 027" addition describing its
change in full:

- `docs/design/design.md` — subsystem-map adapter-count refresh (11 → 13
  adapter types); no pipeline-diagram or subsystem-boundary change.
- `partner_scrape/DESIGN.md` (root) — `Event.eligibility` field,
  `PROGRAM_EXTRACTION_KINDS` shared constant.
- `partner_scrape/adapters/DESIGN.md` — the new `program_page`/
  `program_listing` adapter family, its LLM client and cache, and the
  constructor-injection deviation from "adapters hold no instance
  state."
- `partner_scrape/enrich/DESIGN.md` — bypass generalized from
  `kind == "internship"` to `kind in PROGRAM_EXTRACTION_KINDS`.
- `partner_scrape/normalize/DESIGN.md` — collapse/dedup bypass and
  deadline-first availability generalized the same way;
  `DEADLINE_FIRST_TYPES` gains `"Funding Opportunities"`; `eligibility`
  resolution gains an Event-level source alongside the existing
  `taxonomy_defaults` one.
- `partner_scrape/registry/DESIGN.md` — the new adapter_type values as
  ordinary registry data, no registry code change.

### Architecture Overview

See the `design/` overlay's edited copies (above) for the full 7-step
write-up: responsibilities, module boundaries, the component diagram,
and the dependency-graph note.

### Design Rationale

See the `design/` overlay's edited copies for the full Decision /
Context / Alternatives / Consequences entries — most notably: kind
routing (`internship` vs `program`) as the mechanism's discriminator
rather than `opportunity_type`; the constructor-injection deviation for
LLM-client/cache testability; and closed-window handling via `Event.
start`/`Event.end` reuse (no `Opportunity` schema change).

### Migration Concerns

See the `design/` overlay's edited copies. Summary: additive only — no
existing source, adapter, or `Opportunity` consumer changes behavior
except the two named, precedented extensions (`DEADLINE_FIRST_TYPES`
gains one member; the kind-based bypass set gains one member), both
scoped to this sprint's own new curated records.

## Use Cases

### SUC-031: Extract a curated individual program page into a deadline-first record
Parent: UC-011 (Discover STEM company events and internships)

- **Actor**: Pipeline, on behalf of a registered `program_page` source.
- **Preconditions**: A source TOML registers one program page URL with
  `adapter_type = "program_page"` and a `program_kind` of `"internship"`
  or `"program"`.
- **Main Flow**:
  1. `ProgramPageAdapter.discover()` returns the one configured URL as
     an `EventRef`.
  2. `ProgramPageAdapter.fetch()` retrieves it via the injected
     `Fetcher` (`acquisition_kwargs`, matching every other adapter).
  3. `ProgramPageAdapter.extract()` checks the program-extraction cache
     by URL+content-hash; on a miss, calls the injected
     `ProgramLLMClient` with the page body, asking for {program name,
     audience/grades, date range, application window/deadline,
     paid/cost, eligibility, open/closed status}.
  4. The result is mapped onto a canonical `Event` (`kind="internship"`
     or `"program"` per the source's `program_kind`; `start`/`end` as
     the application window open/deadline; `eligibility` set via
     `Event.set(...)`).
- **Postconditions**: One `Event` per registered page, carrying
  deadline-first fields with real provenance/confidence.
- **Acceptance Criteria**:
  - [ ] A `FixtureProgramLLMClient` test proves the mapping from a
        canned extraction result to `Event` fields, including
        `eligibility` and `opportunity_type` (for `program_kind =
        "program"`).
  - [ ] A cache-hit test proves an unchanged page's second run makes no
        `ProgramLLMClient` call.
  - [ ] A non-200 fetch is logged and skipped, not raised.

### SUC-032: A program-listing source yields one record per eligible card
Parent: UC-011

- **Actor**: Pipeline, on behalf of a registered `program_listing`
  source (UCSD Summer Program Finder, SIO research-internships table).
- **Preconditions**: A source TOML sets `adapter_type =
  "program_listing"` with `listing_urls`/`site_url` (matching
  `listing_html`'s existing config shape).
- **Main Flow**:
  1. `ProgramListingAdapter.discover()` crawls the listing page(s) and
     returns one `EventRef` per matched card/detail link (reusing or
     extending `discovery.listing.discover_via_listing`'s pattern).
  2. Each ref is fetched and extracted exactly as SUC-031's single-page
     flow — one LLM extraction call per discovered program.
- **Postconditions**: One `Event` per listing-page program card, each
  independently carrying its own audience/grade/deadline/eligibility —
  not one blended record for the whole listing.
- **Acceptance Criteria**:
  - [ ] A fixture listing page with N cards yields N distinct `Event`s.
  - [ ] A card whose target page fails to fetch/extract is skipped
        (logged), not fatal to the other cards.
  - [ ] The reconciliation between this sprint's listing-sourced
        programs and its individually-registered named pages (Open
        Question: avoiding duplicate publication for a program named in
        both, e.g. COSMOS/OPTIMUS/ENLACE) is resolved and recorded
        before both are registered live.

### SUC-033: Program/internship records bypass collapse, dedup, and LLM enrichment
Parent: SUC-005 (sprint 006's `kind="internship"` relevance-gate bypass,
generalized)

- **Actor**: `normalize.run()` and `enrich.enricher.LLMEnricher`.
- **Preconditions**: An `Event.kind` is `"internship"` or `"program"`.
- **Main Flow**:
  1. `LLMEnricher.enrich()`'s pass-1 bypass check widens from `kind ==
     "internship"` to `kind in PROGRAM_EXTRACTION_KINDS` — no cache
     lookup, no LLM call, no field mutation, no gate re-judgment, for
     either kind.
  2. `normalize.run()`'s internship/other split widens the same way,
     routing both kinds around `collapse_recurring`/`dedup_cross_source`
     into their own 1:1 `Instance`s.
- **Postconditions**: A `program`-kind `Event` gets exactly the same
  bypass treatment `internship`-kind already has — the reuse surface
  sprints 029/030 build on.
- **Acceptance Criteria**:
  - [ ] A fixture `kind="program"` Event proves zero `LLMClient` calls
        through `LLMEnricher.enrich()`.
  - [ ] A fixture pair of same-title `kind="program"` Events from
        different sources both survive `normalize.run()` as separate
        `Opportunity` records (no cross-source collapse).
  - [ ] Every existing `kind="internship"` fixture test continues to
        pass unmodified (pure generalization, no behavior change for
        the existing case).

### SUC-034: A program record's availability and currency reflect its application-window state
Parent: SUC-008 (sprint 015 ticket 007's deadline-first currency/sort/
availability, generalized)

- **Actor**: `normalize.run()` / `export.writer.export_opportunities()`.
- **Preconditions**: A `program`/`internship`-kind `Event` carries
  `start` (application window opens) and/or `end` (deadline).
- **Main Flow**:
  1. If `end` is set and in the past, the record is excluded from
     export (`is_current_or_upcoming()`'s existing `DEADLINE_FIRST_TYPES`
     rule — unchanged, now reachable by this sprint's own records once
     their `opportunity_type` is a member).
  2. If `start` is set and in the future, `availability` reads "Opens
     ~<date>" instead of "Apply by <date>".
  3. Otherwise, the existing "Apply by <date>" / "Rolling — apply
     anytime" derivation applies unchanged.
- **Postconditions**: A closed application window never ships; a
  not-yet-open one displays an honest "Opens ~" note instead of being
  silently hidden or shown as immediately actionable.
- **Acceptance Criteria**:
  - [ ] A fixture record with a past `end` is excluded from export.
  - [ ] A fixture record with a future `start` and no/future `end`
        renders "Opens ~<date>".
  - [ ] Every existing `Work-based Learning`/`Competitions` availability
        fixture continues to pass unmodified.

### SUC-035: The SD Foundation Community Scholarship ships as a Funding Opportunities record
Parent: UC-011

- **Actor**: Pipeline, on behalf of the SD Foundation Community
  Scholarship's registered `program_page` source.
- **Preconditions**: The source's `program_kind = "program"` and its
  extraction/config sets `opportunity_type = "Funding Opportunities"`.
- **Main Flow**:
  1. SUC-031's extraction flow runs, producing a `kind="program"` Event
     with `opportunity_type` set via `Event.set(...)`.
  2. `DEADLINE_FIRST_TYPES` (now including `"Funding Opportunities"`)
     applies the deadline-first currency/sort/availability rule to it.
- **Postconditions**: The scholarship displays as a `Funding
  Opportunities`-typed, deadline-first record, demonstrating the
  mechanism's non-internship path end to end.
- **Acceptance Criteria**:
  - [ ] A fixture test proves a `Funding Opportunities`-typed,
        `kind="program"` record with a future deadline exports and
        sorts by `date_end`.
  - [ ] The same record with a past deadline is excluded.

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
| 001 | Generalize the curated-program-kind bypass mechanism | — |
| 002 | Build the program-page LLM extraction client and cache | — |
| 003 | Build the ProgramPageAdapter for individually-registered program pages | 001, 002 |
| 004 | Build the ProgramListingAdapter for program-listing sources | 002, 003 |
| 005 | Register the individual HS internship and research program pages | 003 |
| 008 | Add selector-based listing discovery and multi-record page extraction to the program-page mechanism | 002, 004 |
| 006 | Register the UCSD Summer Program Finder and SIO listing sources | 005, 008 |
| 007 | Register the SD Foundation Community Scholarship as a Funding Opportunities record | 001, 003 |

Tickets execute in the order listed (not strictly by ticket number —
008 was created after 006 during ticket 006's exception-revision cycle,
but must execute before the rewritten 006, which now depends on it).
001 and 002 have no dependency on each other and could execute in
either order (or in parallel, if this sprint opts into parallel
worktrees) before 003. 007 has no dependency on 006/008 and could
execute at any point after 003.

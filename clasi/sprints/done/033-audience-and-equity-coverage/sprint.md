---
id: '033'
title: Audience and equity coverage
status: done
branch: sprint/033-audience-and-equity-coverage
use-cases:
- SUC-063
- SUC-064
- SUC-065
issues:
- 34-audience-gaps-spanish-regional-accessibility.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 033: Audience and equity coverage

## Goals

Make the site's equity story ("particularly for underserved
communities") measurable and partly addressable: surface a
bilingual/Spanish-available signal and a sensory-friendly/accessibility
signal for known offerings, and add per-region counts (South Bay, East
County, etc.) to the yield report / site meta so regional coverage
regressions are visible the same way per-source yield already is.

**Revised at detail-planning time** (see Architecture, below, for the
full reasoning): the bilingual/accessibility signals turned out not to
need a new `bilingual` field or new schema at all — the site's own
`Opportunity.specific_attention` field already carries exactly these
values in its documented vocabulary and has simply never been
populated. This sprint populates it. Export-time LLM translation is
deferred to a follow-up issue (see Design Rationale) rather than built
this sprint.

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

- **Bilingual/Spanish and accessibility signals**: derive both from
  existing record text/tags (CMOD's already-captured "Bilingual"
  category, SHPE's Noche de Ciencias, Fleet's San Ysidro STEM Fair,
  "Sensory Friendly"/"Accessibility Mornings"/"ASD Mornings" title
  keywords) into the site schema's own already-defined but never-
  populated `Opportunity.specific_attention` field (`"Programs in
  Spanish"`, `"Programs for students with disabilities"`) — not a new
  field, not a schema change. `stem-ecosystem`'s card/calendar
  components already wire this field into the DOM
  (`data-attention={opp.specific_attention?.join(',')}`); whether that
  wiring already renders a usable filter, or needs `stem-ecosystem`-side
  UI work, is that repo's own follow-up to verify.
- **Accessibility offering coverage**: ensure all three known offerings
  (Fleet Accessibility Mornings, the Nat's ASD Mornings, CMOD Sensory
  Friendly Mornings) are actually reachable by the pipeline and flagged
  — registering the Nat as a new source is the most likely fix (no
  `registry/sources/*.toml` entry found for it as of planning).
- **Regional yield measurement**: add a per-region count to
  `observability/`'s existing yield report and to `scrape-meta.json`,
  following the same per-source yield-accounting precedent already
  established there — this is additive instrumentation, not a new
  reporting subsystem. Requires one new internal (non-site-schema)
  field, `Opportunity.region`, treated like the existing `sources`
  bookkeeping field.
- **Deferred, not built this sprint**: LLM translation of flagged
  records' Spanish descriptions (issue 34 item b) — see Design
  Rationale for why. El Trompo / binational listing (issue 34 item c)
  remains an unresolved stakeholder decision, unactioned.

**Explicitly out of scope, an unresolved stakeholder decision**: whether
to list El Trompo (the Tijuana children's science museum) as a
binational entry. Not decided as of the issue's 2026-08-30 writing;
this sprint does not resolve it and plans no work toward it. Casa de
Amistad, MAAC, and BLCI partner outreach for program data, and the
unresolved tribal-youth/military-family/foster-youth programming gaps,
are recorded as open but not actioned this sprint — they depend on
outreach outcomes outside this project's control.

## Success Criteria

- Bilingual/Spanish-flagged records (CMOD Bilingual, SHPE Noche de
  Ciencias, Fleet San Ysidro STEM Fair) export with `"Programs in
  Spanish"` in `specific_attention`.
- All three known accessibility offerings (Fleet, the Nat, CMOD)
  surface and export with `"Programs for students with disabilities"`
  in `specific_attention`.
- The yield report and `scrape-meta.json` carry a per-region count, so
  a regional-coverage regression (e.g. East County dropping back to 0)
  would be visible the same way a per-source yield drop is today.
- El Trompo is not listed; no work is done toward the binational
  listing decision.
- Full hermetic test suite stays green; no `PROMPT_VERSION` bump.

## Scope

### In Scope

- Deriving `specific_attention` (bilingual/Spanish and accessibility
  values) from existing record text/tags — populating an existing,
  already-exported site-schema field, not adding one.
- One new internal (non-site-schema) `Opportunity.region` field plus a
  per-region count in the yield report and `scrape-meta.json`.
- Verifying and, if needed, fixing why 2 of 3 known accessibility
  offerings aren't currently surfacing (most likely: registering the
  Nat as a new source).

### Out of Scope

- LLM translation of flagged records' descriptions (issue 34 item b) —
  deferred to a follow-up issue; see Design Rationale.
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
- Any `stem-ecosystem`-side UI work (a `specific_attention` filter
  control, surfacing `scrape-meta.json`'s regional counts) — this
  repo's job ends at the data, matching sprint 030's precedent for
  `offerings.json`.

## Test Strategy

Unit tests for the new `derive_specific_attention`/`derive_region`
keyword rules in `normalize/taxonomy.py` (hermetic, no network/LLM —
both are deterministic text derivations, not LLM calls). Tests for the
per-region yield-counting logic, following `observability/`'s existing
per-source yield-accounting test pattern, plus a `scrape-meta.json`
`"regions"` key test. A verification check (ticket 003) that all three
known accessibility offerings surface with the flag set correctly.

## Architecture

**Substantial.** Sized up from the roadmap's tentative "compact" guess
after detail investigation found: (1) a genuine data-model addition —
`Opportunity` gains an internal `region` bookkeeping field (not part of
the site schema, same treatment as the existing `sources` field), and
(2) 4+ modules touched (`normalize/taxonomy.py`, `normalize/run.py`,
`observability/yield_report.py` + `reporter.py`/`render.py`/
`snapshot.py`, `export/writer.py`, plus a registry data addition). Both
are explicit substantial-tier triggers per the sizing rubric. The full
write-up (and full self-review) lives in this sprint's `design/`
overlay (`Project.design_docs_opt_in` is `True`) — see
`clasi/sprints/033-audience-and-equity-coverage/design/`:
`design.md`, `DESIGN.md` (root), `normalize-DESIGN.md`,
`observability-DESIGN.md`, `export-DESIGN.md`. This section
summarizes; the overlay is the authoritative content.

**Key discovery that reshapes scope**: the site's own data contract
already defines `Opportunity.specific_attention: string[]`
("Values like `Programs for boys`, `Programs for girls`, `Programs for
students with disabilities`, `Programs in Spanish`, etc.") — a stub
that every record has always exported as `[]` (sprint 015 ticket 008
left it, along with `financial_support`/`ngss_aligned`/contact fields,
an explicitly unread hardcoded stub). `stem-ecosystem`'s
`OpportunityCard.astro`/`CalendarView.astro` already wire
`data-attention={opp.specific_attention?.join(',')}` into the DOM.
Both "Spanish/bilingual" and "students with disabilities" are already
named values in the schema's own documented vocabulary. So: the
bilingual and accessibility flags this sprint needs are **not** a new
field or a new cross-repo contract change — they are populating an
already-shipped, already-wired stub with real values, via a new
deterministic keyword-derivation function in `normalize/taxonomy.py`
(the same "text in, tags out" pattern `derive_areas_of_interest`
already uses). No `Event` field, no `Opportunity` schema change, no
new dependency edge for this half of the sprint.

**A component diagram is omitted** — one sentence, per the sizing
rubric's escape hatch: every new derivation (`specific_attention`,
`region`) flows through Opportunity-list edges (`normalize/run.py` →
`observability/`, `normalize/run.py` → `export/`) that already exist
and are unchanged in direction or presence; nothing new is composed,
only one new attribute flows through each existing edge, matching
sprint 014's and sprint 020's own no-diagram precedent for a
same-shape, no-new-composition change.

**Translation (issue 34 item b) is explicitly deferred to a follow-up
issue, not built this sprint.** See Design Rationale in the overlay
and this section's own note below — the two ways to build it either
force a `PROMPT_VERSION` bump (full-corpus re-enrichment cost) for a
field only a handful of records use, or require new, separately-cached
LLM-call infrastructure outside the existing `EnrichmentResult`
schema. Both are real scope, not a one-line addition, and deserve their
own ticket rather than riding along with a measurement-focused sprint.

**El Trompo (binational listing)** is explicitly out of scope per
issue 34's own framing — an unresolved stakeholder decision, not
addressed by any ticket this sprint.

**PROMPT_VERSION**: **not bumped this sprint.** Nothing in this
sprint's design touches `EnrichmentResult`'s schema, the LLM system
prompt, or any LLM call at all — `specific_attention` and `region` are
both deterministic keyword/text derivations in `normalize/taxonomy.py`,
computed at normalize time, not enrichment time. No forced
re-enrichment, no LLM cost.

### Architecture Overview

See `design/design.md`'s "Sprint 033 addition" note (system level) and
`design/normalize-DESIGN.md`/`design/observability-DESIGN.md`/
`design/export-DESIGN.md`'s own sprint 033 sections for the full
module-by-module design. Summary:

- `normalize/taxonomy.py` gains two pure derivation functions:
  `derive_specific_attention(text) -> list[str]` (keyword rules against
  the existing `build_taxonomy_text()` blob, values `"Programs in
  Spanish"` and `"Programs for students with disabilities"` from the
  site's own already-documented vocabulary) and `derive_region(location)
  -> str` (a new, internal-only San Diego sub-region vocabulary: South
  Bay, East County, North County Coastal, North County Inland, Central
  San Diego, or `""` for unclassified — city-keyword matching against
  `Opportunity`'s already-resolved `location` text, ordered
  specific-before-generic, same convention as
  `OPPORTUNITY_TYPE_KEYWORDS`).
- `normalize/run.py`'s `_to_opportunity()` calls both: replaces the
  `specific_attention=[]` stub with the derived list, and adds one new
  internal `Opportunity.region: str = ""` field (excluded from
  `SITE_SCHEMA_FIELDS`, the same "internal bookkeeping, not part of the
  site schema" treatment already given to `sources`).
- `observability/yield_report.py` adds per-region counting
  (`RegionYield`, mirroring `SourceYield`'s found/previous/delta/
  zero-count shape but keyed by region instead of source, computed from
  the final `Opportunity` list's `.region` attribute via `getattr` —
  no new import, preserving the module's stated "never imports
  `normalize.run.Opportunity`" decoupling). `YieldReport` gains a
  `.regions` list; `snapshot.py` persists region counts under one
  reserved top-level key (`"__regions__"`, collision-safe against real
  `source_id`s) so next run can compute a delta; `render.py` gains a
  "Regional coverage" section.
- `export/writer.py`'s `export_opportunities()` computes the same
  per-region tally from the exported (current/upcoming) payload and
  adds a `"regions"` key to `scrape-meta.json` — an additive key on an
  existing cross-repo file (see Migration Concerns).
- `registry/sources/`: a data-only addition/fix for whichever of the
  three known accessibility offerings (Fleet Accessibility Mornings,
  the Nat's ASD Mornings, CMOD Sensory Friendly Mornings) is not
  currently surfacing — likely registering the Nat as a new source
  (not currently in `registry/sources/`) and/or verifying Fleet's
  `/events` listing actually links its 3rd-Saturday Accessibility
  Mornings page. No new adapter code — "onboarding an organization is
  a new TOML file," the existing convention.

### Design Rationale

See the overlay docs' own Design Rationale entries (`normalize-DESIGN.md`
for the `specific_attention`-reuse and `region`-as-internal-field
decisions; `observability-DESIGN.md` for `RegionYield`'s shape choice;
`export-DESIGN.md` for the `scrape-meta.json` addition). This section
records the one decision made here, at the sprint level rather than in
a single subsystem doc: **defer translation (issue 34 item b) to a
follow-up issue.**

- **Decision**: Do not implement LLM translation of flagged records'
  descriptions this sprint.
- **Context**: Issue 34 frames this as "cheap" ("LLM translation at
  export is cheap"). It is cheap in isolation (the affected record
  count is small — a handful of CMOD/SHPE/Fleet records) but not free
  to build correctly.
- **Alternatives considered**: (a) Add a `description_es` field to
  `EnrichmentResult` and request it on every enrichment call — rejected:
  this changes `EnrichmentResult`'s schema, which forces a
  `PROMPT_VERSION` bump and a full-corpus re-enrichment (sprint 015's
  precedent) for a value only a handful of flagged records would ever
  use — the overwhelming majority of the corpus would pay the
  re-enrichment cost for a field it never populates. (b) Call
  translation from `export/writer.py` at export time, per issue 34's
  literal framing — rejected: this would be `export/`'s first-ever
  dependency on an LLM client, contradicting `export/DESIGN.md`'s
  stated "`export/` re-derives nothing... its inputs arrive finished
  from `normalize/`" constraint, and would need its own new,
  separately-cached call path (translation-at-export has no natural
  cache-invalidation hook the way enrichment's content-hash cache
  does). (c) A separate, `bilingual`-gated LLM call inside
  `enrich/enricher.py`, outside `EnrichmentResult`'s schema, with its
  own small cache — technically the correct shape, but real new
  infrastructure (a second LLM-call path, a second cache), not a
  one-line addition to a sprint whose stated purpose is measurement
  over already-produced records.
- **Why this choice**: Every real option is either expensive in a way
  the issue's "cheap" framing understates (a), a boundary violation (b),
  or new infrastructure deserving its own scoped ticket (c). Given the
  hermetic-test constraint (no live LLM calls in tests) and this
  sprint's own framing ("adds flags and measurement over records the
  pipeline already produces," not new LLM infrastructure), (c) is the
  right design but the wrong sprint.
- **Consequences**: Spanish-language descriptions for
  bilingual-flagged records are not available this sprint; only the
  `"Programs in Spanish"` flag itself ships. A follow-up issue should
  scope option (c) explicitly, sized on its own rather than folded in
  here.

### Migration Concerns

- **`scrape-meta.json` gains a `"regions"` key.** Additive, not a
  breaking change — an existing consumer reading only `last_updated`
  is unaffected. Per this sprint's brief: this repo's job ends at
  publishing the count; any `stem-ecosystem` UI that surfaces it is
  that repo's own follow-up, exactly as sprint 030 concluded for
  `offerings.json`.
- **`opportunities.json`'s `specific_attention` field changes from
  always-`[]` to sometimes-populated.** This is a content change, not
  a schema/shape change — the field has been part of the exported
  contract since sprint 015. Any `stem-ecosystem` code that already
  reads `specific_attention` (`OpportunityCard.astro`,
  `CalendarView.astro` already wire `data-attention`) starts receiving
  real values with no contract change on either side. Whether that
  wiring already renders a working filter or needs `stem-ecosystem`-side
  UI work to expose one is that repo's own follow-up to verify — not
  re-solved here.
- **No `PROMPT_VERSION` bump, no forced re-enrichment.** See the
  Architecture summary above.
- **`yield-history.json`'s snapshot shape gains one reserved top-level
  key (`"__regions__"`).** An old snapshot file with no such key reads
  as "no previous region baseline" — the same, already-tested
  first-run behavior every per-source entry gets when absent, so this
  is non-breaking for an in-flight snapshot file.

## Use Cases

### SUC-063: A record's bilingual/Spanish or accessibility signal surfaces as a `specific_attention` tag
Parent: UC-005 (Normalize a record into the site opportunity schema)

- **Actor**: Pipeline, on behalf of any registered source whose event
  text carries a bilingual/Spanish or accessibility signal (e.g. CMOD's
  "Bilingual" category tag or "Sensory Friendly Mornings" title, SHPE's
  "Noche de Ciencias", Fleet's "San Ysidro STEM Fair" or "Accessibility
  Mornings", the Nat's "ASD Mornings").
- **Preconditions**: An `Event` survives normalization with a title/
  description/categories/tags blob carrying one of the known keyword
  signals.
- **Main Flow**:
  1. `normalize/run.py`'s `_to_opportunity()` builds the same
     `build_taxonomy_text()` blob already used for `areas_of_interest`.
  2. `taxonomy.derive_specific_attention(text)` matches it against a
     keyword rule set and returns zero or more of the site's own
     documented vocabulary values (`"Programs in Spanish"`, `"Programs
     for students with disabilities"`).
  3. The result replaces the previous hardcoded `specific_attention=[]`
     stub.
- **Postconditions**: A bilingual or accessibility-flagged record
  exports with a non-empty `specific_attention` list; every other
  record is unaffected (empty list, unchanged from today).
- **Acceptance Criteria**:
  - [ ] CMOD's "Bilingual"-tagged events export with `"Programs in
        Spanish"` in `specific_attention`.
  - [ ] SHPE's Noche de Ciencias and Fleet's San Ysidro STEM Fair
        export with `"Programs in Spanish"`.
  - [ ] Fleet Accessibility Mornings, the Nat's ASD Mornings, and
        CMOD's Sensory Friendly Mornings each export with `"Programs
        for students with disabilities"`.
  - [ ] A record matching neither keyword set exports
        `specific_attention=[]`, unchanged from today.
  - [ ] No `Event` or `Opportunity` schema field is added for this use
        case — the existing `specific_attention` field is populated,
        not extended.

### SUC-064: Per-region opportunity counts are visible in the yield report and site meta
Parent: UC-007 (Run the scheduled self-updating loop)

- **Actor**: Operator, via the console yield report and
  `scrape-meta.json`.
- **Preconditions**: A run completes normalization; the previous run's
  `yield-history.json` snapshot may or may not carry a prior region
  baseline.
- **Main Flow**:
  1. `normalize/run.py` classifies each `Opportunity`'s `region` from
     its resolved `location` text via `taxonomy.derive_region()`.
  2. `observability/yield_report.py` tallies the final exported
     opportunity list by region into `RegionYield` entries (count,
     previous count, delta), the same shape `SourceYield` already
     provides per source.
  3. `render.py`'s console output gains a "Regional coverage" section.
  4. `export/writer.py` computes the same tally over the
     current/upcoming payload and writes it into `scrape-meta.json`'s
     new `"regions"` key.
  5. `snapshot.py` persists this run's region counts for the next
     run's delta.
- **Postconditions**: An operator (or a future automated check) can see
  South Bay/East County/etc. counts and whether they moved, the same
  way per-source yield is already visible — a regression (e.g. East
  County dropping back to 0) is observable without a manual count.
- **Acceptance Criteria**:
  - [ ] The console yield report shows a per-region count for every
        classified region.
  - [ ] `scrape-meta.json` carries a `"regions"` object with the same
        counts.
  - [ ] A record whose `location` matches no known city keyword
        classifies as unknown (`""`/uncategorized), not silently
        dropped from any region's count and not force-fit into a wrong
        bucket.
  - [ ] Re-running with an unchanged corpus reproduces the same counts
        (deterministic classification).
  - [ ] `observability/yield_report.py` gains no new import — region
        counting reads `.region` via `getattr`, matching the existing
        `.sources`/`.slug` duck-typing convention.

### SUC-065: The county's three known accessibility offerings all surface
Parent: UC-009 (Fix the flagship-source gaps)

- **Actor**: Operator/Engine.
- **Preconditions**: Fleet Accessibility Mornings (3rd Saturday), the
  Nat's ASD Mornings, and CMOD Sensory Friendly Mornings are real,
  recurring, publicly listed offerings; as of issue 34's 2026-08-30
  writing only 1 of 3 surfaces in the pipeline's output.
- **Main Flow**:
  1. For each of the three, confirm whether its source is registered
     (`registry/sources/`) and, if registered, whether the specific
     recurring event/page is actually reachable by that source's
     adapter (discovery/listing coverage, not just "the org has a
     source").
  2. Register or fix whichever is missing — most likely the Nat (no
     `registry/sources/*.toml` entry found for it as of this sprint's
     planning) and/or Fleet's `/events` listing discovery.
  3. Verify all three export with `specific_attention` containing
     `"Programs for students with disabilities"` (SUC-063).
- **Postconditions**: All three known accessibility offerings surface
  in the pipeline's output, flagged.
- **Acceptance Criteria**:
  - [ ] Fleet Accessibility Mornings surfaces.
  - [ ] The Nat's ASD Mornings surfaces (registering the Nat as a new
        source if that is why it currently does not).
  - [ ] CMOD Sensory Friendly Mornings continues to surface (verify,
        do not regress).
  - [ ] Whichever fix was needed is documented in the ticket's Notes
        (which of the three was broken, and why).

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
| 001 | Derive specific_attention and region on Opportunity | — |
| 002 | Per-region yield measurement in observability and scrape-meta.json | 001 |
| 003 | Fix accessibility offering coverage (Fleet, the Nat, CMOD) | 001 |

Tickets execute serially in the order listed. 002 and 003 both depend only
on 001 (not on each other) and could run in parallel if the sprint's
execution mode opts into parallel worktrees; serial execution in listed
order is the default and is correctness-safe either way.

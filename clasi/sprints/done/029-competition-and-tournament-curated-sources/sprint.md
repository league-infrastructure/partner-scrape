---
id: 029
title: Competition and tournament curated sources
status: done
branch: sprint/029-competition-and-tournament-curated-sources
use-cases:
- SUC-044
- SUC-045
- SUC-046
- SUC-047
- SUC-048
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

Reuse Sprint A's (027/028) `program_page`/`program_page_multi`/
`program_listing` LLM-extraction mechanism verbatim, applied here to the
static-page competition calendar rather than program pages —
see the Architecture section below for the mechanism decision (this
supersedes the two either/or options — a `listing_html` extension, or a
standalone curated-source file — this section originally sketched at
roadmap time, before sprint 027/028 had shipped the generalized
mechanism both options would otherwise have duplicated). Depends on the
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

- Registry entries (reusing the `program_page`/`program_page_multi`/
  `program_listing` mechanism) for every static-page competition named
  in issue 30.
- SDCEC org registration and its list as a discovery cross-check.

### Out of Scope

- The already feed-backed competition sources (cafirst.org TEC, issue
  25; RobotEvents, issue 26) — unaffected, not revisited this sprint.
- Any change to the `Opportunity`/taxonomy schema — sprint 015 already
  delivered the `Competitions` type.
- Building a new extraction mechanism — this sprint reuses Sprint A's
  (027) curated-source + LLM date-extraction mechanism as-is.

## Test Strategy

Fixture-based tests for the new registry entries' LLM date-extraction,
reusing sprint 027/028's test pattern exactly (saved page fixtures,
`FixtureProgramLLMClient`, no live network). Registry-loader parsing
tests for each new source file. Live-verification (a dry-run check)
confirms each registered source yields the expected dated record before
being wired into the default run — the "annual review" issue 30 asks
for is served by this existing live-verification step plus the existing
weekly scheduled run, not a new mechanism (see Architecture > Design
Rationale).

## Architecture

**Compact** — this sprint reuses sprint 027/028's `program_page`/
`program_page_multi`/`program_listing` mechanism verbatim: every change
is a new `registry/sources/*.toml` file (or, for GSDSEF, possibly a
config edit to its *existing* file) plus, where the page is
single-purpose, an operator-curated `config.opportunity_type =
"Competitions"` override — the identical pattern the SD Foundation
Scholarship's `"Funding Opportunities"` and the camp sources' `"Camps"`
overrides already established. No new adapter code, no new
cross-module dependency (`registry/` already flows into `adapters/`
unchanged), no dependency-direction change, and no `Opportunity`/
`Event` schema change — this clears the compact bar on every count and
sits below it on module count (zero *code* modules touched; `registry/`
gains data, not code). The real design work this sprint does is the
mechanism decision itself (below) and the discipline of not
double-registering the two sources that are already partners (GSDSEF,
SD Festival of Science & Engineering) — see Design Rationale.

Because this project has opted into the persistent per-subsystem design
doc set (`design_docs: enabled`), the write-up lives in this sprint's
`design/` overlay (`clasi/sprints/029-competition-and-tournament-curated-sources/design/`),
not in this section — see `architecture-authoring`'s Mode 2a, and
sprints 027/028's `sprint.md` for the precedent this follows. The
affected canonical docs (updated by the 2026-09-02 revision below):

- `partner_scrape/registry/DESIGN.md` (overlay:
  `design/registry-DESIGN.md`) — a "Sprint 029" addendum documenting
  the new competition/tournament source registrations (every one reusing
  an already-shipped `adapter_type` value), the SDCEC org-plus-hub
  coexistence, and the mechanism decision below.
- `partner_scrape/adapters/DESIGN.md` (overlay:
  `design/adapters-DESIGN.md`) — added by the 2026-09-02 revision below;
  documents the corrected competition-genre extraction mechanism (a
  `profile`-selected LLM prompt variant, a new `registration_deadline`
  field, and a `ProgramExtractionCache` schema-version bump), not part
  of this sprint's original scope.

**Revision (2026-09-02 — competition-genre extraction fix, team-lead
escalation).** This sprint's original premise — reuse sprint 027/028's
`program_page`/`program_page_multi`/`program_listing` mechanism
*verbatim*, zero new code — did not survive tickets 001/002's own
required live-verification step: of 13 sources registered, only 3
shipped a usable record, and most of the rest failed on real extraction,
not a site block. The root cause (`adapters/program_llm.py`'s prompt
written for sprint 027's application-window *program* genre, wrong for
single-dated-event *competitions*), the corrected mechanism, and the
full Design Rationale (including why `normalize/run.py`'s
`DEADLINE_FIRST_TYPES` is deliberately left unchanged) live in
`adapters/DESIGN.md`'s own "Revision (2026-09-02 — sprint 029
competition-genre extraction fix)" section — read that, not a
restatement here. This revision's own tier, judged in isolation, is
**substantial** (3 `adapters/` modules touched: `program_llm.py`'s
prompt/schema, `program_page.py`'s profile-selection call sites,
`program_cache.py`'s version bump; a real cross-module design decision
on whether to touch `normalize/run.py`) — it was self-reviewed against
the full five-category standard and passed (see the sprint's recorded
`architecture_review` gate history), even though the sprint's *original*
registry-only scope remains correctly sized Compact. Tickets 006 (the
fix) and 007 (live re-verification) implement it — see this sprint's
Tickets table.

### Architecture Overview

See the `design/` overlay's edited copy for the full write-up: the
mechanism decision, the alternatives rejected and why, and the
per-source `adapter_type` assignment (`program_page` for single-event
pages, `program_page_multi` for one page/sheet holding N inline dated
items, `program_listing` for a listing whose cards link to N detail
pages).

### Design Rationale

See the `design/` overlay's edited copy for the full Decision / Context
/ Alternatives / Consequences entries — most notably: choosing
`program_page`/`program_page_multi`/`program_listing` reuse over either
of issue 30's own two proposed mechanisms (a generic `listing_html`
extension, or a hand-rolled standalone curated-source file); no new
annual-review/recheck subsystem (reusing sprint 028's identical "the
existing weekly cron already re-checks every enabled source" reasoning,
applied here to an annual rather than a seasonal cadence); and the
GSDSEF/SD Festival dual-registration discipline, mirroring the sprint
027 COSMOS/OPTIMUS/ENLACE and sprint 028 Air & Space/Helen Woodward
precedents.

### Migration Concerns

See the `design/` overlay's edited copy. Summary: additive only — no
existing source, adapter, or `Opportunity` consumer changes behavior.
GSDSEF's existing registration may gain a config edit (not a new file)
if live verification finds its judging/public-day dates are not
surfacing today; that is the one possible edit to a pre-existing file
this sprint makes, and it is a data edit, not a code change.
`registry/hubs/sdcec-stem.toml` (SDCEC's existing discovery-only hub,
sprint 024) is read but not modified.

## Use Cases

### SUC-044: A single-event competition/tournament page yields a dated Competitions-typed record
Parent: UC-011 (Discover STEM company events and internships (extension))

- **Actor**: Pipeline, on behalf of a registered single-event
  `program_page` competition source.
- **Preconditions**: A source TOML registers one competition/tournament
  page with `adapter_type = "program_page"`, `config.program_kind =
  "program"`, and `config.opportunity_type = "Competitions"`.
- **Main Flow**: Identical to sprint 027's SUC-031 — `ProgramPageAdapter.
  discover()`/`fetch()`/`extract()` call the existing `ProgramLLMClient`
  and map the result onto an `Event` via the existing
  `_map_result_to_event`, with `opportunity_type` forced to
  `"Competitions"` by the config override.
- **Postconditions**: One `Event` per registered competition page,
  dated and typed `Competitions`, with zero new mapping code.
- **Acceptance Criteria**:
  - [x] Each of San Diego Regional Science Olympiad, SDFTC league play,
        SeaPerch San Diego Regional, MATHCOUNTS SD chapter, DOE National
        Science Bowl SD regionals, Garibaldi Bowl, San Diego Brain Bee,
        Botball Greater SD, Congressional App Challenge, TritonHacks,
        and CipherHacks is either registered `enabled = true` and
        live-verified to yield a correctly-dated `Competitions` record,
        or registered `enabled = false` with a reason comment (sprint
        027/028 precedent) if blocked. **(ticket 007, 2026-09-02)**
        Re-verified against the corrected extraction mechanism:
        `doe-science-bowl-sd`, `congressional-app-challenge-sd`,
        `cipherhacks` (from tickets 001/001b), plus `sd-brain-bee`,
        `seaperch-sd-regional`, `tritonhacks` (newly fixed by ticket
        006, re-enabled by ticket 007) are `enabled = true` and
        live-verified. `sd-science-olympiad`, `garibaldi-bowl`,
        `mathcounts-sd-chapter` (unrelated fetch/WAF blocks, unchanged),
        `sdftc-league-play`, and `botball-greater-sd` (re-verified
        post-fix by ticket 007; still no calendar date reaches the
        model at all -- a fetch/content-availability gap distinct from
        the framing bug ticket 006 fixed) stay `enabled = false` with an
        evidenced reason comment. Note: `tritonhacks`' correctly-dated
        record (2026-05-16/17) is itself an already-past annual cycle
        relative to this ticket's 2026-09-02 verification date -- a
        correct extraction of a not-yet-updated page, dropped from
        export by the existing, unrelated currency filter, not an
        extraction failure.
  - [x] CyberPatriot SD / SoCal Mayor's Cyber Cup is registered
        `enabled = false` with a reason comment referencing issue 38
        (the headless-fetcher settle-wait gap `ndia-sd.org`'s
        JS-rendering needs), not silently omitted.
  - [x] A `FixtureProgramLLMClient` test proves at least one of these
        sources' pages maps to a correctly-dated, `Competitions`-typed
        `Event` via the existing `_extract_one_program` mapping.
        (`tests/test_adapters_program_page.py`'s
        `TestCompetitionSourceExtraction`/
        `TestCompetitionRegistrationDeadlineSeparation`.)

### SUC-045: San Diego Math Circle's public calendar sheet yields its distinct annual dates as separate records
Parent: UC-011

- **Actor**: Pipeline, on behalf of San Diego Math Circle's registered
  `program_page_multi` source.
- **Preconditions**: `sdmathcircle.org`'s public master-calendar Google
  Sheet is fetchable (its export URL registered as `config.url`);
  `adapter_type = "program_page_multi"`.
- **Main Flow**: `ProgramPageMultiAdapter.extract()` runs the fetched
  sheet export through `extract.reduce_html_to_text()` before caching/
  the LLM call, same as every other `program_page_multi` source
  (`reduce_html_to_text()` is an `lxml.html`-based parser, tolerant of
  non-HTML input — it does not raise on plain CSV/text, returning it
  largely intact modulo whitespace collapse; ticket-level live
  verification confirms the sheet's actual export format parses
  cleanly, per this SUC's Acceptance Criteria), then calls
  `extract_programs()`, which identifies each distinct dated item (AMC,
  AIME, ARML, Math Kangaroo, and Saturday session dates) and maps each
  to its own `Event` via the existing per-result mapping.
- **Postconditions**: San Diego Math Circle's distinct annual dated
  competitions/sessions each publish as their own record, never blended
  into one.
- **Acceptance Criteria**:
  - [ ] Live-verified: the registered sheet export URL is fetchable and
        yields at least the AMC/AIME/ARML/Math Kangaroo dated items as
        distinct records.
  - [ ] A fixture test with a saved sheet export proves N distinct dated
        `Event`s via `FixtureProgramLLMClient.list_responses`.
  - [ ] If the sheet is not cleanly fetchable at ticket time, the source
        is registered `enabled = false` with a reason comment instead of
        silently dropped.

### SUC-046: The SD Festival of Science & Engineering's festival-week program yields one record per per-event detail page
Parent: UC-011

- **Actor**: Pipeline, on behalf of the SD Festival of Science &
  Engineering / EXPO Day's registered `program_listing` source.
- **Preconditions**: `lovestemsd.org`'s DB-driven per-event festival-week
  pages (~35 events) are discoverable from a listing page;
  `adapter_type = "program_listing"`, with `config.link_selector` set if
  live verification finds `EVENT_PATH_RE` doesn't match the listing's
  card markup (the ticket 006/008 precedent this sprint reuses, not
  rebuilds).
- **Main Flow**: `ProgramListingAdapter.discover()` resolves each
  festival-week event's detail page; each is fetched and extracted
  independently via `_extract_one_program`. No `opportunity_type`
  override is set — festival-week events span more than one type
  (workshops, the EXPO Day showcase, competitions), so each record's
  type is the LLM's own per-page classification, the same "leave it to
  the LLM" default `program_page`/`program_listing` already use when no
  config override is present.
- **Postconditions**: The festival week's dated events, including EXPO
  Day, each publish as their own independently-typed record.
- **Acceptance Criteria**:
  - [ ] Live-verified: discovery yields at least one detail-page
        `EventRef` per festival-week event (using `link_selector` if
        `EVENT_PATH_RE` does not match).
  - [ ] A fixture test with a saved listing page plus N saved detail
        pages proves N distinct dated `Event`s.
  - [ ] The Mar 7 2026 EXPO Day / Petco Park date specifically surfaces
        as one of the extracted records.
  - [ ] `registry/sources/usasciencefestival.toml` (the unrelated,
        already-disabled national USA Science & Engineering Festival
        registration) is left untouched, confirming this is a different
        organization and not a dual registration.

### SUC-047: SDCEC ships as a registered org whose curated list also serves as a cross-check
Parent: UC-011

- **Actor**: Pipeline/operator, on behalf of SDCEC's new registered
  source.
- **Preconditions**: `registry/hubs/sdcec-stem.toml` already exists as a
  discovery-only hub (sprint 024); this sprint adds
  `registry/sources/sdcec.toml` (`adapter_type = "program_page_multi"`
  against the same `/stem` page), with no `opportunity_type` override so
  each curated item classifies independently, the same choice SUC-046
  makes for the same reason.
- **Main Flow**:
  1. SDCEC's `/stem` page is registered as a `program_page_multi`
     source, extracting its hand-curated youth STEM list (including the
     Feb 20 2026 Engineers Week awards) into N independently-typed
     `Event`s.
  2. The existing hub entry is left unchanged — per
     `registry/DESIGN.md`'s hub/source physical-separation invariant, a
     hub-plus-source pair for the *same* org is a different, already-
     supported catalog relationship, not the same-org-registered-twice-
     within-`sources/` risk sprints 027/028 warn about.
  3. SDCEC's curated list is cross-checked against this sprint's other
     new registrations for accidental overlap (the same failure mode
     sprint 027's COSMOS/OPTIMUS/ENLACE Open Question names) before both
     go live.
- **Postconditions**: SDCEC ships as a registered org; its curated list
  both publishes its own events and continues serving as an
  operator-visible discovery cross-check via the unaffected hub.
- **Acceptance Criteria**:
  - [ ] `registry/sources/sdcec.toml` is registered, live-verified, and
        yields at least the Engineers Week awards as a dated record.
  - [ ] `registry/hubs/sdcec-stem.toml` is unmodified.
  - [ ] Any item in SDCEC's curated list that duplicates an org this (or
        a prior) sprint already registers elsewhere is identified and
        reconciled, not silently double-published — recorded in the
        ticket's notes even if no conflict is found.

### SUC-048: GSDSEF's existing registration surfaces its judging and public-day dates without a second registration
Parent: UC-011

- **Actor**: Operator/pipeline, on behalf of GSDSEF's existing
  registered source.
- **Preconditions**: `registry/sources/gsdsef.toml` already exists
  (`generic_html`, `enabled = true`, headless fetch strategy).
- **Main Flow**:
  1. Live-verify whether the existing registration's extraction
     (`extract/`'s deterministic ladder plus `enrich/`'s LLM
     field-recovery pass) already surfaces the Mar 18 2026 judging date
     and the Mar 21 2026 public day date.
  2. If both dates already surface correctly, no change is made.
  3. If not, the *existing* `gsdsef.toml`'s config is edited (e.g.
     `site_url` pointed at the specific page carrying these dates, or
     — if that alone is insufficient — its `adapter_type` changed to
     `program_page`/`program_page_multi`) — a data edit to the existing
     file, never a second registration.
- **Postconditions**: GSDSEF's Mar 18/21 dates surface on the site
  through exactly one registration.
- **Acceptance Criteria**:
  - [ ] A live check records whether the two dates surface today.
  - [ ] If a config edit is needed, it is made to the existing
        `gsdsef.toml` file — no new `registry/sources/` file for GSDSEF.
  - [ ] Exactly one `registry/sources/` entry exists for GSDSEF before
        and after this ticket.

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

| # | Title | Depends On | Issue |
|---|-------|------------|-------|
| 001 | Register single-event program_page competition sources | — | 30 |
| 002 | Register San Diego Math Circle's public calendar sheet as a program_page_multi source | — | 30 |
| 006 | Fix competition-genre extraction: date-vs-deadline framing, year inference, registration deadline field | — | 30 |
| 007 | Re-verify and re-enable competition sources under the corrected extraction mechanism | 006 | 30 |
| 003 | Register the SD Festival of Science & Engineering / EXPO Day as a program_listing source | — | 30 |
| 004 | Register SDCEC as a source org alongside its existing discovery hub | 001, 002, 003 | 30 |
| 005 | Verify GSDSEF's existing registration surfaces its judging and public-day dates | — | 30 |

Tickets execute serially in the order listed above (superseding the
original 001-005 ordering below this paragraph, kept for its still-true
reasoning about 003/004/005's mutual independence).

**(2026-09-02 revision)** Tickets 001/002's real live-verification found
that most of the batch's registered sources' extraction was
systematically wrong — not the "reuse verbatim, zero new code" premise
this sprint's original Architecture assumed — traced to
`adapters/program_llm.py`'s prompt being written for sprint 027's
application-window *program* genre, not for single-dated-event
*competitions*. See `adapters/DESIGN.md`'s "Revision (2026-09-02 —
sprint 029 competition-genre extraction fix)" section and this sprint's
`design/adapters-DESIGN.md` overlay for the full finding and the
corrected mechanism. Tickets 006 (the fix) and 007 (live re-verification
of the five sources ticket 001 disabled for a genuine extraction
failure — `sdftc-league-play`, `botball-greater-sd`, `sd-brain-bee`,
`seaperch-sd-regional`, `tritonhacks`) are inserted between 002 and 003,
ahead of the remaining original tickets, since 007 needs 006's fix (and
its cache-schema-version bump) in place first. `sd-math-circle` and
`mathcounts-sd-chapter` are explicitly **not** re-verified by ticket
007 — the former is a distinct, deferred grid-extraction problem
(`adapters/DESIGN.md`'s Design Rationale), the latter a fetch-level WAF
block unrelated to extraction framing; both stay `enabled = false`.
Tickets 003, 004, and 005's own scope is **unchanged** by this revision
— 004's `depends-on` still reads `001, 002, 003` (not `006`/`007`; SDCEC's
overlap cross-check does not need the extraction fix), and 005 uses an
entirely different pipeline (`generic_html` + `enrich/`, not
`program_llm.py`) so this revision does not touch it at all. Ticket 003
gets a non-scope-changing forward-reference note (see its own file)
flagging that its festival-week source deliberately sets no
`config.opportunity_type` override, so this fix's profile selection does
not reach it — if its own live verification hits the same
deadline-vs-event-date framing bug, the documented fallback is
`adapters/DESIGN.md`'s matching Open Question, not a fresh investigation.

Original ordering rationale (001, 002, 003, and 005 have no hard
dependency on each other — each is an independent batch of registry data
reusing an already-shipped `adapter_type` (`program_page`,
`program_page_multi`, `program_listing`, and a config-only edit to an
existing file, respectively) — and could execute in any order, or in
parallel if this sprint opts into parallel worktrees. 004 depends on
001-003 because SDCEC's curated-list cross-check needs this sprint's
other new registrations to exist first, to check for overlap) still
holds for 003/004/005 among themselves; it is superseded only in that
006/007 are now inserted into the overall serial order as shown in the
table above.

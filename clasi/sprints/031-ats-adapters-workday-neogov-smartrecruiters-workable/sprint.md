---
id: '031'
title: 'ATS adapters: Workday, NEOGOV, SmartRecruiters, Workable'
status: executing
branch: sprint/031-ats-adapters-workday-neogov-smartrecruiters-workable
use-cases:
- SUC-054
- SUC-055
- SUC-056
- SUC-057
- SUC-058
- SUC-059
- SUC-060
issues:
- 31-ats-adapters-workday-neogov-smartrecruiters.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 031: ATS adapters: Workday, NEOGOV, SmartRecruiters, Workable

## Goals

Add college/early-career internship coverage for the career-pathway
story via four new ATS adapters: Workday (Northrop Grumman including
its HS Internship Program req, Cubic, Illumina, Dexcom, likely ResMed
and Sempra/SDG&E), NEOGOV/governmentjobs.com (County of SD, City of SD,
SANDAG, Port of SD as one adapter, four agencies), SmartRecruiters
(ServiceNow), and Workable (SD County Regional Airport Authority).
Also register Sony Interactive Entertainment against the existing
Greenhouse adapter.

## Problem

The site has no college/early-career internship coverage from major
San Diego employers' applicant-tracking systems. Each ATS vendor has
its own API/scraping shape (Workday needs browser-like headers via
POST to `/wday/cxs/{tenant}/{site}/jobs`; NEOGOV is one shape across
four agency instances; SmartRecruiters and Workable both expose public
JSON). This is self-contained work, independent of the record-shape and
extraction-mechanism work in Sprints A-D.

## Solution

Build four adapters in the order named, reusing the existing
`ats_filters` (internship + STEM + San Diego filtering) and the routing
convention already established for the existing greenhouse/lever
adapters (Work-based Learning type). Add Sony Interactive Entertainment
(board `sonyinteractiveentertainmentglobal`, verified 200) to the
existing Greenhouse adapter's registered boards as a small additive
registration alongside the new adapter work. Probe, but do not build
bespoke adapters for, the unconfirmed-ATS employers (Qualcomm,
Solar Turbines, Teradata, BAE, General Atomics, Intuit) — if a probe
finds a clean shape, that is future work, not this sprint's.
Expect long stretches of zero matching postings from any given
adapter — internship reqs are seasonal and rare relative to total
postings — that is signal, not error, matching this codebase's existing
tolerance for source-level sparsity.

## Success Criteria

- Workday, NEOGOV, SmartRecruiters, and Workable adapters are built, in
  that order, and each registers at least the employer(s) named above.
- Sony Interactive Entertainment is registered against the existing
  Greenhouse adapter.
- All four new adapters route matching postings as Work-based Learning,
  filtered through `ats_filters`.
- Full hermetic test suite stays green, with fixture-based tests for
  each new adapter (no live network).

## Scope

### In Scope

- Workday adapter (Northrop Grumman, Cubic, Illumina, Dexcom; ResMed
  and Sempra/SDG&E if confirmed during implementation).
- NEOGOV/governmentjobs.com adapter (County of SD, City of SD, SANDAG,
  Port of SD).
- SmartRecruiters adapter (ServiceNow).
- Workable adapter (SD County Regional Airport Authority).
- Sony Interactive Entertainment registration on the existing
  Greenhouse adapter.

### Out of Scope

- Bespoke adapters for unconfirmed-ATS employers (Qualcomm, Solar
  Turbines, Teradata, BAE, General Atomics, Intuit) — probe only if
  time allows; building one is future work.
- Any change to `ats_filters`' filtering logic itself, beyond what's
  needed to route the new adapters' output through it.
- Any of the other sprints' record shapes or extraction mechanisms —
  this sprint is self-contained and has no dependency on Sprints A-D.

## Test Strategy

Fixture-based tests for each new adapter (Workday, NEOGOV,
SmartRecruiters, Workable), following the existing per-adapter test
convention (saved API-response fixtures, no live network). A dry-run
check confirms each registered employer yields correctly-filtered,
correctly-typed Work-based Learning records before being wired into
the default run. Explicit test coverage for the zero-postings case
(an adapter that runs cleanly and yields nothing is a pass, not a
failure).

## Architecture

**Substantial** — four new adapter modules (`workday`, `neogov`,
`smartrecruiters`, `workable`), a new external-integration count of
four ATS vendors, and a genuine cross-module capability change: the
`Fetcher` protocol (`fetch/`) gains a `post()` method so `adapters/`
can issue Workday's required `POST` request, the first non-`GET`
network call anywhere in this codebase. That is a new capability on an
existing dependency edge (`adapters` → `fetch`), not merely a same-
shape repeat of the existing 16 adapter types — well past the
"compact" (one module, no new cross-module dependency) tier. Per this
project's design-doc opt-in, the full write-up lives in this sprint's
`design/` overlay, not in this section — see `architecture-authoring`'s
Mode 2a. This section is a pointer, not a restatement.

The affected canonical docs and their overlay copies:

- `partner_scrape/adapters/DESIGN.md` (overlay:
  `design/adapters-DESIGN.md`) — four new adapter types in a fifth
  family ("ATS — internship-filtered"), reusing `ats_filters.py`
  unchanged; the Sony Interactive Entertainment Greenhouse registration
  (zero adapter-code change); and the probe pass over six unconfirmed-
  ATS employers that is scoped to produce findings, not adapters.
- `partner_scrape/fetch/DESIGN.md` (overlay: `design/fetch-DESIGN.md`)
  — `Fetcher.post()`, `UrllibFetcher.post()`, and
  `PoliteFetcher.post()`, plus the deliberate decision not to cache
  POST responses on disk.
- `partner_scrape/registry/DESIGN.md` (overlay:
  `design/registry-DESIGN.md`) — four new `adapter_type` values and
  their conventional `config` keys (`tenant`/`site`/`api_base` for
  Workday, `agency` for NEOGOV, `company` for SmartRecruiters,
  `account` for Workable), all ordinary registry data with zero
  schema/loader change.
- `docs/design/design.md` (overlay: `design/design.md`) — a short
  "Sprint 031 addition" paragraph noting the adapter-type count moves
  sixteen → twenty and the `fetch/` subsystem gains its first non-GET
  verb.

Architecture review: **APPROVE** (full five-category self-review,
recorded via `record_gate_result`). See that gate's notes for the
summary; see the overlay `.diff.md` files for the reviewed content
itself.

### Architecture Overview

See the `design/` overlay's edited copies for the full write-up. In
outline: all four new adapters follow the exact `discover → fetch →
extract` shape `greenhouse.py`/`lever.py` already established in
sprint 006 (per-posting classification via the unchanged
`adapters/ats_filters.py`, `kind="internship"` `Event`s, no changes
needed to `enrich/`, `normalize/`, or `export/` — sprint 006 built and
sprint 027 generalized their `kind in PROGRAM_EXTRACTION_KINDS` bypass,
and it already covers this sprint's records unchanged). The one real
new mechanism is Workday's `POST /wday/cxs/{tenant}/{site}/jobs`, which
needs a `post()` method added to the `Fetcher` Protocol/
`UrllibFetcher`/`PoliteFetcher` — everything else is additive registry
data plus four adapter modules.

### Design Rationale

See the `design/` overlay's edited copies for the full Decision /
Context / Alternatives / Consequences entries — most notably: extending
the `Fetcher` Protocol with `post()` rather than having the Workday
adapter open its own `urllib` call (`fetch-DESIGN.md`); not caching
POST responses on disk at this sprint's traffic volume
(`fetch-DESIGN.md`); leaving `Event.start` unset for a Workday posting
whose only date signal is a relative string like "Posted 30+ Days Ago"
rather than fabricating a parsed date (`adapters-DESIGN.md`); and
scoping the six unconfirmed-ATS employers to a probe ticket that
produces findings rather than four speculative adapters
(`adapters-DESIGN.md`).

### Migration Concerns

Additive only — no existing adapter's behavior changes (Sony is a new
Greenhouse *registration*, zero code diff to `greenhouse.py` itself).
`Fetcher.get()`'s signature and every existing caller are unchanged;
`post()` is a new method no existing `Fetcher` implementation is
required to provide unless it is used by an adapter that calls it (only
`workday.py` does). `enrich/`, `normalize/`, and `export/` are
untouched — confirmed by reading all three before designing on top of
them (per the team-lead's dispatch): `kind in PROGRAM_EXTRACTION_KINDS`
and the `Work-based Learning` current/upcoming rule already generalize
to any adapter that sets them, with no sprint-031-specific code.

**Deferred, explicitly, to a follow-up issue**: bespoke adapters for
any unconfirmed-ATS employer the probe ticket (ticket 007) finds has a
clean, scrapable shape. No follow-up issue number exists yet — none of
the six (Qualcomm, Solar Turbines, Teradata, BAE, General Atomics,
Intuit) has been live-verified as buildable, so filing one ahead of the
probe's findings would be speculative. The team-lead should file one
against whichever employer(s) the probe confirms, once ticket 007
closes.

## Use Cases

### SUC-054: Sony Interactive Entertainment surfaces via the existing Greenhouse adapter
Parent: UC-ATS-internships (issue 31)

- **Actor**: A learner browsing internship/early-career opportunities.
- **Preconditions**: Sony Interactive Entertainment's Greenhouse board
  token (`sonyinteractiveentertainmentglobal`) is live and returns
  HTTP 200 (verified 2026-08-30 per issue 31).
- **Main Flow**:
  1. A new `registry/sources/*.toml` file registers Sony against
     `adapter_type = "greenhouse"` with `config.board_token =
     "sonyinteractiveentertainmentglobal"` — zero changes to
     `adapters/greenhouse.py` itself.
  2. The existing Greenhouse adapter fetches the board, runs every
     posting through the unchanged `ats_filters.classify_posting()`.
  3. Matching postings (internship + STEM + San Diego) become
     `kind="internship"` `Event`s exactly as any other Greenhouse
     source's postings already do.
- **Postconditions**: Sony's board is part of every scheduled run.
  Zero matching postings on a given run is an accepted, expected
  outcome (Sony rarely posts SD-local internships), not a failure.
- **Acceptance Criteria**:
  - [ ] `registry/sources/` contains a new Sony entry with a header
        comment recording the live-verification date and result.
  - [ ] A dry run against the live board (or a fixture reproducing its
        real shape) completes with no error, whether or not it yields
        any matching `Event`.
  - [ ] No change to `adapters/greenhouse.py`'s code.

### SUC-055: SmartRecruiters adapter surfaces ServiceNow internships
Parent: UC-ATS-internships (issue 31)

- **Actor**: A learner browsing internship/early-career opportunities.
- **Preconditions**: `api.smartrecruiters.com/v1/companies/ServiceNow/
  postings` is a live, public, unauthenticated GET endpoint (verified
  2026-08-30 per issue 31).
- **Main Flow**:
  1. A new `adapters/smartrecruiters.py` module, dispatched as
     `adapter_type = "smartrecruiters"`, `discover()`s the postings
     endpoint (probing for total count/pagination the same
     probe-then-paginate shape `tec_rest`/`localist` already use, since
     SmartRecruiters' public API paginates via `offset`/`limit`).
  2. `fetch()` retrieves each page via the injected `Fetcher.get()`.
  3. `extract()` maps each posting through `ats_filters.classify_posting`
     (title, `typeOfEmployment.label` as the commitment signal,
     `department.label`, `location.city`/`location.region`), producing
     `kind="internship"` `Event`s for matches only.
  4. ServiceNow is registered as the first `smartrecruiters` source.
- **Postconditions**: ServiceNow's board is part of every scheduled
  run. A long stretch of zero matching postings is expected and is not
  cause to disable the source.
- **Acceptance Criteria**:
  - [ ] `adapters/smartrecruiters.py` exists, registered in
        `adapters/__init__.py`'s `ADAPTERS` table.
  - [ ] Fixture-based tests (recorded real response JSON, captured
        during ticket execution's live verification) prove: pagination
        across 2+ pages is followed; a fixture mixing internship/
        non-internship, STEM/non-STEM, and SD-local/non-local postings
        keeps only the matching subset; a malformed record is skipped,
        not fatal.
  - [ ] `registry/sources/servicenow.toml` (or similar) is registered,
        live-verified, with a header comment recording the verification
        date and result.
  - [ ] No live network call in any test.

### SUC-056: Workable adapter surfaces SD County Regional Airport Authority internships
Parent: UC-ATS-internships (issue 31)

- **Actor**: A learner browsing internship/early-career opportunities.
- **Preconditions**: San Diego County Regional Airport Authority's
  public Workable JSON (`apply.workable.com`) is live and
  unauthenticated (verified 2026-08-30 per issue 31; paid 9-week summer
  internships confirmed present).
- **Main Flow**:
  1. A new `adapters/workable.py` module, dispatched as `adapter_type =
     "workable"`, `discover()`s the account's one public jobs endpoint
     — no probe-then-paginate step, mirroring `greenhouse.py`'s "not
     paginated" precedent, pending ticket-time confirmation that this
     account's response is genuinely unpaginated.
  2. `fetch()` retrieves it via the injected `Fetcher.get()`.
  3. `extract()` maps each posting through `ats_filters.classify_posting`
     (title, `employment_type` as the commitment signal, `department`,
     `location.city`/`location.region`), producing `kind="internship"`
     `Event`s for matches only.
  4. SD County Regional Airport Authority is registered as the first
     `workable` source.
- **Postconditions**: The Authority's board is part of every scheduled
  run.
- **Acceptance Criteria**:
  - [ ] `adapters/workable.py` exists, registered in
        `adapters/__init__.py`'s `ADAPTERS` table.
  - [ ] Fixture-based tests (recorded real response JSON) prove
        filtering keeps exactly the matching subset, including the
        confirmed paid-internship postings.
  - [ ] `registry/sources/` gains a live-verified entry for the
        Authority, header comment recording the verification date and
        result.
  - [ ] No live network call in any test.

### SUC-057: Fetcher supports POST requests
Parent: UC-ATS-internships (issue 31)

- **Actor**: The Workday adapter (an internal, non-human actor — this
  use case is a mechanism, not a user-facing outcome, matching sprint
  006's precedent of a per-module SUC for `ats_filters.py`).
- **Preconditions**: None — purely additive.
- **Main Flow**:
  1. `fetch/fetcher.py`'s `Fetcher` Protocol gains a second method,
     `post(url, body, headers=None) -> FetchResponse`, alongside the
     existing `get()`.
  2. `UrllibFetcher.post()` implements it via `urllib.request.Request`
     with `method="POST"`, a JSON-encoded body, and
     `Content-Type: application/json`, reusing the same transport-error
     handling `get()` already has (never raises; returns
     `TRANSPORT_ERROR_STATUS` on a connection failure).
  3. `PoliteFetcher.post()` composes the same robots-check and
     per-domain throttle `get()` already applies, then delegates to the
     wrapped `Fetcher.post()` — but does **not** consult or write the
     on-disk conditional-GET cache (see Design Rationale in the
     overlay: POST semantics don't fit a URL-keyed cache without a
     body-hash extension this sprint doesn't need).
- **Postconditions**: Every existing `Fetcher`/`PoliteFetcher` caller
  and test double is unaffected — `get()`'s signature and behavior are
  byte-for-byte unchanged.
- **Acceptance Criteria**:
  - [ ] `Fetcher.post()`, `UrllibFetcher.post()`, `PoliteFetcher.post()`
        exist with the shape above.
  - [ ] Hermetic unit tests (a fixture `Fetcher` double) prove:
        `PoliteFetcher.post()` respects robots.txt and the per-domain
        throttle exactly like `get()`; a POST is never served from or
        written to the on-disk cache; `UrllibFetcher.post()` sends the
        body as JSON with the right `Content-Type`.
  - [ ] Every existing test in the suite (2316 baseline) still passes
        unchanged — no existing `Fetcher` double is required to
        implement `post()` unless its own test exercises it.

### SUC-058: Workday adapter surfaces internships from four-to-six confirmed San Diego employers
Parent: UC-ATS-internships (issue 31)

- **Actor**: A learner browsing internship/early-career opportunities,
  including a high-school-age learner (Northrop Grumman's HS Internship
  Program req).
- **Preconditions**: SUC-057 (`Fetcher.post()`) is implemented. Each
  employer's Workday tenant/site pair and API host shard
  (`{tenant}.wdN.myworkdayjobs.com`) is live-verified during this
  ticket's execution — a plain `requests`/`urllib` `GET` returns 403
  per issue 31's own census; whether adding browser-like headers
  (`Accept`, `Content-Type: application/json`, `Referer` set to the
  employer's own careers page, a realistic `User-Agent`) to a `POST`
  clears that 403 is exactly what this ticket must confirm live.
- **Main Flow**:
  1. A new `adapters/workday.py` module, dispatched as `adapter_type =
     "workday"`, `discover()`s each source by probing
     `POST /wday/cxs/{tenant}/{site}/jobs` with `offset=0` to learn
     `total`, then returns one `EventRef` per page (`context={"offset":
     ...}`), mirroring `tec_rest`/`localist`'s probe-then-paginate
     shape but over POST instead of GET query params.
  2. `fetch()` issues each page's `POST` via `Fetcher.post()`, with
     browser-like headers per source `config` (or a documented
     package-wide default if one set of headers proves sufficient for
     every tenant).
  3. `extract()` maps each `jobPostings[]` entry (title,
     `locationsText`, `externalPath` joined with the site's careers
     base to build the apply URL) through `ats_filters.classify_posting`,
     producing `kind="internship"` `Event`s for matches only.
     `Event.start` is left unset when Workday's only date signal is a
     relative string ("Posted Today", "Posted 30+ Days Ago") that
     cannot be parsed into an absolute date without fabricating one
     (rolling-internship semantics, already supported by
     `normalize.run()`'s existing no-deadline branch).
  4. Northrop Grumman, Cubic, Illumina, and Dexcom are registered as
     required; ResMed and Sempra/SDG&E are registered too if this
     ticket's own live verification confirms their tenant/site pair —
     best-effort, not blocking.
- **Postconditions**: Each confirmed employer's board is part of every
  scheduled run. A long stretch of zero matching postings — including
  for Northrop Grumman's specific HS Internship Program req, which may
  not always be open — is expected and is not cause to disable the
  source. If the 403 persists even with browser-like headers (a
  TLS/JA3-fingerprint block plain `urllib`/`requests` cannot clear),
  that employer is registered `enabled = false` with a comment
  explaining the finding, and a headless-browser-driven POST workaround
  is noted as a follow-up, not attempted in this sprint.
- **Acceptance Criteria**:
  - [ ] `adapters/workday.py` exists, registered in
        `adapters/__init__.py`'s `ADAPTERS` table.
  - [ ] Fixture-based tests (recorded real response JSON, captured
        during live verification) prove: pagination across 2+ pages is
        followed; a fixture mixing internship/non-internship, STEM/
        non-STEM, and SD-local/non-local postings keeps only the
        matching subset; Northrop Grumman's HS Internship Program req
        (or an equivalent fixture posting) survives classification; a
        posting with only a relative-date string gets no fabricated
        `Event.start`.
  - [ ] Each of Northrop Grumman, Cubic, Illumina, Dexcom is either
        registered `enabled = true` with a live-verification header
        comment, or `enabled = false` with a comment naming the
        specific blocker found.
  - [ ] No live network call in any test.

### SUC-059: NEOGOV/governmentjobs.com adapter surfaces seasonal student/intern postings from four San Diego public agencies
Parent: UC-ATS-internships (issue 31)

- **Actor**: A learner browsing internship/early-career opportunities.
- **Preconditions**: Unlike Workday/SmartRecruiters/Workable, issue 31
  does not carry a confirmed endpoint shape for NEOGOV — only that
  County of San Diego, City of San Diego, SANDAG, and Port of San Diego
  each publish through `governmentjobs.com`. This ticket's first step
  is to live-confirm whether a structured JSON endpoint exists for
  these agencies' postings.
- **Main Flow**:
  1. Confirm the real endpoint shape live against at least one of the
     four agencies.
  2. If a structured JSON endpoint exists: build `adapters/neogov.py`
     (`adapter_type = "neogov"`) following this family's usual
     `discover → fetch → extract` shape, with per-source `config.agency`
     identifying which of the four agencies a given registration is
     for (one adapter, four registered sources, per the roadmap plan).
  3. If no structured endpoint exists and postings are only reachable
     as rendered HTML: register each agency instead through the
     existing `generic_html` or `listing_html` adapter — no new
     adapter type — rather than forcing a nonexistent JSON API. This
     is a legitimate, in-scope pivot, not a scope failure, and should
     be recorded as such in the ticket's own notes.
  4. Whichever mechanism applies, every posting is run through the
     unchanged `ats_filters.classify_posting()` before becoming a
     `kind="internship"` `Event`.
  5. All four agencies are registered.
- **Postconditions**: Student/intern classes post seasonally at these
  agencies — long stretches of zero matching postings, punctuated by
  seasonal bursts, are expected and are not cause to disable a source.
- **Acceptance Criteria**:
  - [ ] The real endpoint/markup shape for at least one agency is
        confirmed live and recorded in the ticket's notes before any
        adapter code is written against an assumed shape.
  - [ ] All four agencies (County of SD, City of SD, SANDAG, Port of
        SD) are registered, live-verified, whichever mechanism
        (bespoke `neogov` adapter or existing HTML adapter) the live
        finding supports.
  - [ ] Fixture-based tests (recorded real response data) prove
        filtering keeps exactly the matching subset.
  - [ ] No live network call in any test.

### SUC-060: Unconfirmed-ATS employers are probed, not speculatively built
Parent: UC-ATS-internships (issue 31)

- **Actor**: The team-lead / a future sprint planner, who needs
  evidence rather than speculation before deciding whether to build a
  fifth ATS adapter family.
- **Preconditions**: None.
- **Main Flow**:
  1. For each of Qualcomm (Eightfold-ish, previously 403), Solar
     Turbines, Teradata, BAE (Phenom), General Atomics (BrassRing), and
     Intuit (Radancy), attempt a live, read-only probe of its careers
     site/API to determine: does a public, unauthenticated structured
     endpoint exist; does it 403 even with browser-like headers; does
     it require a credential or a headless browser to reach.
  2. Record findings per employer — reachable-and-structured,
     reachable-but-HTML-only, or blocked-and-how — without writing any
     adapter code for a genuinely new ATS shape.
  3. If time and evidence both support it, no obstacle prevents
     registering a probed employer through an *already-existing*
     adapter type (e.g. if one turns out to run Greenhouse or Lever
     under an unlisted board name) in this same ticket — that is
     registration, not new adapter work, and stays in scope.
- **Postconditions**: A findings record exists per employer. No
  bespoke adapter for a genuinely new ATS vendor is built this sprint;
  any that the findings justify is deferred to a follow-up issue (see
  this sprint's Architecture > Migration Concerns for why no issue
  number is filed yet).
- **Acceptance Criteria**:
  - [ ] Each of the six employers has a recorded finding (in the
        ticket's own notes, and in a registry candidate/disabled-source
        comment if a registration attempt was made).
  - [ ] No new adapter module is added for a vendor shape this sprint
        has not already built (Workday/NEOGOV/SmartRecruiters/Workable/
        Greenhouse only).
  - [ ] If any employer is found reachable through an existing adapter
        type, it is registered and live-verified in this same ticket.

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [x] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Use Cases | Depends On |
|---|-------|-----------|------------|
| 001 | Register Sony Interactive Entertainment on the existing Greenhouse adapter | SUC-054 | — |
| 002 | SmartRecruiters adapter — ServiceNow internships | SUC-055 | — |
| 003 | Workable adapter — SD County Regional Airport Authority internships | SUC-056 | — |
| 004 | Fetcher gains POST support for Workday's CXS API | SUC-057 | — |
| 005 | Workday adapter — Northrop Grumman, Cubic, Illumina, Dexcom internships | SUC-058 | 004 |
| 006 | NEOGOV adapter — County/City of SD, SANDAG, Port of SD seasonal internships | SUC-059 | — |
| 007 | Probe unconfirmed-ATS employers (Qualcomm, Solar Turbines, Teradata, BAE, General Atomics, Intuit) | SUC-060 | — |

Tickets execute serially in the order listed — cheapest-and-surest
first (001-003: a registry-only registration plus two adapters with
confirmed public endpoints), then the one piece of new infrastructure
plus its consumer (004-005: `Fetcher.post()`, then Workday, the
sprint's highest-risk ticket), then the shape-unconfirmed adapter
(006: NEOGOV), then the probe (007), matching the team-lead's dispatch
guidance to sequence the surest work first. Only 005 has a real
dependency (004); 001, 002, 003, 006, and 007 are independent of each
other and of 004/005, so a worktree-parallel execution could run them
concurrently if the sprint opts into that — not assumed here, since
this sprint does not carry that opt-in flag.

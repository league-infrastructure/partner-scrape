---
id: '024'
title: Hub Registry Discovery Hubs and Do-Not-Scrape List
status: done
branch: sprint/024-hub-registry-discovery-hubs-and-do-not-scrape-list
use-cases:
- SUC-001
- SUC-002
issues:
- 36-hub-registry-discovery-only.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 024: Hub Registry Discovery Hubs and Do-Not-Scrape List

## Goals

- Populate the Hub Registry (`registry/hubs/`) with real, live-verified
  discovery-only hubs, replacing today's placeholder-only state.
- Codify a do-not-scrape / excluded-source reference so a future session
  never has to re-investigate a site's ToS or robots.txt from scratch
  once this project has already settled the question.

## Problem

`registry/hubs/` has exactly one file, `example-regional-calendar.toml`,
explicitly marked as a non-live template. Issue 36 names seven candidate
discovery-only hubs from 2026-08-30 research and a list of sites this
project has already decided never to scrape — neither is codified.
Nothing stops a future session from re-researching Eventbrite's ToS from
scratch, and nothing prevented this sprint's own fresh re-check from
finding that several of the issue's "ready to register" hub candidates
actually carry explicit anti-scraping ToS clauses on the site's own
terms page today.

## Solution

Live-reverify each candidate hub's URL, robots.txt, and ToS as of
2026-08-31 (the 2026-08-30 research is a day old and, per this sprint's
own checking, already stale in several places — see Design Rationale).
Register only what checks out cleanly against this project's existing
"robots.txt/ToS verified before registering" convention (sprints
014-016). Write a new `partner_scrape/registry/DO_NOT_SCRAPE.md`,
colocated with the other registry catalogs, capturing both issue 36's
pre-vetted do-not-scrape list and this sprint's own newly-found
exclusions, so a future session can grep it instead of re-investigating.

## Success Criteria

- `registry/hubs/` contains at least one new real, live-verified hub
  beyond the template, loadable by `load_hubs()` and reachable through
  the existing `discover-candidates` CLI path with zero code changes.
- `partner_scrape/registry/DO_NOT_SCRAPE.md` exists, is checked in, and
  lists every site from issue 36's do-not-scrape set plus every
  exclusion this sprint's own verification newly found, each with a
  one-line reason and the verification date.
- `tests/test_registry_hub_schema.py`'s real-directory assertions are
  updated to match the new hub roster rather than left broken by the
  registration.
- No hub is registered whose live-checked ToS or robots.txt this sprint
  actually found to forbid automated access — issue 36's framing is a
  starting point, not a substitute for this sprint's own check.

## Scope

### In Scope

- Registering SDCEC's youth STEM list (sandiegoengineers.org/stem) as a
  discovery-only hub — the one issue-36 candidate that verified cleanly
  live on 2026-08-31 (reachable, no robots.txt restriction, no ToS
  found, and directly confirmed to carry 124 distinct outbound
  organization domains on its `/stem` page).
- Writing `partner_scrape/registry/DO_NOT_SCRAPE.md`, covering issue
  36's full pre-vetted do-not-scrape list plus four newly-excluded
  candidates (KidsOutAndAbout, sandiegostemsummercamps.com,
  sandiegomoms.com, San Diego Reader — all ToS-blocked on this sprint's
  fresh read) and two deferred, not-excluded entries (KPBS's community
  calendar, Macaroni Kid — see Design Rationale and Open Questions).
- Updating the one hardcoded test assertion in
  `tests/test_registry_hub_schema.py` that currently asserts the real
  hub registry contains exactly `{"example-regional-calendar"}`.

### Out of Scope

- Balboa Park and UCSD Localist — issue 25's scope, not issue 36's; the
  2026-08-30 stakeholder call to treat them as sources, not hubs, is
  taken as settled and is not re-litigated here.
- Any code change to `hub_schema.py`, `hub_scan.py`, or
  `candidate_pipeline.py` — the Hub Scan mechanism is unchanged; this
  sprint is registration and documentation only.
- A multi-hop / recursive hub-scan capability that would make
  listing-style hubs like KPBS's calendar viable (see Design Rationale)
  — a real gap this sprint surfaces but does not build.
- A stakeholder-level reconsideration of whether lead-generation-only
  automated access is acceptable against the four newly-found
  ToS-blocked candidates' boilerplate — flagged as Open Question 2, not
  decided here.
- Macaroni Kid's ToS verification — its `/terms-conditions` route did
  not resolve reliably under direct fetch within this sprint's effort
  budget; already flagged optional/low-yield in issue 36, deferred
  rather than force-verified.

## Test Strategy

Hermetic, matching this project's standing convention: no test in
`tests/` hits the live network. Registering SDCEC is a pure data
addition, validated the same way the sprint-005 template hub already
is — `tests/test_registry_hub_schema.py`'s `TestRealSeedHubRegistry`
class loads the real `registry/hubs/` directory (local disk, no
network) and asserts on the parsed `HubConfig` objects. The one existing
test that hardcodes a single-entry hub set
(`test_defaults_to_the_real_hubs_directory_when_no_argument_given`)
must be updated to include the new hub's id, or it fails the moment a
second hub file exists — this is a required part of the registration
ticket, not incidental cleanup.

`DO_NOT_SCRAPE.md` is documentation; nothing in the test suite executes
it, matching how `DESIGN.md` documents elsewhere in this codebase are
not test subjects.

Live verification for this sprint itself (robots.txt fetches, ToS page
reads, outbound-link sampling on the candidate pages) is a one-time
planning-time activity, not a repeatable automated check. Its result is
captured as findings in this sprint.md and in the registered hub's own
TOML comments — mirroring `usasciencefestival.toml`'s and
`balboa-park.toml`'s existing precedent of writing the live-verification
date and result directly into the file. This matches how sprints
014-016 verified feeds live once at registration time rather than
re-verifying on every CI run.

## Architecture

**Sizing: Compact.** This sprint adds one new checked-in documentation
artifact (`registry/DO_NOT_SCRAPE.md`) and populates the existing Hub
Registry catalog (`registry/hubs/`) with one new, live-verified entry.
No code module is added or changed, no new cross-module dependency is
introduced (the new hub file is read through the exact same,
unmodified `hub_schema.load_hubs()` → `discovery.hub_scan.scan_hub()`
→ `candidate_pipeline` → `registry.candidates.write_candidate()` path
the template hub already exercises), and no data model changes (the
existing `HubConfig` schema — `hub_id`, `hub_name`, `page_urls`,
`config` — is used unchanged, with no new field). No diagram is
included: nothing new is being composed between modules: this is
population of an existing, already-diagrammed extension point (see
`registry/DESIGN.md` §2's four-catalog table), not a change to the
shape of the system.

### What Changed

- **`registry/hubs/sdcec-stem.toml` (new).** SDCEC's hand-curated STEM
  youth-program list at `https://www.sandiegoengineers.org/stem`, the
  one issue-36 candidate that verified cleanly live on 2026-08-31: the
  page returns HTTP 200, `robots.txt` returns HTTP 404 (no file
  present, which `fetch/robots.py`'s existing "any non-200 response is
  treated as everything allowed" convention already covers correctly
  with no code change), no Terms of Service or legal notice link exists
  anywhere on the site, and a direct fetch of the page found 124
  distinct outbound (different-domain) links — real lead-generation
  signal, not an empty or placeholder page. Note: the bare
  `sandiegoengineers.org` domain (no `www`) fails TLS negotiation
  entirely; `page_urls` must use the `www.` host.
- **`partner_scrape/registry/DO_NOT_SCRAPE.md` (new).** A checked-in
  reference, colocated with `registry/DESIGN.md`, `hubs/`, `sources/`,
  and `candidates/`, cataloging every site this project has
  investigated and decided not to scrape: issue 36's pre-vetted list
  (Eventbrite, Idealist/VolunteerMatch, ActivityHero, Tinybeans, SDCOE
  OMS, Patch, SanDiego.org/CONNECT/StartupSD, ActiveNet apm REST,
  JustServe/HandsOn San Diego/Points of Light, Meetup per-group iCal)
  plus four candidates this sprint's own live re-verification newly
  found ToS-blocked (KidsOutAndAbout, sandiegostemsummercamps.com,
  sandiegomoms.com, San Diego Reader), plus two deferred-not-excluded
  entries with their own reasons (KPBS community calendar, Macaroni
  Kid) — see Design Rationale below for why the deferred pair is a
  distinct category from the excluded ones.
- **One assertion updated in `tests/test_registry_hub_schema.py`.**
  `test_defaults_to_the_real_hubs_directory_when_no_argument_given`
  currently asserts the real `registry/hubs/` directory parses to
  exactly `{"example-regional-calendar"}`; this becomes
  `{"example-regional-calendar", "sdcec-stem"}`.

### Why

Issue 36's core ask — "so future sessions don't re-litigate
already-settled ToS/robots findings" — needs somewhere durable and
discoverable to live. `registry/` is structurally that place already:
its own `DESIGN.md` describes it as "the codebase's configuration
boundary," and it already holds one checked-in doc (`DESIGN.md` itself)
alongside four data catalogs. A fifth checked-in doc for exclusions is
the same *kind* of artifact this directory already holds, not a new
kind of thing requiring a new pattern. No schema/loader pair is
warranted for it: nothing in the pipeline needs to consume this list
programmatically, because there is no "attempt to scrape X" code path
in this project for a denylist to intercept — the registry is
opt-in-by-construction (a hub or source exists only once someone writes
a TOML file for it), so the exclusion list's entire job is informing a
human *before* they write one, not gating one already written.

### Impact on Existing Components

`hub_schema.py`, `hub_scan.py`, `candidate_pipeline.py`, and `cli.py`'s
`discover-candidates` subcommand: none — SDCEC is read through the
exact same, unmodified path the template hub already exercises, and the
`discover-candidates` CLI command already defaults to scanning whatever
is in `registry/hubs/`, so registering the new file is sufficient by
itself; no wiring is needed. `registry/DESIGN.md`: gains one
cross-reference line pointing at `DO_NOT_SCRAPE.md`; its §2 catalog
table is deliberately left unchanged, since that table documents
*loaded* catalogs (`sources/`, `hubs/`, `ads/`, `candidates/`) and
`DO_NOT_SCRAPE.md` is documentation, not a fifth loaded catalog — adding
a "not applicable, it's a doc" row would blur what the table is
actually for.

### Migration Concerns

None — purely additive. The one required test update (see What
Changed) is not a migration in the data-model sense; it is a test that
was written to assert "there is exactly one hub in the real registry"
and becomes factually wrong the moment any second hub file exists,
independent of which hub this sprint chose to add.

### Design Rationale

**Decision: exclude KidsOutAndAbout, sandiegostemsummercamps.com,
sandiegomoms.com, and San Diego Reader from this sprint's hub
registration, despite issue 36 naming them as pre-cleared or
clearance-pending.**

- *Context*: issue 36 described KidsOutAndAbout as "the best
  camp-provider discovery source" and flagged only
  sandiegostemsummercamps.com as needing an explicit ToS check before
  enabling; sandiegomoms.com and San Diego Reader carried no ToS
  caveat at all in the issue text.
- *What this sprint found*, reading each site's own live ToS page on
  2026-08-31: KidsOutAndAbout's ToS prohibits "access[ing]... any of
  our Resources through any automated, unethical or unconventional
  means"; sandiegostemsummercamps.com's ToS prohibits "scrape, harvest,
  copy, or republish Site content"; sandiegomoms.com's ToS prohibits
  "use any robot, spider or other automatic device... to access the
  Website for any purpose, including monitoring or copying any of the
  material"; San Diego Reader's ToS states plainly "You may not scrape
  or otherwise copy our content without permission." All four are
  unambiguous — not the kind of generic boilerplate this project has
  previously treated as safely ignorable.
- *Alternatives considered*: (a) register anyway, on the reasoning that
  Hub Scan is lead-generation-only and structurally never republishes
  the hub's own content (see `hub_scan.py`'s own module docstring), so
  a "no scraping/republishing" clause arguably doesn't reach this use
  case; (b) register with a documented risk flag and let a stakeholder
  decide later; (c) exclude outright, matching how this project already
  treats Eventbrite's/ActivityHero's equivalently-worded clauses within
  issue 36's own do-not-scrape list.
- *Why this choice*: (a) would apply a permissive legal reading to
  these four sites that this project does not apply to its own
  do-not-scrape list — Eventbrite and ActivityHero are excluded on ToS
  language no more restrictive than this, and carving out an exception
  here only because these four happen to be attractive discovery
  sources is exactly the kind of case-by-case inconsistency issue 36 is
  trying to stop future sessions from reintroducing. (c) is the only
  option that treats "the ToS says no automated access" as a bright
  line rather than a judgment call — which is what makes it durable
  enough to write down once and stop re-litigating, the actual point of
  this sprint's do-not-scrape doc.
- *Consequences*: this sprint registers one hub (SDCEC) instead of the
  up-to-six issue 36's framing implied. That is a real, material scope
  reduction from the issue text, surfaced explicitly to the stakeholder
  rather than silently absorbed. A future sprint could reopen any of
  these four with an explicit stakeholder ruling on risk tolerance for
  lead-generation-only use against generic ToS boilerplate — that
  ruling is out of this sprint's authority to make unilaterally, the
  same kind of boundary that already keeps this sprint from
  re-litigating the Balboa Park/UCSD Localist hub-vs-source call. See
  Open Question 2.

**Decision: do not register KPBS's community calendar this sprint,
though its ToS and robots.txt are both clean.**

- *Context*: issue 36 named "KPBS/TheFinestSD community calendar,"
  citing "per-event .ics; free public submissions" as the reason to
  register it as a discovery-only hub.
- *What this sprint found*: `thefinestsd.com`, the domain issue 36
  names, no longer resolves to a working site — connection timeout from
  two independent network paths (this project's own fetcher-equivalent
  `curl` check, and a separate fetch tool). "The Finest" turns out to
  be a KPBS-branded arts/culture calendar living at `kpbs.org/arts` and
  `kpbs.org/events/all`, not a standalone site. Both KPBS pages are
  live, robots.txt-clean (`Disallow: /venue/*` and `/place/*` only —
  neither matches `/arts` or `/events/`), and its ToS page carries no
  scraping/bot restriction at all. But `hub_scan.scan_hub` is
  single-hop by design: it extracts outbound (different-domain) links
  only from the exact page(s) listed in `page_urls`, with no recursive
  crawl. Fetching both KPBS listing pages directly and extracting their
  outbound links found zero organization-hosting-site domains — only
  KPBS's own cross-properties (`donate.kpbs.org`, `kpbslegacy.org`,
  `plus.kpbs.org`, `pbskids.org`) and social platforms (Facebook,
  Instagram, TikTok, YouTube, add-to-calendar links). The organization
  actually presenting an event — confirmed by sampling one individual
  event detail page, which links out to `spreckelsorgan.org` — sits one
  hop deeper than any `page_urls` entry can reach.
- *Alternatives considered*: (a) register the listing page anyway,
  reasoning a human review queue can reject noise for free; (b)
  register a hand-picked set of individual event-detail-page URLs as
  `page_urls` instead of the listing page; (c) don't register; document
  the mechanism mismatch as an open gap.
- *Why this choice*: (a) would permanently queue the same ~10
  KPBS-owned or social-platform domains as "candidates" — the Candidate
  Review Queue's own dedup-on-write (`candidates.py`) stops the *same*
  non-candidate from being re-queued on every future scan, but does
  nothing to prevent the first, permanent write of entries that can
  never be anything but noise, which runs against that module's own
  stated design goal of not cluttering the review queue. (b) doesn't
  scale: event detail pages change weekly, and hand-picking them isn't
  hub registration, it's a standing maintenance chore this sprint has
  no mandate to create. (c) is the only option that's honest about what
  is actually true here: KPBS's calendar is a legitimate discovery
  source in principle, but the *current* single-hop Hub Scan mechanism
  cannot reach the links that would make it one in practice.
- *Consequences*: this is a real capability gap, not a KPBS-specific
  problem — any hub whose organization-identifying links live one hop
  below its landing page hits the same wall. Recorded as Open Question
  1 rather than solved here; solving it (a bounded second hop in
  `discovery/hub_scan.py`) is a code change, out of this compact-tier,
  registration-only sprint's scope.

### Open Questions

1. Should `discovery/hub_scan.py` gain a bounded second hop (follow a
   same-domain link one level, then extract outbound links from *that*
   page) to make listing-style hubs like KPBS's calendar viable? A real
   gap this sprint surfaced live (see Design Rationale's second
   decision); not attempted here — this sprint is registration-only,
   compact-tier, and a second-hop crawl is a `discovery/hub_scan.py`
   code change with its own design questions (how deep, how to bound
   fan-out, whether it changes the "never republishes" guarantee's
   reasoning).
2. Should the four ToS-blocked candidates (KidsOutAndAbout,
   sandiegostemsummercamps.com, sandiegomoms.com, San Diego Reader) be
   revisited with an explicit stakeholder ruling on whether
   lead-generation-only automated access — never republishing the hub's
   own content — is an acceptable reading against generic "no
   scraping" ToS boilerplate? This sprint applied the project's
   existing bright-line convention (ToS says no automated access →
   exclude) rather than making that judgment call itself; see Design
   Rationale's first decision.
3. Macaroni Kid's `/terms-conditions` route returned inconsistent
   404/302 responses under a direct (non-JS) fetch, so its ToS could
   not be verified within this sprint's effort budget. Already flagged
   "optional/low-yield" in issue 36; still deferred, not resolved.

## Use Cases

Sized to the change: two brief sprint-level use cases, each extending
UC-008 (Add a new partner source) the same way sprint 005's original
Hub Registry use case did.

### SUC-001: Register a live-verified discovery-only hub
Parent: UC-008 (Add a new partner source)

An operator adds a new hub TOML file for a curated site whose URL,
robots.txt, and ToS have been checked live as of the registration date
and found to permit automated access. `load_hubs()` and the
`discover-candidates` CLI path pick it up with no code change, and
`scan_hub` produces `OrgCandidate` stubs in `registry/candidates/` for
a human to review — never an `Event`, never anything published
directly.

- **Actor**: Operator (via a sprint ticket in this instance).
- **Preconditions**: The candidate site's robots.txt and ToS have been
  read live, not assumed from prior research.
- **Main Flow**:
  1. Fetch the candidate page(s) and confirm HTTP 200.
  2. Check robots.txt for the target path(s).
  3. Read the site's ToS for an automated-access/scraping prohibition.
  4. If clean, write `registry/hubs/<hub-id>.toml` with `hub_name` and
     absolute `page_urls`, documenting the verification date and result
     in a file comment (matching `usasciencefestival.toml`'s and
     `balboa-park.toml`'s precedent).
- **Postconditions**: `load_hubs()` returns the new hub;
  `discover-candidates` scans it on the next run.
- **Acceptance Criteria**:
  - [ ] The new hub file is loadable by `HubConfig.from_toml` with no
        `InvalidHubConfig`.
  - [ ] The file's own comments record the live-verification date and
        what was checked (robots.txt status, ToS finding).
  - [ ] `tests/test_registry_hub_schema.py`'s real-directory assertions
        include the new hub's id.

### SUC-002: Consult the do-not-scrape list before investigating a new site
Parent: UC-008 (Add a new partner source)

Before spending time re-researching a site's ToS or robots.txt, a
future session (or operator) checks `registry/DO_NOT_SCRAPE.md` first.
If the site is already listed, the reason and verification date are
right there, and no new investigation is needed.

- **Actor**: Operator / future planning session.
- **Preconditions**: `registry/DO_NOT_SCRAPE.md` exists and is current
  as of the last session that touched it.
- **Main Flow**:
  1. Before registering a new hub or source, check
     `registry/DO_NOT_SCRAPE.md` for the candidate domain.
  2. If listed, skip investigation and cite the existing entry.
  3. If not listed and investigation finds a hard exclusion reason
     (ToS or robots.txt forbids automated access), add an entry with
     the reason and date rather than leaving the finding undocumented.
- **Postconditions**: The exclusion list only grows more complete over
  time; it is never silently bypassed.
- **Acceptance Criteria**:
  - [ ] `DO_NOT_SCRAPE.md` lists every site from issue 36's original
        do-not-scrape set.
  - [ ] `DO_NOT_SCRAPE.md` lists this sprint's four newly-found
        ToS-blocked exclusions, each with the exact clause and
        verification date.
  - [ ] `DO_NOT_SCRAPE.md` lists the two deferred (not excluded, not
        registered) entries with their own distinct reasons.

## GitHub Issues

(None linked yet — issue 36 is a CLASI issue, not a GitHub issue.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [x] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Write the do-not-scrape / excluded-source reference | — |
| 002 | Register SDCEC as a live-verified discovery-only hub | — |

Tickets execute serially in the order listed.

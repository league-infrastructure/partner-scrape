---
id: '035'
title: Enable robots-blocked ATS sources under the stakeholder override
status: done
branch: sprint/035-enable-robots-blocked-ats-sources-under-the-stakeholder-override
use-cases:
- SUC-066
- SUC-067
issues:
- 44-robots-named-allowlist-policy-decision.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 035: Enable robots-blocked ATS sources under the stakeholder override

## Goals

Implement the stakeholder's decision on issue 44: enable the five ATS
sources currently disabled solely because their robots.txt allows only
a named crawler allow-list, using the per-source `respect_robots`
override the fetch/registry layers have supported since sprint 015 —
and record the policy exception durably in `DO_NOT_SCRAPE.md` so it
isn't re-litigated.

## Problem

Sprint 031 built five working ATS adapter registrations
(`servicenow.toml` against SmartRecruiters; `city-of-san-diego-careers.toml`,
`county-of-san-diego-careers.toml`, `sandag-careers.toml`, and
`port-of-san-diego-careers.toml` against NEOGOV/governmentjobs.com) and
left all five `enabled = false`, each with a header comment explaining
that the vendor's own robots.txt disallows all bots except a named
allow-list (LinkedInBot for SmartRecruiters; Googlebot/bingbot/etc. for
governmentjobs.com), and that flipping them on needed a stakeholder
policy decision, not more adapter code. Issue 44 raised that decision.
Eric's answer (2026-09-02): "for number one, issue 44, go ahead and
scrape them." `DO_NOT_SCRAPE.md`'s bright-line rule ("ToS/robots says no
automated access → exclude") needs a precisely-scoped exception recorded
against it, distinct from the sprint 024 hub exclusions (KidsOutAndAbout,
sandiegostemsummercamps.com, sandiegomoms.com, San Diego Reader), which
were blocked by an actual ToS clause and are not reopened by this
decision.

## Solution

No new code. This is a registry-data and documentation change using a
mechanism that already exists end to end (sprint 015's
`acquisition_policy.respect_robots` threading through
`registry/schema.py` → `adapters/base.acquisition_kwargs` →
`fetch/cache.PoliteFetcher.get()`):

1. For each of the five sources, set `enabled = true` and add
   `acquisition_policy.respect_robots = false`, with a comment on each
   file naming this stakeholder decision (issue 44) and its date
   (2026-09-02). The project's global `respect_robots` default is
   untouched — this is a per-source override only, identical in kind to
   the iCal `respect_robots = false` precedent from issue 38/sprint 015.
2. Add a new, precisely-scoped exception entry to
   `partner_scrape/registry/DO_NOT_SCRAPE.md`, distinguishing this
   vendor-blanket-policy case from the sprint-024 agency/organization
   ToS exclusions, and explicit that the sprint-024 exclusions are
   unaffected.
3. Live-verify each of the five sources with a real
   `uv run partner-scrape --source <id> --dry-run -v`, confirming the
   fetch no longer raises `RobotsDisallowed` and the adapter parses and
   filters the real response — a working adapter returning zero matching
   postings is a pass, not a failure (per issue 31/sprint 031's
   standard).

## Success Criteria

- All five sources (`servicenow`, `city-of-san-diego-careers`,
  `county-of-san-diego-careers`, `sandag-careers`,
  `port-of-san-diego-careers`) are `enabled = true` with a per-source
  `respect_robots = false` override and a comment naming this decision
  and its date.
- The global `respect_robots` default is unchanged.
- `DO_NOT_SCRAPE.md` records the exception, scoped precisely to
  named-allowlist robots.txt on ATS/job-board vendors for low-volume,
  non-republishing, link-out-only fetching of public job postings, and
  explicitly states that the sprint-024 ToS-blocked hub exclusions are
  untouched.
- A real, live dry run against each of the five sources completes with
  no `RobotsDisallowed` (or any other) error. Zero matching postings on
  any of the five is an accepted pass, not a failure — matching sprint
  031's own live results for these ATS/job-board adapters (e.g.
  Workday's five tenants: 55-3715 postings each, 0 matches, all passes).
- Full hermetic test suite stays at or above the 2508-test baseline,
  with no live network call in any test.

## Scope

### In Scope

- Registry edits to the five named `registry/sources/*.toml` files
  (`enabled`, `acquisition_policy.respect_robots`, header comment).
- A new exception entry in `partner_scrape/registry/DO_NOT_SCRAPE.md`.
- Live verification (`--dry-run -v`) of all five sources.

### Out of Scope

- Any adapter code change — `adapters/smartrecruiters.py` and
  `adapters/neogov.py` are already complete and fixture-tested (sprint
  031) and need no changes.
- Any change to the global `respect_robots` default or to
  `fetch/`'s/`registry/`'s existing mechanism — the threading already
  exists (sprint 015) and is reused as-is.
- Reopening or revisiting the sprint-024 ToS-blocked hub exclusions
  (KidsOutAndAbout, sandiegostemsummercamps.com, sandiegomoms.com, San
  Diego Reader) — those remain excluded on different grounds (an actual
  ToS clause, not a robots.txt allow-list) unless the stakeholder says
  otherwise.
- The six unconfirmed-ATS employer probes from sprint 031 (Qualcomm,
  Solar Turbines, Teradata, BAE, General Atomics, Intuit) — unrelated to
  this issue.
- Writes into the `stem-ecosystem` checkout — none needed; this sprint
  touches only `partner-scrape`.

## Test Strategy

No new hermetic tests are needed — the `respect_robots = false` code
path and the two adapters are already covered by sprint 015's and
sprint 031's existing test suites respectively (this sprint changes
registry data, not code). The verification specific to this sprint is a
live, real dry run against each of the five sources
(`uv run partner-scrape --source <id> --dry-run -v`, requiring
`dangerouslyDisableSandbox: true` for network access), confirming no
`RobotsDisallowed` error and correct parse/filter behavior. Zero
matching postings is an explicit pass condition, not a failure signal —
this must be stated in each ticket's acceptance criteria so live
verification isn't mistaken for a broken source. The existing 2508-test
hermetic baseline must continue to pass unchanged, with no live network
call in any test.

## Architecture

**Trivial** — a registry-data (config) change confined to one existing
module (`registry/sources/`), reusing a mechanism (`acquisition_policy.
respect_robots`, sprint 015) that already threads end-to-end through
`registry/` → `adapters/base.py` → `fetch/cache.PoliteFetcher`. No new
module, no new or changed cross-module dependency, no dependency-
direction change, no data-model change, and no adapter code change (the
`smartrecruiters`/`neogov` adapters were already built and tested in
sprint 031). The accompanying `DO_NOT_SCRAPE.md` edit is documentation,
not code, and records a policy decision rather than describing a system
change. Per the effort-decision rubric, this is squarely the trivial/
small tier, not compact — there is no new or changed *component*, only
five existing sources' `enabled`/`acquisition_policy` fields flipping
under a mechanism that predates this sprint by two sprints. The
architecture self-review (Phase 3) is skipped for this reason; the gate
result is recorded as `skipped`.

No subsystem design document needs an update: `registry/DESIGN.md`
already documents `acquisition_policy` as an untyped dict of
politeness knobs "passed through to `PoliteFetcher`" (§5b), and
`fetch/DESIGN.md` already documents `PoliteFetcher.get()`'s
`respect_robots` parameter and the sprint-015-ticket-003 fix that makes
every caller actually supply it from the source's `acquisition_policy`.
Neither file's *mechanism* description changes — only registry *data*
does — so this sprint seeds no `design/` overlay, per
`architecture-authoring`'s guidance to skip the overlay when a sprint
changes no subsystem design.

### Architecture Overview

N/A — no component or dependency change. See Architecture above.

### Design Rationale

N/A — no design decision beyond applying the stakeholder's ruling via
the exact mechanism issue 44 itself names (sprint 015's per-source
`respect_robots` override). The one true judgment call this sprint
does make is stated in Use Cases below: how narrowly to scope the
`DO_NOT_SCRAPE.md` exception, so it doesn't silently read as blanket
permission to override robots.txt generally.

### Migration Concerns

None. Purely additive/enabling — no existing source's behavior changes,
no schema change, no data migration. The five sources go from
"registered but disabled" to "registered and enabled"; nothing else in
the pipeline is affected.

## Use Cases

### SUC-066: Named-allowlist-blocked ATS sources are enabled per stakeholder override
Parent: UC-ATS-internships (issue 31, issue 44)

- **Actor**: A learner browsing internship/early-career opportunities;
  secondarily, a future planner or programmer who must not re-disable a
  working source for returning zero postings.
- **Preconditions**: The five sources are registered, fixture-tested,
  and `enabled = false` per sprint 031, each blocked only by a
  named-allowlist robots.txt (not a ToS clause, not a broken adapter).
  Eric has ruled, per issue 44: "go ahead and scrape them."
- **Main Flow**:
  1. Each of `servicenow.toml`, `city-of-san-diego-careers.toml`,
     `county-of-san-diego-careers.toml`, `sandag-careers.toml`, and
     `port-of-san-diego-careers.toml` is set to `enabled = true` with
     `acquisition_policy.respect_robots = false`.
  2. Each file's header comment records this decision, citing issue 44
     and the date 2026-09-02, alongside (not replacing) the sprint 031
     comment already describing the live-verified endpoint shape and
     the genuine robots block.
  3. A real `uv run partner-scrape --source <id> --dry-run -v` is run
     against each of the five, confirming no `RobotsDisallowed` (or any
     other) error.
- **Postconditions**: All five sources run as part of every scheduled
  pipeline run. The project's global `respect_robots` default is
  unchanged — this is a per-source override only. A source returning
  zero matching postings on a given live-verification run is an
  accepted pass (per sprint 031's own calibration: e.g. Sony/Greenhouse
  197→0, Workable/Airport Authority 5→0, Workday's five tenants
  55-3715→0 each — all passes), not a reason to revert `enabled` to
  `false`.
- **Acceptance Criteria**:
  - [ ] All five named TOML files have `enabled = true`,
        `acquisition_policy.respect_robots = false`, and a comment
        naming issue 44 and the date 2026-09-02.
  - [ ] The global/default `respect_robots` value (used by every other
        source with no override) is unchanged.
  - [ ] A real, live `--dry-run -v` against each of the five sources
        completes with no `RobotsDisallowed` error and no other
        exception — regardless of whether it yields any matching
        `Event`.
  - [ ] `adapters/smartrecruiters.py` and `adapters/neogov.py` are not
        modified.
  - [ ] The full hermetic test suite (2508-test baseline) still passes,
        with no live network call in any test.

### SUC-067: The robots-allowlist exception is recorded precisely in DO_NOT_SCRAPE.md
Parent: UC-ATS-internships (issue 44)

- **Actor**: A future team-lead or sprint planner deciding whether a new
  candidate source blocked by a named-crawler-allowlist robots.txt may
  be enabled, without re-litigating this decision from scratch.
- **Preconditions**: `DO_NOT_SCRAPE.md` currently states only the
  bright-line rule ("ToS/robots says no automated access → exclude")
  and the sprint-024 ToS-blocked exclusions; it has no entry addressing
  a robots.txt named-allowlist case, and no exception mechanism at all.
- **Main Flow**:
  1. A new entry (or a new "Exceptions" section, whichever reads more
     naturally alongside the existing Excluded/Deferred structure) is
     added to `DO_NOT_SCRAPE.md`, stating the exception covers
     **named-allowlist robots.txt on ATS/job-board vendors**, for
     **low-volume, non-republishing, link-out-only** fetching of
     **public job postings** — not a general robots-override license.
  2. The entry names the five sources this sprint enables and cites
     issue 44's reasoning: the four public-sector agencies (County,
     City, SANDAG, Port) want their postings found by job-seekers — the
     block is the ATS vendor's (governmentjobs.com's,
     api.smartrecruiters.com's) blanket policy, not the agency's or
     employer's own choice.
  3. The entry states explicitly that this does **not** reopen the
     sprint-024 hub exclusions (KidsOutAndAbout,
     sandiegostemsummercamps.com, sandiegomoms.com, San Diego Reader),
     which were excluded on different grounds — an actual ToS clause
     forbidding scraping, not a robots.txt allow-list — and remain
     excluded unless the stakeholder rules otherwise on those
     specifically.
- **Postconditions**: A future session facing a new named-allowlist-
  blocked ATS/job-board candidate can read this entry and know the
  policy question is already settled for that narrow shape, without
  re-reading issue 44 or re-asking the stakeholder; a future session
  facing any other robots.txt- or ToS-blocked candidate (a different
  vendor shape, a non-job-board site, a high-volume or republishing use)
  knows this exception does not extend to it by default.
- **Acceptance Criteria**:
  - [ ] `DO_NOT_SCRAPE.md` contains a new entry/section stating the
        exception's precise scope (named-allowlist robots.txt,
        ATS/job-board vendor, low-volume, non-republishing, link-out
        only).
  - [ ] The entry names issue 44, the date 2026-09-02, and the five
        sources it covers.
  - [ ] The entry explicitly states the sprint-024 ToS-blocked
        exclusions are unaffected and remain excluded.
  - [ ] The existing bright-line rule and the sprint-024 exclusion
        entries are otherwise unchanged.

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
| 001 | Record the robots-allowlist exception in DO_NOT_SCRAPE.md | SUC-067 | — |
| 002 | Enable and live-verify the five named-allowlist ATS sources | SUC-066 | 001 |

Tickets execute serially in the order listed — 001 (documentation) must
land first since 002's registry-comment edits cite it as the recorded
decision, though the two carry no technical/code dependency and could
be reordered without breaking anything.

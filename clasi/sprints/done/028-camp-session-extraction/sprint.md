---
id: 028
title: Camp session extraction
status: done
branch: sprint/028-camp-session-extraction
use-cases:
- SUC-036
- SUC-037
- SUC-038
- SUC-039
- SUC-040
- SUC-041
- SUC-042
- SUC-043
issues:
- 29-camp-session-extraction.md
- 36-reduce-page-html-before-llm-extraction.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 028: Camp session extraction

## Goals

Make camps visible on the site — currently the category most families
search for first, and entirely absent, including our own partners'
camps (Fleet ran 27 topics over 10 weeks for 787 campers in 2025).
Deliver marketing-page session extraction for the ~10 verified
providers that publish full session dates and prices in plain HTML
(San Diego Zoo, Air & Space Museum, Living Coast, Coastal Roots Farm,
Elementary Institute of Science, SD Model Railroad Museum, Camp
Galileo SD, Camp Invention, CMOD, Helen Woodward, Southwestern College
Y.E.S., Birch via its newsroom page, Fleet's seasonal marketing page),
plus platform adapters in the issue's stated priority order:
`campscui.active.com` (ActiveNet), CampBrain, then the Pike13 API.

## Problem

Registration platforms mostly block bots, so camp session data — dates,
prices, availability — is largely invisible to the current pipeline.
Unlike the event calendars the pipeline already ingests, camp session
listings are marketing pages, not structured feeds; the ~10 verified
providers above are the exception, publishing plain HTML with dates and
prices scrapable today.

## Solution

Marketing-page extraction for the ~10 verified providers, reusing the
extraction ladder (`extract/`) and, where the LLM must recover
structured session fields (dates, price, sold-out flags) from prose,
the same LLM-extraction pattern Sprint A (027) builds for program
pages. Then platform adapters, built in the issue's stated order:
`campscui.active.com` first (covers Air & Space, Helen Woodward, likely
more), then CampBrain (Coastal Roots, Watersports Camp), then the
Pike13 API (developer.pike13.com — the League's own camps; the
cleanest API of any provider). Depends on the `Camps` opportunity_type,
already delivered by sprint 015's taxonomy work.

**Scope decision carried over from the stakeholder's issue text:**
institutional/nonprofit camps only. Commercial chains (Code Ninjas, iD
Tech, Galileo [the studio brand, not to be confused with "Camp Galileo
SD location page" above which is one of our verified nonprofit-adjacent
sources], Mathnasium, RSM) are competitors of the League's own classes
and are explicitly deferred — the issue itself flags this as an
unresolved stakeholder decision as of 2026-08-30. This sprint does not
plan any work toward them; the decision is simply noted here as
deferred, not re-litigated.

Sources still blocked by JS rendering (Gateway Galaxy webstores,
SeaWorld, YMCA Salesforce, Code Ninjas, Mad Science, Challenge Island
portal, RoboThink, iD Tech) need issue 23's browser path and are out of
scope for this sprint regardless of the commercial-chain question.

## Success Criteria

- Issue 36's HTML-reduction step lands first and unblocks the SD
  Foundation Community Scholarship (`enabled = true`, live-verified)
  and the previously-failing UCSD Summer Program Finder cards.
- The verified nonprofit/institutional marketing-page providers named
  in issue 29 (SD Zoo's per-program pages, Living Coast, Coastal Roots
  Farm, Elementary Institute of Science, SD Model Railroad Museum, Camp
  Invention, CMOD, Southwestern College Y.E.S., Birch's newsroom page,
  Fleet) yield camp session records with correct dates and prices,
  typed `Camps`.
- The `campscui.active.com` (ActiveNet) and CampBrain adapters are
  built, in the issue's stated priority order, and register at least
  the sources named for each. **Pike13 is explicitly deferred** — see
  "Deferred to a follow-up issue" below.
- A season-ahead view is possible for an in-season-only marketing page
  (e.g. Fleet): it is registered `enabled = true` year-round and
  extraction tolerates a currently-empty page (zero sessions, not an
  error), so the existing weekly scheduled run picks sessions up the
  first week they publish — no new scheduling subsystem is built (see
  the `design/` overlay's Design Rationale for why this is sufficient).
- No commercial-chain camp is registered this sprint. Camp Galileo SD
  is explicitly excluded despite appearing in issue 29's marketing-page
  list — see "Camp Galileo tension" below.
- No organization is registered through two adapter paths at once (the
  sprint 027 COSMOS/OPTIMUS/ENLACE dual-registration risk, applied
  here to Air & Space Museum/Helen Woodward, both ActiveNet-covered).
- Full hermetic test suite stays green, with fixture-based tests for
  the new adapters and the reduction step (no live network, no live
  LLM calls).

## Scope

### In Scope

- The HTML-to-text reduction step (issue 36), wired into the existing
  `program_page`/`program_listing`/`program_page_multi` family, and the
  SD Foundation/UCSD re-verification it unblocks.
- Marketing-page session extraction for the verified institutional/
  nonprofit providers named in issue 29, excluding Camp Galileo SD and
  excluding Air & Space Museum/Helen Woodward (routed through
  ActiveNet instead — see Design Rationale).
- `campscui.active.com` (ActiveNet) adapter, registering at least Air &
  Space Museum and Helen Woodward.
- CampBrain adapter, registering at least one CampBrain-hosted
  organization not already covered by a marketing page (e.g.
  Watersports Camp).
- Graceful zero-result handling for an in-season-only page (Fleet),
  relying on the existing weekly cron for re-check cadence — no new
  scheduling mechanism.

### Deferred to a follow-up issue

- **Pike13 API adapter.** Issue 29 lists it third in priority and
  itself asks whether it "supersedes gaps in leaguesync" — an
  unresolved overlap with the already-shipped `leaguesync` adapter for
  the League's own camps. It also needs its own credential
  provisioning, unlike the two higher-priority platforms (apparently
  public browse surfaces). Neither is close to resolved, so building it
  this sprint risks a low-confidence adapter or a stalled ticket. A
  follow-up issue should capture Pike13 together with the
  leaguesync-overlap question for a future sprint.

### Out of Scope

- Commercial camp chains (Code Ninjas, iD Tech, Galileo, Mathnasium,
  RSM) — open stakeholder decision, not made this sprint.
- **Camp Galileo tension**: Camp Galileo SD appears in issue 29's own
  marketing-page list (its page is scrapable), but "Galileo" is also
  named in the roadmap's commercial-chain exclusion list. Camp Galileo
  is a commercial camp chain (the studio brand), so it is excluded on
  the same grounds as Code Ninjas/iD Tech/Mathnasium/RSM, not
  registered as one of this sprint's marketing-page sources, despite
  issue 29 listing its page as technically scrapable.
- JS-rendered/blocked platforms requiring issue 23's browser path
  (Gateway Galaxy, SeaWorld, YMCA Salesforce, Mad Science, Challenge
  Island, RoboThink) regardless of commercial-chain status.
- Any change to the `Opportunity`/taxonomy schema — sprint 015 already
  delivered the `Camps` type; this sprint reuses the existing
  `ProgramExtractionResult` shape unchanged (see Design Rationale).

## Test Strategy

A saved ~900KB fixture page proves the HTML-reduction step stays clear
of the model's context limit and still yields correct fields via
`FixtureProgramLLMClient`. Fixture-based tests for each new platform
adapter (`campscui.active.com`, CampBrain), following the existing
per-adapter test convention (saved page/API-response fixtures, no live
network). Marketing-page extraction tests use saved HTML fixtures for
each verified provider registered this sprint, including at least one
fixture exercising a sold-out session and one exercising an
in-season-only page's empty-list case (Fleet). A dry-run check confirms
registered sources yield correctly-dated, correctly-priced session
records before being wired into the default run.

## Architecture

**Substantial.** Four modules get real code changes (`adapters/` — the
existing `program_page`/`program_listing`/`program_page_multi` family
plus two brand-new platform adapters, `extract/`, `registry/` as data),
and a new cross-module dependency is introduced
(`adapters/program_page.py` starts depending on `extract/`, which it
previously bypassed entirely). This clears the substantial bar on both
module-count and new-cross-module-dependency grounds. No
`Opportunity`/`Event` schema change (preserved, as scoped).

Because this project has opted into the persistent per-subsystem design
doc set (`design_docs: enabled`), the full architecture write-up lives
in this sprint's `design/` overlay
(`clasi/sprints/028-camp-session-extraction/design/`), not in this
section — see `architecture-authoring`'s Mode 2a, and sprint 027's
`sprint.md` for the precedent this follows. Affected canonical docs,
each carrying a "Sprint 028" addition describing its change in full:

- `docs/design/design.md` (overlay: `design/design.md`) — subsystem-map
  adapter-count refresh (fourteen → sixteen: `activenet_camps`,
  `campbrain`).
- `partner_scrape/adapters/DESIGN.md` (overlay:
  `design/adapters-DESIGN.md`) — the HTML-reduction step wired into the
  existing `program_page`/`program_listing`/`program_page_multi` family,
  the generalized `is_open` semantics and camp sold-out surfacing via
  `Event.description`, the two new platform adapter types, and the
  deferred-Pike13 decision.
- `partner_scrape/extract/DESIGN.md` (overlay:
  `design/extract-DESIGN.md`) — the new exported
  `reduce_html_to_text()` function.
- `partner_scrape/registry/DESIGN.md` (overlay:
  `design/registry-DESIGN.md`) — the new `activenet_camps`/`campbrain`
  `adapter_type` values and their conventional `config` keys, as
  ordinary registry data.

### Architecture Overview

See the `design/` overlay's edited copies (above) for the full 7-step
write-up: responsibilities, module boundaries, the component diagram,
and the dependency-graph note.

### Design Rationale

See the `design/` overlay's edited copies for the full Decision /
Context / Alternatives / Consequences entries — most notably: reusing
`ProgramExtractionResult`/`program_page_multi` unchanged for camp
sessions rather than adding a camp-specific schema; hashing the reduced
text (not the raw HTML) for the extraction cache key; relying on the
existing weekly cron plus a prompt-level "empty list is valid" instruction
instead of building a seasonal-recheck subsystem; excluding Camp Galileo
SD and avoiding dual registration of Air & Space Museum/Helen Woodward
across the marketing-page and ActiveNet paths; and deferring Pike13 to a
follow-up issue.

### Migration Concerns

See the `design/` overlay's edited copies. Summary: additive only for
every existing `program_page`/`program_listing` registration except the
one shared-file change (HTML reduction before hashing/LLM call, which
changes the extraction cache's effective key — a harmless one-time
re-extraction per already-cached page, not a correctness issue, per the
cache's own "pure optimization" contract) and the `is_open` field's
generalized prompt wording (backward-compatible: existing
internship/program pages' `is_open` truth values are unaffected). No
existing adapter, registered source, or `Opportunity` consumer outside
this sprint's own new sources changes behavior.

## Use Cases

### SUC-036: Reduce oversized page HTML to text before LLM program extraction
Parent: UC-004 (Recover missing dates/fields via LLM extraction)

- **Actor**: Pipeline, on behalf of any `program_page`/`program_listing`/
  `program_page_multi` source.
- **Preconditions**: A source's fetched page body may be arbitrarily
  large (840KB-965KB measured on sdfoundation.org during sprint 027).
- **Main Flow**:
  1. `_extract_one_program`/`_extract_many_programs` reduce `raw.body`
     to visible text via a new `extract.reduce_html_to_text()` function
     before any cache lookup or LLM call.
  2. The reduced text is capped at a documented character limit that
     keeps the page's main content and stays safely under the model's
     200K-token context window even for the largest measured pages.
  3. Cache lookup/store keys off the reduced text's content hash, not
     the raw HTML's.
- **Postconditions**: A previously-oversized page's extraction call
  succeeds instead of raising `anthropic.BadRequestError`.
- **Acceptance Criteria**:
  - [ ] A saved ~900KB fixture page reduces to a size that stays clear
        of the 200K-token limit and still yields correct fields via
        `FixtureProgramLLMClient`.
  - [ ] Every existing `program_page`/`program_listing`/
        `program_page_multi` fixture test continues to pass unmodified
        (reducing an already-small page is a no-op on its extracted
        fields).
  - [ ] A cache-hit test proves the cache key is derived from the
        reduced text (a content-only change to a stripped element, e.g.
        a `<script>` block, does not invalidate the cache).

### SUC-037: Previously-oversized/failing program pages extract successfully after reduction
Parent: UC-004

- **Actor**: Pipeline, on behalf of the SD Foundation Community
  Scholarship source and the UCSD Summer Program Finder's
  previously-failing cards.
- **Preconditions**: SUC-036 lands;
  `sd-foundation-community-scholarship.toml` is currently
  `enabled = false`.
- **Main Flow**:
  1. Live-verify the SD Foundation source now extracts a program
     record.
  2. Flip `enabled = true`.
  3. Re-check the UCSD cards recorded as failing during sprint 027
     (e.g. `www.rmtlacademy.org`) and confirm they now yield a record.
- **Postconditions**: The SD Foundation Community Scholarship ships;
  previously-empty UCSD cards yield records where the underlying page
  supports it.
- **Acceptance Criteria**:
  - [ ] `sd-foundation-community-scholarship.toml` is `enabled = true`
        and live-verified.
  - [ ] The UCSD cards previously failing are re-verified; any still
        failing for a reason unrelated to page size is logged as a new,
        separate issue, not silently dropped.

### SUC-038: A camp marketing page's weekly sessions each yield their own dated, priced record
Parent: UC-011 (Discover STEM company events and internships (extension))

- **Actor**: Pipeline, on behalf of a registered `program_page_multi`
  camp source.
- **Preconditions**: The source's `config.program_kind = "program"` and
  `config.opportunity_type = "Camps"`.
- **Main Flow**:
  1. `ProgramPageMultiAdapter.extract()` calls `extract_programs()`
     (on the reduced text, per SUC-036).
  2. Each returned result maps to its own `Event` via
     `_map_result_to_event`, with `date_start`/`date_end` as that
     session's own week dates and `cost` as that session's own price.
  3. `opportunity_type` is forced to `"Camps"` via the config override,
     regardless of the LLM's own classification.
- **Postconditions**: N distinct week-session `Opportunity` records
  publish from one registered page.
- **Acceptance Criteria**:
  - [ ] A fixture page with N week-rows (each with its own dates and
        price) yields N `Event`s, each with distinct `start`/`end`/
        `cost`.
  - [ ] Every resulting `Event`'s `opportunity_type` is `"Camps"`.

### SUC-039: A sold-out camp session is flagged rather than presented as available
Parent: UC-011

- **Actor**: Pipeline (extraction/mapping), on behalf of a camp source
  whose page marks some sessions sold out (e.g. SD Model Railroad
  Museum's table).
- **Preconditions**: SUC-038's mechanism is in place.
- **Main Flow**:
  1. `_FIELD_EXTRACTION_RULES`'s `is_open` definition generalizes from
     "applications open" to "open for enrollment/application; false if
     closed, full, or sold out" — a backward-compatible prompt-wording
     change.
  2. `_map_result_to_event`, when the resolved `opportunity_type` is
     `"Camps"` and `result.is_open` is `False`, sets `Event.description`
     to a sold-out note (a field this mechanism previously left unset
     for every `program_kind`).
- **Postconditions**: A sold-out session ships with a visible marker
  rather than reading identically to an open one.
- **Acceptance Criteria**:
  - [ ] A fixture record with `is_open=False` and `opportunity_type=
        "Camps"` carries a sold-out `Event.description`.
  - [ ] A fixture record with `is_open=False` and a non-`"Camps"`
        `opportunity_type` (e.g. an internship) is unaffected —
        `Event.description` stays unset, matching pre-sprint behavior
        exactly.

### SUC-040: An in-season-only camp page with no currently-published sessions yields zero records, not an error
Parent: UC-011

- **Actor**: Pipeline, on behalf of Fleet's marketing page
  (registration opens Feb; the page may show nothing off-season).
- **Preconditions**: Fleet's `program_page_multi` source is registered
  `enabled = true` year-round.
- **Main Flow**:
  1. `_SYSTEM_PROMPT_MULTI` instructs the model to return an empty
     `programs` list when no distinct sessions are described on the
     page.
  2. `_extract_many_programs` maps zero results to zero `Event`s, not
     an error.
  3. The existing weekly scheduled run (`.github/workflows/
     scheduled-run.yml`) re-fetches the page every week regardless of
     season, so sessions appear the first week they are published —
     no separate scheduling mechanism is built.
- **Postconditions**: An off-season run yields zero `Camps` records for
  Fleet without raising or logging a false failure; an in-season run
  yields its sessions the same way any other camp source does.
- **Acceptance Criteria**:
  - [ ] A fixture off-season page (`list_responses = []`) yields zero
        `Event`s with no exception.
  - [ ] Fleet is registered `enabled = true` (not gated behind a
        disabled flag pending "season").

### SUC-041: The verified nonprofit/institutional camp marketing-page providers are registered and typed Camps
Parent: UC-011

- **Actor**: Operator/pipeline.
- **Preconditions**: SUC-036, SUC-038, SUC-039, and SUC-040 land.
- **Main Flow**:
  1. Each of the verified providers named in issue 29 that this sprint
     registers via a marketing page (SD Zoo's per-program pages, Living
     Coast, Coastal Roots Farm, Elementary Institute of Science, SD
     Model Railroad Museum, Camp Invention, CMOD, Southwestern College
     Y.E.S., Birch's newsroom page, Fleet) is registered as one or more
     `program_page`/`program_page_multi` sources and live-verified.
  2. Camp Galileo SD is explicitly **not** registered (commercial-chain
     scope exclusion, carried over from the roadmap decision).
  3. Air & Space Museum and Helen Woodward are explicitly **not**
     registered via this marketing-page path — see SUC-042; they are
     registered via the ActiveNet adapter instead, to avoid dual
     registration of the same org.
- **Postconditions**: The verified institutional/nonprofit providers'
  camp sessions are visible on the site; no commercial-chain camp and
  no dual-registered org appear.
- **Acceptance Criteria**:
  - [ ] Every registered source live-verifies to at least one
        correctly-dated, correctly-priced session record, or is
        registered `enabled = false` with a reason comment (sprint 027
        tickets 005/006 precedent) if blocked.
  - [ ] `registry/sources/` contains no Camp Galileo SD entry.
  - [ ] `registry/sources/` contains no marketing-page entry for Air &
        Space Museum or Helen Woodward.

### SUC-042: campscui.active.com (ActiveNet) camp sessions extract via a structured platform adapter
Parent: UC-011

- **Actor**: Pipeline, on behalf of a registered `activenet_camps`
  source.
- **Preconditions**: An organization's camps are hosted on
  `campscui.active.com`.
- **Main Flow**:
  1. The new `ActiveNetCampsAdapter`'s `discover()`/`fetch()`/
     `extract()` retrieve and parse the platform's session listing
     (JSON or server-rendered HTML — confirmed at ticket time) into
     dated, priced `Event`s with `kind="program"`,
     `opportunity_type="Camps"` (config override).
  2. A sold-out session maps the same way SUC-039 defines.
- **Postconditions**: Air & Space Museum and Helen Woodward (at
  minimum) publish their ActiveNet-hosted camp sessions.
- **Acceptance Criteria**:
  - [ ] A fixture-based test proves the adapter maps a saved ActiveNet
        response/page into correctly-dated, correctly-priced `Event`s,
        with no live network or LLM call.
  - [ ] At least Air & Space Museum and Helen Woodward are registered
        and live-verified.

### SUC-043: CampBrain-hosted camp sessions extract via a structured platform adapter
Parent: UC-011

- **Actor**: Pipeline, on behalf of a registered `campbrain` source.
- **Preconditions**: An organization's camps are hosted on CampBrain
  and have no equivalent marketing-page coverage registered this
  sprint.
- **Main Flow**: Mirrors SUC-042, substituting the new
  `CampBrainAdapter`.
- **Postconditions**: At least one CampBrain-hosted organization not
  already covered by a marketing page (e.g. Watersports Camp) publishes
  its camp sessions.
- **Acceptance Criteria**:
  - [ ] A fixture-based test proves the adapter maps a saved CampBrain
        response/page into correctly-dated, correctly-priced `Event`s,
        with no live network or LLM call.
  - [ ] At least one CampBrain-hosted organization is registered and
        live-verified.
  - [ ] Coastal Roots Farm is registered via at most one path (its
        marketing page, per SUC-041) — not duplicated via CampBrain.

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
| 001 | Reduce fetched HTML to bounded text before program-page LLM extraction | — | 36 |
| 002 | Re-enable SD Foundation Community Scholarship and re-verify failing UCSD cards | 001 | 36 |
| 003 | Generalize is_open for sold-out sessions and empty-list handling for off-season pages | 001 | 29 |
| 004 | Register verified nonprofit/institutional camp marketing-page providers | 003 | 29 |
| 005 | Build the activenet_camps adapter for campscui.active.com | 003 | 29 |
| 006 | Build the campbrain adapter | 004, 005 | 29 |

Tickets execute serially in the order listed. 001/002 (issue 36) are
sequenced first, per the dispatch's instruction, since the camp
marketing pages ticket 004 registers would otherwise hit the same
oversized-HTML failure sprint 027 hit. 003 has no code dependency on
001/002 beyond touching the same file area (`program_page.py`/
`program_llm.py`) — sequenced after 001 to avoid merge churn, not
because it needs the reduction step's behavior. 005 and 006 have no
hard dependency on each other and could execute in either order (or in
parallel, if this sprint opts into parallel worktrees); 006 depends on
005 only for the shared adapter pattern to be proven once, and on 004
for the dual-registration check in its own acceptance criteria.

**Pike13** (issue 29's third-priority platform adapter) has no ticket
this sprint — split out of issue 29 into a new sibling issue,
`pike13-camp-platform-adapter.md`, during detail planning
(`status: pending`, no `sprint` set, not part of this sprint's `issues:`
list above). It currently sits alongside this sprint's other issue files
on disk (a `split_issue` artifact of where issue 29 lived); team-lead may
want to relocate it into the top-level issue pool at sprint close. See
this doc's "Deferred to a follow-up issue" note above and
`design/adapters-DESIGN.md`'s Design Rationale for why.

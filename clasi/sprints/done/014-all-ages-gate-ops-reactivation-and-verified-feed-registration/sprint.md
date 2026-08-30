---
id: '014'
title: All-Ages Gate, Ops Reactivation, and Verified-Feed Registration
status: done
branch: sprint/014-all-ages-gate-ops-reactivation-and-verified-feed-registration
use-cases: []
issues:
- 22-all-ages-relevance-gate.md
- 23-ops-playwright-cron-and-browser-fetch.md
- 24-triage-zero-yield-sources.md
- 25-register-verified-structured-feeds.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 014: All-Ages Gate, Ops Reactivation, and Verified-Feed Registration

## Goals

Roughly double what sdstemecosystem.org shows — without writing a single
new adapter — by fixing four independent things that are each silently
blocking already-scraped content from reaching the site:

1. Widen the LLM relevance gate from K-12-only to all ages, matching the
   site's own "learners of all ages" framing and its existing `Adult`
   age facet, so sources like UCSD Extended Studies, Salk, Qualcomm, and
   sandiego.gov stop publishing zero despite the adapter already finding
   hundreds of records.
2. Turn the operational machinery that already exists back on: install
   the optional Playwright dependency, flip more JS-rendered/403-blocked
   sources to the existing headless fetch strategy, and re-enable the
   weekly scheduled cron.
3. Triage the ~33 sources that returned zero adapter-level records in
   the last run to a resolved disposition — fixed, re-typed, marked
   headless, or disabled with a documented reason — including two known
   mis-registrations (`sd-river-park-foundation`, `sandiego-gov`).
4. Register roughly 20 live-verified structured feeds against the three
   adapters (`tec_rest`, `ical`, `localist`) the codebase already has,
   with zero new adapter engineering.

## Problem

Four independent gaps, each already diagnosed by live research
(2026-08-30 gap analysis, referenced from issues 22-25):

- **The relevance gate is narrower than the product.** `enrich/
  llm_client.py`'s system prompt gates on "a STEM learning opportunity
  for youth (not an adult-only program...)". Of 6,598 cached `relevant:
  false` verdicts, 1,027 are adult/professional programs — the reason
  UC San Diego Extended Studies (300 found -> 0 published), Salk (126 ->
  0), Qualcomm (49 -> 0), sandiego.gov (299 -> 0), and Fleet's own adult
  partner series (Suds & Science, After Dark, Nat Talks, Birch
  Perspectives) publish nothing, even though the adapters already found
  them. This is a pure gate problem, not an acquisition problem — the
  events are already in hand.
- **Operational machinery exists but is switched off.** `fetch/
  headless.py`'s `PlaywrightFetcher` and `pipeline.py`'s per-source
  `fetch_strategy = "headless"` wiring are fully built and tested (only
  `sandiego-air-space.toml` uses it today), but `playwright` is not
  installed in any runtime, so 9 Wix partner sites and a longer list of
  403-blocked sources (aquarium.ucsd.edu, Gateway Galaxy webstores,
  ActiveNet REST, zoo.sandiegozoo.org kids-programs, several city
  library/rec sites, Mathnasium, AoPS) stay blind. Separately, `.github/
  workflows/scheduled-run.yml`'s weekly cron trigger has been commented
  out since sprint 004; every run since has been a manual
  `workflow_dispatch`.
- **A third of sources return nothing at the adapter level.** 33 of 99
  registered sources found zero raw records in the last run, including
  ones that should be among the largest (`sdpl`, same BiblioCommons
  platform as `sdcl`'s 3,957; three Tier-1 TEC REST sources that worked
  in the `dev/` era: `cleansd`, `ilacsd`, `eefkids`). Two are outright
  mis-registrations: `sd-river-park-foundation` is registered
  `generic_html` but its actual platform (verified live, 73 events) is
  TEC REST; `sandiego-gov`'s `org_name` ("Discover U at San Diego Public
  Library") does not match its `site_url` (sandiego.gov) at all.
- **~20 already-verified feeds sit unregistered.** The same research run
  live-confirmed roughly 20 structured feeds — Balboa Park's park-wide
  TEC calendar, SD County Parks' 553-event iCal feed, FIRST California,
  SD Astronomy Association, and more — every one of which fits an
  adapter (`tec_rest`, `ical`, or `localist`) this codebase already has.
  This is registration work, not engineering.

## Solution

Four tracks, sequenced gate-and-ops first (they multiply everything
downstream: a source triaged or registered against a narrower gate or a
still-broken fetch path would be re-diagnosed for no reason), then
triage, then registration (which verifies against the now-reactivated
pipeline):

1. **Widen the gate (issue 22).** Rewrite `enrich/llm_client.py`'s
   `_SYSTEM_PROMPT` so `relevant` means "a STEM learning opportunity for
   any audience" while keeping the existing noise rejection (non-STEM
   recreation, galas, closure notices, nav pages) unchanged. Because
   `enrich/cache.py`'s content hash deliberately covers only an event's
   *input* fields (not the prompt), a prompt-semantics change needs its
   own versioning signal, parallel to (never folded into) the existing
   `_CACHE_SCHEMA_VERSION` mechanism that already exists for *output
   shape* changes — see Architecture / Design Rationale. Age
   classification already has an `Adult` value in
   `_AGE_GRADE_LEVEL_VALUES` and the site already has an `Adult` filter
   facet; neither needs to change.
2. **Turn the machine back on (issue 23).** `PlaywrightFetcher` and its
   `pipeline.py` wiring are already complete and tested, and most of
   this track is deployment/config, not engineering: add `playwright`
   to the environments that need it (dev, CI, the scheduled workflow),
   flag the known-blocked sources `acquisition_policy.fetch_strategy =
   "headless"` in their TOMLs, and uncomment the cron trigger in
   `scheduled-run.yml`. Two small real code changes are required,
   though — found during this sprint's own architecture self-review,
   not the original issue text: `fetch/headless.py`'s
   `PlaywrightFetcher` shares one browser page across every
   headless-flagged source, safely today only because exactly one
   source uses that strategy; flagging ~10 more (this track's whole
   point) makes concurrent, multi-threaded access to that shared page
   a near-certainty, a correctness hazard (silently misattributed
   content, or a Playwright thread-affinity error), not just a crash
   risk. `pipeline.py` gains a dedicated single-worker dispatch path
   for `headless`-strategy sources (the load-bearing fix, since only
   the dispatcher controls which thread runs a given source), and
   `PlaywrightFetcher.get()` gains a lock as defense in depth — see
   Architecture. The PAT provisioning step documented in `docs/deploy/
   scheduled-run.md` (sprint 004) remains operator-only and is
   explicitly out of this ticket's scope — the ticket does everything
   else code-side and leaves that one manual step documented, not
   skipped.
3. **Triage the 33 (issue 24).** Per-source investigation producing one
   of four dispositions per source: fixed (a real bug found and
   corrected), re-typed (wrong `adapter_type`, corrected — e.g.
   `sd-river-park-foundation` to `tec_rest`), marked headless (needs
   `fetch_strategy = "headless"`, now installable per track 2), or
   disabled with a documented reason (`enabled = false  # disabled:
   ...`, matching the existing convention in `jointheleague.toml`/
   `olivewood-gardens.toml`). Live network probing is used for
   diagnosis; only fixture-based tests are committed.
4. **Register the verified feeds (issue 25).** ~20 new source TOMLs
   against `tec_rest`/`ical`/`localist`, using each feed's already
   live-verified endpoint from the issue. Balboa Park's park-wide
   calendar overlaps organizations already scraped individually (Fleet,
   Nat, etc.) — existing cross-source dedup (`normalize/dedup.py`)
   handles this structurally by title+date+venue, so no new mechanism is
   needed, but it is noted as an accepted, imperfect match (see Open
   Questions). New orgs without a `partners.json` match display with
   their scraped `org_name` and no logo/partner link — this is already
   the tested, non-fatal behavior of `normalize/partners.py`'s
   `find_partner`; expanding the actual partner roster is issue 32's
   job, explicitly out of scope here. LibCal/NPS-API feeds are
   registered only if the existing plain `ical` adapter consumes their
   iCal URLs unchanged; otherwise deferred, not engineered new.

## Success Criteria

- A fixture event written with adult-only language (e.g. "for working
  professionals") enriches `relevant=True` with `age_grade_level`
  including `Adult`; the site's existing `Adult` facet filters it.
- A prompt-version change forces exactly one fresh LLM call per
  previously-cached `Event` on the next run (not a full cache wipe, not
  zero re-evaluation) — proven by a fixture test, not just asserted.
- `uv sync --extra headless` succeeds in dev and CI; a live run against
  a previously-blind Wix source returns non-empty rendered HTML.
- The weekly cron trigger is uncommented and a `workflow_dispatch` run
  of the updated workflow completes end-to-end; the one remaining
  manual step (PAT provisioning) is documented, not silently dropped.
- Every one of the ~33 previously zero-yield sources has a recorded
  disposition (fixed / re-typed / headless / disabled-with-reason);
  `sd-river-park-foundation` is `tec_rest`; `sandiego-gov`'s `org_name`/
  `site_url` mismatch is resolved.
- ~20 new source TOMLs are registered, each against a live-verified
  endpoint cited in issue 25; Balboa Park's cross-source overlap is
  documented, not silently duplicated on the site.
- The full test suite (1,433 tests at sprint start) stays green and
  fully hermetic/offline throughout; no version bump happens mid-sprint
  (`close_sprint` bumps once at the end).

## Scope

### In Scope

- `partner_scrape/enrich/llm_client.py` — `_SYSTEM_PROMPT` rewrite,
  new `PROMPT_VERSION` constant.
- `partner_scrape/enrich/cache.py` — cache entries carry and check a
  prompt version, parallel to and independent of the existing
  `_CACHE_SCHEMA_VERSION` check.
- `partner_scrape/pipeline.py` — dedicated single-worker dispatch path
  for `headless`-strategy sources (found during architecture
  self-review; the load-bearing fix required before more than one
  source can safely use `fetch_strategy = "headless"`).
- `partner_scrape/fetch/headless.py` — `PlaywrightFetcher.get()` gains
  an instance-owned lock as defense in depth.
- `.github/workflows/scheduled-run.yml` — uncomment the `schedule:`
  cron trigger; add `--extra headless` to the dependency install step.
- `pyproject.toml` / `uv.lock` — no schema change (the `headless` extra
  already exists), but the lockfile may need refreshing once the extra
  is actually installed in CI.
- `docs/deploy/scheduled-run.md` — update step 1 (merging the workflow
  used to be the only code-side prerequisite for the cron; after this
  sprint the workflow's cron is already uncommented on `main`, so the
  runbook should reflect that only the PAT steps remain).
- `partner_scrape/registry/sources/*.toml` — `fetch_strategy = "headless"`
  flags on known-blocked sources; ~33 zero-yield source dispositions
  (edits, re-types, or `enabled = false` with a reason); ~20 new source
  files for issue 25's verified feeds.
- Any adapter-level bug fix a triage investigation turns up (e.g. if
  `sdpl`'s BiblioCommons zero-yield turns out to be a real code issue,
  not a config one) — scoped narrowly to what triage actually finds,
  inside `adapters/`.
- This sprint's `design/` overlay: `docs/design/design.md`,
  `partner_scrape/enrich/DESIGN.md`, `partner_scrape/fetch/DESIGN.md`,
  `partner_scrape/registry/DESIGN.md`,
  `partner_scrape/normalize/DESIGN.md`.

### Out of Scope

- **Writing or expanding `stem-ecosystem`'s partner roster**
  (`partners_viable.csv` / `partners.json`). That is issue 32's job.
  This sprint's new source TOMLs use `org_name` values chosen to match
  `partners.json` where a match already exists, and accept the existing,
  already-tested no-match behavior (org name displays, no logo/partner
  link) where it doesn't.
- **A new LibCal or NPS-events-API adapter.** Registered only if the
  existing `ical` adapter already consumes the feed unchanged;
  otherwise explicitly deferred to a future sprint, not designed here.
- **Internships / company events** (UC-011) — a separate, ongoing
  thread, untouched by this sprint.
- **Any change to `normalize/`, `export/`, or `pipeline.py` code.**
  Nothing in this sprint's four tracks requires one — see Architecture.
- **A cost-accounting or per-run LLM budget mechanism.** The one-time
  re-enrichment cost from the gate change (~9,700 records) is a real,
  accepted, one-time spend (Migration Concerns), not a reason to build
  budget tooling this sprint — `enrich/DESIGN.md`'s existing Open
  Question about no cost accounting is unchanged.
- **`store/` wiring, yield-alert delivery channels, or any other
  standing open question** not directly implicated by these four
  issues.

## Test Strategy

Fixture-based and hermetic wherever the change is code (the existing
1,433-test convention: no network, `playwright` importable-or-not both
supported). Specifically:

- **Gate + cache (issue 22):** a `FixtureLLMClient`-driven test proves
  an adult-audience-worded fixture event now enriches `relevant=True`;
  a existing K-12 noise fixture (a gala, a closure notice) still
  enriches `relevant=False` — the gate widens, it does not disable. A
  cache-versioning test proves a `PROMPT_VERSION` bump forces exactly
  one fresh LLM call for a previously-cached `Event` whose content
  hash is unchanged (matching `_CACHE_SCHEMA_VERSION`'s existing
  call-counting test convention in `enrich/cache.py`'s test module),
  and that an *unbumped* prompt version still hits cache normally.
- **Ops reactivation (issue 23):** the committed suite cannot prove a
  real browser fetch succeeds — that is inherently a live check. It
  does prove the deferred-import discipline still holds (`fetch/
  headless.py`'s existing tests keep passing whether or not
  `playwright` is actually installed in the environment they run in)
  and, new this sprint, two concurrency properties: that
  `PlaywrightFetcher.get()` never lets two calls overlap (a fixture
  test drives two threads calling `.get()` on one shared instance with
  a fixture `page_factory` whose `goto`/`content` are instrumented to
  detect interleaving), and that `pipeline.run()` dispatches every
  `headless`-strategy source to the same worker thread (a fixture test
  records `threading.current_thread()` inside the fixture
  `page_factory` across 2+ headless-flagged sources). What no fixture
  can prove is Playwright's own real thread-affinity behavior — a
  fixture double has no opinion about which thread called it — so that
  is exclusively a pre-close live-validation concern, not a gap left
  uncovered by choice. Pre-close, required live validation (not a
  committed test): `uv sync --extra headless` succeeds; a real fetch
  against one newly-flagged Wix source returns non-empty rendered
  HTML; a live run with 2+ headless sources active completes with no
  cross-attributed content and no Playwright/thread-related error; a
  `workflow_dispatch` run of the updated workflow completes and the
  job summary shows a per-source yield report.
- **Triage (issue 24):** live network probing is explicitly allowed
  (and necessary) for diagnosis per source, but nothing committed to
  the suite depends on network access — any adapter-level fix found
  along the way gets a fixture-based regression test the same as any
  other adapter change; a pure TOML re-type/disable needs no new test
  beyond the registry loader's existing generic parsing coverage.
- **Registration (issue 25):** each new source's endpoint is
  live-verified before its TOML is committed (matching the "verified
  live" bar the issue itself sets), but, like triage, adds no new
  hermetic tests beyond what `registry/`'s existing loader tests
  already cover generically — a new `tec_rest`/`ical`/`localist` TOML
  is data, not new adapter code.
- Full suite (`uv run pytest`) must stay green after every ticket; no
  ticket may leave the suite red for a later ticket to fix.

## Architecture

**Substantial** — this sprint spans four largely independent tracks that together
touch `enrich/` (a real code change: the relevance-gate prompt and a new
`prompt_version` cache-key component), `fetch/` (a second real code change, found
during this sprint's own self-review, not scoped by the original issues: a
concurrency fix in `PlaywrightFetcher`, required before the headless path can safely
go from one flagged source to many — see below), `registry/` (~50+ TOML
edits/additions — corrections, dispositions, and new registrations), and a
cross-cutting product decision touching `normalize/`'s partner-join and
cross-source-dedup behavior (no code change, but a real policy decision worth
recording). No single module dominates or is rewritten, but the breadth is real: 4
linked issues, ~120 files touched by sprint end, a CI/ops activation with a genuine
one-time cost (the ~9,700-record re-enrichment), and an investigation ticket whose
scope is not fully known until it runs. Per this project's sizing guidance, when a
sprint is this broad it is judged by the heavier tier — this sprint's own
self-review is itself evidence for that judgment: a "compact" sizing would have
scoped the review narrowly enough to plausibly miss the `fetch/` concurrency issue
entirely.

This project has the persistent per-subsystem design-doc set enabled
(`design_docs_opt_in`), so per `architecture-authoring`'s Mode 2a the full per-doc
write-up lives in this sprint's `design/` overlay, not here:

- `design/design.md` — updates §1's project description (K-12-only → all ages),
  adds a "Sprint 014 addition" paragraph to §3, and adds four new system-wide open
  questions to §6.
- `design/enrich-DESIGN.md` — documents the widened relevance-gate prompt, the new
  `PROMPT_VERSION` cache-key component and its independence from
  `_CACHE_SCHEMA_VERSION`, and the one-time re-enrichment cost.
- `design/DESIGN.md` (root overview) — updates the `pipeline.py` bullet and adds a
  new shared concurrency convention documenting the dedicated single-worker executor
  for `headless`-strategy sources.
- `design/fetch-DESIGN.md` — documents the `PlaywrightFetcher.get()` concurrency
  fix (an instance-owned lock, defense in depth) and why the load-bearing
  thread-affinity guarantee has to live in `pipeline.py`'s dispatch instead, plus the
  throughput trade-off both accept.
- `design/registry-DESIGN.md` — documents the sprint's scale of TOML changes, the
  partial resolution of the "disabled sources accumulate with no reason" open
  question, and the `sandiego-gov` cross-field-consistency lesson.
- `design/normalize-DESIGN.md` — documents, as an explicit sprint-time decision
  rather than a code change, the accepted Balboa Park cross-source-dedup limitation
  and the accepted no-partner-match display path for newly-registered orgs.

This section is the pointer and summary; the overlay is the source of truth tickets
are derived from.

**No component/module diagram, entity-relationship diagram, or dependency graph.**
Every one of this sprint's four tracks activates, corrects, extends, or hardens
*existing* wiring — no new module is created, and no new cross-module dependency is
introduced: the gate change and its cache-key addition stay inside `enrich/`; the
concurrency fix touches two places (`pipeline.py`'s existing headless-dispatch logic
gains a second executor variable, `PlaywrightFetcher.get()` gains a lock) but adds
no new edge — `pipeline.py` already depends on `fetch/` and already branches on
`fetch_strategy`, so a second executor inside that same existing function is a
change in *degree* (how dispatch is done), not a new dependency or a new component;
registry growth is data, consumed the same way every existing source's data already
is. No dependency direction changes, and the `Opportunity`/`Event` data models are
unchanged. This is the same shape of exception `architecture-authoring` and sprint
020 both establish precedent for: many existing modules touched for independent,
non-composing reasons, with the omission stated rather than silent. A diagram of
"many TOML files feed the registry loader, which pipeline.py already reads" or
"pipeline.py now has two executors instead of one, and PlaywrightFetcher gained a
lock" would not clarify anything beyond what §3's subsystem map in
`design/design.md` and the root `design/DESIGN.md`'s §2 already show, both updated
in place rather than diagrammed.

### Architecture Overview

| Area | Change | Use cases served |
|---|---|---|
| `enrich/llm_client.py` | `_SYSTEM_PROMPT` rewritten (K-12-only → any audience); new `PROMPT_VERSION` constant | SUC-001, SUC-002 |
| `enrich/cache.py` | Cache entries carry and independently check `prompt_version` alongside the existing `schema_version` | SUC-002 |
| `site/src/components/OpportunityFilters.astro` (site repo, unchanged) | Existing `Adult` facet now has non-trivial data to filter | SUC-003 |
| `pipeline.py` | `headless`-strategy sources dispatched through a new, dedicated single-worker executor instead of the main 8-worker one (the load-bearing thread-affinity fix) | SUC-004 |
| `fetch/headless.py` | `PlaywrightFetcher.get()` gains an instance-owned `threading.Lock` as defense in depth | SUC-004 |
| `.github/workflows/scheduled-run.yml` | `schedule:` cron trigger uncommented; `--extra headless` added to the dependency install step | SUC-005 |
| `docs/deploy/scheduled-run.md` | Updated to reflect the code-side prerequisite (merging the uncommented workflow) is now satisfied | SUC-005 |
| `partner_scrape/registry/sources/*.toml` (known-blocked sources) | `acquisition_policy.fetch_strategy = "headless"` flags added | SUC-004 |
| `partner_scrape/registry/sources/*.toml` (~33 zero-yield sources) | Fixed / re-typed / flagged headless / disabled-with-reason dispositions; `sd-river-park-foundation` and `sandiego-gov` corrected | SUC-006 |
| `partner_scrape/registry/sources/*.toml` (~20 new files) | New `tec_rest`/`ical`/`localist` registrations against live-verified endpoints | SUC-007 |
| `partner_scrape/normalize/*` (unchanged, exercised) | Existing dedup and partner-join behavior confirmed sufficient for Balboa Park overlap and no-match orgs | SUC-008 |
| `partner_scrape/adapters/*` (contingent) | Any real bug a triage investigation finds, scoped narrowly | SUC-006 |

### Design Rationale

- **Decision: a new, independent `prompt_version` cache-key component, not a reuse of
  `_CACHE_SCHEMA_VERSION`.** *Context:* the gate-widening prompt change (issue 22)
  needs to force re-evaluation of ~9,700 pre-existing cache entries whose stored
  `relevant` verdict was computed under the old, narrower prompt; `content_hash`
  deliberately does not cover the prompt text (only an event's input fields), so it
  cannot detect this. *Alternatives considered:* bump `_CACHE_SCHEMA_VERSION` instead
  — rejected, because that constant's entire documented purpose is "is the *stored
  value's shape* still what this code expects," a question about `EnrichmentResult`'s
  dataclass fields, orthogonal to whether the *judgment* those fields hold is still
  valid under the current prompt; clear the whole cache directory — rejected as the
  issue's own fallback option, but strictly worse than a targeted version bump: it
  would force re-evaluation of every record including the ~90% whose verdict the
  prompt change does not actually affect, for no correctness benefit. *Why this
  choice:* a second, independently-checked version integer preserves the "orthogonal
  signal, checked independently" principle `_CACHE_SCHEMA_VERSION` was already built
  around, extended rather than violated. *Consequences:* one more field per cache
  entry; a future change that touches both prompt semantics and `EnrichmentResult`'s
  shape in the same sprint bumps both constants, which is harmless (both checks
  agree on the outcome) and costs only conceptual bookkeeping, not behavior.
- **Decision: ops reactivation (issue 23) needs exactly two small code changes — a
  dedicated single-worker dispatch path for headless sources in `pipeline.py`, and a
  defense-in-depth lock in `PlaywrightFetcher.get()` — plus deployment and data
  changes, not a rebuild of the fetch layer.** *Context:* the issue's acceptance
  sketch reads like it might need new engineering ("browser-fetch fallback... beyond
  the existing Wix use case"), but `fetch/headless.py`'s `PlaywrightFetcher` and
  `pipeline.py`'s per-source `fetch_strategy` dispatch are both already complete and
  tested (sprint 003/005); only one source (`sandiego-air-space.toml`) currently
  uses the flag, which is why a real gap survived unnoticed: `PlaywrightFetcher`
  shares one browser page across every headless-flagged source with no
  synchronization, and Playwright's sync API additionally expects one consistent
  driving thread — both safe only because concurrent, multi-threaded access has
  never been possible with a single flagged source — found during this sprint's own
  self-review, not the original issue text. *Alternatives considered:* a lock inside
  `PlaywrightFetcher` alone, with no `pipeline.py` change — rejected once the
  thread-affinity requirement was identified: a lock prevents overlap but cannot
  guarantee *which* thread a `ThreadPoolExecutor` hands a given task to, and only the
  dispatcher controls that; extend `PlaywrightFetcher` with per-source timeout/retry
  tuning while touching it anyway — rejected as scope creep with no issue-driven
  justification, `fetch/DESIGN.md`'s existing Open Question 4 already flags that as
  a future need, not this sprint's; ship the ops track without either fix and flag
  only one or two headless sources to stay under the concurrency risk — rejected,
  since it would defeat the issue's own point (9 Wix sites plus more blocked
  sources) for the sake of avoiding a small, well-scoped fix. *Why this choice:*
  fixing the actual gap means touching exactly four things — deployment (playwright
  installed), data (more sources flagged), and the one latent correctness bug that
  flagging more sources would otherwise expose, fixed at both the layer that owns
  the shared state (`fetch/`) and the layer that controls thread assignment
  (`pipeline.py`) — nothing more, matching the codebase's own "configuration is
  data; environment is read in one place" convention (`design.md` §5) for the first
  two, and its "no shared mutable state without a clear owner" boundary principle
  for the third and fourth. *Consequences:* this sprint's ops track carries two
  small, well-contained code changes (see `fetch-DESIGN.md`'s and the root
  `DESIGN.md`'s own Design Rationale entries for the full alternatives analysis)
  plus real deployment risk (a first-ever CI installation of a browser binary, a
  first-ever unattended cron run) — see Migration Concerns.
- **Decision: register Balboa Park and accept its cross-source-dedup imperfection,
  rather than deferring it or building a stronger identity match.** *Context:* Balboa
  Park's park-wide calendar (170 upcoming events) covers institutions already scraped
  individually; `normalize/dedup.py`'s `normalized_title + date + normalized_venue`
  identity will merge exact-title matches and miss near-title matches. *Alternatives
  considered:* defer Balboa Park to a future sprint pending a stronger identity
  match — rejected; the source is independently valuable (Workshop/Lecture/Kid
  Friendly programming from institutions with no direct source of their own) and the
  imperfect-merge outcome (occasional duplicate publication, never a missing event)
  is the same failure mode `normalize/DESIGN.md` already documents and accepts
  project-wide, not a new risk category; build a stronger cross-source identity this
  sprint — rejected as scope creep on `normalize/` with no issue driving it, and
  `normalize/`'s explicit non-goal is staying out of this sprint's four tracks unless
  a track requires it. *Why this choice:* registering now and measuring the actual
  duplicate rate against a live export is cheaper and more honest than speculatively
  engineering a fix for a problem whose real size is unmeasured. *Consequences:* some
  events may briefly double-publish until measured and, if material, addressed in a
  future sprint (see `normalize-DESIGN.md`'s Open Questions).
- **Decision: new source registrations do not touch `partners.json`; issue 32 owns
  the roster.** *Context:* issue 25's own text says "register each org in the partner
  roster too where absent (see issue on roster expansion)," and issue 32
  (`partner-roster-expansion-and-housekeeping`) exists, unlinked to this sprint, and
  explicitly covers roster additions plus a URL fix for the Water Conservation Garden
  that overlaps this sprint's own `thegarden.org` registration. *Alternatives
  considered:* write `partners.json` directly from this sprint's registration ticket
  — rejected; `normalize/partners.py`'s own docstring states the roster is read-only
  from this repo's perspective, an existing, deliberate boundary, and `partners.json`
  itself lives in the sibling `stem-ecosystem` repo, not this one — writing it would
  cross a repo boundary this sprint has no other reason to cross. *Why this choice:*
  respecting the existing read-only boundary and the issue-level scope split (25 vs.
  32) keeps this sprint's registration ticket a same-repo, same-boundary change; the
  already-tested no-match display path means shipping the sources now costs nothing
  functionally. *Consequences:* several newly-registered orgs display without a
  partner logo/link until issue 32 lands — an accepted, temporary, cosmetic gap, not
  a data-loss risk.

### Migration Concerns

- **One-time re-enrichment cost (~9,700 records).** The `PROMPT_VERSION` bump forces
  exactly one fresh Anthropic API call per previously-cached event on the first run
  after this sprint merges. This is real, bounded, one-time spend — not an ongoing
  cost increase — and is the direct, accepted price of correcting the K-12-only gate;
  no code mitigates it because the correction requires re-judging every previously
  gated record.
- **A pre-existing latent correctness bug becomes live risk if the fix ships
  without being verified.** `PlaywrightFetcher`'s unsynchronized, potentially
  cross-thread shared page has been present since sprint 003/005 but never
  exercised as unsafe (never more than one headless source). This sprint is the
  first to make the hazard real; the two-layer mitigation (`pipeline.py`'s
  dedicated single-worker dispatch, `PlaywrightFetcher`'s lock) must actually run
  and be verified — SUC-004's fixture tests plus a live run with 2+ headless
  sources active before close — not just exist as a ticket checkbox. A dispatch
  change that is present but untested against real concurrent, multi-source
  headless dispatch would leave the sprint's core ops-reactivation goal resting on
  an unverified assumption.
- **First-ever CI installation of a browser binary.** `uv sync --extra headless`
  installing Playwright (and, transitively, a Chromium binary) in the scheduled
  workflow's CI runner is a new failure surface (install time, disk/memory footprint,
  a new external download dependency) that has never been exercised in this project's
  CI before. Pre-close live validation (Test Strategy) is required specifically to
  catch this before the cron is trusted to run unattended.
- **First-ever unattended weekly run.** Every run to date has been a manual
  `workflow_dispatch`. Re-enabling `schedule:` means the first genuinely unattended
  run is this sprint's own validation run — mitigated by requiring a successful
  `workflow_dispatch` run first (SUC-005's acceptance criteria) before trusting the
  cron, matching `docs/deploy/scheduled-run.md`'s own existing "only after a real
  end-to-end run like this succeeds should the weekly cron be trusted" guidance.
- **No backward-incompatible change to `EnrichmentResult`, `Opportunity`, or any
  exported JSON schema.** The `prompt_version` field is internal to the cache's
  on-disk entry format, not exported; a consumer of `opportunities.json` sees no
  schema change, only more/different records.
- **Registry growth is purely additive and reversible.** Every new or corrected
  source is a TOML file; `enabled = false` remains the standing, non-destructive way
  to back out any registration that turns out to be wrong, matching the existing
  registry convention (no file deletion, history preserved).

## Use Cases

`docs/design/usecases.md`'s twelve existing UCs predate this sprint's
four issues. Matching sprint 013's precedent, each SUC below parents to
the closest existing UC by shape rather than minting a new top-level UC.

### SUC-001: Widen the relevance gate to all ages
Parent: UC-004

- **Actor**: Engine
- **Preconditions**: An event record has been enriched by
  `enrich.enricher.LLMEnricher` (LLM call or cache hit).
- **Main Flow**:
  1. `enrich/llm_client.py`'s `_SYSTEM_PROMPT` asks the model to judge
     `relevant` as "a STEM learning opportunity for any audience
     (children, teens, families, adults, educators, college-bound
     students)".
  2. Noise rejection is unchanged: non-STEM recreation, fundraising
     galas, closure notices, press releases, navigation pages, and
     records with no evaluable content are still `relevant=False`.
  3. `age_grade_level` continues to populate `Adult` (already a valid
     value in `_AGE_GRADE_LEVEL_VALUES`) for adult-audience content.
  4. The relevance gate in `LLMEnricher.enrich()`'s fourth pass still
     drops `relevant=False` events unless `event.trusted` — unchanged.
- **Postconditions**: An event previously rejected only for being
  adult-audience now survives the gate; a genuinely non-STEM or noise
  record still does not.
- **Error Flows**: Unchanged — a failed LLM call still fails open
  (`relevant=True` via the taxonomy fallback), never drops a record for
  an LLM outage.
- **Acceptance Criteria**:
  - [ ] Fixture test: an adult-audience-worded event (e.g. "a
        professional development workshop for working engineers")
        enriches `relevant=True` with `Adult` in `age_grade_level`.
  - [ ] Fixture test: an existing noise fixture (gala, closure notice,
        nav page) still enriches `relevant=False` — the gate widens
        audience, it does not loosen noise rejection.
  - [ ] A live comparison run (pre-close, not a committed test) shows a
        yield jump for `extendedstudies-ucsd`, `extension-ucsd`,
        `salk`, `qualcomm`, `grossmont`, `sandiego-gov`, `wccsd`,
        matching the issue's expected sources.

### SUC-002: Invalidate stale cached relevance verdicts after a prompt change
Parent: UC-004

- **Actor**: Engine
- **Preconditions**: `enrich/cache.py` holds pre-existing entries
  written under the old (K-12-only) system prompt; `_SYSTEM_PROMPT` has
  changed (SUC-001).
- **Main Flow**:
  1. `enrich/llm_client.py` gains a `PROMPT_VERSION` constant, bumped
     alongside a semantic change to `_SYSTEM_PROMPT`.
  2. `EnrichmentCache.store()` writes the current `PROMPT_VERSION` into
     each entry, alongside the existing `schema_version` and
     `content_hash`.
  3. `EnrichmentCache.lookup()` treats a missing or mismatched
     `prompt_version` as a miss — independently of, and in addition to,
     the existing `content_hash`/`schema_version` checks — forcing
     exactly one fresh LLM call per affected `Event`.
  4. An entry written under the new prompt version, with an unchanged
     content hash, is treated as a hit on the next run (no repeated
     re-enrichment).
- **Postconditions**: Every one of the ~9,700 previously-enriched
  records is re-evaluated against the new prompt exactly once; none is
  silently stuck on a stale K-12-only verdict.
- **Error Flows**: A cache file predating this change entirely (no
  `prompt_version` key at all) is treated as a miss, the same as any
  other version mismatch — matching the existing precedent for a
  pre-sprint-009 entry with no `schema_version` key.
- **Acceptance Criteria**:
  - [ ] Fixture test: a cache entry written at the old
        `PROMPT_VERSION` is a miss under the new one, even though its
        `content_hash` is unchanged; the LLM client is called exactly
        once more for that event.
  - [ ] Fixture test: a cache entry already at the current
        `PROMPT_VERSION` remains a hit (no spurious re-enrichment).
  - [ ] Fixture test: `prompt_version` and `schema_version` are
        independent signals — bumping one without the other still
        forces exactly the intended re-check, not both or neither.

### SUC-003: Visitor filters adult-audience content via the Adult facet
Parent: UC-012

- **Actor**: Visitor
- **Preconditions**: SUC-001/SUC-002 have run at least once against the
  live registry; `opportunities.json` now includes previously-gated
  adult-audience records with `age_grade_level` including `Adult`.
- **Main Flow**:
  1. Visitor opens the Opportunities directory.
  2. The existing `Adult` age facet (already present in
     `OpportunityFilters.astro`) now has a non-trivial count.
  3. A family wanting only youth programming unchecks `Adult` and sees
     the K-12-oriented set essentially unchanged from before this
     sprint; a visitor wanting the adult/professional programs checks
     it and finds Salk, Qualcomm, UCSD Extended Studies, and similar
     newly-published.
- **Postconditions**: The site serves its full stated audience
  ("learners of all ages") without forcing a family to wade through
  adult-only content by default.
- **Error Flows**: None new — this is exercising an existing site
  facet against newly-published data, no site code changes.
- **Acceptance Criteria**:
  - [ ] A live/staged export shows a non-zero, materially larger
        `Adult`-tagged opportunity count than before this sprint.
  - [ ] No site code change is required or made; the existing facet
        UI is confirmed sufficient.

### SUC-004: Reactivate headless fetching for JS-rendered and blocked sources
Parent: UC-002

- **Actor**: Engine / Operator
- **Preconditions**: A source's site is client-rendered (Wix) or
  returns 403 to a plain HTTP request; `fetch/headless.py`'s
  `PlaywrightFetcher` and `pipeline.py`'s `fetch_strategy` wiring
  already exist; only one source uses the strategy today.
- **Main Flow**:
  1. Operator runs `uv sync --extra headless` in dev/CI/the scheduled
     workflow, installing the previously-absent `playwright` package.
  2. `pipeline.run()` gains a second, dedicated single-worker
     `ThreadPoolExecutor` for `headless`-strategy sources — every such
     source's `_run_one_source` call runs on that one consistent
     worker thread, one at a time, never on the main 8-worker pool.
     `PlaywrightFetcher.get()` additionally gains an instance-owned
     lock as defense in depth. Together these are a one-time fix,
     required before flagging more than one source headless is safe
     (see Architecture / Design Rationale).
  3. Operator sets `acquisition_policy.fetch_strategy = "headless"` in
     a known-blocked source's TOML (the 9 Wix partner sources, plus
     newly identified blockers: aquarium.ucsd.edu, Gateway Galaxy
     webstores, ActiveNet REST, zoo.sandiegozoo.org kids-programs,
     Chula Vista/National City library sites, North County city rec
     sites, Mathnasium, AoPS, where each is already a registered
     source).
  4. `pipeline.run()`'s existing per-source `fetch_strategy` read
     still selects `PoliteFetcher(fetcher=PlaywrightFetcher())` over
     the static `UrllibFetcher` for those sources — unchanged — but
     now submits that work to the new dedicated executor instead of
     the shared one.
  5. A real run now retrieves rendered HTML for that source instead of
     an empty shell or a 403, safely even when several headless sources
     are flagged alongside every static source in the same run.
- **Postconditions**: Previously-blind sources produce non-empty raw
  HTML for their adapter to parse; no headless fetch's content is ever
  attributed to a different headless fetch's URL; no headless fetch
  raises a Playwright thread-affinity error.
- **Error Flows**: `PlaywrightNotInstalledError` (already implemented)
  still fires with an actionable message if a `headless`-flagged source
  is run in an environment where the extra was not installed — this
  sprint's CI/dev change prevents that in the environments that matter,
  it does not remove the guard.
- **Acceptance Criteria**:
  - [ ] `uv sync --extra headless` succeeds in dev and CI.
  - [ ] Fixture tests for `fetch/headless.py` keep passing whether or
        not `playwright` is actually importable in the test
        environment (deferred-import discipline unchanged).
  - [ ] Fixture test: two threads calling `.get()` on one
        `PlaywrightFetcher` instance concurrently never interleave —
        proven by an instrumented fixture `page_factory`, not merely by
        the lock's presence.
  - [ ] Fixture test: `pipeline.run()` with 2+ active sources flagged
        `headless` dispatches every one of them via the same worker
        (asserted, e.g., by recording `threading.current_thread()`
        inside a fixture `page_factory`) — this is what a fixture can
        prove about thread affinity; it cannot exercise Playwright's
        own real thread-affinity behavior, which only a live run can
        (next bullet).
  - [ ] Live validation (pre-close): at least one previously-403/blank
        source now returns non-empty rendered HTML through the
        headless path; a live run with 2+ headless sources active
        completes with no cross-attributed content and no
        Playwright/thread-related error.

### SUC-005: Run the weekly scrape unattended
Parent: UC-007

- **Actor**: Operator (via scheduler)
- **Preconditions**: `.github/workflows/scheduled-run.yml`'s `schedule:`
  trigger is currently commented out; `SITE_REPO_TOKEN`/
  `ANTHROPIC_API_KEY` provisioning is documented in `docs/deploy/
  scheduled-run.md` (sprint 004) but is an operator action, not
  something this ticket performs.
- **Main Flow**:
  1. This sprint uncomments the `schedule: - cron: '0 13 * * 1'` block
     and adds `--extra headless` to the workflow's dependency install
     step.
  2. Once merged to `master`, GitHub evaluates the weekly trigger (it
     only evaluates `schedule` triggers for files present on the
     default branch).
  3. An operator still performs the one remaining manual step — PAT
     provisioning, per the existing runbook — before the first
     unattended Monday run can succeed.
  4. A `workflow_dispatch` run (available immediately, no PAT
     prerequisite blocks manual testing of everything except the
     cross-repo publish step) exercises the rest of the pipeline
     end-to-end.
- **Postconditions**: The site can refresh weekly with zero per-run
  human effort, once the one documented operator step is done.
- **Error Flows**: A missing `SITE_REPO_TOKEN` still fails fast with
  the existing actionable `::error::` message (unchanged) rather than
  the opaque `actions/checkout` failure.
- **Acceptance Criteria**:
  - [ ] `scheduled-run.yml`'s cron trigger is uncommented on this
        sprint's branch.
  - [ ] `docs/deploy/scheduled-run.md` is updated to reflect that the
        code-side prerequisite (merging the uncommented workflow) is
        now satisfied by this sprint, leaving only the PAT steps.
  - [ ] A `workflow_dispatch` run of the updated workflow completes
        end-to-end (pre-close live validation).

### SUC-006: Triage a zero-yield source to a resolved disposition
Parent: UC-008

- **Actor**: Operator
- **Preconditions**: A source in the registry returned zero adapter-
  level records (`found == 0`) in the last run; ~33 of 99 sources are
  in this state, including `sdpl`, `cleansd`, `ilacsd`, `eefkids`,
  `sandiegozoowildlifealliance`, `sdgirlscouts`, `ecovivarium`,
  `agua-hedionda`, `sdcwa`, `sdfutures`, `robolink`, `lajollalibrary`,
  `usasciencefestival`, four ATS boards, `sd-river-park-foundation`
  (mis-typed `generic_html`, should be `tec_rest`), and `sandiego-gov`
  (org_name/site_url mismatch).
- **Main Flow**:
  1. Operator regenerates a current per-source yield report (a live
     dry-run against the real registry — the committed
     `dev/output/.../yield-history.json` predates this sprint's
     2026-08-30 research run and is not authoritative for the current
     33) to get the exact current list.
  2. For each zero-yield source, Operator probes live (endpoint check,
     platform detection, site-still-exists check) and assigns one
     disposition: **fixed** (a real bug, corrected, with a regression
     test), **re-typed** (wrong `adapter_type`, corrected —
     `sd-river-park-foundation` to `tec_rest` against
     `https://sandiegoriver.org/wp-json/tribe/events/v1/events/`),
     **marked headless** (needs `fetch_strategy = "headless"`, per
     SUC-004), or **disabled with reason**
     (`enabled = false  # disabled: <reason>`, matching the existing
     `jointheleague.toml`/`olivewood-gardens.toml` convention).
  3. `sandiego-gov`'s `org_name` ("Discover U at San Diego Public
     Library", which belongs to a different org entirely) is corrected
     to match its actual `site_url` (sandiego.gov), or the TOML is
     split if it was conflating two organizations.
  4. ATS boards (`boundlessbio`, `gossamerbio`, `elementbiosciences`,
     `shieldai`) are re-verified live; a genuinely-empty board (zero
     open matching jobs) is left `enabled = true` with a code comment
     confirming the token is still live, not disabled.
- **Postconditions**: No source is silently zero-yield with no
  explanation; every one of the ~33 has a disposition an operator (or a
  future triage pass) can read directly off its TOML.
- **Error Flows**: A source found to be genuinely defunct or moved with
  no successor is disabled with that reason recorded, never silently
  deleted (registry convention: disabling is a data edit, not a file
  deletion, so history is preserved).
- **Acceptance Criteria**:
  - [ ] Every source in the current zero-yield set has one of the four
        dispositions recorded, verifiable by reading its TOML.
  - [ ] `sd-river-park-foundation.toml` is `adapter_type = "tec_rest"`
        with a working `api_base`.
  - [ ] `sandiego-gov.toml`'s `org_name` and `site_url` refer to the
        same organization.
  - [ ] Any adapter-level fix found along the way has a fixture-based
        regression test; live probing itself is never committed as a
        test.

### SUC-007: Register a verified structured feed against an existing adapter
Parent: UC-008

- **Actor**: Operator
- **Preconditions**: A feed endpoint has been live-verified (per issue
  25's list: Balboa Park, cafirst.org, SD Coastkeeper, YMCA of San Diego
  County, Comic-Con Museum, SD Archaeological Center, SHPE San Diego,
  navalstem.us, thegarden.org, Junior Achievement of San Diego via
  `tec_rest`; SD County Parks, SD Astronomy Association, Mission Trails
  Regional Park Foundation, Surfrider SD, SWE San Diego, California DI,
  Oceanside/Coronado libraries, Cabrillo National Monument Foundation
  via `ical`; additional UCSD Localist `group_id`s beyond Birch via
  `localist`); none of these currently has a source file.
- **Main Flow**:
  1. Operator writes a new `partner_scrape/registry/sources/<slug>.toml`
     per feed, setting `adapter_type` to whichever of `tec_rest`/
     `ical`/`localist` the feed already fits, `config` to the
     live-verified endpoint, and `org_name` matching `partners.json`'s
     `name` field where that org is already a partner (checked against
     the local `site/src/data/partners.json` copy).
  2. Where the org has no `partners.json` match, `org_name` is still
     chosen sensibly (it will display as-is, with no partner_id/logo —
     the existing, tested `normalize/partners.py` behavior); the org is
     noted as a candidate for issue 32's roster expansion, not added to
     the roster here.
  3. Operator runs the source once (`partner-scrape --dry-run`) to
     confirm non-zero, dated output before committing.
  4. LibCal (Carlsbad, Escondido) and the NPS events API (Cabrillo) are
     registered via the plain `ical` adapter only if it consumes their
     iCal URLs unchanged; otherwise left unregistered with a note
     deferring them (no new adapter is written this sprint).
- **Postconditions**: ~20 new sources contribute events on subsequent
  runs, each traceable to a live-verified endpoint at registration time.
- **Error Flows**: A feed that turns out not to actually fit the
  assumed adapter cleanly (a response shape mismatch discovered at
  dry-run time) is either fixed with a config adjustment or deferred
  with a note — never force-registered against a broken config.
- **Acceptance Criteria**:
  - [ ] Each new TOML's endpoint was live-verified (endpoint reachable,
        non-zero records) before commit.
  - [ ] `org_name` matches `partners.json` for every org already in the
        roster; non-matches are listed for issue 32, not silently
        dropped.
  - [ ] LibCal/NPS are registered only if the plain `ical` adapter
        already handles them; otherwise explicitly deferred, not
        engineered.

### SUC-008: Avoid duplicate opportunities from an institutional calendar
Parent: UC-005

- **Actor**: Engine
- **Preconditions**: Balboa Park's park-wide TEC calendar (170 upcoming
  events, covering many institutions already scraped individually — the
  Fleet, Nat, and others) is registered (SUC-007).
- **Main Flow**:
  1. `normalize/collapse.py` and `normalize/dedup.py` run exactly as
     they do for any other pair of sources — no new mechanism is added.
  2. A Balboa Park calendar entry and an individually-scraped
     institution's own listing for the same real-world event merge into
     one `Opportunity` when `normalized_title + date + normalized_venue`
     match; `sources` records both organizations.
  3. A Balboa Park entry whose title differs materially from the
     institution's own listing (a real, known limitation of
     `dedup.cross_source_identity()`, documented in `normalize/
     DESIGN.md`'s Open Questions) does not merge, and both publish
     separately.
- **Postconditions**: Exact-match duplicates collapse; near-miss
  duplicates are an accepted, pre-existing limitation, not a new defect
  introduced by this sprint.
- **Error Flows**: None new — this exercises existing dedup logic
  against a new data source, not a new code path.
- **Acceptance Criteria**:
  - [ ] A live/staged export after registering Balboa Park shows at
        least one collapsed cross-source match against an existing
        Fleet/Nat source's own listing for the same event.
  - [ ] No change is made to `normalize/collapse.py` or `normalize/
        dedup.py`; this is confirmed to be unnecessary, not merely
        skipped.

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

| # | Title | Issue | Depends On |
|---|-------|-------|------------|
| 001 | All-ages relevance gate and cache invalidation | 22 | — |
| 002 | Ops reactivation: Playwright install, headless dispatch fix, and weekly cron | 23 | — |
| 003 | Triage zero-yield sources | 24 | 002 |
| 004 | Register verified structured feeds | 25 | 002, 003 |

Tickets execute serially in the order listed. 001 and 002 have no
inter-dependency (gate widening and ops reactivation are independent
tracks) but are sequenced first because both "multiply everything
downstream" — a source triaged or registered against a narrower gate
or a still-broken fetch path would be re-diagnosed for no reason. 003
depends on 002 because diagnosing a zero-yield source's correct
disposition (in particular, whether it needs `fetch_strategy =
"headless"`) requires the reactivated, concurrency-safe headless path
to actually exist. 004 depends on both: it verifies each new
registration against the reactivated pipeline (002) and avoids
duplicating any source 003 already corrected (e.g.
`sd-river-park-foundation`).

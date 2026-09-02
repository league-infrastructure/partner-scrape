# Adapters

**Owner:** Eric Busboom · **Last reviewed:** 2026-09-02 (sprint 030 — `pd` extraction profile added) · **Status:** stable

---

## Revision (2026-09-02 — sprint 030 educator-PD extraction profile)

Issue 33 part 1's curated educator-PD program pages (UCSD CREATE, SD
Science Project, UCSD Math Project, Code.org regional partner,
CSTA-SD, SDSU CRMSE, Fleet educator workshops, Salk STEM Educators
Summit, Zoo teacher workshops) register through the existing
`program_page`/`program_page_multi`/`program_listing` mechanism, typed
`Professional Development / Conferences` — the reuse surface this
module's own `ProgramPageMultiAdapter` docstring already named as
expected ("sprints 029 (competitions) and 030 (educator pages) are
expected to register against directly with zero further adapter
code"). That claim holds exactly as written for `discover()`/`fetch()`/
the dispatch structure — no new adapter class, no new discovery logic.
**It does not hold for the LLM extraction prompt**, and this revision
exists because sprint 029's own Revision (above) is the direct
precedent for why: reusing an existing profile's *wording* for a
structurally different genre produces systematic, silent extraction
errors, not merely site-specific quirks (`sd-brain-bee`,
`seaperch-sd-regional`, `tritonhacks` — all three traced to
framing/vocabulary mismatches, not fetch or model failures). This
revision does the same live-verification-informed judgment sprint 029
was forced into, up front, rather than repeating its optimism.

**Why an educator-PD workshop/conference page is its own third genre,
neither `"program"` nor `"competition"`.** An educator-PD page (a
summit, a workshop series, a CSTA-SD chapter meeting) shares one
structural property with the competition genre — its primary date is
the event's own date, not an application-window open/close pair, so
`"program"`'s framing ("the application window's open date" /
"the application deadline") is the wrong lens here exactly as it was
for `sd-brain-bee`. But it shares none of the competition genre's own
vocabulary assumptions: `_FIELD_EXTRACTION_RULES_COMPETITION`'s date
guidance explicitly steers the model toward "Event Date," "Competition
Date," "Tournament Date," "Save the Date" phrasing and a
"competition/tournament" framing sentence — vocabulary a PD workshop
page does not use ("Register for our fall workshop," "RSVP by," "Summit
registration closes"), and telling the model "this is a competition or
tournament" when it plainly is not risks exactly the kind of
label-primed misreading 029's own root-cause analysis diagnosed for the
*other* direction (a program-shaped prompt on event-shaped content).
**Design decision: a third `profile="pd"`, with its own system prompt
pair, following the exact mechanical shape `profile="competition"`
already established** — no `ProgramExtractionResult` schema change (the
existing `date_start`/`date_end`/`registration_deadline`/`cost`/
`eligibility`/`is_open`/`opportunity_type` fields already cover a PD
event's shape: `date_start`/`date_end` for the workshop's own date(s),
`registration_deadline` for a stated RSVP/registration cutoff distinct
from the event date, `eligibility` for "K-12 STEM educators," grade
band, or district restriction, `audience_grades` reused to hold an
educator-audience descriptor like "K-5 teachers" or "STEM
coordinators" rather than a student grade band). No
`ProgramExtractionCache._CACHE_SCHEMA_VERSION` bump either — the
stored-entry *shape* is unchanged, only which of three prompt variants
produced it (see this section's Open Question below for the one real,
pre-existing risk this raises).

`ProgramLLMClient.extract_program`/`extract_programs`'s `profile`
parameter's accepted values become `"program"` (default) |
`"competition"` (sprint 029) | `"pd"` (this sprint) — a plain string,
not a typed enum (matching this module's existing "small, hand-curated
set, not worth over-typing" convention for comparable fields).
`program_page.py`'s `_resolve_extraction_profile()` extends its
existing single-branch check to a three-way one, still driven entirely
by data the registry already carries, still with **no new registry
`config` key**:

```python
def _resolve_extraction_profile(source: SourceConfig) -> str:
    opportunity_type = source.config.get("opportunity_type")
    if opportunity_type == "Competitions":
        return "competition"
    if opportunity_type == "Professional Development / Conferences":
        return "pd"
    return "program"
```

This is the same "select the prompt variant from the config override
value every affected source's TOML already carries" mechanism sprint
029 established, extended by one more `elif`-shaped case — not a new
mechanism. Every existing `"program"`- and `"competition"`-profile
source's behavior is byte-for-byte unchanged (neither branch's
condition can newly match a pre-existing registration).

**Reused verbatim, no new code:** `_extract_one_program()`/
`_extract_many_programs()` (the HTML-reduction, cache lookup, and
per-ref exception-isolation logic), `ProgramExtractionCache` itself,
`_map_result_to_event()`'s date/eligibility/cost/opportunity_type
mapping, and `ProgramListingAdapter`'s `config.link_selector` discovery
path (ticket 006 exception revision) for any educator-PD listing page
whose cards aren't `EVENT_PATH_RE`-shaped (a real possibility for
CSTA-SD's or Fleet's own event-listing pages — registered per-source as
needed, decided at registration time, not a mechanism change).
`program_page_multi` is available for any educator-PD source whose
page holds several session dates inline on one page rather than links
to N separate detail pages (e.g. a CSTA-SD chapter's own upcoming-
meetings list), the identical SIO-shape reuse this module's own
docstring already anticipated for "sprint 030 (educator pages)."

**Open question — pre-existing, not new to this revision, flagged
here because this sprint is the second consumer to make it matter.**
`ProgramExtractionCache`'s key is `(url, content_hash(body))` —
`profile` is not part of the key (`program_cache.py`, unchanged by
either this revision or sprint 029's). This has been true since sprint
027 and is harmless for every source registered so far, because a
given URL is registered under exactly one `config.opportunity_type`
value for its whole life. It would stop being harmless only if a
source's `opportunity_type` override were ever *changed* after a cache
entry already exists for that URL under the old profile — the cache
would silently serve the stale, wrong-profile result until the page's
own content changes. Not a risk this sprint introduces or needs to fix
(no educator-PD URL has ever been cached under a different profile),
but worth a follow-up issue given two sprints have now added a profile
without ever revisiting this — see this sprint's sprint.md Open
Questions for the recommended follow-up.

## Revision (2026-09-02 — sprint 029 competition-genre extraction fix)

Tickets 001/002's own live-verification (real network, real
`AnthropicProgramLLMClient` — a correction of both tickets' first-pass
WebFetch-only checks, recorded in their own Notes sections) found a
systematic extraction problem, not a series of unrelated site quirks: of
the sources ticket 001 registered, only `doe-science-bowl-sd`,
`congressional-app-challenge-sd`, and `cipherhacks` currently ship a
usable record; five more (`sdftc-league-play`, `botball-greater-sd`,
`sd-brain-bee`, `seaperch-sd-regional`, `tritonhacks`) and ticket 002's
`sd-math-circle` were flipped to `enabled = false` after real dry-runs
contradicted the first pass. The team-lead's cross-ticket read of the
evidence (both tickets' Notes, all six disabled sources' TOML header
comments) traced three of these failures to one shared root cause,
distinct from two other, unrelated failure classes:

- **`program_llm.py`'s `_SYSTEM_PROMPT`/`_SYSTEM_PROMPT_MULTI` and
  `_FIELD_EXTRACTION_RULES`, unchanged since sprint 027, were written for
  sprint 027's own target genre — a prose *program* page whose primary
  date is an application window (`date_start` = "the application
  window's open date", `date_end` = "the application deadline")** — and
  this framing actively misleads the model on a genuinely different
  genre, a single dated *event*:
  - `sd-brain-bee` — the fetched, reduced text plainly states "Event
    Date: February 14, 2026"; two independent extraction calls against
    that identical text both return `date_start=""`/`date_end=""`. The
    date is present; the field rules give the model nothing to
    recognize "Event Date:" as a signal worth extracting.
  - `seaperch-sd-regional` — the fetched text contains both the April 4
    2026 competition date and the March 27 2026 Technical Design Report
    submission deadline. Two independent calls both map only the TDR
    deadline into `date_end`, leaving `date_start` empty — reading "the
    application deadline" field rule literally, the TDR paperwork
    cutoff *is* the closest match on the page to "a deadline," even
    though it is not the date visitors need.
  - `tritonhacks` — the fetched text states "May 16 & 17" with no
    adjacent year; the only "2026" on the whole page is an unrelated
    footer copyright line. The model filled in a year anyway
    (`2025-05-08`, already past) rather than being given a reference
    date to reason from or a rule for inferring one.
- **`sdftc-league-play` and `botball-greater-sd`** are a different
  failure class: their fetched, reduced text contains *no calendar date
  at all* (nav/mission-statement copy for the first; day-of-week labels
  with an apparently client-side-rendered date widget for the second) —
  no prompt wording recovers a date that never reached the model. These
  are fetch/content-availability gaps, not framing gaps; this revision's
  fix is not expected to re-enable them on its own — ticket 007 (below)
  says so explicitly rather than assuming a shared cause.
- **`sd-math-circle`** is a third, unrelated failure class: `extract_programs()`
  correctly receives intact AMC/AIME/etc. dated rows in the fetched text
  (confirmed by grepping the exact reduced text sent to the LLM), but the
  page's shape — a dense ~40-week × 5-column weekly class-schedule grid,
  with the actual competition dates as scattered one-off rows *inside*
  that grid — is not "N distinct top-level program sections," the shape
  `extract_programs()`'s framing assumes. This is a grid/tabular
  extraction gap, not a deadline-vs-event-date framing gap; **explicitly
  deferred**, not attempted by this revision — see §4's Design Rationale
  below.

**Design decision: a `profile`-selected competition extraction mode,
plus one new field — no `Opportunity`/`Event` schema change, no
`normalize/run.py` change.** See §4's new Design entries and Design
Rationale blocks for the full write-up. In outline:
`ProgramLLMClient.extract_program`/`extract_programs` gain a new
keyword parameter, `profile: str = "program"`, selecting between the
existing application-window system prompt (default, unchanged — every
sprint 027/028 source's behavior is byte-for-byte identical) and a new
competition-genre system prompt, chosen by `program_page.py`'s two call
sites from data already on hand
(`source.config.get("opportunity_type") == "Competitions"`) — no new
registry `config` key. `ProgramExtractionResult` gains one new field,
`registration_deadline: str = ""`, populated only by the competition
prompt and folded into `Event.description` (mirroring sprint 028's
Camps-sold-out precedent) rather than into `start`/`end`.
`ProgramExtractionCache._CACHE_SCHEMA_VERSION` bumps 2 → 3.

**No change to `normalize/run.py`'s `DEADLINE_FIRST_TYPES` or
`export/writer.py`'s currency rule.** Confirmed by reading both before
designing on top of them, per the team-lead's explicit ask.
`"Competitions"` has been a `DEADLINE_FIRST_TYPES` member since sprint
015 for a *different*, unrelated sub-case — a `generic_html`-sourced,
`enrich/llm_client.py`-classified pitch/essay competition whose own
actionable date genuinely is a submission deadline (`export/writer.py`'s
`_DEADLINE_FIRST_STALE_POSTING_DAYS` comment names "2nd Innovation in
Women's Health Pitch Competition" as the motivating case). Removing
`"Competitions"` from that set to fix program-page-sourced single-dated
events would regress that case — out of this revision's evidence and
authority. See §4's Design Rationale for the full reasoning, including
why sprint 015's own "no real producer yet" rejection of a distinct
deadline field no longer applies now that the competition profile is a
real producer of one.

**Surface: internal.** This is a mechanism-choice correction inside
`ProgramLLMClient`'s implementation, found by tickets 001/002's own
required live-verification step — no SUC-044/SUC-045 wording changes as
a result (both already required a "correctly-dated" record; this
revision is how that gets satisfied for real, not a renegotiation of
what was promised).

## Revision (2026-09-02 — ticket 006 exception cycle)

Ticket 006's own required live-verification step (its Fix shape's step 3)
found that `ProgramListingAdapter.discover()`'s sole discovery signal —
100% delegation to `discovery.listing.discover_via_listing`, whose only
match is `discovery.sitemap.EVENT_PATH_RE` against raw `<a href>`
targets — fits neither of this sprint's two headline listing sources'
real markup. The UCSD Summer Program Finder's ~24 HS-eligible cards
(`<li data-grade="High School">…<a class="learnmore" href=…>`) link to
unrelated cross-domain program homepages with no `/program(s)?`-shaped
path segment — 0 of the 24 HS-eligible cards are among the 8 (of ~60)
links `EVENT_PATH_RE` did match. The SIO research-internships page isn't
a cards-link-to-detail-pages listing at all: its ~10 programs
(JT-SURF, MPL, CW3E, CCE LTER, …) are `<div class="page-section">`
blocks whose deadlines are inline prose directly on the summary page,
each linking out (at most) to a program homepage that doesn't itself
carry the deadline — a shape `ProgramListingAdapter`'s card→detail-page
model has no mechanism to represent, regardless of pattern tuning. This
doc's own §6 Open Questions had already named the first risk
speculatively before ticket 006's live verification encountered it for
real, for both sources at once.

**Surface reclassification.** The exception was thrown `surface:
user-visible` (framed as a conflict with SUC-032's Main Flow). The
team-lead reclassified it `internal` before dispatching this revision:
SUC-032's Main Flow describes an outcome — "one Event per listing-page
program card" — and never specifies *how* a card link is identified;
the gap is entirely inside `ProgramListingAdapter.discover()`'s
implementation strategy, a mechanism choice this sprint already owns,
not a renegotiation of anything promised to the stakeholder. No SUC-032
wording changes as a result of this revision.

**Design decision.** The live evidence rules out fixing this by
retuning `EVENT_PATH_RE` — neither target page's link shape is a path
pattern problem. Instead this revision adds two independent, additive
mechanisms, each matched to one of the two page shapes actually
observed (full write-up in §4 below):

1. A configurable CSS-selector discovery strategy for `program_listing`
   sources (`config.link_selector`), alongside — never replacing —
   `EVENT_PATH_RE` matching, for a listing whose card links are
   identified by markup structure/attributes rather than URL path shape.
2. A new `program_page_multi` adapter type for a page whose N program
   records are inline sections on the page itself rather than links to
   N separate detail pages.

Both are designed as the general, reusable capability sprints 029
(competitions) and 030 (educator pages) are already expected to build
on — see §4's "Reuse surface" note. A third, smaller change closes this
doc's own previously-speculative "discovers zero `EventRef`s silently"
Open Question generically, for every adapter type, not only the two
program families.

## Revision (2026-09-01 — sprint 028)

Issue 36 (found during sprint 027's own live verification, recorded in the previous
Revision note's neighbor, `sd-foundation-community-scholarship.toml`'s `enabled = false`
disable reason) and issue 29 (camp session extraction) both land in this sprint. Four
changes to this family, all additive:

1. **HTML-to-text reduction, closing issue 36.** `_extract_one_program`/
   `_extract_many_programs` now call the new `extract.reduce_html_to_text()`
   (`extract/DESIGN.md`'s sprint 028 section) on `raw.body` before every cache lookup and
   LLM call, instead of passing the raw fetched body straight through. This directly
   re-enables `sd-foundation-community-scholarship.toml` (`enabled = true` again this
   sprint) and the UCSD Summer Program Finder cards that previously failed the same way.
2. **`is_open`'s prompt-level definition generalizes** from "applications are open" to
   "open for enrollment/application; false if closed, full, or sold out" — see §4's
   Design Rationale below for why this is the right way to serve camp sessions' sold-out
   flags without a schema change.
3. **Two new adapter types, `activenet_camps` and `campbrain`** (a fifteenth and
   sixteenth adapter type; `docs/design/design.md`'s subsystem-map count moves fourteen
   → sixteen) — structured platform adapters for `campscui.active.com` (ActiveNet) and
   CampBrain, the two highest-priority items in issue 29's platform-adapter list. See
   §4's Design section.
4. **Pike13 (issue 29's third-priority platform) is explicitly deferred**, not designed
   here — see §4's Design Rationale and `sprint.md`'s "Deferred to a follow-up issue".

No `Opportunity`/`Event` schema change. No change to `enrich/` or `normalize/` — the
`kind in PROGRAM_EXTRACTION_KINDS` bypass sprint 027 already generalized covers every
record this sprint's adapters emit unchanged, since all of them still set
`kind="program"`.

## 1. Purpose

`adapters/` owns the translation from *one registered source* into *canonical `Event`
records*. It is a subsystem because the codebase deliberately draws a seam between "how
you talk to a particular site or API" (endlessly varied, one implementation per vendor
shape, expected to grow) and everything downstream of it (which only ever sees `Event`).
That seam is what lets a new organization be onboarded by adding a TOML file plus, at
most, one new adapter class — never by editing the pipeline, the normalizer, or the
exporter. Nothing else in the system owns per-vendor protocol knowledge; if vendor
quirks appear outside this directory, the boundary has leaked.

**(Sprint 016 ticket 004)** `robotevents.py` (new) adds an eleventh adapter type,
`robotevents` — VEX Robotics Competition (V5RC/VIQRC) and Aerial Drone Competition
tournament events, via RobotEvents API v2 (`robotevents.com/api/v2`), the first robotics
league besides FIRST this project ingests. Structurally it is `tec_rest`/`localist`'s
exact shape (probe `page=1` at a cheap `per_page`, learn `meta.last_page`, enumerate the
rest) with `leaguesync`'s auth convention (`Authorization: Bearer <token>`, via the new
`config.get_robotevents_api_key()`/`get_robotevents_url()`, mirroring
`get_tba_api_key()`/`get_tba_url()`). One documented deviation from `localist`'s
probe-failure handling: a `401` probe response raises `RuntimeError` immediately (matching
`teams/sources/tba.py`'s explicit-401-raise precedent) rather than degrading to "assume 1
page" — an auth failure is not a transient probe hiccup, and raising here is what lets
`pipeline.run()`'s existing per-source isolation catch it, rather than silently returning
zero events for a broken credential. No `ROBOTEVENTS_KEY` was available during this
ticket's execution (see `config.py`'s own docstring), so the exact `/events` request/
response shape was confirmed against RobotEvents' own published OpenAPI schema (via the
open-source `robotevents` npm client's generated types) rather than a live probe —
documented in `robotevents.py`'s own module docstring, to be re-verified live the first
time a token is provisioned.

**(Sprint 027)** Two new adapter types, `program_page` and `program_listing`, add a
twelfth and thirteenth family: **LLM extraction**, alongside Structured API and HTML.
Where every existing adapter maps a *deterministic* source (a known JSON shape, or
HTML run through `extract/`'s confidence-ranked ladder) into `Event`s, these two map an
arbitrary **prose program page** — a paid summer-research placement, a scholarship
program, an application-window announcement — by asking an LLM to extract a bespoke,
program-shaped field set {name, audience/grades, date range, application window/
deadline, paid/cost, eligibility, open/closed status} that no structured API publishes
and no deterministic ladder rung could recover. See §4 for why this lives here (as a
12th/13th adapter type) rather than as a new top-level subsystem, and for the one
documented deviation from §3's "adapters hold no instance state" invariant this family
needs for test injectability.

**(Sprint 028)** Two more adapter types, `activenet_camps` and `campbrain`, extend the
LLM-extraction family's own extension pattern one step further: where `program_page`/
`program_listing`/`program_page_multi` map an arbitrary *prose* page onto `Event`s via an
LLM call, these two map a **known camp-registration platform's** session listing — a
JSON API when the vendor exposes one cleanly, an LLM-extracted page otherwise — onto the
exact same intermediate shape (`ProgramExtractionResult`), so the existing
`_map_result_to_event` mapping serves them with zero new mapping code. See §4.

## 2. Orientation

The public contract is `base.py`'s `Adapter` Protocol: three methods, `discover` →
`fetch` → `extract`, chained by the module-level `run(source, fetcher)` function.

- `discover(source, fetcher) -> Iterable[EventRef]` resolves a `SourceConfig` into the
  set of fetchable units. For a structured API that is usually "enumerate the pages",
  sometimes after a cheap probe call; for the HTML adapters it delegates to the
  `discovery/` subsystem.
- `fetch(ref, fetcher, source) -> RawResponse` retrieves one unit through the injected
  `Fetcher`. Adapters never open sockets themselves. **(Sprint 015 ticket 003)** gained
  the `source` parameter, matching `discover()`/`extract()`, which already received it
  — see below.
- `extract(raw, source) -> Iterable[Event]` maps one raw body into zero or more `Event`s.

**(Sprint 015 ticket 003)** `fetch()`'s `source` parameter exists so every
implementation can call the new `acquisition_kwargs(source) -> dict[str, Any]` helper
(also in `base.py`) and spread its result into its own `fetcher.get()` call(s):
`fetcher.get(url, **acquisition_kwargs(source))`. `acquisition_kwargs()` reads
`source.acquisition_policy["rate_limit_seconds"]`/`["respect_robots"]`, falling back to
`PoliteFetcher.get()`'s own defaults when a source sets neither — the same
default-merge pattern `run()`'s own `max_urls` handling already uses. Before this
ticket, `fetch()` took only `(ref, fetcher)`, so no adapter's fetch call could reach a
source's acquisition policy at all; every `fetcher.get()` call site in this package's
adapters and in `discovery/sitemap.py`/`discovery/listing.py` (which import
`acquisition_kwargs` from here the same way they already import `EventRef`) now passes
it through. This is what makes `leaguesync.toml`'s `respect_robots = false` — parsed
but previously never threaded anywhere — finally reach `PoliteFetcher.get()`. See
`fetch/DESIGN.md`'s own Sprint 015 addendum for the receiving side.

`run()` is the only chaining logic and is adapter-agnostic: it looks the class up in the
`ADAPTERS` dispatch dict, instantiates it, materializes `discover()`'s output, truncates
it to the source's `max_urls` cap, then loops fetch→extract accumulating events.

Sixteen adapter types are registered today, in four families:

| Family | Types | Shape |
|---|---|---|
| Structured API | `tec_rest`, `wp_rest`, `ical`, `localist`, `bibliocommons`, `greenhouse`, `lever`, `leaguesync`, `robotevents` | Known endpoint, JSON/iCal parsing, `CONFIDENCE = 1.0` |
| HTML | `generic_html`, `listing_html` | URL discovery via `discovery/`, field recovery via `extract/`'s ladder |
| LLM extraction (sprint 027) | `program_page`, `program_listing`, `program_page_multi` | One registered page (or one crawled listing's cards, or one page read as N inline records), field recovery via a bespoke `ProgramLLMClient` call, never `extract/`'s ladder |
| **Camp platform (sprint 028)** | `activenet_camps`, `campbrain` | One registered per-organization camp-listing endpoint on a known registration platform; session records recovered deterministically when the platform exposes a parseable JSON response, else via the same `ProgramLLMClient.extract_programs()` call `program_page_multi` uses — either way, normalized into `ProgramExtractionResult` before mapping |

**(Ticket 006 exception revision) `program_page_multi`.** A third LLM-extraction type,
alongside `program_page`/`program_listing`: one registered page whose body contains N
program records as inline sections (SIO's shape — see this doc's Revision note above),
extracted with a single list-returning LLM call rather than one call per discovered
detail page. See §4's write-up.

`ats_filters.py` is a shared helper, not an adapter: the deterministic
internship / STEM / San-Diego-local classifier the two applicant-tracking-system adapters
(`greenhouse`, `lever`) use to decide whether a job posting becomes an `Event` at all.

## 3. Constraints and Invariants

- **Registration is one line in `adapters/__init__.py`.** New types are added by
  assigning into `ADAPTERS`; `base.py`'s `run()`/`get_adapter()` are never touched. If a
  change to `base.py` looks necessary to add an adapter, the new adapter is being written
  against the wrong contract — fix the adapter, not the dispatch.
- **`ADAPTERS` is populated in `__init__.py`, never in `base.py`.** Each concrete adapter
  imports from `base`, so populating the table inside `base` would create an import
  cycle.
- **Per-record error isolation inside `extract()`.** One malformed record in an otherwise
  good response is logged and skipped, never raised. This is distinct from `pipeline.py`'s
  per-*source* isolation: without it, a single bad row silently discards every other
  record in the same page.
- **`discover()` must return an eagerly-computed list, not a lazy generator with
  per-item side effects.** `run()` materializes and slices the result to enforce
  `max_urls`; a generator whose side effects only fire on iteration would have the cap
  applied after the work was already done.
- **The `max_urls` cap (`acquisition_policy.max_urls`, default 300) is enforced
  centrally and never silently.** It is the adapter-agnostic backstop against one
  pathological source (a "sitemap" that is really hundreds of blog posts) dominating a
  run's wall clock. Truncation logs the discovered count and the dropped count.
- **Adapters do not construct `Fetcher`s.** The `Fetcher` arrives as an argument, chosen
  per source by `pipeline.run()`. No adapter knows whether it is being served static
  `urllib` responses or a headless browser, and none should learn.
- **Adapters hold no instance state.** Instances are constructed fresh per `run()` call
  and every method takes what it needs explicitly. Caching anything on `self` breaks the
  assumption that a fresh instance is equivalent to a reused one.
  **(Sprint 027, documented deviation)** `ProgramPageAdapter`/`ProgramListingAdapter`
  accept optional `llm_client`/`cache` constructor arguments, defaulting to a real
  `AnthropicProgramLLMClient`/`ProgramExtractionCache` when omitted. This is a narrow,
  justified exception, not a reversal of the invariant: `get_adapter()`'s zero-arg
  `adapter_cls()` construction (`base.py`, unchanged) still produces a fully-working
  production instance, since the defaults fill in — no change to `run()`/`get_adapter()`
  was needed, matching §3's "never a change to `base.py`" rule. What the invariant
  actually protects against — a fresh instance behaving differently from a reused one —
  still holds: the constructor argument is a fixed collaborator (an LLM client and a
  content-hash cache), not per-call mutable state, the same distinction `enrich.
  enricher.LLMEnricher(llm_client, cache)` already relies on one layer up. The sole
  reason for the constructor seam is test injectability: no existing adapter has ever
  needed to call an external LLM, so there was no precedent for how a test substitutes
  a fixture for one — every other adapter's "no instance state" is enforced by having
  nothing to inject in the first place. Tests construct
  `ProgramPageAdapter(llm_client=FixtureProgramLLMClient(...), cache=...)` directly and
  call `.extract()`, bypassing `adapters.run()`/`get_adapter()` entirely — exactly how
  every other adapter's own unit tests already call `SomeAdapter().extract(raw, source)`
  directly rather than through the dispatch registry.
  **(Ticket 006 exception revision)** `ProgramPageMultiAdapter` (new, §4) takes the
  identical `llm_client`/`cache` constructor pair for the identical reason — it is not a
  new deviation, just this one's third instance.
  **(Sprint 028)** `ActiveNetCampsAdapter`/`CampBrainAdapter` (new, §4) take the same
  `llm_client`/`cache` constructor pair — their fourth and fifth instance — for their
  LLM-extraction fallback path (their deterministic-JSON path needs no LLM client at all,
  but the constructor shape stays uniform across the whole family so a source can be
  registered either way with no adapter-selection logic anywhere else).
- **Deliberate non-goal — no normalization, dedup, or taxonomy work here.** Adapters
  emit raw canonical `Event`s. Collapsing recurrences, cross-source merging, and
  controlled-vocabulary tagging belong to `normalize/`; doing any of it here would apply
  it inconsistently, only to whichever sources happened to implement it.

## 4. Design

**Data shapes.** `EventRef` is a URL plus a free-form `context` dict; it names one
fetchable unit, which for a paginated API is one *page*, not one event. `RawResponse`
carries the originating `ref` alongside `status` and `body`, so `extract()` can log which
page a malformed body came from. Both are inert dataclasses with no behavior.

**Why `discover()` exists at all.** For the structured-API adapters it is nearly trivial
— enumerate known page URLs. It is part of the contract anyway because it is the seam the
HTML adapters need: `generic_html` implements it as a sitemap diff and `listing_html` as
a listing-page crawl, both by delegating to `discovery/`, with no change to `base.py`. The
contract was designed for the harder case before that case existed.

**Confidence.** Structured-API adapters set `CONFIDENCE = 1.0` and record it through
`Event.set(field, value, source, confidence)`, populating `field_provenance`. That
provenance is what lets `normalize/`'s collapse and dedup stages pick the
best-supported record when two sources disagree. HTML adapters instead pass through the
per-field confidence tiers `extract/ladder.py` returns.

**HTML adapters are thin.** `generic_html.py` (88 lines) and `listing_html.py` (103
lines) each do only: call the matching `discovery/` entry point for URLs, fetch, hand the
body to `extract.extract_fields()`, and assemble an `Event` from the returned
`{field: (value, confidence)}` map. All the real extraction logic lives in `extract/`,
all the real URL-resolution logic in `discovery/` — this keeps the two HTML adapters
differing only in their discovery strategy, which is the actual distinction between them.

**`listing_html`'s `default_location` fallback convention. (Sprint 015 ticket 004)**
`ListingHtmlAdapter.extract()` falls back to `source.config.get("default_location", "")`
for `Event.location` only when the extraction ladder recovered no location at all —
never overriding a ladder-recovered value. This exists because some `listing_html` sites
(Fleet Science Center's Drupal `/events` listing, confirmed live) have a single fixed
venue that is never printed per-page for the ladder to recover, so every raw `Event` from
that source carried an empty `location` and could never cross-source-dedup against a
calendar aggregator (e.g. Balboa Park's park-wide TEC feed) that does record the venue —
sprint 014 ticket 004 measured this precisely (0 collapses; see that ticket's Notes).
Deliberately a registry-generic adapter behavior, not Fleet-specific code: any current or
future `listing_html` source with the same fixed-undocumented-venue shape gets the same
fix as a one-line TOML edit (`registry/DESIGN.md`'s "onboarding is a data edit, not a
code change" design point). A source with no `default_location` key reproduces
pre-ticket-004 behavior exactly. The fallback value is recorded via `Event.set()` at
`CONFIDENCE_DEFAULT_LOCATION = 1.0` — an operator-curated, known value from the registry
TOML, not a guess extracted from ambiguous markup, so it is trusted at the ladder's own
top tier rather than a lower one.

**`ical.py` hardening against two live-measured parse failures. (Sprint 016
ticket 001)** Sprint 015 ticket 005's live dry-run verification found the
two highest-yield feeds in the robots-gated batch (`county-parks`, 553 raw
VEVENTs; `sd-astronomy-association`, 677 raw VEVENTs) both returned zero
events, from two distinct `ical.py` bugs unrelated to the robots-policy
question that ticket resolved. Both fixes stay entirely inside `ical.py`:

1. **Tockify's `X-PUBLISHED-TTL:P15M`, and (ticket 002) `REFRESH-
   INTERVAL:P15M`.** Calendar-level properties whose value `icalendar`'s
   duration parser can read as 15 *months* under ISO-8601 grammar rather
   than the 15 *minutes* Tockify evidently intends, which can abort
   `Calendar.from_ical()` before a single `VEVENT` is read. Ticket 001
   shipped a targeted strip of `X-PUBLISHED-TTL:` alone; ticket 002's
   live re-verification of the `county-parks` registration (the same
   feed) found the fix necessary but not sufficient — the identical
   `P15M` value also appears on `REFRESH-INTERVAL:`, immediately
   adjacent in the same `VCALENDAR` header, still aborting the parse.
   `extract()` now strips both known lines (via `_NONSTANDARD_DURATION_RE`,
   built from the `_NONSTANDARD_DURATION_PROPERTIES` list) before the
   body reaches `from_ical()` — properties this adapter never reads
   anyway. Deliberately a targeted strip of the evidenced properties, not
   a general X-property/custom-property sanitizer: a different malformed
   property still fails loudly through the existing top-level
   `except Exception` around `from_ical()`, until a third real case
   justifies widening the list further.
2. **A `VEVENT` with more than one `RRULE` property.** `icalendar`
   returns a Python `list` for `component.get("rrule")` in this case;
   `_extract_component` previously assumed a single `vRecur` and crashed
   (`AttributeError: 'list' object has no attribute 'to_ical'`) — an
   exception type outside `extract()`'s then-existing per-`VEVENT` catch
   (`ValueError, TypeError, KeyError`), so it escaped the per-record loop
   and aborted the whole source. `_extract_component` now detects a
   list-valued `rrule_prop`, logs a warning naming how many additional
   rules were discarded, and salvages via the first rule — matching RFC
   5545's technical allowance for multiple `RRULE`s while keeping the
   expansion itself unchanged. `extract()`'s per-`VEVENT` catch is also
   widened from the three-exception tuple to `except Exception`,
   matching this module's own top-level precedent above and the §3
   per-record-isolation invariant directly — the narrower tuple was
   itself the bug that let the `AttributeError` propagate.

**ATS adapters are a filtered family.** `greenhouse` and `lever` read public job-board
JSON, then run `ats_filters.classify_posting()` to decide whether a posting is an
internship, is STEM, and is San Diego-local. Postings that survive become
`kind="internship"` Events, which are treated specially further downstream (they bypass
LLM enrichment and both normalize stages). Graduate/PhD-level postings are rejected
here; the project's audience is K-12.

**(Sprint 027) Why the new family lives inside `adapters/`, not a new top-level
subsystem.** `adapters/`'s own one-sentence purpose — "translate one registered source
into canonical `Event` records" — describes `program_page`/`program_listing` exactly;
only the *means* of extraction differs (an LLM call instead of a JSON parse or the HTML
ladder), which the `Adapter` Protocol (`discover → fetch → extract`) never constrained
in the first place. `teams/` was the precedent considered and rejected: it is a
*second, independent pipeline* precisely because a `Team` never becomes an `Opportunity`
(`partner_scrape/DESIGN.md`'s Sprint 011 note). A program page's `Event` *does* flow
through the normal `normalize.run()` → `export.writer` path (it only skips two of
`normalize/`'s internal stages — see `normalize/DESIGN.md`), so it belongs where every
other `Opportunity`-bound source's adapter lives.

**New modules, one new capability.** `adapters/program_page.py` defines
`ProgramPageAdapter` (`discover()` returns the one configured URL as a single
`EventRef`, mirroring `greenhouse.py`/`lever.py`'s "no probe-then-paginate" shape) and
`ProgramListingAdapter` (`discover()` crawls `source.config["listing_urls"]` and
returns one `EventRef` per matched card/detail link, reusing
`discovery.listing.discover_via_listing` — the same mechanism `listing_html` already
uses, since `EVENT_PATH_RE` already matches a `/program(s)?` path segment). Both share
one `extract()` implementation: check `adapters/program_cache.py`'s
`ProgramExtractionCache` by URL + content-hash (mirrors `enrich/cache.py`'s shape,
minus the `Event`-identity keying — there is no `Event` yet at fetch time, only a URL
and a page body). Unlike `enrich/cache.py`'s deliberately single-threaded writes
(`enrich/DESIGN.md`'s Constraints), concurrent writes here are safe by construction
without that same restriction: `pipeline.py`'s per-*source* `ThreadPoolExecutor` is the
only concurrency in play, each source's own `adapters.run()` call processes its
discovered refs sequentially within that one worker thread, and every cache key is a
distinct URL+hash — two threads can only ever write two different files, never the
same path, so no lock or single-threaded discipline is needed here. On a miss, call the
injected `ProgramLLMClient`
(`adapters/program_llm.py` — `enrich_program(url, body) -> ProgramExtractionResult`,
its JSON schema generated from the dataclass exactly as `enrich/llm_client.py`'s
`_build_enrichment_json_schema()` already does, per this sprint's own explicit
"reusing `enrich/llm_client.py`'s structured JSON-schema pattern" framing);
map the result onto a canonical `Event` (`kind` from the source's `program_kind`
config; `start`/`end` as the application-window open/deadline; `eligibility` and
`opportunity_type` set via `Event.set(...)`, so `normalize/`'s existing
field_provenance-presence precedence picks them up with no further code change — see
`normalize/DESIGN.md`).

**Deliberately mirrors, never imports, `enrich/llm_client.py`.** Same rationale as
`teams/sponsor_llm.py`'s sprint 013 precedent (`teams/DESIGN.md`): a second Anthropic
client sharing the injectable-Protocol/JSON-schema-from-dataclass *shape* costs one
more small module, versus reaching across the `adapters` → `enrich` layering this
codebase has never needed and does not want — `enrich/`'s own constraint that it "never
imports `normalize/taxonomy.py`" despite overlapping vocabulary is the same accepted
duplication-over-coupling trade, applied here to a sibling module instead.

**Kind, not `opportunity_type`, is this mechanism's discriminator.** A registered
source's `program_kind` config (`"internship"` or `"program"`) sets `Event.kind`
directly; `opportunity_type` is a separate, independent decision (forced to
`Work-based Learning` for `kind="internship"`, exactly as today; read from the LLM
extraction result or a fixed per-source override for `kind="program"`). This keeps the
bypass mechanism (§3's constructor note; `enrich/DESIGN.md`, `normalize/DESIGN.md`)
orthogonal to which `opportunity_type` a given program ultimately displays as — the
same separation the codebase already has between `kind`-based routing (collapse/dedup
bypass) and `opportunity_type`-based display rules (`DEADLINE_FIRST_TYPES`).

**(Ticket 006 exception revision) Selector-based listing discovery, alongside
`EVENT_PATH_RE` — never replacing it.** `discovery/listing.py` gains a sibling function,
`discover_via_selector(source, fetcher)`, used by `ProgramListingAdapter.discover()`
only when `source.config` sets `link_selector` (a CSS selector string); a source with no
`link_selector` key reproduces today's `discover_via_listing`/`EVENT_PATH_RE` behavior
exactly, so `listing_html`'s existing Fleet Science Center registration and any future
`program_listing` source whose card links genuinely are `/program(s)?`-shaped are
unaffected. The two functions share the same per-listing-page fetch loop (resolve each
`config.listing_urls` entry against `config.site_url`, GET via `acquisition_kwargs`, skip
a non-200 page with a logged warning) and differ only in how links are picked out of the
parsed tree: `EVENT_PATH_RE.search()` against every `<a href>` for the existing function,
`tree.cssselect(link_selector)` for the new one. Deliberately no separate
"grade filter" or "allow-cross-domain" config key: an operator-authored CSS selector
already expresses both "which links" and "which cards" in one string — UCSD's own
registration uses `li[data-grade*="High School"] a.learnmore`, which is simultaneously
the discovery pattern and the HS-eligibility filter, live-confirmed against the real
page markup during this revision. No cross-domain restriction is introduced because none
existed before: `EVENT_PATH_RE` already matched "any href containing the pattern,
regardless of domain" (this doc's own pre-revision Open Question said so), so a
selector-based match inherits the identical, already-accepted absence of a domain check.

**(Ticket 006 exception revision) `program_page_multi`: one page, N inline program
records.** `ProgramPageMultiAdapter` (`adapters/program_page.py`) shares
`ProgramPageAdapter`'s `discover()` verbatim — a `program_page_multi` source is still one
fixed configured URL, one `EventRef`, no probe-then-paginate step — and differs only in
`extract()`: it calls a new `ProgramLLMClient.extract_programs(url, body) ->
list[ProgramExtractionResult]` method (added to the Protocol alongside the existing
singular `extract_program`, implemented on both `AnthropicProgramLLMClient` — a second
structured-output schema wrapping the same per-record object in `{"programs": [...]}`
— and `FixtureProgramLLMClient`) and maps each returned result onto its own `Event`, via
the same field-mapping logic `_extract_one_program` already applies per result. All N
Events from one page share the same `url`/`source_id`; this is safe by construction, not
by convention, because `Event.identity_key()` never keys on `url` — it is
`(source_id, external_id)` when set, else `(source_id, normalized_title, start_date)`
(`model.py`) — so N records with N distinct titles already get N distinct identity keys
with no adapter-side bookkeeping. `ProgramExtractionCache` gains a parallel
`lookup_many`/`store_many` pair, keyed identically (URL + content hash) but storing a
JSON list instead of one object; the cache's `_CACHE_SCHEMA_VERSION` is bumped once,
which forces exactly one harmless re-extraction of any pre-revision cache entry (a cache
is a pure optimization, so a version-forced miss costs one extra LLM call, never a
correctness issue — matching this cache's own existing "missing key or stale version is
a miss, not a deserialization error" contract).

**Reuse surface for sprints 029/030.** `program_page_multi` is deliberately generic, not
SIO-specific: any future curated page whose N records live as sections on one page —
named explicitly in this sprint's own dispatch as issue 30's competition pages and
issue 33's educator-program pages — registers as a `program_page_multi` source with zero
further adapter code, the same "onboarding is a data edit" property `program_page`/
`program_listing` already have. This is this revision's answer to the dispatch's
explicit ask to "design that surface for reuse."

**(Ticket 006 exception revision) Zero-discovered-refs is no longer silent.**
`adapters/base.py`'s `run()` now logs a `logger.warning` immediately after
`refs = list(adapter.discover(source, fetcher))`, naming `source_id`, `adapter_type`,
and the zero count, whenever an enabled source's (pre-truncation) discovery yields no
refs at all — generic across all fourteen adapter types, not only the two program
families, alongside the existing max_urls-truncation warning in the same function. This
resolves this doc's own pre-revision Open Question ("a future `program_listing` source
whose card links don't contain any matched path segment... would discover zero
`EventRef`s silently") directly at its cause. It is a complement to, not a duplicate of,
`observability/yield_report.py`'s existing per-run zero-yield alert (which already flags
a source whose final Event count is zero): the yield report cannot distinguish "discover()
itself found nothing" from "discover() found candidates but every one failed fetch or
extraction" — this warning fires at the earlier, more specific point, giving an operator
looking at logs (not only a periodic yield report) the finer-grained signal for exactly
the failure mode ticket 006 hit.

**Why a Protocol rather than an ABC.** Structural typing keeps concrete adapters from
needing to inherit anything, and keeps test doubles trivial — a plain object with the
three methods is a valid `Adapter`.

**(Sprint 028) HTML-to-text reduction, closing issue 36.** `_extract_one_program`/
`_extract_many_programs` (`program_page.py`) now call
`extract.reduce_html_to_text(raw.body)` immediately after the non-200 status check, and
use the *reduced* text for everything downstream: `cache.lookup`/`cache.lookup_many`,
`llm_client.extract_program`/`extract_programs`, and `cache.store`/`store_many`. This
means the extraction cache's key (`content_hash`, `adapters/DESIGN.md`'s own §5 entry for
`ProgramExtractionCache`) is now a hash of the reduced text, not the raw fetched body —
see the Design Rationale below for why this is a deliberate improvement, not an
incidental side effect. `_CACHE_SCHEMA_VERSION` is **not** bumped: the entry's on-disk
*shape* (`schema_version`/`content_hash`/`result`|`results`) is unchanged, only what gets
hashed — an old entry's stored hash simply won't match the new hash on the next run,
which the cache's existing "stale content hash is a miss, not an error" contract already
handles as a normal, harmless one-time re-extraction per already-cached page (same
"pure optimization" reasoning `_CACHE_SCHEMA_VERSION`'s own docstring already relies on).

**Design Rationale: hash the reduced text, not the raw HTML.**
- *Decision*: `content_hash()` is computed over `reduce_html_to_text()`'s output, called
  once per fetch, with the same value reused for the cache key and the LLM call.
- *Context*: `ProgramExtractionCache` already existed keyed on `content_hash(raw body)`;
  adding a reduction step needed a decision about which text to hash.
- *Alternatives considered*: keep hashing `raw.body` (the fetched HTML) and only pass the
  reduced text to the LLM call.
- *Why this choice*: a page's raw HTML changes on every visit to a boilerplate element
  that `reduce_html_to_text()` already discards (a nav-menu link, an inline script's
  cache-busting query string, an ad-tag version bump) — hashing the raw body would
  invalidate the cache on changes that can never affect the extracted fields, since the
  LLM never sees them. Hashing the reduced text instead means the cache only misses when
  content the LLM actually reads has changed — a strictly better hit rate with no
  correctness cost.
- *Consequences*: every previously-cached `program_page`/`program_listing`/
  `program_page_multi` entry misses exactly once on this sprint's first post-deploy run
  (its stored hash was computed over raw HTML, the new code hashes reduced text) and is
  then cached under the new key going forward — a one-time, bounded-cost, already-
  contracted-for cache miss, not a bug.

**(Sprint 028) `is_open`'s prompt-level definition generalizes, and camp sessions surface
sold-out status via `Event.description`.** `program_llm.py`'s `_FIELD_EXTRACTION_RULES`
(shared verbatim between the single- and multi-record system prompts) rewords `is_open`'s
guidance from "true if the page indicates applications are currently open... false if...
closed for the current cycle" to "true if open for enrollment/application; false if
closed, full, or sold out" — a backward-compatible broadening, not a new field: an
internship/program page's own truth value is unaffected (a closed application window was
already "not open"; a sold-out camp session is now also "not open," a case that simply
never arose for the pre-028 program_kind population). `_map_result_to_event`
(`program_page.py`) gains one new branch: when the resolved `opportunity_type` is
`"Camps"` and `result.is_open` is `False`, it now calls `event.set("description", "Sold
out", source=PROGRAM_LLM_SOURCE, confidence=PROGRAM_LLM_CONFIDENCE)` — the one field this
mechanism has left conspicuously unset since sprint 027 (see this doc's own "No
`description` field" note in `program_page.py`'s module docstring), now given exactly one
use, gated narrowly enough that no other `program_kind`/`opportunity_type` combination's
`Event.description` changes from its pre-sprint-028 unset state.

**Design Rationale: reuse `ProgramExtractionResult`/`program_page_multi` unchanged for
camp sessions, rather than a camp-specific result shape.**
- *Decision*: A camp session (dates, price, sold-out flag) is represented as one
  `ProgramExtractionResult`, extracted via the existing `program_page_multi` mechanism —
  no new dataclass, no new adapter-family prompt shape.
- *Context*: issue 29 explicitly asked whether `program_page_multi` serves camps
  directly or needs a camp-specific shape, since sessions carry price + sold-out +
  week-by-week dates that `ProgramExtractionResult` might not carry.
- *Alternatives considered*: (a) a new `CampSessionExtractionResult` dataclass plus a
  parallel prompt/schema/cache/adapter path; (b) extend `ProgramExtractionResult` with new
  fields (e.g. `sold_out: bool`, `session_label: str`).
- *Why this choice*: on inspection, the existing fields already have a 1:1 mapping onto a
  camp session's real needs — `date_start`/`date_end` are the session's own week dates
  (exactly what `program_page_multi`'s "N inline records, each independently dated"
  design already provides), `cost` is a free-text price string (already accepts "$525/wk"
  as readily as "Free"), and `is_open` already means "currently available" once its
  prompt wording is read generically rather than application-window-specifically (the
  wording change above). (a) would duplicate roughly 400 lines of schema/prompt/cache
  machinery for a shape that turns out not to need new fields. (b) is a real schema
  change to a dataclass three existing use cases (SUC-031 through SUC-035) already
  depend on, for no field this sprint's actual data needs. Reusing the shape as-is, with
  only prose-level prompt generalization and one small `_map_result_to_event` branch,
  needed neither.
- *Consequences*: no new LLM-extraction schema, no new cache entry shape, no
  `_CACHE_SCHEMA_VERSION` bump for this reason. The tradeoff is that `is_open`'s field
  name reads oddly for a camp session ("is open" meaning "not sold out") — judged an
  acceptable naming cost against duplicating the whole mechanism, and documented here so
  a future reader of `program_llm.py` understands why.

**(Sprint 028) An in-season-only page's empty result is valid, not an error, closing the
Fleet seasonal-recheck requirement.** `_SYSTEM_PROMPT_MULTI` gains one explicit
instruction: "If no distinct programs are described on the page, return an empty list."
`_extract_many_programs` already maps a zero-length `results`/`list_responses` to zero
`Event`s with no special-casing needed — the only change is telling the model that zero
is an acceptable, correct answer rather than something to guess around.

**Design Rationale: no new seasonal-recheck subsystem.**
- *Decision*: Fleet's marketing page (and any other in-season-only camp page) is
  registered `enabled = true` year-round; the existing weekly scheduled run
  (`.github/workflows/scheduled-run.yml`) is the entire "recheck" mechanism.
- *Context*: the roadmap `sprint.md`'s Success Criteria asked for "a season-ahead view":
  a camp whose registration opens later should be "scheduled for a seasonal re-check
  rather than silently stale."
- *Alternatives considered*: a per-source `next_check_date`/recheck-interval field in
  `registry/`'s `SourceConfig`, read by `pipeline.run()` to skip a source outside its
  window; a cron-level seasonal filter.
- *Why this choice*: the pipeline already re-fetches every enabled source on every
  scheduled run, unconditionally — there was never a technical gap in *re-checking*
  Fleet's page. The actual gap was narrower and already fixed above: `extract_programs()`
  had no explicit permission to return an empty list for a page with nothing on it yet,
  so an off-season run risked either a hallucinated session or a parse error, not silence.
  Building registry-level scheduling machinery for a problem that doesn't require it
  would be exactly the "speculative generality" this codebase's own architecture-quality
  principles warn against, and this project's own `registry/DESIGN.md` already treats
  "no schema validation for `config`" as an accepted minimalism tradeoff of the same
  shape.
- *Consequences*: an off-season Fleet run legitimately yields zero `Camps` records, which
  is indistinguishable in `observability/`'s yield report from a broken source — see §6's
  new Open Question for this residual, accepted gap.

**(Sprint 028) `activenet_camps`/`campbrain`: platform adapters sharing the LLM family's
own intermediate shape.** `ActiveNetCampsAdapter`/`CampBrainAdapter` share
`ProgramPageAdapter`'s exact `discover()`/`fetch()` shape — one registered
`config.url` per organization (the platform's per-org camp-listing endpoint), one
`EventRef`, no probe-then-paginate step, matching the "onboarding is a data edit"
convention every other adapter type already follows (`registry/DESIGN.md`'s own §1). They
differ only in `extract()`: each vendor's response is first attempted as a deterministic
parse (a known JSON shape, `CONFIDENCE_STRUCTURED_PLATFORM = 1.0`, mirroring the
Structured API family's own confidence convention) into one `ProgramExtractionResult` per
session found; if the platform's actual response turns out not to be cleanly structured
(confirmed at ticket time via live verification — issue 29 calls ActiveNet "HTML-ish", not
confirmed JSON), `extract()` falls back to `extract.reduce_html_to_text()` plus
`ProgramLLMClient.extract_programs()` — the exact same call `program_page_multi` already
makes, with the exact same `_SYSTEM_PROMPT_MULTI`. Either path produces a
`list[ProgramExtractionResult]`, mapped onto `Event`s via the existing
`_map_result_to_event` with zero new mapping code — see this section's earlier Design
Rationale for why `ProgramExtractionResult` was kept as the one shared intermediate shape.
`config.opportunity_type = "Camps"` is set on every registered `activenet_camps`/
`campbrain` source, the same operator-curated override convention
`sd-foundation-community-scholarship.toml` already established for `"Funding
Opportunities"`.

**Design Rationale: defer Pike13; exclude Camp Galileo SD; avoid dual-registering Air &
Space Museum/Helen Woodward.**
- *Decision*: this sprint designs and registers only `activenet_camps` and `campbrain`
  (issue 29's first- and second-priority platforms). Pike13 (third priority) is deferred
  to a follow-up issue. Camp Galileo SD is not registered by any path. Air & Space Museum
  and Helen Woodward are registered only via `activenet_camps`, never also via a
  marketing-page `program_page_multi` source.
- *Context*: issue 29 lists all three platforms and names Camp Galileo SD among the
  marketing-page targets; both Air & Space Museum and Helen Woodward appear in issue 29's
  marketing-page list *and* its ActiveNet-coverage note.
- *Alternatives considered*: build all three platform adapters this sprint; register
  Camp Galileo SD pending the stakeholder's still-open commercial-chain decision;
  register Air & Space/Helen Woodward through both paths and rely on downstream dedup.
- *Why this choice*: Pike13 needs its own credential provisioning and has an unresolved
  overlap question with the already-shipped `leaguesync` adapter (issue 29's own text) —
  forcing it in risks a low-confidence adapter or a stalled ticket, so it is scoped out
  explicitly rather than attempted and left half-verified. Camp Galileo is the studio
  brand named in the roadmap `sprint.md`'s own commercial-chain exclusion list — the
  scope decision already made at roadmap time applies to it regardless of which list
  issue 29 happens to also put it on. Registering Air & Space/Helen Woodward through two
  adapter types would repeat, for a case we can see coming, the exact dual-registration
  risk `adapters/DESIGN.md`'s own sprint 027 Open Question documents as unresolved for
  COSMOS/OPTIMUS/ENLACE (`kind in PROGRAM_EXTRACTION_KINDS` records bypass cross-source
  dedup by design, so nothing downstream would catch the duplicate).
- *Consequences*: a follow-up issue is filed at sprint close for Pike13, carrying the
  leaguesync-overlap question forward. `registry/sources/` gets no Camp Galileo entry.
  Air & Space Museum/Helen Woodward's marketing pages, though scrapable, are deliberately
  never registered as `program_page_multi` sources.

**Reuse surface for future platforms.** `activenet_camps`/`campbrain`'s "deterministic
parse, LLM fallback, `ProgramExtractionResult` either way" shape is deliberately generic:
a future camp-registration platform (or Pike13, when its follow-up issue is picked up)
can follow the identical pattern with zero change to `program_llm.py`, `program_cache.py`,
or `_map_result_to_event`.

**(Sprint 029 revision) Competition-genre extraction profile, selected by
`source.config.opportunity_type`.** `ProgramLLMClient.extract_program(url,
body, *, profile="program", reference_date=None)`/`extract_programs(url,
body, *, profile="program", reference_date=None)` — two new keyword-only
parameters, both optional and defaulting to today's exact behavior, so
every sprint 027/028 call site (camps, scholarships, SIO, UCSD Summer
Program Finder) that never passes them is unaffected byte-for-byte.
`profile` selects between `_SYSTEM_PROMPT`/`_SYSTEM_PROMPT_MULTI`
(default, unchanged) and a new `_SYSTEM_PROMPT_COMPETITION`/
`_SYSTEM_PROMPT_COMPETITION_MULTI` pair, sharing a new
`_FIELD_EXTRACTION_RULES_COMPETITION` the same way the existing pair
shares `_FIELD_EXTRACTION_RULES`. `registration_deadline` is a new
required field on the shared `ProgramExtractionResult` dataclass (see
below), so it is present in the JSON schema sent on *every* call
regardless of profile — the base (unchanged) `_FIELD_EXTRACTION_RULES`
gains one new line, "`registration_deadline`: always `""` for this page
type — an application-window program's one deadline is already
`date_end`," so the base profile's own behavior stays fully specified
rather than relying on unstated structured-output defaulting. `program_page.py`'s
`_extract_one_program`/`_extract_many_programs` compute `profile =
"competition" if source.config.get("opportunity_type") == "Competitions"
else "program"` and pass it straight through — no new registry `config`
key, reusing the exact override value this sprint's own TOML files
already carry for every affected source. `reference_date` (default
`date.today()` when omitted; threaded from the call sites so tests can
pin it) is injected into the *user* prompt, never the system prompt (it
varies per call, unlike the system prompt's static text), as "Page
fetched on: `<ISO date>`" — see the field rules below for how it is used.
`FixtureProgramLLMClient.extract_program`/`extract_programs` gain the
same two keyword-only parameters (accepted, ignored — canned responses
never depend on them), so no existing fixture-test call site needs to
change.

**Competition profile field rules — the deadline-vs-event-date
distinction, spelled out rather than left implicit:**
- `date_start`/`date_end` are redefined for this profile: the
  competition/event's own date (`date_start`; the first day if
  multi-day) and its last day if multi-day, else empty (`date_end`) —
  never a registration/application deadline. Explicit negative
  instruction: "`date_end` is the event's own last day if it spans
  multiple days; it is NOT a registration, sign-up, or paperwork
  deadline — put that in `registration_deadline` instead, never here."
- `registration_deadline` (new field, this profile only): a
  registration/team-signup/paperwork deadline stated separately from the
  event's own date, or `""` if none is stated or the page states only
  one date. Directly fixes `seaperch-sd-regional`'s
  TDR-deadline-swallows-event-date failure by giving the model a place
  to put the deadline that isn't `date_start`/`date_end`.
- Explicit phrasing guidance naming the patterns tickets 001/002 found
  the model missing: "look for the date under any of: 'Event Date,'
  'Competition Date,' 'Tournament Date,' 'Save the Date,' as well as
  ordinary prose" — directly fixes `sd-brain-bee`'s "Event Date: February
  14, 2026" miss (the pre-revision prompt's application-window framing
  gave the model nothing to match this phrasing against).
- Year inference, using the new `reference_date`: "If a date states a
  month and day but no year, infer the soonest year (this one, or next)
  in which that month/day falls on or after `<reference_date>` — never
  leave the year off, and do not default to the current calendar year if
  that month/day has already passed relative to the reference date." A
  deliberate, narrow, named exception to this profile's (and the base
  profile's, unchanged) general "never guess a date not stated"
  instruction — scoped only to the year component of an otherwise-stated
  month/day, via a mechanical, single-step rule rather than open-ended
  guessing. Directly fixes `tritonhacks`'s wrong-year failure.

**Design Rationale: fold `registration_deadline` into `Event.description`,
not `Event.end`/`DEADLINE_FIRST_TYPES` — and why a distinct field is now
justified when sprint 015 rejected one.**
- *Decision*: `registration_deadline` is a new `ProgramExtractionResult`
  field, mapped by `_map_result_to_event` onto `Event.description` (a
  short note, e.g. "Registration deadline: `<date>`") when the resolved
  `opportunity_type` is `"Competitions"` and the field is non-empty —
  mirroring sprint 028's identical `resolved_opportunity_type ==
  "Camps" and result.is_open is False → Event.description` branch
  verbatim, in shape and in scope-narrowness. It is never mapped onto
  `Event.start`/`Event.end`; `normalize/run.py`'s `DEADLINE_FIRST_TYPES`/
  `_internship_availability` and `export/writer.py`'s
  `is_current_or_upcoming` are unmodified.
- *Context*: `normalize/DESIGN.md`'s sprint 015 addendum explicitly
  rejected a distinct `application_deadline` field at that time: "No
  adapter or the LLM prompt currently distinguishes a registration
  deadline from an event's own end date/time for any non-internship
  record, so a new field would have no real producer yet." This revision
  is the first real producer — the competition profile genuinely
  extracts a registration deadline distinct from the event date
  (`seaperch-sd-regional`'s TDR deadline vs. its April 4 competition
  date is exactly the case sprint 015 anticipated but had no evidence
  for yet).
- *Alternatives considered*: (a) do what the pre-revision prompt was
  implicitly attempting — put the registration deadline in `date_end`,
  the event's own date in `date_start`, and let the existing
  deadline-first currency/sort/availability rules apply unchanged; (b)
  remove `"Competitions"` from `DEADLINE_FIRST_TYPES` entirely, treating
  every competition record with the plain "`date_end` or `date_start` >=
  today" currency rule.
- *Why this choice, over (a)*: (a) is the direct cause of
  `seaperch-sd-regional`'s failure — `date_end` cannot simultaneously
  mean "the event's own last day, if multi-day" (needed for
  `tritonhacks`' May 16-17 span) and "a separate registration deadline"
  (needed for SeaPerch's TDR cutoff) when a single page can carry both
  facts about two different dates at once. Overloading one field for two
  distinct real-world dates is exactly the ambiguity the model was
  already failing on; giving each its own field removes the ambiguity
  from the prompt rather than asking the model to keep guessing which
  one field on the page it is supposed to describe.
- *Why this choice, over (b)*: `"Competitions"` has carried a second,
  unrelated, already-shipped meaning in `DEADLINE_FIRST_TYPES` since
  sprint 015 — a `generic_html`-sourced record whose only actionable
  date *is* a submission/registration deadline (the Health Pitch
  Competition case). That case has no `kind="program"`/`program_llm.py`
  involvement at all; its `date_end` genuinely is its deadline, and the
  currency/sort/availability behavior `DEADLINE_FIRST_TYPES` gives it
  today is correct for it. `DEADLINE_FIRST_TYPES` is `opportunity_type`-
  keyed by deliberate design (`normalize/DESIGN.md`'s sprint 027 Design
  Rationale: kind-awareness in `export/writer.py` was rejected as a
  speculative `Opportunity` schema change), so there is no way to
  special-case "program-page-sourced Competitions get event-first
  semantics, `generic_html`-sourced Competitions keep deadline-first
  semantics" without either reintroducing that rejected `kind` threading
  or splitting `"Competitions"` into two `opportunity_type` values (a
  real taxonomy change, explicitly Out of Scope for sprint 029).
  Changing the shared rule would fix program-page competitions at the
  cost of silently regressing the pitch-competition case this revision
  has no live evidence about and no mandate to touch.
- *Consequences*: a program-page-sourced Competitions record's currency
  now behaves exactly like an ordinary dated event under
  `DEADLINE_FIRST_TYPES`'s existing "no `date_end` → `date_start` within
  `_DEADLINE_FIRST_STALE_POSTING_DAYS` (365 days) counts as current"
  rule — a pre-existing, already-accepted allowance (not tightened or
  loosened by this revision), somewhat more permissive than "`date_start`
  must be strictly in the future" for a single-day event with no
  `registration_deadline`. This is unchanged, pre-existing
  `DEADLINE_FIRST_TYPES` behavior for every `Competitions` record today
  (RobotEvents/TEC-backed included), not a new risk this revision
  introduces — noted here, not re-litigated (see §6's new Open
  Question). `registration_deadline`'s own currency is not tracked at
  all (descriptive text only); a registration deadline that has passed
  while the event itself is still upcoming does not affect the record's
  export status, which is the correct behavior — the event, not the
  registration window, is what the record should stay current for.

**Design Rationale: `ProgramExtractionCache._CACHE_SCHEMA_VERSION` bumps
2 → 3.**
- *Decision*: bump `_CACHE_SCHEMA_VERSION` from 2 to 3, per this module's
  own documented rule ("bumped whenever `ProgramExtractionResult`'s
  shape changes").
- *Context*: `registration_deadline` is a new required field on the
  dataclass the JSON schema is built from (`_build_program_extraction_
  json_schema()`'s dataclass introspection); a stored pre-revision cache
  entry has no such key.
- *Why this choice*: matches the ticket 006 exception revision's
  identical precedent (1 → 2, for the `lookup_many`/`store_many` shape)
  exactly — forces exactly one harmless re-extraction of any
  already-cached URL, which the cache's own "stale `schema_version` is a
  miss, not a deserialization error" contract already handles with no
  further code change. This bump additionally does necessary, not
  merely tidy, work here: tickets 001/002's real dry-runs already
  populated cache entries for all six of this revision's affected
  sources under the *old*, since-corrected prompt; without the bump,
  ticket 007's re-verification would read back those stale entries and
  never call the corrected prompt at all, silently reproducing the
  exact failures this revision fixes.
- *Consequences*: identical, already-accepted cost shape to the ticket
  006 precedent — one extra LLM call per previously-cached program-page/
  listing/multi URL project-wide on the next run, not only for this
  revision's six sources.

**Design Rationale: SD Math Circle's grid-shaped sheet is explicitly out
of scope for this revision.**
- *Decision*: no attempt is made to extend `extract_programs()` to
  recover per-row dated items from a page whose primary shape is a dense
  weekly-schedule grid with competition dates as one-off rows inside it.
  `sd-math-circle` stays `enabled = false`.
- *Context*: ticket 002's own live-verification already isolated this as
  a distinct failure axis from the deadline-vs-event-date framing bug
  this revision fixes — the AMC/AIME dated rows survive
  `reduce_html_to_text()` intact and are present in the exact text sent
  to the model; the failure is that `extract_programs()`'s framing
  ("identify every distinct program described on the page") locks onto
  the sheet's 5 recurring class-group columns instead of the scattered
  one-off competition rows, a wrong-axis-of-extraction problem no amount
  of deadline-vs-event-date prompt correction touches.
- *Alternatives considered*: (a) fix it in this revision anyway, via
  grid/tabular-aware field rules or a per-row extraction pass; (b) point
  `config.url` at the individual `/events/<slug>` detail pages
  `sd-math-circle.toml`'s own header comment already names
  (`sdmathcircle.org/events/amc-10-12-a`, `/events/aime`, `/events/arml`,
  `/events/math-kangaroo`) as a `program_listing` or several individual
  `program_page` sources instead of the grid sheet.
- *Why this choice*: (a) is a materially different extraction mechanism
  (per-row/per-cell reasoning over a schedule grid, not per-section
  reasoning over a page of prose sections) that the team-lead's own
  dispatch explicitly permits deferring rather than forcing; building it
  now, on evidence from exactly one grid-shaped source, risks the
  speculative-generality trap this codebase's architecture principles
  already warn against repeatedly. (b) is a real, promising alternative —
  live-verified detail pages likely have the same single-event shape
  this revision's competition profile already handles well — but it is
  untested at architecture-authoring time (no ticket has live-verified
  those detail pages' actual content) and changes `sd-math-circle.toml`'s
  registration shape entirely, ticket-level work, not something to
  design blind here.
- *Consequences*: `sd-math-circle` remains disabled after this revision;
  ticket 007 (below) does not include it in its re-verification set. (b)
  is recorded here as the likely next step for a follow-up issue — not
  built speculatively now.

## 5. Interfaces

### Exposes
- **`run(source: SourceConfig, fetcher: Fetcher) -> list[Event]`** — the whole
  subsystem's entry point. Dispatches on `source.adapter_type`, chains
  discover→fetch→extract, applies the `max_urls` cap. Raises `UnknownAdapterType` if the
  type is unregistered; per-record failures inside `extract()` are swallowed by the
  adapter itself, so this returns a possibly-short list rather than raising. A
  fetch-level failure surfaces as a `RawResponse` with a non-2xx or sentinel status,
  which `extract()` is responsible for handling. **(Ticket 006 exception revision)** also
  logs a warning (never raises) when `discover()` returns zero refs for an enabled
  source, for every adapter type — see §4.
- **`Adapter` Protocol, `EventRef`, `RawResponse`** — the contract a new adapter type
  implements.
- **`ADAPTERS: dict[str, type[Adapter]]`** — the dispatch table. Mutated exactly once per
  type, at import of `adapters/__init__.py`.
- **`get_adapter(adapter_type) -> Adapter`** — instantiates a registered adapter; raises
  `UnknownAdapterType` with the known-type list rather than a bare `KeyError`.
- **`ats_filters.classify_posting(...) -> PostingVerdict`** — shared internship/STEM/
  locality classification for the ATS adapters.
- **`acquisition_kwargs(source: SourceConfig) -> dict[str, Any]`** — **(Sprint 015
  ticket 003)** the `rate_limit_seconds`/`respect_robots` kwargs for `fetcher.get()`,
  read from `source.acquisition_policy`. Consumed by every `fetch()` implementation in
  this package and by `discovery/sitemap.py`/`discovery/listing.py`, which import it
  from here the same way they already import `EventRef` — see §2.
- **`ProgramPageAdapter(llm_client=None, cache=None)`, `ProgramListingAdapter(llm_client=
  None, cache=None)`** (sprint 027) — the two original adapter types; see §3's
  constructor-injection note and §4's Design. **`ProgramPageMultiAdapter(llm_client=None,
  cache=None)`** (ticket 006 exception revision) — the third, "one page, N inline
  records" type; identical constructor shape, see §4.
- **`ProgramLLMClient` Protocol, `ProgramExtractionResult`, `AnthropicProgramLLMClient`,
  `FixtureProgramLLMClient`** (sprint 027, `adapters/program_llm.py`) — the injectable
  LLM-extraction seam and its production/test implementations, structurally parallel to
  `enrich/llm_client.py`'s `LLMClient`/`EnrichmentResult`/`AnthropicLLMClient`/
  `FixtureLLMClient` but never importing them (see §4). **(Ticket 006 exception
  revision)** `ProgramLLMClient` gains a second method, `extract_programs(url, body) ->
  list[ProgramExtractionResult]`, for `program_page_multi`'s one-page/N-record shape;
  both real and fixture implementations now support both methods. **(Sprint 029
  revision)** both methods gain two keyword-only parameters, `profile: str = "program"`
  and `reference_date: date | None = None` (see §4) — additive, every existing call site
  that omits them is unaffected. `ProgramExtractionResult` gains one new field,
  `registration_deadline: str = ""`, populated only by `profile="competition"` (see §4's
  Design Rationale for why this field exists rather than reusing `date_end`).
- **`ActiveNetCampsAdapter(llm_client=None, cache=None)`, `CampBrainAdapter(llm_client=
  None, cache=None)`** (sprint 028) — the two new camp-platform adapter types; see §4's
  Design. Same constructor-injection shape as the `program_page` family, for the same
  test-injectability reason.
- **`CONFIDENCE_STRUCTURED_PLATFORM`** (sprint 028, `adapters/activenet_camps.py`/
  `campbrain.py`) — the confidence stamped on a deterministically-parsed platform
  session field, `1.0`, matching every Structured API adapter's own `CONFIDENCE = 1.0`
  convention. Not used on the LLM-fallback path, which stamps `PROGRAM_LLM_CONFIDENCE`
  (`0.9`) exactly as `program_page_multi` already does.
- **`ProgramExtractionCache(cache_dir=None)`** (sprint 027, `adapters/program_cache.py`)
  — one JSON file per URL+content-hash under `{SCRAPE_CACHE_DIR}/
  program_extraction_cache/`, avoiding a repeat `ProgramLLMClient` call for an unchanged
  page across pipeline runs. Mirrors `enrich/cache.py`'s shape; a separate cache
  directory and class, not a reuse of `EnrichmentCache`, because the cache key differs
  (URL, not `Event.identity_key()` — no `Event` exists yet at fetch time). **(Ticket 006
  exception revision)** gains `lookup_many`/`store_many`, the list-valued counterpart to
  `lookup`/`store`, for `program_page_multi`; `_CACHE_SCHEMA_VERSION` is bumped once for
  the new entry shape (see §4). **(Sprint 029 revision)** `_CACHE_SCHEMA_VERSION` bumps
  again, 2 → 3, for `registration_deadline`'s addition to `ProgramExtractionResult` — see
  §4's Design Rationale for why this bump is load-bearing, not only tidy, for this
  revision specifically.

### Consumes
- **`Fetcher` (from `fetch/`)** — every remote read. Injected per call; see `fetch/DESIGN.md`.
- **`SourceConfig` and `DEFAULT_MAX_URLS_PER_SOURCE` (from `registry/`)** — the per-source
  data that drives dispatch and the URL cap. See `registry/DESIGN.md`.
- **`Event`, `Provenance` (from `model.py`)** — the output record. See the root
  `partner_scrape/DESIGN.md`.
- **`discover_changed_urls` / `discover_via_listing` (from `discovery/`)** — URL
  resolution for the two HTML adapters. See `discovery/DESIGN.md`. **(Ticket 006
  exception revision)** `discover_via_selector`, the new sibling function, is consumed by
  `ProgramListingAdapter.discover()` the same way, when `config.link_selector` is set.
- **`extract_fields` (from `extract/`)** — per-field values and confidences for the two
  HTML adapters. See `extract/DESIGN.md`.
- **`config.get_leaguesync_api_key` / `get_leaguesync_url` (from `config.py`)** — the
  `leaguesync` adapter's credentials, read through the one module allowed to touch
  `os.environ`.
- **`config.get_robotevents_api_key` / `get_robotevents_url` (from `config.py`)**
  — **(Sprint 016 ticket 004)** the `robotevents` adapter's credentials, same
  `os.environ`-isolation convention as `leaguesync`'s pair above.
- **The `anthropic` SDK** (sprint 027, `program_llm.py`'s `AnthropicProgramLLMClient`
  only) — reads `ANTHROPIC_API_KEY` itself, not routed through `config.py`, matching
  `enrich/llm_client.py`'s identical credential convention. This is a new external
  dependency for `adapters/` specifically (the package as a whole already depended on
  `anthropic` transitively via `enrich/`, but no adapter had ever called it directly).
- **`config.get_scrape_cache_dir()` (from `config.py`)** (sprint 027,
  `program_cache.py`) — the parent of `program_extraction_cache/`, matching
  `enrich/cache.py`'s and `store/event_store.py`'s existing convention.
- **`extract.reduce_html_to_text(html, max_chars)` (from `extract/`)** (sprint 028) — the
  new dependency this sprint adds: `program_page.py` now imports from `extract/`, which
  it previously never did (only `generic_html.py`/`listing_html.py` depended on `extract/`
  before this sprint). See `extract/DESIGN.md`'s sprint 028 section. No credential or
  API-key dependency was added for `activenet_camps`/`campbrain` this sprint — both
  platforms' endpoints are treated as public for architecture purposes, pending each
  registration's own live verification; if verification finds a required API key, that
  ticket adds a `config.py` accessor pair mirroring `get_leaguesync_api_key()`/
  `get_robotevents_api_key()`, not designed in advance of evidence requiring it.

## 6. Open Questions / Known Limitations

- There is a real circular-import hazard between `adapters.listing_html` and
  `discovery.listing`: each needs a name from the other's package. `cli.py` works around
  it by importing `partner_scrape.pipeline` before `partner_scrape.discovery`, with an
  explanatory comment. That is a load-order workaround, not a fix; the cycle should be
  broken properly (most likely by moving the shared path regex out of `discovery`).
- `EventRef.context` is an untyped `dict[str, Any]`. It works, but there is no schema and
  no cross-adapter convention for what goes in it.
- Every adapter re-implements its own `_strip_html`, `_parse_datetime`, and HTML-entity
  table. Five near-identical copies exist. Deduplication was deferred on the grounds that
  each adapter's version has drifted to fit its own source's quirks; that reasoning is
  worth re-testing.
- `bibliocommons`'s audience prefilter defaults `KEEP_IF_UNKNOWN_AUDIENCE = True`, which
  is deliberately permissive and relies on the downstream LLM relevance gate to catch
  what it lets through. If enrichment is disabled (`--no-enrich`), that safety net is
  absent.
- **(Sprint 027, real risk, not yet fully resolved)** A program named in both a
  `program_listing` source's crawl (e.g. the UCSD Summer Program Finder's own COSMOS/
  OPTIMUS/ENLACE cards) and a separately-registered individual `program_page` source
  for the same program would publish as two distinct `Opportunity` records — `kind in
  PROGRAM_EXTRACTION_KINDS` records bypass cross-source dedup entirely (§4;
  `normalize/DESIGN.md`), by design, for the correct reason (distinct internship
  postings/programs are not recurrences of each other), but that same bypass means this
  one accidental case is never caught automatically. Registering these two source
  families for the same real-world program is a data-authoring error, not a code
  defect — ticket-level work must reconcile the seed list (issue 28's own bullets name
  COSMOS/OPTIMUS/ENLACE in both the listing description and the individual-pages list)
  before both go live, and no code-level guard against it exists yet.
- **(Sprint 027, RESOLVED by the ticket 006 exception revision)** ~~`discovery.listing.
  discover_via_listing`'s `EVENT_PATH_RE` matches any href containing a `/program(s)?`
  path segment, regardless of domain — reused as-is for `ProgramListingAdapter`... A
  future `program_listing` source whose card links don't contain any matched path
  segment would discover zero `EventRef`s silently.~~ This is exactly what ticket 006's
  live verification hit for both of this sprint's actual listing sources — see this
  doc's Revision note and §4. Resolved by the new `config.link_selector` discovery path
  (for a shape a CSS selector can express) and the generic zero-refs warning (for
  whatever shape still isn't covered). **Residual, not solved here:** no automatic
  re-check that a registered `link_selector` still matches after a target site's markup
  changes — a silent drift back to zero cards is caught by the new warning and by
  `observability/`'s yield report, but nothing re-validates the selector itself or
  alerts on a *partial* drift (e.g. 24 cards silently becoming 3). Not built
  speculatively; revisit if a registered `link_selector` source is ever observed to
  drift.
- **(Ticket 006 exception revision)** `program_page_multi`'s per-page LLM call has no
  guard against the model returning near-duplicate records for what is really one
  program described twice in different words on the same page (SIO's own page has no
  such duplication today, live-confirmed). Cross-record dedup *within* one
  `program_page_multi` extraction is not built — `kind in PROGRAM_EXTRACTION_KINDS`'s
  existing cross-source dedup bypass (§4, `normalize/DESIGN.md`) means nothing
  downstream would catch it either. Not solved speculatively; revisit if a real page
  exhibits this.
- **(Sprint 027)** No per-run cost/latency budget exists for `ProgramLLMClient` calls
  beyond `ProgramExtractionCache`'s cross-run reuse — a `program_listing` source's
  `extract()` calls the LLM once per discovered card, sequentially, within that one
  source's `adapters.run()` call (concurrency exists only *across* sources, via
  `pipeline.py`'s existing `ThreadPoolExecutor`). At this sprint's scale (~21 UCSD cards
  plus a handful more) this is an accepted, unmeasured cost; a future listing source
  with materially more cards might need its own bounded concurrency, mirroring
  `enrich/enricher.py`'s pattern — not built here. **(Ticket 006 exception revision)**
  `program_page_multi` is one call per page regardless of how many records it returns
  (cheaper per-record than `program_listing`'s one-call-per-card, since SIO's ~10
  programs cost one call, not ten) — this doesn't change the calculus above, just notes
  the new type's own cost shape for whoever revisits this.
- **(Sprint 028)** An off-season, in-season-only camp page (Fleet) legitimately yields
  zero `Camps` records, which is indistinguishable in `observability/`'s per-run yield
  report from a broken source. Accepted per this doc's own Design Rationale above (no
  seasonal-recheck subsystem was built); not solved here. A future sprint could give
  `registry/` sources an optional "expected zero-yield window" annotation if this proves
  to generate false-positive yield alerts in practice — not built speculatively.
- **(Sprint 028)** `activenet_camps`/`campbrain`'s exact response shape (a clean JSON API
  vs. server-rendered HTML needing the LLM-fallback path) is unconfirmed at
  architecture-authoring time — issue 29 calls ActiveNet "HTML-ish" without further
  detail. Both adapters are designed to support either shape identically (see §4), but
  which shape each vendor actually needs is a ticket-level live-verification finding,
  not an architecture decision made here.
- **(Sprint 028)** Whether Coastal Roots Farm's existing marketing-page table
  (`program_page_multi`) is sufficient on its own, or whether its CampBrain-hosted
  registration data would ever need to supersede it, is a ticket-level judgment call once
  the `campbrain` adapter's actual per-organization coverage is confirmed live — this
  sprint registers Coastal Roots Farm via its marketing page only (see `sprint.md`'s
  SUC-043), not via `campbrain`, to avoid the same dual-registration risk named above for
  Air & Space Museum/Helen Woodward.
- **(Sprint 028)** Pike13 (issue 29's third-priority platform) is deferred, along with
  its own open question — whether it supersedes gaps in the already-shipped `leaguesync`
  adapter for the League's own camps — to a follow-up issue. Not designed here.
- **(Sprint 029 revision, new)** Does ticket 003's SD Festival / EXPO Day listing need
  the competition profile too? Ticket 003 (SUC-046) deliberately sets no
  `config.opportunity_type` override — its ~35 festival-week pages mix workshops, the
  EXPO Day showcase, and competitions, so each page's type is left to the LLM's own
  per-page classification. This revision's profile selection is driven by
  `source.config.get("opportunity_type") == "Competitions"`, which does **not** fire for
  ticket 003's source at all — every one of its ~35 LLM calls still uses the default,
  unrevised "program" profile, regardless of whether a given page turns out to be a
  single-dated event (a workshop, EXPO Day itself) rather than an application-window
  program. If ticket 003's own live verification finds the Mar 7 2026 EXPO Day date (or
  another festival-week event's date) fails to surface for the same deadline-vs-event-date
  reason this revision fixes, the documented fallback is to widen profile selection to
  also fire on the *LLM's own self-classified* `opportunity_type` — inspect one
  extraction's `result.opportunity_type` and, if it comes back `"Competitions"` on a page
  with no config override, decide whether a second corrective call is worth its extra LLM
  cost, or whether the single-call self-classifying prompt should itself gain a soft "if
  this appears to be a single dated event rather than an application-window program,
  prefer this wording" instruction. Not designed further here — this revision was not
  asked to solve ticket 003's use case ahead of its own live evidence, and doing so risks
  solving a problem ticket 003's real pages may not actually have. Ticket 003's own scope
  is otherwise unchanged.
- **(Sprint 029 revision, new)** `DEADLINE_FIRST_TYPES`'s existing 365-day
  `_DEADLINE_FIRST_STALE_POSTING_DAYS` allowance (a `Competitions` record with no
  `date_end` counts as current if `date_start` is anywhere from 365 days in the past to
  any point in the future) is somewhat more permissive than a plain "must be in the
  future" rule for a genuinely single-day, no-`registration_deadline` competition event —
  this is pre-existing behavior for every `Competitions` record since sprint 020, not
  something this revision changes or newly introduces (see §4's Design Rationale
  Consequences). Not solved here; revisit only if this is observed to surface a stale
  single-day competition in production, the same "not built speculatively" standard every
  other entry in this section already applies.

---
source_file: adapters-DESIGN.md
source_hash: 997435faaa40f3e6d064d0e36d72d49f3412ae254320fed248cfd8e4ed022172
---
# Diff: adapters-DESIGN.md

Comparison of the sprint overlay copy of `adapters-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- adapters-DESIGN.md (pristine)
+++ adapters-DESIGN.md (current)
@@ -3,6 +3,105 @@
 **Owner:** Eric Busboom · **Last reviewed:** 2026-08-28 · **Status:** stable
 
 ---
+
+## Revision (2026-09-02 — sprint 029 competition-genre extraction fix)
+
+Tickets 001/002's own live-verification (real network, real
+`AnthropicProgramLLMClient` — a correction of both tickets' first-pass
+WebFetch-only checks, recorded in their own Notes sections) found a
+systematic extraction problem, not a series of unrelated site quirks: of
+the sources ticket 001 registered, only `doe-science-bowl-sd`,
+`congressional-app-challenge-sd`, and `cipherhacks` currently ship a
+usable record; five more (`sdftc-league-play`, `botball-greater-sd`,
+`sd-brain-bee`, `seaperch-sd-regional`, `tritonhacks`) and ticket 002's
+`sd-math-circle` were flipped to `enabled = false` after real dry-runs
+contradicted the first pass. The team-lead's cross-ticket read of the
+evidence (both tickets' Notes, all six disabled sources' TOML header
+comments) traced three of these failures to one shared root cause,
+distinct from two other, unrelated failure classes:
+
+- **`program_llm.py`'s `_SYSTEM_PROMPT`/`_SYSTEM_PROMPT_MULTI` and
+  `_FIELD_EXTRACTION_RULES`, unchanged since sprint 027, were written for
+  sprint 027's own target genre — a prose *program* page whose primary
+  date is an application window (`date_start` = "the application
+  window's open date", `date_end` = "the application deadline")** — and
+  this framing actively misleads the model on a genuinely different
+  genre, a single dated *event*:
+  - `sd-brain-bee` — the fetched, reduced text plainly states "Event
+    Date: February 14, 2026"; two independent extraction calls against
+    that identical text both return `date_start=""`/`date_end=""`. The
+    date is present; the field rules give the model nothing to
+    recognize "Event Date:" as a signal worth extracting.
+  - `seaperch-sd-regional` — the fetched text contains both the April 4
+    2026 competition date and the March 27 2026 Technical Design Report
+    submission deadline. Two independent calls both map only the TDR
+    deadline into `date_end`, leaving `date_start` empty — reading "the
+    application deadline" field rule literally, the TDR paperwork
+    cutoff *is* the closest match on the page to "a deadline," even
+    though it is not the date visitors need.
+  - `tritonhacks` — the fetched text states "May 16 & 17" with no
+    adjacent year; the only "2026" on the whole page is an unrelated
+    footer copyright line. The model filled in a year anyway
+    (`2025-05-08`, already past) rather than being given a reference
+    date to reason from or a rule for inferring one.
+- **`sdftc-league-play` and `botball-greater-sd`** are a different
+  failure class: their fetched, reduced text contains *no calendar date
+  at all* (nav/mission-statement copy for the first; day-of-week labels
+  with an apparently client-side-rendered date widget for the second) —
+  no prompt wording recovers a date that never reached the model. These
+  are fetch/content-availability gaps, not framing gaps; this revision's
+  fix is not expected to re-enable them on its own — ticket 007 (below)
+  says so explicitly rather than assuming a shared cause.
+- **`sd-math-circle`** is a third, unrelated failure class: `extract_programs()`
+  correctly receives intact AMC/AIME/etc. dated rows in the fetched text
+  (confirmed by grepping the exact reduced text sent to the LLM), but the
+  page's shape — a dense ~40-week × 5-column weekly class-schedule grid,
+  with the actual competition dates as scattered one-off rows *inside*
+  that grid — is not "N distinct top-level program sections," the shape
+  `extract_programs()`'s framing assumes. This is a grid/tabular
+  extraction gap, not a deadline-vs-event-date framing gap; **explicitly
+  deferred**, not attempted by this revision — see §4's Design Rationale
+  below.
+
+**Design decision: a `profile`-selected competition extraction mode,
+plus one new field — no `Opportunity`/`Event` schema change, no
+`normalize/run.py` change.** See §4's new Design entries and Design
+Rationale blocks for the full write-up. In outline:
+`ProgramLLMClient.extract_program`/`extract_programs` gain a new
+keyword parameter, `profile: str = "program"`, selecting between the
+existing application-window system prompt (default, unchanged — every
+sprint 027/028 source's behavior is byte-for-byte identical) and a new
+competition-genre system prompt, chosen by `program_page.py`'s two call
+sites from data already on hand
+(`source.config.get("opportunity_type") == "Competitions"`) — no new
+registry `config` key. `ProgramExtractionResult` gains one new field,
+`registration_deadline: str = ""`, populated only by the competition
+prompt and folded into `Event.description` (mirroring sprint 028's
+Camps-sold-out precedent) rather than into `start`/`end`.
+`ProgramExtractionCache._CACHE_SCHEMA_VERSION` bumps 2 → 3.
+
+**No change to `normalize/run.py`'s `DEADLINE_FIRST_TYPES` or
+`export/writer.py`'s currency rule.** Confirmed by reading both before
+designing on top of them, per the team-lead's explicit ask.
+`"Competitions"` has been a `DEADLINE_FIRST_TYPES` member since sprint
+015 for a *different*, unrelated sub-case — a `generic_html`-sourced,
+`enrich/llm_client.py`-classified pitch/essay competition whose own
+actionable date genuinely is a submission deadline (`export/writer.py`'s
+`_DEADLINE_FIRST_STALE_POSTING_DAYS` comment names "2nd Innovation in
+Women's Health Pitch Competition" as the motivating case). Removing
+`"Competitions"` from that set to fix program-page-sourced single-dated
+events would regress that case — out of this revision's evidence and
+authority. See §4's Design Rationale for the full reasoning, including
+why sprint 015's own "no real producer yet" rejection of a distinct
+deadline field no longer applies now that the competition profile is a
+real producer of one.
+
+**Surface: internal.** This is a mechanism-choice correction inside
+`ProgramLLMClient`'s implementation, found by tickets 001/002's own
+required live-verification step — no SUC-044/SUC-045 wording changes as
+a result (both already required a "correctly-dated" record; this
+revision is how that gets satisfied for real, not a renegotiation of
+what was promised).
 
 ## Revision (2026-09-02 — ticket 006 exception cycle)
 
@@ -640,6 +739,213 @@
 can follow the identical pattern with zero change to `program_llm.py`, `program_cache.py`,
 or `_map_result_to_event`.
 
+**(Sprint 029 revision) Competition-genre extraction profile, selected by
+`source.config.opportunity_type`.** `ProgramLLMClient.extract_program(url,
+body, *, profile="program", reference_date=None)`/`extract_programs(url,
+body, *, profile="program", reference_date=None)` — two new keyword-only
+parameters, both optional and defaulting to today's exact behavior, so
+every sprint 027/028 call site (camps, scholarships, SIO, UCSD Summer
+Program Finder) that never passes them is unaffected byte-for-byte.
+`profile` selects between `_SYSTEM_PROMPT`/`_SYSTEM_PROMPT_MULTI`
+(default, unchanged) and a new `_SYSTEM_PROMPT_COMPETITION`/
+`_SYSTEM_PROMPT_COMPETITION_MULTI` pair, sharing a new
+`_FIELD_EXTRACTION_RULES_COMPETITION` the same way the existing pair
+shares `_FIELD_EXTRACTION_RULES`. `registration_deadline` is a new
+required field on the shared `ProgramExtractionResult` dataclass (see
+below), so it is present in the JSON schema sent on *every* call
+regardless of profile — the base (unchanged) `_FIELD_EXTRACTION_RULES`
+gains one new line, "`registration_deadline`: always `""` for this page
+type — an application-window program's one deadline is already
+`date_end`," so the base profile's own behavior stays fully specified
+rather than relying on unstated structured-output defaulting. `program_page.py`'s
+`_extract_one_program`/`_extract_many_programs` compute `profile =
+"competition" if source.config.get("opportunity_type") == "Competitions"
+else "program"` and pass it straight through — no new registry `config`
+key, reusing the exact override value this sprint's own TOML files
+already carry for every affected source. `reference_date` (default
+`date.today()` when omitted; threaded from the call sites so tests can
+pin it) is injected into the *user* prompt, never the system prompt (it
+varies per call, unlike the system prompt's static text), as "Page
+fetched on: `<ISO date>`" — see the field rules below for how it is used.
+`FixtureProgramLLMClient.extract_program`/`extract_programs` gain the
+same two keyword-only parameters (accepted, ignored — canned responses
+never depend on them), so no existing fixture-test call site needs to
+change.
+
+**Competition profile field rules — the deadline-vs-event-date
+distinction, spelled out rather than left implicit:**
+- `date_start`/`date_end` are redefined for this profile: the
+  competition/event's own date (`date_start`; the first day if
+  multi-day) and its last day if multi-day, else empty (`date_end`) —
+  never a registration/application deadline. Explicit negative
+  instruction: "`date_end` is the event's own last day if it spans
+  multiple days; it is NOT a registration, sign-up, or paperwork
+  deadline — put that in `registration_deadline` instead, never here."
+- `registration_deadline` (new field, this profile only): a
+  registration/team-signup/paperwork deadline stated separately from the
+  event's own date, or `""` if none is stated or the page states only
+  one date. Directly fixes `seaperch-sd-regional`'s
+  TDR-deadline-swallows-event-date failure by giving the model a place
+  to put the deadline that isn't `date_start`/`date_end`.
+- Explicit phrasing guidance naming the patterns tickets 001/002 found
+  the model missing: "look for the date under any of: 'Event Date,'
+  'Competition Date,' 'Tournament Date,' 'Save the Date,' as well as
+  ordinary prose" — directly fixes `sd-brain-bee`'s "Event Date: February
+  14, 2026" miss (the pre-revision prompt's application-window framing
+  gave the model nothing to match this phrasing against).
+- Year inference, using the new `reference_date`: "If a date states a
+  month and day but no year, infer the soonest year (this one, or next)
+  in which that month/day falls on or after `<reference_date>` — never
+  leave the year off, and do not default to the current calendar year if
+  that month/day has already passed relative to the reference date." A
+  deliberate, narrow, named exception to this profile's (and the base
+  profile's, unchanged) general "never guess a date not stated"
+  instruction — scoped only to the year component of an otherwise-stated
+  month/day, via a mechanical, single-step rule rather than open-ended
+  guessing. Directly fixes `tritonhacks`'s wrong-year failure.
+
+**Design Rationale: fold `registration_deadline` into `Event.description`,
+not `Event.end`/`DEADLINE_FIRST_TYPES` — and why a distinct field is now
+justified when sprint 015 rejected one.**
+- *Decision*: `registration_deadline` is a new `ProgramExtractionResult`
+  field, mapped by `_map_result_to_event` onto `Event.description` (a
+  short note, e.g. "Registration deadline: `<date>`") when the resolved
+  `opportunity_type` is `"Competitions"` and the field is non-empty —
+  mirroring sprint 028's identical `resolved_opportunity_type ==
+  "Camps" and result.is_open is False → Event.description` branch
+  verbatim, in shape and in scope-narrowness. It is never mapped onto
+  `Event.start`/`Event.end`; `normalize/run.py`'s `DEADLINE_FIRST_TYPES`/
+  `_internship_availability` and `export/writer.py`'s
+  `is_current_or_upcoming` are unmodified.
+- *Context*: `normalize/DESIGN.md`'s sprint 015 addendum explicitly
+  rejected a distinct `application_deadline` field at that time: "No
+  adapter or the LLM prompt currently distinguishes a registration
+  deadline from an event's own end date/time for any non-internship
+  record, so a new field would have no real producer yet." This revision
+  is the first real producer — the competition profile genuinely
+  extracts a registration deadline distinct from the event date
+  (`seaperch-sd-regional`'s TDR deadline vs. its April 4 competition
+  date is exactly the case sprint 015 anticipated but had no evidence
+  for yet).
+- *Alternatives considered*: (a) do what the pre-revision prompt was
+  implicitly attempting — put the registration deadline in `date_end`,
+  the event's own date in `date_start`, and let the existing
+  deadline-first currency/sort/availability rules apply unchanged; (b)
+  remove `"Competitions"` from `DEADLINE_FIRST_TYPES` entirely, treating
+  every competition record with the plain "`date_end` or `date_start` >=
+  today" currency rule.
+- *Why this choice, over (a)*: (a) is the direct cause of
+  `seaperch-sd-regional`'s failure — `date_end` cannot simultaneously
+  mean "the event's own last day, if multi-day" (needed for
+  `tritonhacks`' May 16-17 span) and "a separate registration deadline"
+  (needed for SeaPerch's TDR cutoff) when a single page can carry both
+  facts about two different dates at once. Overloading one field for two
+  distinct real-world dates is exactly the ambiguity the model was
+  already failing on; giving each its own field removes the ambiguity
+  from the prompt rather than asking the model to keep guessing which
+  one field on the page it is supposed to describe.
+- *Why this choice, over (b)*: `"Competitions"` has carried a second,
+  unrelated, already-shipped meaning in `DEADLINE_FIRST_TYPES` since
+  sprint 015 — a `generic_html`-sourced record whose only actionable
+  date *is* a submission/registration deadline (the Health Pitch
+  Competition case). That case has no `kind="program"`/`program_llm.py`
+  involvement at all; its `date_end` genuinely is its deadline, and the
+  currency/sort/availability behavior `DEADLINE_FIRST_TYPES` gives it
+  today is correct for it. `DEADLINE_FIRST_TYPES` is `opportunity_type`-
+  keyed by deliberate design (`normalize/DESIGN.md`'s sprint 027 Design
+  Rationale: kind-awareness in `export/writer.py` was rejected as a
+  speculative `Opportunity` schema change), so there is no way to
+  special-case "program-page-sourced Competitions get event-first
+  semantics, `generic_html`-sourced Competitions keep deadline-first
+  semantics" without either reintroducing that rejected `kind` threading
+  or splitting `"Competitions"` into two `opportunity_type` values (a
+  real taxonomy change, explicitly Out of Scope for sprint 029).
+  Changing the shared rule would fix program-page competitions at the
+  cost of silently regressing the pitch-competition case this revision
+  has no live evidence about and no mandate to touch.
+- *Consequences*: a program-page-sourced Competitions record's currency
+  now behaves exactly like an ordinary dated event under
+  `DEADLINE_FIRST_TYPES`'s existing "no `date_end` → `date_start` within
+  `_DEADLINE_FIRST_STALE_POSTING_DAYS` (365 days) counts as current"
+  rule — a pre-existing, already-accepted allowance (not tightened or
+  loosened by this revision), somewhat more permissive than "`date_start`
+  must be strictly in the future" for a single-day event with no
+  `registration_deadline`. This is unchanged, pre-existing
+  `DEADLINE_FIRST_TYPES` behavior for every `Competitions` record today
+  (RobotEvents/TEC-backed included), not a new risk this revision
+  introduces — noted here, not re-litigated (see §6's new Open
+  Question). `registration_deadline`'s own currency is not tracked at
+  all (descriptive text only); a registration deadline that has passed
+  while the event itself is still upcoming does not affect the record's
+  export status, which is the correct behavior — the event, not the
+  registration window, is what the record should stay current for.
+
+**Design Rationale: `ProgramExtractionCache._CACHE_SCHEMA_VERSION` bumps
+2 → 3.**
+- *Decision*: bump `_CACHE_SCHEMA_VERSION` from 2 to 3, per this module's
+  own documented rule ("bumped whenever `ProgramExtractionResult`'s
+  shape changes").
+- *Context*: `registration_deadline` is a new required field on the
+  dataclass the JSON schema is built from (`_build_program_extraction_
+  json_schema()`'s dataclass introspection); a stored pre-revision cache
+  entry has no such key.
+- *Why this choice*: matches the ticket 006 exception revision's
+  identical precedent (1 → 2, for the `lookup_many`/`store_many` shape)
+  exactly — forces exactly one harmless re-extraction of any
+  already-cached URL, which the cache's own "stale `schema_version` is a
+  miss, not a deserialization error" contract already handles with no
+  further code change. This bump additionally does necessary, not
+  merely tidy, work here: tickets 001/002's real dry-runs already
+  populated cache entries for all six of this revision's affected
+  sources under the *old*, since-corrected prompt; without the bump,
+  ticket 007's re-verification would read back those stale entries and
+  never call the corrected prompt at all, silently reproducing the
+  exact failures this revision fixes.
+- *Consequences*: identical, already-accepted cost shape to the ticket
+  006 precedent — one extra LLM call per previously-cached program-page/
+  listing/multi URL project-wide on the next run, not only for this
+  revision's six sources.
+
+**Design Rationale: SD Math Circle's grid-shaped sheet is explicitly out
+of scope for this revision.**
+- *Decision*: no attempt is made to extend `extract_programs()` to
+  recover per-row dated items from a page whose primary shape is a dense
+  weekly-schedule grid with competition dates as one-off rows inside it.
+  `sd-math-circle` stays `enabled = false`.
+- *Context*: ticket 002's own live-verification already isolated this as
+  a distinct failure axis from the deadline-vs-event-date framing bug
+  this revision fixes — the AMC/AIME dated rows survive
+  `reduce_html_to_text()` intact and are present in the exact text sent
+  to the model; the failure is that `extract_programs()`'s framing
+  ("identify every distinct program described on the page") locks onto
+  the sheet's 5 recurring class-group columns instead of the scattered
+  one-off competition rows, a wrong-axis-of-extraction problem no amount
+  of deadline-vs-event-date prompt correction touches.
+- *Alternatives considered*: (a) fix it in this revision anyway, via
+  grid/tabular-aware field rules or a per-row extraction pass; (b) point
+  `config.url` at the individual `/events/<slug>` detail pages
+  `sd-math-circle.toml`'s own header comment already names
+  (`sdmathcircle.org/events/amc-10-12-a`, `/events/aime`, `/events/arml`,
+  `/events/math-kangaroo`) as a `program_listing` or several individual
+  `program_page` sources instead of the grid sheet.
+- *Why this choice*: (a) is a materially different extraction mechanism
+  (per-row/per-cell reasoning over a schedule grid, not per-section
+  reasoning over a page of prose sections) that the team-lead's own
+  dispatch explicitly permits deferring rather than forcing; building it
+  now, on evidence from exactly one grid-shaped source, risks the
+  speculative-generality trap this codebase's architecture principles
+  already warn against repeatedly. (b) is a real, promising alternative —
+  live-verified detail pages likely have the same single-event shape
+  this revision's competition profile already handles well — but it is
+  untested at architecture-authoring time (no ticket has live-verified
+  those detail pages' actual content) and changes `sd-math-circle.toml`'s
+  registration shape entirely, ticket-level work, not something to
+  design blind here.
+- *Consequences*: `sd-math-circle` remains disabled after this revision;
+  ticket 007 (below) does not include it in its re-verification set. (b)
+  is recorded here as the likely next step for a follow-up issue — not
+  built speculatively now.
+
 ## 5. Interfaces
 
 ### Exposes
@@ -677,7 +983,12 @@
   `FixtureLLMClient` but never importing them (see §4). **(Ticket 006 exception
   revision)** `ProgramLLMClient` gains a second method, `extract_programs(url, body) ->
   list[ProgramExtractionResult]`, for `program_page_multi`'s one-page/N-record shape;
-  both real and fixture implementations now support both methods.
+  both real and fixture implementations now support both methods. **(Sprint 029
+  revision)** both methods gain two keyword-only parameters, `profile: str = "program"`
+  and `reference_date: date | None = None` (see §4) — additive, every existing call site
+  that omits them is unaffected. `ProgramExtractionResult` gains one new field,
+  `registration_deadline: str = ""`, populated only by `profile="competition"` (see §4's
+  Design Rationale for why this field exists rather than reusing `date_end`).
 - **`ActiveNetCampsAdapter(llm_client=None, cache=None)`, `CampBrainAdapter(llm_client=
   None, cache=None)`** (sprint 028) — the two new camp-platform adapter types; see §4's
   Design. Same constructor-injection shape as the `program_page` family, for the same
@@ -695,7 +1006,10 @@
   (URL, not `Event.identity_key()` — no `Event` exists yet at fetch time). **(Ticket 006
   exception revision)** gains `lookup_many`/`store_many`, the list-valued counterpart to
   `lookup`/`store`, for `program_page_multi`; `_CACHE_SCHEMA_VERSION` is bumped once for
-  the new entry shape (see §4).
+  the new entry shape (see §4). **(Sprint 029 revision)** `_CACHE_SCHEMA_VERSION` bumps
+  again, 2 → 3, for `registration_deadline`'s addition to `ProgramExtractionResult` — see
+  §4's Design Rationale for why this bump is load-bearing, not only tidy, for this
+  revision specifically.
 
 ### Consumes
 - **`Fetcher` (from `fetch/`)** — every remote read. Injected per call; see `fetch/DESIGN.md`.
@@ -819,3 +1133,34 @@
 - **(Sprint 028)** Pike13 (issue 29's third-priority platform) is deferred, along with
   its own open question — whether it supersedes gaps in the already-shipped `leaguesync`
   adapter for the League's own camps — to a follow-up issue. Not designed here.
+- **(Sprint 029 revision, new)** Does ticket 003's SD Festival / EXPO Day listing need
+  the competition profile too? Ticket 003 (SUC-046) deliberately sets no
+  `config.opportunity_type` override — its ~35 festival-week pages mix workshops, the
+  EXPO Day showcase, and competitions, so each page's type is left to the LLM's own
+  per-page classification. This revision's profile selection is driven by
+  `source.config.get("opportunity_type") == "Competitions"`, which does **not** fire for
+  ticket 003's source at all — every one of its ~35 LLM calls still uses the default,
+  unrevised "program" profile, regardless of whether a given page turns out to be a
+  single-dated event (a workshop, EXPO Day itself) rather than an application-window
+  program. If ticket 003's own live verification finds the Mar 7 2026 EXPO Day date (or
+  another festival-week event's date) fails to surface for the same deadline-vs-event-date
+  reason this revision fixes, the documented fallback is to widen profile selection to
+  also fire on the *LLM's own self-classified* `opportunity_type` — inspect one
+  extraction's `result.opportunity_type` and, if it comes back `"Competitions"` on a page
+  with no config override, decide whether a second corrective call is worth its extra LLM
+  cost, or whether the single-call self-classifying prompt should itself gain a soft "if
+  this appears to be a single dated event rather than an application-window program,
+  prefer this wording" instruction. Not designed further here — this revision was not
+  asked to solve ticket 003's use case ahead of its own live evidence, and doing so risks
+  solving a problem ticket 003's real pages may not actually have. Ticket 003's own scope
+  is otherwise unchanged.
+- **(Sprint 029 revision, new)** `DEADLINE_FIRST_TYPES`'s existing 365-day
+  `_DEADLINE_FIRST_STALE_POSTING_DAYS` allowance (a `Competitions` record with no
+  `date_end` counts as current if `date_start` is anywhere from 365 days in the past to
+  any point in the future) is somewhat more permissive than a plain "must be in the
+  future" rule for a genuinely single-day, no-`registration_deadline` competition event —
+  this is pre-existing behavior for every `Competitions` record since sprint 020, not
+  something this revision changes or newly introduces (see §4's Design Rationale
+  Consequences). Not solved here; revisit only if this is observed to surface a stale
+  single-day competition in production, the same "not built speculatively" standard every
+  other entry in this section already applies.
```

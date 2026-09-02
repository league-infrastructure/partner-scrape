---
source_file: adapters-DESIGN.md
source_hash: b411723c277adfcd4bafc807f2d50f2d57d535f2807934fe6888fda568cdc554
---
# Diff: adapters-DESIGN.md

Comparison of the sprint overlay copy of `adapters-DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- adapters-DESIGN.md (pristine)
+++ adapters-DESIGN.md (current)
@@ -1,8 +1,234 @@
 # Adapters
 
-**Owner:** Eric Busboom · **Last reviewed:** 2026-09-02 (sprint 030 — `pd` extraction profile added) · **Status:** stable
+**Owner:** Eric Busboom · **Last reviewed:** 2026-09-02 (sprint 031 — Workday/NEOGOV/SmartRecruiters/Workable ATS adapters) · **Status:** stable
 
 ---
+
+## Revision (2026-09-02 — sprint 031 four new ATS adapters)
+
+Issue 31's verified San Diego ATS census (2026-08-30) adds four new
+`adapter_type` values — `workday`, `neogov`, `smartrecruiters`,
+`workable` — a seventeenth through twentieth adapter type, all in the
+same "ATS — internship-filtered" family `greenhouse`/`lever` already
+established in sprint 006: fetch a vendor's public job-board JSON, run
+every posting through the unchanged `adapters/ats_filters.py`
+(internship + STEM + San-Diego-local), and emit `kind="internship"`
+`Event`s for matches only. Sony Interactive Entertainment is also
+registered against the *existing* `greenhouse` adapter — a
+`registry/`-only change, zero lines of adapter code. A sixth,
+unrelated piece of this sprint — a probe pass over six unconfirmed-ATS
+employers (Qualcomm, Solar Turbines, Teradata, BAE, General Atomics,
+Intuit) — deliberately produces findings, not a new adapter family;
+see this section's own Design Rationale below for why.
+
+**No changes needed to `enrich/`, `normalize/`, or `export/`.**
+Confirmed by reading all three before designing on top of them (the
+team-lead's own explicit ask, mirroring sprint 029's precedent above):
+`enrich/enricher.py`'s `kind in PROGRAM_EXTRACTION_KINDS` bypass and
+`normalize/run.py`'s identical-keyed collapse/dedup bypass and
+deadline-first availability branch, and `export/writer.py`'s
+`Work-based Learning` current/upcoming rule, are all already generic
+across *any* adapter that sets `kind="internship"` — sprint 006 built
+them for `greenhouse`/`lever` specifically and sprint 027 generalized
+the `kind` check from `"internship"` alone to
+`PROGRAM_EXTRACTION_KINDS`, but neither ever hardcoded which adapter
+produces the record. This sprint's four new adapters inherit that
+downstream behavior with zero further code, the same way sprint 016's
+`robotevents` and sprint 006's own `greenhouse`/`lever` already do for
+their own respective concerns.
+
+**Component diagram (required: 3+ modules touched, a new cross-module
+capability on the `adapters` → `fetch` edge).**
+
+```mermaid
+graph LR
+    Registry["Source Registry<br/>(registry/sources/*.toml,<br/>new company/agency entries)"]
+    Dispatch["Adapter Dispatch<br/>(adapters/base.py, unchanged)"]
+    GH["Greenhouse Adapter<br/>(adapters/greenhouse.py,<br/>unchanged code; +Sony)"]
+    WD["Workday Adapter<br/>(adapters/workday.py, new)"]
+    NG["NEOGOV Adapter<br/>(adapters/neogov.py, new)"]
+    SR["SmartRecruiters Adapter<br/>(adapters/smartrecruiters.py, new)"]
+    WK["Workable Adapter<br/>(adapters/workable.py, new)"]
+    ATSFilters["ATS Filters<br/>(adapters/ats_filters.py, unchanged)"]
+    FetchGet["Fetcher.get()<br/>(fetch/, unchanged)"]
+    FetchPost["Fetcher.post()<br/>(fetch/, NEW)"]
+
+    Dispatch -->|adapter_type=greenhouse| GH
+    Dispatch -->|adapter_type=workday| WD
+    Dispatch -->|adapter_type=neogov| NG
+    Dispatch -->|adapter_type=smartrecruiters| SR
+    Dispatch -->|adapter_type=workable| WK
+    GH -->|classify posting| ATSFilters
+    WD -->|classify posting| ATSFilters
+    NG -->|classify posting| ATSFilters
+    SR -->|classify posting| ATSFilters
+    WK -->|classify posting| ATSFilters
+    GH -->|fetch| FetchGet
+    NG -->|fetch| FetchGet
+    SR -->|fetch| FetchGet
+    WK -->|fetch| FetchGet
+    WD -->|fetch, NEW verb| FetchPost
+    Registry -->|SourceConfig| Dispatch
+```
+
+Every edge except `WD -> FetchPost` already existed in shape (a
+different adapter type using an already-established dependency); that
+one edge is this sprint's real new composition, which is why the
+diagram is included despite four of the five new/touched modules being
+same-shape repeats of the existing ATS-family pattern (`greenhouse.py`/
+`lever.py`, unchanged, are omitted from this diagram's "touched" set
+except as the Sony registration's target — `lever.py` itself is not
+touched at all this sprint and is left off entirely). No ERD: no
+`Event`/`Opportunity` field changes. No separate dependency graph: every
+edge above is a real, already-shown dependency; a second diagram would
+be node-for-node identical, matching sprint 006's own precedent for
+this exact family.
+
+**The one genuinely new mechanism: Workday needs a `POST`, not a
+`GET`.** `POST /wday/cxs/{tenant}/{site}/jobs` (search text, pagination
+offset, facet filters, all in the request body) has no GET-based
+equivalent — see `fetch/DESIGN.md`'s own sprint 031 section for the
+`Fetcher.post()` addition this requires and its Design Rationale.
+`workday.py` is the only module in this sprint (or this codebase) that
+calls it.
+
+**Workday adapter (`adapters/workday.py`, new).** `discover()` probes
+`offset=0` against each source's configured tenant/site pair (`config.
+tenant`, `config.site`, `config.api_base` — Workday's API host is
+sharded per tenant, e.g. `{tenant}.wd5.myworkdayjobs.com`, so unlike
+Greenhouse's single global default host, every Workday source likely
+needs its own `api_base` value, confirmed per tenant during live
+verification) to learn `total`, then returns one `EventRef` per page
+(`context={"offset": N}`) — the same probe-then-paginate shape
+`tec_rest`/`localist` already use, adapted to a POST body's offset
+field instead of a GET query parameter. `fetch()` issues each page's
+`POST` via the new `Fetcher.post()`, with browser-like headers (see
+Design Rationale below). `extract()` maps each `jobPostings[]` entry
+(title, `locationsText`, `externalPath` joined onto the site's careers
+base URL for the apply link) through `ats_filters.classify_posting`
+exactly like every other ATS adapter in this family; matches become
+`kind="internship"` `Event`s. Northrop Grumman (including its HS
+Internship Program req), Cubic, Illumina, and Dexcom are the required
+registrations; ResMed and Sempra/SDG&E are registered only if this
+sprint's own live verification confirms their tenant/site pair
+(best-effort, per issue 31's own "likely," not a required outcome).
+
+**Design Rationale: leave `Event.start` unset for a Workday posting
+whose only date signal is a relative string.**
+- *Decision*: when a Workday `jobPostings[]` entry's `postedOn` field
+  is a relative string ("Posted Today", "Posted 30+ Days Ago" — the
+  only date field Workday's list-view API returns; there is no absolute
+  timestamp), `_extract_one` leaves `Event.start` unset rather than
+  parsing or guessing an absolute date from it.
+- *Context*: `greenhouse.py`/`lever.py` both parse an absolute
+  timestamp (`updated_at`, `createdAt`) directly from their respective
+  APIs; Workday's list endpoint has no equivalent field.
+- *Alternatives considered*: (a) compute an approximate `Event.start`
+  by subtracting the relative string's implied day count from
+  "today" (e.g. "Posted 30+ Days Ago" → 30 days before the run's own
+  date); (b) treat "Posted Today" as `start = today` and leave every
+  other relative string unset.
+- *Why this choice*: both (a) and (b) fabricate a date the source
+  itself never actually asserts — exactly the failure mode issue 40
+  documents for a different mechanism (LLM extraction inferring a date
+  from a reference date with no textual support) and this codebase has
+  already paid a real cost to catch. A Workday posting's genuine
+  "when" is "currently live in the ATS," not a specific calendar date;
+  `normalize.run()`'s existing internship rolling-availability branch
+  (built in sprint 006 for exactly the "no known deadline" case,
+  `_internship_availability`) already handles an unset `start`/`date_end`
+  correctly — there is no downstream gap a fabricated date would be
+  filling.
+- *Consequences*: a Workday-sourced internship displays with
+  "Rolling"/no-deadline availability semantics, identical to a
+  Greenhouse/Lever posting with no parseable date, rather than a
+  fabricated post date. No `Opportunity`/`export/writer.py` change
+  needed — this reuses sprint 006's existing rolling-availability path
+  unchanged.
+
+**NEOGOV adapter (`adapters/neogov.py`, new — shape pending live
+verification).** Unlike Workday/SmartRecruiters/Workable, issue 31's
+census does not carry a confirmed endpoint shape for
+`governmentjobs.com` — only that County of San Diego, City of San
+Diego, SANDAG, and Port of San Diego each publish through it. This
+sprint's ticket accordingly opens with a live-verification step before
+any parsing code is written: if a structured JSON endpoint exists,
+`neogov.py` follows this family's usual shape with a per-source
+`config.agency` key identifying which of the four agencies a given
+registration is for (one adapter, four sources, per the roadmap plan);
+if postings are reachable only as rendered HTML, the ticket registers
+each agency through the *existing* `generic_html`/`listing_html`
+adapter instead — a legitimate, in-scope pivot, not a new adapter type,
+and not a scope failure. See `registry/DESIGN.md`'s own sprint 031
+section for the registration-side implication either way.
+
+**SmartRecruiters adapter (`adapters/smartrecruiters.py`, new).** Public
+GET `api.smartrecruiters.com/v1/companies/{company}/postings`, paginated
+via `offset`/`limit` (probe-then-paginate, same shape as `tec_rest`/
+`localist`). `extract()` maps `content[]` (`name` as title,
+`typeOfEmployment.label` as the commitment signal passed to
+`classify_posting`, `department.label`, `location.city`/
+`location.region`, `releasedDate`, `postingUrl`/`applyUrl`) through
+`ats_filters.classify_posting`; matches become `kind="internship"`
+`Event`s. ServiceNow is the first registered source.
+
+**Workable adapter (`adapters/workable.py`, new).** Public GET against
+the account's Workable widget JSON endpoint (`apply.workable.com`),
+not paginated for a company this sprint's size — mirroring
+`greenhouse.py`'s "no probe-then-paginate" precedent, pending
+ticket-time confirmation the SD County Regional Airport Authority's
+own account is genuinely unpaginated. `extract()` maps each posting
+(`title`, `employment_type` as the commitment signal,
+`department`, `location.city`/`location.region`, `created_at`,
+`url`/`shortcode`) through `ats_filters.classify_posting`; matches
+become `kind="internship"` `Event`s. SD County Regional Airport
+Authority is the first registered source, confirmed to include paid
+9-week summer internships.
+
+**Sony Interactive Entertainment (registry-only, zero adapter code).**
+A new `registry/sources/*.toml` entry with `adapter_type = "greenhouse"`
+and `config.board_token = "sonyinteractiveentertainmentglobal"` — the
+existing `adapters/greenhouse.py` is unmodified. This is the same
+"onboarding is a data edit" property every structured-API adapter in
+this codebase already has (`registry/DESIGN.md` §1); it is listed here
+only because issue 31 names it alongside the four new adapters, not
+because it touches this module.
+
+**Design Rationale: the six unconfirmed-ATS employers get a probe
+ticket, not four speculative adapters.**
+- *Decision*: Qualcomm (Eightfold-ish, previously 403), Solar Turbines,
+  Teradata, BAE (Phenom), General Atomics (BrassRing), and Intuit
+  (Radancy) are live-probed for a reachable, structured endpoint —
+  recording findings per employer — with no new adapter module written
+  for any of them this sprint, regardless of what the probe finds,
+  unless an employer turns out to already run one of this codebase's
+  *existing* adapter types under an unlisted board/company name (in
+  which case registering it is data-only, not new adapter work, and
+  stays in scope).
+- *Context*: issue 31 explicitly separates these six from the four
+  confirmed vendors, naming each one's *apparent* ATS platform
+  (Eightfold, Phenom, BrassRing, Radancy) without a verified public
+  endpoint for any of them, and says explicitly to "probe before
+  building anything bespoke."
+- *Alternatives considered*: build a bespoke adapter for each platform
+  speculatively, on the assumption that a named ATS vendor implies a
+  reachable public API shaped similarly to Greenhouse/Lever/
+  SmartRecruiters/Workable.
+- *Why this choice*: none of these four platforms (Eightfold, Phenom,
+  BrassRing, Radancy) has a confirmed-live, unauthenticated, public
+  postings endpoint the way Workday/NEOGOV/SmartRecruiters/Workable do
+  — Qualcomm's own endpoint already 403s per issue 31's own prior
+  probe. Building four more adapter modules against an *assumed* shape
+  risks the same speculative-generality trap this codebase's own
+  architecture principles warn against repeatedly (`adapters/DESIGN.md`'s
+  own sprint 028 Design Rationale entries above), compounded four times
+  over with no live evidence any of the four is even reachable without
+  a credential or a headless browser.
+- *Consequences*: this sprint adds no fifth ATS-vendor-specific module
+  beyond the four confirmed ones. A follow-up issue is recommended, not
+  filed, for whichever employer(s) the probe finds genuinely buildable
+  — see `sprint.md`'s Architecture > Migration Concerns for why no
+  issue number exists yet.
 
 ## Revision (2026-09-02 — sprint 030 educator-PD extraction profile)
 
@@ -386,14 +612,15 @@
 `ADAPTERS` dispatch dict, instantiates it, materializes `discover()`'s output, truncates
 it to the source's `max_urls` cap, then loops fetch→extract accumulating events.
 
-Sixteen adapter types are registered today, in four families:
+Twenty adapter types are registered today, in five families (sprint 031 adds a fifth):
 
 | Family | Types | Shape |
 |---|---|---|
-| Structured API | `tec_rest`, `wp_rest`, `ical`, `localist`, `bibliocommons`, `greenhouse`, `lever`, `leaguesync`, `robotevents` | Known endpoint, JSON/iCal parsing, `CONFIDENCE = 1.0` |
+| Structured API | `tec_rest`, `wp_rest`, `ical`, `localist`, `bibliocommons`, `leaguesync`, `robotevents` | Known endpoint, JSON/iCal parsing, `CONFIDENCE = 1.0` |
 | HTML | `generic_html`, `listing_html` | URL discovery via `discovery/`, field recovery via `extract/`'s ladder |
 | LLM extraction (sprint 027) | `program_page`, `program_listing`, `program_page_multi` | One registered page (or one crawled listing's cards, or one page read as N inline records), field recovery via a bespoke `ProgramLLMClient` call, never `extract/`'s ladder |
-| **Camp platform (sprint 028)** | `activenet_camps`, `campbrain` | One registered per-organization camp-listing endpoint on a known registration platform; session records recovered deterministically when the platform exposes a parseable JSON response, else via the same `ProgramLLMClient.extract_programs()` call `program_page_multi` uses — either way, normalized into `ProgramExtractionResult` before mapping |
+| Camp platform (sprint 028) | `activenet_camps`, `campbrain` | One registered per-organization camp-listing endpoint on a known registration platform; session records recovered deterministically when the platform exposes a parseable JSON response, else via the same `ProgramLLMClient.extract_programs()` call `program_page_multi` uses — either way, normalized into `ProgramExtractionResult` before mapping |
+| **ATS — internship-filtered (sprint 006, sprint 031)** | `greenhouse`, `lever`, `workday`, `neogov`, `smartrecruiters`, `workable` | Known job-board endpoint (GET for every type except `workday`, which needs `POST`); every raw posting run through the shared `ats_filters.classify_posting()` (internship + STEM + San-Diego-local) before becoming a `kind="internship"` `Event` — the only family whose adapters *reject* most of what they fetch by design |
 
 **(Ticket 006 exception revision) `program_page_multi`.** A third LLM-extraction type,
 alongside `program_page`/`program_listing`: one registered page whose body contains N
@@ -1080,7 +1307,14 @@
 - **`get_adapter(adapter_type) -> Adapter`** — instantiates a registered adapter; raises
   `UnknownAdapterType` with the known-type list rather than a bare `KeyError`.
 - **`ats_filters.classify_posting(...) -> PostingVerdict`** — shared internship/STEM/
-  locality classification for the ATS adapters.
+  locality classification for the ATS adapters. **(Sprint 031)** unchanged; now shared by
+  six adapters (`greenhouse`, `lever`, `workday`, `neogov`, `smartrecruiters`, `workable`)
+  instead of two.
+- **`WorkdayAdapter`, `NeoGovAdapter`, `SmartRecruitersAdapter`, `WorkableAdapter`**
+  (sprint 031, new) — the four new ATS adapter types. Same `discover → fetch → extract`
+  shape as `GreenhouseAdapter`/`LeverAdapter`; `WorkdayAdapter` is the only adapter in the
+  codebase whose `fetch()` calls `Fetcher.post()` instead of `.get()` — see `fetch/
+  DESIGN.md`'s own sprint 031 section.
 - **`acquisition_kwargs(source: SourceConfig) -> dict[str, Any]`** — **(Sprint 015
   ticket 003)** the `rate_limit_seconds`/`respect_robots` kwargs for `fetcher.get()`,
   read from `source.acquisition_policy`. Consumed by every `fetch()` implementation in
@@ -1128,6 +1362,8 @@
 
 ### Consumes
 - **`Fetcher` (from `fetch/`)** — every remote read. Injected per call; see `fetch/DESIGN.md`.
+  **(Sprint 031)** `workday.py` is the first and only consumer of `Fetcher.post()`, the
+  new second method on the Protocol — see `fetch/DESIGN.md`'s own sprint 031 section.
 - **`SourceConfig` and `DEFAULT_MAX_URLS_PER_SOURCE` (from `registry/`)** — the per-source
   data that drives dispatch and the URL cap. See `registry/DESIGN.md`.
 - **`Event`, `Provenance` (from `model.py`)** — the output record. See the root
@@ -1269,6 +1505,24 @@
   asked to solve ticket 003's use case ahead of its own live evidence, and doing so risks
   solving a problem ticket 003's real pages may not actually have. Ticket 003's own scope
   is otherwise unchanged.
+- **(Sprint 031, new)** Whether browser-like headers alone clear Workday's 403 for every
+  tenant, or only some, is unconfirmed at architecture-authoring time — issue 31's own
+  census establishes only that a headerless plain request 403s. A tenant that stays
+  blocked even with headers (a TLS/JA3-fingerprint-level block) is registered
+  `enabled = false` with a comment naming the finding; a headless-browser-driven POST
+  (e.g. via Playwright's `page.request` API, `fetch/headless.py`'s existing raw-resource
+  path) is the documented next step for a future issue, not attempted here.
+- **(Sprint 031, new)** NEOGOV/`governmentjobs.com`'s real endpoint shape is unconfirmed
+  at architecture-authoring time (unlike Workday/SmartRecruiters/Workable, whose shapes
+  issue 31's own census already verified) — see this section's NEOGOV write-up above for
+  the ticket-level live-verification-first plan and the documented pivot to
+  `generic_html`/`listing_html` if no structured endpoint exists.
+- **(Sprint 031, new)** The probe pass over Qualcomm/Solar Turbines/Teradata/BAE/General
+  Atomics/Intuit may find one or more genuinely buildable — no follow-up issue is filed in
+  advance of that finding (see `sprint.md`'s Architecture > Migration Concerns). A future
+  sprint picking this up should re-verify live rather than trusting this sprint's probe
+  findings unchanged, the same "re-verify, don't assume yesterday's census still holds"
+  standard this document's own sprint 014/029 revisions already establish.
 - **(Sprint 029 revision, new)** `DEADLINE_FIRST_TYPES`'s existing 365-day
   `_DEADLINE_FIRST_STALE_POSTING_DAYS` allowance (a `Competitions` record with no
   `date_end` counts as current if `date_start` is anywhere from 365 days in the past to
```

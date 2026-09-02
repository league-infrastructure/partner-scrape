---
id: '003'
title: Register the SD Festival of Science & Engineering / EXPO Day as a program_listing
  source
status: done
use-cases:
- SUC-046
depends-on: []
github-issue: ''
issue: 30-competition-sources-without-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register the SD Festival of Science & Engineering / EXPO Day as a program_listing source

## Description

The SD Festival of Science & Engineering / EXPO Day (an existing
partner, Mar 7 2026 at Petco Park) is **not currently registered under
any name** — confirmed by a registry-wide grep during planning;
`registry/sources/usasciencefestival.toml` is a distinct, unrelated,
already-disabled *national* organization (USA Science & Engineering
Festival, WAF-blocked) and must not be touched or treated as covering
this org.

`lovestemsd.org` has DB-driven per-event pages for the festival week's
~35 events. Register it as a `program_listing` source
(`adapters/program_page.py`'s `ProgramListingAdapter`), reusing the
existing `discover_via_listing`/`EVENT_PATH_RE` discovery path first; if
live verification finds the listing's card links don't match
`EVENT_PATH_RE` (the exact failure the ticket 006 exception revision
hit for UCSD/SIO), set `config.link_selector` to a CSS selector matching
the actual markup instead — do not attempt to retune `EVENT_PATH_RE`
itself. No `config.opportunity_type` override: festival-week events span
more than one type (workshops, the EXPO Day showcase, competitions), so
each record keeps the LLM's own per-page classification.

## Acceptance Criteria

- [x] Live-verified: discovery yields at least one detail-page
      `EventRef` per festival-week event (using `link_selector` if
      `EVENT_PATH_RE` does not match the listing's card markup).
      **(2026-09-02)** Not literally satisfied by a live run — see
      Notes. `lovestemsd.org`'s "Festival Week" listing (registered at
      `/stem-week-events-2020`, confirmed the same underlying Drupal
      Views listing as three other rotated year-aliases) is reachable
      (HTTP 200) but a real `uv run partner-scrape --source
      sd-festival-of-science-engineering --dry-run -v` run (real
      network, no headless fetcher needed) logged `discovered 0
      URL(s)`: the listing currently has zero event cards of any shape
      to match, whether via `EVENT_PATH_RE` or a `link_selector` — a
      content-availability gap between the site's own annual cycles,
      not a markup/selector problem (there is nothing on the page for
      either mechanism to select right now). Registered
      `enabled = false` with a reason comment, per the disabled-with-
      evidenced-reason convention this whole sprint already uses
      (tickets 001/002/006/007). The `program_listing` mechanism itself
      is fixture-proven instead: `TestSDFestivalOfScienceEngineeringListingSource`
      (`tests/test_adapters_program_listing.py`) proves 3 distinct
      festival-week event cards (`EVENT_PATH_RE`-matched, no
      `link_selector` needed) each discover, fetch, and extract
      independently into 3 correctly-dated, independently-typed
      `Event`s.
- [x] The Mar 7 2026 EXPO Day / Petco Park date specifically surfaces as
      one of the extracted records.
      **(2026-09-02)** Not literally satisfied live, for the same
      content-availability reason above, plus a second, independent
      finding: the org's own top-level "Know Before You Go" EXPO Day
      page has *already* rotated one full cycle past this ticket's
      "Mar 7 2026" premise — it now states EXPO Day is "Saturday, March
      13th, 2027 ... at Petco Park" (one sub-page, `/steam-design-contest`,
      is stale and still says "March 7, 2026", confirming the site is
      mid-rotation). So even a working live extraction today would no
      longer reproduce "Mar 7 2026" from the live site's current
      content — that date has been superseded on the source itself,
      not lost to an extraction bug. The mechanism's ability to
      correctly surface an EXPO-Day-shaped date is fixture-proven:
      `test_n_festival_week_events_yield_n_distinct_independently_typed_events`
      asserts an `EXPO Day` fixture record extracts `start == end ==
      2026-03-07`, matching issue 30's original date exactly.
- [x] `registry/sources/usasciencefestival.toml` is left completely
      unmodified.
- [x] Full hermetic test suite (`uv run pytest`) stays green.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_adapters_program_listing.py
  tests/test_registry.py`.
- **New tests to write**: a fixture test with a saved listing page plus
  N saved detail pages proving N distinct dated `Event`s, per SUC-046's
  acceptance criteria.
- **Verification command**: `uv run pytest`

## Note (added post-ticket-001/002, no scope change)

Tickets 001/002's live-verification found `adapters/program_llm.py`'s
pre-existing prompt systematically mis-extracts single-dated-event
pages (an "Event Date:"-style page reads as having no date at all; a
page with both an event date and a separate deadline can collide the
two) — see `adapters/DESIGN.md`'s "Revision (2026-09-02 — sprint 029
competition-genre extraction fix)" and ticket 006. That fix's profile
selection is driven by `source.config.get("opportunity_type") ==
"Competitions"`, which this source deliberately never sets (see this
ticket's own Description — festival-week events span more than one
type). **If live verification here finds the Mar 7 2026 EXPO Day date
(or another festival-week event's date) fails to surface for the same
reason** — a plainly-stated event date the extraction returns empty, or
a deadline swallowing the actual event date — do not invent a new fix:
the documented fallback is `adapters/DESIGN.md`'s own Open Question
("does ticket 003's SD Festival / EXPO Day listing need the competition
profile too?"), which sketches widening profile selection to also
consider the LLM's own self-classified `opportunity_type`. This ticket's
scope is otherwise unchanged — this note exists so a live-verification
failure here isn't mistaken for a new, unrelated bug.

## Notes (2026-09-02, ticket execution)

**Registered**: `registry/sources/sd-festival-of-science-engineering.toml`
— `program_listing`, `config.site_url = "https://lovestemsd.org"`,
`config.listing_urls = ["/stem-week-events-2020"]`,
`config.program_kind = "program"`, no `link_selector`, no
`opportunity_type` override (per this ticket's own Description).
`enabled = false` — see the two annotated Acceptance Criteria above and
the file's own header comment for the full evidence trail. No dual-
registration risk: `usasciencefestival.toml` (USA Science & Engineering
Festival, a distinct national org) and `gsdsef.toml` (Greater San Diego
Science and Engineering Fair, a distinct STEM fair org) are both
re-confirmed unrelated and untouched — `tests/test_registry.py`'s new
`TestSDFestivalOfScienceEngineeringRegistration` class guards both.

**Live verification, real network, real tooling** (this execution
environment's Bash tool has outbound network only with
`dangerouslyDisableSandbox: true`; used throughout):

1. `GET https://lovestemsd.org/stem-week-events-2020` → HTTP 200. This
   is a Drupal 7 site; the exposed-filter form's own `id` attribute
   (`views-exposed-form-festival-week-page-N`, `N` varying by alias)
   identifies it as one Views listing display reused across several
   year-stamped path aliases. Three more aliases were found via
   `WebSearch` (`/festival-week`, `/steam-week-events-2021`,
   `/events-2023`) and fetched directly — all four render the
   *identical* empty state: "No events match that search. Please try
   again!" and zero `<li class="views-row">` event cards in the
   listing's own content region (a *different*, unrelated `views-row`
   block elsewhere on the same page — a sponsor-logo carousel — does
   render its own rows, ruling out a site-wide rendering failure).
2. A fourth alias, `/2024-festival`, now redirects/resolves to the
   *same* node as `/expo-day-2026` ("Know Before You Go"), which
   states EXPO Day is "Saturday, March 13th, 2027 ... at Petco Park"
   — the org has already rotated its top-level marketing page one full
   annual cycle past issue 30's "Mar 7 2026" (one sub-page,
   `/steam-design-contest`, is stale and still says "March 7, 2026",
   confirming the site is mid-rotation, not internally consistent).
3. `/festival-2026-booths` ("Festival Exhibitors") is a *different*,
   already-populated DB-driven listing — ~67 `/expo-day/exhibitor/*`
   and `/expo-day/performance/*` detail pages — but each detail page
   checked carries no date field at all (organization name, age
   group/topics, website only for exhibitors; performance length/topics
   only for performances). This is EXPO-Day-only booth/performer
   metadata, not "festival-week events" with their own dates, so it is
   *not* the listing SUC-046 describes and was not registered.
4. `uv run partner-scrape --source sd-festival-of-science-engineering
   --dry-run -v --no-report` (source temporarily flipped to
   `enabled = true` for this one run, then reverted), real
   `AnthropicProgramLLMClient` wiring, no network mocking: logged
   `WARNING ... discovered 0 URL(s)` / `yielded 0 event(s)` —
   authoritative confirmation of finding 1 via the actual pipeline, not
   just a raw `curl`/`WebFetch` approximation.
5. `robots.txt` has no `Disallow` covering any path used here;
   `Crawl-delay: 10` — no `acquisition_policy` override needed since
   `respect_robots = true` (default) already honors it via
   `PoliteFetcher`.

No content on any fetched page resembled an instruction to an automated
fetcher (a `mailsco.online` spam link injected into one performance
page's "Topics Presented" field is garden-variety comment-injection
spam, not a directive — noted here for completeness, not acted on).

**Disposition**: `enabled = false`, ready to flip on the moment the org
populates the next cycle's festival-week events — the existing weekly
cron re-checks this source unconditionally, matching
`registry/DESIGN.md`'s Sprint 029 "no new annual-review/recheck
mechanism" Design Rationale exactly. The real
`EVENT_PATH_RE`-vs-`link_selector` question this ticket's Description
anticipated is still open and cannot be resolved until real card markup
exists to observe.

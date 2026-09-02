---
id: '006'
title: 'Fix competition-genre extraction: date-vs-deadline framing, year inference,
  registration deadline field'
status: done
use-cases:
- SUC-044
depends-on: []
github-issue: ''
issue: 30-competition-sources-without-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix competition-genre extraction: date-vs-deadline framing, year inference, registration deadline field

## Description

Tickets 001/002's real (not WebFetch-only) live-verification found that
`adapters/program_llm.py`'s `_SYSTEM_PROMPT`/`_SYSTEM_PROMPT_MULTI` and
`_FIELD_EXTRACTION_RULES` — unchanged since sprint 027, written for that
sprint's application-window *program* genre (`date_start` = "the
application window's open date", `date_end` = "the application
deadline") — systematically mis-extract a genuinely different genre:
single-dated-event *competitions*. Three of this sprint's five disabled
single-event sources fail for exactly this reason (see
`adapters/DESIGN.md`'s "Revision (2026-09-02 — sprint 029
competition-genre extraction fix)" section and this sprint's own
`design/adapters-DESIGN.md` overlay for the full evidence and design
write-up — read both before starting):

- `sd-brain-bee.toml` — the fetched text plainly states "Event Date:
  February 14, 2026"; extraction recovers no date at all, reproduced
  across two calls.
- `seaperch-sd-regional.toml` — extraction consistently maps the
  Technical Design Report *submission deadline* (Mar 27 2026) into
  `date_end`, never recovering the actual Apr 4 2026 competition date
  that is also present in the fetched text.
- `tritonhacks.toml` — extraction recovers the correct month/day but
  the wrong year (no year appears near the dates in the fetched text;
  the model guessed one that was already past).

Implement the corrected mechanism exactly as designed in
`adapters/DESIGN.md`'s Revision section and this sprint's
`design/adapters-DESIGN.md` overlay:

1. **`adapters/program_llm.py`**:
   - Add two new keyword-only parameters to `ProgramLLMClient.
     extract_program`/`extract_programs` (Protocol, `AnthropicProgramLLMClient`,
     and `FixtureProgramLLMClient`): `profile: str = "program"` and
     `reference_date: date | None = None`. Both default to today's exact
     behavior — no existing call site that omits them changes behavior.
   - Add `_SYSTEM_PROMPT_COMPETITION`/`_SYSTEM_PROMPT_COMPETITION_MULTI`,
     sharing a new `_FIELD_EXTRACTION_RULES_COMPETITION`, selected by
     `profile == "competition"` (default `_SYSTEM_PROMPT`/
     `_SYSTEM_PROMPT_MULTI` otherwise). The competition field rules must:
     - Redefine `date_start`/`date_end` as the event's own date (first
       day / last day if multi-day) — explicitly **not** a registration
       deadline.
     - Name the phrasing patterns tickets 001/002 found the model
       missing: "Event Date," "Competition Date," "Tournament Date,"
       "Save the Date," in addition to ordinary prose.
     - Use the new `reference_date` (injected into the *user* prompt as
       "Page fetched on: `<ISO date>`", never the system prompt) for a
       narrow, explicit year-inference rule: if a date states a month
       and day but no year, infer the soonest year (this one or next) in
       which that month/day falls on or after the reference date — never
       leave the year off.
   - Add `registration_deadline: str = ""` to `ProgramExtractionResult`
     (a new dataclass field — the JSON schema updates automatically via
     the existing dataclass-introspection builders). It is populated
     only by the competition profile's field rules: a
     registration/team-signup/paperwork deadline stated *separately*
     from the event's own date, or `""` if none is stated or the page
     states only one date. Add one line to the base (unchanged)
     `_FIELD_EXTRACTION_RULES` too: "`registration_deadline`: always
     `""` for this page type — an application-window program's one
     deadline is already `date_end`," so the base profile's behavior for
     this newly-required field is fully specified, not left to unstated
     structured-output defaulting.
2. **`adapters/program_page.py`**:
   - `_extract_one_program`/`_extract_many_programs` compute `profile =
     "competition" if source.config.get("opportunity_type") ==
     "Competitions" else "program"` and pass it (plus `reference_date`,
     defaulting to `date.today()`) through to the `llm_client` call.
   - `_map_result_to_event` gains one new branch, mirroring sprint 028's
     `resolved_opportunity_type == "Camps" and result.is_open is False
     → Event.description = "Sold out"` precedent exactly in shape: when
     the resolved `opportunity_type` is `"Competitions"` and
     `result.registration_deadline` is non-empty, set
     `Event.description` to a short note (e.g. "Registration deadline:
     `<date>`"). Never map `registration_deadline` onto `Event.start`/
     `Event.end`, and make **no** change to `normalize/run.py`'s
     `DEADLINE_FIRST_TYPES` or `export/writer.py`'s `is_current_or_upcoming`
     — see the architecture doc's Design Rationale for why this was
     considered and rejected (it would regress the unrelated, already-
     shipped `generic_html`-sourced pitch-competition case sprint 015's
     `DEADLINE_FIRST_TYPES` membership serves).
3. **`adapters/program_cache.py`**: bump `_CACHE_SCHEMA_VERSION` from 2
   to 3 (documented rule: "bumped whenever `ProgramExtractionResult`'s
   shape changes"). This is load-bearing, not only tidy: tickets 001/002's
   real dry-runs already wrote cache entries for `sd-brain-bee`,
   `seaperch-sd-regional`, `tritonhacks`, `sdftc-league-play`,
   `botball-greater-sd`, and `sd-math-circle` under the *old*, now-fixed
   prompt — without this bump, ticket 007's re-verification would read
   those stale entries back and never invoke the corrected prompt at
   all.

**Do not touch `sdftc-league-play.toml`/`botball-greater-sd.toml`'s root
cause.** Both fail because their fetched, reduced text contains no
calendar date at all (nav/mission-statement copy; an apparently
client-side-rendered date widget) — a fetch/content-availability gap,
not a framing gap. This ticket's fix is not expected to re-enable them;
ticket 007 re-verifies all five candidates honestly rather than assuming
a shared cause.

**Do not attempt SD Math Circle's grid-extraction problem.** Explicitly
out of scope — see the architecture doc's Design Rationale. It stays
`enabled = false`.

## Acceptance Criteria

- [x] `ProgramLLMClient.extract_program`/`extract_programs` (Protocol,
      `AnthropicProgramLLMClient`, `FixtureProgramLLMClient`) accept
      `profile: str = "program"` and `reference_date: date | None =
      None`, both optional and backward-compatible — every existing
      test that constructs/calls these without the new parameters
      passes unchanged.
- [x] `_SYSTEM_PROMPT_COMPETITION`/`_SYSTEM_PROMPT_COMPETITION_MULTI` and
      `_FIELD_EXTRACTION_RULES_COMPETITION` exist, distinguish the
      event's own date from a registration deadline, name the "Event
      Date"/"Save the Date"-style phrasing patterns, and specify the
      reference-date-based year-inference rule.
- [x] `ProgramExtractionResult` gains `registration_deadline: str = ""`;
      the base (non-competition) profile's field rules explicitly say it
      is always `""` for that profile.
- [x] `program_page.py`'s `_extract_one_program`/`_extract_many_programs`
      select `profile` from `source.config.get("opportunity_type")`
      with no new registry `config` key.
- [x] `_map_result_to_event` sets `Event.description` from
      `registration_deadline` only for resolved `opportunity_type ==
      "Competitions"`, and never sets `Event.start`/`Event.end` from it.
      No change to `normalize/run.py` or `export/writer.py`.
- [x] `ProgramExtractionCache._CACHE_SCHEMA_VERSION` is 3; a fixture test
      proves a pre-bump (`schema_version: 2`) cache entry is treated as
      a miss, not a deserialization error.
- [x] A `FixtureProgramLLMClient`-based fixture test proves the
      competition profile correctly separates an event date from a
      distinct registration deadline on one synthetic page (a
      SeaPerch-shaped fixture: one page whose text carries both an event
      date and an earlier "TDR due" deadline) — the resulting `Event`
      has `start` = the event date, `description` carrying the
      registration deadline note, and no wrong-field collision.
- [x] A second fixture test proves the year-inference rule: a synthetic
      page stating a month/day with no adjacent year, extracted with a
      fixed `reference_date`, yields the expected inferred year.
- [x] No change to `Opportunity`'s schema, `normalize/run.py`, or
      `export/writer.py`.
- [x] Full hermetic test suite (`uv run pytest`) stays green — no live
      network, no live Anthropic API call in any test (use
      `FixtureProgramLLMClient` throughout, per this project's testing
      convention).

## Testing

- **Existing tests to run**: `uv run pytest tests/test_adapters_program_llm.py
  tests/test_adapters_program_page.py tests/test_adapters_program_page_multi.py
  tests/test_registry.py` (confirm no regression to sprint 027/028's own
  camp/scholarship/SIO/UCSD fixture coverage — every one of those call
  sites omits the new parameters and must behave identically).
- **New tests to write**: per the Acceptance Criteria above — a
  cache-schema-version-miss test, a competition-profile date-vs-deadline
  separation fixture test, and a year-inference fixture test. All
  `FixtureProgramLLMClient`-based; no live network or live Anthropic API
  call anywhere in this ticket's tests.
- **Verification command**: `uv run pytest`

Do not attempt live re-verification of the five disabled sources in
this ticket — that is ticket 007's job, sequenced after this one so it
runs against the corrected mechanism and a cleared cache.

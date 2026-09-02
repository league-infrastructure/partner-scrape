---
id: '004'
title: Add pd extraction profile for educator-PD pages to program_llm.py and program_page.py
status: done
use-cases:
- SUC-049
depends-on: []
github-issue: ''
issue: 33-educator-programs-layer.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add pd extraction profile for educator-PD pages to program_llm.py and program_page.py

## Description

Mechanism-only ticket, independent of tickets 001-003 (different
subsystem, `adapters/` not `directory/`). Adds a third
`ProgramLLMClient` extraction profile, `profile="pd"`, for educator
professional-development pages (workshops, summits, conference/chapter
meetings) — the genre issue 33 part 1's registrations (ticket 005) will
use.

**Read `adapters/DESIGN.md`'s "Revision (2026-09-02 — sprint 029
competition-genre extraction fix)" section before starting** — that
sprint's premise ("reuse the existing mechanism verbatim, zero new
code") did not survive live verification, because the `"program"`
profile's application-window framing systematically misread genuinely
different genres. This sprint's `design/adapters-DESIGN.md` (its own
"Revision (2026-09-02 — sprint 030 educator-PD extraction profile)"
section) explains why an educator-PD page is its own third genre,
neither `"program"` (no application window — a workshop is signed up
for, not applied to) nor `"competition"` (the vocabulary
`_FIELD_EXTRACTION_RULES_COMPETITION` steers toward — "Competition
Date," "Tournament Date" — actively misleads on a PD page, and labeling
a workshop page "a competition or tournament" in the system prompt
risks the same kind of label-primed misreading sprint 029 diagnosed in
the other direction). Read that section for the full reasoning before
writing the prompt.

## Acceptance Criteria

- [x] `partner_scrape/adapters/program_llm.py` gains
      `_FIELD_EXTRACTION_RULES_PD` and `_SYSTEM_PROMPT_PD`/
      `_SYSTEM_PROMPT_PD_MULTI`, following the exact structural pattern
      `_FIELD_EXTRACTION_RULES_COMPETITION`/`_SYSTEM_PROMPT_COMPETITION`/
      `_SYSTEM_PROMPT_COMPETITION_MULTI` already establish — but with
      PD-appropriate framing and vocabulary: the page's primary date is
      the workshop/summit/session's own date (not an application
      window), field guidance should reference "Workshop Date,"
      "Session Date," "Registration closes," "RSVP by" rather than
      competition-genre phrasing, `registration_deadline` captures a
      stated RSVP/registration cutoff distinct from the event date
      (same field, same semantics as the competition profile's),
      `eligibility` should describe the *educator* audience (grade
      band taught, district, subject) rather than a student-audience
      framing, and `audience_grades` is documented as holding an
      educator-audience descriptor (e.g. "K-5 teachers," "STEM
      coordinators") for this profile. Reuse the same narrow
      year-inference rule the competition profile already has
      (scoped only to a bare month/day with no year).
- [x] **No `ProgramExtractionResult` field is added.** The existing
      `date_start`/`date_end`/`registration_deadline`/`cost`/
      `eligibility`/`is_open`/`opportunity_type`/`audience_grades`
      fields already cover a PD event's shape — confirm this by
      re-reading the dataclass before writing the prompt, don't add a
      field speculatively.
- [x] **No `ProgramExtractionCache._CACHE_SCHEMA_VERSION` bump.** The
      stored-entry shape is unchanged; only which prompt variant
      produced it changes, and no `"pd"`-profile URL has ever been
      cached under a different profile (nothing to invalidate).
- [x] `ProgramLLMClient.extract_program`/`extract_programs`'s `profile`
      parameter accepts `"pd"` as a third value alongside `"program"`/
      `"competition"` — still a plain string, not a typed enum
      (matching this module's existing convention for this kind of
      small hand-curated set).
- [x] `partner_scrape/adapters/program_page.py`'s
      `_resolve_extraction_profile()` extends to a three-way check:
      `"Competitions"` → `"competition"`, `"Professional Development /
      Conferences"` → `"pd"`, else → `"program"` — still driven
      entirely by `source.config.get("opportunity_type")`, still **no
      new registry `config` key**. Every existing `"program"`- and
      `"competition"`-profile source's behavior must be byte-for-byte
      unchanged (write a test proving this, not just eyeballing the
      diff).
- [x] `AnthropicProgramLLMClient`'s real dispatch (whatever internal
      mapping selects a system prompt by `profile` value) is extended
      for `"pd"`, mirroring exactly how `"competition"` was added.
- [x] `FixtureProgramLLMClient` (the test double) is extended so tests
      can register a `profile="pd"` fixture result distinctly from
      `"program"`/`"competition"` fixtures.

## Testing

- **Existing tests to run**: `uv run pytest tests/adapters/` (full
  suite — `program_page`/`program_llm`/`program_cache` tests must stay
  green; the existing `"program"`/`"competition"` profile tests must
  be unaffected by the new branch).
- **New tests to write**:
  - `tests/adapters/test_program_llm.py`: a `profile="pd"` case
    exercising `_SYSTEM_PROMPT_PD` (or its multi-variant) via
    `FixtureProgramLLMClient`, proving the three profiles select
    independently and a PD-profile call never returns a
    competition-framed result.
  - `tests/adapters/test_program_page.py`: extend
    `_resolve_extraction_profile()`'s existing test coverage with the
    `"Professional Development / Conferences"` → `"pd"` case, and a
    regression assertion that pre-existing `"program"`/`"competition"`
    source configs still resolve unchanged.
  - No live network, no live Anthropic API call in any test — fixture
    client only, per this sprint's hard constraint.
- **Verification command**: `uv run pytest`

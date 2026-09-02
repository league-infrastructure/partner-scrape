---
id: '003'
title: Generalize is_open for sold-out sessions and empty-list handling for off-season
  pages
status: open
use-cases:
- SUC-039
- SUC-040
depends-on:
- '001'
github-issue: ''
issue: 29-camp-session-extraction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Generalize is_open for sold-out sessions and empty-list handling for off-season pages

## Description

Prepares `adapters/program_page.py`'s `program_page_multi` mechanism (sprint
027) to serve camp sessions, per issue 29's own question of whether that
mechanism can serve camps directly or needs a camp-specific result shape.
Decision (see `design/adapters-DESIGN.md`'s sprint 028 Design Rationale):
reuse `ProgramExtractionResult` unchanged — its fields already map 1:1 onto
a camp session's needs (`date_start`/`date_end` = the session's own week
dates, `cost` = the session's price, `is_open` = currently available). Two
small, additive changes make that mapping complete:

1. **Generalize `is_open`'s prompt-level definition.** In
   `program_llm.py`'s `_FIELD_EXTRACTION_RULES` (shared by both the
   single- and multi-record system prompts), reword the `is_open` field
   description from "true if the page indicates applications are
   currently open... false if... closed for the current cycle" to "true if
   open for enrollment/application; false if closed, full, or sold out."
   This is a backward-compatible broadening: an internship/program page's
   own truth value is unaffected (a closed application window was already
   "not open"), and a sold-out camp session becomes expressible for the
   first time.
2. **Surface sold-out status via `Event.description`.** In
   `_map_result_to_event` (`program_page.py`), add: when the *resolved*
   `opportunity_type` for this record is `"Camps"` and `result.is_open` is
   `False`, call `event.set("description", "Sold out",
   source=PROGRAM_LLM_SOURCE, confidence=PROGRAM_LLM_CONFIDENCE)`. This
   must be computed *after* `opportunity_type` is resolved (the config
   override or the LLM's own classification — whichever the existing logic
   already picks), so the branch only fires for camp records. No other
   `program_kind`/`opportunity_type` combination's `Event.description`
   changes from its current unset state.
3. **Let a page with nothing on it yield zero records, not an error or a
   guess.** Add one explicit instruction to `_SYSTEM_PROMPT_MULTI`: "If no
   distinct programs are described on the page, return an empty list."
   `_extract_many_programs` already maps a zero-length result list to zero
   `Event`s with no code change needed — this is a prompt-only fix, closing
   the gap that would otherwise let an off-season page (e.g. Fleet's,
   in-season-only, registration opens Feb) either hallucinate a session or
   raise a parse error instead of legitimately returning nothing.

This ticket does no registry work — no camp source is registered here (that
is ticket 004). It only prepares the shared mapping/prompt code the
marketing-page and platform-adapter tickets both depend on.

## Acceptance Criteria

- [ ] `_FIELD_EXTRACTION_RULES`'s `is_open` description is generalized as
      above, applied identically to both `_SYSTEM_PROMPT` and
      `_SYSTEM_PROMPT_MULTI` (they already share this text).
- [ ] `_map_result_to_event` sets `Event.description` to a sold-out note
      when `opportunity_type == "Camps"` and `result.is_open is False`.
- [ ] A fixture record with `is_open=False` and a non-`"Camps"`
      `opportunity_type` (e.g. an internship) leaves `Event.description`
      unset, exactly matching pre-ticket behavior.
- [ ] `_SYSTEM_PROMPT_MULTI` explicitly instructs the model that an empty
      `programs` list is a valid response for a page with no distinct
      programs/sessions.
- [ ] A fixture test proves `_extract_many_programs` maps a
      `FixtureProgramLLMClient` empty-list response to zero `Event`s with
      no exception.
- [ ] Every existing `program_page`/`program_listing`/`program_page_multi`
      fixture test continues to pass unmodified.

## Testing

- **Existing tests to run**: `uv run pytest tests/adapters/test_program_page.py
  tests/adapters/test_program_llm.py` (adjust to this repo's actual test
  layout).
- **New tests to write**:
  - A fixture `ProgramExtractionResult` with `is_open=False`,
    `opportunity_type="Camps"` (via config override), proving the mapped
    `Event.description` carries a sold-out note.
  - A fixture `ProgramExtractionResult` with `is_open=False` and a
    non-Camps `opportunity_type` (e.g. `program_kind="internship"`),
    proving `Event.description` stays unset.
  - A `FixtureProgramLLMClient` configured to return `list_responses={url:
    []}`, proving `ProgramPageMultiAdapter.extract()` returns `[]` with no
    exception.
- **Verification command**: `uv run pytest`

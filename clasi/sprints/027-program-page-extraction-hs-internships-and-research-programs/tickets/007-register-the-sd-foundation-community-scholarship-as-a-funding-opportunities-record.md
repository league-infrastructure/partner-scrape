---
id: '007'
title: Register the SD Foundation Community Scholarship as a Funding Opportunities
  record
status: open
use-cases: [SUC-035]
depends-on: ['001', '003']
github-issue: ''
issue: 28-hs-internship-program-page-extractor.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register the SD Foundation Community Scholarship as a Funding Opportunities record

## Description

Register the San Diego Foundation Community Scholarship (150+
scholarships, one common application, opens winter) as a `program_page`
source with `program_kind = "program"` (not `"internship"` — this is
the sprint's one deliberate non-internship-kind registration,
exercising the mechanism's non-internship path end to end per SUC-035)
and `opportunity_type = "Funding Opportunities"` set as a fixed
per-source config override (an operator-curated, known fact — this
source's type is not left to the LLM extraction's own classification).

Depends on ticket 001 (needs `DEADLINE_FIRST_TYPES` to include
`"Funding Opportunities"` for this record's currency/sort/availability
to behave correctly) and ticket 003 (the `program_page` adapter and its
`opportunity_type`-override handling).

## Fix shape

1. Create `registry/sources/sd-foundation-community-scholarship.toml`:
   `adapter_type = "program_page"`, `config.url` (the Foundation's
   scholarship program page), `config.program_kind = "program"`,
   `config.opportunity_type = "Funding Opportunities"`.
2. Live-verify with `uv run partner-scrape --source
   sd-foundation-community-scholarship --dry-run -v`. Confirm the
   exported record's `opportunity_type` reads `"Funding Opportunities"`
   (the config override, not an LLM guess) and its `availability`/
   currency behave per `DEADLINE_FIRST_TYPES` (e.g. "Opens ~<date>" if
   the application window has not opened at verification time, given
   the source's own "opens winter" cycle).

## Acceptance Criteria

- [ ] The source is registered, live-verified, and `enabled = true`.
- [ ] The exported `Opportunity.opportunity_type ==
      "Funding Opportunities"`.
- [ ] The exported record's `availability`/currency reflects its actual
      application-window state at verification time (open, not-yet-open,
      or — if genuinely closed with no known future cycle — correctly
      excluded from export, matching `is_current_or_upcoming()`'s
      existing `DEADLINE_FIRST_TYPES` rule).
- [ ] A fixture test (not only the live verification) proves a
      `Funding Opportunities`-typed, `kind="program"` record with a
      future `date_end` exports and sorts by `date_end`; the same
      record with a past `date_end` is excluded — this may already be
      satisfied by ticket 001's own fixture tests, in which case this
      criterion is satisfied by cross-reference rather than a new test.
- [ ] Full test suite stays green.

## Testing

- **Existing tests to run**: full suite.
- **New tests to write**: none beyond ticket 001's `Funding
  Opportunities`/`kind="program"` fixture coverage, unless live
  verification surfaces a gap that coverage doesn't already prove.
- **Verification command**: `uv run pytest`, plus live `--dry-run -v`
  verification.

## Implementation Plan

**Approach**: Register and live-verify, same convention as tickets
005/006. This is the smallest data-registration ticket (one source)
and doubles as this sprint's end-to-end proof that the mechanism
correctly handles a non-internship `kind="program"` record.

**Files to create**: 1 new `registry/sources/*.toml` file.

**Testing plan**: see Testing above.

**Documentation updates**: None expected beyond this ticket's own Notes
recording the live-verification outcome.

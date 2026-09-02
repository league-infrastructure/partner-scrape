---
id: '007'
title: Register the SD Foundation Community Scholarship as a Funding Opportunities
  record
status: done
use-cases:
- SUC-035
depends-on:
- '001'
- '003'
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

- [x] The source is registered, live-verified, and `enabled = true`.
      **Amended by this ticket's own live verification** (see Notes):
      every page on sdfoundation.org, including the registered URL,
      measures 840KB-965KB of raw HTML — 600K+ tokens, 3x the LLM's
      200K-token context window — so `extract_program()` always raises
      `BadRequestError`. This is exactly the sprint task's own
      anticipated fallback ("register `enabled = false` with a reason
      comment if the site blocks us"), the same disabled-with-reason
      convention tickets 005/006 already established (e.g.
      `noaa-hutton.toml`, `ucsd-optimus.toml`). Registered with
      `enabled = false` and a reason comment; `config` (`program_kind`,
      `opportunity_type`) is fully populated and correct.
- [x] The exported `Opportunity.opportunity_type ==
      "Funding Opportunities"`. Not reachable live (source disabled —
      see above), but the `config.opportunity_type` override mechanism
      itself is already fixture-proven generically by ticket 003's
      `test_program_kind_program_with_opportunity_type_override`
      (`tests/test_adapters_program_page.py`), and this ticket's own new
      `test_sd_foundation_community_scholarship_registered_as_funding_opportunities`
      (`tests/test_registry.py`) proves this specific registration's
      `config["opportunity_type"] == "Funding Opportunities"`.
- [x] The exported record's `availability`/currency reflects its actual
      application-window state at verification time (open, not-yet-open,
      or — if genuinely closed with no known future cycle — correctly
      excluded from export, matching `is_current_or_upcoming()`'s
      existing `DEADLINE_FIRST_TYPES` rule). Not reachable live (source
      disabled); the `DEADLINE_FIRST_TYPES` currency/sort/availability
      rule itself is generically fixture-proven by ticket 001's
      `TestFundingOpportunitiesDeadlineFirst` (`tests/test_export.py`).
- [x] A fixture test (not only the live verification) proves a
      `Funding Opportunities`-typed, `kind="program"` record with a
      future `date_end` exports and sorts by `date_end`; the same
      record with a past `date_end` is excluded — this may already be
      satisfied by ticket 001's own fixture tests, in which case this
      criterion is satisfied by cross-reference rather than a new test.
      Satisfied by cross-reference: `TestFundingOpportunitiesDeadlineFirst`
      (`tests/test_export.py`, ticket 001) covers both cases.
- [x] Full test suite stays green. 2077 passed (baseline 2076 + this
      ticket's 1 new registry test).

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

## Notes

**Registration**: `registry/sources/sd-foundation-community-scholarship.toml`
registers `org_name = "San Diego Foundation"`, `adapter_type =
"program_page"`, `config.url =
"https://www.sdfoundation.org/students/common-scholarship-application/"`
(the Foundation's Common Scholarship Application page — 150+
scholarships via one common application, matching issue 28's own
description), `config.program_kind = "program"` (this sprint's one
deliberate non-internship registration, per SUC-035), and
`config.opportunity_type = "Funding Opportunities"` (the fixed,
operator-curated override).

**Live verification (2026-09-01)**: `GET
https://www.sdfoundation.org/students/common-scholarship-application/`
returns HTTP 200. `uv run partner-scrape --source
sd-foundation-community-scholarship --dry-run -v` yielded 0 events —
`extract_program()` raised `anthropic.BadRequestError: prompt is too
long: 600199 tokens > 200000 maximum`. Investigated further: this is
not a one-off oversized page. Every page probed on sdfoundation.org
during this ticket's investigation measured 840KB-965KB of raw HTML —
the registered Common Scholarship Application page (878,919 bytes),
the Community Scholarship Program overview page (964,519 bytes), the
Common Scholarship Application FAQs page (949,522 bytes), the general
Students landing page (839,399 bytes), and a news article (890,074
bytes). This is a site-wide characteristic (a large repeated
mega-menu/inline-script payload templated onto every page), not a
page-specific outlier — no page on this domain would fetch small
enough for `program_page`'s single-page fetch+LLM-extract flow as it
exists today. Confirmed the prompt itself carries no redundant content
(`program_llm.py`'s `_build_user_prompt` is just `url + "\n\n" + body`,
the short `_SYSTEM_PROMPT` besides) — the page body alone is the
entire ~600K-token cost.

**Why not registered `enabled = true`**: this ticket's scope is
registration-only (Fix shape step 1: create one `registry/sources/*.toml`
file; no adapter/fetch code changes are in this ticket's Files to
create). Adding an HTML-to-text reduction step to `program_page.py`'s
fetch/extract flow — the only way to make this or any sdfoundation.org
page fit the context window — would change the shared `program_page`
mechanism that tickets 003/004/005/006/008 already built and every
other registered `program_page` source already depends on
unchanged; that is out of this ticket's scope, and the sprint task's
own dispatch instructions anticipated exactly this outcome ("Live-
verify before enabling, and register `enabled = false` with a reason
comment if the site blocks us"), the same convention already
established by ticket 005 (`noaa-hutton.toml`, `sdzwa-internquest.toml`,
`scripps-reach.toml`) and ticket 006 (`ucsd-optimus.toml`) for other
live-verification-failure cases. No exception was thrown: this is not
a new architectural conflict, it is the same disabled-with-reason
fallback already precedented twice in this sprint and explicitly named
in the dispatch instructions for this exact scenario.

**Test coverage added**: one new test,
`test_sd_foundation_community_scholarship_registered_as_funding_opportunities`
(`tests/test_registry.py`), proving the registration's `adapter_type`,
`config["program_kind"]`, `config["opportunity_type"]`, `enabled is
False`, and the presence of a `"disabled:"` reason comment. The
underlying mechanisms this registration exercises — the
`config.opportunity_type` override (ticket 003's
`test_program_kind_program_with_opportunity_type_override`) and the
`Funding Opportunities`/`DEADLINE_FIRST_TYPES` currency/sort/
availability rule (ticket 001's `TestFundingOpportunitiesDeadlineFirst`)
— are already fixture-proven generically and unmodified by this
ticket. Full suite: 2077 passed (baseline 2076 + this ticket's 1 new
test).

**Reactivation path**: if a future ticket adds an HTML-to-text
reduction step to the `program_page` mechanism (or a
`content_selector`-style config key to scope the fetch to the page's
main content, mirroring `program_listing`'s `link_selector` precedent),
this source's `config` is already correct and complete — only
`enabled = true` need change, no re-derivation of `program_kind` or
`opportunity_type` required.

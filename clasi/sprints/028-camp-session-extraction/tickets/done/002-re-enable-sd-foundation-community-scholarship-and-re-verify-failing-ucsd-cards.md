---
id: '002'
title: Re-enable SD Foundation Community Scholarship and re-verify failing UCSD cards
status: done
use-cases:
- SUC-037
depends-on:
- '001'
github-issue: ''
issue: 36-reduce-page-html-before-llm-extraction.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Re-enable SD Foundation Community Scholarship and re-verify failing UCSD cards

## Description

Closes the second half of issue 36, following ticket 001's HTML-reduction
step. `registry/sources/sd-foundation-community-scholarship.toml` is
currently `enabled = false` with a documented reason (page HTML exceeds the
LLM's 200K-token context window). With ticket 001 landed:

1. Live-verify (`uv run partner-scrape --source
   sd-foundation-community-scholarship --dry-run -v`) that the source now
   extracts a program record without raising.
2. Flip `enabled = true` and remove/update the disable-reason comment to
   reflect the fix (mirroring sprint 027 ticket 007's own precedent for how
   a disabled-source TOML documents its history).
3. Re-check the UCSD Summer Program Finder cards recorded as failing during
   sprint 027 (at minimum `www.rmtlacademy.org`) via the same dry-run
   mechanism, and confirm they now yield a record.
4. Any card still failing for a reason unrelated to page size (a genuinely
   different problem) is logged as a new, separate issue — not silently
   dropped or left undocumented.

## Acceptance Criteria

- [x] `sd-foundation-community-scholarship.toml` is `enabled = true`.
- [x] A live dry-run confirms the SD Foundation source extracts a program
      record with `opportunity_type = "Funding Opportunities"` (per its
      existing `config.opportunity_type` override).
- [x] The UCSD cards recorded as failing during sprint 027 are re-verified
      live; each either now yields a record, or has a new issue filed
      documenting why it still doesn't (with the specific reason).

## Notes

Live-verified 2026-09-01 via direct `discover()->fetch()->extract()` calls
against the real network with a real `AnthropicProgramLLMClient` (mirroring
sprint 027 ticket 006's own OPTIMUS live-verification precedent), and
separately via the actual CLI (`uv run partner-scrape --source
sd-foundation-community-scholarship --dry-run -v`).

- **SD Foundation Community Scholarship**: raw body 878910 bytes (~879KB),
  unchanged from sprint 027's measurement. `reduce_html_to_text()` +
  `extract_program()` now succeed with no exception. Yields one `Event`:
  title "Common Scholarship Application", eligibility (graduating HS
  seniors/current college students, min 2.0 GPA, SD County residency,
  FAFSA/CA Dream Act, financial need), cost ("Scholarships ranging from
  $1,000 to more than $5,000"), `opportunity_type = "Funding
  Opportunities"` (confirmed via the `config` override, not the LLM's own
  classification). No `start`/`end` recovered -- the page describes a
  rolling/annual application with no stated deadline, not a
  reduction-step gap. Flipped `enabled = true`; disable-reason comment
  rewritten to record both the original failure and this re-verification
  (`registry/sources/sd-foundation-community-scholarship.toml`).
  `tests/test_registry.py::TestProgramPageSourceConfig::
  test_sd_foundation_community_scholarship_registered_as_funding_opportunities`
  updated to assert `enabled is True` (previously asserted `enabled is
  False`, pre-fix).

- **UCSD Summer Program Finder**: sprint 027 ticket 006 recorded exactly
  one card failing on page size -- `www.rmtlacademy.org` (612KB), which
  raised `anthropic.BadRequestError: prompt is too long: 259984 tokens >
  200000 maximum` (21 of 22 discovered refs succeeded at the time). A full
  live re-run of `ProgramListingAdapter.discover()->fetch()->extract()`
  across all 22 discovered refs now yields 22/22 `Event`s.
  `www.rmtlacademy.org` (still 612547 bytes raw) now extracts cleanly:
  title "Research Methodology Training Laboratory Academy", eligibility
  "Students from economically disadvantaged backgrounds; Title I school
  partnerships". No card in this listing is still failing, so no new
  issue is filed. `registry/sources/ucsd-summer-program-finder.toml`'s
  header comment updated to record this re-verification (the source's
  own `enabled`/config were already correct; no registry flip was
  needed).

- **Sources deliberately left untouched, per this ticket's own scope**:
  `ucsd-optimus.toml` (`enabled = false` for a page-content reason --
  no deadline/eligibility, dead apply link -- unrelated to HTML size;
  not re-verified here) and the sprint-027-ticket-005 WAF/403/TLS-chain
  disabled sources (`noaa-hutton`, `sdzwa-internquest`,
  `scripps-reach`), whose disable reasons were also never about page
  size.

Full suite: `uv run pytest` -- 2088 passed (same as baseline; this
ticket updates one existing assertion rather than adding new tests, per
its own Testing section).

## Testing

- **Existing tests to run**: `uv run pytest` (full suite — this ticket is
  primarily a live-verification/registry-flip ticket, not new adapter code).
- **New tests to write**: none required beyond what ticket 001 already adds;
  if the live re-verification surfaces a page-specific parsing gap, add a
  targeted fixture test for it.
- **Verification command**: `uv run pytest`, plus the live dry-run commands
  described above (not part of the hermetic suite).

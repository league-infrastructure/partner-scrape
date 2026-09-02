---
id: '002'
title: Re-enable SD Foundation Community Scholarship and re-verify failing UCSD cards
status: open
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

- [ ] `sd-foundation-community-scholarship.toml` is `enabled = true`.
- [ ] A live dry-run confirms the SD Foundation source extracts a program
      record with `opportunity_type = "Funding Opportunities"` (per its
      existing `config.opportunity_type` override).
- [ ] The UCSD cards recorded as failing during sprint 027 are re-verified
      live; each either now yields a record, or has a new issue filed
      documenting why it still doesn't (with the specific reason).

## Testing

- **Existing tests to run**: `uv run pytest` (full suite — this ticket is
  primarily a live-verification/registry-flip ticket, not new adapter code).
- **New tests to write**: none required beyond what ticket 001 already adds;
  if the live re-verification surfaces a page-specific parsing gap, add a
  targeted fixture test for it.
- **Verification command**: `uv run pytest`, plus the live dry-run commands
  described above (not part of the hermetic suite).

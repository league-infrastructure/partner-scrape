---
id: '002'
title: Register San Diego Math Circle's public calendar sheet as a program_page_multi
  source
status: open
use-cases: [SUC-045]
depends-on: []
github-issue: ''
issue: 30-competition-sources-without-feeds.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register San Diego Math Circle's public calendar sheet as a program_page_multi source

## Description

sdmathcircle.org's master calendar is a public Google Sheet, not a page
of prose — its several distinct annual dated items (AMC, AIME, ARML,
Math Kangaroo, and its regular Saturday sessions at UCSD) live as rows
in one sheet. Register it as a `program_page_multi` source
(`adapters/program_page.py`'s `ProgramPageMultiAdapter`), pointing
`config.url` at the sheet's export URL, so its N dated items map to N
independent `Event`s via the existing `extract_programs()` call — the
identical mechanism sprint 028 already proved for one-page/N-record
extraction, no new adapter code.

At ticket time, confirm which export form is actually fetchable and
cleanly parseable (a CSV export via the sheet's `/export?format=csv`
endpoint, or the sheet's own published HTML view) — `config.url` must
point at whichever form live-verification confirms works.
`extract.reduce_html_to_text()` is an `lxml.html`-based parser; it
tolerates non-HTML text without raising, but confirm at ticket time that
the fetched export's actual content parses into usable text rather than
assuming it from this ticket's description alone.

## Acceptance Criteria

- [ ] Live-verified: the registered export URL is fetchable and yields
      at least the AMC, AIME, ARML, and Math Kangaroo dated items as
      distinct records.
- [ ] `config.program_kind = "program"` and
      `config.opportunity_type = "Competitions"` are set.
- [ ] If the sheet is not cleanly fetchable/parseable at ticket time,
      the source is registered `enabled = false` with a reason comment
      instead of silently dropped.
- [ ] Full hermetic test suite (`uv run pytest`) stays green.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_adapters_program_page_multi.py
  tests/test_registry.py`.
- **New tests to write**: a fixture test with a saved sheet export
  (CSV or HTML view, matching whichever form is actually registered)
  proving N distinct dated `Event`s via
  `FixtureProgramLLMClient.list_responses`, per SUC-045's acceptance
  criteria.
- **Verification command**: `uv run pytest`

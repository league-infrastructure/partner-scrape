---
id: '002'
title: Register San Diego Math Circle's public calendar sheet as a program_page_multi
  source
status: done
use-cases:
- SUC-045
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
      distinct records. **Not met as literally worded — see Notes.**
      The export URL is fetchable and its text parses cleanly (the
      AMC/AIME dated rows are intact in the exact text forwarded to
      the LLM), but the real `AnthropicProgramLLMClient` extraction
      does not recover AMC/AIME/ARML/Math Kangaroo as distinct dated
      records — it extracts the sheet's 5 recurring class-group
      columns instead, each sharing one non-representative date.
      Math Kangaroo additionally has no dated row anywhere in the live
      sheet at all (see Notes). This is the real-world case AC3 below
      exists to handle; resolved via AC3's path (`enabled = false`
      with a reason comment) rather than this AC's.
- [x] `config.program_kind = "program"` and
      `config.opportunity_type = "Competitions"` are set (in
      `registry/sources/sd-math-circle.toml`'s `[config]`, regardless
      of the `enabled = false` state — the override is present and
      correct for if/when this source is re-enabled).
- [x] If the sheet is not cleanly fetchable/parseable at ticket time,
      the source is registered `enabled = false` with a reason comment
      instead of silently dropped. Invoked: the sheet fetches and its
      text parses cleanly, but real extraction against it is not
      usable (mislabeled and misdated) — registered `enabled = false`
      with a detailed, evidenced reason comment in the TOML file
      header, per the sprint 027/028 disabled-with-reason precedent.
- [x] Full hermetic test suite (`uv run pytest`) stays green — 2152
      passed (baseline 2147 + 5 new: 4 in `test_registry.py`'s new
      `TestMathCircleSourceConfig`, 1 in
      `test_adapters_program_page_multi.py`'s new
      `TestSDMathCircleFixtureExtraction`).

## Testing

- **Existing tests to run**: `uv run pytest tests/test_adapters_program_page_multi.py
  tests/test_registry.py`.
- **New tests to write**: a fixture test with a saved sheet export
  (CSV or HTML view, matching whichever form is actually registered)
  proving N distinct dated `Event`s via
  `FixtureProgramLLMClient.list_responses`, per SUC-045's acceptance
  criteria.
- **Verification command**: `uv run pytest`

## Notes

**Sheet located and CSV export verified fetchable (2026-09-02).**
sdmathcircle.org/sdmc-calendar links one dated Google Sheet per school
year (2018-19 through 2025-26 all present); the anchor text itself
names each one, e.g. "2025-2026 Master Calendar" — sheet id
`18u6y_7MGD3ZQCIBh7fqE5TZTK0qzP0Ns6z1A9_5W0oA`, `gid=28676418`. Real
`curl` against `.../export?format=csv&gid=28676418` returns HTTP 200
with 335 lines of real row data. `.../htmlview` returns only 82 lines
of script scaffolding and no row data (JS-only); `.../edit` is
auth-gated. `config.url` is registered against the CSV export
accordingly.

**Text reaching the LLM verified intact.** Calling
`extract.reduce_html_to_text()` directly on the fetched CSV and
grepping the result confirms the AMC/AIME dated rows (e.g. "AMC 10 A
and AMC 12 A / November 05, 2025") survive the reduction step
unmangled — this is not a `reduce_html_to_text()` bug and not a fetch
failure; the raw material the LLM receives is correct.

**Real extraction failure, live-verified end-to-end.** A real
`uv run partner-scrape --source sd-math-circle --dry-run -v` run (real
network, real `AnthropicProgramLLMClient`, the sprint 027/028/ticket
001b standard) reports `found=6 dated=5`. Inspecting the actual
payload (`partner_scrape.pipeline.run()` called directly) shows the 5
dated records are "San Diego Math Circle - Fermat/Euler/Gauss/Cauchy/AI
Group" — the sheet's 5 recurring grade-level class-group columns, not
competition items — each dated identically to 2025-09-27 (the shared
"Opening Day" row), and none named AMC, AIME, ARML, or Math Kangaroo.
This sheet's shape (a dense ~40-week × 5-column weekly class-schedule
grid, with competition dates as scattered one-off rows *inside* the
grid rather than the page's own top-level "distinct programs") is
outside what the current `program_page_multi` extraction prompt
handles correctly — the same class of one-off-competition-page
weakness ticket 001 identified, compounded here by the grid shape.
Fixing the prompt/mechanism is out of this ticket's and sprint's scope
(sprint.md's Out of Scope: "Building a new extraction mechanism").
Registered `enabled = false` rather than shipped with mislabeled
("Competitions") and misdated (all sharing one meaningless date)
records — see `registry/sources/sd-math-circle.toml`'s header comment
for the full evidence trail.

**Math Kangaroo is not a dated item in this sheet at all**, independent
of the extraction-failure finding above — checked directly (`grep -i
kangaroo` over the full 335-line CSV export): it appears exactly once,
in the sheet's own "External Links" reference table
(`Math Kangaroo,,http://www.mathkangaroo.com/mk/default.html`), with
no date. Unlike AMC/AIME, which SDMC hosts on-site with specific dated
rows, Math Kangaroo runs through independent local registration
centers nationally; SDMC's own sheet only links to it as an external
resource. Issue 30 and SUC-045 named it as an expected item alongside
AMC/AIME/ARML — this is a real, live-verified finding that the
assumption doesn't hold for this data source, reported precisely per
instruction rather than silently worked around.

**No prompt-injection or similar probe found** in the fetched sheet
content (checked, per the standing instruction after ticket 001's
`cipherhacks.tech` finding) — nothing to report on that front.

**Fixture test.** `tests/fixtures/program_pages/sd_math_circle_calendar.csv`
is a trimmed, real excerpt of the live sheet's actual CSV export
(same grid shape: class-group columns interleaved with one-off
competition rows). `TestSDMathCircleFixtureExtraction` in
`tests/test_adapters_program_page_multi.py` proves the
`ProgramPageMultiAdapter` mechanism itself is sound — 5 canned
`ProgramExtractionResult`s (standing in for a *correct* AMC/AIME/ARML
extraction, deliberately not the real LLM's wrong "class group"
output) map to 5 independently-dated `Competitions`-typed `Event`s,
sharing url/source_id, each with its own distinct `start` date. This
satisfies SUC-045's own fixture-test acceptance criterion
independently of the real registration's `enabled = false` state — the
adapter code path is unchanged and already covered by sprint 027/028's
own tests; this test extends that coverage to this source's specific
real-world content shape.

**Test suite**: `uv run pytest tests/test_adapters_program_page_multi.py
tests/test_registry.py` → 84 passed. Full suite `uv run pytest` → 2152
passed (baseline 2147 + 5 new).

**No exception thrown.** This is a live-verification finding of the
same kind ticket 001 already established precedent for (issue/SUC text
assumptions not holding against real data/real LLM behavior), resolved
via the ticket's own designed AC3 fallback — not an architecture
conflict or use-case boundary requiring escalation.

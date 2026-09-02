---
id: '003'
title: Register the SD Festival of Science & Engineering / EXPO Day as a program_listing
  source
status: open
use-cases: [SUC-046]
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

- [ ] Live-verified: discovery yields at least one detail-page
      `EventRef` per festival-week event (using `link_selector` if
      `EVENT_PATH_RE` does not match the listing's card markup).
- [ ] The Mar 7 2026 EXPO Day / Petco Park date specifically surfaces as
      one of the extracted records.
- [ ] `registry/sources/usasciencefestival.toml` is left completely
      unmodified.
- [ ] Full hermetic test suite (`uv run pytest`) stays green.

## Testing

- **Existing tests to run**: `uv run pytest tests/test_adapters_program_listing.py
  tests/test_registry.py`.
- **New tests to write**: a fixture test with a saved listing page plus
  N saved detail pages proving N distinct dated `Event`s, per SUC-046's
  acceptance criteria.
- **Verification command**: `uv run pytest`

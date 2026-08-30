---
id: '003'
title: Deterministic sponsor candidate extraction
status: done
use-cases:
- SUC-003
depends-on:
- '001'
github-issue: ''
issue: 21-scrape-team-sites-for-sponsors.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Deterministic sponsor candidate extraction

## Description

This ticket builds the first half of sponsor extraction — the
deterministic, offline half — and nothing that calls an LLM or the
network. There is no schema.org vocabulary for sponsorship
(`extract/ladder.py`'s confidence-ranked ladder does not apply, per
issue 21's own analysis), so sponsors have to be found heuristically:
sponsors on a robotics team site are typically a footer logo wall,
`<img>` tags whose `alt` text or filename carries the name, sometimes
under a "Sponsors"/"Our Partners"/"Thank you to" heading.

Add `partner_scrape/teams/sponsor_candidates.py`'s
`gather_sponsor_candidates(html: str, page_url: str) -> list[str]`: parse
`html` once with `lxml` (matching `extract/`'s existing dependency),
collect text from headings matching `/sponsor|partner|thank/i` and their
following block, plus every `<img alt>`/`<img title>` and outbound-link
text/hostname inside any `<footer>` element wherever it appears on the
page (not only near a matching heading — many team sites have a footer
logo wall with no heading at all). Deduplicate and cap the result (e.g.
40 candidates) before returning. A page with neither signal returns `[]`
— this is the normal case for most team pages, and it is the cost-control
gate that keeps ticket 004/005's LLM stage from ever being called on a
page with nothing to look at.

This is a pure function: no network, no LLM, no state, fully testable
against static HTML fixtures — including at least one **real,
live-captured** team page, per the sprint's Test Strategy (a
hand-authored HTML fixture would repeat the exact ticket-011-003
mistake this project has twice now documented as a lesson).

See `sprint.md`'s SUC-003 and Architecture Overview for the full
approved design, and `design/teams-DESIGN.diff.md` for the Interfaces
entry describing this function's exact contract.

## Acceptance Criteria

- [x] `partner_scrape/teams/sponsor_candidates.py` exists with
      `gather_sponsor_candidates(html: str, page_url: str) -> list[str]`.
- [x] Recognizes headings matching `/sponsor|partner|thank/i` (covering
      at minimum "Sponsors", "Our Partners", and "Thank You to Our
      Sponsors"-style headings) and collects the following block's
      `alt`/`title`/link text.
- [x] Independently scans any `<footer>` element for `alt`/`title`/link
      text/hostname, whether or not a matching heading exists nearby.
- [x] Deduplicates candidates and caps the returned list at a fixed,
      documented size (e.g. 40).
- [x] A page with no matching heading and no footer signal returns `[]`.
- [x] Unparseable HTML returns `[]` with a logged warning — never raises
      (matching `extract/ladder.py`'s and
      `discovery/hub_scan.py::_extract_candidates()`'s existing
      precedent for malformed-HTML handling).
- [x] Never imports or calls anything from `fetch/`, `enrich/`, or the
      `anthropic` SDK — this module is offline and LLM-free by
      construction.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/` — must stay
  green.
- **New tests to write** (`tests/teams/test_sponsor_candidates.py`):
  - At least one fixture **captured from a real, live FRC team page**
    (fetched during this ticket's own build, saved under
    `tests/fixtures/teams/`, matching `tests/fixtures/teams/tba_teams_page0.json`'s
    precedent of real-captured-not-hand-authored data) containing a
    footer logo wall — assert its known sponsor names appear among the
    returned candidates (not necessarily *only* those; filtering false
    positives is ticket 005's job).
  - A second real captured page with a "Thank You to Our Sponsors"
    heading and a third with a plain "Our Partners" heading — both
    recognized by the same pattern.
  - A real captured page with no sponsor-shaped section at all returns
    `[]`.
  - A hand-authored malformed/unparseable HTML string returns `[]` and
    logs a warning (this one case is fine to hand-author, since it is
    testing a parser-failure path, not approximating real site
    structure).
  - A candidate-count cap test: a synthetic page with more than the cap
    (e.g. 60) distinct `alt` texts in a footer returns at most the
    documented cap.
- **Verification command**: `uv run pytest`.

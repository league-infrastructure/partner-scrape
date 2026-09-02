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

## Note (added post-ticket-001/002, no scope change)

Tickets 001/002's live-verification found `adapters/program_llm.py`'s
pre-existing prompt systematically mis-extracts single-dated-event
pages (an "Event Date:"-style page reads as having no date at all; a
page with both an event date and a separate deadline can collide the
two) — see `adapters/DESIGN.md`'s "Revision (2026-09-02 — sprint 029
competition-genre extraction fix)" and ticket 006. That fix's profile
selection is driven by `source.config.get("opportunity_type") ==
"Competitions"`, which this source deliberately never sets (see this
ticket's own Description — festival-week events span more than one
type). **If live verification here finds the Mar 7 2026 EXPO Day date
(or another festival-week event's date) fails to surface for the same
reason** — a plainly-stated event date the extraction returns empty, or
a deadline swallowing the actual event date — do not invent a new fix:
the documented fallback is `adapters/DESIGN.md`'s own Open Question
("does ticket 003's SD Festival / EXPO Day listing need the competition
profile too?"), which sketches widening profile selection to also
consider the LLM's own self-classified `opportunity_type`. This ticket's
scope is otherwise unchanged — this note exists so a live-verification
failure here isn't mistaken for a new, unrelated bug.

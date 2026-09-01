---
id: '001'
title: Audit sprint 013 website import and verify status wiring
status: in-progress
use-cases:
- SUC-021
depends-on: []
github-issue: ''
issue: 44-team-website-links-and-descriptions.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Audit sprint 013 website import and verify status wiring

## Description

Issue 44 asks us to verify — not assume — whether the 31 team websites
(plus 21 social-only teams) discovered by sprint 013's agent-assisted
web-search research ever actually reached `teams.json`. Planning-time
investigation already found the answer: they did.
`partner_scrape/teams/data/discovered-websites.toml` (sprint 013 ticket
006) contains exactly 52 entries — 31 carrying a `website` key, 21
social-only — an exact match to sprint 013's own
`research/discovered-websites.json` `meta.websites: 31` /
`meta.social_only: 21` counts. `teams/website_overrides.py`'s
`apply_website_overrides()` reads this file and is sequenced
unconditionally in `teams/pipeline.py`'s `run_teams()` immediately
before `teams.scrape.verify_team_websites()` — so every run sets
`Team.website_status` for every team with a website, overlay-sourced or
not, by construction.

A stem-ecosystem peer separately flagged the sharper risk during this
sprint's planning: if `website_status` were ever left unset for an
overlay-sourced site, a site-side detail-page guard keyed on
`website_status == "confirmed"` would silently hide a real, working
link — a data bug on this side, not a rendering bug on theirs. Reading
`teams/pipeline.py`'s stage order confirms this can't happen by
construction (the overlay always runs before verification, every run),
but **no existing test proves it end to end** — every wiring test in
`tests/teams/test_pipeline.py` that exercises `verify_team_websites()`
sets `website=` directly on the stub `Team` it constructs, never routing
through the overlay-population code path at all. That is the one real,
findable gap this ticket closes.

This ticket is therefore **audit-and-verify, not re-import**. Do not add
a second import path, do not touch `teams/data/discovered-websites.toml`
or `teams/website_overrides.py`'s logic, and do not invent work beyond
what the audit actually finds missing. If the required live dry-run
below surfaces a real defect, note it in this ticket's own findings and
fix only that — do not expand scope pre-emptively.

## Acceptance Criteria

- [ ] A new test parses the real, committed
      `teams/data/discovered-websites.toml` (not a fixture copy) and
      asserts exactly 31 entries carry a non-empty `website` and 21
      entries are social-only (`website` absent/empty, `social`
      non-empty) — 52 total, matching sprint 013's
      `research/discovered-websites.json` `meta.websites`/
      `meta.social_only` counts exactly.
- [ ] A new hermetic `run_teams()` test in `tests/teams/test_pipeline.py`
      (alongside the existing `TestSponsorExtractionWiring`-style tests)
      constructs a stub team whose `website` is **empty from its
      source**, backed only by a fixture overlay entry (a small,
      dedicated fixture `discovered-websites.toml`, not the real 52-entry
      file), and drives it through the real `apply_website_overrides()`
      → `verify_team_websites()` chain inside `run_teams()`. Asserts the
      published `website_status` is `"confirmed"` for a 200 fixture
      fetch — proving the overlay-to-verification path works end to end,
      which no existing test currently exercises (every existing wiring
      test sets `website=` directly on the stub `Team`, bypassing the
      overlay entirely).
- [ ] A required pre-close live run: `partner-scrape teams --dry-run -v`
      against the real, live Team Registry, with the actual
      `website_status` distribution (confirmed/unverified/none counts)
      recorded in this ticket's own Notes — closing the audit with real
      numbers, not just code-level reasoning, matching this project's
      established "verify against a live run before close" convention
      (sprint 011/013 precedent, `teams/DESIGN.md`'s Open Questions).
- [ ] If the live run finds any overlay-sourced team with an unset/
      unexpected `website_status`, that finding and its fix (if any) are
      documented in this ticket's Notes. If the live run confirms
      everything is correct (the expected outcome), that is documented
      too — this ticket does not close silently either way.
- [ ] No change to `teams/website_overrides.py`, `teams/scrape.py`, or
      `teams/data/discovered-websites.toml` unless the live run finds an
      actual defect.
- [ ] Full existing test suite stays green.

## Implementation Plan

**Approach**: This is primarily a verification ticket. Read
`teams/website_overrides.py`, `teams/scrape.py`, and `teams/pipeline.py`
to confirm the current stage ordering and behavior (already done at
planning time; re-confirm at implementation time in case anything has
changed on `master` since). Write the two new tests described above.
Run the required live dry-run and record its output. Only touch
production code if the live run surfaces a genuine defect.

**Files to create/modify**:
- `tests/teams/test_website_overrides.py` or a new small test module —
  add the real-data parity test against the actual committed
  `discovered-websites.toml`.
- `tests/teams/test_pipeline.py` — add the overlay-to-verification
  end-to-end wiring test, using a small dedicated fixture overlay file
  (do not reuse the real 52-entry file for this test — mirrors
  `test_website_overrides.py`'s own existing convention of a
  small `overlay_dir` fixture, not the real data file).
- This ticket's own file — record the live dry-run's
  `website_status` distribution and any findings in Notes before
  closing.

**Testing plan**: see Acceptance Criteria above. No test touches live
network for the two new hermetic tests (fixture fetchers only); the
live dry-run is a required manual verification step, not an automated
test, run once during implementation and recorded.

**Documentation updates**: none expected — no behavior changes if the
audit confirms the current code is correct, which is the expected
outcome per this sprint's own planning-time investigation.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/` (full teams
  subsystem suite), `uv run pytest` (full suite) before closing.
- **New tests to write**:
  - Real-data parity test: `teams/data/discovered-websites.toml` has
    exactly 31 website entries + 21 social-only entries.
  - End-to-end `run_teams()` wiring test: an overlay-only-sourced
    website reaches a non-default `website_status`.
- **Verification command**: `uv run pytest`, plus the required
  `partner-scrape teams --dry-run -v` live run (recorded in Notes, not
  an automated test).

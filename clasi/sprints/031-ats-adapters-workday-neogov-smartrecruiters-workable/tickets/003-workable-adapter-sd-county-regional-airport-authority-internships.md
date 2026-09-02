---
id: "003"
title: "Workable adapter — SD County Regional Airport Authority internships"
status: open
use-cases: [SUC-056]
depends-on: []
github-issue: ""
issue: 31-ats-adapters-workday-neogov-smartrecruiters.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Workable adapter — SD County Regional Airport Authority internships

## Description

Build a new `adapters/workable.py` module (`adapter_type =
"workable"`) following the ATS-family pattern (`adapters/greenhouse.py`/
`lever.py`). Register San Diego County Regional Airport Authority
(`apply.workable.com`, public JSON, verified 2026-08-30 per issue 31)
as the first source — confirmed to include paid 9-week summer
internships. See `design/adapters-DESIGN.md`'s sprint 031 section.

Mirror `greenhouse.py`'s "not paginated" precedent — a single
organization's Workable account is expected to return every posting in
one response, like Greenhouse's board API — but confirm this live for
the Authority's own account before assuming it; if it turns out to
paginate, follow SmartRecruiters' (ticket 002) probe-then-paginate
shape instead.

## Acceptance Criteria

- [ ] Live-verify the Authority's public Workable JSON endpoint before
      writing extraction code — confirm the real response shape and
      whether it is genuinely unpaginated, and record any difference
      from this ticket's assumed shape in this ticket's Notes.
- [ ] `adapters/workable.py` implements `discover → fetch → extract`,
      registered in `adapters/__init__.py`'s `ADAPTERS` table as
      `"workable"`.
- [ ] `extract()` runs every posting through
      `ats_filters.classify_posting()` before constructing an `Event`;
      only matches become `Event`s.
- [ ] A fixture mixing internship/full-time, STEM/non-STEM, and
      SD-local/non-local postings proves exactly the matching subset
      survives, including at least one of the confirmed paid
      9-week-summer-internship postings.
- [ ] A malformed record is logged and skipped — never fatal to the
      rest of the response.
- [ ] SD County Regional Airport Authority is registered in
      `registry/sources/`, `enabled = true`, with a header comment
      recording the live-verification date, raw posting count, and
      match count.
- [ ] No live network call in any test.
- [ ] Full test suite (`uv run pytest`) stays green.

## Implementation Plan

**Approach**: Mirror `adapters/greenhouse.py`'s structure closely for
its "no probe-then-paginate" shape, adapted to Workable's own field
names (`title`, `employment_type`, `department`, `location.city`/
`location.region`, `created_at`, `url`/`shortcode`). Do not modify
`ats_filters.py` — pass `employment_type` as the `commitment` argument.

**Files to create/modify**:
- `partner_scrape/adapters/workable.py` (new)
- `partner_scrape/adapters/__init__.py` (register `ADAPTERS["workable"]`)
- `tests/test_adapters_workable.py` (new)
- `tests/fixtures/` — a recorded Authority postings JSON fixture
  (captured during live verification)
- `registry/sources/sd-county-regional-airport-authority.toml` (new)

**Testing plan**:
- **Existing tests to run**: `uv run pytest` (full suite).
- **New tests to write**: fixture-based tests mirroring
  `tests/test_adapters_greenhouse.py`'s pattern — filtering keeps
  exactly the matching subset (including the confirmed paid-internship
  postings); a malformed record is skipped; a non-200/malformed-JSON
  response is handled without raising.
- **Verification command**: `uv run pytest`

**Documentation updates**: None beyond the ticket's own live-
verification Notes.

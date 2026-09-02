---
id: "002"
title: "SmartRecruiters adapter — ServiceNow internships"
status: open
use-cases: [SUC-055]
depends-on: []
github-issue: ""
issue: 31-ats-adapters-workday-neogov-smartrecruiters.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# SmartRecruiters adapter — ServiceNow internships

## Description

Build a new `adapters/smartrecruiters.py` module (`adapter_type =
"smartrecruiters"`) following this codebase's ATS-family pattern
(`adapters/greenhouse.py`/`lever.py`, sprint 006): fetch a public
job-board JSON feed, run every posting through the unchanged
`adapters/ats_filters.classify_posting()`, and emit `kind="internship"`
`Event`s for matches only. Register ServiceNow
(`api.smartrecruiters.com/v1/companies/ServiceNow/postings`, public
GET, verified 2026-08-30 per issue 31) as the first source. See
`design/adapters-DESIGN.md`'s sprint 031 section for the full design.

SmartRecruiters' public API paginates via `offset`/`limit` — unlike
Greenhouse/Lever's single-response shape, `discover()` needs a
probe-then-paginate step, the same pattern `adapters/tec.py`/
`localist.py` already use (cheap probe call, learn total count, return
one `EventRef` per page).

## Acceptance Criteria

- [ ] Live-verify `api.smartrecruiters.com/v1/companies/ServiceNow/postings`
      before writing extraction code — confirm the real response shape
      (`totalFound`, `content[]`, each posting's `name`, `location`,
      `department.label`, `typeOfEmployment.label`, `releasedDate`,
      `postingUrl`/`applyUrl`) matches or differs from this ticket's
      assumed shape, and record any difference in this ticket's Notes.
- [ ] `adapters/smartrecruiters.py` implements `discover → fetch →
      extract`, registered in `adapters/__init__.py`'s `ADAPTERS` table
      as `"smartrecruiters"`.
- [ ] `discover()` probes for total count and returns one `EventRef`
      per page (`context={"offset": N}`); a source with fewer postings
      than one page's `limit` still works (single-page case).
- [ ] `extract()` runs every posting through
      `ats_filters.classify_posting()` before constructing an `Event`;
      only matches become `Event`s.
- [ ] A fixture mixing internship/full-time, STEM/non-STEM, and
      SD-local/non-local postings (recorded from the live-verification
      step above) proves exactly the matching subset survives.
- [ ] A malformed record (missing title, unparseable date) is logged
      and skipped — never fatal to the rest of the page, matching
      `greenhouse.py`'s per-record isolation convention.
- [ ] ServiceNow is registered in `registry/sources/`, `enabled = true`
      regardless of current match count, with a header comment
      recording the live-verification date, raw posting count, and
      whether any posting currently matches.
- [ ] No live network call in any test.
- [ ] Full test suite (`uv run pytest`) stays green.

## Implementation Plan

**Approach**: Mirror `adapters/greenhouse.py`'s structure and
docstring conventions closely, adapted for SmartRecruiters' paginated,
`content[]`-wrapped response shape and its own field names. Reuse
`adapters/base.py`'s `EventRef`/`RawResponse`/`acquisition_kwargs`
exactly as every other structured-API adapter does. Do not modify
`ats_filters.py` — pass `typeOfEmployment.label` as the `commitment`
argument (SmartRecruiters' own internship signal, the same role
Lever's `categories.commitment` plays) and `department.label` as the
`department` argument.

**Files to create/modify**:
- `partner_scrape/adapters/smartrecruiters.py` (new)
- `partner_scrape/adapters/__init__.py` (register `ADAPTERS["smartrecruiters"]`)
- `tests/test_adapters_smartrecruiters.py` (new)
- `tests/fixtures/` — a recorded ServiceNow postings JSON fixture
  (captured during this ticket's required live verification), mixing
  matching and non-matching postings
- `registry/sources/servicenow.toml` (new)

**Testing plan**:
- **Existing tests to run**: `uv run pytest` (full suite; specifically
  confirm `tests/test_adapters_ats_filters.py`,
  `tests/test_adapters_greenhouse.py`, `tests/test_adapters_lever.py`
  are unaffected — this ticket touches no shared code).
- **New tests to write**: fixture-based tests mirroring
  `tests/test_adapters_greenhouse.py`'s pattern — pagination across 2+
  pages; filtering keeps exactly the matching subset; a malformed
  record is skipped, not fatal; a non-200/malformed-JSON page response
  is handled without raising.
- **Verification command**: `uv run pytest`

**Documentation updates**: None beyond the ticket's own live-
verification Notes — the design write-up already lives in this
sprint's `design/adapters-DESIGN.md` and `design/registry-DESIGN.md`
overlay, applied to the canonical docs at sprint close.

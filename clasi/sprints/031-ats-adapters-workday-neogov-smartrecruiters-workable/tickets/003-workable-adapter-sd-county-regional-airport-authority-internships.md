---
id: '003'
title: "Workable adapter \u2014 SD County Regional Airport Authority internships"
status: done
use-cases:
- SUC-056
depends-on: []
github-issue: ''
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

- [x] Live-verify the Authority's public Workable JSON endpoint before
      writing extraction code — confirm the real response shape and
      whether it is genuinely unpaginated, and record any difference
      from this ticket's assumed shape in this ticket's Notes.
- [x] `adapters/workable.py` implements `discover → fetch → extract`,
      registered in `adapters/__init__.py`'s `ADAPTERS` table as
      `"workable"`.
- [x] `extract()` runs every posting through
      `ats_filters.classify_posting()` before constructing an `Event`;
      only matches become `Event`s.
- [x] A fixture mixing internship/full-time, STEM/non-STEM, and
      SD-local/non-local postings proves exactly the matching subset
      survives, including at least one of the confirmed paid
      9-week-summer-internship postings.
- [x] A malformed record is logged and skipped — never fatal to the
      rest of the response.
- [x] SD County Regional Airport Authority is registered in
      `registry/sources/`, `enabled = true`, with a header comment
      recording the live-verification date, raw posting count, and
      match count.
- [x] No live network call in any test.
- [x] Full test suite (`uv run pytest`) stays green.

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

## Notes

**Live verification (2026-09-02).** Found the Authority's Workable
account slug (`san-diego-county-regional-airport-authority`) via web
search, since issue 31's census recorded only "confirmed public JSON"
without the exact account name. `GET
https://apply.workable.com/api/v1/widget/accounts/
san-diego-county-regional-airport-authority?details=true` → HTTP 200,
5 raw postings, one response — confirmed genuinely not paginated for
this account (no `offset`/`limit`/paging metadata in the response at
all). `curl -s https://apply.workable.com/robots.txt` → `Disallow:`
(empty) for `User-agent: *` — no robots block, unlike ticket 002's
SmartRecruiters finding.

**One shape difference from this ticket's assumed response.** The
ticket's Implementation Plan assumed `location.city`/`location.region`
(a nested object). The real response instead carries flat `city`/
`state` keys directly on each job record (a separate, richer
`locations[]` array also exists but isn't needed) — `workable.py`
reads the flat pair, per its own module docstring.

All 5 current postings ("Airport Art Program Manager", "Airport
Traffic Officer", "Manager, Airline Relations", "Procurement
Coordinator", "Senior Network Engineer") are San Diego-located,
full-time, non-internship roles — 0 of 5 match
`ats_filters.classify_posting`. This account has previously posted paid
9-week summer internships (issue 31's own census names "Business
Intelligence - Intern II"; a live web search during this ticket's
verification confirmed the same posting's existence, though it is no
longer open — its direct URL now 302-redirects). Since the ticket's own
acceptance criteria requires the *fixture* to include a confirmed paid
9-week-summer-internship-shaped posting (not that one currently be
live), `tests/fixtures/workable/jobs.json` includes a synthesized
`employment_type: "Internship"` posting reproducing the real account's
confirmed field shape, in San Diego, in a STEM department — proving the
adapter correctly classifies and maps such a posting when one is open.
Registered `sd-county-regional-airport-authority.toml` `enabled = true`
per this sprint's own zero-match-is-a-pass standard (no robots block
here, unlike ServiceNow) — a real dry run
(`uv run partner-scrape --source sd-county-regional-airport-authority
--dry-run -v`) completed with no error, 0 events, matching the live
finding exactly.

Full suite: 2358 passed (2339 baseline + 19 new).

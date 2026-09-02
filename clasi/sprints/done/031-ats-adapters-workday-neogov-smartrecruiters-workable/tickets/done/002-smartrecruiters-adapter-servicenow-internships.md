---
id: '002'
title: "SmartRecruiters adapter \u2014 ServiceNow internships"
status: done
use-cases:
- SUC-055
depends-on: []
github-issue: ''
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

- [x] Live-verify `api.smartrecruiters.com/v1/companies/ServiceNow/postings`
      before writing extraction code — confirm the real response shape
      (`totalFound`, `content[]`, each posting's `name`, `location`,
      `department.label`, `typeOfEmployment.label`, `releasedDate`,
      `postingUrl`/`applyUrl`) matches or differs from this ticket's
      assumed shape, and record any difference in this ticket's Notes.
- [x] `adapters/smartrecruiters.py` implements `discover → fetch →
      extract`, registered in `adapters/__init__.py`'s `ADAPTERS` table
      as `"smartrecruiters"`.
- [x] `discover()` probes for total count and returns one `EventRef`
      per page (`context={"offset": N}`); a source with fewer postings
      than one page's `limit` still works (single-page case).
- [x] `extract()` runs every posting through
      `ats_filters.classify_posting()` before constructing an `Event`;
      only matches become `Event`s.
- [x] A fixture mixing internship/full-time, STEM/non-STEM, and
      SD-local/non-local postings (recorded from the live-verification
      step above) proves exactly the matching subset survives.
- [x] A malformed record (missing title, unparseable date) is logged
      and skipped — never fatal to the rest of the page, matching
      `greenhouse.py`'s per-record isolation convention.
- [x] ServiceNow is registered in `registry/sources/`, with a header
      comment recording the live-verification date, raw posting count,
      and whether any posting currently matches — **deviation from this
      criterion's literal `enabled = true` wording: registered
      `enabled = false`, because live verification found a genuine
      block this ticket did not anticipate** (robots.txt disallows all
      bots except a named `LinkedInBot` exception — see this ticket's
      Notes for the full finding and why `enabled = false` was judged
      the correct call under this sprint's own "enabled=false only for
      a genuine block" standard, not an "empty-but-working" case).
- [x] No live network call in any test.
- [x] Full test suite (`uv run pytest`) stays green.

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

## Notes

**Live verification (2026-09-02), shape differences from this
ticket's assumed response.** `GET
https://api.smartrecruiters.com/v1/companies/ServiceNow/postings?limit=100&offset=0`
→ HTTP 200, `totalFound=577`. Two differences from the assumed shape:

1. `limit` is server-capped at 100 — requesting `limit=200` echoes
   back `limit=100`. `PAGE_SIZE=100` in the adapter, matching this cap
   (probe-at-real-page-size, `tec.py`'s own convention).
2. `content[]` list entries carry **no** `postingUrl`/`applyUrl`
   field — those only exist on the per-posting *detail* endpoint
   (`.../postings/{id}`), which would need one extra fetch per
   posting. Confirmed instead that
   `https://jobs.smartrecruiters.com/{company}/{id}` (the detail
   endpoint's own `postingUrl` value, minus its optional title-slug
   suffix) returns HTTP 200 on its own, so `registration_url` is built
   deterministically from `id` + the source's `company` config, no
   extra network call.

All 577 raw postings were fetched (6 pages) and run through the real
`ats_filters.classify_posting` (via `uv run python3`, direct requests,
not fixture-simulated): 41 located "San Diego" (all Senior/Staff/
Director/Manager-level full-time roles); the one
`typeOfEmployment.label == "Intern"` posting on the whole board
("Intern - Marketing Associate") is in Sydney, Australia, Marketing
department — not STEM. 0 of 577 match. Per this sprint's Success
Criteria, this is itself a working-adapter pass.

**Genuine block found, changing this ticket's registration outcome.**
`curl -s https://api.smartrecruiters.com/robots.txt` →
```
User-agent: LinkedInBot
Allow: /v1/companies/
User-agent: *
Disallow: /
```
This project's `PoliteFetcher` respects robots.txt by default
(`acquisition_policy.respect_robots` defaults to `true`), and a real
dry run (`uv run partner-scrape --source servicenow --dry-run -v`,
with `enabled = true` and no override) raised `RobotsDisallowed`
immediately on the probe call — the source cannot run at all under
this project's default politeness policy, not merely "reachable but
zero matches." This is structurally different from the
`respect_robots = false` precedent for iCal feeds (issue 38): that was
an explicit stakeholder decision that *published calendar subscription
URLs* are feed-client traffic; no equivalent stakeholder decision
exists for a SmartRecruiters-hosted JSON API that deliberately excludes
generic bots while carving out one named partner (LinkedIn). Overriding
`respect_robots` here would be a policy call outside this ticket's
authority, not an implementation one. Registered `servicenow.toml` with
`enabled = false` and a header comment recording the exact finding,
per the sprint's "enabled = false only for a genuine block" standard —
confirmed with a real dry run that the disabled source is skipped
cleanly (no error, `found=0`, not attempted). The adapter itself is
fully built, registered in `ADAPTERS`, and tested against 6 real-
shape-derived fixtures (23 tests, `tests/test_adapters_smartrecruiters.py`)
— flipping `servicenow.toml` to `enabled = true` (with or without a
`respect_robots` override, once a stakeholder decides) needs only a
registry edit, no further adapter code.

Full suite: 2339 passed (2316 baseline + 23 new).

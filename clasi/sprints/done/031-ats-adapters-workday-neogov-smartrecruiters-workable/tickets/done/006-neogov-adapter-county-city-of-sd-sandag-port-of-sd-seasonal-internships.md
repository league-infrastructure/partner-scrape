---
id: '006'
title: "NEOGOV adapter \u2014 County/City of SD, SANDAG, Port of SD seasonal internships"
status: done
use-cases:
- SUC-059
depends-on: []
github-issue: ''
issue: 31-ats-adapters-workday-neogov-smartrecruiters.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# NEOGOV adapter — County/City of SD, SANDAG, Port of SD seasonal internships

## Description

Unlike tickets 002/003/005, issue 31 does not carry a confirmed
endpoint shape for `governmentjobs.com` — only that County of San
Diego, City of San Diego, SANDAG, and Port of San Diego each publish
through it. **Start with live verification, not code.** If a
structured JSON endpoint exists, build `adapters/neogov.py`
(`adapter_type = "neogov"`) following this family's usual shape, with
a per-source `config.agency` key. If postings are reachable only as
rendered HTML, register each agency through the *existing*
`generic_html`/`listing_html` adapter instead — a legitimate, in-scope
pivot, not a new adapter type. See `design/adapters-DESIGN.md`'s
sprint 031 section.

Student/intern classes at these agencies post seasonally — cadence
matters more than parsing precision here. Long stretches of zero
matching postings, punctuated by seasonal bursts, are expected and are
not cause to disable a source.

## Acceptance Criteria

- [x] The real endpoint/markup shape for at least one of the four
      agencies is confirmed live and recorded in this ticket's Notes
      **before** any adapter code is written against an assumed shape.
- [x] Whichever mechanism the live finding supports (bespoke `neogov`
      adapter type, or registration through the existing `generic_html`/
      `listing_html` adapter), all four agencies (County of SD, City of
      SD, SANDAG, Port of SD) are registered.
- [x] If a bespoke `adapters/neogov.py` is built: it implements
      `discover → fetch → extract`, registered in
      `adapters/__init__.py`'s `ADAPTERS` table as `"neogov"`; every
      posting runs through `ats_filters.classify_posting()` before
      becoming a `kind="internship"` `Event`.
- [x] If the HTML-adapter pivot is used instead: each agency's
      registration follows `generic_html`'s/`listing_html`'s existing
      conventions (no bespoke ATS classification needed for those
      adapter types — confirm during implementation whether
      `ats_filters` still applies or whether the existing HTML-adapter
      relevance path is the right one for this content, and record the
      decision in this ticket's Notes). N/A — the bespoke `neogov`
      adapter path was the one the live finding supported (see Notes).
- [x] Fixture-based tests (recorded real response data, whichever
      mechanism applies) prove filtering keeps exactly the matching
      subset.
- [x] Each of the four agencies is registered with a header comment
      recording the live-verification date and finding.
- [x] No live network call in any test.
- [x] Full test suite (`uv run pytest`) stays green.

## Notes

**Live discovery (2026-09-02).** A plain `curl` against each agency's
public careers page (`https://www.governmentjobs.com/careers/{agency}`)
returns HTML whose `<div id="job-list-container">` is empty server-side
("0 jobs found" is a static placeholder) — the real job list is
populated client-side by an AJAX call the page's own JS makes after
load. Tracing that call through the site's own minified
`AgencyPages/search` JS bundle found two candidate AJAX endpoints: the
default HTML-fragment search (`{routePrefix}/home/index`, returns an
HTML partial, not JSON) and the map-view search
(`{routePrefix}/home/loadJobsOnMaps`, returns
`{"success": true, "jobList": [...]}"` — genuine structured JSON). The
second is what this ticket's adapter uses:

    GET https://www.governmentjobs.com/careers/{agency}/home/loadJobsOnMaps

Confirmed live for all four agencies, with **no session/cookie
required** — only three headers the page's own AJAX call sends
(`X-Requested-With: XMLHttpRequest`, `Accept: application/json,
text/javascript, */*; q=0.01`, `Referer:
https://www.governmentjobs.com/careers/{agency}`). Response shape,
field mapping, and the full per-field write-up are in
`adapters/neogov.py`'s own module docstring — not duplicated here.

**Agency slugs confirmed live** (found by probing candidate slugs
against each page's `<title>` tag, then cross-checked against each
agency's own site where ambiguous):
- City of San Diego: `sandiego`
- County of San Diego: `sdcounty`
- SANDAG: `sandag`
- Port of San Diego: `portofsd` (confirmed via a live fetch of
  `https://www.portofsandiego.org/people/careers`, which links directly
  to `governmentjobs.com/careers/portofsd` — not guessed from a slug
  pattern, since generic guesses for the Port all fell through to
  GovernmentJobs' own fallback homepage).

**One adapter, four sources, per the roadmap plan** — the structured
JSON endpoint exists and has an identical shape across all four
agencies, so `adapters/neogov.py` (`adapter_type = "neogov"`) was built
rather than pivoting to `generic_html`/`listing_html`. The HTML-adapter
pivot named in this ticket's Description/Implementation Plan was not
needed; this doc's own AC #4 is marked N/A for that reason, not skipped.

**Live-verification result (2026-09-02, all four agencies).** 110 total
postings fetched (32 City of San Diego, 1 SANDAG, 72 County of San
Diego, 5 Port of San Diego), all in one un-paginated response per
agency. Running the real live response data through
`ats_filters.classify_posting()` directly (title, joined `Categories`
as the commitment signal, `DepartmentName`, `Location`): **0 of 110
match** the internship + STEM + San Diego test. Two County of San Diego
postings carry NEOGOV's own `"Internship"` `Categories` tag ("Student
Worker-25090512-Undergraduate, Graduate/Tech and High School" and
"Student Organizer Internship Program (Student Worker)-26090508U") —
both correctly pass `is_internship_posting` via the commitment signal,
both correctly fail `is_stem_posting` (no STEM-coded title/department:
Human Resources; a multi-department "Administrative Assistant/
Community Services/.../Human Services" list). Two City of San Diego
postings ("Junior Engineer - Civil (Student)", "Student Engineer") are
STEM-coded (`Engineering`) but carry no `"Internship"` category and no
recognized internship-pattern word in the title, so they fail
`is_internship_posting`. A working, zero-match pass, not a failure, per
this sprint's own Success Criteria — and exactly the seasonal case
issue 31 itself names: cadence matters more than any single run's
yield for these four sources.

**GENUINE ROBOTS BLOCK — all four agencies registered `enabled =
false`.** `www.governmentjobs.com/robots.txt` (one shared host, one
shared robots.txt for all four agencies) carries a named-crawler allow
list (Googlebot, bingbot, yahoobot, msnbot, gsa-crawler-www, NHN,
Twitterbot, facebookexternalhit) followed by `User-agent: *` /
`Disallow: /` — the identical shape `servicenow.toml`'s SmartRecruiters
registration (sprint 031 ticket 002) already documents and disables
for. This project's `PoliteFetcher` respects robots.txt by default and
would raise `RobotsDisallowed` for this bot's user agent against any
path under this host, including `/home/loadJobsOnMaps`. No stakeholder
decision exists yet to override `respect_robots` for this vendor (the
same gap ticket 002's own registration names) — registered `enabled =
false` per this sprint's own "`enabled = false` only for a genuine
block" standard, not routed around. The adapter is fully built and
fixture-tested (`tests/test_adapters_neogov.py`, 22 tests, all fixture-
based, no live network); flipping any of the four sources to `enabled =
true` needs no further adapter code, only a registry edit plus a
stakeholder decision to override `respect_robots` for this vendor.

**Files changed:**
- `partner_scrape/adapters/neogov.py` (new)
- `partner_scrape/adapters/__init__.py` (registered `ADAPTERS["neogov"]`)
- `tests/test_adapters_neogov.py` (new, 22 tests)
- `tests/fixtures/neogov/jobs.json`, `jobs_empty.json` (new)
- `registry/sources/city-of-san-diego-careers.toml`,
  `county-of-san-diego-careers.toml`, `sandag-careers.toml`,
  `port-of-san-diego-careers.toml` (new, all `enabled = false`)

**Full test suite**: `uv run pytest` — 2432 passed (baseline 2410 + 22
new).

## Implementation Plan

**Approach**: Spend the first pass of this ticket purely on live
discovery — check whether `governmentjobs.com`/`neogov.com` expose any
public JSON (inspect network requests a real agency careers page makes,
or check for a documented public API) before writing any parsing code.
If found, mirror `adapters/smartrecruiters.py`'s (ticket 002) shape,
adapted to NEOGOV's real field names. If not found, register each
agency via `generic_html`/`listing_html` per `registry/DESIGN.md`'s
existing onboarding convention — no new adapter code in that case.

**Files to create/modify** (bespoke-adapter path):
- `partner_scrape/adapters/neogov.py` (new)
- `partner_scrape/adapters/__init__.py` (register `ADAPTERS["neogov"]`)
- `tests/test_adapters_neogov.py` (new)
- `tests/fixtures/` — recorded response fixtures for at least one
  agency
- `registry/sources/` — one TOML per agency (county-of-san-diego,
  city-of-san-diego, sandag, port-of-san-diego)

**Files to create/modify** (HTML-adapter pivot path):
- `registry/sources/` — one TOML per agency, `adapter_type =
  "generic_html"` or `"listing_html"` per each agency's actual page
  shape
- No new adapter module

**Testing plan**:
- **Existing tests to run**: `uv run pytest` (full suite).
- **New tests to write**: whichever path applies — either
  `adapters/neogov.py`'s own fixture-based filtering tests (mirroring
  ticket 002's pattern), or confirmation that the existing
  `generic_html`/`listing_html` test suite already covers the new
  registrations' shape with no new adapter-level test needed.
- **Verification command**: `uv run pytest`

**Documentation updates**: Record which mechanism was actually used
(bespoke adapter vs. existing HTML adapter) in this ticket's Notes in
enough detail for `design/adapters-DESIGN.md`'s sprint 031 section to
be corrected at sprint close if the live finding differs from its
current "shape pending live verification" framing.

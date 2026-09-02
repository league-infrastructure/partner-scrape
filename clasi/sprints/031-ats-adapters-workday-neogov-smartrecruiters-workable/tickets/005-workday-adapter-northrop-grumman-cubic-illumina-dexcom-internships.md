---
id: "005"
title: "Workday adapter — Northrop Grumman, Cubic, Illumina, Dexcom internships"
status: open
use-cases: [SUC-058]
depends-on: ["004"]
github-issue: ""
issue: 31-ats-adapters-workday-neogov-smartrecruiters.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Workday adapter — Northrop Grumman, Cubic, Illumina, Dexcom internships

## Description

Build a new `adapters/workday.py` module (`adapter_type = "workday"`)
using `Fetcher.post()` (ticket 004) to call
`POST /wday/cxs/{tenant}/{site}/jobs`, following this ATS family's
usual classify-then-emit shape (`ats_filters.classify_posting()`,
`kind="internship"` `Event`s). Register Northrop Grumman (including
its HS Internship Program req), Cubic, Illumina, and Dexcom as
required; register ResMed and Sempra/SDG&E too if this ticket's own
live verification confirms their Workday tenant/site pair
(best-effort). See `design/adapters-DESIGN.md`'s sprint 031 section
for the full design, including why `Event.start` is deliberately left
unset for a posting whose only date signal is a relative string.

**This is the sprint's highest-risk ticket.** Issue 31's own census
found a plain `requests` `GET` gets a 403; whether adding browser-like
headers to a `POST` clears it is unconfirmed. Live-verify early, per
employer, and be prepared for the outcome that some or all employers
stay blocked — that is an acceptable ticket outcome (register
`enabled = false` with a comment naming the finding), not a ticket
failure, per this sprint's Success Criteria.

## Acceptance Criteria

- [ ] For each of Northrop Grumman, Cubic, Illumina, Dexcom: live-
      verify the tenant/site pair and API host shard
      (`{tenant}.wdN.myworkdayjobs.com`), and confirm whether a `POST`
      with browser-like headers (`Accept`, `Content-Type:
      application/json`, a `Referer` set to the employer's own careers
      page, a realistic `User-Agent`) clears the 403 a headerless plain
      request gets. Record the finding per employer in this ticket's
      Notes.
- [ ] `adapters/workday.py` implements `discover → fetch → extract`,
      registered in `adapters/__init__.py`'s `ADAPTERS` table as
      `"workday"`.
- [ ] `discover()` probes `offset=0` to learn `total`, then returns one
      `EventRef` per page (`context={"offset": N}`).
- [ ] `fetch()` calls `Fetcher.post()` with the source's configured
      headers/body.
- [ ] `extract()` runs every `jobPostings[]` entry through
      `ats_filters.classify_posting()`; only matches become
      `kind="internship"` `Event`s.
- [ ] A posting whose only date signal is a relative string (e.g.
      "Posted 30+ Days Ago") gets no fabricated `Event.start` — a unit
      test asserts this explicitly.
- [ ] A fixture including (or modeling) Northrop Grumman's HS
      Internship Program req proves it survives classification.
- [ ] Each of Northrop Grumman, Cubic, Illumina, Dexcom is either
      registered `enabled = true` with a live-verification header
      comment (date, tenant/site, raw count, match count), or
      `enabled = false` with a comment naming the specific blocker
      found (e.g. "403 persists with browser-like headers — likely
      TLS/JA3 fingerprint block, needs headless-browser POST, see
      follow-up").
- [ ] ResMed and Sempra/SDG&E are registered the same way if their
      tenant/site pair is confirmed live; otherwise noted as
      unconfirmed in this ticket's Notes, not registered.
- [ ] No live network call in any test.
- [ ] Full test suite (`uv run pytest`) stays green.

## Implementation Plan

**Approach**: Mirror `adapters/tec.py`'s/`localist.py`'s
probe-then-paginate `discover()` shape, adapted to a POST body's
`offset` field instead of a GET query parameter. Mirror
`greenhouse.py`'s per-record classification/mapping shape for
`extract()`. Build the apply URL by joining `externalPath` onto the
site's own careers base URL (confirm the exact join during live
verification — Workday's `externalPath` is typically relative to
`https://{tenant}.wdN.myworkdayjobs.com/{site}`). Do not modify
`ats_filters.py`.

**Files to create/modify**:
- `partner_scrape/adapters/workday.py` (new)
- `partner_scrape/adapters/__init__.py` (register `ADAPTERS["workday"]`)
- `tests/test_adapters_workday.py` (new)
- `tests/fixtures/` — recorded (or carefully hand-modeled, if a given
  tenant stays blocked even to this ticket's own live verification)
  Workday `jobPostings` response fixtures, including one entry shaped
  like the Northrop Grumman HS Internship Program req and one with
  only a relative-date `postedOn` value
- `registry/sources/` — one TOML per confirmed employer (up to six:
  northrop-grumman, cubic, illumina, dexcom, resmed, sempra-sdge)

**Testing plan**:
- **Existing tests to run**: `uv run pytest` (full suite; specifically
  confirm ticket 004's new `Fetcher.post()` tests still pass — this
  ticket is the first real consumer).
- **New tests to write**: pagination across 2+ pages; filtering keeps
  exactly the matching subset; the HS Internship Program req survives;
  a relative-date-only posting gets no `Event.start`; a malformed
  record is skipped, not fatal; a non-200/malformed-JSON page response
  is handled without raising.
- **Verification command**: `uv run pytest`

**Documentation updates**: None beyond the ticket's own live-
verification Notes — record per-employer findings there in enough
detail that a future sprint revisiting a blocked employer (e.g. for a
headless-POST workaround) doesn't have to re-discover them from
scratch.

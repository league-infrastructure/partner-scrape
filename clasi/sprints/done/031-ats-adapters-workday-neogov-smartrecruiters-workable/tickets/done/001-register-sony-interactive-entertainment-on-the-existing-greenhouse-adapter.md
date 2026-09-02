---
id: '001'
title: Register Sony Interactive Entertainment on the existing Greenhouse adapter
status: done
use-cases:
- SUC-054
depends-on: []
github-issue: ''
issue: 31-ats-adapters-workday-neogov-smartrecruiters.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Register Sony Interactive Entertainment on the existing Greenhouse adapter

## Description

Register Sony Interactive Entertainment as a new source using the
existing `greenhouse` adapter (`partner_scrape/adapters/greenhouse.py`)
— zero adapter code change. Issue 31's census (2026-08-30) confirmed
board token `sonyinteractiveentertainmentglobal` returns HTTP 200 with
valid JSON. This is a registry-only ticket, the cheapest, surest item
in this sprint, and establishes the "live-verify, then register with a
header comment" pattern the rest of the sprint's tickets follow.

## Acceptance Criteria

- [x] `curl -s https://boards-api.greenhouse.io/v1/boards/sonyinteractiveentertainmentglobal/jobs`
      is re-verified live (HTTP 200, valid JSON) before registering —
      do not trust the 2026-08-30 census without a fresh check.
- [x] A new `registry/sources/*.toml` file registers Sony with
      `adapter_type = "greenhouse"`, `config.board_token =
      "sonyinteractiveentertainmentglobal"`, following
      `registry/sources/gossamerbio.toml`'s existing header-comment
      convention (live-verification date, raw posting count, whether
      any posting currently survives `ats_filters.classify_posting`).
  - [x] `enabled = true` regardless of whether any posting currently
        matches — a zero-match result is a pass per this sprint's own
        Success Criteria, not a reason to disable.
- [x] `partner_scrape/adapters/greenhouse.py` has zero diff.
- [x] A dry run (`uv run partner-scrape --source <sony-source-id>
      --dry-run -v`) completes with no error.
- [x] Full test suite (`uv run pytest`) stays green — 2316+ passing,
      no regressions.

## Implementation Plan

**Approach**: This is registry data only. Copy
`registry/sources/gossamerbio.toml`'s shape (org_name, adapter_type,
enabled, `[config]` board_token, `[acquisition_policy]`) and substitute
Sony's own values and live-verification findings.

**Files to create/modify**:
- `registry/sources/sony-interactive-entertainment.toml` (new)

**Testing plan**:
- No new test file is needed — Greenhouse's adapter-level fixture tests
  (`tests/test_adapters_greenhouse.py`) already cover the shape this
  registration exercises; a new registry entry needs no adapter-level
  test of its own, matching every other Greenhouse company source's
  precedent (`gossamerbio.toml` etc. have no per-source test file).
- Run the full suite to confirm the new registry file loads cleanly
  (`registry/loader.py`'s directory scan will pick it up automatically)
  and breaks nothing.
- **Verification command**: `uv run pytest`

**Documentation updates**: None beyond the TOML file's own header
comment — this sprint's `design/` overlay already documents the
mechanism (`adapters-DESIGN.md`, `registry-DESIGN.md`).

## Notes

Live re-verified 2026-09-02: `curl -s -o /dev/null -w '%{http_code}'
https://boards-api.greenhouse.io/v1/boards/
sonyinteractiveentertainmentglobal/jobs` → 200. Fetched the full body
and ran it through the real `ats_filters.classify_posting` (via `uv run
python3`, imported directly, not fixture-simulated): 197 raw postings,
19 located "United States, San Diego, CA", 0 of the 197 match
`classify_posting` (internship + STEM + San Diego). Every San
Diego-located posting is a Senior/Staff/Director/Manager-level
full-time role (e.g. "Senior Software Engineer", "Staff Program
Manager") — none carries an intern/co-op/apprentice/early-career
signal. Registered `enabled = true` per this sprint's explicit
zero-match-is-a-pass standard. `partner_scrape/adapters/greenhouse.py`
was not touched. Dry run (`uv run partner-scrape --source
sony-interactive-entertainment --dry-run -v`) completed with no error,
0 events, matching the live-verification finding exactly. Full suite:
2316 passed.

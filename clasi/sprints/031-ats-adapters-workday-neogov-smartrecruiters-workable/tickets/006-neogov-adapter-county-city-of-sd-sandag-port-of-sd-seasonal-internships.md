---
id: "006"
title: "NEOGOV adapter — County/City of SD, SANDAG, Port of SD seasonal internships"
status: open
use-cases: [SUC-059]
depends-on: []
github-issue: ""
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

- [ ] The real endpoint/markup shape for at least one of the four
      agencies is confirmed live and recorded in this ticket's Notes
      **before** any adapter code is written against an assumed shape.
- [ ] Whichever mechanism the live finding supports (bespoke `neogov`
      adapter type, or registration through the existing `generic_html`/
      `listing_html` adapter), all four agencies (County of SD, City of
      SD, SANDAG, Port of SD) are registered.
- [ ] If a bespoke `adapters/neogov.py` is built: it implements
      `discover → fetch → extract`, registered in
      `adapters/__init__.py`'s `ADAPTERS` table as `"neogov"`; every
      posting runs through `ats_filters.classify_posting()` before
      becoming a `kind="internship"` `Event`.
- [ ] If the HTML-adapter pivot is used instead: each agency's
      registration follows `generic_html`'s/`listing_html`'s existing
      conventions (no bespoke ATS classification needed for those
      adapter types — confirm during implementation whether
      `ats_filters` still applies or whether the existing HTML-adapter
      relevance path is the right one for this content, and record the
      decision in this ticket's Notes).
- [ ] Fixture-based tests (recorded real response data, whichever
      mechanism applies) prove filtering keeps exactly the matching
      subset.
- [ ] Each of the four agencies is registered with a header comment
      recording the live-verification date and finding.
- [ ] No live network call in any test.
- [ ] Full test suite (`uv run pytest`) stays green.

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

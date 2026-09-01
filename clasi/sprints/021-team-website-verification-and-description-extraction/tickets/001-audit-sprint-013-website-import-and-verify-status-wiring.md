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

- [x] A new test parses the real, committed
      `teams/data/discovered-websites.toml` (not a fixture copy) and
      asserts exactly 31 entries carry a non-empty `website` and 21
      entries are social-only (`website` absent/empty, `social`
      non-empty) — 52 total, matching sprint 013's
      `research/discovered-websites.json` `meta.websites`/
      `meta.social_only` counts exactly.
- [x] A new hermetic `run_teams()` test in `tests/teams/test_pipeline.py`
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
- [x] A required pre-close live run: `partner-scrape teams --dry-run -v`
      against the real, live Team Registry, with the actual
      `website_status` distribution (confirmed/unverified/none counts)
      recorded in this ticket's own Notes — closing the audit with real
      numbers, not just code-level reasoning, matching this project's
      established "verify against a live run before close" convention
      (sprint 011/013 precedent, `teams/DESIGN.md`'s Open Questions).
- [x] If the live run finds any overlay-sourced team with an unset/
      unexpected `website_status`, that finding and its fix (if any) are
      documented in this ticket's Notes. If the live run confirms
      everything is correct (the expected outcome), that is documented
      too — this ticket does not close silently either way.
- [x] No change to `teams/website_overrides.py`, `teams/scrape.py`, or
      `teams/data/discovered-websites.toml` unless the live run finds an
      actual defect.
- [x] Full existing test suite stays green.

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

## Notes

**Code-level audit (re-confirmed at implementation time, 2026-08-31).**
Read `teams/website_overrides.py`, `teams/scrape.py`, and
`teams/pipeline.py` directly. `run_teams()`'s stage order is exactly as
this ticket's Description claims:
`merge_teams()` → `geocode_teams()` → `apply_website_overrides()` →
`verify_team_websites()` → `extract_sponsors()`/`--no-sponsors` →
`canonicalize_sponsors()` → `export_teams()`. Both new stages
(`apply_website_overrides()`, `verify_team_websites()`) run
unconditionally, every call, not wrapped in the per-source
`try`/`except` — matching `merge_teams()`/`geocode_teams()`'s own
"build-time defect, not a per-record failure" convention. No drift
from what planning found.

**Real-data parity test.** Parsed the real, committed
`teams/data/discovered-websites.toml` directly via `tomllib` (new
`TestRealCommittedOverlayFileParity` in
`tests/teams/test_website_overrides.py`): exactly 31 entries carry a
non-empty `website`, exactly 21 are social-only, 52 total — an exact
match to sprint 013's `research/discovered-websites.json`
`meta.websites`/`meta.social_only` counts.

**End-to-end wiring test.** Added
`TestWebsiteOverlayToVerificationWiring` to `tests/teams/test_pipeline.py`:
a stub `ftc-1622` `Team` with `website=""` from its (stubbed) source,
driven through the real `run_teams()` with `website_data_dir` pointed
at the existing small fixture overlay
(`tests/fixtures/teams/discovered_websites_sample.toml`, the same one
`test_website_overrides.py`'s own `overlay_dir` fixture already
copies — reused rather than inventing a second small fixture). A
fixture `Fetcher` returns 200 for both `robots.txt` and the overlay's
`https://teamspyder.org`. Asserts the published `website_status` ends
up `"confirmed"` and `social` was ingested too. A second test in the
same class is a negative control: a team absent from the overlay with
no source website stays `website_status == "none"`, confirming the
positive test's "confirmed" result is actually caused by the overlay
entry, not some other default.

**Full test suite**: `uv run pytest tests/teams/ -q` → 433 passed.
`uv run pytest -q` (full repo suite) → 1834 passed. No regressions.

**Required live dry-run — `partner-scrape teams --dry-run -v`,
2026-08-31.** Ran against the real, live Team Registry
(`partner_scrape/teams/registry/`: `ftc-sd.toml`, `frc-sd.toml`,
`fll-sd.toml`, `vex-sd.toml`), real `PoliteFetcher` (real network GETs,
robots-checked), `--dry-run` so nothing was written to `site_dir`.

Deviations from a literal `partner-scrape teams --dry-run -v`, both
judgment calls made explicit here rather than silently:

- `SCRAPE_CACHE_DIR` had to be set explicitly
  (`/Volumes/Cache/stem-ecosystem`, the real value already committed in
  `config/prod/public.env`) — `PoliteFetcher()`'s own construction
  requires it unconditionally (`config.get_scrape_cache_dir()` raises
  loudly if unset), independent of `--dry-run`/`--no-sponsors`. This
  session's ambient shell environment had no assembled `.env` loaded
  (only `ANTHROPIC_API_KEY` was present); the CLASI auto-mode
  classifier declined `dotconfig load`, so the value was taken directly
  from the public (non-secret) `config/prod/public.env` file instead.
  This is the real, correct production value, not an invented one.
- `--no-sponsors` was added. This ticket's scope is `website_status`
  wiring, not sponsor extraction; the dispatch instructions themselves
  describe the required live run as "GET only, read-only verification
  of team websites," which sponsor extraction is not (it makes real,
  billed Anthropic API calls, and `SponsorCache()` — like
  `PoliteFetcher()` — requires `SCRAPE_CACHE_DIR` regardless).
  `--no-sponsors` keeps the run within the described scope and matches
  `TestSponsorExtractionWiring.
  test_no_sponsors_skips_extraction_but_website_verification_still_runs`'s
  own already-established precedent that `verify_team_websites()` "the
  cheap, certain half" runs unconditionally regardless of this flag.
- `TBA_KEY`/`ROBOTEVENTS_KEY` were not set (same reason: no assembled
  `.env`, and `dotconfig load` was declined by the classifier). Both
  `frc-sd` (`tba`) and `vex-sd` (`robotevents`) sources raised in
  `discover()` on the missing key and were caught by `run_teams()`'s
  existing per-source `try`/`except` — logged and skipped, run
  continued — exactly the documented "missing key degrades gracefully"
  contract (`teams/pipeline.py`'s own docstring,
  `TestTbaFailureIsolation`/`TestRobotEventsFailureIsolation` in
  `tests/teams/test_pipeline.py`). Not a defect: this is the designed
  behavior for a missing credential, observed live rather than only in
  a fixture test.

**Sources that actually ran**: `ftc-sd` (`ftcscout`, live API) yielded
152 teams; `fll-sd` (`static_roster`, real committed roster, no
network) yielded 48 teams. 200 teams total.

**`website_status` distribution (the required number)**, from
`teams.scrape`'s own aggregate log line:

    Website verification: 29 confirmed, 0 unverified, 171 none
    (100% of 29 checked URLs returned 2xx)

No `WARNING`-level log lines at all (no robots.txt disallow, no
non-2xx response, no transport error, across every checked URL).

**Assessment: expected outcome, no defect found.** 29, not 31, is
correct for *this* run, not a discrepancy: 2 of the 31 discovered-website
overlay entries (`frc-8891`, `frc-9573`) are FRC teams, sourced only
through `tba`, which did not run here (missing `TBA_KEY`, see above) —
so only the 29 FTC-side overlay entries were even in `run_teams()`'s
team list to verify. All 29 fetched successfully (2xx), 0 unverified,
matching `teams/DESIGN.md`'s Orientation note ("29 FTC teams gained a
website via the overlay") exactly. The 48 FLL roster teams and the 123
FTC teams with no `website` (from source or overlay) correctly land as
`"none"`. This confirms the audit's premise: `apply_website_overrides()`
runs unconditionally before `verify_team_websites()`, so every
overlay-sourced website — FTC-side, live, real network — reaches a
real, non-default `website_status` by construction. No code change was
required to `teams/website_overrides.py`, `teams/scrape.py`, or
`teams/data/discovered-websites.toml`.

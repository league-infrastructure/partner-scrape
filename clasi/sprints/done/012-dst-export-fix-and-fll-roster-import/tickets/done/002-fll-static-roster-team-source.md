---
id: '002'
title: FLL static roster team source
status: done
use-cases:
- SUC-002
depends-on: []
github-issue: ''
issue: 20-fll-static-roster-import.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# FLL static roster team source

## Description

Sprint 011 shipped `/teams` with 230 live, refreshable FTC (FTCScout)
and FRC (The Blue Alliance) teams and deliberately deferred the third
San Diego FIRST league, First LEGO League (48 teams), because there is
no public FLL API or third-party aggregator to pull from (probed and
confirmed). The only source is a hand-maintained, dated export in a
sibling repo
(`../robot-team-analysis/fll/sd-fll-teams-contact-list.md`) that also
carries 40 email addresses this project has an explicit structural
policy against ever publishing — `model.Team` has no `email` field, by
design.

This ticket adds a `static_roster` `TeamSource`
(`partner_scrape/teams/sources/static_roster.py`) that reads a
committed, already-contact-stripped roster file and publishes FLL
alongside the two live sources, reusing every downstream pipeline stage
(`merge_teams()`, `geocode_teams()`, `export_teams()`) unchanged.

See `clasi/issues/20-fll-static-roster-import.md` for the full write-up
and `clasi/sprints/012-dst-export-fix-and-fll-roster-import/design/teams-DESIGN.diff.md`
for the approved design (the "(Sprint 012)" additions throughout
`teams/DESIGN.md`'s Orientation, Constraints, Design, Interfaces, and
Open Questions sections).

## Acceptance Criteria

- [x] A new, committed roster data file exists under
      `partner_scrape/teams/data/` (e.g. `fll-sd-teams.tsv` or `.csv`),
      derived from the upstream
      `../robot-team-analysis/fll/sd-fll-teams-contact-list.md` export,
      with every contact field (email, phone, or any other personal
      contact data) removed **before commit** — the committed file
      itself must never contain a contact field, not merely have one
      filtered out at read time.
- [x] `partner_scrape/teams/sources/static_roster.py` implements
      `TeamSource` (`discover`/`fetch`/`extract`): `discover()` returns
      a single `TeamRef` pointing at the committed roster file (a local
      path, not a URL); `fetch()` reads that file directly off disk and
      never calls the injected `Fetcher`; `extract()` maps each row to a
      `Team` with `league="FLL"`, `sources=["static_roster"]`, and
      `organization=""`/`org_type="family_community"` for any row with
      no sponsoring school (mirroring `sources/ftcscout.py`'s
      `Family/Community` sentinel mapping so `merge_teams()` never
      falsely groups unrelated home teams).
- [x] `partner_scrape/teams/registry/fll-sd.toml` is added:
      `adapter_type = "static_roster"`, `config.roster_path` pointing at
      the committed data file, `config.sunset_season = "2026-27"`.
- [x] `teams.pipeline._TEAM_SOURCES` gains a `"static_roster"` entry
      mapping to `StaticRosterSource()`.
- [x] `teams.pipeline.run_teams()` logs `logging.WARNING` exactly once
      per run when any active source's `config["sunset_season"]` is
      present and `date.today()` is past the parsed season-end date
      (treat `"YYYY-YY"` as ending June 1 of the second year, e.g.
      `"2026-27"` → June 1, 2027) — and logs nothing when `sunset_season`
      is absent or not yet passed.
- [x] No location fields (`latitude`/`longitude`/`location_precision`)
      are set by `static_roster.py` itself — like every other source,
      that remains exclusively `teams.geo.geocode_teams()`'s job, run
      unchanged after this source the same way it runs after
      FTCScout/TBA.
- [x] `merge_teams()`, `geocode_teams()`, and `export_teams()` require
      no code change for this ticket to work end to end.
- [x] No `email` field is added anywhere, and no code path in this
      ticket reads a contact field from any source, upstream or
      committed.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/` — must stay
  green with no modification to any existing test file (per
  `merge.py`'s existing "empty organization never groups" contract,
  confirmed unchanged by this ticket's own design review).
- **New tests to write**:
  - `tests/teams/test_sources_static_roster.py`: extraction against a
    committed fixture derived from real rows of the actual committed
    roster file (not hand-authored from scratch — see the sprint 011
    ticket-011-003 lesson below); a school-affiliated record; a
    family/home record (`organization=""`, confirmed never grouped by
    `merge_teams()` in a combined-fixture test); a test asserting
    `fetch()`/`extract()` never call the injected `Fetcher` using a
    `Fetcher` test double that raises on any call, exercised through the
    full `sources.base.run()` chain; a test asserting no field on any
    extracted `Team` contains an email-address-pattern string even if a
    hypothetical malformed roster row somehow carried one (defense in
    depth on top of the committed-file-has-no-contact-fields guarantee).
  - `tests/teams/test_pipeline.py`: a test simulating `date.today()`
    past `2026-27` produces the sunset `WARNING` log record; a test
    simulating `date.today()` before it produces no such warning.
  - Extend `tests/teams/test_export.py`'s existing no-email-pattern
    regression test's fixture set to include FLL records, confirming the
    structural no-`email`-field guarantee (`model.Team` itself) holds
    with the third source present — this test should need no logic
    change, only a richer fixture.
- **The sprint 011 ticket-011-003 lesson, applied directly**: that
  defect shipped because a hand-authored TBA fixture (`"CA"` on every
  record) didn't match what the real API actually returned
  (`"California"` on the majority), caught only by a live pipeline run
  during sprint validation, not by the fixture-based suite. This is the
  first ticket to ingest the FLL roster; its fixture must be a direct
  excerpt of the real committed roster file's actual rows, not a
  hand-authored approximation of the expected shape. **Before this
  ticket is considered done**, run `partner-scrape teams --dry-run -v`
  against the real (non-fixture) registry and confirm the reported
  totals are 278 teams overall (152 FTC + 78 FRC + 48 FLL) and
  `meta.by_league["FLL"] == 48` — this is a required verification step,
  not optional polish, per `sprint.md`'s Test Strategy and Success
  Criteria.
- **Verification command**: `uv run pytest` (full suite, ~1190 tests,
  must stay green), followed by the real `partner-scrape teams
  --dry-run -v` run described above.

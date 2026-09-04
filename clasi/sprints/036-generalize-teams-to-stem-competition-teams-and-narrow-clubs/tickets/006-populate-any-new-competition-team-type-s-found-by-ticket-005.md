---
id: '006'
title: Populate any new competition-team type(s) found by ticket 005
status: done
use-cases:
- SUC-071
depends-on:
- '005'
github-issue: ''
issue: 47-generalize-teams-and-narrow-clubs.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Populate any new competition-team type(s) found by ticket 005

## Description

Conditional on ticket 005's findings. For up to two competition types
ticket 005 found a real, live-verified, San Diego-specific public
roster for, curate and register a roster the same way ticket 002
populated Science Olympiad/CyberPatriot: a new `teams/data/*.tsv`, a
new `teams/registry/*.toml` (`adapter_type = "team_static_roster"`),
and a `League` widening for the new code(s) (reusing ticket 001's
`VALID_LEAGUES` mechanism — no model change needed beyond adding the
Literal value(s)).

**If ticket 005 found zero populatable types**, this ticket's scope is
to confirm that finding is fully recorded (per ticket 005's own
acceptance criteria) and close with no code change — a legitimate,
expected outcome per sprints 027-032's precedent, not a reason to force
a marginal roster into the pipeline.

**If ticket 005 found more than two**, populate the two most
straightforward finds (a real public roster with minimal fetch/access
friction, per ticket 005's own findings) and record the remainder as a
deferred, findings-backed candidate for a future sprint — do not expand
this ticket's own scope mid-execution to cover all of them; per
sprint.md's Open Questions, stop after two and surface the rest.

## Acceptance Criteria

- [x] For each newly-populated type: a new `teams/data/<type>-sd.tsv`
      following `science-olympiad-sd.tsv`'s column shape exactly
      (`league`, `program`, `number`, `name`, `organization`,
      `org_type`, `city`, `postal_code`, `website`), and a new
      `teams/registry/<type>-sd.toml` (`adapter_type =
      "team_static_roster"`, enabled, header comments citing the exact
      source(s) ticket 005 live-verified).
- [x] `teams/model.py`'s `League` widens to include the new code(s);
      `VALID_LEAGUES` picks up the widening via its existing
      `get_args()` derivation.
- [x] Every new row is geocoded through the normal
      `teams.geo.geocode_teams()` pass (no pre-verified geocoding to
      preserve this time, unlike ticket 002's migration) —
      `location_precision`/`needs_review` reflect whatever the ladder
      actually resolves, honestly, including `"none"` for a school the
      ladder cannot match.
- [x] A real `uv run partner-scrape teams --dry-run -v` run confirms
      the new records appear with the expected count and no regression
      to any existing league's count.
- [x] `data/SCHEMA.md`'s `teams.json` section and `teams/DESIGN.md` are
      updated with the new league code(s), count(s), and source
      citation(s) — this ticket's own documentation update, not
      deferred back to ticket 004 (already closed by this point).
- [x] If zero types were populated: `data/SCHEMA.md`/`teams/DESIGN.md`
      are left unchanged from ticket 004's state, and this ticket's own
      notes confirm ticket 005's "no populatable type found" finding
      was reviewed and accepted, not skipped. **N/A — two types were
      populated (see Notes).**

## Notes — execution (2026-09-03)

Populated both candidates ticket 005 found, per its own "build both"
recommendation (a 1-team TARC league is worth shipping, matching
CyberPatriot's own 3-team precedent, rather than omitting a confirmed
real team). No candidate beyond these two was re-examined — ticket
005's other 15 dispositions stand as recorded.

**Re-verification (this ticket's own execution, real `curl` from an
unsandboxed shell):**
- `https://cspeef.org/competitions/san-diego/` — HTTP 200, 96550 bytes.
- `https://cspeef.org/wp-content/uploads/2026/03/San-Diego-Chapter-2026-Competition-Official-Results.pdf`
  — HTTP 200, 580674 bytes, read in full via `pdftotext`; confirms all
  13 named schools from ticket 005's own reading.
- `https://www.rocketrychallenge.org/result/2026-finalists/` — HTTP
  200, 61804 bytes; confirms Del Norte High School as the sole San
  Diego-area entry.

All three match ticket 005's own findings exactly — no divergence.
Per the ticket's own instruction, `registry/sources/
mathcounts-sd-chapter.toml`'s `enabled = false` flag was **not**
touched (issue 45's scope, not this ticket's).

**Built:**
- `teams/data/mathcounts-sd.tsv` (13 rows) + `teams/registry/
  mathcounts-sd.toml`, `source_id = "mathcounts-sd"`.
- `teams/data/tarc-sd.tsv` (1 row) + `teams/registry/tarc-sd.toml`,
  `source_id = "tarc-sd"` — TOML header states the "national-finalist
  subset, not a census" caveat explicitly.
- `teams/model.py`: `League` widened to add `"MATHCOUNTS"`, `"TARC"`.

**Geocoding (real `teams.geo.geocode_teams()` pass, no pre-verified
data carried over):** all 14 new rows resolve at `location_precision
== "school"`. 13 are exact normalized-name matches against the real
committed CDE/NCES school directories (`needs_review == False`); one
(MATHCOUNTS' Thurgood Marshall Middle School, matched against CDE's
"Marshall Middle") is a genuine sub-0.85-Jaccard fuzzy match, honestly
flagged `needs_review == True` — not overridden or hand-tuned to force
an exact match.

**Live verification:**
- `uv run partner-scrape teams --source team_static_roster --dry-run -v`
  → `wrote 41 teams` (24 SCIOLY + 3 CYBERPATRIOT + 13 MATHCOUNTS + 1
  TARC — the full offline static-roster set).
- A real, full, unfiltered `uv run partner-scrape teams --dry-run -v`
  run (live FTCScout/TBA network, `--no-sponsors --no-descriptions` to
  avoid unnecessary LLM cost) → `wrote 319 teams`, `by_league`: FTC 152,
  FRC 78, FLL 48, SCIOLY 24, CYBERPATRIOT 3, MATHCOUNTS 13, TARC 1
  (VEX absent — `ROBOTEVENTS_KEY` unprovisioned in this environment,
  pre-existing and unrelated to this ticket — `credential_failures ==
  ["VEX"]`). No existing league's count regressed.

**Tests:** extended `tests/teams/test_model.py` (`VALID_LEAGUES`
widened set) and `tests/teams/test_sources_team_static_roster.py`
(fixed `test_unrecognized_league_raises_value_error`, which had used
the now-valid `"MATHCOUNTS"` string as its unrecognized-league example
— replaced with `"NOTALEAGUE"`). Added a new `tests/teams/
test_dataset_validity.py` (11 tests) covering `team_id`
uniqueness/non-blank across every real offline (static-roster) source,
`League` recognition, the two new rosters' exact content, and their
real, live geocoding outcome. Updated every real-registry-driven
`tests/teams/test_pipeline.py` total/`by_league` assertion (14 more
teams than before this ticket, always-on) — full diff is in this
ticket's commit.

## Testing

- **Existing tests to run**: `uv run pytest tests/teams/` in full — no
  regression to any existing league's fixture-driven test.
- **New tests to write** (only if at least one type is populated):
  - A `tests/teams/test_sources_team_static_roster.py` case (or a
    sibling fixture file) covering the new roster's specific shape,
    mirroring ticket 001's test suite for the mechanism.
  - `tests/teams/test_model.py`: `VALID_LEAGUES` includes the new
    code(s).
- **Verification command**: `uv run pytest`, plus a real
  `uv run partner-scrape teams --dry-run -v` run to confirm the
  populated payload. Any live-network check of a candidate source
  during this ticket's own execution (re-confirming ticket 005's
  finding still holds) requires `dangerouslyDisableSandbox: true` on
  Bash — the hermetic test suite itself never touches the network.

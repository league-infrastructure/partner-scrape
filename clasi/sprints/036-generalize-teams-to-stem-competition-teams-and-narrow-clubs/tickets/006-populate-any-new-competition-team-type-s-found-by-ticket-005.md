---
id: '006'
title: Populate any new competition-team type(s) found by ticket 005
status: open
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

- [ ] For each newly-populated type: a new `teams/data/<type>-sd.tsv`
      following `science-olympiad-sd.tsv`'s column shape exactly
      (`league`, `program`, `number`, `name`, `organization`,
      `org_type`, `city`, `postal_code`, `website`), and a new
      `teams/registry/<type>-sd.toml` (`adapter_type =
      "team_static_roster"`, enabled, header comments citing the exact
      source(s) ticket 005 live-verified).
- [ ] `teams/model.py`'s `League` widens to include the new code(s);
      `VALID_LEAGUES` picks up the widening via its existing
      `get_args()` derivation.
- [ ] Every new row is geocoded through the normal
      `teams.geo.geocode_teams()` pass (no pre-verified geocoding to
      preserve this time, unlike ticket 002's migration) —
      `location_precision`/`needs_review` reflect whatever the ladder
      actually resolves, honestly, including `"none"` for a school the
      ladder cannot match.
- [ ] A real `uv run partner-scrape teams --dry-run -v` run confirms
      the new records appear with the expected count and no regression
      to any existing league's count.
- [ ] `data/SCHEMA.md`'s `teams.json` section and `teams/DESIGN.md` are
      updated with the new league code(s), count(s), and source
      citation(s) — this ticket's own documentation update, not
      deferred back to ticket 004 (already closed by this point).
- [ ] If zero types were populated: `data/SCHEMA.md`/`teams/DESIGN.md`
      are left unchanged from ticket 004's state, and this ticket's own
      notes confirm ticket 005's "no populatable type found" finding
      was reviewed and accepted, not skipped.

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

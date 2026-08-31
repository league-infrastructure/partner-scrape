---
id: '002'
title: 'Establish data/ as the pipeline''s own publish target: config accessor and
  legacy file removal'
status: in-progress
use-cases:
- SUC-019
depends-on: []
github-issue: ''
issue: 60-publish-pipeline-output-in-well-known-data-directory.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Establish data/ as the pipeline's own publish target: config accessor and legacy file removal

## Description

Foundation ticket for issue 60 — every other data/-publish ticket in
this sprint (003-007) depends on this one. Two independent pieces of
prerequisite work:

1. **New config accessor.** `partner_scrape/config.py` currently has
   `get_site_dir()`/`DEFAULT_SITE_DIR` for the sibling `stem-ecosystem`
   checkout. Add the equivalent for partner-scrape's own repo:
   `DEFAULT_OWN_DATA_DIR = _REPO_ROOT / "data"` and
   `get_own_data_dir() -> Path`, matching `get_site_dir()`'s exact shape
   (same docstring convention, same "reads env if set, else default"
   pattern shape) EXCEPT this one takes no environment variable at all
   — the location is fixed by design (see sprint.md Design Rationale
   and Open Questions: deliberately not env-overridable this sprint).
   `get_own_data_dir()` simply returns `DEFAULT_OWN_DATA_DIR`
   unconditionally.

2. **Remove confirmed-dead legacy files.** Delete
   `data/partners_viable.csv` and `data/robot-teams.json` — both
   confirmed dead (zero production readers; issue 60's own research).
   `data/robot-teams.json` has no test reference to update (its only
   mentions are historical docstring comments in `teams/geo.py`,
   `teams/model.py`, `teams/sources/tba.py`, and
   `tests/teams/test_sources_tba.py`, all describing how a hand-written
   city/roster list was *originally derived* — none of them read the
   file at runtime or in a test; leave those comments as accurate
   historical narrative, no code change needed there).
   `data/partners_viable.csv` DOES have one test reader:
   `tests/test_roster_housekeeping.py`. Remove
   `TestNoBareCaliforniaCentroid`, `TestNoOutOfBoundsCoordinates`,
   `TestNoHijackedDomain`, and the `_load_partners_csv()`
   helper/`PARTNERS_CSV` constant they share (their JSON-side
   counterparts were already retired to issue 48 by sprint 019 ticket
   002's own docstring note — these three classes are the CSV-side half
   of that same retirement, now that the CSV itself is gone too).
   `TestRegistrySourceNameStability`, `TestBatchARegistrySourceNames`,
   and `TestBatchBRegistrySourceNames` read the registry TOML directly,
   never the CSV — leave them untouched. Update the test file's module
   docstring, which currently describes `data/partners_viable.csv` as
   "remain[ing] tracked, local files" — that sentence becomes stale
   after this ticket.

## Acceptance Criteria

- [ ] `config.py` exposes `DEFAULT_OWN_DATA_DIR` (`<repo_root>/data`)
      and `get_own_data_dir()`, matching `DEFAULT_SITE_DIR`/`get_site_dir()`'s
      docstring convention.
- [ ] `data/partners_viable.csv` and `data/robot-teams.json` no longer
      exist in the repo.
- [ ] `tests/test_roster_housekeeping.py` no longer references
      `data/partners_viable.csv`; `TestNoBareCaliforniaCentroid`,
      `TestNoOutOfBoundsCoordinates`, `TestNoHijackedDomain`, and
      `_load_partners_csv()`/`PARTNERS_CSV` are removed.
      `TestRegistrySourceNameStability`, `TestBatchARegistrySourceNames`,
      `TestBatchBRegistrySourceNames` still pass, unmodified.
- [ ] `grep -rn "partners_viable\|robot-teams"` across `partner_scrape/`
      and `tests/` (excluding historical docstring mentions in
      `teams/geo.py`, `teams/model.py`, `teams/sources/tba.py`,
      `tests/teams/test_sources_tba.py`) returns nothing.
- [ ] `uv run pytest tests/test_roster_housekeeping.py -q` passes.

## Implementation Plan

**Approach**: additive config change plus a deletion+test-trim, no
interaction between the two halves.

**Files to modify**:
- `partner_scrape/config.py` — add `DEFAULT_OWN_DATA_DIR`,
  `get_own_data_dir()` near `DEFAULT_SITE_DIR`/`get_site_dir()`.
- `tests/test_roster_housekeeping.py` — remove the three CSV-dependent
  test classes and their shared helper/constant; update the module
  docstring's now-stale sentence about the CSV remaining tracked.

**Files to delete**:
- `data/partners_viable.csv`
- `data/robot-teams.json`

**Files to create**: none. (No test file is needed for
`get_own_data_dir()` alone — it has no branching logic; tickets 003-007
exercise it indirectly through each export function's own new tests.)

## Testing

- **Existing tests to run**: `uv run pytest tests/test_roster_housekeeping.py -q`,
  then the full suite (`uv run pytest -q`) to confirm the deletions
  introduce no other failures.
- **New tests to write**: none required for `get_own_data_dir()` itself
  (trivial accessor, no branch); covered indirectly by tickets 003-007.
- **Verification command**: `uv run pytest -q`

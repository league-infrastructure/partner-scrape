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

- [x] `config.py` exposes `DEFAULT_OWN_DATA_DIR` (`<repo_root>/data`)
      and `get_own_data_dir()`, matching `DEFAULT_SITE_DIR`/`get_site_dir()`'s
      docstring convention.
- [x] `data/partners_viable.csv` and `data/robot-teams.json` no longer
      exist in the repo.
- [x] `tests/test_roster_housekeeping.py` no longer references
      `data/partners_viable.csv`; `TestNoBareCaliforniaCentroid`,
      `TestNoOutOfBoundsCoordinates`, `TestNoHijackedDomain`, and
      `_load_partners_csv()`/`PARTNERS_CSV` are removed.
      `TestRegistrySourceNameStability`, `TestBatchARegistrySourceNames`,
      `TestBatchBRegistrySourceNames` still pass, unmodified.
- [x] `grep -rn "partners_viable\|robot-teams"` across `partner_scrape/`
      and `tests/` (excluding historical docstring mentions in
      `teams/geo.py`, `teams/model.py`, `teams/sources/tba.py`,
      `tests/teams/test_sources_tba.py`) returns nothing. **See
      Implementation Notes below** — the literal grep also matches a
      large number of `discovered_via` provenance strings in
      `partner_scrape/registry/sources/*.toml` and
      `partner_scrape/teams/registry/*.toml`, plus doc/docstring hits in
      `partner_scrape/teams/DESIGN.md` and
      `partner_scrape/teams/sources/ftcscout.py`, none of which the
      ticket's exclusion list names. Verified none of these are
      functional file reads (confirmed via `registry/candidates.py` and
      `registry/schema.py` — `discovered_via` is a free-text metadata
      field, never a path used for I/O) and left untouched as historical
      narrative, consistent with the ticket's own rationale for the 4
      named exclusions. Flagging per the process instruction to report
      findings beyond what was already known rather than silently
      broadening the exclusion list myself.
- [x] `uv run pytest tests/test_roster_housekeeping.py -q` passes.

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

## Implementation Notes

**Config accessor**: added `DEFAULT_OWN_DATA_DIR = _REPO_ROOT / "data"`
and `get_own_data_dir() -> Path` in `partner_scrape/config.py`, right
after `get_site_dir()`, matching its docstring convention exactly except
noting the no-env-override difference. `get_own_data_dir()` returns
`DEFAULT_OWN_DATA_DIR` unconditionally, no branching.

**Legacy files**: `data/partners_viable.csv` was still tracked; removed
via `git rm`. `data/robot-teams.json` turned out to already be tracked
in the index (an untracked `??` file at session start per the harness's
git-status snapshot had since been staged/committed outside this
ticket's own history — `git log --oneline -- data/robot-teams.json`
showed one prior commit); removed via `rm` + `git add` of the deletion.
Both are now staged as deletions.

**Coverage disposition (`tests/test_roster_housekeeping.py`)**: removed
`TestNoBareCaliforniaCentroid`, `TestNoOutOfBoundsCoordinates`,
`TestNoHijackedDomain`, `_load_partners_csv()`, and the `PARTNERS_CSV`
constant, per the ticket's Description. Checked issue 48
(`clasi/issues/48-pipeline-level-roster-data-quality-validation.md`,
status: `pending`) before deleting — it explicitly proposes recovering
this exact CSV-side guard set (bare-California centroid,
out-of-bounds coordinates, hijacked domain) as pipeline-level
validation, and is the tracked home for it, but is **not yet
implemented**. This ticket's deletion therefore does leave those three
guards genuinely uncovered until issue 48 lands — not a silent drop,
but a real, currently-open coverage gap tracked at the issue level per
the ticket's own instruction ("their JSON-side counterparts were
already retired to issue 48... these three classes are the CSV-side
half of that same retirement"). The three registry-TOML classes
(`TestRegistrySourceNameStability`, `TestBatchARegistrySourceNames`,
`TestBatchBRegistrySourceNames`) are untouched and still pass. Also
removed the now-orphaned `SD_BOUNDS` module-level constant (was used
only by the deleted `TestNoOutOfBoundsCoordinates`) rather than leaving
dead code; its historical purpose is preserved in the updated module
docstring instead. Updated the module docstring's now-stale "remain
tracked, local files" sentence to describe the ticket 002 deletion and
point at issue 48.

**Additional grep findings beyond the ticket's known exclusion list**:
`grep -rn "partners_viable\|robot-teams" partner_scrape/ tests/` also
matches (a) `discovered_via = "partners_viable.csv ..."` provenance
strings across ~80 files in `partner_scrape/registry/sources/*.toml`
(documenting the July 2026 bulk-registration batch each source came
from) and two in `partner_scrape/teams/registry/*.toml` (referencing
sprint-011/issue filenames that happen to contain the substring
"robot-teams"); (b) three mentions in `partner_scrape/teams/DESIGN.md`
(architecture doc prose, including one forward-looking "sprint may
eventually ingest `data/robot-teams.json`" note that is now stale given
the deletion); (c) a docstring in
`partner_scrape/teams/sources/ftcscout.py` referencing an issue
filename containing "robot-teams". None of these are functional file
reads — confirmed `discovered_via` is a free-text metadata field in
`registry/schema.py`/`registry/candidates.py`, never used to open a
file. Left all of these untouched as historical/provenance narrative,
same treatment as the ticket's own 4 named exclusions, rather than
unilaterally editing ~80 TOML files or an architecture doc outside this
ticket's stated file list. Flagging here rather than silently expanding
scope or silently marking the literal grep AC as clean.

---
id: '003'
title: Drop 4-H, Civil Air Patrol, and Sea Cadets; narrow ClubType to genuine clubs
status: open
use-cases:
- SUC-070
depends-on:
- '002'
github-issue: ''
issue: 47-generalize-teams-and-narrow-clubs.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Drop 4-H, Civil Air Patrol, and Sea Cadets; narrow ClubType to genuine clubs

## Description

Issue 47 calls for dropping 4-H (14), Civil Air Patrol (7), and Sea
Cadets (4) entirely — 25 entries, stakeholder call ("the military
stuff you can drop"), not migrated anywhere. After ticket 002 has
already moved Science Olympiad/CyberPatriot out, this ticket removes
the remaining three non-club types, leaving `Club` with exactly the
two genuine clubs issue 47 confirms: Hack Club (4) and Girls Who Code
(1). This is also where `directory/DESIGN.md` gets the explicit
meets-vs-competes rule so a future sprint populating a new club type
checks it before mis-filing another competition team the way sprint
032 did.

## Acceptance Criteria

- [ ] `directory/registry/4-h-sd.toml`, `civil-air-patrol-sd.toml`,
      `sea-cadets-sd.toml` deleted.
- [ ] `directory/data/4-h-sd.tsv`, `civil-air-patrol-sd.tsv`,
      `sea-cadets-sd.tsv` deleted.
- [ ] `directory/model.py`'s `ClubType` narrows from
      `Literal["hack-club", "girls-who-code", "4-h",
      "civil-air-patrol", "sea-cadets"]` (ticket 002's post-migration
      state) to `Literal["hack-club", "girls-who-code"]`;
      `VALID_CLUB_TYPES` picks up the narrowing via its existing
      `get_args()` derivation, no further change needed.
- [ ] A real `uv run partner-scrape directory` run shows `clubs.json`'s
      `total` drop from 30 (ticket 002's post-migration state) to 5,
      `by_club_type` reading exactly `{"hack-club": 4,
      "girls-who-code": 1}`.
- [ ] `directory/DESIGN.md` gains an explicit, standalone
      meets-vs-competes statement (a new, quotable section — not
      folded into a Revision note where a future reader could miss
      it): a `Club` is a standing entity that *meets* with no
      competition circuit attached; a standing entity that *competes*
      in a named STEM competition belongs in `Team`
      (`partner_scrape/teams/`), regardless of whether that
      competition is robotics. Cite this sprint's own history (sprint
      032 mis-populated `Club` with four competition-team types; this
      sprint corrected it) as the concrete cautionary example.
- [ ] No dangling reference to a dropped `ClubType` value anywhere in
      `directory/registry/*.toml`, `directory/data/*`, or any test
      fixture.

## Testing

- **Existing tests to run**: `uv run pytest tests/directory/` in full.
- **New tests to write**:
  - `tests/directory/test_model.py` (or equivalent): `VALID_CLUB_TYPES
    == frozenset({"hack-club", "girls-who-code"})`.
  - Update any test hard-coding the old 30- or 57-club total, or
    referencing a `4-h-sd`/`civil-air-patrol-sd`/`sea-cadets-sd`
    registry entry or data file.
  - `tests/directory/test_dataset_validity.py`'s `Club`-side `club_id`
    uniqueness/non-blank check continues to pass against the final
    5-row dataset.
- **Verification command**: `uv run pytest`, plus a real
  `uv run partner-scrape directory --dry-run -v` (network-free — every
  active `directory/` source is a local-file static roster) to confirm
  the final `clubs.json` shape.

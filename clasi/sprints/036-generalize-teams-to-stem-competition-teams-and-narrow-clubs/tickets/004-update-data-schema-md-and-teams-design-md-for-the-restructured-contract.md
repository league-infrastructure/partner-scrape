---
id: '004'
title: Update data/SCHEMA.md and teams/DESIGN.md for the restructured contract
status: open
use-cases:
- SUC-068
- SUC-069
- SUC-070
depends-on:
- '003'
github-issue: ''
issue: 47-generalize-teams-and-narrow-clubs.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update data/SCHEMA.md and teams/DESIGN.md for the restructured contract

## Description

`data/SCHEMA.md` is the published contract description for `data/` —
"If you are an agent reading this to use the data: everything you need
is in this directory." It currently describes `teams.json` as
"FIRST robotics teams (FRC/FTC/FLL, and VEX when credentialed)" and
`clubs.json`'s `club_type` vocabulary as the old seven-value set. Both
are now wrong after tickets 001-003. This ticket brings the document
back in sync with the code, per CLAUDE.md's standing instruction that
"any sprint that changes one of those [schema] constants... must
update this document in the same ticket" — done here as one dedicated
ticket, after the restructuring settles, rather than spread thin across
001-003's own smaller doc touches.

## Acceptance Criteria

- [ ] `data/SCHEMA.md`'s `teams.json` section: description updated from
      "FIRST robotics teams (FRC/FTC/FLL, and VEX when credentialed)"
      to something accurate to the generalized model (e.g. "STEM
      competition teams — FIRST/VEX robotics (FRC/FTC/FLL/VEX) plus any
      other curated competition type this pipeline tracks"). The
      `league`/`by_league` prose notes that `by_league`'s key set is no
      longer closed to the four robotics codes.
  - [ ] The `meta.credential_failures` explanation is re-verified
        against the actual widened `League` set: still correct that
        only credentialed sources (`FRC` via TBA, `VEX` via
        RobotEvents) can ever appear there, and that a static-roster
        league code (`FLL`, `SCIOLY`, `CYBERPATRIOT`, and whatever
        ticket 006 adds) never can.
- [ ] `data/SCHEMA.md`'s `clubs.json` section: `club_type` vocabulary
      updated to `hack-club`, `girls-who-code` only; the "VEX teams are
      not here" callout is joined by an equivalent "Science Olympiad
      and CyberPatriot teams are not here either — they moved to
      `teams.json` in sprint 036" note, so a reader who remembers the
      old shape isn't left guessing where they went.
- [ ] `data/SCHEMA.md`'s closing "Last verified against a real pipeline
      run" line is updated with the actual post-migration counts from a
      real run (opportunities/teams/places/clubs/offerings/partners),
      not copied from the pre-sprint line.
- [ ] `teams/DESIGN.md` gets a full sprint-036 section (not just ticket
      002's short note): the widened `League` vocabulary, the new
      `team_static_roster.py` module's place among `teams/sources/`,
      and a cross-reference to `directory/DESIGN.md`'s
      meets-vs-competes rule (ticket 003) so a reader of either
      document can find the other half of the story.
- [ ] Every field-list/count claim in both updated documents is checked
      against a real pipeline run's actual output, not against this
      sprint's plan-time estimates (28-team-total etc.) — the estimates
      are directional, the shipped documentation must match reality.

## Testing

- **Existing tests to run**: none code-level — this is a documentation
  ticket. Run the full suite once (`uv run pytest`) to confirm tickets
  001-003 left it green before writing final counts into the docs.
- **New tests to write**: none — `data/SCHEMA.md` has no automated
  drift guard yet (issue 46's proposed successor work, explicitly out
  of this sprint's scope).
- **Verification command**: `uv run pytest`, plus real
  `uv run partner-scrape teams --dry-run -v` and
  `uv run partner-scrape directory --dry-run -v` runs to source the
  exact counts/vocabularies written into the docs.

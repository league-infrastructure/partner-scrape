---
status: done
sprint: '036'
tickets:
- 036-001
- 036-002
- 036-003
- 036-004
- 036-005
- 036-006
---

# Generalize teams to all STEM competition teams; narrow clubs to real clubs

## The problem

Sprint 032 populated the `Club` standing-entity model with six club
types. Most of them are not clubs — they are **competition teams**, and
they were only in `Club` because `Team` was built as a robotics-only
model (FRC/FTC/FLL/VEX) with no home for a non-robotics team.

Stakeholder's framing (2026-09-03): "Most of the clubs you've got
aren't actually clubs... The science olympiad teams: go move them over
to teams. That makes the team category not just teams. It makes it
robotic teams, then not just robotics team. That makes a general team."

## The distinction to encode

- **Team = competes.** A standing group that enters a named STEM
  competition. Robotics is one instance, not the definition.
- **Club = meets.** A school-based STEM club with no competition
  circuit attached.

## Changes

Current 57 clubs: 4-H 14, Science Olympiad 24, Civil Air Patrol 7,
Hack Club 4, Sea Cadets 4, CyberPatriot 3, Girls Who Code 1.

**Drop entirely (25):**
- 4-H (14) — stakeholder call.
- Civil Air Patrol (7) and Sea Cadets (4) — "the military stuff you can
  drop."

**Move to teams (27):**
- Science Olympiad school teams (24) — explicitly directed.
- CyberPatriot (3) — a cybersecurity competition team, and the exact
  case the stakeholder then asked us to go find more of. It was already
  in the wrong bucket.

**Keep as clubs (5):**
- Hack Club (4) and Girls Who Code (1). Both are school-based coding
  clubs, not competition teams. Hack Club was initially dropped ("too
  hard to figure out what they actually are") and then reinstated on
  the club-vs-team criterion: "if you got Girls Who Code, then you got
  Hack Club in there. Hack Club's a club, so put Hack Club back."

Result: clubs 57 → 5, teams 278 → ~305.

## Model work

`Team` (`partner_scrape/teams/`) assumes robotics throughout — `league`
and `program` are FIRST/VEX-shaped, and `teams.json`'s `meta.by_league`
and `credential_failures` follow. Generalize it to carry a
competition-team type without breaking the existing FRC/FTC/FLL/VEX
records or `TEAMS_SCHEMA_FIELDS` consumers. Science Olympiad and
CyberPatriot arrive as static curated rosters, not API sources, so the
static-roster source pattern moves across from `directory/` too.

Check what `clubs.json`'s remaining 5 entries mean for the
`directory/` module — the `Club` model stays, but its docs should state
the meets-vs-competes rule so this does not drift back.

## Then: find more teams

The stakeholder asked for a brainstorm and a hunt: "go look for other
teams, like cybersecurity teams, and do some brainstorming on what
other kinds of youth STEM teams there are in STEM competitions."

Starting list to research for San Diego rosters (not exhaustive, and
not all will have public rosters):
DOE Science Bowl, National/Garibaldi Ocean Sciences Bowl, MATHCOUNTS,
American Rocketry Challenge (TARC), SeaPerch, Botball, Envirothon,
Future City, TSA chapters, SkillsUSA chapters, eCyberMission, Zero
Robotics, Junior Solar Sprint, Solar Cup, Math Circle / AMC-AIME school
teams, picoCTF and Mayor's Cyber Cup teams.

Sprint 029 already registered several of these as *events* in
`registry/sources/` — those pages are the natural first place to look
for participating-team rosters.

Apply the standard held since sprint 027: live-verify every roster, and
record "no public roster exists" as a finding rather than padding.

## Reference

Sprint 032 built the club rosters being undone here; sprint 018 built
`directory/` and the `Club` model; sprints 011/016 built `teams/`.
See also `data/SCHEMA.md`, which documents both files and will need
updating.

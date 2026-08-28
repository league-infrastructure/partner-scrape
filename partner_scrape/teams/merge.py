"""Cross-league organizational identity (``teams.merge``).

Links `Team` records that belong to the same real-world organization
across leagues/sources -- e.g. Canyon Crest Academy's FTC and FRC
teams -- **without** ever fusing them into a single record. Each
league's team is its own standing entity (different students,
different robot, different season, in FTC-vs-FRC's case even a
different competition program), so what "linking" means here is
setting `Team.org_key` (the shared identity) and
`Team.sibling_team_ids` (the other `team_id`s at that org) on every
member of the group -- the records themselves stay separate.

**Why organization name, not team number.** `Team.team_id` already
guarantees uniqueness by construction (`f"{league.lower()}-{number}"`
-- see `teams/model.py`), so team numbers never collide *as IDs*. But
raw team *numbers* do occasionally repeat across leagues -- FTC 1622
and FRC 1622 are both real, both at Poway High School, entirely
different teams that happen to share a number because Poway registered
both. If `merge.py` keyed on number, a program with the same number at
an *unrelated* school (measured: FTC 812 and FRC 812 are at different
schools) would incorrectly link two strangers, and Poway's genuine
1622-to-1622 link would work for the wrong reason (number match, not
organizational fact) and silently break the moment either team
renumbers. Keying on `normalize.partners.normalize_org_name`-normalized
`Team.organization` instead links on the fact that is actually true
here -- the *organization*, not the number, is what running in FTC and
FRC simultaneously is a fact about. Reused directly (not reimplemented)
per sprint.md's Design Rationale ("avoids a second, independently-
drifting normalizer").

**Why `Family/Community` and empty organizations never group.**
`sources/ftcscout.py` maps its `Family/Community` sentinel (and any
team with no reported organization) to `Team.organization == ""` --
deliberately, so this module can treat "no organization" as
structurally ungroupable rather than as one giant matching bucket.
Measured: 58 of 152 San Diego FTC teams are `Family/Community`. Without
this guard, `normalize_org_name("")` would return `""` for every one
of them, and a naive group-by-normalized-name would fuse all 58 (plus
any other empty-organization team, FRC included) into one bogus
~60-team "organization" -- exactly the failure mode this module exists
to avoid. Every `Team` with an empty `organization` gets
`org_key = ""` and is excluded from grouping entirely, regardless of
how many other teams also have an empty `organization`.
"""

from __future__ import annotations

from partner_scrape.normalize.partners import normalize_org_name
from partner_scrape.teams.model import Team


def _org_key(team: Team) -> str:
    """The grouping key for `team`, or `""` if it must never group.

    `""` covers both `Family/Community`/home teams (`Team.organization
    == ""`, set by `sources/ftcscout.py`) and any team whose
    organization name normalizes to nothing (e.g. punctuation-only) --
    both cases mean "no real organization identity to link on."
    """
    if not team.organization:
        return ""
    return normalize_org_name(team.organization)


def merge_teams(teams: list[Team]) -> list[Team]:
    """Set `org_key`/`sibling_team_ids` on `teams` in place; return `teams`.

    Groups `teams` by :func:`_org_key`, skipping the empty-key group
    entirely (never grouped -- see module docstring). Every team in a
    group of 2+ gets `org_key` set to the shared key and
    `sibling_team_ids` set to the other members' `team_id`s (sorted,
    for deterministic output) -- a group of exactly 1 (an organization
    with only one team, in only one league) gets its `org_key` set but
    an empty `sibling_team_ids`, since there is no sibling yet.

    Does not deduplicate, drop, or otherwise change how many `Team`
    objects come out versus went in -- every input team is returned,
    including ones with an empty `org_key`. Idempotent: calling this
    twice on the same list is a no-op the second time.
    """
    by_org_key: dict[str, list[Team]] = {}
    for team in teams:
        org_key = _org_key(team)
        team.org_key = org_key
        if org_key:
            by_org_key.setdefault(org_key, []).append(team)

    for group in by_org_key.values():
        ids = sorted(t.team_id for t in group)
        for team in group:
            team.sibling_team_ids = [tid for tid in ids if tid != team.team_id]

    return teams

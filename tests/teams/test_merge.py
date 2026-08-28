"""Tests for partner_scrape.teams.merge: cross-league organizational identity.

Every test here builds `Team` objects directly rather than going
through a source's `extract()` -- `merge.py` operates on already-
acquired `Team[]` regardless of which source(s) produced them, so its
tests exercise the merge *logic* in isolation, matching this module's
own "operates after both sources have run" contract. The two live
sources' end-to-end contribution to merging is covered separately in
`tests/teams/test_pipeline.py`.
"""

from __future__ import annotations

from partner_scrape.teams.merge import merge_teams
from partner_scrape.teams.model import Team


def _team(team_id: str, league: str, number: int, organization: str) -> Team:
    return Team(
        team_id=team_id,
        league=league,
        number=number,
        name=f"Team {number}",
        organization=organization,
        org_type="school" if organization else "unknown",
        sources=[league.lower()],
    )


class TestDualProgramOrganization:
    """Canyon Crest Academy fields FTC teams 7159/9837/14425 (real,
    live-captured fixture data) and FRC team 3128 (real historical
    data) -- one of the seven organizations sprint.md's Design
    Rationale names as running teams in both programs.
    """

    def _canyon_crest_teams(self) -> list[Team]:
        return [
            _team("ftc-7159", "FTC", 7159, "Canyon Crest Academy"),
            _team("ftc-9837", "FTC", 9837, "Canyon Crest Academy"),
            _team("ftc-14425", "FTC", 14425, "Canyon Crest Academy"),
            _team("frc-3128", "FRC", 3128, "Canyon Crest Academy"),
        ]

    def test_all_four_teams_share_one_org_key(self):
        teams = merge_teams(self._canyon_crest_teams())

        org_keys = {t.org_key for t in teams}
        assert len(org_keys) == 1
        assert org_keys != {""}

    def test_each_team_lists_the_other_three_as_siblings(self):
        teams = merge_teams(self._canyon_crest_teams())
        by_id = {t.team_id: t for t in teams}

        assert set(by_id["frc-3128"].sibling_team_ids) == {"ftc-7159", "ftc-9837", "ftc-14425"}
        assert set(by_id["ftc-7159"].sibling_team_ids) == {"frc-3128", "ftc-9837", "ftc-14425"}

    def test_records_stay_separate_not_fused_into_one(self):
        # The whole point: merging links, it never collapses records.
        teams = merge_teams(self._canyon_crest_teams())

        assert len(teams) == 4
        assert {t.team_id for t in teams} == {
            "ftc-7159", "ftc-9837", "ftc-14425", "frc-3128",
        }

    def test_org_key_is_case_and_punctuation_insensitive(self):
        # normalize_org_name is reused, not reimplemented -- confirm
        # its normalization actually takes effect here (e.g. a
        # trailing "The " or differing case still links).
        teams = [
            _team("ftc-1", "FTC", 1, "Canyon Crest Academy"),
            _team("frc-2", "FRC", 2, "  canyon crest academy  "),
        ]

        merged = merge_teams(teams)

        assert merged[0].org_key == merged[1].org_key
        assert merged[1].sibling_team_ids == ["ftc-1"]


class TestFamilyCommunityAndEmptyOrgNeverGroup:
    """FTCScout maps its `Family/Community` sentinel to
    `Team.organization == ""`; TBA has no such sentinel but an
    unaffiliated FRC team also reports no `school_name`, mapping the
    same way. Neither case may ever group -- 58 unrelated home teams
    fusing into one bogus 100-team "organization" is exactly the
    failure this module exists to prevent (sprint.md's Design
    Rationale).
    """

    def test_multiple_empty_organization_teams_never_share_an_org_key_group(self):
        teams = [
            _team("ftc-1", "FTC", 1, ""),
            _team("ftc-2", "FTC", 2, ""),
            _team("ftc-3", "FTC", 3, ""),
            _team("frc-4", "FRC", 4, ""),
        ]

        merged = merge_teams(teams)

        assert all(t.org_key == "" for t in merged)
        assert all(t.sibling_team_ids == [] for t in merged)

    def test_empty_organization_team_does_not_link_to_a_real_org_by_accident(self):
        teams = [
            _team("ftc-1", "FTC", 1, ""),
            _team("frc-2", "FRC", 2, "Poway High School"),
        ]

        merged = merge_teams(teams)
        by_id = {t.team_id: t for t in merged}

        assert by_id["ftc-1"].org_key == ""
        assert by_id["ftc-1"].sibling_team_ids == []
        assert by_id["frc-2"].sibling_team_ids == []  # only 1 real team at this org


class TestTeamNumberCollisionNeverCausesAFalseMerge:
    """team_id already guarantees uniqueness (league-prefixed), but
    merge.py must key strictly on organization, never on the bare
    number -- otherwise a coincidental number match across leagues at
    *unrelated* schools would wrongly link two strangers.
    """

    def test_same_number_same_org_links_but_stays_two_records(self):
        # FTC 1622 and FRC 1622 -- both real Poway High School teams,
        # different students/robot/season. Must link via org (correct)
        # but never fuse into one record.
        teams = [
            _team("ftc-1622", "FTC", 1622, "Poway High School"),
            _team("frc-1622", "FRC", 1622, "Poway High School"),
        ]

        merged = merge_teams(teams)

        assert len(merged) == 2
        by_id = {t.team_id: t for t in merged}
        assert by_id["ftc-1622"].sibling_team_ids == ["frc-1622"]
        assert by_id["frc-1622"].sibling_team_ids == ["ftc-1622"]
        assert by_id["ftc-1622"].org_key == by_id["frc-1622"].org_key

    def test_same_number_different_org_never_links(self):
        # FTC 812 and FRC 812 are at different schools (measured) --
        # number-based linking would be actively wrong here.
        teams = [
            _team("ftc-812", "FTC", 812, "Some FTC-Only School"),
            _team("frc-812", "FRC", 812, "The Preuss School UCSD"),
        ]

        merged = merge_teams(teams)
        by_id = {t.team_id: t for t in merged}

        assert by_id["ftc-812"].org_key != by_id["frc-812"].org_key
        assert by_id["ftc-812"].sibling_team_ids == []
        assert by_id["frc-812"].sibling_team_ids == []


class TestSingleTeamOrganization:
    def test_an_organization_with_only_one_team_gets_an_org_key_but_no_siblings(self):
        teams = [_team("ftc-1", "FTC", 1, "Only One Team High School")]

        merged = merge_teams(teams)

        assert merged[0].org_key != ""
        assert merged[0].sibling_team_ids == []


class TestIdempotency:
    def test_calling_merge_teams_twice_is_a_no_op_the_second_time(self):
        teams = [
            _team("ftc-7159", "FTC", 7159, "Canyon Crest Academy"),
            _team("frc-3128", "FRC", 3128, "Canyon Crest Academy"),
        ]

        once = merge_teams(teams)
        snapshot = [(t.team_id, t.org_key, tuple(t.sibling_team_ids)) for t in once]
        twice = merge_teams(once)
        after = [(t.team_id, t.org_key, tuple(t.sibling_team_ids)) for t in twice]

        assert snapshot == after


class TestReturnValue:
    def test_returns_the_same_list_object_mutated_in_place(self):
        teams = [_team("ftc-1", "FTC", 1, "Some School")]

        result = merge_teams(teams)

        assert result is teams

    def test_every_input_team_is_present_in_the_output_including_empty_org(self):
        teams = [
            _team("ftc-1", "FTC", 1, "Some School"),
            _team("ftc-2", "FTC", 2, ""),
        ]

        result = merge_teams(teams)

        assert {t.team_id for t in result} == {"ftc-1", "ftc-2"}

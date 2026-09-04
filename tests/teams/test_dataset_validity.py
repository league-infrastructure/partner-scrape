"""Dataset-validity regression tests for the whole real, committed Team
Registry's *offline* (static-roster) sources -- FLL's bespoke
``static_roster`` module plus every ``team_static_roster`` entry
(Science Olympiad, CyberPatriot, and, as of sprint 036 ticket 006,
MATHCOUNTS and TARC).

Sprint 036 ticket 006's own Test Strategy: "tests/teams/
test_dataset_validity.py (or equivalent) gains the same uniqueness/
non-blank check for the new team_static_roster rows if no equivalent
guard already covers team_id uniqueness across all sources." No such
guard existed before this ticket -- this module is that guard,
mirroring tests/directory/test_club_dataset_validity.py's own
real-data-not-a-fixture precedent. Scoped to this subsystem's offline
sources specifically (never FTCScout/TBA/RobotEvents, which need live
network/credentials): every team_id these hermetic sources produce is
still combined into the same `teams.json` a live-network run publishes,
so a collision here is a real collision there too.
"""

from __future__ import annotations

from pathlib import Path

from partner_scrape.registry.loader import load_active_sources
from partner_scrape.teams.model import VALID_LEAGUES
from partner_scrape.teams.pipeline import DEFAULT_TEAMS_REGISTRY_DIR
from partner_scrape.teams.sources.base import run
from partner_scrape.teams.sources.static_roster import StaticRosterSource
from partner_scrape.teams.sources.team_static_roster import TeamStaticRosterSource

_TEAM_SOURCES_BY_ADAPTER = {
    "static_roster": StaticRosterSource(),
    "team_static_roster": TeamStaticRosterSource(),
}


class _NeverCalledFetcher:
    def get(self, url, headers=None):
        raise AssertionError("must never call the injected Fetcher")


def _real_offline_teams():
    """Every `Team` produced by the real, committed Team Registry's
    offline (non-network) sources -- FLL's `static_roster` plus every
    `team_static_roster` entry, in registry-file order."""
    teams = []
    for source in load_active_sources(DEFAULT_TEAMS_REGISTRY_DIR):
        team_source = _TEAM_SOURCES_BY_ADAPTER.get(source.adapter_type)
        if team_source is None:
            continue
        teams.extend(run(source, team_source, _NeverCalledFetcher()))
    return teams


def _real_team_static_roster_teams():
    """Just the `team_static_roster`-sourced teams (excludes FLL's
    bespoke `static_roster`) -- the subset this ticket's new rosters
    (MATHCOUNTS, TARC) belong to."""
    teams = []
    for source in load_active_sources(DEFAULT_TEAMS_REGISTRY_DIR):
        if source.adapter_type != "team_static_roster":
            continue
        teams.extend(run(source, TeamStaticRosterSource(), _NeverCalledFetcher()))
    return teams


class TestUniqueTeamIds:
    def test_every_offline_sourced_team_id_is_unique(self):
        ids = [t.team_id for t in _real_offline_teams()]
        assert len(ids) == len(set(ids))

    def test_no_offline_sourced_team_id_is_blank(self):
        assert all(t.team_id for t in _real_offline_teams())


class TestEveryLeagueIsRecognized:
    def test_every_offline_sourced_team_has_a_valid_league(self):
        for team in _real_offline_teams():
            assert team.league in VALID_LEAGUES, team.team_id


class TestMathcountsRosterContent:
    """AC: the committed `mathcounts-sd.tsv` roster names exactly the
    13 schools ticket 005's research verified against the official 2026
    San Diego Chapter MATHCOUNTS results PDF."""

    def _mathcounts_teams(self):
        return [t for t in _real_team_static_roster_teams() if t.league == "MATHCOUNTS"]

    def test_exactly_13_mathcounts_teams(self):
        assert len(self._mathcounts_teams()) == 13

    def test_every_verified_school_is_present(self):
        organizations = {t.organization for t in self._mathcounts_teams()}
        assert organizations == {
            "Black Mountain Middle School",
            "Carmel Valley Middle School",
            "Design 39 Campus",
            "Francis Parker School",
            "Meadowbrook Middle School",
            "Mesa Verde Middle School",
            "Muirlands Middle School",
            "Oak Valley Middle School",
            "Pacific Trails Middle School",
            "San Diego French American School",
            "Sycamore Ridge School",
            "The Bishop's School",
            "Thurgood Marshall Middle School",
        }

    def test_this_source_never_sets_a_coordinate(self):
        # geocode_teams() is the only stage that ever does (see
        # sources/team_static_roster.py's own docstring) -- this class
        # asserts the source-level half of that guarantee.
        for team in self._mathcounts_teams():
            assert team.latitude is None
            assert team.longitude is None
            assert team.location_precision == "none"


class TestTarcRosterContent:
    """AC: the committed `tarc-sd.tsv` roster is exactly the one
    live-verified San Diego-area National Finalist ticket 005 found --
    deliberately thin, not a census (see tarc-sd.toml's own header)."""

    def _tarc_teams(self):
        return [t for t in _real_team_static_roster_teams() if t.league == "TARC"]

    def test_exactly_1_tarc_team(self):
        assert len(self._tarc_teams()) == 1

    def test_the_one_team_is_del_norte_high_school(self):
        assert self._tarc_teams()[0].organization == "Del Norte High School"


class TestRealPipelineGeocodingResolvesTicket006RostersHonestly:
    """End-to-end: every real curated MATHCOUNTS/TARC row, run through
    the real committed `teams/data/` school directories, resolves via
    the shared ladder's actual school-matching rungs -- not a guess, not
    a fixture stand-in. Mirrors tests/directory/
    test_club_dataset_validity.py's TestRealPipelineGeocodingResolves...
    class one subsystem over."""

    def _geocoded(self, tmp_path):
        from partner_scrape.teams.pipeline import run_teams

        payload = run_teams(
            source="team_static_roster",
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            no_sponsors=True,
            no_descriptions=True,
        )
        return [t for t in payload["teams"] if t["league"] in ("MATHCOUNTS", "TARC")]

    def test_every_new_roster_team_resolves_at_school_precision(self, tmp_path):
        for team in self._geocoded(tmp_path):
            assert team["location_precision"] == "school", team["team_id"]

    def test_matched_name_is_never_blank(self, tmp_path):
        for team in self._geocoded(tmp_path):
            assert team["matched_name"], team["team_id"]

    def test_exactly_one_needs_review_thurgood_marshall(self, tmp_path):
        # A genuine, honestly-flagged sub-0.85-Jaccard fuzzy match
        # ("Thurgood Marshall Middle School" vs. CDE's "Marshall
        # Middle") -- every other row is an exact normalized-name match
        # (needs_review == False).
        flagged = {t["team_id"] for t in self._geocoded(tmp_path) if t["needs_review"]}
        assert flagged == {"mathcounts-thurgood-marshall-middle"}

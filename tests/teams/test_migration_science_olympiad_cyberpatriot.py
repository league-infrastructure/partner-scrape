"""Regression test for sprint 036 ticket 002's Science Olympiad/
CyberPatriot migration from `directory.model.Club` to `teams.model.
Team`.

This is the **permanent, re-runnable form of the one-time diff-check
gate** the ticket's own execution performed before deleting any `Club`
data: it asserts that geocoding the committed `teams/data/
science-olympiad-sd.tsv`/`cyberpatriot-sd.tsv` rows through the real
committed `teams/data/` school directories reproduces a fixture
snapshot of the *pre-migration* `Club` rows' five geocoding fields
(`location_precision`, `latitude`, `longitude`, `matched_name`,
`needs_review`) exactly -- captured from `data/clubs.json` before this
ticket touched anything (San Dieguito High School Academy's
`needs_review = true` and The Preuss School UC San Diego's `"city"`
fallthrough included, both real, both verified to survive).

Why this reproduces rather than re-researches: `teams.geo.SchoolIndex`
(used by `geocode_teams()`) is a documented behavior-identical subclass
of the same `geo_ladder.GeoLadder` `directory.pipeline.
_apply_club_geocoding()` already used to produce the original `Club`
rows, and `directory/data/`'s school directories are a byte-identical
copy of `teams/data/`'s own -- so feeding the same `host_school`/
`city`/`postal_code` strings through `teams.geo.geocode_teams()`
deterministically reproduces the same match. See `directory/DESIGN.md`'s
sprint 036 Revision and `teams/DESIGN.md`'s sprint 036 Revision for the
full migration writeup.
"""

from __future__ import annotations

from pathlib import Path

from partner_scrape.registry.loader import load_active_sources
from partner_scrape.teams.geo import geocode_teams
from partner_scrape.teams.sources.base import run
from partner_scrape.teams.sources.team_static_roster import TeamStaticRosterSource

TEAMS_REGISTRY_DIR = (
    Path(__file__).resolve().parents[2] / "partner_scrape" / "teams" / "registry"
)

#: A fixture snapshot of the 27 pre-migration `Club` rows' five
#: geocoding fields, captured from the real committed `data/clubs.json`
#: (2026-09-03, before sprint 036 ticket 002 deleted the
#: `science-olympiad`/`cyberpatriot` Club rows) -- keyed by the
#: migrated `Team.team_id` (`f"{league.lower()}-{number}"`, where
#: `number` is the same school-name slug the original `club_id` used
#: after stripping its `"science-olympiad-"`/`"cyberpatriot-"` prefix).
_PRE_MIGRATION_SNAPSHOT: dict[str, dict[str, object]] = {
    "cyberpatriot-canyon-crest-academy": {
        "location_precision": "school",
        "latitude": 32.96024,
        "longitude": -117.18835,
        "matched_name": "Canyon Crest Academy",
        "needs_review": False,
    },
    "cyberpatriot-del-norte-high": {
        "location_precision": "school",
        "latitude": 33.015119,
        "longitude": -117.12162,
        "matched_name": "Del Norte High",
        "needs_review": False,
    },
    "cyberpatriot-scripps-ranch-high": {
        "location_precision": "school",
        "latitude": 32.908719,
        "longitude": -117.11199,
        "matched_name": "Scripps Ranch High",
        "needs_review": False,
    },
    "scioly-academy-our-lady-of-peace": {
        "location_precision": "school",
        "latitude": 32.7653,
        "longitude": -117.135661,
        "matched_name": "Academy Of Our Lady Of Peace",
        "needs_review": False,
    },
    "scioly-canyon-crest-academy": {
        "location_precision": "school",
        "latitude": 32.96024,
        "longitude": -117.18835,
        "matched_name": "Canyon Crest Academy",
        "needs_review": False,
    },
    "scioly-carlsbad-high": {
        "location_precision": "school",
        "latitude": 33.163433,
        "longitude": -117.3278,
        "matched_name": "Carlsbad High",
        "needs_review": False,
    },
    "scioly-cathedral-catholic-high": {
        "location_precision": "school",
        "latitude": 32.95965,
        "longitude": -117.201461,
        "matched_name": "Cathedral Catholic High School",
        "needs_review": False,
    },
    "scioly-del-norte-high": {
        "location_precision": "school",
        "latitude": 33.015119,
        "longitude": -117.12162,
        "matched_name": "Del Norte High",
        "needs_review": False,
    },
    "scioly-la-costa-canyon-high": {
        "location_precision": "school",
        "latitude": 33.07348,
        "longitude": -117.22995,
        "matched_name": "La Costa Canyon High",
        "needs_review": False,
    },
    "scioly-la-jolla-high": {
        "location_precision": "school",
        "latitude": 32.833607,
        "longitude": -117.27403,
        "matched_name": "La Jolla High",
        "needs_review": False,
    },
    "scioly-mira-mesa-high": {
        "location_precision": "school",
        "latitude": 32.910904,
        "longitude": -117.14037,
        "matched_name": "Mira Mesa High",
        "needs_review": False,
    },
    "scioly-mt-carmel-high": {
        "location_precision": "school",
        "latitude": 32.965926,
        "longitude": -117.12091,
        "matched_name": "Mt. Carmel High",
        "needs_review": False,
    },
    "scioly-olympian-high": {
        "location_precision": "school",
        "latitude": 32.607105,
        "longitude": -116.97209,
        "matched_name": "Olympian High",
        "needs_review": False,
    },
    "scioly-pacific-ridge-school": {
        "location_precision": "school",
        "latitude": 33.12287,
        "longitude": -117.249791,
        "matched_name": "Pacific Ridge School",
        "needs_review": False,
    },
    "scioly-poway-high": {
        "location_precision": "school",
        "latitude": 32.996858,
        "longitude": -117.02366,
        "matched_name": "Poway High",
        "needs_review": False,
    },
    "scioly-rancho-bernardo-high": {
        "location_precision": "school",
        "latitude": 32.994329,
        "longitude": -117.06805,
        "matched_name": "Rancho Bernardo High",
        "needs_review": False,
    },
    "scioly-rancho-buena-vista-high": {
        "location_precision": "school",
        "latitude": 33.164594,
        "longitude": -117.24715,
        "matched_name": "Rancho Buena Vista High",
        "needs_review": False,
    },
    "scioly-sage-creek-high": {
        "location_precision": "school",
        "latitude": 33.142565,
        "longitude": -117.24945,
        "matched_name": "Sage Creek High",
        "needs_review": False,
    },
    "scioly-san-dieguito-academy": {
        "location_precision": "school",
        "latitude": 33.036329,
        "longitude": -117.27501,
        "matched_name": "San Dieguito HS Academy",
        "needs_review": True,
    },
    "scioly-san-marcos-high": {
        "location_precision": "school",
        "latitude": 33.131215,
        "longitude": -117.20543,
        "matched_name": "San Marcos High",
        "needs_review": False,
    },
    "scioly-scripps-ranch-high": {
        "location_precision": "school",
        "latitude": 32.908719,
        "longitude": -117.11199,
        "matched_name": "Scripps Ranch High",
        "needs_review": False,
    },
    "scioly-bishops-school": {
        "location_precision": "school",
        "latitude": 32.841228,
        "longitude": -117.278766,
        "matched_name": "The Bishop'S School",
        "needs_review": False,
    },
    "scioly-grauer-school": {
        "location_precision": "school",
        "latitude": 33.028537,
        "longitude": -117.256225,
        "matched_name": "Grauer School The",
        "needs_review": False,
    },
    "scioly-preuss-school": {
        "location_precision": "city",
        "latitude": 32.842825,
        "longitude": -117.257645,
        "matched_name": "La Jolla (city centroid)",
        "needs_review": False,
    },
    "scioly-torrey-pines-high": {
        "location_precision": "school",
        "latitude": 32.956384,
        "longitude": -117.22497,
        "matched_name": "Torrey Pines High",
        "needs_review": False,
    },
    "scioly-university-city-high": {
        "location_precision": "school",
        "latitude": 32.861197,
        "longitude": -117.20954,
        "matched_name": "University City High",
        "needs_review": False,
    },
    "scioly-westview-high": {
        "location_precision": "school",
        "latitude": 32.965082,
        "longitude": -117.14808,
        "matched_name": "Westview High",
        "needs_review": False,
    },
}


def _real_migrated_teams():
    sources = load_active_sources(TEAMS_REGISTRY_DIR)
    matches = [s for s in sources if s.source_id in ("science-olympiad-sd", "cyberpatriot-sd")]
    assert len(matches) == 2, "expected both science-olympiad-sd and cyberpatriot-sd entries"

    teams = []
    for source_config in matches:
        teams.extend(run(source_config, TeamStaticRosterSource(), fetcher=None))
    return geocode_teams(teams)


class TestMigrationReproducesOriginalClubGeocodingExactly:
    def test_extracts_exactly_27_teams(self):
        assert len(_real_migrated_teams()) == 27

    def test_snapshot_covers_every_migrated_team(self):
        teams = _real_migrated_teams()
        assert {t.team_id for t in teams} == set(_PRE_MIGRATION_SNAPSHOT)

    def test_every_migrated_team_reproduces_its_pre_migration_club_geocoding_exactly(self):
        for team in _real_migrated_teams():
            expected = _PRE_MIGRATION_SNAPSHOT[team.team_id]
            assert team.location_precision == expected["location_precision"], team.team_id
            assert team.latitude == expected["latitude"], team.team_id
            assert team.longitude == expected["longitude"], team.team_id
            assert team.matched_name == expected["matched_name"], team.team_id
            assert team.needs_review == expected["needs_review"], team.team_id

    def test_san_dieguito_academy_needs_review_flag_survives(self):
        teams = {t.team_id: t for t in _real_migrated_teams()}
        assert teams["scioly-san-dieguito-academy"].needs_review is True

    def test_preuss_school_city_fallthrough_survives(self):
        teams = {t.team_id: t for t in _real_migrated_teams()}
        assert teams["scioly-preuss-school"].location_precision == "city"

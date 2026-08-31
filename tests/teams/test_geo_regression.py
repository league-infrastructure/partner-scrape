"""Byte-identical output regression proof for ticket 018-006's
extraction of the shared offline geocoding ladder out of
``teams/geo.py`` into ``partner_scrape/geo_ladder.py``.

The expected values in ``_EXPECTED`` below were captured by running
``teams.geo.geocode_teams()`` against this file's fixture data
*before* the extraction touched a single line of ``teams/geo.py`` --
not reasoned out by hand, not re-derived after the fact. This test
proves the refactor is a pure code move: every field
``geocode_teams()`` sets on a ``Team`` (latitude, longitude,
``location_precision``, ``matched_name``, ``needs_review``,
``organization_website``) is identical, field for field, before and
after ``SchoolIndex`` became a thin subclass of the shared
``GeoLadder``. It deliberately exercises every rung in one combined
run through one shared index (rather than one index per rung, as
``tests/teams/test_geo.py``'s per-rung tests do) as an additional,
end-to-end angle on the same ``geocode_teams()`` entry point
``teams.pipeline.run_teams()`` actually calls.

Fixture data is intentionally distinct from (not shared with)
``tests/teams/test_geo.py``'s own ``_build_data_dir`` fixtures, so this
regression proof does not silently depend on that file's fixtures
staying exactly as they are today.
"""

from __future__ import annotations

from pathlib import Path

from partner_scrape.teams.geo import geocode_teams
from partner_scrape.teams.model import Team

_PUBLIC_HEADER = "School\tDistrict\tCity\tZip\tWebSite\tLatitude\tLongitude\tStatusType\tVirtual"
_PRIVATE_HEADER = "School\tCity\tZip\tLatitude\tLongitude\tVintages"

#: (School, District, City, Zip, WebSite, Latitude, Longitude, StatusType, Virtual)
_PUBLIC_ROWS = [
    # Rung 2, with a website -- proves organization_website population
    # survives the extraction unchanged.
    ("Mission Bay High", "San Diego Unified", "San Diego", "92109", "www.sandiegounified.org/missionbay", "32.790000", "-117.240000", "Active", "N"),
    # Rung 2, StatusType preference: Closed must lose to Active.
    ("Clairemont High", "San Diego Unified", "San Diego", "92117", "", "1.111111", "-1.111111", "Closed", "N"),
    ("Clairemont High", "San Diego Unified", "San Diego", "92117", "", "2.222222", "-2.222222", "Active", "N"),
    # Virtual == "V" -- must never be a match candidate.
    ("Ghost Academy Online", "Encinitas Union", "Encinitas", "92024", "", "5.000000", "-5.000000", "Active", "V"),
    # Rung 3: token-set >= 0.60 within the same city (score 0.60, needs_review).
    ("Kearny Digital Media Design Academy", "San Diego Unified", "San Diego", "92123", "", "32.800000", "-117.100000", "Active", "N"),
    # Rung 4: token-set >= 0.80 county-wide (score exactly 0.80, needs_review).
    ("Riverside Canyon Community Learning Academy", "Julian Union", "Julian", "92036", "", "33.080000", "-116.600000", "Active", "N"),
]

#: (School, City, Zip, Latitude, Longitude, Vintages)
_PRIVATE_ROWS = [
    # NCES-only match -- proves the private directory is consulted and
    # its missing website column never fabricates organization_website.
    ("Grace Lutheran Academy", "Vista", "92083", "33.200000", "-117.250000", "2021-22,2023-24"),
]

_ZIP_CENTROIDS = {"92173": (32.542200, -117.032500)}
_CITY_CENTROIDS = {"clairelake": (33.500000, -117.300000)}

_OVERRIDES_TOML = (
    '["mystery academy"]\n'
    'matched_name = "Mystery Academy (verified)"\n'
    "latitude = 34.001000\n"
    "longitude = -118.001000\n"
)


def _write_tsv(path: Path, header: str, rows: list[tuple[str, ...]]) -> None:
    lines = [header] + ["\t".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_centroids_toml(path: Path, entries: dict[str, tuple[float, float]]) -> None:
    parts = []
    for key, (lat, lon) in entries.items():
        parts.append(f'["{key}"]\nlatitude = {lat}\nlongitude = {lon}\n')
    path.write_text("\n".join(parts), encoding="utf-8")


def _build_data_dir(tmp_path: Path) -> Path:
    data_dir = tmp_path / "geo-regression-data"
    data_dir.mkdir()
    _write_tsv(data_dir / "sd-schools-public.tsv", _PUBLIC_HEADER, _PUBLIC_ROWS)
    _write_tsv(data_dir / "sd-schools-private.tsv", _PRIVATE_HEADER, _PRIVATE_ROWS)
    _write_centroids_toml(data_dir / "zip-centroids.toml", _ZIP_CENTROIDS)
    _write_centroids_toml(data_dir / "city-centroids.toml", _CITY_CENTROIDS)
    (data_dir / "school-overrides.toml").write_text(_OVERRIDES_TOML, encoding="utf-8")
    return data_dir


def _team(**kwargs) -> Team:
    defaults = dict(team_id="t", league="FTC", number="1", name="Test Team")
    defaults.update(kwargs)
    return Team(**defaults)


#: One Team per rung (plus website population and virtual-row
#: rejection), captured against pre-extraction `teams/geo.py`.
_FIXTURE_TEAMS = [
    _team(team_id="t1", organization="Mission Bay High", city="San Diego"),
    _team(team_id="t2", organization="Clairemont High", city="San Diego"),
    _team(team_id="t3", organization="Kearny Digital Media", city="San Diego"),
    _team(team_id="t4", organization="Riverside Canyon Community Academy", city="Alpine"),
    _team(team_id="t5", organization="Grace Lutheran Academy", city="Vista"),
    _team(team_id="t6", organization="Nonexistent Robotics Club", city="Nowhereville", postal_code="92173"),
    _team(team_id="t7", organization="", city="Clairelake"),
    _team(team_id="t8", organization="", city="  ClaireLake  "),
    _team(team_id="t9", organization="Totally Unknown Org", city="Nowhereatall"),
    _team(team_id="t10", organization="Mystery Academy", city="Anywhere"),
    _team(team_id="t11", organization="Ghost Academy Online", city="Encinitas"),
]

#: Captured pre-refactor, one entry per `_FIXTURE_TEAMS` team_id:
#: (latitude, longitude, location_precision, matched_name, needs_review,
#: organization_website).
_EXPECTED: dict[str, tuple[float | None, float | None, str, str, bool, str]] = {
    "t1": (32.79, -117.24, "school", "Mission Bay High", False, "www.sandiegounified.org/missionbay"),
    "t2": (2.222222, -2.222222, "school", "Clairemont High", False, ""),
    "t3": (32.8, -117.1, "school", "Kearny Digital Media Design Academy", True, ""),
    "t4": (33.08, -116.6, "school", "Riverside Canyon Community Learning Academy", True, ""),
    "t5": (33.2, -117.25, "school", "Grace Lutheran Academy", False, ""),
    "t6": (32.5422, -117.0325, "zip", "ZIP 92173 centroid", False, ""),
    "t7": (33.5, -117.3, "city", "Clairelake (city centroid)", False, ""),
    "t8": (33.5, -117.3, "city", "ClaireLake (city centroid)", False, ""),
    "t9": (None, None, "none", "", False, ""),
    "t10": (34.001, -118.001, "school", "Mystery Academy (verified)", False, ""),
    "t11": (None, None, "none", "", False, ""),
}


def test_geocode_teams_output_is_byte_identical_to_pre_refactor_capture(tmp_path):
    data_dir = _build_data_dir(tmp_path)

    result = geocode_teams(list(_FIXTURE_TEAMS), data_dir=data_dir)

    assert {t.team_id for t in result} == set(_EXPECTED)
    for team in result:
        actual = (
            team.latitude,
            team.longitude,
            team.location_precision,
            team.matched_name,
            team.needs_review,
            team.organization_website,
        )
        assert actual == _EXPECTED[team.team_id], f"{team.team_id}: {actual} != {_EXPECTED[team.team_id]}"

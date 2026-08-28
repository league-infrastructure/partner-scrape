"""Tests for partner_scrape.teams.geo: the seven-rung offline
geocoding ladder.

Every test here builds a small, hand-authored fixture data directory
(`_build_data_dir`) rather than touching the real, committed
`partner_scrape/teams/data/` files (~800+213 school rows) -- fixture-
based, no network, matching sprint.md's Test Strategy exactly. Real
data files are read only via `SchoolIndex(data_dir=None)`'s default in
`TestRealCommittedDataFiles`, which sanity-checks the real files parse
and stay internally consistent -- it does not assert exact match
counts against them (those depend on CDE/NCES's live content and are
covered, with tolerant bounds, by `tests/teams/test_pipeline.py`'s
aggregate-distribution test over the real 211-team FTC+FRC corpus).
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

import partner_scrape.teams.geo as geo_module
from partner_scrape.teams.geo import (
    SchoolIndex,
    geocode_teams,
    normalize_city_name,
    normalize_school_name,
)
from partner_scrape.teams.model import Team

# ---------------------------------------------------------------------------
# Fixture data directory builder
# ---------------------------------------------------------------------------

_PUBLIC_HEADER = "School\tDistrict\tCity\tZip\tWebSite\tLatitude\tLongitude\tStatusType\tVirtual"
_PRIVATE_HEADER = "School\tCity\tZip\tLatitude\tLongitude\tVintages"

#: (School, District, City, Zip, WebSite, Latitude, Longitude, StatusType, Virtual)
_PUBLIC_ROWS = [
    # Rung 2 (exact match, after stopword-stripping) + StatusType
    # preference: two rows share the normalized name "poway high" --
    # the Closed one must lose to the Active one.
    ("Poway High", "Poway Unified", "Poway", "92064", "www.powayusd.com/poway", "33.100000", "-117.100000", "Closed", "N"),
    ("Poway High", "Poway Unified", "Poway", "92064", "www.powayusd.com/poway", "33.000000", "-117.000000", "Active", "N"),
    # Rejected: Virtual == "V" (primarily virtual, no real campus). If
    # this leaked into the index, a team org exactly matching this name
    # would wrongly resolve to school precision.
    ("Old Online Academy", "Escondido Union", "Escondido", "92025", "", "32.000000", "-117.000000", "Active", "V"),
    # Rung 3: token-set >= 0.60 within the same city, score < 0.85 so
    # needs_review is expected. "Foothill Oak Elementary" (3 tokens)
    # vs. a team org normalizing to {foothill, oak} (2 tokens) ->
    # Jaccard = 2/3 = 0.667.
    ("Foothill Oak Elementary", "Ramona Unified", "Ramona", "92065", "", "33.030000", "-116.870000", "Active", "N"),
    # Rung 4: token-set >= 0.80 county-wide, *not* within the team's
    # reported city (so rung 3 must miss and fall through to rung 4).
    # "Riverside Canyon Community Learning Academy" (5 tokens) vs. a
    # team org normalizing to {riverside, canyon, community, academy}
    # (4 tokens) -> Jaccard = 4/5 = 0.80.
    ("Riverside Canyon Community Learning Academy", "Julian Union", "Julian", "92036", "", "33.080000", "-116.600000", "Active", "N"),
]

#: (School, City, Zip, Latitude, Longitude, Vintages)
_PRIVATE_ROWS = [
    # NCES-only match: no public-school row shares this name, proving
    # the private-school directory is actually consulted.
    ("Grace Christian Academy", "Escondido", "92026", "33.150000", "-117.050000", "2021-22,2023-24"),
]

_ZIP_CENTROIDS = {
    "92064": (32.960000, -117.035000),  # Poway
}

_CITY_CENTROIDS = {
    "julian": (33.078600, -116.602800),
    "san clemente": (33.426900, -117.612300),
    # deliberately no "ensenada" entry -- out-of-country, never guessed
    # (matches dev/refresh_school_directories.py's own real omission).
}


def _write_tsv(path: Path, header: str, rows: list[tuple[str, ...]]) -> None:
    lines = [header] + ["\t".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_centroids_toml(path: Path, entries: dict[str, tuple[float, float]]) -> None:
    parts = []
    for key, (lat, lon) in entries.items():
        parts.append(f'["{key}"]\nlatitude = {lat}\nlongitude = {lon}\n')
    path.write_text("\n".join(parts), encoding="utf-8")


def _build_data_dir(
    tmp_path: Path,
    *,
    public_rows: list[tuple[str, ...]] | None = None,
    private_rows: list[tuple[str, ...]] | None = None,
    zip_centroids: dict[str, tuple[float, float]] | None = None,
    city_centroids: dict[str, tuple[float, float]] | None = None,
    overrides_toml: str = "",
) -> Path:
    data_dir = tmp_path / "geo-data"
    data_dir.mkdir()
    _write_tsv(data_dir / "sd-schools-public.tsv", _PUBLIC_HEADER, public_rows if public_rows is not None else _PUBLIC_ROWS)
    _write_tsv(data_dir / "sd-schools-private.tsv", _PRIVATE_HEADER, private_rows if private_rows is not None else _PRIVATE_ROWS)
    _write_centroids_toml(data_dir / "zip-centroids.toml", zip_centroids if zip_centroids is not None else _ZIP_CENTROIDS)
    _write_centroids_toml(data_dir / "city-centroids.toml", city_centroids if city_centroids is not None else _CITY_CENTROIDS)
    (data_dir / "school-overrides.toml").write_text(overrides_toml, encoding="utf-8")
    return data_dir


def _team(**kwargs) -> Team:
    defaults = dict(team_id="ftc-1", league="FTC", number=1, name="Test Team")
    defaults.update(kwargs)
    return Team(**defaults)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


class TestNormalizeSchoolName:
    def test_strips_parentheticals(self):
        # CDE writes "Surname (Given Name)" -- e.g. "Feaster (Mae L.) Charter".
        assert normalize_school_name("Feaster (Mae L.) Charter") == "feaster charter"

    def test_lowercases_and_strips_punctuation(self):
        assert normalize_school_name("Mt. Carmel High") == "mt carmel high"

    def test_drops_generic_stopword_tokens(self):
        # "School"/"the" carry no identifying signal and, left in,
        # would make "Poway High School" score below the CDE
        # directory's own official "Poway High" -- see _STOPWORD_TOKENS.
        assert normalize_school_name("Poway High School") == normalize_school_name("Poway High")
        assert normalize_school_name("The Waldorf School Of San Diego") == normalize_school_name(
            "Waldorf School of San Diego"
        )

    def test_does_not_drop_type_words_that_carry_real_signal(self):
        # "High"/"Middle"/"Elementary" distinguish real, different
        # schools at the same place name -- must never be stripped.
        assert normalize_school_name("Poway High") != normalize_school_name("Poway Middle")

    def test_empty_and_whitespace_only_normalize_to_empty_string(self):
        assert normalize_school_name("") == ""
        assert normalize_school_name("   ") == ""


class TestNormalizeCityName:
    def test_dirty_city_strings_normalize_identically(self):
        assert normalize_city_name("La Jolla ") == normalize_city_name("la jolla")
        assert normalize_city_name("carlsbad") == normalize_city_name("Carlsbad")
        assert normalize_city_name("san diego") == normalize_city_name("San Diego")

    def test_distinct_cities_stay_distinct(self):
        assert normalize_city_name("Poway") != normalize_city_name("Ramona")


# ---------------------------------------------------------------------------
# Ladder rungs, end to end via SchoolIndex.resolve()
# ---------------------------------------------------------------------------


class TestRung1Overrides:
    def test_override_wins_even_when_an_algorithmic_match_would_also_succeed(self, tmp_path):
        overrides = (
            '["poway high"]\n'
            'matched_name = "Poway High (hand-verified)"\n'
            "latitude = 40.000000\n"
            "longitude = -100.000000\n"
        )
        data_dir = _build_data_dir(tmp_path, overrides_toml=overrides)
        index = SchoolIndex(data_dir=data_dir)
        team = _team(organization="Poway High School", city="Poway")

        index.resolve(team)

        assert team.location_precision == "school"
        assert team.latitude == 40.0
        assert team.longitude == -100.0
        assert team.matched_name == "Poway High (hand-verified)"
        assert team.needs_review is False


class TestRung2ExactMatch:
    def test_exact_normalized_match_resolves_to_the_active_row(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)
        team = _team(organization="Poway High School", city="Poway")

        index.resolve(team)

        assert team.location_precision == "school"
        assert team.latitude == 33.0
        assert team.longitude == -117.0  # the Active row, not the Closed one
        assert team.matched_name == "Poway High"
        assert team.needs_review is False
        assert team.organization_website == "www.powayusd.com/poway"

    def test_closed_row_never_wins_over_active(self, tmp_path):
        # Directly proves the StatusType preference, independent of
        # which row happens to be listed first in the TSV.
        rows = [
            ("Poway High", "Poway Unified", "Poway", "92064", "", "1.000000", "-1.000000", "Active", "N"),
            ("Poway High", "Poway Unified", "Poway", "92064", "", "99.000000", "-99.000000", "Closed", "N"),
        ]
        data_dir = _build_data_dir(tmp_path, public_rows=rows)
        index = SchoolIndex(data_dir=data_dir)
        team = _team(organization="Poway High", city="Poway")

        index.resolve(team)

        assert (team.latitude, team.longitude) == (1.0, -1.0)


class TestVirtualRowRejected:
    def test_a_virtual_school_row_is_never_a_match_candidate(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)
        team = _team(organization="Old Online Academy", city="Escondido")

        index.resolve(team)

        # The Virtual row is entirely absent from the index -- this
        # team falls all the way through to "none" (no zip/city
        # centroid fixture exists for Escondido/92025 either).
        assert team.location_precision == "none"
        assert team.latitude is None


class TestNcesPrivateSchoolMatch:
    def test_a_school_present_only_in_the_private_directory_still_resolves(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)
        team = _team(organization="Grace Christian Academy", city="Escondido")

        index.resolve(team)

        assert team.location_precision == "school"
        assert team.latitude == 33.15
        assert team.longitude == -117.05
        assert team.matched_name == "Grace Christian Academy"
        assert team.needs_review is False
        # NCES's data has no website column -- never fabricated.
        assert team.organization_website == ""


class TestRung3TokenSetWithinCity:
    def test_moderate_score_within_city_matches_and_needs_review(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)
        team = _team(organization="Foothill Oak School", city="Ramona")

        index.resolve(team)

        assert team.location_precision == "school"
        assert team.matched_name == "Foothill Oak Elementary"
        assert team.needs_review is True  # score 0.667 < 0.85

    def test_score_below_060_does_not_match_at_all(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)
        # Only "foothill" overlaps -- well below the 0.60 within-city floor.
        team = _team(organization="Foothill Zzyzx Nowhere Place", city="Ramona")

        index.resolve(team)

        assert team.location_precision != "school"


class TestRung4TokenSetCountyWide:
    def test_high_score_match_outside_the_teams_city_still_resolves(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)
        # Team reports a city ("Alpine") with no matching candidate at
        # all -- rung 3 must miss and fall through to rung 4's
        # county-wide search, which finds the Julian-city school.
        team = _team(organization="Riverside Canyon Community Academy", city="Alpine")

        index.resolve(team)

        assert team.location_precision == "school"
        assert team.matched_name == "Riverside Canyon Community Learning Academy"
        assert team.needs_review is True  # score exactly 0.80 < 0.85

    def test_needs_review_reflects_score_not_which_rung_matched(self, tmp_path):
        # A fuzzy (non-exact) match that scores >= 0.85 must NOT be
        # flagged -- needs_review is score-driven, not rung-driven.
        # 7-token CDE name, team org drops exactly one token:
        # Jaccard = 6/7 = 0.857 >= 0.85.
        rows = list(_PUBLIC_ROWS) + [
            ("Alpha Beta Gamma Delta Epsilon Zeta Academy", "Somewhere Union", "Coronado", "92118", "", "10.000000", "-10.000000", "Active", "N"),
        ]
        data_dir = _build_data_dir(tmp_path, public_rows=rows)
        index = SchoolIndex(data_dir=data_dir)
        team = _team(organization="Alpha Beta Gamma Delta Epsilon Zeta", city="Coronado")

        index.resolve(team)

        assert team.location_precision == "school"
        assert team.matched_name == "Alpha Beta Gamma Delta Epsilon Zeta Academy"
        assert team.needs_review is False  # score 0.857 >= 0.85, despite being a fuzzy match


class TestRung5ZipCentroid:
    def test_unmatched_org_falls_through_to_zip_centroid(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)
        team = _team(organization="Some Unresolvable Org Name", city="Nowhere", postal_code="92064")

        index.resolve(team)

        assert team.location_precision == "zip"
        assert (team.latitude, team.longitude) == (32.96, -117.035)
        assert team.matched_name == "ZIP 92064 centroid"
        assert team.needs_review is False

    def test_empty_organization_with_a_zip_resolves_to_zip_precision(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)
        team = _team(organization="", city="Nowhere", postal_code="92064-1234")

        index.resolve(team)

        assert team.location_precision == "zip"


class TestRung6CityCentroid:
    def test_family_community_team_resolves_to_city_precision(self, tmp_path):
        # organization="" is exactly what sources/ftcscout.py maps its
        # Family/Community sentinel to.
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)
        team = _team(organization="", org_type="family_community", city="Julian")

        index.resolve(team)

        assert team.location_precision == "city"
        assert (team.latitude, team.longitude) == (33.0786, -116.6028)
        assert team.matched_name == "Julian (city centroid)"
        assert team.needs_review is False

    def test_dirty_city_string_still_resolves_to_the_same_centroid(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)

        clean = _team(team_id="ftc-1", organization="", city="Julian")
        dirty_spacing = _team(team_id="ftc-2", organization="", city="Julian ")
        dirty_case = _team(team_id="ftc-3", organization="", city="julian")

        for team in (clean, dirty_spacing, dirty_case):
            index.resolve(team)

        assert (clean.latitude, clean.longitude) == (dirty_spacing.latitude, dirty_spacing.longitude)
        assert (clean.latitude, clean.longitude) == (dirty_case.latitude, dirty_case.longitude)
        assert clean.location_precision == dirty_spacing.location_precision == dirty_case.location_precision == "city"

    def test_out_of_county_team_with_a_real_city_centroid_still_resolves_and_stays_flagged(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)
        team = _team(organization="", city="San Clemente", in_region=False)

        index.resolve(team)

        assert team.location_precision == "city"
        assert team.in_region is False  # geo.py never touches in_region
        assert team.matched_name == "San Clemente (city centroid)"


class TestRung7NoMatch:
    def test_ensenada_team_exhausts_every_rung_and_stays_present(self, tmp_path):
        # No CDE/NCES match, no ZIP, and (deliberately) no "ensenada"
        # city-centroid entry -- Mexico, out of US Census/CDE coverage,
        # never guessed (matches dev/refresh_school_directories.py's
        # own real omission of Ensenada).
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)
        team = _team(
            team_id="ftc-9164",
            organization="CETYS Preparatoria",
            city="Ensenada",
            in_region=False,
        )

        index.resolve(team)

        assert team.location_precision == "none"
        assert team.latitude is None
        assert team.longitude is None
        assert team.matched_name == ""
        assert team.needs_review is False
        # Never dropped -- still a fully present, returned Team.
        assert team.team_id == "ftc-9164"
        assert team.in_region is False

    def test_geocode_teams_never_drops_an_unresolvable_team_from_the_list(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        teams = [_team(team_id="ftc-9164", organization="Nobody Knows This Org", city="Ensenada")]

        result = geocode_teams(teams, data_dir=data_dir)

        assert len(result) == 1
        assert result[0].team_id == "ftc-9164"
        assert result[0].location_precision == "none"


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


class TestPerSchoolNotPerTeamCaching:
    def test_multiple_teams_at_the_same_school_hit_the_matcher_once(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)
        teams = [
            _team(team_id="ftc-1", organization="Poway High School", city="Poway"),
            _team(team_id="ftc-2", organization="Poway High School", city="Poway"),
            _team(team_id="frc-3", organization="Poway High School", city="Poway"),
        ]

        for team in teams:
            index.resolve(team)

        assert index.match_calls == 1
        assert all(t.location_precision == "school" for t in teams)

    def test_negative_matches_are_cached_too(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)

        first = index.resolve_school("D Robotics Education", "San Diego")
        second = index.resolve_school("D Robotics Education", "San Diego")

        assert first is None
        assert second is None
        assert index.match_calls == 1

    def test_different_organizations_each_cost_one_match_call(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)

        index.resolve_school("Poway High School", "Poway")
        index.resolve_school("Grace Christian Academy", "Escondido")
        index.resolve_school("Poway High School", "Poway")  # repeat -- cached

        assert index.match_calls == 2

    def test_empty_organization_never_invokes_or_counts_against_the_matcher(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        index = SchoolIndex(data_dir=data_dir)

        result = index.resolve_school("", "San Diego")

        assert result is None
        assert index.match_calls == 0


# ---------------------------------------------------------------------------
# Zero network calls (structural)
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORT_PREFIXES = ("urllib", "http", "requests", "socket", "partner_scrape.fetch")


def _imports_forbidden_network_module(py_path: Path) -> list[str]:
    tree = ast.parse(py_path.read_text(), filename=str(py_path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders.extend(
                alias.name
                for alias in node.names
                if alias.name.startswith(_FORBIDDEN_IMPORT_PREFIXES)
            )
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(_FORBIDDEN_IMPORT_PREFIXES):
                offenders.append(node.module)
    return offenders


class TestZeroNetworkCalls:
    def test_geo_module_source_imports_no_network_capable_module(self):
        geo_path = Path(geo_module.__file__)

        offenders = _imports_forbidden_network_module(geo_path)

        assert offenders == []

    def test_geocode_teams_signature_has_no_fetcher_or_network_parameter(self):
        # Not "an unused Fetcher parameter" -- there is no such
        # parameter at all, so no network-capable object can reach this
        # function even by accident.
        params = set(inspect.signature(geocode_teams).parameters)

        assert params == {"teams", "data_dir"}

    def test_school_index_constructor_has_no_fetcher_or_network_parameter(self):
        params = set(inspect.signature(SchoolIndex.__init__).parameters) - {"self"}

        assert params == {"data_dir"}

    def test_geocode_teams_runs_to_completion_with_only_a_fixture_data_dir(self, tmp_path):
        # End-to-end proof, not just a signature check: a full run
        # against fixture-only teams, with nothing resembling a Fetcher
        # constructed or importable anywhere in this test's own scope.
        data_dir = _build_data_dir(tmp_path)
        teams = [_team(organization="Poway High School", city="Poway")]

        result = geocode_teams(teams, data_dir=data_dir)

        assert result[0].location_precision == "school"


# ---------------------------------------------------------------------------
# Malformed data files fail loudly
# ---------------------------------------------------------------------------


class TestMalformedDataFailsLoudly:
    def test_missing_data_directory_raises_runtime_error(self, tmp_path):
        with pytest.raises(RuntimeError):
            SchoolIndex(data_dir=tmp_path / "does-not-exist")

    def test_missing_one_required_file_raises_runtime_error(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        (data_dir / "zip-centroids.toml").unlink()

        with pytest.raises(RuntimeError):
            SchoolIndex(data_dir=data_dir)

    def test_malformed_toml_raises_runtime_error(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        (data_dir / "school-overrides.toml").write_text("this is not [ valid toml", encoding="utf-8")

        with pytest.raises(RuntimeError):
            SchoolIndex(data_dir=data_dir)

    def test_non_numeric_coordinate_raises_runtime_error(self, tmp_path):
        rows = [("Bad Coordinate School", "Some Unified", "Somewhere", "92064", "", "not-a-number", "-117.000000", "Active", "N")]
        data_dir = _build_data_dir(tmp_path, public_rows=rows)

        with pytest.raises(RuntimeError):
            SchoolIndex(data_dir=data_dir)


# ---------------------------------------------------------------------------
# geocode_teams(): the pipeline-facing entry point
# ---------------------------------------------------------------------------


class TestGeocodeTeamsEntryPoint:
    def test_mutates_and_returns_the_same_list_object(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        teams = [_team(organization="Poway High School", city="Poway")]

        result = geocode_teams(teams, data_dir=data_dir)

        assert result is teams

    def test_every_input_team_is_present_in_the_output(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        teams = [
            _team(team_id="ftc-1", organization="Poway High School", city="Poway"),
            _team(team_id="ftc-2", organization="", city="Julian"),
            _team(team_id="ftc-3", organization="Nothing Matches This", city="Nowhere"),
        ]

        result = geocode_teams(teams, data_dir=data_dir)

        assert {t.team_id for t in result} == {"ftc-1", "ftc-2", "ftc-3"}


# ---------------------------------------------------------------------------
# Real, committed data files -- sanity only, no exact-count pinning
# ---------------------------------------------------------------------------


class TestRealCommittedDataFiles:
    """Loads the actual `partner_scrape/teams/data/` files this
    ticket commits -- proves they parse and the index builds cleanly.
    Exact match-count assertions against the real 211-team corpus live
    in `tests/teams/test_pipeline.py` (tolerant bounds, since CDE/NCES
    content changes with each yearly refresh)."""

    def test_default_data_dir_loads_without_error(self):
        index = SchoolIndex(data_dir=None)

        assert index.match_calls == 0

    def test_a_known_real_school_resolves_via_the_real_data(self):
        index = SchoolIndex(data_dir=None)
        team = _team(organization="Poway High School", city="Poway")

        index.resolve(team)

        assert team.location_precision == "school"
        assert team.latitude is not None
        assert team.needs_review is False

"""Tests for partner_scrape.geo_ladder: the shared, ``Team``-independent
offline geocoding ladder extracted from ``teams/geo.py`` in ticket
018-006.

These tests exercise `GeoLadder` entirely through plain strings
(`organization`, `city`, `postal_code`) -- no `Team` (or any other
caller-owned record type) is constructed anywhere in this file, proving
the ladder is genuinely usable independent of `teams/`. `tests/teams/
test_geo.py` continues to cover the `Team`-specific wrapper
(`teams.geo.SchoolIndex`/`geocode_teams`) end to end, and
`tests/teams/test_geo_regression.py` proves the extraction changed
nothing about that wrapper's output.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from partner_scrape.geo_ladder import (
    GeoLadder,
    LocationMatch,
    normalize_city_name,
    normalize_school_name,
)

_PUBLIC_HEADER = "School\tDistrict\tCity\tZip\tWebSite\tLatitude\tLongitude\tStatusType\tVirtual"
_PRIVATE_HEADER = "School\tCity\tZip\tLatitude\tLongitude\tVintages"

_PUBLIC_ROWS = [
    ("Poway High", "Poway Unified", "Poway", "92064", "www.powayusd.com/poway", "33.000000", "-117.000000", "Active", "N"),
]
_PRIVATE_ROWS: list[tuple[str, ...]] = []

_ZIP_CENTROIDS = {"92064": (32.960000, -117.035000)}
_CITY_CENTROIDS = {"julian": (33.078600, -116.602800)}


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
    data_dir = tmp_path / "geo-ladder-data"
    data_dir.mkdir()
    _write_tsv(data_dir / "sd-schools-public.tsv", _PUBLIC_HEADER, public_rows if public_rows is not None else _PUBLIC_ROWS)
    _write_tsv(data_dir / "sd-schools-private.tsv", _PRIVATE_HEADER, private_rows if private_rows is not None else _PRIVATE_ROWS)
    _write_centroids_toml(data_dir / "zip-centroids.toml", zip_centroids if zip_centroids is not None else _ZIP_CENTROIDS)
    _write_centroids_toml(data_dir / "city-centroids.toml", city_centroids if city_centroids is not None else _CITY_CENTROIDS)
    (data_dir / "school-overrides.toml").write_text(overrides_toml, encoding="utf-8")
    return data_dir


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestNormalizeSchoolName:
    def test_strips_parentheticals_lowercases_and_drops_stopwords(self):
        assert normalize_school_name("Feaster (Mae L.) Charter") == "feaster charter"
        assert normalize_school_name("Poway High School") == normalize_school_name("Poway High")

    def test_does_not_drop_type_words_that_carry_real_signal(self):
        assert normalize_school_name("Poway High") != normalize_school_name("Poway Middle")


class TestNormalizeCityName:
    def test_dirty_city_strings_normalize_identically(self):
        assert normalize_city_name("La Jolla ") == normalize_city_name("la jolla")
        assert normalize_city_name("San Diego") == normalize_city_name("san diego")


# ---------------------------------------------------------------------------
# Rungs 5/6: zip/city centroid, callable independent of any Team
# ---------------------------------------------------------------------------


class TestZipCentroidIndependentOfTeam:
    def test_resolve_zip_returns_a_bare_coordinate_tuple(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        assert ladder.resolve_zip("92064") == (32.96, -117.035)

    def test_resolve_zip_truncates_zip9_to_zip5(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        assert ladder.resolve_zip("92064-1234") == (32.96, -117.035)

    def test_resolve_zip_returns_none_for_an_unknown_zip(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        assert ladder.resolve_zip("00000") is None

    def test_resolve_zip_returns_none_for_empty_input(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        assert ladder.resolve_zip("") is None


class TestCityCentroidIndependentOfTeam:
    def test_resolve_city_returns_a_bare_coordinate_tuple(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        assert ladder.resolve_city("Julian") == (33.0786, -116.6028)

    def test_resolve_city_normalizes_dirty_input(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        assert ladder.resolve_city(" julian ") == ladder.resolve_city("Julian")

    def test_resolve_city_returns_none_for_an_unknown_city(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        assert ladder.resolve_city("Nowhereville") is None


# ---------------------------------------------------------------------------
# Rung 7: the "never guess" honesty rule, callable independent of any Team
# ---------------------------------------------------------------------------


class TestNeverGuessRung7:
    def test_locate_with_no_organization_zip_or_city_match_returns_none_precision(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        match = ladder.locate("Nobody Knows This Org", "Nowhereatall", "")

        assert match == LocationMatch(
            latitude=None,
            longitude=None,
            location_precision="none",
            matched_name="",
            needs_review=False,
            website="",
        )

    def test_locate_never_fabricates_a_coordinate_even_with_a_close_almost_match(self, tmp_path):
        # "Poway High" exists but nothing here is close enough to match
        # at any threshold -- proving a near-miss still yields "none"
        # rather than a guessed pin.
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        match = ladder.locate("Zzyzx Nonexistent Institute", "Zzyzx", "")

        assert match.location_precision == "none"
        assert match.latitude is None
        assert match.longitude is None


# ---------------------------------------------------------------------------
# locate(): the full ladder, generic and Team-independent
# ---------------------------------------------------------------------------


class TestLocateFullLadder:
    def test_school_match_takes_priority_over_zip_and_city(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        match = ladder.locate("Poway High School", "Poway", "92064")

        assert match.location_precision == "school"
        assert match.matched_name == "Poway High"
        assert match.website == "www.powayusd.com/poway"

    def test_falls_through_to_zip_when_organization_does_not_match(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        match = ladder.locate("Some Unresolvable Org", "Nowhere", "92064")

        assert match.location_precision == "zip"
        assert (match.latitude, match.longitude) == (32.96, -117.035)

    def test_falls_through_to_city_when_organization_and_zip_do_not_match(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        match = ladder.locate("", "Julian", "")

        assert match.location_precision == "city"
        assert match.matched_name == "Julian (city centroid)"

    def test_empty_organization_skips_school_matching_entirely(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        ladder = GeoLadder(data_dir)

        ladder.locate("", "Julian", "")

        assert ladder.match_calls == 0


# ---------------------------------------------------------------------------
# Malformed data fails loudly
# ---------------------------------------------------------------------------


class TestMalformedDataFailsLoudly:
    def test_missing_data_directory_raises_runtime_error(self, tmp_path):
        with pytest.raises(RuntimeError):
            GeoLadder(tmp_path / "does-not-exist")

    def test_missing_one_required_file_raises_runtime_error(self, tmp_path):
        data_dir = _build_data_dir(tmp_path)
        (data_dir / "city-centroids.toml").unlink()

        with pytest.raises(RuntimeError):
            GeoLadder(data_dir)


# ---------------------------------------------------------------------------
# Zero network calls (structural) -- same invariant as teams/geo.py
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORT_PREFIXES = ("urllib", "http", "requests", "socket", "partner_scrape.fetch")


def test_geo_ladder_module_source_imports_no_network_capable_module():
    import ast
    import partner_scrape.geo_ladder as geo_ladder_module

    geo_ladder_path = Path(geo_ladder_module.__file__)
    tree = ast.parse(geo_ladder_path.read_text(), filename=str(geo_ladder_path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders.extend(
                alias.name for alias in node.names if alias.name.startswith(_FORBIDDEN_IMPORT_PREFIXES)
            )
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(_FORBIDDEN_IMPORT_PREFIXES):
                offenders.append(node.module)

    assert offenders == []


def test_geo_ladder_module_never_imports_anything_under_teams():
    """The dependency direction must be teams/geo.py -> geo_ladder.py,
    never the reverse -- this is what lets a future `directory/`
    module depend on `geo_ladder` without touching `teams/` at all
    (see this module's own docstring and sprint.md's Design Rationale).
    """
    import ast
    import partner_scrape.geo_ladder as geo_ladder_module

    geo_ladder_path = Path(geo_ladder_module.__file__)
    tree = ast.parse(geo_ladder_path.read_text(), filename=str(geo_ladder_path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("partner_scrape.teams"):
                offenders.append(node.module)
        elif isinstance(node, ast.Import):
            offenders.extend(
                alias.name for alias in node.names if alias.name.startswith("partner_scrape.teams")
            )

    assert offenders == []

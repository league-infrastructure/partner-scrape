"""Tests for partner_scrape.directory.pipeline: `run_directory()`'s
registry -> source dispatch -> geo fallback/geocoding -> export
sequencing, for both Places (ticket 007) and Clubs (ticket 018-008).
"""

from __future__ import annotations

from pathlib import Path

from partner_scrape.directory.model import Club, Place
from partner_scrape.directory.pipeline import (
    DEFAULT_GEO_DATA_DIR,
    DEFAULT_PLACES_REGISTRY_DIR,
    _apply_club_geocoding,
    _apply_geo_fallback,
    run_directory,
)
from partner_scrape.fetch.fetcher import FetchResponse

# -- fixture geo data dir, mirroring tests/teams/test_geo.py's own
# "small, hand-authored fixture data directory" pattern rather than
# touching the real, committed directory/data/ files. -----------------

_PUBLIC_HEADER = "School\tDistrict\tCity\tZip\tWebSite\tLatitude\tLongitude\tStatusType\tVirtual\n"
_PRIVATE_HEADER = "School\tCity\tZip\tLatitude\tLongitude\tVintages\n"


def _write_centroids_toml(path: Path, entries: dict[str, tuple[float, float]]) -> None:
    lines = []
    for key, (lat, lon) in entries.items():
        lines.append(f'["{key}"]')
        lines.append(f"latitude = {lat}")
        lines.append(f"longitude = {lon}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_geo_data_dir(
    tmp_path: Path,
    *,
    zip_centroids: dict[str, tuple[float, float]] | None = None,
    city_centroids: dict[str, tuple[float, float]] | None = None,
    public_school_rows: list[tuple[str, ...]] | None = None,
    private_school_rows: list[tuple[str, ...]] | None = None,
    overrides_toml: str = "",
) -> Path:
    data_dir = tmp_path / "geo-data"
    data_dir.mkdir()
    public_lines = [_PUBLIC_HEADER.rstrip("\n")] + [
        "\t".join(row) for row in (public_school_rows or [])
    ]
    (data_dir / "sd-schools-public.tsv").write_text(
        "\n".join(public_lines) + "\n", encoding="utf-8"
    )
    private_lines = [_PRIVATE_HEADER.rstrip("\n")] + [
        "\t".join(row) for row in (private_school_rows or [])
    ]
    (data_dir / "sd-schools-private.tsv").write_text(
        "\n".join(private_lines) + "\n", encoding="utf-8"
    )
    (data_dir / "school-overrides.toml").write_text(overrides_toml, encoding="utf-8")
    _write_centroids_toml(data_dir / "zip-centroids.toml", zip_centroids or {})
    _write_centroids_toml(data_dir / "city-centroids.toml", city_centroids or {})
    return data_dir


class _NeverCalledFetcher:
    def get(self, url: str, headers=None) -> FetchResponse:
        raise AssertionError("must never call the injected Fetcher")


class TestApplyGeoFallback:
    def test_a_place_with_curated_coordinates_is_left_untouched(self, tmp_path):
        place = Place(
            place_id="x",
            name="X",
            category="makerspace",
            latitude=32.7,
            longitude=-117.1,
            location_precision="address",
            matched_name="X",
        )

        result = _apply_geo_fallback([place], data_dir=tmp_path / "unused-nonexistent")

        assert result[0].latitude == 32.7
        assert result[0].longitude == -117.1
        assert result[0].location_precision == "address"

    def test_geo_ladder_is_never_constructed_when_nothing_needs_fallback(self, tmp_path):
        # A nonexistent data_dir would make GeoLadder(...) raise --
        # this proves the ladder is never constructed at all when every
        # Place already carries a curated coordinate.
        place = Place(
            place_id="x",
            name="X",
            category="makerspace",
            latitude=1.0,
            longitude=2.0,
            location_precision="address",
        )

        result = _apply_geo_fallback([place], data_dir=tmp_path / "does-not-exist")

        assert result[0].location_precision == "address"

    def test_falls_back_to_zip_centroid_when_postal_code_matches(self, tmp_path):
        data_dir = _build_geo_data_dir(tmp_path, zip_centroids={"92154": (32.579101, -116.966528)})
        place = Place(place_id="x", name="X", category="makerspace", postal_code="92154")

        result = _apply_geo_fallback([place], data_dir=data_dir)

        assert result[0].latitude == 32.579101
        assert result[0].longitude == -116.966528
        assert result[0].location_precision == "zip"
        assert result[0].matched_name == "ZIP 92154 centroid"

    def test_falls_back_to_city_centroid_when_no_zip_match(self, tmp_path):
        data_dir = _build_geo_data_dir(tmp_path, city_centroids={"san diego": (32.7, -117.1)})
        place = Place(place_id="x", name="X", category="makerspace", city="San Diego")

        result = _apply_geo_fallback([place], data_dir=data_dir)

        assert result[0].latitude == 32.7
        assert result[0].longitude == -117.1
        assert result[0].location_precision == "city"
        assert result[0].matched_name == "San Diego (city centroid)"

    def test_zip_is_preferred_over_city_when_both_would_match(self, tmp_path):
        data_dir = _build_geo_data_dir(
            tmp_path,
            zip_centroids={"92154": (1.0, 2.0)},
            city_centroids={"san diego": (3.0, 4.0)},
        )
        place = Place(
            place_id="x", name="X", category="makerspace", postal_code="92154", city="San Diego"
        )

        result = _apply_geo_fallback([place], data_dir=data_dir)

        assert result[0].location_precision == "zip"

    def test_no_match_anywhere_leaves_none_never_a_guess(self, tmp_path):
        data_dir = _build_geo_data_dir(tmp_path)
        place = Place(place_id="x", name="X", category="makerspace", city="Nowhereville")

        result = _apply_geo_fallback([place], data_dir=data_dir)

        assert result[0].latitude is None
        assert result[0].longitude is None
        assert result[0].location_precision == "none"

    def test_default_geo_data_dir_points_at_directorys_own_data(self):
        assert DEFAULT_GEO_DATA_DIR.name == "data"
        assert DEFAULT_GEO_DATA_DIR.parent.name == "directory"


# -- fixture school rows for the Club-side geocoding tests below.
# `_apply_geo_fallback()` above never exercises the school-matching
# rungs 1-4 (Places don't route through them), so this is the first
# place in this test module a school row actually matters. ------------

_POWAY_HIGH_ROW = (
    "Poway High", "Poway Unified", "Poway", "92064",
    "www.powayusd.com/poway", "33.000000", "-117.000000", "Active", "N",
)
_HELIX_HIGH_ROW = (
    "Helix High", "Grossmont Union High", "La Mesa", "91941",
    "www.helixcharter.net", "32.755905", "-117.039810", "Active", "C",
)
_MATER_DEI_PRIVATE_ROW = (
    "Mater Dei Catholic High School", "Chula Vista", "91913",
    "32.621445", "-116.975624", "2023-24",
)


class TestApplyClubGeocoding:
    """`_apply_club_geocoding()` runs the shared `GeoLadder`'s *full*
    ladder (school rungs 1-4, then ZIP/city rungs 5-6, then the
    rung-7 "none") over `Club.host_school`/`city`/`postal_code` --
    unlike `_apply_geo_fallback()` above, which never touches the
    school rungs at all."""

    def test_exact_public_school_match_gets_school_precision_and_website(self, tmp_path):
        data_dir = _build_geo_data_dir(tmp_path, public_school_rows=[_POWAY_HIGH_ROW])
        club = Club(club_id="x", name="X", host_school="Poway High School", city="Poway")

        result = _apply_club_geocoding([club], data_dir=data_dir)

        assert result[0].location_precision == "school"
        assert result[0].latitude == 33.0
        assert result[0].longitude == -117.0
        assert result[0].matched_name == "Poway High"
        assert result[0].needs_review is False
        assert result[0].host_school_website == "www.powayusd.com/poway"

    def test_exact_private_school_match_gets_school_precision_and_no_website(self, tmp_path):
        # NCES's private-school data has no website column -- mirrors
        # geo_ladder.LocationMatch's own documented behavior.
        data_dir = _build_geo_data_dir(tmp_path, private_school_rows=[_MATER_DEI_PRIVATE_ROW])
        club = Club(
            club_id="x",
            name="X",
            host_school="Mater Dei Catholic High School",
            city="Chula Vista",
        )

        result = _apply_club_geocoding([club], data_dir=data_dir)

        assert result[0].location_precision == "school"
        assert result[0].host_school_website == ""

    def test_fuzzy_same_city_match_flags_needs_review(self, tmp_path):
        # "Helix Charter High School" vs. CDE's own "Helix High" --
        # same real-world case this ticket's real curated data hits
        # (see directory/DESIGN.md).
        data_dir = _build_geo_data_dir(tmp_path, public_school_rows=[_HELIX_HIGH_ROW])
        club = Club(
            club_id="x", name="X", host_school="Helix Charter High School", city="La Mesa"
        )

        result = _apply_club_geocoding([club], data_dir=data_dir)

        assert result[0].location_precision == "school"
        assert result[0].matched_name == "Helix High"
        assert result[0].needs_review is True

    def test_falls_back_to_zip_centroid_when_no_school_matches(self, tmp_path):
        data_dir = _build_geo_data_dir(
            tmp_path, zip_centroids={"92154": (32.579101, -116.966528)}
        )
        club = Club(club_id="x", name="X", host_school="Nonexistent School", postal_code="92154")

        result = _apply_club_geocoding([club], data_dir=data_dir)

        assert result[0].location_precision == "zip"
        assert result[0].latitude == 32.579101

    def test_falls_back_to_city_centroid_when_no_school_or_zip_matches(self, tmp_path):
        data_dir = _build_geo_data_dir(tmp_path, city_centroids={"san diego": (32.7, -117.1)})
        club = Club(club_id="x", name="X", host_school="Nonexistent School", city="San Diego")

        result = _apply_club_geocoding([club], data_dir=data_dir)

        assert result[0].location_precision == "city"

    def test_no_match_anywhere_leaves_none_never_a_guess(self, tmp_path):
        data_dir = _build_geo_data_dir(tmp_path)
        club = Club(club_id="x", name="X", host_school="Nowhere High", city="Nowhereville")

        result = _apply_club_geocoding([club], data_dir=data_dir)

        assert result[0].latitude is None
        assert result[0].longitude is None
        assert result[0].location_precision == "none"

    def test_geo_ladder_is_never_constructed_for_an_empty_club_list(self, tmp_path):
        # A nonexistent data_dir would make GeoLadder(...) raise -- this
        # proves the ladder is never constructed when there are no
        # Clubs to geocode at all (mirrors _apply_geo_fallback()'s own
        # equivalent test).
        result = _apply_club_geocoding([], data_dir=tmp_path / "does-not-exist")

        assert result == []


class TestRunDirectoryRealFixtureData:
    """Against the real, committed Place Registry and roster -- no
    fixture copy, matching this ticket's other "trust the real data"
    tests."""

    def test_dry_run_reports_19_places_with_no_network(self, tmp_path):
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        assert payload["meta"]["total"] == 19
        assert len(payload["places"]) == 19

    def test_default_places_registry_dir_is_directorys_own_registry(self):
        assert DEFAULT_PLACES_REGISTRY_DIR.name == "registry"
        assert DEFAULT_PLACES_REGISTRY_DIR.parent.name == "directory"

    def test_atlas_labs_resolves_via_the_real_zip_centroid_fallback(self, tmp_path):
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        atlas = next(p for p in payload["places"] if p["place_id"] == "atlas-labs")
        assert atlas["location_precision"] == "zip"
        assert atlas["latitude"] is not None
        assert atlas["longitude"] is not None

    def test_dry_run_reports_four_clubs_with_no_network(self, tmp_path):
        # Ticket 018-008's own AC: every Hack Club chapter issue 35
        # names has a Club record, geocoded through the real, now
        # populated directory/data/ school directories -- not a fixture
        # copy, the same "trust the real data" precedent this class
        # already applies to Places.
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        assert payload["clubs_meta"]["total"] == 4
        assert len(payload["clubs"]) == 4

    def test_every_real_hack_club_chapter_resolves_to_school_precision_never_a_guess(
        self, tmp_path
    ):
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        for club in payload["clubs"]:
            assert club["location_precision"] == "school", club["club_id"]
            assert club["latitude"] is not None
            assert club["longitude"] is not None
            assert club["matched_name"]

    def test_helix_charter_is_the_one_real_chapter_flagged_needs_review(self, tmp_path):
        # Real-world residue this ticket's curated host_school value
        # ("Helix Charter High School") genuinely hits: CDE's own
        # record is named "Helix High" -- a legitimate rung-3
        # same-city fuzzy match, not an exact one, so it is flagged
        # rather than silently trusted. See directory/DESIGN.md.
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        by_id = {c["club_id"]: c for c in payload["clubs"]}
        needing_review = {cid for cid, c in by_id.items() if c["needs_review"]}

        assert needing_review == {"hack-club-helix-charter-high"}

    def test_public_school_chapters_carry_the_matched_schools_own_website(self, tmp_path):
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        by_id = {c["club_id"]: c for c in payload["clubs"]}
        # University City High and La Jolla High are CDE public schools
        # with a WebSite column; Mater Dei Catholic is NCES private
        # (no website column at all).
        assert by_id["hack-club-university-city-high"]["host_school_website"]
        assert by_id["hack-club-la-jolla-high"]["host_school_website"]
        assert by_id["hack-club-mater-dei-catholic-high"]["host_school_website"] == ""


class TestSourceFilter:
    def test_source_filter_by_adapter_type_matches_the_real_registry(self, tmp_path):
        payload = run_directory(
            source="static_roster",
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            site_dir=tmp_path / "unused",
        )

        assert payload["meta"]["total"] == 19
        assert payload["clubs_meta"]["total"] == 0

    def test_club_source_filter_by_adapter_type_matches_the_real_registry(self, tmp_path):
        payload = run_directory(
            source="hack_club_static_roster",
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            site_dir=tmp_path / "unused",
        )

        assert payload["clubs_meta"]["total"] == 4
        assert payload["meta"]["total"] == 0

    def test_source_filter_for_an_unregistered_adapter_type_yields_nothing(self, tmp_path):
        payload = run_directory(
            source="nonexistent-adapter",
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            site_dir=tmp_path / "unused",
        )

        assert payload["meta"]["total"] == 0
        assert payload["clubs_meta"]["total"] == 0


class _BoomingSource:
    def discover(self, source, fetcher):
        raise RuntimeError("boom")


class TestPerSourceErrorIsolation:
    """Mirrors teams.pipeline.run_teams()'s own per-source isolation
    convention: one broken source is logged and skipped, never fatal to
    the rest of the run."""

    def test_a_source_whose_adapter_type_has_no_registered_place_source_is_skipped(
        self, tmp_path, caplog
    ):
        registry_dir = tmp_path / "registry"
        registry_dir.mkdir()
        (registry_dir / "unknown.toml").write_text(
            'org_name = "Unknown"\nadapter_type = "totally-unregistered"\nenabled = true\n'
            "[config]\n",
            encoding="utf-8",
        )

        payload = run_directory(
            registry_dir=registry_dir,
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            site_dir=tmp_path / "unused",
        )

        assert payload["meta"]["total"] == 0

    def test_a_raising_source_is_logged_and_skipped_not_fatal(self, tmp_path, monkeypatch):
        import partner_scrape.directory.pipeline as pipeline_module

        monkeypatch.setitem(pipeline_module._PLACE_SOURCES, "static_roster", _BoomingSource())

        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        assert payload["meta"]["total"] == 0

    def test_a_raising_club_source_is_logged_and_skipped_not_fatal(self, tmp_path, monkeypatch):
        import partner_scrape.directory.pipeline as pipeline_module

        monkeypatch.setitem(
            pipeline_module._CLUB_SOURCES, "hack_club_static_roster", _BoomingSource()
        )

        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        assert payload["clubs_meta"]["total"] == 0
        # The unrelated Place source is unaffected -- per-source
        # isolation, not "one broken source kills the whole run".
        assert payload["meta"]["total"] == 19

    def test_a_raising_place_source_does_not_affect_club_processing(self, tmp_path, monkeypatch):
        import partner_scrape.directory.pipeline as pipeline_module

        monkeypatch.setitem(pipeline_module._PLACE_SOURCES, "static_roster", _BoomingSource())

        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        assert payload["meta"]["total"] == 0
        assert payload["clubs_meta"]["total"] == 4

    def test_combined_dispatch_never_logs_a_spurious_place_warning_for_a_real_club_entry(
        self, caplog
    ):
        # Regression guard for the "one combined loop, not two separate
        # ones" design decision (see pipeline.py's own module
        # docstring): a real Club registry entry (adapter_type
        # "hack_club_static_roster") must never trip the Place branch's
        # "no PlaceSource registered" warning.
        import logging

        with caplog.at_level(logging.WARNING):
            run_directory(fetcher=_NeverCalledFetcher(), dry_run=True, site_dir="unused")

        assert not any(
            "no placesource registered" in record.message.lower() for record in caplog.records
        )

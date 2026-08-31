"""Tests for partner_scrape.directory.pipeline: `run_directory()`'s
registry -> source dispatch -> geo fallback -> export sequencing.
"""

from __future__ import annotations

from pathlib import Path

from partner_scrape.directory.model import Place
from partner_scrape.directory.pipeline import (
    DEFAULT_GEO_DATA_DIR,
    DEFAULT_PLACES_REGISTRY_DIR,
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
) -> Path:
    data_dir = tmp_path / "geo-data"
    data_dir.mkdir()
    (data_dir / "sd-schools-public.tsv").write_text(_PUBLIC_HEADER, encoding="utf-8")
    (data_dir / "sd-schools-private.tsv").write_text(_PRIVATE_HEADER, encoding="utf-8")
    (data_dir / "school-overrides.toml").write_text("", encoding="utf-8")
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


class TestSourceFilter:
    def test_source_filter_by_adapter_type_matches_the_real_registry(self, tmp_path):
        payload = run_directory(
            source="static_roster",
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            site_dir=tmp_path / "unused",
        )

        assert payload["meta"]["total"] == 19

    def test_source_filter_for_an_unregistered_adapter_type_yields_nothing(self, tmp_path):
        payload = run_directory(
            source="nonexistent-adapter",
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            site_dir=tmp_path / "unused",
        )

        assert payload["meta"]["total"] == 0


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

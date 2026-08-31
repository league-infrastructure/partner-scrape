"""Tests for partner_scrape.directory.sources.static_roster: the Places
static-roster PlaceSource.

Like `tests/teams/test_sources_static_roster.py`'s own precedent, most
of this module drives `StaticRosterSource` against the **real,
committed roster** (`partner_scrape/directory/data/places.toml`,
exposed here as `DEFAULT_ROSTER_PATH`) rather than a copied-in fixture
-- this *is* the file, not a copy that could silently drift from it.
`places_malformed.toml` under `tests/fixtures/directory/` is
hand-authored (the real roster has no malformed entries) to exercise
per-entry error isolation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from partner_scrape.directory.model import VALID_CATEGORIES
from partner_scrape.directory.sources.base import RawPlaceResponse, PlaceRef, run
from partner_scrape.directory.sources.static_roster import (
    DEFAULT_DATA_DIR,
    DEFAULT_ROSTER_PATH,
    StaticRosterSource,
    _extract_one,
)
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.loader import load_active_sources
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "directory"
DIRECTORY_REGISTRY_DIR = (
    Path(__file__).resolve().parents[2] / "partner_scrape" / "directory" / "registry"
)


def _real_source_config() -> SourceConfig:
    sources = load_active_sources(DIRECTORY_REGISTRY_DIR)
    matches = [s for s in sources if s.adapter_type == "static_roster"]
    assert len(matches) == 1, "expected exactly one static_roster registry entry"
    return matches[0]


class _NeverCalledFetcher:
    """`Fetcher` double that raises on any call -- proves
    `StaticRosterSource` never touches it, exercised through the full
    `sources.base.run()` chain, matching
    `teams/sources/static_roster.py`'s own test precedent."""

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        raise AssertionError("StaticRosterSource must never call the injected Fetcher")


class TestNeverTouchesFetcher:
    def test_run_never_calls_fetcher_get(self):
        places = run(_real_source_config(), StaticRosterSource(), _NeverCalledFetcher())
        assert len(places) == 19


class TestDiscover:
    def test_discover_returns_a_local_path_not_a_url(self):
        refs = StaticRosterSource().discover(_real_source_config(), _NeverCalledFetcher())

        assert len(refs) == 1
        assert refs[0].url == str(DEFAULT_ROSTER_PATH)
        assert not refs[0].url.startswith("http")

    def test_discover_falls_back_to_default_roster_path_when_config_omits_it(self):
        source = SourceConfig(
            source_id="places-sd",
            org_name="Places",
            adapter_type="static_roster",
            config={},
        )

        refs = StaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(DEFAULT_ROSTER_PATH)

    def test_discover_resolves_a_relative_roster_path_against_data_dir(self):
        source = SourceConfig(
            source_id="places-sd",
            org_name="Places",
            adapter_type="static_roster",
            config={"roster_path": "places.toml"},
        )

        refs = StaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(DEFAULT_DATA_DIR / "places.toml")

    def test_discover_leaves_an_absolute_roster_path_untouched(self, tmp_path):
        absolute = tmp_path / "custom-roster.toml"
        source = SourceConfig(
            source_id="places-sd",
            org_name="Places",
            adapter_type="static_roster",
            config={"roster_path": str(absolute)},
        )

        refs = StaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(absolute)


class TestFetch:
    def test_fetch_reads_the_file_directly_ignoring_fetcher(self):
        ref = PlaceRef(url=str(DEFAULT_ROSTER_PATH))

        raw = StaticRosterSource().fetch(ref, _NeverCalledFetcher())

        assert raw.status == 200
        assert "sdpl-idea-lab-central" in raw.body

    def test_fetch_raises_for_a_missing_file(self, tmp_path):
        ref = PlaceRef(url=str(tmp_path / "does-not-exist.toml"))

        with pytest.raises(OSError):
            StaticRosterSource().fetch(ref, _NeverCalledFetcher())


class TestExtractAgainstTheRealRoster:
    """Drives extract() against the real, committed 19-place roster (via
    the full sources.base.run() chain)."""

    def _real_places(self):
        return run(_real_source_config(), StaticRosterSource(), _NeverCalledFetcher())

    def test_extracts_exactly_19_places(self):
        assert len(self._real_places()) == 19

    def test_every_category_named_in_issue_35_has_at_least_one_entry(self):
        places = self._real_places()
        categories = {p.category for p in places}

        assert categories == VALID_CATEGORIES

    def test_place_ids_are_unique(self):
        ids = [p.place_id for p in self._real_places()]

        assert len(ids) == len(set(ids))

    def test_sources_field_records_static_roster_provenance(self):
        for place in self._real_places():
            assert place.sources == ["static_roster"]

    def test_every_curated_coordinate_gets_address_precision(self):
        for place in self._real_places():
            if place.latitude is not None:
                assert place.location_precision == "address"
                assert place.matched_name == place.name
                assert place.needs_review is False

    def test_atlas_labs_is_marked_opening_not_open(self):
        by_id = {p.place_id: p for p in self._real_places()}

        atlas = by_id["atlas-labs"]

        assert atlas.status == "opening"
        assert "2027" in atlas.status_note
        # Not yet geocoded by this source -- directory.pipeline's own
        # zip-fallback stage resolves it (see tests/directory/
        # test_pipeline.py), not the static roster source itself.
        assert atlas.latitude is None
        assert atlas.longitude is None
        assert atlas.location_precision == "none"

    def test_every_other_place_has_open_status_and_no_status_note(self):
        for place in self._real_places():
            if place.place_id == "atlas-labs":
                continue
            assert place.status == "open"
            assert place.status_note == ""

    def test_no_source_ever_calls_a_live_geocoder(self):
        # Structural proxy for "never live-geocoded": every extracted
        # Place's coordinates are either the roster's own curated
        # values (location_precision == "address") or entirely absent
        # (location_precision == "none", left for the pipeline's
        # offline fallback) -- never any other precision value, which
        # only directory.pipeline._apply_geo_fallback ever sets.
        for place in self._real_places():
            assert place.location_precision in {"address", "none"}


class TestMalformedEntryIsolation:
    """`places_malformed.toml` (hand-authored -- the real roster has no
    malformed entries) carries several broken entries plus one good
    entry, matching `fll_roster_malformed.tsv`'s per-record isolation
    precedent."""

    def test_malformed_entries_are_skipped_and_logged_not_raised(self, caplog):
        body = (FIXTURES_DIR / "places_malformed.toml").read_text()
        ref = PlaceRef(url="places_malformed.toml")
        raw = RawPlaceResponse(ref=ref, status=200, body=body)

        places = StaticRosterSource().extract(raw, _real_source_config())

        assert len(places) == 1
        assert places[0].place_id == "good-place"
        assert places[0].name == "Good Place"


class TestExtractOne:
    def test_missing_place_id_raises_value_error(self):
        with pytest.raises(ValueError, match="no usable place_id or name"):
            _extract_one({"name": "Some Place", "category": "makerspace"})

    def test_missing_name_raises_value_error(self):
        with pytest.raises(ValueError, match="no usable place_id or name"):
            _extract_one({"place_id": "some-place", "category": "makerspace"})

    def test_unrecognized_category_raises_value_error(self):
        with pytest.raises(ValueError, match="unrecognized category"):
            _extract_one(
                {"place_id": "x", "name": "X", "category": "science-museum"}
            )

    def test_unrecognized_status_raises_value_error(self):
        with pytest.raises(ValueError, match="unrecognized status"):
            _extract_one(
                {
                    "place_id": "x",
                    "name": "X",
                    "category": "makerspace",
                    "status": "coming-soon",
                }
            )

    def test_non_open_status_without_a_status_note_raises_value_error(self):
        with pytest.raises(ValueError, match="status_note"):
            _extract_one(
                {
                    "place_id": "x",
                    "name": "X",
                    "category": "makerspace",
                    "status": "opening",
                }
            )

    def test_curated_coordinates_are_parsed_as_floats(self):
        place = _extract_one(
            {
                "place_id": "x",
                "name": "X",
                "category": "makerspace",
                "latitude": 32.5,
                "longitude": -117.0,
            }
        )

        assert place.latitude == 32.5
        assert place.longitude == -117.0
        assert place.location_precision == "address"

    def test_missing_coordinates_leave_location_precision_none(self):
        place = _extract_one({"place_id": "x", "name": "X", "category": "makerspace"})

        assert place.latitude is None
        assert place.longitude is None
        assert place.location_precision == "none"

    def test_related_partner_id_is_parsed_as_int_when_present(self):
        place = _extract_one(
            {
                "place_id": "x",
                "name": "X",
                "category": "makerspace",
                "related_partner_id": 121,
            }
        )

        assert place.related_partner_id == 121

    def test_related_partner_id_defaults_to_none(self):
        place = _extract_one({"place_id": "x", "name": "X", "category": "makerspace"})

        assert place.related_partner_id is None


class TestMalformedWholeFileFailsLoudly:
    def test_unparseable_toml_raises_value_error(self):
        ref = PlaceRef(url="broken.toml")
        raw = RawPlaceResponse(ref=ref, status=200, body="this is not [ valid toml")

        with pytest.raises(ValueError, match="Malformed places roster TOML"):
            StaticRosterSource().extract(raw, _real_source_config())


class TestRegistryConfig:
    """AC: partner_scrape/directory/registry/places-sd.toml registers
    the static_roster source, reusing registry.schema.SourceConfig /
    registry.loader.load_active_sources verbatim (no new schema)."""

    def test_places_sd_toml_loads_via_load_active_sources(self):
        source = _real_source_config()

        assert source.source_id == "places-sd"
        assert source.adapter_type == "static_roster"
        assert source.enabled is True

    def test_loaded_source_config_drives_discover_to_the_real_roster_file(self):
        source = _real_source_config()

        refs = StaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs == [PlaceRef(url=str(DEFAULT_ROSTER_PATH))]

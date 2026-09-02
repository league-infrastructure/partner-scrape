"""Tests for partner_scrape.directory.sources.offering_static_roster:
the Offerings static-roster OfferingSource (sprint 030, ticket 001).

Like `tests/directory/test_sources_static_roster.py`'s own precedent,
most of this module drives `OfferingStaticRosterSource` against the
**real, committed roster** (`partner_scrape/directory/data/
offerings.toml`, exposed here as `DEFAULT_ROSTER_PATH`) rather than a
copied-in fixture -- this *is* the file, not a copy that could silently
drift from it. As of ticket 002 (issue 14 Strategy B), the real roster
carries six curated `"volunteer"` rows plus ticket 001's original
`"free_program"` placeholder row (seven total) -- ticket 003 replaces
that placeholder with seven real `"free_program"` rows (thirteen
total); `offerings_malformed.toml` under `tests/fixtures/directory/` is
hand-authored to exercise per-entry error isolation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from partner_scrape.directory.model import VALID_OFFERING_TYPES
from partner_scrape.directory.sources.base import OfferingRef, RawOfferingResponse, run_offering_source
from partner_scrape.directory.sources.offering_static_roster import (
    DEFAULT_DATA_DIR,
    DEFAULT_ROSTER_PATH,
    OfferingStaticRosterSource,
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
    matches = [s for s in sources if s.adapter_type == "offering_static_roster"]
    assert len(matches) == 1, "expected exactly one offering_static_roster registry entry"
    return matches[0]


class _NeverCalledFetcher:
    """`Fetcher` double that raises on any call -- proves
    `OfferingStaticRosterSource` never touches it, exercised through
    the full `sources.base.run_offering_source()` chain, matching
    `sources/static_roster.py`'s own test precedent."""

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        raise AssertionError(
            "OfferingStaticRosterSource must never call the injected Fetcher"
        )


class TestNeverTouchesFetcher:
    def test_run_never_calls_fetcher_get(self):
        offerings = run_offering_source(
            _real_source_config(), OfferingStaticRosterSource(), _NeverCalledFetcher()
        )
        assert len(offerings) == 7


class TestDiscover:
    def test_discover_returns_a_local_path_not_a_url(self):
        refs = OfferingStaticRosterSource().discover(_real_source_config(), _NeverCalledFetcher())

        assert len(refs) == 1
        assert refs[0].url == str(DEFAULT_ROSTER_PATH)
        assert not refs[0].url.startswith("http")

    def test_discover_falls_back_to_default_roster_path_when_config_omits_it(self):
        source = SourceConfig(
            source_id="offerings-sd",
            org_name="Offerings",
            adapter_type="offering_static_roster",
            config={},
        )

        refs = OfferingStaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(DEFAULT_ROSTER_PATH)

    def test_discover_resolves_a_relative_roster_path_against_data_dir(self):
        source = SourceConfig(
            source_id="offerings-sd",
            org_name="Offerings",
            adapter_type="offering_static_roster",
            config={"roster_path": "offerings.toml"},
        )

        refs = OfferingStaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(DEFAULT_DATA_DIR / "offerings.toml")

    def test_discover_leaves_an_absolute_roster_path_untouched(self, tmp_path):
        absolute = tmp_path / "custom-roster.toml"
        source = SourceConfig(
            source_id="offerings-sd",
            org_name="Offerings",
            adapter_type="offering_static_roster",
            config={"roster_path": str(absolute)},
        )

        refs = OfferingStaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(absolute)


class TestFetch:
    def test_fetch_reads_the_file_directly_ignoring_fetcher(self):
        ref = OfferingRef(url=str(DEFAULT_ROSTER_PATH))

        raw = OfferingStaticRosterSource().fetch(ref, _NeverCalledFetcher())

        assert raw.status == 200
        assert "offering" in raw.body

    def test_fetch_raises_for_a_missing_file(self, tmp_path):
        ref = OfferingRef(url=str(tmp_path / "does-not-exist.toml"))

        with pytest.raises(OSError):
            OfferingStaticRosterSource().fetch(ref, _NeverCalledFetcher())


class TestExtractAgainstTheRealRoster:
    """Drives extract() against the real, committed two-row placeholder
    roster (via the full sources.base.run_offering_source() chain)."""

    def _real_offerings(self):
        return run_offering_source(
            _real_source_config(), OfferingStaticRosterSource(), _NeverCalledFetcher()
        )

    def test_extracts_exactly_seven_offerings(self):
        assert len(self._real_offerings()) == 7

    def test_both_offering_types_are_represented(self):
        offerings = self._real_offerings()
        types = {o.offering_type for o in offerings}

        assert types == VALID_OFFERING_TYPES

    def test_offering_ids_are_unique(self):
        ids = [o.offering_id for o in self._real_offerings()]

        assert len(ids) == len(set(ids))

    def test_sources_field_records_offering_static_roster_provenance(self):
        for offering in self._real_offerings():
            assert offering.sources == ["offering_static_roster"]

    def test_volunteer_row_has_an_age_minimum(self):
        by_id = {o.offering_id: o for o in self._real_offerings()}
        volunteer = next(o for o in by_id.values() if o.offering_type == "volunteer")

        assert volunteer.age_minimum is not None
        assert isinstance(volunteer.age_minimum, int)

    def test_free_program_row_has_no_age_minimum(self):
        free_program = next(
            o for o in self._real_offerings() if o.offering_type == "free_program"
        )

        assert free_program.age_minimum is None

    def test_no_source_ever_touches_a_geocoder_or_carries_location_fields(self):
        # Structural proxy for "Offering has no location fields at
        # all" -- there is no latitude/longitude/location_precision
        # attribute to even inspect.
        for offering in self._real_offerings():
            assert not hasattr(offering, "latitude")
            assert not hasattr(offering, "longitude")


class TestMalformedEntryIsolation:
    """`offerings_malformed.toml` (hand-authored -- the real roster has
    no malformed entries) carries several broken entries plus one good
    entry, matching `places_malformed.toml`'s per-record isolation
    precedent."""

    def test_malformed_entries_are_skipped_and_logged_not_raised(self, caplog):
        body = (FIXTURES_DIR / "offerings_malformed.toml").read_text()
        ref = OfferingRef(url="offerings_malformed.toml")
        raw = RawOfferingResponse(ref=ref, status=200, body=body)

        offerings = OfferingStaticRosterSource().extract(raw, _real_source_config())

        assert len(offerings) == 1
        assert offerings[0].offering_id == "good-offering"
        assert offerings[0].title == "Good Offering"


class TestExtractOne:
    def test_missing_offering_id_raises_value_error(self):
        with pytest.raises(ValueError, match="no usable offering_id"):
            _extract_one({"org_name": "Some Org", "title": "Some Title", "offering_type": "volunteer"})

    def test_missing_org_name_raises_value_error(self):
        with pytest.raises(ValueError, match="no usable offering_id"):
            _extract_one({"offering_id": "x", "title": "Some Title", "offering_type": "volunteer"})

    def test_missing_title_raises_value_error(self):
        with pytest.raises(ValueError, match="no usable offering_id"):
            _extract_one({"offering_id": "x", "org_name": "Some Org", "offering_type": "volunteer"})

    def test_unrecognized_offering_type_raises_value_error(self):
        with pytest.raises(ValueError, match="unrecognized offering_type"):
            _extract_one(
                {
                    "offering_id": "x",
                    "org_name": "Org",
                    "title": "Title",
                    "offering_type": "internship",
                }
            )

    def test_unrecognized_status_raises_value_error(self):
        with pytest.raises(ValueError, match="unrecognized status"):
            _extract_one(
                {
                    "offering_id": "x",
                    "org_name": "Org",
                    "title": "Title",
                    "offering_type": "volunteer",
                    "status": "pending",
                }
            )

    def test_non_active_status_without_a_status_note_raises_value_error(self):
        with pytest.raises(ValueError, match="status_note"):
            _extract_one(
                {
                    "offering_id": "x",
                    "org_name": "Org",
                    "title": "Title",
                    "offering_type": "volunteer",
                    "status": "closed",
                }
            )

    def test_age_minimum_is_parsed_as_int_when_present(self):
        offering = _extract_one(
            {
                "offering_id": "x",
                "org_name": "Org",
                "title": "Title",
                "offering_type": "volunteer",
                "age_minimum": 18,
            }
        )

        assert offering.age_minimum == 18

    def test_age_minimum_defaults_to_none(self):
        offering = _extract_one(
            {
                "offering_id": "x",
                "org_name": "Org",
                "title": "Title",
                "offering_type": "free_program",
            }
        )

        assert offering.age_minimum is None

    def test_related_partner_id_is_parsed_as_int_when_present(self):
        offering = _extract_one(
            {
                "offering_id": "x",
                "org_name": "Org",
                "title": "Title",
                "offering_type": "volunteer",
                "related_partner_id": 121,
            }
        )

        assert offering.related_partner_id == 121

    def test_related_partner_id_defaults_to_none(self):
        offering = _extract_one(
            {
                "offering_id": "x",
                "org_name": "Org",
                "title": "Title",
                "offering_type": "volunteer",
            }
        )

        assert offering.related_partner_id is None


class TestMalformedWholeFileFailsLoudly:
    def test_unparseable_toml_raises_value_error(self):
        ref = OfferingRef(url="broken.toml")
        raw = RawOfferingResponse(ref=ref, status=200, body="this is not [ valid toml")

        with pytest.raises(ValueError, match="Malformed offerings roster TOML"):
            OfferingStaticRosterSource().extract(raw, _real_source_config())


class TestRegistryConfig:
    """AC: partner_scrape/directory/registry/offerings-sd.toml registers
    the offering_static_roster source, reusing registry.schema.SourceConfig
    / registry.loader.load_active_sources verbatim (no new schema)."""

    def test_offerings_sd_toml_loads_via_load_active_sources(self):
        source = _real_source_config()

        assert source.source_id == "offerings-sd"
        assert source.adapter_type == "offering_static_roster"
        assert source.enabled is True

    def test_loaded_source_config_drives_discover_to_the_real_roster_file(self):
        source = _real_source_config()

        refs = OfferingStaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs == [OfferingRef(url=str(DEFAULT_ROSTER_PATH))]

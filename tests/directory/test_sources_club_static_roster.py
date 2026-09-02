"""Tests for partner_scrape.directory.sources.hack_club_static_roster:
the Hack Club chapters static-roster ClubSource (ticket 018-008).

Like `tests/directory/test_sources_static_roster.py`'s own precedent,
most of this module drives `HackClubStaticRosterSource` against the
**real, committed roster** (`partner_scrape/directory/data/
hack-club-sd.tsv`, exposed here as `DEFAULT_ROSTER_PATH`) rather than a
copied-in fixture -- this *is* the file, not a copy that could silently
drift from it. `hack_club_malformed.tsv` under `tests/fixtures/
directory/` is hand-authored (the real roster has no malformed entries)
to exercise per-record error isolation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from partner_scrape.directory.model import VALID_CLUB_TYPES
from partner_scrape.directory.sources.base import ClubRef, RawClubResponse, run_club_source
from partner_scrape.directory.sources.hack_club_static_roster import (
    DEFAULT_DATA_DIR,
    DEFAULT_ROSTER_PATH,
    HackClubStaticRosterSource,
    _extract_one,
)
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.loader import load_active_sources
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "directory"
DIRECTORY_REGISTRY_DIR = (
    Path(__file__).resolve().parents[2] / "partner_scrape" / "directory" / "registry"
)

_HACK_CLUB_HOST_SCHOOLS = {
    "University City High School",
    "La Jolla High School",
    "Helix Charter High School",
    "Mater Dei Catholic High School",
}


def _real_source_config() -> SourceConfig:
    sources = load_active_sources(DIRECTORY_REGISTRY_DIR)
    matches = [s for s in sources if s.adapter_type == "hack_club_static_roster"]
    assert len(matches) == 1, "expected exactly one hack_club_static_roster registry entry"
    return matches[0]


class _NeverCalledFetcher:
    """`Fetcher` double that raises on any call -- proves
    `HackClubStaticRosterSource` never touches it, exercised through
    the full `sources.base.run_club_source()` chain, matching
    `teams/sources/static_roster.py`'s own test precedent."""

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        raise AssertionError(
            "HackClubStaticRosterSource must never call the injected Fetcher"
        )


class TestNeverTouchesFetcher:
    def test_run_club_source_never_calls_fetcher_get(self):
        clubs = run_club_source(
            _real_source_config(), HackClubStaticRosterSource(), _NeverCalledFetcher()
        )
        assert len(clubs) == 4


class TestDiscover:
    def test_discover_returns_a_local_path_not_a_url(self):
        refs = HackClubStaticRosterSource().discover(_real_source_config(), _NeverCalledFetcher())

        assert len(refs) == 1
        assert refs[0].url == str(DEFAULT_ROSTER_PATH)
        assert not refs[0].url.startswith("http")

    def test_discover_falls_back_to_default_roster_path_when_config_omits_it(self):
        source = SourceConfig(
            source_id="hack-club-sd",
            org_name="Hack Club",
            adapter_type="hack_club_static_roster",
            config={},
        )

        refs = HackClubStaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(DEFAULT_ROSTER_PATH)

    def test_discover_resolves_a_relative_roster_path_against_data_dir(self):
        source = SourceConfig(
            source_id="hack-club-sd",
            org_name="Hack Club",
            adapter_type="hack_club_static_roster",
            config={"roster_path": "hack-club-sd.tsv"},
        )

        refs = HackClubStaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(DEFAULT_DATA_DIR / "hack-club-sd.tsv")

    def test_discover_leaves_an_absolute_roster_path_untouched(self, tmp_path):
        absolute = tmp_path / "custom-roster.tsv"
        source = SourceConfig(
            source_id="hack-club-sd",
            org_name="Hack Club",
            adapter_type="hack_club_static_roster",
            config={"roster_path": str(absolute)},
        )

        refs = HackClubStaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs[0].url == str(absolute)


class TestFetch:
    def test_fetch_reads_the_file_directly_ignoring_fetcher(self):
        ref = ClubRef(url=str(DEFAULT_ROSTER_PATH))

        raw = HackClubStaticRosterSource().fetch(ref, _NeverCalledFetcher())

        assert raw.status == 200
        assert "hack-club-university-city-high" in raw.body

    def test_fetch_raises_for_a_missing_file(self, tmp_path):
        ref = ClubRef(url=str(tmp_path / "does-not-exist.tsv"))

        with pytest.raises(OSError):
            HackClubStaticRosterSource().fetch(ref, _NeverCalledFetcher())


class TestExtractAgainstTheRealRoster:
    """Drives extract() against the real, committed 4-chapter roster
    (via the full sources.base.run_club_source() chain). This is the
    ticket's own acceptance criterion: every Hack Club chapter issue 35
    names (University City HS, La Jolla HS, Helix Charter, Mater Dei
    Catholic) has a Club record."""

    def _real_clubs(self):
        return run_club_source(
            _real_source_config(), HackClubStaticRosterSource(), _NeverCalledFetcher()
        )

    def test_extracts_exactly_four_clubs(self):
        assert len(self._real_clubs()) == 4

    def test_every_chapter_issue_35_names_is_present_by_host_school(self):
        clubs = self._real_clubs()
        host_schools = {c.host_school for c in clubs}

        assert host_schools == _HACK_CLUB_HOST_SCHOOLS

    def test_club_ids_are_unique(self):
        ids = [c.club_id for c in self._real_clubs()]

        assert len(ids) == len(set(ids))

    def test_every_club_type_is_hack_club(self):
        for club in self._real_clubs():
            assert club.club_type == "hack-club"
        assert {c.club_type for c in self._real_clubs()} == VALID_CLUB_TYPES

    def test_sources_field_records_hack_club_static_roster_provenance(self):
        for club in self._real_clubs():
            assert club.sources == ["hack_club_static_roster"]

    def test_every_club_is_active_with_no_status_note(self):
        for club in self._real_clubs():
            assert club.status == "active"
            assert club.status_note == ""

    def test_this_source_never_geocodes(self):
        # Structural proxy for "acquisition never geocodes" (mirrors
        # sources/static_roster.py's own equivalent test): every
        # extracted Club is left at the honest not-yet-geocoded
        # defaults -- directory.pipeline._apply_club_geocoding() is the
        # only stage that ever sets these (see tests/directory/
        # test_pipeline.py).
        for club in self._real_clubs():
            assert club.latitude is None
            assert club.longitude is None
            assert club.location_precision == "none"
            assert club.matched_name == ""
            assert club.needs_review is False
            assert club.host_school_website == ""


class TestMalformedEntryIsolation:
    """`hack_club_malformed.tsv` (hand-authored -- the real roster has
    no malformed entries) carries five broken rows plus one good row,
    matching `places_malformed.toml`'s / `fll_roster_malformed.tsv`'s
    per-record isolation precedent."""

    def test_malformed_rows_are_skipped_and_logged_not_raised(self, caplog):
        body = (FIXTURES_DIR / "hack_club_malformed.tsv").read_text()
        ref = ClubRef(url="hack_club_malformed.tsv")
        raw = RawClubResponse(ref=ref, status=200, body=body)

        clubs = HackClubStaticRosterSource().extract(raw, _real_source_config())

        assert len(clubs) == 1
        assert clubs[0].club_id == "hack-club-good-club"
        assert clubs[0].name == "Good Club"


class TestExtractOne:
    def test_missing_club_id_raises_value_error(self):
        with pytest.raises(ValueError, match="no usable club_id or name"):
            _extract_one({"name": "X", "club_type": "hack-club"})

    def test_missing_name_raises_value_error(self):
        with pytest.raises(ValueError, match="no usable club_id or name"):
            _extract_one({"club_id": "x", "club_type": "hack-club"})

    def test_unrecognized_club_type_raises_value_error(self):
        with pytest.raises(ValueError, match="unrecognized club_type"):
            _extract_one({"club_id": "x", "name": "X", "club_type": "robotics-club"})

    def test_unrecognized_status_raises_value_error(self):
        with pytest.raises(ValueError, match="unrecognized status"):
            _extract_one(
                {"club_id": "x", "name": "X", "club_type": "hack-club", "status": "retired"}
            )

    def test_non_active_status_without_a_status_note_raises_value_error(self):
        with pytest.raises(ValueError, match="status_note"):
            _extract_one(
                {"club_id": "x", "name": "X", "club_type": "hack-club", "status": "inactive"}
            )

    def test_defaults_to_active_status_when_omitted(self):
        club = _extract_one({"club_id": "x", "name": "X", "club_type": "hack-club"})

        assert club.status == "active"
        assert club.status_note == ""

    def test_host_school_city_and_postal_code_are_carried_through(self):
        club = _extract_one(
            {
                "club_id": "x",
                "name": "X",
                "club_type": "hack-club",
                "host_school": "Some High School",
                "city": "San Diego",
                "postal_code": "92101",
            }
        )

        assert club.host_school == "Some High School"
        assert club.city == "San Diego"
        assert club.postal_code == "92101"

    def test_never_sets_geocoding_fields(self):
        # Mirrors sources/static_roster.py's own "acquisition never
        # geocodes" convention -- _extract_one() has no lat/lon/
        # precision fields to set at all, structurally.
        club = _extract_one({"club_id": "x", "name": "X", "club_type": "hack-club"})

        assert club.latitude is None
        assert club.longitude is None
        assert club.location_precision == "none"


class TestRegistryConfig:
    """AC: partner_scrape/directory/registry/hack-club-sd.toml
    registers the hack_club_static_roster source, reusing
    registry.schema.SourceConfig / registry.loader.load_active_sources
    verbatim (no new schema)."""

    def test_hack_club_sd_toml_loads_via_load_active_sources(self):
        source = _real_source_config()

        assert source.source_id == "hack-club-sd"
        assert source.adapter_type == "hack_club_static_roster"
        assert source.enabled is True

    def test_loaded_source_config_drives_discover_to_the_real_roster_file(self):
        source = _real_source_config()

        refs = HackClubStaticRosterSource().discover(source, _NeverCalledFetcher())

        assert refs == [ClubRef(url=str(DEFAULT_ROSTER_PATH))]

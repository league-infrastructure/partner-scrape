"""Tests for partner_scrape.directory.pipeline: `run_directory()`'s
registry -> source dispatch -> geo fallback/geocoding -> export
sequencing, for both Places (ticket 007) and Clubs (ticket 018-008).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from partner_scrape.directory.model import Club, Offering, Place
from partner_scrape.directory.pipeline import (
    DEFAULT_GEO_DATA_DIR,
    DEFAULT_PLACES_REGISTRY_DIR,
    _apply_club_geocoding,
    _apply_geo_fallback,
    run_directory,
)
from partner_scrape.directory.sources.base import OfferingRef, PlaceRef, RawOfferingResponse, RawPlaceResponse
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.validate_roster import RosterValidationError

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


# -- ticket 004 (issue 48): real-data tests below now dispatch through
# the real static_roster source, whose real, committed places.toml
# carries 17 related_partner_id references (see this ticket's Notes).
# run_directory() now validates those references before export, so any
# test exercising the real registry against a fake site_dir needs a
# partners.json fixture with a matching `id` for each one. Parsed
# straight out of the real places.toml text rather than hand-listed, so
# this fixture can never drift from the data it stands in for -- and
# never a duplicate committed copy of the real partners.json itself
# (sprint.md Scope > Out of Scope). Sprint 030 tickets 002/003 extend
# this to also parse offerings.toml's own related_partner_id references
# (six from ticket 002's curated volunteer org profiles, seven more from
# ticket 003's curated free/Title I school-program rows) --
# _check_related_partner_references() joins Place and Offering
# references in one combined check, so a fixture built from places.toml
# alone now under-covers a real, unfiltered run_directory() call. -----


def _real_related_partner_ids() -> list[int]:
    places_text = (DEFAULT_GEO_DATA_DIR / "places.toml").read_text(encoding="utf-8")
    offerings_text = (DEFAULT_GEO_DATA_DIR / "offerings.toml").read_text(encoding="utf-8")
    ids = {int(m) for m in re.findall(r"related_partner_id\s*=\s*(\d+)", places_text)}
    ids |= {int(m) for m in re.findall(r"related_partner_id\s*=\s*(\d+)", offerings_text)}
    return sorted(ids)


def _write_real_partners_fixture(site_dir: Path) -> None:
    """Write a `partners.json` at `{site_dir}/src/data/partners.json`
    with a fixture row for every id `_real_related_partner_ids()` finds
    -- enough for `check_partner_references()` to resolve every real
    reference, without asserting anything about the fixture rows'
    content beyond their `id`."""
    data_dir = site_dir / "src" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    partners = [{"id": pid, "name": f"Fixture Partner {pid}"} for pid in _real_related_partner_ids()]
    (data_dir / "partners.json").write_text(json.dumps(partners), encoding="utf-8")


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
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        assert payload["meta"]["total"] == 19
        assert len(payload["places"]) == 19

    def test_default_places_registry_dir_is_directorys_own_registry(self):
        assert DEFAULT_PLACES_REGISTRY_DIR.name == "registry"
        assert DEFAULT_PLACES_REGISTRY_DIR.parent.name == "directory"

    def test_atlas_labs_resolves_via_the_real_zip_centroid_fallback(self, tmp_path):
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        atlas = next(p for p in payload["places"] if p["place_id"] == "atlas-labs")
        assert atlas["location_precision"] == "zip"
        assert atlas["latitude"] is not None
        assert atlas["longitude"] is not None

    def test_dry_run_reports_fifty_seven_clubs_with_no_network(self, tmp_path):
        # Ticket 018-008's own AC: every Hack Club chapter issue 35
        # names has a Club record, geocoded through the real, now
        # populated directory/data/ school directories -- not a fixture
        # copy, the same "trust the real data" precedent this class
        # already applies to Places. Sprint 032 registers six more
        # real club_static_roster entries: ticket 002's
        # cyberpatriot-sd.toml (3 curated CyberPatriot teams), ticket
        # 003's civil-air-patrol-sd.toml (7 curated CAP entries:
        # Group 8's own HQ plus its six subordinate squadrons), ticket
        # 004's sea-cadets-sd.toml (4 curated NSCC units), ticket 005's
        # 4-h-sd.toml (14 curated San Diego County 4-H community
        # clubs), ticket 006's science-olympiad-sd.toml (24 curated
        # Science Olympiad school teams), and ticket 007's
        # girls-who-code-sd.toml (1 confirmed San Diego-area GWC club),
        # so the real full-registry total is now 4 Hack Club + 3
        # CyberPatriot + 7 Civil Air Patrol + 4 Sea Cadets + 14 4-H + 24
        # Science Olympiad + 1 Girls Who Code = 57, not 4.
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        assert payload["clubs_meta"]["total"] == 57
        assert len(payload["clubs"]) == 57

    def test_every_real_school_hosted_club_resolves_to_school_precision_never_a_guess(
        self, tmp_path
    ):
        # Originally looped over every real Club unconditionally, which
        # only held while every registered club type was school-hosted
        # (Hack Club). Sprint 032 ticket 003 adds Civil Air Patrol
        # squadrons, which genuinely meet at non-school facilities
        # (airfields, an armory, a VFW post) and are expected to fall
        # through honestly to zip/city precision instead -- see
        # sprint.md's Architecture "Geocoding note" and
        # directory/DESIGN.md's sprint 032 ticket 003 Revision. This
        # test now scopes to the club types that genuinely are
        # school-hosted (hack-club, cyberpatriot); civil-air-patrol's
        # own honest zip/city fallthrough is covered by
        # TestRealCivilAirPatrolGeocoding below instead.
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        school_hosted_types = {"hack-club", "cyberpatriot"}
        for club in payload["clubs"]:
            if club["club_type"] not in school_hosted_types:
                continue
            assert club["location_precision"] == "school", club["club_id"]
            assert club["latitude"] is not None
            assert club["longitude"] is not None
            assert club["matched_name"]

    def test_two_real_chapters_are_flagged_needs_review(self, tmp_path):
        # Real-world residue two curated host_school values genuinely
        # hit: Hack Club's "Helix Charter High School" (CDE's own
        # record is named "Helix High" -- a legitimate rung-3
        # same-city fuzzy match, not an exact one) and, as of sprint
        # 032 ticket 006, Science Olympiad's "San Dieguito High School
        # Academy" (CDE's own record is named "San Dieguito HS
        # Academy" -- the same kind of legitimate fuzzy match). Both
        # are flagged rather than silently trusted. See
        # directory/DESIGN.md.
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        by_id = {c["club_id"]: c for c in payload["clubs"]}
        needing_review = {cid for cid, c in by_id.items() if c["needs_review"]}

        assert needing_review == {
            "hack-club-helix-charter-high",
            "science-olympiad-san-dieguito-academy",
        }

    def test_public_school_chapters_carry_the_matched_schools_own_website(self, tmp_path):
        _write_real_partners_fixture(tmp_path / "unused")
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


class TestRealCivilAirPatrolGeocoding:
    """Sprint 032 ticket 003: pins the real, committed
    civil-air-patrol-sd.tsv roster's geocoding outcome end-to-end.
    Unlike Hack Club/CyberPatriot, Civil Air Patrol squadrons genuinely
    meet at non-school facilities (airfields, a VFW post, an
    administrative office) -- per sprint.md's Architecture "Geocoding
    note," the shared ladder's school-matching rungs 1-4 are expected
    to miss for most entries and fall through honestly to zip
    precision, not a defect to chase. One real exception: Squadron 714
    genuinely meets on a K-12 charter high school's campus, so it
    correctly resolves at school precision like any other
    school-hosted club."""

    def _real_clubs_by_id(self, tmp_path):
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )
        return {c["club_id"]: c for c in payload["clubs"] if c["club_type"] == "civil-air-patrol"}

    def test_seven_civil_air_patrol_entries_are_present(self, tmp_path):
        assert len(self._real_clubs_by_id(tmp_path)) == 7

    def test_six_non_school_entries_fall_through_to_zip_precision_honestly(self, tmp_path):
        by_id = self._real_clubs_by_id(tmp_path)
        non_school_ids = {
            "civil-air-patrol-group-8-hq",
            "civil-air-patrol-squadron-144",
            "civil-air-patrol-squadron-201",
            "civil-air-patrol-squadron-47",
            "civil-air-patrol-squadron-57",
            "civil-air-patrol-squadron-87",
        }
        for cid in non_school_ids:
            club = by_id[cid]
            assert club["location_precision"] == "zip", cid
            assert club["needs_review"] is False, cid
            assert club["latitude"] is not None
            assert club["longitude"] is not None

    def test_squadron_714_genuinely_resolves_at_school_precision(self, tmp_path):
        by_id = self._real_clubs_by_id(tmp_path)
        club = by_id["civil-air-patrol-squadron-714"]
        assert club["location_precision"] == "school"
        assert club["needs_review"] is False
        assert club["matched_name"] == "Escondido Charter High"

    def test_no_civil_air_patrol_entry_is_ever_flagged_needs_review(self, tmp_path):
        by_id = self._real_clubs_by_id(tmp_path)
        assert not any(c["needs_review"] for c in by_id.values())


class TestRealSeaCadetsGeocoding:
    """Sprint 032 ticket 004: pins the real, committed sea-cadets-sd.tsv
    roster's geocoding outcome end-to-end. Like Civil Air Patrol, every
    Naval Sea Cadet Corps unit here meets at a non-school facility
    (a police/fire HQ, a Marine Corps air station, a Marine Corps base,
    a naval base) -- per sprint.md's Architecture "Geocoding note," the
    shared ladder's school-matching rungs 1-4 are expected to miss for
    every entry. Unlike Civil Air Patrol, none of the four curated
    units' zip codes are covered by the fixture-independent real
    zip-centroids.toml (Escondido's 92026 is the one exception), so
    three of the four fall through one rung further, to city
    precision -- still a real, non-guessed ladder rung, never a
    fabricated coordinate."""

    def _real_clubs_by_id(self, tmp_path):
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )
        return {c["club_id"]: c for c in payload["clubs"] if c["club_type"] == "sea-cadets"}

    def test_four_sea_cadets_entries_are_present(self, tmp_path):
        assert len(self._real_clubs_by_id(tmp_path)) == 4

    def test_escondido_battalion_resolves_at_zip_precision(self, tmp_path):
        by_id = self._real_clubs_by_id(tmp_path)
        club = by_id["sea-cadets-escondido-battalion"]
        assert club["location_precision"] == "zip"
        assert club["needs_review"] is False
        assert club["latitude"] is not None
        assert club["longitude"] is not None

    def test_the_other_three_units_fall_through_to_city_precision_honestly(self, tmp_path):
        by_id = self._real_clubs_by_id(tmp_path)
        city_precision_ids = {
            "sea-cadets-gunfighter-squadron",
            "sea-cadets-michael-monsoor-battalion",
            "sea-cadets-chief-mcm14-division",
        }
        for cid in city_precision_ids:
            club = by_id[cid]
            assert club["location_precision"] == "city", cid
            assert club["needs_review"] is False, cid
            assert club["latitude"] is not None
            assert club["longitude"] is not None

    def test_no_sea_cadets_entry_is_ever_flagged_needs_review(self, tmp_path):
        by_id = self._real_clubs_by_id(tmp_path)
        assert not any(c["needs_review"] for c in by_id.values())


class TestReal4HGeocoding:
    """Sprint 032 ticket 005: pins the real, committed 4-h-sd.tsv
    roster's geocoding outcome end-to-end. Every one of the fourteen
    curated San Diego County 4-H community clubs meets at a non-school
    facility (a museum, a fairgrounds, a community hall) or has no
    specific facility name recorded at all -- per sprint.md's
    Architecture "Geocoding note," the shared ladder's school-matching
    rungs 1-4 are expected to miss for every entry, and every entry's
    zip code is covered by the real, committed zip-centroids.toml, so
    every entry resolves at zip precision, none falling through further
    to city precision and none needing a school-matching rung at all."""

    def _real_clubs_by_id(self, tmp_path):
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )
        return {c["club_id"]: c for c in payload["clubs"] if c["club_type"] == "4-h"}

    def test_fourteen_4h_entries_are_present(self, tmp_path):
        assert len(self._real_clubs_by_id(tmp_path)) == 14

    def test_every_4h_entry_resolves_at_zip_precision_honestly(self, tmp_path):
        by_id = self._real_clubs_by_id(tmp_path)
        for cid, club in by_id.items():
            assert club["location_precision"] == "zip", cid
            assert club["needs_review"] is False, cid
            assert club["latitude"] is not None, cid
            assert club["longitude"] is not None, cid

    def test_no_4h_entry_is_ever_flagged_needs_review(self, tmp_path):
        by_id = self._real_clubs_by_id(tmp_path)
        assert not any(c["needs_review"] for c in by_id.values())


class TestRealScienceOlympiadGeocoding:
    """Sprint 032 ticket 006: pins the real, committed
    science-olympiad-sd.tsv roster's geocoding outcome end-to-end.
    Unlike Civil Air Patrol/Sea Cadets/4-H, Science Olympiad teams are
    explicitly school-based, so 23 of the 24 curated entries resolve
    through the shared ladder's school-matching rungs 1-4, mirroring
    Hack Club/CyberPatriot -- including one legitimate rung-3 same-city
    fuzzy match (San Dieguito High School Academy, curated from the
    tournament results; CDE's own record is "San Dieguito HS Academy"),
    correctly flagged `needs_review` rather than silently trusted, the
    same Helix Charter precedent Hack Club's own roster already hits.
    One entry (The Preuss School UC San Diego) matches no CDE/NCES
    school record at all and honestly falls through to a non-school
    ladder rung -- not a defect to chase, per sprint.md's Architecture
    Geocoding note."""

    def _real_clubs_by_id(self, tmp_path):
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )
        return {
            c["club_id"]: c for c in payload["clubs"] if c["club_type"] == "science-olympiad"
        }

    def test_twenty_four_science_olympiad_entries_are_present(self, tmp_path):
        assert len(self._real_clubs_by_id(tmp_path)) == 24

    def test_twenty_three_entries_resolve_at_school_precision(self, tmp_path):
        by_id = self._real_clubs_by_id(tmp_path)
        school_precision = {
            cid for cid, c in by_id.items() if c["location_precision"] == "school"
        }
        assert len(school_precision) == 23
        assert "science-olympiad-preuss-school" not in school_precision
        for cid in school_precision:
            club = by_id[cid]
            assert club["latitude"] is not None, cid
            assert club["longitude"] is not None, cid
            assert club["matched_name"], cid

    def test_preuss_school_falls_through_honestly_rather_than_a_guess(self, tmp_path):
        by_id = self._real_clubs_by_id(tmp_path)
        club = by_id["science-olympiad-preuss-school"]
        assert club["location_precision"] != "school"
        assert club["location_precision"] != "none"
        assert club["latitude"] is not None
        assert club["longitude"] is not None

    def test_san_dieguito_academy_is_the_one_science_olympiad_entry_flagged_needs_review(
        self, tmp_path
    ):
        by_id = self._real_clubs_by_id(tmp_path)
        needing_review = {cid for cid, c in by_id.items() if c["needs_review"]}
        assert needing_review == {"science-olympiad-san-dieguito-academy"}


class TestRealGirlsWhoCodeGeocoding:
    """Sprint 032 ticket 007: pins the real, committed
    girls-who-code-sd.tsv roster's geocoding outcome end-to-end. Only
    one San Diego-area GWC club could be live-verified through a
    genuinely public, citable source (Canyon Crest Academy's own
    school-sponsored club, per CCA ASB's current approved-clubs
    roster) -- GWC's official club locator returned a 404 when
    directly tested, matching this ticket's own "least likely of the
    six" expectation. Canyon Crest Academy is school-hosted and already
    resolves at school precision for both the CyberPatriot (ticket 002)
    and Science Olympiad (ticket 006) rosters, so this one entry is
    expected to resolve the same way, not a guess."""

    def _real_clubs_by_id(self, tmp_path):
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )
        return {
            c["club_id"]: c for c in payload["clubs"] if c["club_type"] == "girls-who-code"
        }

    def test_one_girls_who_code_entry_is_present(self, tmp_path):
        assert len(self._real_clubs_by_id(tmp_path)) == 1

    def test_canyon_crest_academy_resolves_at_school_precision(self, tmp_path):
        by_id = self._real_clubs_by_id(tmp_path)
        club = by_id["girls-who-code-canyon-crest-academy"]
        assert club["location_precision"] == "school"
        assert club["needs_review"] is False
        assert club["latitude"] is not None
        assert club["longitude"] is not None
        assert club["matched_name"]


class TestSourceFilter:
    def test_source_filter_by_adapter_type_matches_the_real_registry(self, tmp_path):
        _write_real_partners_fixture(tmp_path / "unused")
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
            source="club_static_roster",
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            site_dir=tmp_path / "unused",
        )

        # 4 Hack Club + 3 CyberPatriot + 7 Civil Air Patrol + 4 Sea
        # Cadets + 14 4-H + 24 Science Olympiad + 1 Girls Who Code
        # (sprint 032 ticket 007) = 57.
        assert payload["clubs_meta"]["total"] == 57
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

        # The Place source raises, but the real Offering source still
        # runs unfiltered and its six curated volunteer rows carry real
        # related_partner_id references -- the fixture is needed even
        # though this test's own assertion is about Places.
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        assert payload["meta"]["total"] == 0

    def test_a_raising_club_source_is_logged_and_skipped_not_fatal(self, tmp_path, monkeypatch):
        import partner_scrape.directory.pipeline as pipeline_module

        monkeypatch.setitem(
            pipeline_module._CLUB_SOURCES, "club_static_roster", _BoomingSource()
        )

        _write_real_partners_fixture(tmp_path / "unused")
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

        # The real Offering source still runs unfiltered alongside
        # Clubs -- its six curated volunteer rows carry real
        # related_partner_id references, so the fixture is needed.
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        assert payload["meta"]["total"] == 0
        # 4 Hack Club + 3 CyberPatriot + 7 Civil Air Patrol + 4 Sea
        # Cadets + 14 4-H + 24 Science Olympiad + 1 Girls Who Code
        # (sprint 032 ticket 007) = 57.
        assert payload["clubs_meta"]["total"] == 57

    def test_combined_dispatch_never_logs_a_spurious_place_warning_for_a_real_club_entry(
        self, tmp_path, caplog
    ):
        # Regression guard for the "one combined loop, not two separate
        # ones" design decision (see pipeline.py's own module
        # docstring): a real Club registry entry (adapter_type
        # "club_static_roster") must never trip the Place branch's
        # "no PlaceSource registered" warning.
        import logging

        _write_real_partners_fixture(tmp_path / "unused")
        with caplog.at_level(logging.WARNING):
            run_directory(
                fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
            )

        assert not any(
            "no placesource registered" in record.message.lower() for record in caplog.records
        )


class _FixedPlaceSource:
    """A `PlaceSource` fixture that ignores discover/fetch and hands
    back a fixed, caller-supplied `Place` list from `extract()` --
    mirrors `_BoomingSource`'s "monkeypatch `_PLACE_SOURCES['static_
    roster']`" injection pattern above, but yields real records instead
    of raising."""

    def __init__(self, places: list[Place]) -> None:
        self._places = places

    def discover(self, source, fetcher):
        return [PlaceRef(url="fixture://places")]

    def fetch(self, ref, fetcher):
        return RawPlaceResponse(ref=ref, status=200, body="")

    def extract(self, raw, source):
        return self._places


def _write_static_roster_only_registry(tmp_path: Path) -> Path:
    """A registry dir with only a `static_roster`-adapter_type entry --
    no `club_static_roster` entry -- so a test's injected
    `_FixedPlaceSource` is the only source `run_directory()` dispatches
    to, matching `TestPerSourceErrorIsolation`'s own registry-dir
    fixture pattern."""
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "places.toml").write_text(
        'org_name = "Fixture Places"\nadapter_type = "static_roster"\nenabled = true\n'
        "[config]\n",
        encoding="utf-8",
    )
    return registry_dir


class TestRelatedPartnerIdJoinIntegrity:
    """Recovers, as pipeline-level validation, the join-integrity
    guard `tests/directory/test_dataset_validity.py`'s deleted
    `TestRelatedPartnerIdJoinIntegrity` class used to provide (issue
    48, ticket 004). See `pipeline._check_related_partner_references()`'s
    own docstring for the full rationale."""

    def test_dangling_related_partner_id_raises_naming_both_ids(self, tmp_path, monkeypatch):
        import partner_scrape.directory.pipeline as pipeline_module

        registry_dir = _write_static_roster_only_registry(tmp_path)
        monkeypatch.setitem(
            pipeline_module._PLACE_SOURCES,
            "static_roster",
            _FixedPlaceSource(
                [
                    Place(
                        place_id="orphan-place",
                        name="Orphan Place",
                        category="makerspace",
                        related_partner_id=999,
                    )
                ]
            ),
        )

        site_dir = tmp_path / "site"
        data_dir = site_dir / "src" / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "partners.json").write_text(
            json.dumps([{"id": 1, "name": "Real Partner"}]), encoding="utf-8"
        )

        with pytest.raises(RosterValidationError) as excinfo:
            run_directory(
                registry_dir=registry_dir,
                fetcher=_NeverCalledFetcher(),
                dry_run=True,
                site_dir=site_dir,
            )

        message = str(excinfo.value)
        assert "orphan-place" in message
        assert "999" in message

    def test_valid_related_partner_id_does_not_raise(self, tmp_path, monkeypatch):
        import partner_scrape.directory.pipeline as pipeline_module

        registry_dir = _write_static_roster_only_registry(tmp_path)
        monkeypatch.setitem(
            pipeline_module._PLACE_SOURCES,
            "static_roster",
            _FixedPlaceSource(
                [
                    Place(
                        place_id="matched-place",
                        name="Matched Place",
                        category="makerspace",
                        related_partner_id=1,
                    )
                ]
            ),
        )

        site_dir = tmp_path / "site"
        data_dir = site_dir / "src" / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "partners.json").write_text(
            json.dumps([{"id": 1, "name": "Real Partner"}]), encoding="utf-8"
        )

        payload = run_directory(
            registry_dir=registry_dir,
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            site_dir=site_dir,
        )

        assert payload["meta"]["total"] == 1

    def test_no_related_partner_id_set_succeeds_without_partners_json(
        self, tmp_path, monkeypatch
    ):
        import partner_scrape.directory.pipeline as pipeline_module

        registry_dir = _write_static_roster_only_registry(tmp_path)
        monkeypatch.setitem(
            pipeline_module._PLACE_SOURCES,
            "static_roster",
            _FixedPlaceSource(
                [
                    Place(
                        place_id="unrelated-place",
                        name="Unrelated Place",
                        category="makerspace",
                    )
                ]
            ),
        )

        # site_dir exists, but its src/data/partners.json deliberately
        # does not -- no Place sets related_partner_id, so
        # partners.json must never be read at all.
        site_dir = tmp_path / "site"

        payload = run_directory(
            registry_dir=registry_dir,
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            site_dir=site_dir,
        )

        assert payload["meta"]["total"] == 1
        assert not (site_dir / "src" / "data" / "partners.json").exists()


# ---------------------------------------------------------------------
# Sprint 030 ticket 001: Offering, the third standing-entity dispatch.
# Against the real, committed Offering Registry -- no fixture copy,
# matching this ticket's other "trust the real data" tests. As of
# ticket 003 (issue 33 part 2), the real roster carries thirteen rows:
# six curated volunteer org profiles (ticket 002, issue 14 Strategy B)
# plus seven curated free/Title I school-program rows (ticket 003) --
# no placeholders remaining.
# ---------------------------------------------------------------------


class TestRunDirectoryOfferingDispatch:
    def test_dry_run_reports_thirteen_offerings_with_no_network(self, tmp_path):
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        assert payload["offerings_meta"]["total"] == 13
        assert len(payload["offerings"]) == 13

    def test_a_real_offering_registry_entry_never_trips_place_or_club_warnings(
        self, tmp_path, caplog
    ):
        # Regression guard for the "one combined loop, checking
        # _PLACE_SOURCES then _CLUB_SOURCES then _OFFERING_SOURCES"
        # design decision (see pipeline.py's own module docstring): a
        # real Offering registry entry (adapter_type
        # "offering_static_roster") must never trip either earlier
        # branch's "not registered" warning.
        import logging

        _write_real_partners_fixture(tmp_path / "unused")
        with caplog.at_level(logging.WARNING):
            run_directory(fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused")

        assert not any(
            "not registered" in record.message.lower() for record in caplog.records
        )

    def test_places_and_clubs_are_still_populated_alongside_offerings(self, tmp_path):
        # The combined three-way dispatch loop must not regress
        # Place/Club acquisition now that a third table is checked per
        # source_config.
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        assert payload["meta"]["total"] == 19
        # 4 Hack Club + 3 CyberPatriot + 7 Civil Air Patrol + 4 Sea
        # Cadets + 14 4-H + 24 Science Olympiad + 1 Girls Who Code
        # (sprint 032 ticket 007) = 57.
        assert payload["clubs_meta"]["total"] == 57
        assert payload["offerings_meta"]["total"] == 13


class TestOfferingHasNoGeocodingStage:
    """AC: "No geocoding stage is added for Offering -- no
    `_apply_offering_geocoding()` function exists," and a test proving
    no `GeoLadder` is ever constructed for `Offering` records. Unlike
    `TestApplyGeoFallback`/`TestApplyClubGeocoding` above, there is no
    `_apply_offering_geocoding()` function to call at all -- this class
    proves that structurally and via a raising `GeoLadder` double over a
    real run that only acquires Offerings.
    """

    def test_no_apply_offering_geocoding_function_exists(self):
        import partner_scrape.directory.pipeline as pipeline_module

        assert not hasattr(pipeline_module, "_apply_offering_geocoding")

    def test_geo_ladder_is_never_constructed_for_an_offering_only_run(
        self, tmp_path, monkeypatch
    ):
        import partner_scrape.directory.pipeline as pipeline_module

        def _boom(*args, **kwargs):
            raise AssertionError("GeoLadder must never be constructed for an Offering-only run")

        monkeypatch.setattr(pipeline_module, "GeoLadder", _boom)

        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            source="offering_static_roster",
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            site_dir=tmp_path / "unused",
        )

        assert payload["offerings_meta"]["total"] == 13
        assert payload["meta"]["total"] == 0
        assert payload["clubs_meta"]["total"] == 0

    def test_offering_records_carry_no_location_attributes(self, tmp_path):
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )

        for offering in payload["offerings"]:
            assert "latitude" not in offering
            assert "longitude" not in offering
            assert "location_precision" not in offering


class TestOfferingSourceFilter:
    def test_source_filter_by_adapter_type_matches_the_real_registry(self, tmp_path):
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            source="offering_static_roster",
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            site_dir=tmp_path / "unused",
        )

        assert payload["offerings_meta"]["total"] == 13
        assert payload["meta"]["total"] == 0
        assert payload["clubs_meta"]["total"] == 0


def _write_offering_only_registry(tmp_path: Path) -> Path:
    """A registry dir with only an `offering_static_roster`-adapter_type
    entry -- mirrors `_write_static_roster_only_registry()`'s own
    pattern above, for the Offering-side error-isolation/join-integrity
    tests below."""
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "offerings.toml").write_text(
        'org_name = "Fixture Offerings"\nadapter_type = "offering_static_roster"\nenabled = true\n'
        "[config]\n",
        encoding="utf-8",
    )
    return registry_dir


class _FixedOfferingSource:
    """An `OfferingSource` fixture double -- mirrors `_FixedPlaceSource`
    above, for `Offering` instead of `Place`."""

    def __init__(self, offerings: list[Offering]) -> None:
        self._offerings = offerings

    def discover(self, source, fetcher):
        return [OfferingRef(url="fixture://offerings")]

    def fetch(self, ref, fetcher):
        return RawOfferingResponse(ref=ref, status=200, body="")

    def extract(self, raw, source):
        return self._offerings


class TestOfferingPerSourceErrorIsolation:
    def test_a_raising_offering_source_is_logged_and_skipped_not_fatal(
        self, tmp_path, monkeypatch
    ):
        import partner_scrape.directory.pipeline as pipeline_module

        monkeypatch.setitem(
            pipeline_module._OFFERING_SOURCES, "offering_static_roster", _BoomingSource()
        )

        # The real committed places.toml carries hand-verified
        # related_partner_id references, validated unconditionally --
        # write the fixture before any call against the real registry.
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused")

        assert payload["offerings_meta"]["total"] == 0
        # The unrelated Place/Club sources are unaffected -- per-source
        # isolation, not "one broken source kills the whole run".
        assert payload["meta"]["total"] == 19
        # 4 Hack Club + 3 CyberPatriot + 7 Civil Air Patrol + 4 Sea
        # Cadets + 14 4-H + 24 Science Olympiad + 1 Girls Who Code
        # (sprint 032 ticket 007) = 57.
        assert payload["clubs_meta"]["total"] == 57


class TestOfferingRelatedPartnerIdJoinIntegrity:
    """Extends `TestRelatedPartnerIdJoinIntegrity` above to
    `Offering.related_partner_id` -- same generic
    `_check_related_partner_references()` guard, now fed references
    from both `places` and `offerings`."""

    def test_dangling_offering_related_partner_id_raises_naming_both_ids(
        self, tmp_path, monkeypatch
    ):
        import partner_scrape.directory.pipeline as pipeline_module

        registry_dir = _write_offering_only_registry(tmp_path)
        monkeypatch.setitem(
            pipeline_module._OFFERING_SOURCES,
            "offering_static_roster",
            _FixedOfferingSource(
                [
                    Offering(
                        offering_id="orphan-offering",
                        org_name="Orphan Org",
                        title="Orphan Offering",
                        offering_type="volunteer",
                        related_partner_id=999,
                    )
                ]
            ),
        )

        site_dir = tmp_path / "site"
        data_dir = site_dir / "src" / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "partners.json").write_text(
            json.dumps([{"id": 1, "name": "Real Partner"}]), encoding="utf-8"
        )

        with pytest.raises(RosterValidationError) as excinfo:
            run_directory(
                registry_dir=registry_dir,
                fetcher=_NeverCalledFetcher(),
                dry_run=True,
                site_dir=site_dir,
            )

        message = str(excinfo.value)
        assert "orphan-offering" in message
        assert "999" in message

    def test_valid_offering_related_partner_id_does_not_raise(self, tmp_path, monkeypatch):
        import partner_scrape.directory.pipeline as pipeline_module

        registry_dir = _write_offering_only_registry(tmp_path)
        monkeypatch.setitem(
            pipeline_module._OFFERING_SOURCES,
            "offering_static_roster",
            _FixedOfferingSource(
                [
                    Offering(
                        offering_id="matched-offering",
                        org_name="Matched Org",
                        title="Matched Offering",
                        offering_type="volunteer",
                        related_partner_id=1,
                    )
                ]
            ),
        )

        site_dir = tmp_path / "site"
        data_dir = site_dir / "src" / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "partners.json").write_text(
            json.dumps([{"id": 1, "name": "Real Partner"}]), encoding="utf-8"
        )

        payload = run_directory(
            registry_dir=registry_dir,
            fetcher=_NeverCalledFetcher(),
            dry_run=True,
            site_dir=site_dir,
        )

        assert payload["offerings_meta"]["total"] == 1

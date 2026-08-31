"""Dataset-validity regression tests for the curated Places roster
(`partner_scrape/directory/data/places.toml`).

Data-only-ticket tests, matching sprint.md's Test Strategy precedent
for a curated dataset (ticket 003's own `TestBatchARegistryJoinIntegrity`
class): these pin down properties of the *real* committed data --
unique ids, in-bounding-box coordinates, no hijacked domain, category
coverage, and a hand-verified join against the real partner roster --
rather than a synthetic fixture, so a future edit to `places.toml`
that regresses one of these is caught directly.
"""

from __future__ import annotations

import json
from pathlib import Path

from partner_scrape.directory.model import VALID_CATEGORIES
from partner_scrape.directory.sources.base import run
from partner_scrape.directory.sources.static_roster import StaticRosterSource
from partner_scrape.registry.loader import load_active_sources

DIRECTORY_REGISTRY_DIR = (
    Path(__file__).resolve().parents[2] / "partner_scrape" / "directory" / "registry"
)
PARTNERS_JSON_PATH = (
    Path(__file__).resolve().parents[2] / "site" / "src" / "data" / "partners.json"
)

# site/src/pages/partners/index.astro's own SD_BOUNDS -- the same
# bounding box ticket 003's own roster housekeeping regression tests
# check new partner rows against.
SD_BOUNDS = {"latMin": 32.4, "latMax": 33.5, "lngMin": -117.7, "lngMax": -116.0}

# The hijacked domain ticket 002 (sprint 018) removed from the partner
# roster -- must never appear in any Place's website field either.
_HIJACKED_DOMAIN = "batiquitosfoundation.org"


class _NeverCalledFetcher:
    def get(self, url: str, headers=None):
        raise AssertionError("must never call the injected Fetcher")


def _real_places():
    sources = load_active_sources(DIRECTORY_REGISTRY_DIR)
    static_roster = next(s for s in sources if s.adapter_type == "static_roster")
    return run(static_roster, StaticRosterSource(), _NeverCalledFetcher())


def _real_partner_ids() -> set[int]:
    data = json.loads(PARTNERS_JSON_PATH.read_text())
    return {row["id"] for row in data}


class TestUniqueIds:
    def test_every_place_id_is_unique(self):
        ids = [p.place_id for p in _real_places()]
        assert len(ids) == len(set(ids))

    def test_no_place_id_is_blank(self):
        assert all(p.place_id for p in _real_places())


class TestCategoryCoverage:
    def test_every_category_issue_35_named_has_at_least_one_entry(self):
        categories = {p.category for p in _real_places()}
        assert categories == VALID_CATEGORIES

    def test_at_least_fifteen_places_curated(self):
        # sprint.md: "populate Places in full (curated, ~15-20 entries)".
        assert len(_real_places()) >= 15


class TestAtlasLabsStatus:
    def test_atlas_labs_is_opening_not_open(self):
        by_id = {p.place_id: p for p in _real_places()}
        assert "atlas-labs" in by_id
        assert by_id["atlas-labs"].status == "opening"
        assert by_id["atlas-labs"].status != "open"


class TestInBoundsCoordinates:
    def test_every_curated_coordinate_is_within_sd_bounds_or_absent(self):
        for place in _real_places():
            if place.latitude is None:
                continue
            assert SD_BOUNDS["latMin"] <= place.latitude <= SD_BOUNDS["latMax"], place.place_id
            assert SD_BOUNDS["lngMin"] <= place.longitude <= SD_BOUNDS["lngMax"], place.place_id


class TestNoHijackedDomain:
    def test_hijacked_domain_never_appears_in_any_website(self):
        for place in _real_places():
            assert _HIJACKED_DOMAIN not in place.website


class TestWebsiteUrlsAreWellFormed:
    def test_every_non_empty_website_starts_with_http(self):
        for place in _real_places():
            if place.website:
                assert place.website.startswith(("http://", "https://")), place.place_id


class TestRelatedPartnerIdJoinIntegrity:
    """Ticket 007's own instruction: "reuse the same curated address/
    coordinates rather than re-researching -- but do not attempt an
    automatic cross-reference join this sprint... hand-copy the
    value." This test verifies every hand-copied `related_partner_id`
    actually resolves to a real row in the current partner roster, the
    same spot-check discipline ticket 003's own
    `TestBatchARegistryJoinIntegrity` applied to its own hand-verified
    org_name matches.
    """

    def test_every_related_partner_id_exists_in_the_real_roster(self):
        partner_ids = _real_partner_ids()
        for place in _real_places():
            if place.related_partner_id is not None:
                assert place.related_partner_id in partner_ids, (
                    place.place_id,
                    place.related_partner_id,
                )

    def test_a_representative_sample_of_joins_point_at_the_expected_org(self):
        partners_by_id = {row["id"]: row for row in json.loads(PARTNERS_JSON_PATH.read_text())}
        by_id = {p.place_id: p for p in _real_places()}

        expected = {
            "fleet-science-center-planetarium": "Fleet Science Center",
            "palomar-observatory": "Palomar Observatory",
            "birch-aquarium-tide-pool-plaza": "Birch Aquarium at Scripps Institution of Oceanography",
            "living-coast-discovery-center": "The Living Coast Discovery Center",
        }
        for place_id, expected_name in expected.items():
            partner_id = by_id[place_id].related_partner_id
            assert partner_id is not None, place_id
            assert partners_by_id[partner_id]["name"] == expected_name


class TestNoLiveGeocodedCoordinate:
    """AC: "No place entry's coordinates come from a live geocoder --
    every one uses the shared geo-ladder ... or a hand-curated
    address, never a guess." The static-roster source itself only ever
    produces "address" (hand-curated) or "none" (left for the shared
    ladder's own offline fallback) -- this is the dataset-level half of
    that guarantee; tests/directory/test_pipeline.py covers the
    fallback's own offline-only behavior.
    """

    def test_every_places_location_precision_is_address_or_none_at_the_source_layer(self):
        for place in _real_places():
            assert place.location_precision in {"address", "none"}

"""Dataset-validity regression tests for the curated Places roster
(`partner_scrape/directory/data/places.toml`).

Data-only-ticket tests, matching sprint.md's Test Strategy precedent
for a curated dataset (ticket 003's own registry-source-name tests):
these pin down properties of the *real* committed data -- unique ids,
in-bounding-box coordinates, no hijacked domain, and category coverage
-- rather than a synthetic fixture, so a future edit to `places.toml`
that regresses one of these is caught directly.

Sprint 019 ticket 002 removed `partner-scrape/site/` as a tracked
directory (build-time-only CI checkout of `stem-ecosystem` now), which
took `site/src/data/partners.json` with it. The `related_partner_id`
join-integrity check that used to verify each hand-copied
`related_partner_id` resolves against that file is tracked for recovery
as pipeline-level validation in issue 48, not reproduced here against a
re-copied fixture (that would recreate the exact two-copies-of-the-
same-file problem the site consolidation exists to eliminate).
"""

from __future__ import annotations

from pathlib import Path

from partner_scrape.directory.model import VALID_CATEGORIES
from partner_scrape.directory.sources.base import run
from partner_scrape.directory.sources.static_roster import StaticRosterSource
from partner_scrape.registry.loader import load_active_sources

DIRECTORY_REGISTRY_DIR = (
    Path(__file__).resolve().parents[2] / "partner_scrape" / "directory" / "registry"
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

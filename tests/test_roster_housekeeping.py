"""Sprint 018 ticket 002 (issue 32 housekeeping) verification.

These tests run against the real `data/partners_viable.csv` and the
registry TOML sources -- not synthetic fixtures, because their whole
purpose is to guard the *actual* roster data against regressing back
into the defects this ticket fixed: the bare-California geocoder
centroid, pins outside the site map's bounding box, the hijacked
`batiquitosfoundation.org` domain, and registry source org_name drift.

Sprint 019 ticket 002 removed `partner-scrape/site/` as a tracked
directory (it is now a build-time-only CI checkout of `stem-ecosystem`),
which took the JSON-side half of these guards (`site/src/data/
partners.json`, `site/public/images/logos/`) with it -- there is no
longer a local file for a hermetic test to read. Those guards (the
bare-California-centroid, out-of-bounds, hijacked-domain, and JSON/CSV
sync checks against `partners.json`, plus the JSON-side registry
join-integrity and logo-backfill checks) are tracked for recovery as
pipeline-level validation in issue 48, not reproduced here against a
re-copied fixture (that would recreate the exact two-copies-of-the-
same-file problem the site consolidation exists to eliminate). The CSV
-side and registry-TOML-side guards below have no such dependency and
are unaffected -- `data/partners_viable.csv` and the registry sources
remain tracked, local files.

Bounding box mirrors `site/src/pages/partners/index.astro`'s own
`SD_BOUNDS` constant (now in `stem-ecosystem`) -- kept in sync by hand
since the value lives in an Astro page, not an importable Python module.
"""

from __future__ import annotations

import csv
from pathlib import Path

from partner_scrape.normalize.partners import normalize_org_name
from partner_scrape.registry.loader import DEFAULT_SOURCES_DIR, load_sources

REPO_ROOT = Path(__file__).resolve().parent.parent
PARTNERS_CSV = REPO_ROOT / "data" / "partners_viable.csv"

# site/src/pages/partners/index.astro's SD_BOUNDS -- the map silently drops
# any pin outside this box.
SD_BOUNDS = {"latMin": 32.4, "latMax": 33.5, "lngMin": -117.7, "lngMax": -116.0}

# Google's geocoder centroid for the bare string "California" -- sprint
# 011's known bad-centroid signature.
BARE_CALIFORNIA_CENTROID = (36.778261, -119.417932)

HIJACKED_DOMAIN = "batiquitosfoundation.org"


def _load_partners_csv() -> list[dict]:
    with PARTNERS_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class TestNoBareCaliforniaCentroid:
    def test_no_csv_row_uses_the_bare_california_centroid(self):
        rows = _load_partners_csv()

        offenders = []
        for r in rows:
            lat, lng = r.get("latitude"), r.get("longitude")
            if not lat or not lng:
                continue
            if round(float(lat), 6) == BARE_CALIFORNIA_CENTROID[0] and round(
                float(lng), 6
            ) == BARE_CALIFORNIA_CENTROID[1]:
                offenders.append(r["id"])

        assert offenders == []


class TestNoOutOfBoundsCoordinates:
    def test_every_csv_row_is_in_bounds_or_has_no_coordinates(self):
        rows = _load_partners_csv()

        offenders = []
        for r in rows:
            lat, lng = r.get("latitude"), r.get("longitude")
            if not lat or not lng:
                continue
            lat, lng = float(lat), float(lng)
            if not (
                SD_BOUNDS["latMin"] <= lat <= SD_BOUNDS["latMax"]
                and SD_BOUNDS["lngMin"] <= lng <= SD_BOUNDS["lngMax"]
            ):
                offenders.append((r["id"], r["name"], lat, lng))

        assert offenders == []


class TestNoHijackedDomain:
    def test_hijacked_domain_absent_from_csv(self):
        assert HIJACKED_DOMAIN not in PARTNERS_CSV.read_text(encoding="utf-8")


class TestRegistrySourceNameStability:
    """Sprint 018 tickets 003/004 (issue 32 batch A/B). Every registry
    source these tickets named as "already registered as an event
    source" must keep the exact `org_name` recorded in the ticket's own
    Notes -- a silent rename in the source TOML would desync the join
    against the roster (the roster-side half of that join-integrity
    check is tracked for recovery in issue 48, since it needs
    `partners.json`, no longer a local file here)."""

    def test_normalize_org_name_is_insensitive_to_the_kept_name_variant(self):
        # The surviving "Living Coast" row was renamed to the registry's
        # literal "The Living Coast Discovery Center" -- confirm the join
        # still works for the un-prefixed variant too (both normalize
        # identically via the leading-"the" strip).
        assert normalize_org_name("The Living Coast Discovery Center") == normalize_org_name(
            "Living Coast Discovery Center"
        )


class TestBatchARegistrySourceNames:
    """Sprint 018 ticket 003 (issue 32 batch A: parks/nature, astronomy,
    museums, libraries). Every registry source this ticket's Description
    named as "already registered as an event source" must still carry
    the org_name recorded here -- verified by reading the TOML directly,
    not assumed from the ticket/gap-analysis prose."""

    BATCH_A_ALREADY_REGISTERED_SOURCES = {
        "county-parks": "San Diego County Parks and Recreation",
        "mission-trails": "Mission Trails Regional Park Foundation",
        "sdcoastkeeper": "San Diego Coastkeeper",
        "surfrider-sd": "Surfrider Foundation San Diego County Chapter",
        "sd-astronomy-association": "San Diego Astronomy Association",
        "comic-con-museum": "Comic-Con Museum",
        "sandiegoarchaeology": "San Diego Archaeological Center",
        "oceanside-library": "Oceanside Public Library",
        "coronado-library": "Coronado Public Library",
        "escondido-library": "Escondido Public Library",
        "balboa-park": "Balboa Park",
    }

    def test_every_batch_a_source_org_name_still_matches_its_toml(self):
        sources_by_id = {s.source_id: s for s in load_sources(DEFAULT_SOURCES_DIR)}

        missing = [
            source_id
            for source_id in self.BATCH_A_ALREADY_REGISTERED_SOURCES
            if source_id not in sources_by_id
        ]
        assert missing == [], f"expected registry sources not found: {missing}"

        mismatched = {
            source_id: sources_by_id[source_id].org_name
            for source_id, expected_org_name in self.BATCH_A_ALREADY_REGISTERED_SOURCES.items()
            if sources_by_id[source_id].org_name != expected_org_name
        }
        assert mismatched == {}, f"source org_name drifted from this test's expectation: {mismatched}"


class TestBatchBRegistrySourceNames:
    """Sprint 018 ticket 004 (issue 32 batch B: youth orgs, competitions/clubs,
    research/health, pipeline/adult). Every registry source this ticket's
    Description named as "already registered as an event source" must
    still carry the org_name recorded here -- verified by reading the
    TOML directly, not assumed from the ticket/gap-analysis prose."""

    BATCH_B_ALREADY_REGISTERED_SOURCES = {
        "shpesd": "SHPE San Diego",
        "ucsd-jacobs-school": "UC San Diego Jacobs School of Engineering",
        "ymcasd": "YMCA of San Diego County",
    }

    def test_every_batch_b_source_org_name_still_matches_its_toml(self):
        sources_by_id = {s.source_id: s for s in load_sources(DEFAULT_SOURCES_DIR)}

        missing = [
            source_id
            for source_id in self.BATCH_B_ALREADY_REGISTERED_SOURCES
            if source_id not in sources_by_id
        ]
        assert missing == [], f"expected registry sources not found: {missing}"

        mismatched = {
            source_id: sources_by_id[source_id].org_name
            for source_id, expected_org_name in self.BATCH_B_ALREADY_REGISTERED_SOURCES.items()
            if sources_by_id[source_id].org_name != expected_org_name
        }
        assert mismatched == {}, f"source org_name drifted from this test's expectation: {mismatched}"

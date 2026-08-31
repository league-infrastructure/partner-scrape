"""Sprint 018 ticket 002 (issue 32 housekeeping) verification.

These tests run against the registry TOML sources -- not synthetic
fixtures, because their whole purpose is to guard the *actual* roster
data against regressing back into the defects sprint 018 fixed: the
bare-California geocoder centroid, pins outside the site map's bounding
box, the hijacked `batiquitosfoundation.org` domain, and registry source
org_name drift.

Sprint 019 ticket 002 removed `partner-scrape/site/` as a tracked
directory (it is now a build-time-only CI checkout of `stem-ecosystem`),
which took the JSON-side half of these guards (`site/src/data/
partners.json`, `site/public/images/logos/`) with it -- there is no
longer a local file for a hermetic test to read. Sprint 020 ticket 002
then deleted `data/partners_viable.csv` itself (confirmed dead, zero
production readers -- issue 60), which took the CSV-side half
(`TestNoBareCaliforniaCentroid`, `TestNoOutOfBoundsCoordinates`,
`TestNoHijackedDomain`, and their shared `_load_partners_csv()` helper)
with it. All of those guards (bare-California-centroid, out-of-bounds,
hijacked-domain, and JSON/CSV sync checks against `partners.json`, plus
the JSON-side registry join-integrity and logo-backfill checks) are
tracked for recovery as pipeline-level validation in issue 48 -- not
reproduced here against a re-copied fixture (that would recreate the
exact two-copies-of-the-same-file problem the site consolidation exists
to eliminate). Only the registry-TOML-side guards below survive locally,
since they have no dependency on either retired file. The bounding-box
constant that guarded coordinates against `site/src/pages/partners/
index.astro`'s `SD_BOUNDS` (San Diego County's lat/lng box) went with
`TestNoOutOfBoundsCoordinates`; issue 48's pipeline-level validation is
expected to need the identical box when it recovers that guard.
"""

from __future__ import annotations

from partner_scrape.normalize.partners import normalize_org_name
from partner_scrape.registry.loader import DEFAULT_SOURCES_DIR, load_sources


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

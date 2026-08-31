"""Sprint 018 ticket 002 (issue 32 housekeeping) verification.

These tests run against the real roster files -- `site/src/data/partners.json`
and `data/partners_viable.csv` -- not synthetic fixtures, because their whole
purpose is to guard the *actual* roster data against regressing back into
the defects this ticket fixed: the bare-California geocoder centroid, pins
outside the site map's bounding box, the hijacked `batiquitosfoundation.org`
domain, duplicate rows that break the partner join, and JSON/CSV drift.

Bounding box mirrors `site/src/pages/partners/index.astro`'s own `SD_BOUNDS`
constant -- kept in sync by hand since the value lives in an Astro page, not
an importable Python module.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from partner_scrape.normalize.partners import find_partner, load_partners, normalize_org_name
from partner_scrape.registry.loader import DEFAULT_SOURCES_DIR, load_sources

REPO_ROOT = Path(__file__).resolve().parent.parent
PARTNERS_JSON = REPO_ROOT / "site" / "src" / "data" / "partners.json"
PARTNERS_CSV = REPO_ROOT / "data" / "partners_viable.csv"

# site/src/pages/partners/index.astro's SD_BOUNDS -- the map silently drops
# any pin outside this box.
SD_BOUNDS = {"latMin": 32.4, "latMax": 33.5, "lngMin": -117.7, "lngMax": -116.0}

# Google's geocoder centroid for the bare string "California" -- sprint
# 011's known bad-centroid signature.
BARE_CALIFORNIA_CENTROID = (36.778261, -119.417932)

HIJACKED_DOMAIN = "batiquitosfoundation.org"


def _load_partners_json() -> list[dict]:
    return json.loads(PARTNERS_JSON.read_text(encoding="utf-8"))


def _load_partners_csv() -> list[dict]:
    with PARTNERS_CSV.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class TestNoBareCaliforniaCentroid:
    def test_no_json_entry_uses_the_bare_california_centroid(self):
        partners = _load_partners_json()

        offenders = [
            p["id"]
            for p in partners
            if p.get("latitude") is not None
            and round(p["latitude"], 6) == BARE_CALIFORNIA_CENTROID[0]
            and round(p["longitude"], 6) == BARE_CALIFORNIA_CENTROID[1]
        ]

        assert offenders == []

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
    def test_every_json_entry_is_in_bounds_or_has_no_coordinates(self):
        partners = _load_partners_json()

        offenders = []
        for p in partners:
            lat, lng = p.get("latitude"), p.get("longitude")
            if lat is None or lng is None:
                continue
            if not (
                SD_BOUNDS["latMin"] <= lat <= SD_BOUNDS["latMax"]
                and SD_BOUNDS["lngMin"] <= lng <= SD_BOUNDS["lngMax"]
            ):
                offenders.append((p["id"], p["name"], lat, lng))

        assert offenders == []

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
    def test_hijacked_domain_absent_from_json(self):
        assert HIJACKED_DOMAIN not in PARTNERS_JSON.read_text(encoding="utf-8")

    def test_hijacked_domain_absent_from_csv(self):
        assert HIJACKED_DOMAIN not in PARTNERS_CSV.read_text(encoding="utf-8")

    def test_known_dead_url_replacements_landed(self):
        text = PARTNERS_JSON.read_text(encoding="utf-8")
        assert "mep.sdsu.edu" not in text
        assert "mesa.sdsu.edu" in text

        partners = _load_partners_json()
        garden = next(p for p in partners if p["name"] == "The Water Conservation Garden")
        assert "thegarden.org" in garden["website"]


class TestJsonCsvSync:
    def test_same_row_count(self):
        assert len(_load_partners_json()) == len(_load_partners_csv())

    def test_same_id_set(self):
        json_ids = {p["id"] for p in _load_partners_json()}
        csv_ids = {int(r["id"]) for r in _load_partners_csv()}
        assert json_ids == csv_ids

    def test_no_duplicate_names_remain(self):
        from collections import Counter

        names = [p["name"] for p in _load_partners_json()]
        dupes = {name: count for name, count in Counter(names).items() if count > 1}
        assert dupes == {}


class TestRegistryJoinIntegrity:
    """Every registry source's org_name must still resolve to exactly one
    roster entry after the dedup -- the failure mode issue 32 and this
    ticket both call out explicitly (`find_partner()`'s `setdefault`
    behavior means a broken dedup would silently keep resolving to the
    *wrong* row rather than erroring)."""

    def test_every_previously_resolving_registry_source_still_resolves(self):
        partners_by_norm = load_partners(PARTNERS_JSON)
        sources = load_sources(DEFAULT_SOURCES_DIR)

        assert sources, "expected at least one registry source to check"

        still_unresolved = []
        for source in sources:
            partner = find_partner(source.org_name, partners_by_norm)
            if partner is None:
                still_unresolved.append(source.org_name)

        # Not every registry source has a roster entry yet (that gap is
        # tickets 003/004's job, not this one's) -- this test only
        # guards that the dedup didn't *break* a join, spot-checked
        # against the 10 named duplicate orgs (+ the San Diego
        # Automotive Museum dup found during the audit) below.
        named_dedup_orgs = {
            "The Living Coast Discovery Center",
            "Elementary Institute of Science",
            "Greater San Diego Science and Engineering Fair",
            "The San Diego River Park Foundation",
            "Fleet Science Center",
            "Viasat",
            "Media Arts Center San Diego",
            "Ocean Connectors",
            "San Diego Futures Foundation",
            "Salk Institute Education Outreach",
            "San Diego Automotive Museum",
        }
        broken = named_dedup_orgs & set(still_unresolved)
        assert broken == set(), f"dedup broke the join for: {broken}"

    def test_deduped_orgs_resolve_to_their_intended_surviving_id(self):
        partners_by_norm = load_partners(PARTNERS_JSON)

        expected = {
            "The Living Coast Discovery Center": 46,
            "Elementary Institute of Science": 165,
            "Greater San Diego Science and Engineering Fair": 231,
            "The San Diego River Park Foundation": 323,
            "Fleet Science Center": 121,
            "Viasat": 166,
            "Media Arts Center San Diego": 277,
            "Ocean Connectors": 174,
            "San Diego Futures Foundation": 176,
            "Salk Institute Education Outreach": 23,
            "San Diego Automotive Museum": 551,
        }

        for org_name, expected_id in expected.items():
            partner = find_partner(org_name, partners_by_norm)
            assert partner is not None, f"{org_name} no longer resolves at all"
            assert partner["id"] == expected_id, (
                f"{org_name} resolved to id {partner['id']}, expected {expected_id}"
            )

    def test_normalize_org_name_is_insensitive_to_the_kept_name_variant(self):
        # The surviving "Living Coast" row was renamed to the registry's
        # literal "The Living Coast Discovery Center" -- confirm the join
        # still works for the un-prefixed variant too (both normalize
        # identically via the leading-"the" strip).
        assert normalize_org_name("The Living Coast Discovery Center") == normalize_org_name(
            "Living Coast Discovery Center"
        )


class TestBatchARegistryJoinIntegrity:
    """Sprint 018 ticket 003 (issue 32 batch A: parks/nature, astronomy,
    museums, libraries). Every registry source this ticket's Description
    named as "already registered as an event source" must now resolve to
    a roster entry whose ``name`` matches the source's own ``org_name``
    literally -- not just the gap-analysis spelling. See ticket 003's
    Notes for the exact org_name each source TOML uses."""

    # source_id -> the source TOML's literal org_name (verified by reading
    # the TOML directly, not assumed from the ticket/gap-analysis prose).
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

    def test_every_batch_a_source_now_resolves_to_exactly_one_roster_entry(self):
        partners_by_norm = load_partners(PARTNERS_JSON)

        unresolved = []
        for org_name in self.BATCH_A_ALREADY_REGISTERED_SOURCES.values():
            if find_partner(org_name, partners_by_norm) is None:
                unresolved.append(org_name)

        assert unresolved == [], f"batch-A org(s) still do not resolve to a roster entry: {unresolved}"

    def test_batch_a_new_rows_are_present_with_expected_ids(self):
        # The 34 rows this ticket adds (ids 731-764): 17 parks/nature, 4
        # astronomy, 6 museums, 6 libraries, plus "Balboa Park" (named in
        # the ticket's own org_name-match list even though it isn't one of
        # the four named categories -- see ticket 003 Notes).
        partners = _load_partners_json()
        ids = {p["id"] for p in partners}
        expected_new_ids = set(range(731, 765))
        assert expected_new_ids <= ids, f"missing expected new ids: {expected_new_ids - ids}"
        assert len(partners) == 176, f"expected 142 (post-002) + 34 (this ticket) = 176, got {len(partners)}"

"""Dataset-validity regression tests for the curated Hack Club chapters
roster (`partner_scrape/directory/data/hack-club-sd.tsv`), and for the
whole `directory/` package's data as it stands after ticket 018-008.

Data-only-ticket tests, matching sprint.md's Test Strategy precedent
for a curated dataset (ticket 003's own `TestBatchARegistryJoinIntegrity`
class, and `tests/directory/test_dataset_validity.py`'s own precedent
for the Places roster): these pin down properties of the *real*
committed data -- unique ids, the four named chapters present, no
live-geocoded coordinate, and (this ticket's own explicit exclusion)
San Diego Math Circle/SDAA never appearing as `Club` records -- rather
than a synthetic fixture, so a future edit to `hack-club-sd.tsv` that
regresses one of these is caught directly.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from partner_scrape.directory.model import VALID_CLUB_TYPES
from partner_scrape.directory.pipeline import DEFAULT_GEO_DATA_DIR, run_directory
from partner_scrape.directory.sources.base import run_club_source
from partner_scrape.directory.sources.hack_club_static_roster import HackClubStaticRosterSource
from partner_scrape.registry.loader import load_active_sources

# -- ticket 004 (issue 48): the real, committed places.toml carries 17
# related_partner_id references; run_directory() now validates those
# before export, so this class's real-registry-against-a-fake-site_dir
# pattern needs a partners.json fixture with a matching `id` for each
# one. Parsed straight out of the real places.toml text rather than
# hand-listed, so this can never drift from the data it stands in for
# -- mirrors tests/directory/test_pipeline.py's identical fixture. ----


def _write_real_partners_fixture(site_dir: Path) -> None:
    text = (DEFAULT_GEO_DATA_DIR / "places.toml").read_text(encoding="utf-8")
    ids = sorted({int(m) for m in re.findall(r"related_partner_id\s*=\s*(\d+)", text)})
    data_dir = site_dir / "src" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    partners = [{"id": pid, "name": f"Fixture Partner {pid}"} for pid in ids]
    (data_dir / "partners.json").write_text(json.dumps(partners), encoding="utf-8")

DIRECTORY_REGISTRY_DIR = (
    Path(__file__).resolve().parents[2] / "partner_scrape" / "directory" / "registry"
)

# site/src/pages/partners/index.astro's own SD_BOUNDS -- the same
# bounding box tests/directory/test_dataset_validity.py's own
# TestInBoundsCoordinates checks Place coordinates against.
SD_BOUNDS = {"latMin": 32.4, "latMax": 33.5, "lngMin": -117.7, "lngMax": -116.0}

# Explicit exclusions per sprint.md's Design Rationale / issue 35's
# scope split: single organizations that belong to the partner
# roster / event-source registry, never the Club model, to prevent
# future double-registration.
_EXCLUDED_NAME_FRAGMENTS = ("math circle", "sdaa")


class _NeverCalledFetcher:
    def get(self, url, headers=None):
        raise AssertionError("must never call the injected Fetcher")


def _real_clubs():
    sources = load_active_sources(DIRECTORY_REGISTRY_DIR)
    hack_club_source = next(s for s in sources if s.adapter_type == "hack_club_static_roster")
    return run_club_source(hack_club_source, HackClubStaticRosterSource(), _NeverCalledFetcher())


class TestUniqueIds:
    def test_every_club_id_is_unique(self):
        ids = [c.club_id for c in _real_clubs()]
        assert len(ids) == len(set(ids))

    def test_no_club_id_is_blank(self):
        assert all(c.club_id for c in _real_clubs())


class TestChapterCoverage:
    def test_every_chapter_issue_35_names_is_present(self):
        clubs = _real_clubs()
        host_schools = {c.host_school for c in clubs}

        assert host_schools == {
            "University City High School",
            "La Jolla High School",
            "Helix Charter High School",
            "Mater Dei Catholic High School",
        }

    def test_at_least_four_chapters_curated(self):
        assert len(_real_clubs()) >= 4

    def test_every_club_type_is_a_recognized_type(self):
        for club in _real_clubs():
            assert club.club_type in VALID_CLUB_TYPES


class TestNoExcludedOrganizations:
    """AC: San Diego Math Circle and SDAA are not present as Club
    records anywhere in directory/'s data -- they are single
    organizations belonging to the partner roster / event-source
    registry, not multi-chapter clubs (sprint.md's Design Rationale)."""

    def test_no_club_name_or_host_school_mentions_an_excluded_organization(self):
        for club in _real_clubs():
            haystack = f"{club.name} {club.host_school}".lower()
            for fragment in _EXCLUDED_NAME_FRAGMENTS:
                assert fragment not in haystack, (club.club_id, fragment)


class TestNoLiveGeocodedCoordinate:
    """AC: each chapter's location precision comes from the shared
    geo-ladder, including a real attempt at the school-matching rung --
    never a guessed coordinate. The static-roster source itself never
    sets a coordinate at all (see sources/hack_club_static_roster.py's
    own docstring); this is the dataset-level half of that guarantee,
    the pipeline-level half is tests/directory/test_pipeline.py's
    TestApplyClubGeocoding / TestRunDirectoryRealFixtureData."""

    def test_the_static_roster_source_itself_never_sets_a_coordinate(self):
        for club in _real_clubs():
            assert club.latitude is None
            assert club.longitude is None
            assert club.location_precision == "none"


class TestRealPipelineGeocodingResolvesEveryChapterHonestly:
    """End-to-end: every real curated chapter, run through the real
    committed directory/data/ school directories, resolves via the
    shared ladder's actual school-matching rungs -- not a guess, not a
    fixture stand-in."""

    def _real_geocoded_clubs(self, tmp_path):
        _write_real_partners_fixture(tmp_path / "unused")
        payload = run_directory(
            fetcher=_NeverCalledFetcher(), dry_run=True, site_dir=tmp_path / "unused"
        )
        return payload["clubs"]

    def test_every_chapter_gets_school_precision(self, tmp_path):
        for club in self._real_geocoded_clubs(tmp_path):
            assert club["location_precision"] == "school", club["club_id"]

    def test_every_chapters_coordinate_is_within_sd_bounds(self, tmp_path):
        for club in self._real_geocoded_clubs(tmp_path):
            assert SD_BOUNDS["latMin"] <= club["latitude"] <= SD_BOUNDS["latMax"], club["club_id"]
            assert (
                SD_BOUNDS["lngMin"] <= club["longitude"] <= SD_BOUNDS["lngMax"]
            ), club["club_id"]

    def test_matched_name_is_never_blank_for_a_resolved_chapter(self, tmp_path):
        for club in self._real_geocoded_clubs(tmp_path):
            assert club["matched_name"]

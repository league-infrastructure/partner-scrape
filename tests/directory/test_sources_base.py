"""Tests for partner_scrape.directory.sources.base: the PlaceSource and
ClubSource protocols and their structural isolation from
partner_scrape.adapters.base and partner_scrape.teams.sources.base.

Mirrors tests/teams/test_sources_base.py's own
`TestNoAdaptersBaseReference` precedent, extended to also forbid an
import of `teams.sources.base` -- see `directory/sources/base.py`'s
own module docstring for why that second boundary is structural here,
not just style.
"""

from __future__ import annotations

import ast
from pathlib import Path

import partner_scrape.directory as directory_pkg
import partner_scrape.directory.sources as directory_sources_pkg
from partner_scrape.directory.model import Club, Offering, Place
from partner_scrape.directory.sources.base import (
    ClubRef,
    OfferingRef,
    PlaceRef,
    RawClubResponse,
    RawOfferingResponse,
    RawPlaceResponse,
    run,
    run_club_source,
    run_offering_source,
)
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.schema import SourceConfig

_FORBIDDEN_PREFIXES = ("partner_scrape.adapters", "partner_scrape.teams")


def _imports_forbidden_module(py_path: Path) -> bool:
    tree = ast.parse(py_path.read_text(), filename=str(py_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name.startswith(prefix)
                for alias in node.names
                for prefix in _FORBIDDEN_PREFIXES
            ):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and any(node.module.startswith(p) for p in _FORBIDDEN_PREFIXES):
                return True
    return False


class TestNoForbiddenModuleReference:
    def test_no_module_in_directory_sources_imports_adapters_or_teams(self):
        pkg_dir = Path(directory_sources_pkg.__file__).resolve().parent
        py_files = sorted(pkg_dir.glob("*.py"))

        # Sanity check the scan itself isn't vacuously true because the
        # directory is empty or misconfigured.
        assert py_files
        assert any(f.name == "static_roster.py" for f in py_files)
        assert any(f.name == "hack_club_static_roster.py" for f in py_files)
        assert any(f.name == "offering_static_roster.py" for f in py_files)

        offenders = [f.name for f in py_files if _imports_forbidden_module(f)]
        assert offenders == []

    def test_adapters_base_ADAPTERS_has_no_directory_entry(self):
        from partner_scrape.adapters.base import ADAPTERS

        assert "static_roster" not in ADAPTERS

    def test_no_module_anywhere_under_directory_package_imports_teams(self):
        # Broader than the sources/-only scan above: sprint 018's Design
        # Rationale forbids `directory/` depending on `teams/` anywhere
        # in the package (pipeline.py, export.py, model.py included),
        # not just in sources/ -- both must depend on the shared
        # geo_ladder module instead, never on each other (see
        # geo_ladder.py's own module docstring).
        pkg_dir = Path(directory_pkg.__file__).resolve().parent
        py_files = sorted(pkg_dir.rglob("*.py"))

        assert py_files
        assert any(f.name == "pipeline.py" for f in py_files)

        offenders = [
            str(f.relative_to(pkg_dir))
            for f in py_files
            if _imports_forbidden_module(f)
        ]
        assert offenders == []


class _FakeSource:
    """Minimal PlaceSource double for exercising base.run()'s chaining."""

    def __init__(self, places: list[Place]):
        self._places = places
        self.discover_calls = 0
        self.fetch_calls: list[PlaceRef] = []

    def discover(self, source: SourceConfig, fetcher):
        self.discover_calls += 1
        return [PlaceRef(url="local://places")]

    def fetch(self, ref: PlaceRef, fetcher) -> RawPlaceResponse:
        self.fetch_calls.append(ref)
        response = fetcher.get(ref.url)
        return RawPlaceResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawPlaceResponse, source: SourceConfig):
        return self._places


class _StubFetcher:
    def get(self, url: str, headers=None) -> FetchResponse:
        return FetchResponse(url=url, status=200, headers={}, body="[]")


def _source() -> SourceConfig:
    return SourceConfig(
        source_id="places-sd",
        org_name="San Diego STEM Places (curated static roster)",
        adapter_type="static_roster",
        config={},
    )


class TestRunChaining:
    def test_run_chains_discover_fetch_extract_and_returns_extracted_places(self):
        expected = [Place(place_id="a-place", name="A Place", category="makerspace")]
        source_double = _FakeSource(expected)

        places = run(_source(), source_double, _StubFetcher())

        assert places == expected
        assert source_double.discover_calls == 1
        assert len(source_double.fetch_calls) == 1

    def test_run_returns_empty_list_when_extract_yields_nothing(self):
        source_double = _FakeSource([])

        places = run(_source(), source_double, _StubFetcher())

        assert places == []


class _FakeClubSource:
    """Minimal ClubSource double for exercising run_club_source()'s
    chaining -- parallel to _FakeSource above, for Club instead of
    Place."""

    def __init__(self, clubs: list[Club]):
        self._clubs = clubs
        self.discover_calls = 0
        self.fetch_calls: list[ClubRef] = []

    def discover(self, source: SourceConfig, fetcher):
        self.discover_calls += 1
        return [ClubRef(url="local://clubs")]

    def fetch(self, ref: ClubRef, fetcher) -> RawClubResponse:
        self.fetch_calls.append(ref)
        response = fetcher.get(ref.url)
        return RawClubResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawClubResponse, source: SourceConfig):
        return self._clubs


def _club_source_config() -> SourceConfig:
    return SourceConfig(
        source_id="hack-club-sd",
        org_name="Hack Club San Diego chapters (curated static roster)",
        adapter_type="hack_club_static_roster",
        config={},
    )


class TestRunClubSourceChaining:
    def test_run_club_source_chains_discover_fetch_extract_and_returns_extracted_clubs(self):
        expected = [Club(club_id="a-club", name="A Club", host_school="A High")]
        source_double = _FakeClubSource(expected)

        clubs = run_club_source(_club_source_config(), source_double, _StubFetcher())

        assert clubs == expected
        assert source_double.discover_calls == 1
        assert len(source_double.fetch_calls) == 1

    def test_run_club_source_returns_empty_list_when_extract_yields_nothing(self):
        source_double = _FakeClubSource([])

        clubs = run_club_source(_club_source_config(), source_double, _StubFetcher())

        assert clubs == []


class _FakeOfferingSource:
    """Minimal OfferingSource double for exercising
    run_offering_source()'s chaining -- parallel to
    `_FakeSource`/`_FakeClubSource` above, for `Offering` instead of
    `Place`/`Club`."""

    def __init__(self, offerings: list[Offering]):
        self._offerings = offerings
        self.discover_calls = 0
        self.fetch_calls: list[OfferingRef] = []

    def discover(self, source: SourceConfig, fetcher):
        self.discover_calls += 1
        return [OfferingRef(url="local://offerings")]

    def fetch(self, ref: OfferingRef, fetcher) -> RawOfferingResponse:
        self.fetch_calls.append(ref)
        response = fetcher.get(ref.url)
        return RawOfferingResponse(ref=ref, status=response.status, body=response.body)

    def extract(self, raw: RawOfferingResponse, source: SourceConfig):
        return self._offerings


def _offering_source_config() -> SourceConfig:
    return SourceConfig(
        source_id="offerings-sd",
        org_name="San Diego STEM Offerings (curated static roster)",
        adapter_type="offering_static_roster",
        config={},
    )


class TestRunOfferingSourceChaining:
    def test_run_offering_source_chains_discover_fetch_extract_and_returns_extracted_offerings(
        self,
    ):
        expected = [
            Offering(
                offering_id="a-offering",
                org_name="An Org",
                title="A Title",
                offering_type="volunteer",
            )
        ]
        source_double = _FakeOfferingSource(expected)

        offerings = run_offering_source(_offering_source_config(), source_double, _StubFetcher())

        assert offerings == expected
        assert source_double.discover_calls == 1
        assert len(source_double.fetch_calls) == 1

    def test_run_offering_source_returns_empty_list_when_extract_yields_nothing(self):
        source_double = _FakeOfferingSource([])

        offerings = run_offering_source(_offering_source_config(), source_double, _StubFetcher())

        assert offerings == []

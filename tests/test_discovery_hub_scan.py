"""Tests for partner_scrape.discovery.hub_scan: lead-generation discovery
over one curated hub.

Every test drives ``scan_hub`` through a fixture ``Fetcher`` returning
recorded hub-page HTML (``tests/fixtures/hubs/``) and a fixture Source
Registry directory (``tests/fixtures/hub_scan_registry/``) -- no test
here opens a real network socket, per sprint.md's test strategy for Hub
Scan. ``TestNeverRepublishesHubContent`` is the concrete, testable form
of issue 09's "never republish a hub's own data" mandate: it proves
``scan_hub`` never calls ``normalize.run()``/``export_opportunities()``
and never constructs a real ``Event``, no matter what the fixture hub
page contains.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape.discovery.hub_scan import OrgCandidate, scan_hub
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.hub_schema import HubConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "hubs"
REGISTRY_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "hub_scan_registry"

HUB_ORIGIN = "https://examplehub.org"
CALENDAR_URL = f"{HUB_ORIGIN}/calendar"
ARCHIVE_URL = f"{HUB_ORIGIN}/calendar/archive"
ROBOTS_URL = f"{HUB_ORIGIN}/robots.txt"

_ALLOW_ALL_ROBOTS = "User-agent: *\nDisallow:\n"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if hub_scan fetches something it shouldn't (e.g. a
    robots.txt-disallowed hub page).
    """

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _hub(page_urls: list[str] | None = None, hub_id: str = "example_hub") -> HubConfig:
    return HubConfig(
        hub_id=hub_id,
        hub_name="Example Hub",
        page_urls=page_urls if page_urls is not None else [CALENDAR_URL],
    )


class TestFetchesConfiguredHubPages:
    def test_fetches_resolved_page_url_via_injected_fetcher(self):
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
            }
        )

        scan_hub(_hub(), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)

        assert CALENDAR_URL in fetcher.calls


class TestDedupAgainstExistingSources:
    def test_org_matching_existing_source_by_domain_is_filtered_out(self):
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
            }
        )

        candidates = scan_hub(_hub(), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)

        org_names = {c.org_name for c in candidates}
        assert "Existing Org By Domain" not in org_names

    def test_org_matching_existing_source_by_normalized_name_is_filtered_out(self):
        # Linked from a domain (totally-different-domain.org) that does
        # NOT match any fixture source's site_url -- only the normalized
        # org_name match should cause this one to be filtered.
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
            }
        )

        candidates = scan_hub(_hub(), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)

        org_names = {c.org_name for c in candidates}
        assert "Existing Org By Name" not in org_names


class TestNewOrgsSurfaced:
    def test_genuinely_new_orgs_surface_as_candidates(self):
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
            }
        )

        candidates = scan_hub(_hub(), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)

        org_names = {c.org_name for c in candidates}
        assert org_names == {"Brand New STEM Org", "Another New Org"}

    def test_candidate_fields_are_populated_correctly(self):
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
            }
        )

        candidates = scan_hub(_hub(hub_id="example_hub"), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)
        by_name = {c.org_name: c for c in candidates}

        maker = by_name["Brand New STEM Org"]
        assert maker.candidate_url == "https://newsteme.org/"
        assert "Brand New STEM Org" in maker.evidence_text
        assert "maker projects" in maker.evidence_text
        assert maker.hub_id == "example_hub"

        space = by_name["Another New Org"]
        assert space.candidate_url == "https://anothernew.org/programs/space-camp"
        assert "Another New Org" in space.evidence_text
        assert space.hub_id == "example_hub"

    def test_candidates_are_org_candidate_instances(self):
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
            }
        )

        candidates = scan_hub(_hub(), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)

        assert candidates
        assert all(isinstance(c, OrgCandidate) for c in candidates)


class TestInternalLinksExcluded:
    def test_hub_own_domain_links_are_not_surfaced(self):
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
            }
        )

        candidates = scan_hub(_hub(), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)

        urls = {c.candidate_url for c in candidates}
        for excluded in (
            f"{HUB_ORIGIN}/",
            f"{HUB_ORIGIN}/about",
            f"{HUB_ORIGIN}/contact",
            f"{HUB_ORIGIN}/privacy",
        ):
            assert excluded not in urls


class TestRobotsCompliance:
    def test_disallowed_page_is_skipped_not_fetched(self):
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_read_fixture("robots_disallow_archive.txt")),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
                ARCHIVE_URL: _response(_read_fixture("example_hub_archive.html")),
            }
        )

        candidates = scan_hub(
            _hub(page_urls=[CALENDAR_URL, ARCHIVE_URL]),
            fetcher,
            sources_dir=REGISTRY_FIXTURES_DIR,
        )

        assert ARCHIVE_URL not in fetcher.calls
        assert "Should Never Appear Org" not in {c.org_name for c in candidates}

    def test_disallowed_page_does_not_prevent_other_pages_from_being_scanned(self):
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_read_fixture("robots_disallow_archive.txt")),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
                ARCHIVE_URL: _response(_read_fixture("example_hub_archive.html")),
            }
        )

        candidates = scan_hub(
            _hub(page_urls=[CALENDAR_URL, ARCHIVE_URL]),
            fetcher,
            sources_dir=REGISTRY_FIXTURES_DIR,
        )

        org_names = {c.org_name for c in candidates}
        assert org_names == {"Brand New STEM Org", "Another New Org"}


class TestUnreachableHubPage:
    def test_non_200_status_is_skipped_and_logged(self, caplog):
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response("", status=404),
            }
        )

        with caplog.at_level(logging.WARNING):
            candidates = scan_hub(_hub(), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)

        assert candidates == []
        assert "status" in caplog.text.lower()

    def test_unreachable_page_does_not_raise(self):
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response("", status=500),
            }
        )

        scan_hub(_hub(), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)  # must not raise


class TestNeverRepublishesHubContent:
    """The concrete, testable form of issue 09's "never republish the
    hub's own data" mandate (sprint.md's Test Strategy, SUC-001's
    Acceptance Criteria).
    """

    def test_scan_hub_never_calls_normalize_run(self, monkeypatch):
        # partner_scrape/normalize/__init__.py does
        # `from partner_scrape.normalize.run import run`, which shadows
        # the `run` *submodule* attribute on the `normalize` package with
        # the function itself -- so the function under test (patched
        # here) is what any real caller would actually reach via
        # `normalize.run(...)`, the public entry point sprint.md's
        # Architecture > Normalize & Dedup describes.
        import partner_scrape.normalize as normalize_pkg

        def _boom(*args, **kwargs):
            raise AssertionError("scan_hub must never call normalize.run()")

        monkeypatch.setattr(normalize_pkg, "run", _boom)

        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
            }
        )

        scan_hub(_hub(), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)  # must not raise

    def test_scan_hub_never_calls_export_opportunities(self, monkeypatch):
        import partner_scrape.export.writer as export_writer

        def _boom(*args, **kwargs):
            raise AssertionError("scan_hub must never call export_opportunities()")

        monkeypatch.setattr(export_writer, "export_opportunities", _boom)

        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
            }
        )

        scan_hub(_hub(), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)  # must not raise

    def test_scan_hub_never_writes_opportunities_json(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
            }
        )

        scan_hub(_hub(), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)

        assert not list(tmp_path.rglob("opportunities.json"))

    def test_hub_scan_module_does_not_import_model_event_construction(self):
        # hub_scan.py must never construct a real Event -- proven at the
        # module level: it does not import partner_scrape.model at all.
        import partner_scrape.discovery.hub_scan as hub_scan_module

        assert not hasattr(hub_scan_module, "Event")

    def test_returned_candidates_carry_no_event_shaped_data(self):
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response(_read_fixture("example_hub.html")),
            }
        )

        candidates = scan_hub(_hub(), fetcher, sources_dir=REGISTRY_FIXTURES_DIR)

        assert candidates
        for candidate in candidates:
            assert not hasattr(candidate, "start")
            assert not hasattr(candidate, "provenance")


class TestSourcesDirDefaultsToRealRegistry:
    def test_omitting_sources_dir_checks_the_real_registry(self):
        # No sources_dir override -- dedup runs against the real
        # partner_scrape/registry/sources/ directory. A candidate linking
        # to the real jointheleague.org domain must be filtered out.
        fetcher = FixtureFetcher(
            {
                ROBOTS_URL: _response(_ALLOW_ALL_ROBOTS),
                CALENDAR_URL: _response(
                    '<html><body><p>Presented by '
                    '<a href="https://www.jointheleague.org/classes/">'
                    "The LEAGUE of Amazing Programmers</a>.</p></body></html>"
                ),
            }
        )

        candidates = scan_hub(_hub(), fetcher)

        assert candidates == []

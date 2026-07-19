"""End-to-end fixture proof for jointheleague.org's generic_html source
(sprint 005 ticket 002, SUC-003).

Drives ticket 001's sitemap-diff discovery + the generic_html adapter's
extraction ladder over a fixture set modeled on jointheleague.org's real
sitemap shape (tests/fixtures/sitemaps/jointheleague/): a <sitemapindex>
with one child <urlset> mixing /classes/*, /news/*, and /about/* URLs.
Only /classes/* pages must survive into Events -- discovery/sitemap.py's
existing EVENT_PATH_RE already includes literal "classes" in its
alternation, with zero pattern changes needed for this source.

A second test proves the extracted events' org_name ("The LEAGUE of
Amazing Programmers", exact match to stem-ecosystem's real partners.json
entry, id 287) joins via normalize.run() against a small fixture
partners.json containing that record -- tests/fixtures/partners_with_league.json,
a synthetic fixture, never the real stem-ecosystem checkout.

No test here opens a real network socket: the FixtureFetcher raises
KeyError for any URL it wasn't given a canned response for, so an
accidental fetch of a /news/* or /about/* page (which discovery must
never request in the first place) fails loudly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape.adapters import run
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.normalize.run import run as normalize_run
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "sitemaps" / "jointheleague"
PARTNERS_WITH_LEAGUE = Path(__file__).resolve().parent / "fixtures" / "partners_with_league.json"

SITE_URL = "https://www.jointheleague.org"
ROOT_SITEMAP_URL = f"{SITE_URL}/sitemap-index.xml"
CHILD_SITEMAP_URL = f"{SITE_URL}/sitemap-0.xml"

CLASS_URLS = [
    f"{SITE_URL}/classes/coding-101/",
    f"{SITE_URL}/classes/summer-robotics-camp/",
]
NEWS_URL = f"{SITE_URL}/news/2026/05/12/league-wins-community-award/"
ABOUT_URL = f"{SITE_URL}/about/our-team/"

ORG_NAME = "The LEAGUE of Amazing Programmers"


def _read(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if discovery or the adapter ever fetches a /news/* or
    /about/* page, which must be excluded before any fetch is attempted.
    """

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _source() -> SourceConfig:
    return SourceConfig(
        source_id="jointheleague",
        org_name=ORG_NAME,
        adapter_type="generic_html",
        config={"site_url": SITE_URL, "sitemap_url": ROOT_SITEMAP_URL},
    )


@pytest.fixture(autouse=True)
def _cache_dir(tmp_path, monkeypatch):
    """Point SCRAPE_CACHE_DIR at a tmp_path for every test in this file
    -- no test here ever touches the real configured cache directory.
    """
    monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
    return tmp_path


def _fetcher() -> FixtureFetcher:
    return FixtureFetcher(
        {
            ROOT_SITEMAP_URL: _response(_read("sitemap-index.xml")),
            CHILD_SITEMAP_URL: _response(_read("sitemap-0.xml")),
            CLASS_URLS[0]: _response(_read("class_coding_101.html")),
            CLASS_URLS[1]: _response(_read("class_summer_robotics_camp.html")),
            # Deliberately no entries for NEWS_URL/ABOUT_URL -- KeyError
            # if discovery or the adapter ever fetches either.
        }
    )


class TestDiscoveryIncludesOnlyClassesPages:
    def test_only_classes_urls_become_event_refs(self):
        from partner_scrape.discovery.sitemap import discover_changed_urls

        refs = discover_changed_urls(_source(), _fetcher())

        assert sorted(r.url for r in refs) == sorted(CLASS_URLS)
        assert NEWS_URL not in [r.url for r in refs]
        assert ABOUT_URL not in [r.url for r in refs]


class TestEndToEndDiscoverFetchExtract:
    def test_run_produces_events_only_for_classes_pages(self):
        fetcher = _fetcher()

        events = run(_source(), fetcher)

        assert len(events) == 2
        assert {e.url for e in events} == set(CLASS_URLS)
        titles = {e.title for e in events}
        assert titles == {"Coding 101", "Summer Robotics Camp"}
        assert all(e.kind == "event" for e in events)
        assert all(e.source_id == "jointheleague" for e in events)
        # Neither /news/* nor /about/* was ever fetched -- proves
        # exclusion happens at discovery, before any fetch is attempted.
        assert NEWS_URL not in fetcher.calls
        assert ABOUT_URL not in fetcher.calls

    def test_extraction_ladder_recovers_title_and_description(self):
        fetcher = _fetcher()

        events = run(_source(), fetcher)

        coding_101 = next(e for e in events if e.title == "Coding 101")
        assert "fundamentals of programming" in coding_101.description.lower()

        robotics_camp = next(e for e in events if e.title == "Summer Robotics Camp")
        assert "design, build, and program" in robotics_camp.description.lower()


class TestPartnerJoin:
    def test_extracted_events_join_to_the_real_league_partner_record(self):
        fetcher = _fetcher()
        events = run(_source(), fetcher)

        opportunities = normalize_run(
            events,
            PARTNERS_WITH_LEAGUE,
            source_org_names={"jointheleague": ORG_NAME},
        )

        assert opportunities, "expected at least one opportunity from the fixture events"
        for opp in opportunities:
            assert opp.partner_id == 287
            assert opp.partner_name == ORG_NAME

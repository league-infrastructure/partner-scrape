"""Tests for partner_scrape.adapters.generic_html: the generic_html Adapter.

Drives discover -> fetch -> extract end to end through
``adapters.run``, composing ticket 001's sitemap-diff discovery fixture
(tests/fixtures/sitemaps/events_sitemap.xml) with the ladder's fixture
HTML pages (tests/fixtures/html/) via a FixtureFetcher -- no test here
opens a real network socket, per sprint.md's test strategy. Per-rung
extraction correctness is ticket 002's test_extract_ladder.py's job, not
this file's -- this file is integration + registration only, per the
ticket's Testing plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

from partner_scrape.adapters import ADAPTERS, get_adapter, run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.generic_html import GenericHtmlAdapter
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

SITEMAP_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "sitemaps"
HTML_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "html"

SITE_URL = "https://example.org"
ROOT_SITEMAP_URL = f"{SITE_URL}/sitemap_index.xml"

#: The three event URLs tests/fixtures/sitemaps/events_sitemap.xml
#: contains (ticket 001's fixture, reused as-is per this ticket's
#: Testing plan -- "ticket 001's fixtures or equivalent").
EVENT_URLS = [
    "https://example.org/events/tide-pool-exploration/",
    "https://example.org/events/beach-cleanup/",
    "https://example.org/events/star-party/",
]


def _read(path: Path) -> str:
    return path.read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if the adapter under test fetches something it shouldn't.
    """

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _source() -> SourceConfig:
    return SourceConfig(
        source_id="fixture_org",
        org_name="Fixture Org",
        adapter_type="generic_html",
        config={"site_url": SITE_URL},
    )


@pytest.fixture(autouse=True)
def _cache_dir(tmp_path, monkeypatch):
    """Point SCRAPE_CACHE_DIR at a tmp_path for every test in this file
    -- no test here ever touches the real configured cache directory.
    """
    monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
    return tmp_path


class TestRegistration:
    def test_generic_html_is_registered_in_adapters_table(self):
        assert ADAPTERS["generic_html"] is GenericHtmlAdapter

    def test_generic_html_resolves_via_get_adapter(self):
        assert isinstance(get_adapter("generic_html"), GenericHtmlAdapter)


class TestEndToEndDiscoverFetchExtract:
    def test_run_produces_canonical_events_from_sitemap_and_html_fixtures(self):
        fetcher = FixtureFetcher(
            {
                ROOT_SITEMAP_URL: _response(
                    _read(SITEMAP_FIXTURES_DIR / "events_sitemap.xml")
                ),
                EVENT_URLS[0]: _response(_read(HTML_FIXTURES_DIR / "json_ld_event.html")),
                EVENT_URLS[1]: _response(_read(HTML_FIXTURES_DIR / "time_tag_only.html")),
                EVENT_URLS[2]: _response(_read(HTML_FIXTURES_DIR / "opengraph_only.html")),
            }
        )

        events = run(_source(), fetcher)

        titles = {e.title for e in events}
        assert titles == {"Tide Pool Exploration", "Beach Cleanup", "Star Party Night"}
        assert len(events) == 3
        assert all(e.kind == "event" for e in events)
        assert all(e.source_id == "fixture_org" for e in events)
        assert {e.url for e in events} == set(EVENT_URLS)

        tide_pool = next(e for e in events if e.title == "Tide Pool Exploration")
        assert tide_pool.start == datetime.fromisoformat("2026-08-15T09:00:00-07:00")
        assert tide_pool.field_provenance["title"] == Provenance(
            source="generic_html", confidence=1.0
        )

        beach_cleanup = next(e for e in events if e.title == "Beach Cleanup")
        assert beach_cleanup.start == datetime(2026, 9, 1, 10, 0, 0)
        assert beach_cleanup.field_provenance["start"].confidence < 1.0

        star_party = next(e for e in events if e.title == "Star Party Night")
        assert star_party.start is None
        assert "start" not in star_party.field_provenance


class TestNoTitlePerRecordIsolation:
    def test_page_with_no_usable_title_is_dropped_not_emitted_blank(self):
        adapter = GenericHtmlAdapter()
        raw = RawResponse(
            ref=EventRef(url="https://example.org/events/mystery/"),
            status=200,
            body=_read(HTML_FIXTURES_DIR / "no_title.html"),
        )

        assert list(adapter.extract(raw, _source())) == []

    def test_one_bad_page_does_not_fail_the_rest_of_the_source(self):
        fetcher = FixtureFetcher(
            {
                ROOT_SITEMAP_URL: _response(
                    _read(SITEMAP_FIXTURES_DIR / "events_sitemap.xml")
                ),
                EVENT_URLS[0]: _response(_read(HTML_FIXTURES_DIR / "no_title.html")),
                EVENT_URLS[1]: _response(_read(HTML_FIXTURES_DIR / "time_tag_only.html")),
                EVENT_URLS[2]: _response(_read(HTML_FIXTURES_DIR / "opengraph_only.html")),
            }
        )

        events = run(_source(), fetcher)

        titles = {e.title for e in events}
        assert titles == {"Beach Cleanup", "Star Party Night"}
        assert len(events) == 2


class TestExtractRobustness:
    def test_non_200_page_status_returns_no_events_without_raising(self):
        adapter = GenericHtmlAdapter()
        raw = RawResponse(
            ref=EventRef(url="https://example.org/events/x/"), status=500, body=""
        )

        assert list(adapter.extract(raw, _source())) == []

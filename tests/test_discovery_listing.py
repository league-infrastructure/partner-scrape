"""Tests for partner_scrape.discovery.listing: listing-page discovery.

Every test drives ``discover_via_listing`` through a fixture Fetcher
returning recorded listing-page HTML (tests/fixtures/listing/) -- no
test here opens a real network socket, per sprint.md's test strategy for
Listing-Page Discovery. Unlike ``test_discovery_sitemap.py``, no test
here monkeypatches ``SCRAPE_CACHE_DIR`` to hold state across calls --
this module is deliberately stateless (no snapshot, no diffing), and one
test below asserts exactly that: nothing is ever written under
``SCRAPE_CACHE_DIR``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape.discovery.listing import discover_via_listing
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "listing"

SITE_URL = "https://www.fleetscience.org"
LISTING_URL = f"{SITE_URL}/events"

#: The 10 distinct /events/{slug} URLs
#: tests/fixtures/listing/fleet_events_listing.html contains (the first
#: three are each linked twice -- a thumbnail anchor and a title anchor
#: -- to exercise within-page dedup).
EVENT_URLS = [
    f"{SITE_URL}/events/candlelight-concerts",
    f"{SITE_URL}/events/sky-tonight",
    f"{SITE_URL}/events/traveling-with-the-stars",
    f"{SITE_URL}/events/dynamic-earth",
    f"{SITE_URL}/events/whales-giants-of-the-deep",
    f"{SITE_URL}/events/robot-revolution",
    f"{SITE_URL}/events/wildest-weather-in-the-solar-system",
    f"{SITE_URL}/events/national-park-adventure",
    f"{SITE_URL}/events/perfect-little-planet",
    f"{SITE_URL}/events/sea-lions-live",
]


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url="", status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    A URL absent from ``responses`` raises ``KeyError`` -- a loud
    failure if discovery fetches something it shouldn't.
    """

    responses: dict[str, FetchResponse]
    calls: list[str] = field(default_factory=list)

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _source(listing_urls: list[str] | None = None) -> SourceConfig:
    return SourceConfig(
        source_id="fleet-science-center",
        org_name="Fleet Science Center",
        adapter_type="listing_html",
        config={
            "site_url": SITE_URL,
            "listing_urls": listing_urls if listing_urls is not None else ["/events"],
        },
    )


@pytest.fixture(autouse=True)
def _cache_dir(tmp_path, monkeypatch):
    """Point SCRAPE_CACHE_DIR at an empty tmp_path for every test in this
    file -- lets :class:`TestNoDiffing` assert nothing was ever written
    there.
    """
    monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
    return tmp_path


class TestFetchesConfiguredListingUrls:
    def test_fetches_resolved_listing_url_via_injected_fetcher(self):
        fetcher = FixtureFetcher(
            {LISTING_URL: _response(_read_fixture("fleet_events_listing.html"))}
        )

        discover_via_listing(_source(), fetcher)

        assert fetcher.calls == [LISTING_URL]


class TestMatchingLinks:
    def test_yields_one_event_ref_per_matched_link(self):
        fetcher = FixtureFetcher(
            {LISTING_URL: _response(_read_fixture("fleet_events_listing.html"))}
        )

        refs = discover_via_listing(_source(), fetcher)

        assert [r.url for r in refs] == EVENT_URLS

    def test_duplicate_anchors_to_the_same_url_yield_one_ref(self):
        # candlelight-concerts, sky-tonight, and traveling-with-the-stars
        # are each linked twice in the fixture (thumbnail + title anchor).
        fetcher = FixtureFetcher(
            {LISTING_URL: _response(_read_fixture("fleet_events_listing.html"))}
        )

        refs = discover_via_listing(_source(), fetcher)

        urls = [r.url for r in refs]
        assert len(urls) == len(set(urls)) == 10


class TestNonMatchingLinks:
    def test_nav_and_footer_links_are_excluded(self):
        fetcher = FixtureFetcher(
            {LISTING_URL: _response(_read_fixture("fleet_events_listing.html"))}
        )

        refs = discover_via_listing(_source(), fetcher)

        urls = {r.url for r in refs}
        for excluded in (
            f"{SITE_URL}/",
            f"{SITE_URL}/about",
            f"{SITE_URL}/donate",
            f"{SITE_URL}/visit",
            f"{SITE_URL}/careers",
            "https://www.facebook.com/fleetsciencecenter",
        ):
            assert excluded not in urls


class TestUnreachableListingPage:
    def test_non_200_status_yields_zero_refs_and_warns(self, caplog):
        fetcher = FixtureFetcher({LISTING_URL: _response("", status=404)})

        with caplog.at_level(logging.WARNING):
            refs = discover_via_listing(_source(), fetcher)

        assert refs == []
        assert "status" in caplog.text.lower()

    def test_unreachable_page_does_not_raise(self):
        fetcher = FixtureFetcher({LISTING_URL: _response("", status=500)})

        discover_via_listing(_source(), fetcher)  # must not raise

    def test_per_page_isolation_other_listing_pages_still_processed(self):
        broken_url = f"{SITE_URL}/programs"
        fetcher = FixtureFetcher(
            {
                LISTING_URL: _response(_read_fixture("fleet_events_listing.html")),
                broken_url: _response("", status=404),
            }
        )

        refs = discover_via_listing(
            _source(listing_urls=["/events", "/programs"]), fetcher
        )

        assert [r.url for r in refs] == EVENT_URLS


class TestNoDiffing:
    def test_second_call_against_unchanged_fixture_yields_same_refs(self):
        fetcher = FixtureFetcher(
            {LISTING_URL: _response(_read_fixture("fleet_events_listing.html"))}
        )

        first_refs = discover_via_listing(_source(), fetcher)
        second_refs = discover_via_listing(_source(), fetcher)

        assert [r.url for r in first_refs] == EVENT_URLS
        assert [r.url for r in second_refs] == EVENT_URLS

    def test_no_file_written_under_scrape_cache_dir(self, tmp_path):
        fetcher = FixtureFetcher(
            {LISTING_URL: _response(_read_fixture("fleet_events_listing.html"))}
        )

        discover_via_listing(_source(), fetcher)
        discover_via_listing(_source(), fetcher)

        assert list(tmp_path.iterdir()) == []

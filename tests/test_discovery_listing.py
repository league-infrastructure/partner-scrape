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

from partner_scrape.discovery.listing import discover_via_listing, discover_via_selector
from partner_scrape.fetch import DEFAULT_RATE_LIMIT_SECONDS
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


#: UCSD Summer Program Finder fixture (sprint 027 ticket 006 exception
#: revision) -- reproduces the real card shape live-verification found:
#: ``<li data-grade="High School">`` cards whose ``a.learnmore`` links go
#: cross-domain, with no ``/program(s)?``-shaped path segment.
UCSD_SITE_URL = "https://summerprogramfinder.ucsd.edu"
UCSD_LISTING_URL = f"{UCSD_SITE_URL}/finder"
UCSD_LINK_SELECTOR = 'li[data-grade*="High School"] a.learnmore'
#: The three HS-eligible cards' learnmore hrefs, in document order.
UCSD_HS_ELIGIBLE_URLS = [
    "https://cosmos.ucsd.edu/",
    "https://optimus.ucsd.edu/apply",
    "https://enlace.ucsd.edu/info",
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
    #: Every call's rate_limit_seconds/respect_robots, keyed by URL --
    #: sprint 015 ticket 003's acquisition_kwargs() threading, recorded
    #: separately from ``calls`` so existing ``calls == [...]``-style
    #: assertions elsewhere in this file are unaffected.
    policy_calls: dict[str, tuple[float, bool]] = field(default_factory=dict)

    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        rate_limit_seconds: float = 1.0,
        respect_robots: bool = True,
    ) -> FetchResponse:
        self.calls.append(url)
        self.policy_calls[url] = (rate_limit_seconds, respect_robots)
        return self.responses[url]


def _source(
    listing_urls: list[str] | None = None, acquisition_policy: dict | None = None
) -> SourceConfig:
    return SourceConfig(
        source_id="fleet-science-center",
        org_name="Fleet Science Center",
        adapter_type="listing_html",
        config={
            "site_url": SITE_URL,
            "listing_urls": listing_urls if listing_urls is not None else ["/events"],
        },
        acquisition_policy=acquisition_policy or {},
    )


def _ucsd_source(
    listing_urls: list[str] | None = None,
    link_selector: str = UCSD_LINK_SELECTOR,
    acquisition_policy: dict | None = None,
) -> SourceConfig:
    return SourceConfig(
        source_id="ucsd-summer-program-finder",
        org_name="UCSD Summer Program Finder",
        adapter_type="program_listing",
        config={
            "site_url": UCSD_SITE_URL,
            "listing_urls": listing_urls if listing_urls is not None else ["/finder"],
            "link_selector": link_selector,
        },
        acquisition_policy=acquisition_policy or {},
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


class TestAcquisitionPolicyThreading:
    def test_sources_acquisition_policy_reaches_fetcher_get(self):
        fetcher = FixtureFetcher(
            {LISTING_URL: _response(_read_fixture("fleet_events_listing.html"))}
        )
        source = _source(acquisition_policy={"rate_limit_seconds": 8.0, "respect_robots": False})

        discover_via_listing(source, fetcher)

        assert fetcher.policy_calls[LISTING_URL] == (8.0, False)

    def test_source_with_no_acquisition_policy_still_gets_polite_fetcher_defaults(self):
        fetcher = FixtureFetcher(
            {LISTING_URL: _response(_read_fixture("fleet_events_listing.html"))}
        )

        discover_via_listing(_source(), fetcher)

        assert fetcher.policy_calls[LISTING_URL] == (DEFAULT_RATE_LIMIT_SECONDS, True)


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


class TestDiscoverViaSelector:
    """``discover_via_selector`` -- the CSS-selector-driven sibling to
    ``discover_via_listing`` (sprint 027 ticket 006 exception revision).
    Driven against a fixture reproducing the UCSD Summer Program Finder's
    real card shape: ``<li data-grade="High School">`` cards whose
    ``a.learnmore`` links go cross-domain with no ``/program(s)?``-shaped
    path segment -- live-verification found 0 of the 24 real HS-eligible
    cards among the links ``EVENT_PATH_RE`` matched.
    """

    def test_returns_matched_links_that_event_path_re_would_not_have(self):
        fetcher = FixtureFetcher(
            {UCSD_LISTING_URL: _response(_read_fixture("ucsd_summer_program_finder.html"))}
        )

        refs = discover_via_selector(_ucsd_source(), fetcher)

        assert [r.url for r in refs] == UCSD_HS_ELIGIBLE_URLS

        # Prove EVENT_PATH_RE-based discover_via_listing would not have
        # found these same three HS-eligible cards -- it matches a wholly
        # different link (the nav's "/programs" listing-index link, which
        # is not any of the three cards' own learnmore hrefs), matching
        # the real 0-of-24 finding this revision's exception documented.
        listing_refs = discover_via_listing(_ucsd_source(), fetcher)
        listing_urls = {r.url for r in listing_refs}
        assert listing_urls.isdisjoint(UCSD_HS_ELIGIBLE_URLS)

    def test_excludes_cards_the_selector_does_not_match(self):
        fetcher = FixtureFetcher(
            {UCSD_LISTING_URL: _response(_read_fixture("ucsd_summer_program_finder.html"))}
        )

        refs = discover_via_selector(_ucsd_source(), fetcher)

        urls = {r.url for r in refs}
        for excluded in ("https://msexplorers.ucsd.edu/", "https://ugresearch.ucsd.edu/"):
            assert excluded not in urls

    def test_links_are_cross_domain_with_no_domain_restriction(self):
        """No cross-domain filtering happens -- matching
        ``discover_via_listing``'s own already-accepted absence of a
        domain check (this doc's design docs, both Revision notes)."""
        fetcher = FixtureFetcher(
            {UCSD_LISTING_URL: _response(_read_fixture("ucsd_summer_program_finder.html"))}
        )

        refs = discover_via_selector(_ucsd_source(), fetcher)

        for url in UCSD_HS_ELIGIBLE_URLS:
            assert not url.startswith(UCSD_SITE_URL)
        assert [r.url for r in refs] == UCSD_HS_ELIGIBLE_URLS

    def test_no_matching_elements_yields_zero_refs(self):
        fetcher = FixtureFetcher(
            {UCSD_LISTING_URL: _response(_read_fixture("ucsd_summer_program_finder.html"))}
        )

        refs = discover_via_selector(
            _ucsd_source(link_selector="li[data-grade*=\"Preschool\"] a.learnmore"), fetcher
        )

        assert refs == []

    def test_non_200_status_yields_zero_refs_and_warns(self, caplog):
        fetcher = FixtureFetcher({UCSD_LISTING_URL: _response("", status=404)})

        with caplog.at_level(logging.WARNING):
            refs = discover_via_selector(_ucsd_source(), fetcher)

        assert refs == []
        assert "status" in caplog.text.lower()

    def test_unreachable_page_does_not_raise(self):
        fetcher = FixtureFetcher({UCSD_LISTING_URL: _response("", status=500)})

        discover_via_selector(_ucsd_source(), fetcher)  # must not raise

    def test_per_page_isolation_other_listing_pages_still_processed(self):
        broken_url = f"{UCSD_SITE_URL}/other-finder"
        fetcher = FixtureFetcher(
            {
                UCSD_LISTING_URL: _response(_read_fixture("ucsd_summer_program_finder.html")),
                broken_url: _response("", status=404),
            }
        )

        refs = discover_via_selector(
            _ucsd_source(listing_urls=["/finder", "/other-finder"]), fetcher
        )

        assert [r.url for r in refs] == UCSD_HS_ELIGIBLE_URLS

    def test_sources_acquisition_policy_reaches_fetcher_get(self):
        fetcher = FixtureFetcher(
            {UCSD_LISTING_URL: _response(_read_fixture("ucsd_summer_program_finder.html"))}
        )
        source = _ucsd_source(acquisition_policy={"rate_limit_seconds": 8.0, "respect_robots": False})

        discover_via_selector(source, fetcher)

        assert fetcher.policy_calls[UCSD_LISTING_URL] == (8.0, False)

    def test_no_file_written_under_scrape_cache_dir(self, tmp_path):
        fetcher = FixtureFetcher(
            {UCSD_LISTING_URL: _response(_read_fixture("ucsd_summer_program_finder.html"))}
        )

        discover_via_selector(_ucsd_source(), fetcher)
        discover_via_selector(_ucsd_source(), fetcher)

        assert list(tmp_path.iterdir()) == []

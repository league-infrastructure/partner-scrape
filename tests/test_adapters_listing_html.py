"""Tests for partner_scrape.adapters.listing_html: the listing_html Adapter.

Drives discover -> fetch -> extract end to end through ``adapters.run``,
composing ticket 003's listing-page discovery fixture
(tests/fixtures/listing/fleet_events_listing.html) with a synthesized
Fleet-style detail-page fixture (tests/fixtures/html/fleet_style_*.html --
no JSON-LD, no ``<time>`` tag, matching Fleet's confirmed real page shape)
via a FixtureFetcher -- no test here opens a real network socket, per
sprint.md's test strategy. Per-rung extraction correctness is
test_extract_ladder.py's job and discover()'s own link-matching logic is
test_discovery_listing.py's job -- this file is integration + registration
+ delegation only, matching test_adapters_generic_html.py's own scope note
for its sibling adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from partner_scrape.adapters import ADAPTERS, get_adapter, run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.listing_html import ListingHtmlAdapter
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

LISTING_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "listing"
HTML_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "html"

SITE_URL = "https://www.fleetscience.org"
LISTING_URL = f"{SITE_URL}/events"

#: The 10 distinct /events/{slug} URLs
#: tests/fixtures/listing/fleet_events_listing.html contains -- ticket
#: 003's own fixture, reused as-is per this ticket's Testing plan
#: ("composing ticket 003's discovery fixtures").
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
        source_id="fleet-science-center",
        org_name="Fleet Science Center",
        adapter_type="listing_html",
        config={"site_url": SITE_URL, "listing_urls": ["/events"]},
    )


class TestRegistration:
    def test_listing_html_is_registered_in_adapters_table(self):
        assert ADAPTERS["listing_html"] is ListingHtmlAdapter

    def test_listing_html_resolves_via_get_adapter(self):
        assert isinstance(get_adapter("listing_html"), ListingHtmlAdapter)


class TestDiscoverDelegatesToListingDiscovery:
    def test_discover_returns_one_ref_per_matched_listing_link(self):
        fetcher = FixtureFetcher(
            {LISTING_URL: _response(_read(LISTING_FIXTURES_DIR / "fleet_events_listing.html"))}
        )
        adapter = ListingHtmlAdapter()

        refs = list(adapter.discover(_source(), fetcher))

        assert [r.url for r in refs] == EVENT_URLS

    def test_discover_has_no_matching_logic_of_its_own(self, monkeypatch):
        """``discover()`` must delegate entirely to
        ``discovery.listing.discover_via_listing`` -- proven here by
        substituting a fake and checking the adapter passes its
        arguments through and returns its result verbatim, with no
        transformation in between.
        """
        sentinel_refs = [EventRef(url="https://www.fleetscience.org/events/sentinel")]
        captured: dict[str, object] = {}

        def fake_discover_via_listing(source, fetcher):
            captured["source"] = source
            captured["fetcher"] = fetcher
            return sentinel_refs

        monkeypatch.setattr(
            "partner_scrape.discovery.listing.discover_via_listing",
            fake_discover_via_listing,
        )

        adapter = ListingHtmlAdapter()
        source = _source()
        fetcher = FixtureFetcher({})

        refs = adapter.discover(source, fetcher)

        assert refs is sentinel_refs
        assert captured["source"] is source
        assert captured["fetcher"] is fetcher


class TestEndToEndDiscoverFetchExtract:
    def test_run_produces_canonical_events_via_lower_ladder_rungs(self):
        # Every discovered detail page is Fleet-style: no JSON-LD, no
        # <time> tag (matching Fleet's confirmed real page shape), so
        # only the OpenGraph rung fires here -- proves discover() and
        # extract() are correctly wired together through adapters.run,
        # reusing the unchanged extraction ladder.
        opengraph_body = _read(HTML_FIXTURES_DIR / "fleet_style_opengraph.html")
        responses = {
            LISTING_URL: _response(
                _read(LISTING_FIXTURES_DIR / "fleet_events_listing.html")
            ),
            **{url: _response(opengraph_body) for url in EVENT_URLS},
        }
        fetcher = FixtureFetcher(responses)

        events = run(_source(), fetcher)

        assert len(events) == 10
        assert all(e.kind == "event" for e in events)
        assert all(e.source_id == "fleet-science-center" for e in events)
        assert {e.url for e in events} == set(EVENT_URLS)
        assert all(e.title == "Candlelight Concerts" for e in events)

        first = events[0]
        assert first.field_provenance["title"] == Provenance(
            source="listing_html", confidence=0.6
        )
        # No JSON-LD/<time> markup on the fixture page -- no date rung
        # could fire, so the event is undated at extraction time (per
        # sprint.md's Design Rationale: the LLM Enricher recovers this
        # downstream, not this adapter).
        assert first.start is None


class TestExtractPerRungFallback:
    def test_opengraph_only_page_still_yields_an_event(self):
        adapter = ListingHtmlAdapter()
        raw = RawResponse(
            ref=EventRef(url=f"{SITE_URL}/events/candlelight-concerts"),
            status=200,
            body=_read(HTML_FIXTURES_DIR / "fleet_style_opengraph.html"),
        )

        events = list(adapter.extract(raw, _source()))

        assert len(events) == 1
        event = events[0]
        assert event.title == "Candlelight Concerts"
        assert event.field_provenance["title"] == Provenance(
            source="listing_html", confidence=0.6
        )

    def test_title_fallback_only_page_still_yields_an_event(self):
        adapter = ListingHtmlAdapter()
        raw = RawResponse(
            ref=EventRef(url=f"{SITE_URL}/events/sky-tonight"),
            status=200,
            body=_read(HTML_FIXTURES_DIR / "fleet_style_title_fallback.html"),
        )

        events = list(adapter.extract(raw, _source()))

        assert len(events) == 1
        event = events[0]
        assert event.title == "Sky Tonight"
        assert event.field_provenance["title"] == Provenance(
            source="listing_html", confidence=0.5
        )


class TestNoTitlePerRecordIsolation:
    def test_page_with_no_usable_title_is_dropped_not_emitted_blank(self):
        adapter = ListingHtmlAdapter()
        raw = RawResponse(
            ref=EventRef(url=f"{SITE_URL}/events/mystery"),
            status=200,
            body=_read(HTML_FIXTURES_DIR / "no_title.html"),
        )

        assert list(adapter.extract(raw, _source())) == []

    def test_one_bad_page_does_not_fail_the_rest_of_the_source(self):
        opengraph_body = _read(HTML_FIXTURES_DIR / "fleet_style_opengraph.html")
        no_title_body = _read(HTML_FIXTURES_DIR / "no_title.html")
        responses = {
            LISTING_URL: _response(
                _read(LISTING_FIXTURES_DIR / "fleet_events_listing.html")
            ),
            **{url: _response(opengraph_body) for url in EVENT_URLS},
        }
        responses[EVENT_URLS[0]] = _response(no_title_body)
        fetcher = FixtureFetcher(responses)

        events = run(_source(), fetcher)

        assert len(events) == 9
        assert EVENT_URLS[0] not in {e.url for e in events}


class TestExtractRobustness:
    def test_non_200_page_status_returns_no_events_without_raising(self):
        adapter = ListingHtmlAdapter()
        raw = RawResponse(
            ref=EventRef(url=f"{SITE_URL}/events/x"), status=500, body=""
        )

        assert list(adapter.extract(raw, _source())) == []

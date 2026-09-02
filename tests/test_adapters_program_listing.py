"""Tests for partner_scrape.adapters.program_page: the ``program_listing``
adapter (``ProgramListingAdapter``).

Sprint 027 ticket 004. Mirrors ``tests/test_adapters_listing_html.py``'s
structure for the discovery half (a fixture listing page crawled via
``discovery.listing.discover_via_listing``) and
``tests/test_adapters_program_page.py``'s structure for the extraction
half (``FixtureProgramLLMClient`` over saved page fixtures) -- no test
here opens a real network socket or calls the real Anthropic API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from partner_scrape.adapters import ADAPTERS, get_adapter
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.program_cache import ProgramExtractionCache
from partner_scrape.adapters.program_llm import (
    FixtureProgramLLMClient,
    ProgramExtractionResult,
)
from partner_scrape.adapters.program_page import ProgramListingAdapter, ProgramPageAdapter
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "program_pages"

SITE_URL = "https://example.org"
LISTING_URL = f"{SITE_URL}/programs"

#: The three distinct /programs/{slug} URLs
#: tests/fixtures/program_pages/listing_card_page.html contains (ticket
#: 002's own fixture, seeded for this ticket -- reused as-is).
CARD_URLS = [
    f"{SITE_URL}/programs/fixture-coastal-ecology",
    f"{SITE_URL}/programs/fixture-data-science-academy",
    f"{SITE_URL}/programs/fixture-ocean-robotics-lab",
]

_DETAIL_FIXTURES = {
    CARD_URLS[0]: "listing_card_detail_coastal_ecology.html",
    CARD_URLS[1]: "listing_card_detail_data_science_academy.html",
    CARD_URLS[2]: "listing_card_detail_ocean_robotics_lab.html",
}


def _read(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _listing_body() -> str:
    return _read("listing_card_page.html")


def _detail_body(url: str) -> str:
    return _read(_DETAIL_FIXTURES[url])


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

    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        rate_limit_seconds: float = 1.0,
        respect_robots: bool = True,
    ) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _source(
    program_kind: str | None = "internship",
    site_url: str = SITE_URL,
    listing_urls: list[str] | None = None,
) -> SourceConfig:
    config: dict = {"site_url": site_url, "listing_urls": listing_urls or ["/programs"]}
    if program_kind is not None:
        config["program_kind"] = program_kind
    return SourceConfig(
        source_id="fixture_program_listing",
        org_name="Fixture Program Listing",
        adapter_type="program_listing",
        config=config,
    )


#: One distinct, independently-authored ProgramExtractionResult per card
#: URL -- proves per-record independence (AC 2): no two discovered
#: programs share an audience/grade/deadline/eligibility value.
_RESULTS: dict[str, ProgramExtractionResult] = {
    CARD_URLS[0]: ProgramExtractionResult(
        program_name="Fixture Coastal Ecology Program",
        audience_grades=["9th grade", "10th grade", "11th grade", "12th grade"],
        date_start="2026-12-15",
        date_end="2027-03-01",
        cost="Free",
        eligibility="Current 9th-12th grade students.",
        is_open=True,
        opportunity_type="Out-of-school Programs",
    ),
    CARD_URLS[1]: ProgramExtractionResult(
        program_name="Fixture Data Science Academy",
        audience_grades=["10th grade", "11th grade", "12th grade"],
        date_start="",
        date_end="",
        cost="$150 program fee",
        eligibility="Current 10th-12th grade students with at least one year of algebra.",
        is_open=True,
        opportunity_type="Out-of-school Programs",
    ),
    CARD_URLS[2]: ProgramExtractionResult(
        program_name="Fixture Ocean Robotics Lab",
        audience_grades=["11th grade", "12th grade"],
        date_start="2027-06-01",
        date_end="2027-01-15",
        cost="$1,000 stipend",
        eligibility="Current 11th and 12th grade students residing in San Diego County.",
        is_open=False,
        opportunity_type="Out-of-school Programs",
    ),
}


def _llm_client() -> FixtureProgramLLMClient:
    return FixtureProgramLLMClient(responses=dict(_RESULTS))


def _run(adapter: ProgramListingAdapter, source: SourceConfig, fetcher: FixtureFetcher) -> list:
    """Chain discover -> fetch -> extract against ``adapter`` directly,
    mirroring ``adapters.base.run()``'s logic exactly (materialize
    ``discover()``, then fetch+extract each ref in turn).

    ``adapters.run()`` itself cannot be used here: it always constructs
    its own adapter via ``get_adapter()``, with no way to inject a
    ``FixtureProgramLLMClient``/test ``ProgramExtractionCache`` -- the
    same reason ``test_adapters_program_page.py``'s own end-to-end tests
    drive the adapter's methods directly rather than going through
    ``adapters.run()``.
    """
    refs = list(adapter.discover(source, fetcher))
    events = []
    for ref in refs:
        raw = adapter.fetch(ref, fetcher, source)
        events.extend(adapter.extract(raw, source))
    return events


class TestRegistration:
    def test_program_listing_is_registered_in_adapters_table(self):
        assert ADAPTERS["program_listing"] is ProgramListingAdapter

    def test_program_listing_resolves_via_get_adapter(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
        adapter = get_adapter("program_listing")

        assert isinstance(adapter, ProgramListingAdapter)


class TestDiscover:
    def test_discover_returns_one_ref_per_matched_card_link(self, tmp_path):
        adapter = ProgramListingAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        fetcher = FixtureFetcher({LISTING_URL: _response(_listing_body())})

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == CARD_URLS

    def test_discover_delegates_entirely_to_discovery_listing(self, tmp_path, monkeypatch):
        """``discover()`` must delegate entirely to
        ``discovery.listing.discover_via_listing`` -- proven by
        substituting a fake and checking the adapter passes its
        arguments through and returns its result verbatim.
        """
        sentinel_refs = [EventRef(url="https://example.org/programs/sentinel")]
        captured: dict[str, object] = {}

        def fake_discover_via_listing(source, fetcher):
            captured["source"] = source
            captured["fetcher"] = fetcher
            return sentinel_refs

        monkeypatch.setattr(
            "partner_scrape.discovery.listing.discover_via_listing",
            fake_discover_via_listing,
        )

        adapter = ProgramListingAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        source = _source()
        fetcher = FixtureFetcher({})

        refs = adapter.discover(source, fetcher)

        assert refs is sentinel_refs
        assert captured["source"] is source
        assert captured["fetcher"] is fetcher


class TestEndToEndExtraction:
    def test_n_cards_yield_n_distinct_independently_extracted_events(self, tmp_path):
        responses = {
            LISTING_URL: _response(_listing_body()),
            **{url: _response(_detail_body(url)) for url in CARD_URLS},
        }
        fetcher = FixtureFetcher(responses)
        adapter = ProgramListingAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        source = _source()

        events = _run(adapter, source, fetcher)

        assert len(events) == 3
        assert {e.url for e in events} == set(CARD_URLS)
        assert all(e.kind == "internship" for e in events)
        assert all(e.source_id == "fixture_program_listing" for e in events)

        by_url = {e.url: e for e in events}

        coastal = by_url[CARD_URLS[0]]
        assert coastal.title == "Fixture Coastal Ecology Program"
        assert coastal.start == datetime.fromisoformat("2026-12-15")
        assert coastal.end == datetime.fromisoformat("2027-03-01")
        assert coastal.eligibility == "Current 9th-12th grade students."
        assert coastal.cost == "Free"

        data_science = by_url[CARD_URLS[1]]
        assert data_science.title == "Fixture Data Science Academy"
        assert data_science.start is None
        assert data_science.end is None
        assert data_science.eligibility == (
            "Current 10th-12th grade students with at least one year of algebra."
        )
        assert data_science.cost == "$150 program fee"

        robotics = by_url[CARD_URLS[2]]
        assert robotics.title == "Fixture Ocean Robotics Lab"
        assert robotics.eligibility == (
            "Current 11th and 12th grade students residing in San Diego County."
        )
        assert robotics.cost == "$1,000 stipend"

        # No two cards share a value -- proves independent, per-record
        # extraction rather than one blended value applied to all three.
        assert len({e.eligibility for e in events}) == 3
        assert len({e.cost for e in events}) == 3
        assert len({e.title for e in events}) == 3

    def test_llm_client_called_once_per_discovered_card(self, tmp_path):
        responses = {
            LISTING_URL: _response(_listing_body()),
            **{url: _response(_detail_body(url)) for url in CARD_URLS},
        }
        fetcher = FixtureFetcher(responses)
        llm_client = _llm_client()
        adapter = ProgramListingAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))

        _run(adapter, _source(), fetcher)

        assert sorted(url for url, _body in llm_client.calls) == sorted(CARD_URLS)
        assert len(llm_client.calls) == 3


class TestPerCardIsolation:
    def test_a_card_whose_fetch_fails_is_skipped_but_the_rest_still_yield_events(self, tmp_path):
        responses = {
            LISTING_URL: _response(_listing_body()),
            CARD_URLS[0]: _response("", status=500),
            CARD_URLS[1]: _response(_detail_body(CARD_URLS[1])),
            CARD_URLS[2]: _response(_detail_body(CARD_URLS[2])),
        }
        fetcher = FixtureFetcher(responses)
        adapter = ProgramListingAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))

        events = _run(adapter, _source(), fetcher)

        assert len(events) == 2
        assert CARD_URLS[0] not in {e.url for e in events}
        assert {e.url for e in events} == {CARD_URLS[1], CARD_URLS[2]}


class TestSharesExtractionLogicWithProgramPageAdapter:
    def test_both_adapters_produce_an_identical_event_from_the_same_raw_response(self, tmp_path):
        """Proves the ticket 003 refactor into a shared helper didn't
        fork behavior between the two adapter types: given the exact
        same fetched raw response and source, ``ProgramPageAdapter`` and
        ``ProgramListingAdapter`` must produce an identical ``Event``
        (the ``EventRef`` that reached them is the same here too, since
        both take the same ``raw.ref``).
        """
        url = CARD_URLS[0]
        body = _detail_body(url)
        result = _RESULTS[url]
        raw = RawResponse(ref=EventRef(url=url), status=200, body=body)
        source = _source()

        page_adapter = ProgramPageAdapter(
            llm_client=FixtureProgramLLMClient(responses={url: result}),
            cache=ProgramExtractionCache(tmp_path / "page"),
        )
        listing_adapter = ProgramListingAdapter(
            llm_client=FixtureProgramLLMClient(responses={url: result}),
            cache=ProgramExtractionCache(tmp_path / "listing"),
        )

        page_events = list(page_adapter.extract(raw, source))
        listing_events = list(listing_adapter.extract(raw, source))

        assert len(page_events) == len(listing_events) == 1
        assert page_events[0] == listing_events[0]

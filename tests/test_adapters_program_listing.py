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

import logging
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


class TestDiscoverRoutesOnLinkSelector:
    """``ProgramListingAdapter.discover()`` routes to
    ``discovery.listing.discover_via_selector`` only when
    ``source.config["link_selector"]`` is set (sprint 027 ticket 006
    exception revision); otherwise it falls back to today's
    ``discover_via_listing`` unchanged -- proven here by substituting a
    fake for each and checking the adapter calls the right one.
    """

    def test_no_link_selector_calls_discover_via_listing(self, tmp_path, monkeypatch):
        captured: dict[str, object] = {}

        def fake_discover_via_listing(source, fetcher):
            captured["called"] = "discover_via_listing"
            return [EventRef(url="https://example.org/programs/sentinel")]

        def fake_discover_via_selector(source, fetcher):
            captured["called"] = "discover_via_selector"
            return []

        monkeypatch.setattr(
            "partner_scrape.discovery.listing.discover_via_listing", fake_discover_via_listing
        )
        monkeypatch.setattr(
            "partner_scrape.discovery.listing.discover_via_selector", fake_discover_via_selector
        )

        adapter = ProgramListingAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        source = _source()  # no link_selector key

        refs = adapter.discover(source, FixtureFetcher({}))

        assert captured["called"] == "discover_via_listing"
        assert [r.url for r in refs] == ["https://example.org/programs/sentinel"]

    def test_link_selector_set_calls_discover_via_selector(self, tmp_path, monkeypatch):
        captured: dict[str, object] = {}

        def fake_discover_via_listing(source, fetcher):
            captured["called"] = "discover_via_listing"
            return []

        def fake_discover_via_selector(source, fetcher):
            captured["called"] = "discover_via_selector"
            captured["link_selector"] = source.config["link_selector"]
            return [EventRef(url="https://cross-domain.example.org/homepage")]

        monkeypatch.setattr(
            "partner_scrape.discovery.listing.discover_via_listing", fake_discover_via_listing
        )
        monkeypatch.setattr(
            "partner_scrape.discovery.listing.discover_via_selector", fake_discover_via_selector
        )

        adapter = ProgramListingAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        source = _source()
        source.config["link_selector"] = 'li[data-grade*="High School"] a.learnmore'

        refs = adapter.discover(source, FixtureFetcher({}))

        assert captured["called"] == "discover_via_selector"
        assert captured["link_selector"] == 'li[data-grade*="High School"] a.learnmore'
        assert [r.url for r in refs] == ["https://cross-domain.example.org/homepage"]


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

    def test_a_card_whose_llm_extraction_raises_is_skipped_but_the_rest_still_yield_events(
        self, tmp_path, caplog
    ):
        # Sprint 027 ticket 006's own live verification found a real
        # UCSD Summer Program Finder card (www.rmtlacademy.org) whose
        # fetched body alone exceeded the model's context window,
        # raising anthropic.BadRequestError from inside
        # llm_client.extract_program() -- previously uncaught, which
        # would have aborted this whole card→discover→fetch→extract
        # loop and discarded every other card's already-fetched Event
        # along with it. FixtureProgramLLMClient raises a plain
        # KeyError for a URL absent from its `responses` dict, which
        # exercises the identical "the LLM call itself raised" code
        # path without needing the real Anthropic SDK.
        responses = {
            LISTING_URL: _response(_listing_body()),
            CARD_URLS[0]: _response(_detail_body(CARD_URLS[0])),
            CARD_URLS[1]: _response(_detail_body(CARD_URLS[1])),
            CARD_URLS[2]: _response(_detail_body(CARD_URLS[2])),
        }
        fetcher = FixtureFetcher(responses)
        broken_llm_client = FixtureProgramLLMClient(
            responses={url: result for url, result in _RESULTS.items() if url != CARD_URLS[1]}
        )
        adapter = ProgramListingAdapter(
            llm_client=broken_llm_client, cache=ProgramExtractionCache(tmp_path)
        )

        with caplog.at_level(logging.WARNING):
            events = _run(adapter, _source(), fetcher)

        assert len(events) == 2
        assert CARD_URLS[1] not in {e.url for e in events}
        assert {e.url for e in events} == {CARD_URLS[0], CARD_URLS[2]}
        assert "extract_program" in caplog.text


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


#: Sprint 029 ticket 003 (SUC-046, issue 30): the SD Festival of Science
#: & Engineering / EXPO Day's registered ``program_listing`` source
#: (``registry/sources/sd-festival-of-science-engineering.toml``). This
#: ticket's own required live-verification found the real
#: ``lovestemsd.org`` "Festival Week" listing currently has zero event
#: cards to discover (a content-availability gap between annual cycles --
#: see that TOML file's own header comment and this ticket's Notes), so
#: the source is registered ``enabled = false`` rather than live-proven
#: end-to-end. This fixture test instead proves the *mechanism* SUC-046
#: describes is correctly wired -- discovery via plain ``EVENT_PATH_RE``
#: matching (no ``config.link_selector`` is registered, since there is
#: currently no live card markup to justify one), one independent LLM
#: extraction call per discovered festival-week event, and each record
#: keeping its *own* LLM-classified ``opportunity_type`` (no
#: ``config.opportunity_type`` override, since festival-week events span
#: more than one type) -- so the mechanism is ready the moment the org
#: repopulates the listing.
_SD_FESTIVAL_SITE_URL = "https://lovestemsd.org"
_SD_FESTIVAL_LISTING_URL = f"{_SD_FESTIVAL_SITE_URL}/stem-week-events-2020"

_SD_FESTIVAL_CARD_URLS = [
    f"{_SD_FESTIVAL_SITE_URL}/events/expo-day-2026",
    f"{_SD_FESTIVAL_SITE_URL}/events/steam-design-contest-2026",
    f"{_SD_FESTIVAL_SITE_URL}/events/educator-workshop-2026",
]

_SD_FESTIVAL_DETAIL_FIXTURES = {
    _SD_FESTIVAL_CARD_URLS[0]: "sd_festival_detail_expo_day.html",
    _SD_FESTIVAL_CARD_URLS[1]: "sd_festival_detail_steam_design_contest.html",
    _SD_FESTIVAL_CARD_URLS[2]: "sd_festival_detail_educator_workshop.html",
}

#: One independently-classified ``ProgramExtractionResult`` per
#: festival-week event -- three distinct ``opportunity_type`` values,
#: proving no single override is collapsing them (SUC-046's Main Flow:
#: "each record's type is the LLM's own per-page classification").
_SD_FESTIVAL_RESULTS: dict[str, ProgramExtractionResult] = {
    _SD_FESTIVAL_CARD_URLS[0]: ProgramExtractionResult(
        program_name="EXPO Day",
        audience_grades=["Pre-K", "Families"],
        date_start="2026-03-07",
        date_end="2026-03-07",
        cost="Free",
        eligibility="Open to the public, all ages.",
        is_open=True,
        opportunity_type="Out-of-school Programs",
    ),
    _SD_FESTIVAL_CARD_URLS[1]: ProgramExtractionResult(
        program_name="STEAM Design Contest",
        audience_grades=["6th grade", "7th grade", "8th grade", "9th grade", "10th grade"],
        date_start="2026-03-04",
        date_end="2026-03-04",
        cost="",
        eligibility="K-12 students enrolled in a San Diego County school.",
        is_open=True,
        opportunity_type="Competitions",
    ),
    _SD_FESTIVAL_CARD_URLS[2]: ProgramExtractionResult(
        program_name="Educator Workshop",
        audience_grades=["Educator Specific"],
        date_start="2026-03-05",
        date_end="2026-03-05",
        cost="Free",
        eligibility="K-12 classroom educators.",
        is_open=True,
        opportunity_type="Educator Resources",
    ),
}


def _sd_festival_source() -> SourceConfig:
    # No config.opportunity_type override -- matching the real
    # registered TOML exactly (see this ticket's Description: festival-
    # week events span more than one type, so the override is
    # deliberately left unset).
    return SourceConfig(
        source_id="sd-festival-of-science-engineering",
        org_name="San Diego Festival of Science & Engineering (lovestemsd.org)",
        adapter_type="program_listing",
        config={
            "site_url": _SD_FESTIVAL_SITE_URL,
            "listing_urls": ["/stem-week-events-2020"],
            "program_kind": "program",
        },
    )


def _sd_festival_llm_client() -> FixtureProgramLLMClient:
    return FixtureProgramLLMClient(responses=dict(_SD_FESTIVAL_RESULTS))


class TestSDFestivalOfScienceEngineeringListingSource:
    """Sprint 029 ticket 003 (SUC-046)."""

    def test_discover_matches_festival_week_event_cards_via_event_path_re(self, tmp_path):
        # No config.link_selector is set (see _sd_festival_source()), so
        # this must resolve via plain EVENT_PATH_RE path matching --
        # exactly like the ticket 002 fixture_program_listing cards
        # above, and unlike ucsd-summer-program-finder's link_selector
        # escape hatch, which this source has no live evidence to need.
        adapter = ProgramListingAdapter(
            llm_client=_sd_festival_llm_client(), cache=ProgramExtractionCache(tmp_path)
        )
        fetcher = FixtureFetcher(
            {_SD_FESTIVAL_LISTING_URL: _response(_read("sd_festival_listing_page.html"))}
        )

        refs = adapter.discover(_sd_festival_source(), fetcher)

        assert [r.url for r in refs] == _SD_FESTIVAL_CARD_URLS

    def test_n_festival_week_events_yield_n_distinct_independently_typed_events(self, tmp_path):
        responses = {
            _SD_FESTIVAL_LISTING_URL: _response(_read("sd_festival_listing_page.html")),
            **{
                url: _response(_read(fixture_name))
                for url, fixture_name in _SD_FESTIVAL_DETAIL_FIXTURES.items()
            },
        }
        fetcher = FixtureFetcher(responses)
        adapter = ProgramListingAdapter(
            llm_client=_sd_festival_llm_client(), cache=ProgramExtractionCache(tmp_path)
        )

        events = _run(adapter, _sd_festival_source(), fetcher)

        assert len(events) == 3
        assert {e.url for e in events} == set(_SD_FESTIVAL_CARD_URLS)
        # No two events share an opportunity_type -- proves each record
        # kept its own LLM classification rather than being collapsed by
        # a config override (there is none registered for this source).
        assert {e.opportunity_type for e in events} == {
            "Out-of-school Programs",
            "Competitions",
            "Educator Resources",
        }

        by_url = {e.url: e for e in events}

        expo_day = by_url[_SD_FESTIVAL_CARD_URLS[0]]
        assert expo_day.title == "EXPO Day"
        assert expo_day.start == datetime.fromisoformat("2026-03-07")
        assert expo_day.end == datetime.fromisoformat("2026-03-07")
        assert expo_day.opportunity_type == "Out-of-school Programs"

        design_contest = by_url[_SD_FESTIVAL_CARD_URLS[1]]
        assert design_contest.title == "STEAM Design Contest"
        assert design_contest.start == datetime.fromisoformat("2026-03-04")
        assert design_contest.opportunity_type == "Competitions"

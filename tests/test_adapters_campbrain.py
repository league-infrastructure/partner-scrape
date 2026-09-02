"""Tests for partner_scrape.adapters.campbrain: the ``campbrain``
adapter (``CampBrainAdapter``).

Sprint 028 ticket 006 (issue 29). Mirrors
``tests/test_adapters_activenet_camps.py``'s structure -- every test
drives the adapter directly (construction + ``.discover()``/``.fetch()``/
``.extract()`` calls), no test here opens a real network socket or calls
the real Anthropic API.

Two extraction paths are covered, matching the adapter's own design:

- ``TestDeterministicJsonPath`` -- a JSON fixture reproducing the
  speculative CampBrain sessions-list shape ``campbrain.py`` supports for
  adapter-contract consistency with ``activenet_camps.py`` (see that
  module's docstring's Design note: this shape is not confirmed against
  any real CampBrain response, since live verification found every route
  authentication-gated).
- ``TestLLMFallbackPath`` -- the path every current ``campbrain``
  registration actually exercises: the real, fully-rendered CampBrain
  login-page DOM (``campbrain_login_page.html``, captured live 2026-09-02
  from both Coastal Roots Farm's and The Watersports Camp's real
  registration portals -- see ``campbrain.py``'s module docstring),
  proving the LLM-fallback path correctly yields zero ``Event``s for the
  real page every registration receives, plus a synthetic positive case
  (a fixture ``ProgramExtractionResult`` list, via
  ``FixtureProgramLLMClient``) proving the adapter's own mapping logic --
  including sold-out surfacing (SUC-039) -- works correctly independent
  of CampBrain's real-world blocked state.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from partner_scrape.adapters import ADAPTERS, get_adapter
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.campbrain import CampBrainAdapter
from partner_scrape.adapters.program_cache import ProgramExtractionCache
from partner_scrape.adapters.program_llm import FixtureProgramLLMClient, ProgramExtractionResult
from partner_scrape.extract.ladder import reduce_html_to_text
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "program_pages"
CAMP_URL = "https://fixturecamporg.campbrainregistration.com/"


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns a canned FetchResponse, no socket."""

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


def _fetcher(url: str = CAMP_URL, body: str = "", status: int = 200) -> FixtureFetcher:
    return FixtureFetcher({url: FetchResponse(url=url, status=status, headers={}, body=body)})


def _source(program_kind: str | None = "program", url: str = CAMP_URL) -> SourceConfig:
    config: dict = {"url": url, "opportunity_type": "Camps"}
    if program_kind is not None:
        config["program_kind"] = program_kind
    return SourceConfig(
        source_id="fixture_campbrain_org",
        org_name="Fixture Camp Org",
        adapter_type="campbrain",
        config=config,
        acquisition_policy={"fetch_strategy": "headless"},
    )


class TestDiscover:
    def test_discover_returns_exactly_one_ref_for_the_configured_url(self, tmp_path):
        adapter = CampBrainAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )

        refs = adapter.discover(_source(), FixtureFetcher({}))

        assert [r.url for r in refs] == [CAMP_URL]

    def test_missing_url_raises(self, tmp_path):
        adapter = CampBrainAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )
        source = SourceConfig(
            source_id="fixture_campbrain_org",
            org_name="Fixture Camp Org",
            adapter_type="campbrain",
            config={"program_kind": "program"},
        )

        try:
            adapter.discover(source, FixtureFetcher({}))
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError for missing url")


class TestFetch:
    def test_fetch_returns_raw_response_from_the_injected_fetcher(self, tmp_path):
        adapter = CampBrainAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )
        source = _source()
        fetcher = _fetcher(body="<html></html>")
        ref = EventRef(url=CAMP_URL)

        raw = adapter.fetch(ref, fetcher, source)

        assert raw.status == 200
        assert raw.body == "<html></html>"
        assert fetcher.calls == [CAMP_URL]


#: A speculative CampBrain sessions-list JSON shape, structurally
#: parallel to activenet_camps's own confirmed-live shape -- see
#: campbrain.py's module docstring's Design note for why this is NOT
#: itself confirmed against a real CampBrain response. The second
#: session is sold out (availableQuantity 0), the third has no tuitions
#: at all (a free session, "" cost, still open by default).
_CAMPBRAIN_JSON_BODY = """{
  "count": 3,
  "sessions": [
    {
      "id": "9001",
      "name": "Week 1 - Farm Explorers",
      "startDate": {"year": 2026, "month": 6, "day": 8},
      "endDate": {"year": 2026, "month": 6, "day": 12},
      "availableQuantity": 12,
      "tuitions": [{"allInclusivePrice": 440.0, "price": 425.0}]
    },
    {
      "id": "9002",
      "name": "Week 2 - Farm Explorers",
      "startDate": {"year": 2026, "month": 6, "day": 15},
      "endDate": {"year": 2026, "month": 6, "day": 19},
      "availableQuantity": 0,
      "tuitions": [{"allInclusivePrice": 440.0, "price": 425.0}]
    },
    {
      "id": "9003",
      "name": "Community Open House",
      "startDate": {"year": 2026, "month": 6, "day": 20},
      "endDate": {"year": 2026, "month": 6, "day": 20},
      "availableQuantity": 999999999,
      "tuitions": []
    }
  ]
}"""


class TestDeterministicJsonPath:
    """AC: extract() supports a deterministic-parse path, producing
    ProgramExtractionResults mapped via the shared _map_result_to_event,
    with no LLM call.
    """

    def test_json_sessions_map_to_correctly_dated_priced_events_no_llm_call(self, tmp_path):
        llm_client = FixtureProgramLLMClient()
        adapter = CampBrainAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=_CAMPBRAIN_JSON_BODY)

        events = list(adapter.extract(raw, _source()))

        assert len(events) == 3
        assert llm_client.calls == []
        assert llm_client.list_calls == []

        week1, week2, open_house = events
        assert week1.title == "Week 1 - Farm Explorers"
        assert week1.start == datetime.fromisoformat("2026-06-08")
        assert week1.end == datetime.fromisoformat("2026-06-12")
        assert week1.cost == "$440.00"
        assert week1.opportunity_type == "Camps"
        assert week1.description == ""

        # Sold out: availableQuantity == 0 -> is_open False -> sold-out
        # Event.description, the same SUC-039 mechanism program_page_multi/
        # activenet_camps use (shared, unmodified _map_result_to_event).
        assert week2.title == "Week 2 - Farm Explorers"
        assert week2.description == "Sold out"

        # No tuitions at all -> "" cost, still open (999999999 sentinel
        # is "unlimited", not "sold out").
        assert open_house.title == "Community Open House"
        assert open_house.cost == ""
        assert open_house.description == ""

    def test_all_events_share_url_and_source_id(self, tmp_path):
        adapter = CampBrainAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=_CAMPBRAIN_JSON_BODY)

        events = list(adapter.extract(raw, _source()))

        assert all(e.url == CAMP_URL for e in events)
        assert all(e.source_id == "fixture_campbrain_org" for e in events)
        assert all(e.kind == "program" for e in events)

    def test_malformed_session_entry_is_skipped_not_fatal(self, tmp_path, caplog):
        body = """{"count": 2, "sessions": [
            {"name": "Good Session", "startDate": {"year": 2026, "month": 6, "day": 1},
             "endDate": {"year": 2026, "month": 6, "day": 5}, "availableQuantity": 10, "tuitions": []},
            {"startDate": {"year": 2026, "month": 6, "day": 1}}
        ]}"""
        adapter = CampBrainAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=body)

        with caplog.at_level(logging.WARNING):
            events = list(adapter.extract(raw, _source()))

        assert len(events) == 1
        assert events[0].title == "Good Session"
        assert "missing a name" in caplog.text

    def test_missing_program_kind_is_logged_and_skipped(self, tmp_path):
        adapter = CampBrainAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=_CAMPBRAIN_JSON_BODY)

        events = list(adapter.extract(raw, _source(program_kind=None)))

        assert events == []


class TestLLMFallbackPath:
    """AC: a fixture-based test proves the LLM-fallback path maps a
    saved CampBrain page into correctly-dated, correctly-priced Events,
    with no live network or LLM call -- plus a test proving the real
    page every current campbrain registration actually receives (a
    login form, see campbrain.py's module docstring) correctly yields
    zero Events, not an error or a hallucinated session.
    """

    def _login_page_body(self) -> str:
        return (FIXTURES_DIR / "campbrain_login_page.html").read_text()

    _RESULTS = [
        ProgramExtractionResult(
            program_name="Week 1 - Farm Explorers",
            audience_grades=["TK", "5th grade"],
            date_start="2026-06-08",
            date_end="2026-06-12",
            cost="$440.00",
            eligibility="Grades TK-5",
            is_open=True,
            opportunity_type="Camps",
        ),
        ProgramExtractionResult(
            program_name="Week 2 - Farm Explorers",
            audience_grades=["TK", "5th grade"],
            date_start="2026-06-15",
            date_end="2026-06-19",
            cost="$440.00",
            eligibility="Grades TK-5",
            is_open=False,
            opportunity_type="Camps",
        ),
    ]

    def _llm_client(self, results=None) -> FixtureProgramLLMClient:
        return FixtureProgramLLMClient(list_responses={CAMP_URL: results if results is not None else self._RESULTS})

    def test_rendered_page_maps_to_correctly_dated_priced_events_with_one_sold_out(self, tmp_path):
        # Proves the adapter's own mapping logic (shared with
        # program_page_multi/activenet_camps) works correctly -- the
        # actual page body's content doesn't matter here since the LLM
        # call itself is a fixture double; see the test below for what
        # the real page's body actually is.
        llm_client = self._llm_client()
        adapter = CampBrainAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=self._login_page_body())

        events = list(adapter.extract(raw, _source()))

        assert len(events) == 2
        assert llm_client.calls == []  # only extract_programs, never extract_program
        assert llm_client.list_calls == [(CAMP_URL, reduce_html_to_text(self._login_page_body()))]

        week1, week2 = events
        assert week1.start == datetime.fromisoformat("2026-06-08")
        assert week1.end == datetime.fromisoformat("2026-06-12")
        assert week1.cost == "$440.00"
        assert week1.opportunity_type == "Camps"
        assert week1.description == ""

        # SUC-039/SUC-043: a sold-out session's Event.description carries
        # the sold-out note.
        assert week2.description == "Sold out"
        assert week2.opportunity_type == "Camps"

    def test_real_login_page_yields_zero_events_not_an_error(self, tmp_path):
        # Matches what every current campbrain registration's fetch()
        # actually receives (see campbrain.py's module docstring's Live
        # Verification note): a family-login form, never session data.
        # A real LLM reading this page would find no distinct program/
        # camp sessions described and return an empty list -- this test
        # proves the adapter handles that gracefully, not as an error.
        llm_client = self._llm_client(results=[])
        adapter = CampBrainAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=self._login_page_body())

        events = list(adapter.extract(raw, _source()))

        assert events == []
        assert llm_client.list_calls == [(CAMP_URL, reduce_html_to_text(self._login_page_body()))]

    def test_non_json_body_falls_through_to_llm_extraction(self, tmp_path):
        # Proves the dispatch itself: a body that is not CampBrain's
        # speculative sessions JSON (ordinary HTML, e.g. the real login
        # page) is not silently dropped -- it is handed to the
        # LLM-fallback path rather than treated as a parse failure that
        # yields zero events with no LLM call at all.
        llm_client = self._llm_client(results=[])
        adapter = CampBrainAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=self._login_page_body())

        events = list(adapter.extract(raw, _source()))

        assert events == []
        assert llm_client.list_calls == [(CAMP_URL, reduce_html_to_text(self._login_page_body()))]

    def test_extract_programs_raising_is_logged_and_skipped_not_raised(self, tmp_path, caplog):
        adapter = CampBrainAdapter(
            llm_client=FixtureProgramLLMClient(list_responses={}),
            cache=ProgramExtractionCache(tmp_path),
        )
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=self._login_page_body())

        with caplog.at_level(logging.WARNING):
            events = list(adapter.extract(raw, _source()))

        assert events == []
        assert "extract_programs" in caplog.text

    def test_second_extract_for_unchanged_body_makes_no_further_llm_call(self, tmp_path):
        llm_client = self._llm_client()
        cache = ProgramExtractionCache(tmp_path)
        adapter = CampBrainAdapter(llm_client=llm_client, cache=cache)
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=self._login_page_body())

        first = list(adapter.extract(raw, _source()))
        assert len(llm_client.list_calls) == 1

        second = list(adapter.extract(raw, _source()))
        assert len(llm_client.list_calls) == 1  # cache hit -- no further call
        assert len(first) == len(second) == 2


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self, tmp_path):
        adapter = CampBrainAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=403, body="")

        assert list(adapter.extract(raw, _source())) == []

    def test_non_200_status_makes_no_llm_call(self, tmp_path):
        llm_client = FixtureProgramLLMClient()
        adapter = CampBrainAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=500, body="")

        list(adapter.extract(raw, _source()))

        assert llm_client.calls == []
        assert llm_client.list_calls == []


class TestDispatchRegistration:
    def test_campbrain_is_registered_in_adapters_table(self):
        assert ADAPTERS["campbrain"] is CampBrainAdapter

    def test_campbrain_resolves_via_get_adapter_to_a_working_instance(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
        adapter = get_adapter("campbrain")

        assert isinstance(adapter, CampBrainAdapter)
        # Zero-arg construction still produces a fully-working instance --
        # the real AnthropicProgramLLMClient/ProgramExtractionCache fill
        # in as defaults (adapters/DESIGN.md's documented deviation).
        refs = adapter.discover(_source(), FixtureFetcher({}))
        assert [r.url for r in refs] == [CAMP_URL]

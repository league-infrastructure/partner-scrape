"""Tests for partner_scrape.adapters.activenet_camps: the
``activenet_camps`` adapter (``ActiveNetCampsAdapter``).

Sprint 028 ticket 005 (issue 29). Mirrors
``tests/test_adapters_program_page_multi.py``'s structure -- every test
drives the adapter directly (construction + ``.discover()``/``.fetch()``/
``.extract()`` calls), no test here opens a real network socket or calls
the real Anthropic API.

Two extraction paths are covered, matching the adapter's own design:

- ``TestDeterministicJsonPath`` -- a JSON fixture reproducing ActiveNet's
  own ``{"count": ..., "sessions": [...]}`` shape, captured live from
  both San Diego Air & Space Museum's and Helen Woodward Animal Center's
  real ``/external/json/seasons/{id}/sessions`` responses (see
  ``activenet_camps.py``'s module docstring). No current production
  registration actually exercises this path (see that docstring's Live
  Verification note), but the adapter contract supports it for a future
  integration that does expose clean JSON.
- ``TestLLMFallbackPath`` -- the path every current registration actually
  uses: a fixture HTML page standing in for ``campscui.active.com``'s
  own JS-rendered DOM (fetched via the headless ``Fetcher``), with a
  ``FixtureProgramLLMClient`` supplying canned ``ProgramExtractionResult``s
  -- including a sold-out session, proving the SUC-039 sold-out-via-
  ``Event.description`` mapping this adapter shares with
  ``program_page_multi``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from partner_scrape.adapters import ADAPTERS, get_adapter
from partner_scrape.adapters.activenet_camps import ActiveNetCampsAdapter
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.program_cache import ProgramExtractionCache
from partner_scrape.adapters.program_llm import FixtureProgramLLMClient, ProgramExtractionResult
from partner_scrape.extract.ladder import reduce_html_to_text
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "program_pages"
CAMP_URL = "https://campscui.active.com/orgs/FixtureCampOrg?orglink=camps-registration"


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
        source_id="fixture_activenet_org",
        org_name="Fixture ActiveNet Org",
        adapter_type="activenet_camps",
        config=config,
        acquisition_policy={"fetch_strategy": "headless"},
    )


class TestDiscover:
    def test_discover_returns_exactly_one_ref_for_the_configured_url(self, tmp_path):
        adapter = ActiveNetCampsAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )

        refs = adapter.discover(_source(), FixtureFetcher({}))

        assert [r.url for r in refs] == [CAMP_URL]

    def test_missing_url_raises(self, tmp_path):
        adapter = ActiveNetCampsAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )
        source = SourceConfig(
            source_id="fixture_activenet_org",
            org_name="Fixture ActiveNet Org",
            adapter_type="activenet_camps",
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
        adapter = ActiveNetCampsAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )
        source = _source()
        fetcher = _fetcher(body="<html></html>")
        ref = EventRef(url=CAMP_URL)

        raw = adapter.fetch(ref, fetcher, source)

        assert raw.status == 200
        assert raw.body == "<html></html>"
        assert fetcher.calls == [CAMP_URL]


#: Real shape captured live (2026-09-01) from ActiveNet's own
#: ``/external/json/seasons/{id}/sessions``(``/group``) response for both
#: San Diego Air & Space Museum and Helen Woodward Animal Center --
#: trimmed to the fields this adapter actually reads. The second session
#: is sold out (``availableQuantity`` 0), the third has no tuitions at
#: all (a free session, "" cost, still open by default).
_ACTIVENET_JSON_BODY = """{
  "count": 3,
  "sessions": [
    {
      "id": "72197036",
      "name": "Monday - Survival - Fall",
      "startDate": {"year": 2026, "month": 10, "day": 26},
      "endDate": {"year": 2026, "month": 10, "day": 27},
      "availableQuantity": 45,
      "tuitions": [{"allInclusivePrice": 103.02, "price": 102.0}]
    },
    {
      "id": "72197037",
      "name": "Tuesday - Shelter - Fall",
      "startDate": {"year": 2026, "month": 10, "day": 27},
      "endDate": {"year": 2026, "month": 10, "day": 28},
      "availableQuantity": 0,
      "tuitions": [{"allInclusivePrice": 103.02, "price": 102.0}]
    },
    {
      "id": "72197038",
      "name": "Demo Party",
      "startDate": {"year": 2026, "month": 9, "day": 14},
      "endDate": {"year": 2026, "month": 9, "day": 15},
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
        adapter = ActiveNetCampsAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=_ACTIVENET_JSON_BODY)

        events = list(adapter.extract(raw, _source()))

        assert len(events) == 3
        assert llm_client.calls == []
        assert llm_client.list_calls == []

        survival, shelter, demo = events
        assert survival.title == "Monday - Survival - Fall"
        assert survival.start == datetime.fromisoformat("2026-10-26")
        assert survival.end == datetime.fromisoformat("2026-10-27")
        assert survival.cost == "$103.02"
        assert survival.opportunity_type == "Camps"
        assert survival.description == ""

        # Sold out: availableQuantity == 0 -> is_open False -> sold-out
        # Event.description, the same SUC-039 mechanism program_page_multi
        # uses (shared, unmodified _map_result_to_event).
        assert shelter.title == "Tuesday - Shelter - Fall"
        assert shelter.description == "Sold out"

        # No tuitions at all -> "" cost, still open (999999999 sentinel
        # is "unlimited", not "sold out").
        assert demo.title == "Demo Party"
        assert demo.cost == ""
        assert demo.description == ""

    def test_all_events_share_url_and_source_id(self, tmp_path):
        adapter = ActiveNetCampsAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=_ACTIVENET_JSON_BODY)

        events = list(adapter.extract(raw, _source()))

        assert all(e.url == CAMP_URL for e in events)
        assert all(e.source_id == "fixture_activenet_org" for e in events)
        assert all(e.kind == "program" for e in events)

    def test_malformed_session_entry_is_skipped_not_fatal(self, tmp_path, caplog):
        body = """{"count": 2, "sessions": [
            {"name": "Good Session", "startDate": {"year": 2026, "month": 6, "day": 1},
             "endDate": {"year": 2026, "month": 6, "day": 5}, "availableQuantity": 10, "tuitions": []},
            {"startDate": {"year": 2026, "month": 6, "day": 1}}
        ]}"""
        adapter = ActiveNetCampsAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=body)

        with caplog.at_level(logging.WARNING):
            events = list(adapter.extract(raw, _source()))

        assert len(events) == 1
        assert events[0].title == "Good Session"
        assert "missing a name" in caplog.text

    def test_missing_program_kind_is_logged_and_skipped(self, tmp_path):
        adapter = ActiveNetCampsAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=_ACTIVENET_JSON_BODY)

        events = list(adapter.extract(raw, _source(program_kind=None)))

        assert events == []


class TestLLMFallbackPath:
    """AC: a fixture-based test proves the LLM-fallback path maps a
    saved ActiveNet page into correctly-dated, correctly-priced Events,
    with no live network or LLM call -- the path every current
    ``activenet_camps`` registration actually exercises (see the module
    docstring's Live Verification note: the headless-rendered DOM is
    HTML, not the underlying JSON API response).
    """

    def _page_body(self) -> str:
        return (FIXTURES_DIR / "activenet_rendered_sessions_page.html").read_text()

    _RESULTS = [
        ProgramExtractionResult(
            program_name="Monday - Survival - Fall",
            audience_grades=["Pre-School", "6th grade"],
            date_start="2026-10-26",
            date_end="2026-10-27",
            cost="$103.02",
            eligibility="Age 4-13, Grade Pre-School - 6th",
            is_open=True,
            opportunity_type="Camps",
        ),
        ProgramExtractionResult(
            program_name="Tuesday - Shelter - Fall",
            audience_grades=["Pre-School", "6th grade"],
            date_start="2026-10-27",
            date_end="2026-10-28",
            cost="$103.02",
            eligibility="Age 4-13, Grade Pre-School - 6th",
            is_open=False,
            opportunity_type="Camps",
        ),
    ]

    def _llm_client(self, results=None) -> FixtureProgramLLMClient:
        return FixtureProgramLLMClient(list_responses={CAMP_URL: results if results is not None else self._RESULTS})

    def test_rendered_page_maps_to_correctly_dated_priced_events_with_one_sold_out(self, tmp_path):
        llm_client = self._llm_client()
        adapter = ActiveNetCampsAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=self._page_body())

        events = list(adapter.extract(raw, _source()))

        assert len(events) == 2
        assert llm_client.calls == []  # only extract_programs, never extract_program
        assert llm_client.list_calls == [(CAMP_URL, reduce_html_to_text(self._page_body()))]

        survival, shelter = events
        assert survival.start == datetime.fromisoformat("2026-10-26")
        assert survival.end == datetime.fromisoformat("2026-10-27")
        assert survival.cost == "$103.02"
        assert survival.opportunity_type == "Camps"
        assert survival.description == ""

        # SUC-039/SUC-042: a sold-out session's Event.description carries
        # the sold-out note.
        assert shelter.description == "Sold out"
        assert shelter.opportunity_type == "Camps"

    def test_non_json_body_falls_through_to_llm_extraction(self, tmp_path):
        # Proves the dispatch itself: a body that is not ActiveNet's
        # sessions JSON (ordinary rendered HTML) is *not* silently
        # dropped -- it is handed to the LLM-fallback path rather than
        # treated as a parse failure that yields zero events.
        llm_client = self._llm_client(results=[])
        adapter = ActiveNetCampsAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=self._page_body())

        events = list(adapter.extract(raw, _source()))

        assert events == []
        assert llm_client.list_calls == [(CAMP_URL, reduce_html_to_text(self._page_body()))]

    def test_off_season_empty_list_yields_zero_events_without_error(self, tmp_path):
        # Matches SUC-040's off-season handling: an ActiveNet org page
        # with no currently-published camp session (e.g. San Diego Air &
        # Space Museum's page as of this ticket's live verification,
        # which showed only a "Birthday Parties" season, no live camp
        # season) must yield zero Events, not an error.
        llm_client = self._llm_client(results=[])
        adapter = ActiveNetCampsAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=self._page_body())

        assert list(adapter.extract(raw, _source())) == []

    def test_extract_programs_raising_is_logged_and_skipped_not_raised(self, tmp_path, caplog):
        adapter = ActiveNetCampsAdapter(
            llm_client=FixtureProgramLLMClient(list_responses={}),
            cache=ProgramExtractionCache(tmp_path),
        )
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=self._page_body())

        with caplog.at_level(logging.WARNING):
            events = list(adapter.extract(raw, _source()))

        assert events == []
        assert "extract_programs" in caplog.text

    def test_second_extract_for_unchanged_body_makes_no_further_llm_call(self, tmp_path):
        llm_client = self._llm_client()
        cache = ProgramExtractionCache(tmp_path)
        adapter = ActiveNetCampsAdapter(llm_client=llm_client, cache=cache)
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=200, body=self._page_body())

        first = list(adapter.extract(raw, _source()))
        assert len(llm_client.list_calls) == 1

        second = list(adapter.extract(raw, _source()))
        assert len(llm_client.list_calls) == 1  # cache hit -- no further call
        assert len(first) == len(second) == 2


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self, tmp_path):
        adapter = ActiveNetCampsAdapter(
            llm_client=FixtureProgramLLMClient(), cache=ProgramExtractionCache(tmp_path)
        )
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=403, body="")

        assert list(adapter.extract(raw, _source())) == []

    def test_non_200_status_makes_no_llm_call(self, tmp_path):
        llm_client = FixtureProgramLLMClient()
        adapter = ActiveNetCampsAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=CAMP_URL), status=500, body="")

        list(adapter.extract(raw, _source()))

        assert llm_client.calls == []
        assert llm_client.list_calls == []


class TestDispatchRegistration:
    def test_activenet_camps_is_registered_in_adapters_table(self):
        assert ADAPTERS["activenet_camps"] is ActiveNetCampsAdapter

    def test_activenet_camps_resolves_via_get_adapter_to_a_working_instance(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
        adapter = get_adapter("activenet_camps")

        assert isinstance(adapter, ActiveNetCampsAdapter)
        # Zero-arg construction still produces a fully-working instance --
        # the real AnthropicProgramLLMClient/ProgramExtractionCache fill
        # in as defaults (adapters/DESIGN.md's documented deviation).
        refs = adapter.discover(_source(), FixtureFetcher({}))
        assert [r.url for r in refs] == [CAMP_URL]

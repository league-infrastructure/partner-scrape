"""Tests for partner_scrape.adapters.program_page: the ``program_page_multi``
adapter (``ProgramPageMultiAdapter``).

Sprint 027 ticket 006 exception revision, ticket 008. Mirrors
``tests/test_adapters_program_page.py``'s structure -- every test drives
the adapter directly (construction + ``.discover()``/``.fetch()``/
``.extract()`` calls), no test here opens a real network socket or calls
the real Anthropic API. Fixture body is
``tests/fixtures/program_pages/sio_research_internships_page.html``, a
fixture reproducing the SIO research-internships page's real shape: N
``<div class="page-section">`` blocks, each one distinct program, all on
one page rather than N separate detail pages.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from partner_scrape.adapters import ADAPTERS, get_adapter
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.program_cache import ProgramExtractionCache
from partner_scrape.adapters.program_llm import FixtureProgramLLMClient, ProgramExtractionResult
from partner_scrape.adapters.program_page import ProgramPageMultiAdapter
from partner_scrape.extract.ladder import reduce_html_to_text
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "program_pages"
PAGE_URL = "https://sio.ucsd.edu/research-internships"


def _page_body() -> str:
    return (FIXTURES_DIR / "sio_research_internships_page.html").read_text()


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


def _fetcher(url: str = PAGE_URL, body: str | None = None, status: int = 200) -> FixtureFetcher:
    return FixtureFetcher({url: FetchResponse(url=url, status=status, headers={}, body=body or _page_body())})


def _source(program_kind: str | None = "internship", url: str = PAGE_URL) -> SourceConfig:
    config: dict = {"url": url}
    if program_kind is not None:
        config["program_kind"] = program_kind
    return SourceConfig(
        source_id="fixture_sio_internships",
        org_name="Fixture SIO",
        adapter_type="program_page_multi",
        config=config,
    )


#: Three distinct programs described on one page -- JT-SURF and MPL
#: deliberately share the same date_end (the AC's own "at least one pair
#: of records with the same start_date but different titles" requirement
#: applies to identity_key(), which is keyed on start_date, not
#: date_end -- see TestDistinctIdentityKeys below for the actual shared
#: field).
_RESULTS = [
    ProgramExtractionResult(
        program_name="Fixture JT-SURF",
        audience_grades=["11th grade", "12th grade"],
        date_start="2026-12-01",
        date_end="2027-02-15",
        cost="Paid stipend",
        eligibility="Current 11th-12th grade students residing in San Diego County.",
        is_open=True,
        opportunity_type="Out-of-school Programs",
    ),
    ProgramExtractionResult(
        program_name="Fixture MPL Summer Internship",
        audience_grades=["12th grade"],
        date_start="2026-12-01",
        date_end="2027-03-01",
        cost="Paid stipend",
        eligibility="Current 12th grade students.",
        is_open=True,
        opportunity_type="Out-of-school Programs",
    ),
    ProgramExtractionResult(
        program_name="Fixture CW3E Undergraduate Fellowship",
        audience_grades=["Undergraduate"],
        date_start="",
        date_end="",
        cost="Unpaid",
        eligibility="Current undergraduate students.",
        is_open=True,
        opportunity_type="Out-of-school Programs",
    ),
]


def _llm_client(results: list[ProgramExtractionResult] | None = None) -> FixtureProgramLLMClient:
    return FixtureProgramLLMClient(list_responses={PAGE_URL: results if results is not None else _RESULTS})


class TestDiscover:
    def test_discover_returns_exactly_one_ref_for_the_configured_url(self, tmp_path):
        adapter = ProgramPageMultiAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))

        refs = adapter.discover(_source(), FixtureFetcher({}))

        assert [r.url for r in refs] == [PAGE_URL]

    def test_missing_url_raises(self, tmp_path):
        adapter = ProgramPageMultiAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        source = SourceConfig(
            source_id="fixture_sio_internships",
            org_name="Fixture SIO",
            adapter_type="program_page_multi",
            config={"program_kind": "internship"},
        )

        try:
            adapter.discover(source, FixtureFetcher({}))
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError for missing url")


class TestEndToEndExtraction:
    """AC: a FixtureProgramLLMClient test proves extract_programs()
    returning N results maps to N distinct Events from
    ProgramPageMultiAdapter.extract(), each with its own title/dates/
    eligibility, sharing the same url/source_id.
    """

    def test_n_results_map_to_n_distinct_events_sharing_url_and_source_id(self, tmp_path):
        llm_client = _llm_client()
        adapter = ProgramPageMultiAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        source = _source()
        fetcher = _fetcher()

        refs = adapter.discover(source, fetcher)
        assert len(refs) == 1
        raw = adapter.fetch(refs[0], fetcher, source)
        events = list(adapter.extract(raw, source))

        assert len(events) == 3
        assert all(e.url == PAGE_URL for e in events)
        assert all(e.source_id == "fixture_sio_internships" for e in events)
        assert all(e.kind == "internship" for e in events)
        assert all(e.registration_url == PAGE_URL for e in events)

        titles = [e.title for e in events]
        assert titles == [
            "Fixture JT-SURF",
            "Fixture MPL Summer Internship",
            "Fixture CW3E Undergraduate Fellowship",
        ]
        # No two records share a value -- proves independent, per-record
        # mapping rather than one blended value applied to all three.
        assert len({e.title for e in events}) == 3
        assert len({e.eligibility for e in events}) == 3

        jt_surf, mpl, cw3e = events
        assert jt_surf.start == datetime.fromisoformat("2026-12-01")
        assert jt_surf.end == datetime.fromisoformat("2027-02-15")
        assert jt_surf.eligibility == "Current 11th-12th grade students residing in San Diego County."
        assert jt_surf.cost == "Paid stipend"

        assert mpl.start == datetime.fromisoformat("2026-12-01")
        assert mpl.end == datetime.fromisoformat("2027-03-01")
        assert mpl.eligibility == "Current 12th grade students."

        assert cw3e.start is None
        assert cw3e.end is None
        assert cw3e.eligibility == "Current undergraduate students."

    def test_llm_client_called_once_for_the_whole_page(self, tmp_path):
        # (Sprint 028, issue 36) the LLM call now receives raw.body only
        # after extract.reduce_html_to_text() has reduced it -- see
        # test_extract_ladder.py / test_adapters_program_page.py's own
        # sprint 028 tests for the reduction step itself. This assertion
        # was updated (not "unmodified" -- see ticket 028-001's own
        # commit) because it inspects the literal body forwarded to the
        # LLM client, an implementation detail this ticket's required
        # wiring necessarily changes; the *behavior* under test --
        # exactly one extract_programs() call for the whole page, never
        # the singular extract_program() -- is unaffected.
        llm_client = _llm_client()
        adapter = ProgramPageMultiAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        list(adapter.extract(raw, _source()))

        assert llm_client.list_calls == [(PAGE_URL, reduce_html_to_text(_page_body()))]
        assert llm_client.calls == []  # never calls the singular extract_program


class TestDistinctIdentityKeys:
    """AC: a test proves the N same-url Events from one program_page_multi
    page have N distinct identity_key() values (no collision), using at
    least one pair of records with the same start_date but different
    titles -- JT-SURF and MPL above both have date_start="2026-12-01".
    """

    def test_n_events_from_one_page_have_n_distinct_identity_keys(self, tmp_path):
        adapter = ProgramPageMultiAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, _source()))

        assert len(events) == 3
        identity_keys = [e.identity_key() for e in events]
        assert len(set(identity_keys)) == 3

    def test_the_shared_start_date_pair_still_yields_distinct_identity_keys(self, tmp_path):
        adapter = ProgramPageMultiAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        jt_surf, mpl, _cw3e = list(adapter.extract(raw, _source()))

        assert jt_surf.start.date() == mpl.start.date()
        assert jt_surf.title != mpl.title
        assert jt_surf.identity_key() != mpl.identity_key()
        # Both share source_id and start_date -- only the normalized
        # title differs, and that alone is enough to distinguish them
        # (Event.identity_key()'s (source_id, normalized_title,
        # start_date) fallback, model.py).
        assert jt_surf.identity_key()[0] == mpl.identity_key()[0]
        assert jt_surf.identity_key()[2] == mpl.identity_key()[2]


class TestCache:
    def test_second_extract_for_unchanged_body_makes_no_further_llm_call(self, tmp_path):
        llm_client = _llm_client()
        cache = ProgramExtractionCache(tmp_path)
        adapter = ProgramPageMultiAdapter(llm_client=llm_client, cache=cache)
        source = _source()
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        first = list(adapter.extract(raw, source))
        assert len(llm_client.list_calls) == 1

        second = list(adapter.extract(raw, source))
        assert len(llm_client.list_calls) == 1  # cache hit -- no further call

        assert len(first) == len(second) == 3
        assert [e.title for e in first] == [e.title for e in second]

    def test_changed_body_makes_a_fresh_llm_call(self, tmp_path):
        cache = ProgramExtractionCache(tmp_path)
        results_one = [ProgramExtractionResult(program_name="First")]
        results_two = [ProgramExtractionResult(program_name="Second")]
        llm_client = FixtureProgramLLMClient(
            list_responses={
                (PAGE_URL, "body one"): results_one,
                (PAGE_URL, "body two"): results_two,
            },
            key_fn=lambda url, body: (url, body),
        )
        adapter = ProgramPageMultiAdapter(llm_client=llm_client, cache=cache)
        source = _source()

        raw_one = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body="body one")
        raw_two = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body="body two")

        events_one = list(adapter.extract(raw_one, source))
        events_two = list(adapter.extract(raw_two, source))

        assert len(llm_client.list_calls) == 2
        assert events_one[0].title == "First"
        assert events_two[0].title == "Second"


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self, tmp_path):
        adapter = ProgramPageMultiAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []
        assert adapter.llm_client.list_calls == []

    def test_missing_program_kind_is_logged_and_skipped(self, tmp_path):
        adapter = ProgramPageMultiAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, _source(program_kind=None)))

        assert events == []

    def test_invalid_program_kind_is_logged_and_skipped(self, tmp_path):
        adapter = ProgramPageMultiAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, _source(program_kind="event")))

        assert events == []

    def test_empty_extraction_result_list_yields_zero_events(self, tmp_path):
        adapter = ProgramPageMultiAdapter(
            llm_client=_llm_client(results=[]), cache=ProgramExtractionCache(tmp_path)
        )
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        assert list(adapter.extract(raw, _source())) == []

    def test_extract_programs_raising_is_logged_and_skipped_not_raised(self, tmp_path, caplog):
        # Sprint 027 ticket 006's own live verification found a real
        # llm_client.extract_program() call can raise (a page whose body
        # exceeds the model's context window raised
        # anthropic.BadRequestError) -- extract_programs() has the
        # identical uncaught-exception risk, so it gets the identical
        # isolation. FixtureProgramLLMClient raises a plain KeyError for
        # a URL absent from its `list_responses` dict, exercising the
        # same "the LLM call itself raised" code path.
        adapter = ProgramPageMultiAdapter(
            llm_client=FixtureProgramLLMClient(list_responses={}),
            cache=ProgramExtractionCache(tmp_path),
        )
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        with caplog.at_level(logging.WARNING):
            events = list(adapter.extract(raw, _source()))

        assert events == []
        assert "extract_programs" in caplog.text


class TestOffSeasonPageYieldsEmptyList:
    """AC (028-003): an in-season-only camp marketing page (e.g. Fleet's,
    registration opens Feb) that currently has nothing to describe must
    yield zero Events -- not a hallucinated session, not a parse error.
    ``_extract_many_programs`` already maps a zero-length
    ``extract_programs()`` result to zero Events with no special-casing;
    this fixture proves that path end-to-end via
    ``ProgramPageMultiAdapter.extract()``, standing in for an off-season
    page (``_SYSTEM_PROMPT_MULTI`` now explicitly tells the model an
    empty list is a valid response for such a page -- see
    ``program_llm.py``).
    """

    OFF_SEASON_URL = "https://example.org/camps/fleet-off-season"

    def test_off_season_page_yields_zero_events_with_no_exception(self, tmp_path):
        llm_client = FixtureProgramLLMClient(list_responses={self.OFF_SEASON_URL: []})
        adapter = ProgramPageMultiAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        source = _source(program_kind="program", url=self.OFF_SEASON_URL)
        raw = RawResponse(ref=EventRef(url=self.OFF_SEASON_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, source))

        assert events == []
        assert llm_client.list_calls == [(self.OFF_SEASON_URL, reduce_html_to_text(_page_body()))]


class TestDispatchRegistration:
    def test_program_page_multi_is_registered_in_adapters_table(self):
        assert ADAPTERS["program_page_multi"] is ProgramPageMultiAdapter

    def test_program_page_multi_resolves_via_get_adapter_to_a_working_instance(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
        adapter = get_adapter("program_page_multi")

        assert isinstance(adapter, ProgramPageMultiAdapter)
        # Zero-arg construction still produces a fully-working instance --
        # the real AnthropicProgramLLMClient/ProgramExtractionCache fill
        # in as defaults (adapters/DESIGN.md's documented deviation).
        refs = adapter.discover(_source(), FixtureFetcher({}))
        assert [r.url for r in refs] == [PAGE_URL]


class TestSDMRMSoldOutCampSessions:
    """Sprint 028 ticket 004's own Testing requirement: a fixture-based
    test exercising a sold-out row, standing in for the San Diego Model
    Railroad Museum's real registered page
    (registry/sources/sd-model-railroad-museum-camps.toml), this
    sprint's designated live target for ticket 003's
    sold-out-via-``Event.description`` mapping (adapters/DESIGN.md's
    sprint 028 section). Fixture body is
    ``tests/fixtures/program_pages/sdmrm_camp_sessions_page.html``, a
    small fixture reproducing the real page's shape: a weekly-sessions
    table with one open week and two "SOLD OUT!" weeks.
    """

    SDMRM_URL = "https://example.org/camps/sdmrm-summer-camps"

    _SDMRM_RESULTS = [
        ProgramExtractionResult(
            program_name="Fixture Model Railroading Camp -- Grades K-2 Beginner (June 15-18)",
            audience_grades=["Grades K-2"],
            date_start="2026-06-15",
            date_end="2026-06-18",
            cost="$200 ($180 member)",
            eligibility="Grades K-2, no prior experience required",
            is_open=True,
            opportunity_type="Camps",
        ),
        ProgramExtractionResult(
            program_name="Fixture Model Railroading Camp -- Grades K-2 Beginner (June 22-26)",
            audience_grades=["Grades K-2"],
            date_start="2026-06-22",
            date_end="2026-06-26",
            cost="$250 ($225 member)",
            eligibility="Grades K-2, no prior experience required",
            is_open=False,
            opportunity_type="Camps",
        ),
        ProgramExtractionResult(
            program_name="Fixture Model Railroading Camp -- Grades 3-5 Apprentice (July 6-10)",
            audience_grades=["Grades 3-5"],
            date_start="2026-07-06",
            date_end="2026-07-10",
            cost="$250 ($225 member)",
            eligibility="Grades 3-5, no prior experience required",
            is_open=False,
            opportunity_type="Camps",
        ),
    ]

    def _sdmrm_body(self) -> str:
        return (FIXTURES_DIR / "sdmrm_camp_sessions_page.html").read_text()

    def _sdmrm_source(self) -> SourceConfig:
        return SourceConfig(
            source_id="fixture_sdmrm_camps",
            org_name="Fixture SD Model Railroad Museum",
            adapter_type="program_page_multi",
            config={
                "url": self.SDMRM_URL,
                "program_kind": "program",
                "opportunity_type": "Camps",
            },
        )

    def test_three_weekly_sessions_extract_with_two_sold_out(self, tmp_path):
        llm_client = FixtureProgramLLMClient(list_responses={self.SDMRM_URL: self._SDMRM_RESULTS})
        adapter = ProgramPageMultiAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=self.SDMRM_URL), status=200, body=self._sdmrm_body())

        events = list(adapter.extract(raw, self._sdmrm_source()))

        assert len(events) == 3
        assert all(e.opportunity_type == "Camps" for e in events)

        open_week, sold_out_week_1, sold_out_week_2 = events
        assert open_week.start == datetime.fromisoformat("2026-06-15")
        assert open_week.cost == "$200 ($180 member)"
        assert open_week.description == ""

        assert sold_out_week_1.start == datetime.fromisoformat("2026-06-22")
        assert sold_out_week_1.description == "Sold out"
        assert sold_out_week_2.start == datetime.fromisoformat("2026-07-06")
        assert sold_out_week_2.description == "Sold out"

        # Distinct identity keys despite sharing source_id and
        # opportunity_type -- each week's own start date and title
        # still distinguish it (TestDistinctIdentityKeys's own AC,
        # exercised here against this ticket's real sold-out shape).
        assert len({e.identity_key() for e in events}) == 3


class TestMultiWeekThemedCampPage:
    """Sprint 028 ticket 004's own Testing requirement: a fixture-based
    test exercising a multi-session page (N week-rows), standing in for
    the San Diego Zoo's registered per-program pages (e.g.
    registry/sources/sd-zoo-classic-camp-kindergarten.toml), each of
    which offers two named four-week themes at one shared price.
    Fixture body is
    ``tests/fixtures/program_pages/multi_week_camp_page.html``.
    """

    ZOO_URL = "https://example.org/camps/fixture-wildlife-camp"

    _ZOO_RESULTS = [
        ProgramExtractionResult(
            program_name="Fixture Wildlife Camp -- Wonderful Wildlife Discoveries (June 8-12)",
            audience_grades=["K-5th grade"],
            date_start="2026-06-08",
            date_end="2026-06-12",
            cost="$525 per person",
            eligibility="Entering K-5th grade in fall 2026",
            is_open=True,
            opportunity_type="Camps",
        ),
        ProgramExtractionResult(
            program_name="Fixture Wildlife Camp -- Wonderful Wildlife Discoveries (June 15-19)",
            audience_grades=["K-5th grade"],
            date_start="2026-06-15",
            date_end="2026-06-19",
            cost="$525 per person",
            eligibility="Entering K-5th grade in fall 2026",
            is_open=True,
            opportunity_type="Camps",
        ),
        ProgramExtractionResult(
            program_name="Fixture Wildlife Camp -- Wildlife on the Move! (July 13-17)",
            audience_grades=["K-5th grade"],
            date_start="2026-07-13",
            date_end="2026-07-17",
            cost="$525 per person",
            eligibility="Entering K-5th grade in fall 2026",
            is_open=True,
            opportunity_type="Camps",
        ),
    ]

    def _zoo_body(self) -> str:
        return (FIXTURES_DIR / "multi_week_camp_page.html").read_text()

    def _zoo_source(self) -> SourceConfig:
        return SourceConfig(
            source_id="fixture_zoo_camp",
            org_name="Fixture Wildlife Camp",
            adapter_type="program_page_multi",
            config={
                "url": self.ZOO_URL,
                "program_kind": "program",
                "opportunity_type": "Camps",
            },
        )

    def test_n_week_rows_yield_n_distinct_dated_priced_camps_events(self, tmp_path):
        llm_client = FixtureProgramLLMClient(list_responses={self.ZOO_URL: self._ZOO_RESULTS})
        adapter = ProgramPageMultiAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=self.ZOO_URL), status=200, body=self._zoo_body())

        events = list(adapter.extract(raw, self._zoo_source()))

        assert len(events) == 3
        assert all(e.opportunity_type == "Camps" for e in events)
        assert all(e.cost == "$525 per person" for e in events)
        assert all(e.description == "" for e in events)  # none sold out

        starts = [e.start.date().isoformat() for e in events]
        assert starts == ["2026-06-08", "2026-06-15", "2026-07-13"]
        # Distinct end dates too -- each is its own independent week,
        # not one blended date range applied to all three.
        ends = {e.end.date().isoformat() for e in events}
        assert len(ends) == 3


class TestSDMathCircleFixtureExtraction:
    """Sprint 029 ticket 002 (issue 30, SUC-045): San Diego Math
    Circle's public master-calendar Google Sheet, registered as
    ``program_page_multi`` (``registry/sources/sd-math-circle.toml``).

    This proves the *mechanism* SUC-045's Main Flow describes -- one
    fetched sheet export, reduced via ``reduce_html_to_text()``, run
    through ``extract_programs()``, with each of its N distinct dated
    items mapped to its own independent ``Event`` -- using a canned
    ``FixtureProgramLLMClient`` result list standing in for what a
    correct extraction of this page's AMC/AIME dated rows would look
    like. This is independent of, and does not contradict,
    ``sd-math-circle.toml``'s own live-verified finding that the real
    ``AnthropicProgramLLMClient`` does not currently produce this
    correct result on this specific grid-shaped sheet (it extracts the
    page's recurring class-group columns instead) -- the real source
    is registered ``enabled = false`` for exactly that reason. This
    test demonstrates the adapter's N-results-to-N-Events mapping
    itself is sound, the same code path every other ``program_page_multi``
    source already relies on.

    Fixture body is ``tests/fixtures/program_pages/
    sd_math_circle_calendar.csv`` -- a trimmed, real excerpt of the
    live 2025-2026 Master Calendar sheet's actual CSV export (real
    row/column shape: recurring class-group columns interleaved with
    one-off competition-dated rows), matching the CSV export form
    actually registered in ``config.url``.
    """

    URL = (
        "https://docs.google.com/spreadsheets/d/18u6y_7MGD3ZQCIBh7fqE5TZTK0qzP0Ns6z1A9_5W0oA"
        "/export?format=csv&gid=28676418"
    )

    #: Five distinct dated competition items, standing in for a correct
    #: extraction of the fixture CSV's AMC/AIME rows -- deliberately
    #: not the wrong "class group" results the real live LLM call
    #: currently returns for this page (see class docstring).
    _RESULTS = [
        ProgramExtractionResult(
            program_name="AMC 10 A and AMC 12 A",
            audience_grades=["9th grade", "10th grade", "11th grade", "12th grade"],
            date_start="2025-11-05",
            date_end="",
            cost="",
            eligibility="",
            is_open=True,
            opportunity_type="Competitions",
        ),
        ProgramExtractionResult(
            program_name="AMC 10 B and AMC 12 B",
            audience_grades=["9th grade", "10th grade", "11th grade", "12th grade"],
            date_start="2025-11-13",
            date_end="",
            cost="",
            eligibility="",
            is_open=True,
            opportunity_type="Competitions",
        ),
        ProgramExtractionResult(
            program_name="AMC 8",
            audience_grades=["6th grade", "7th grade", "8th grade"],
            date_start="2026-01-25",
            date_end="",
            cost="",
            eligibility="",
            is_open=True,
            opportunity_type="Competitions",
        ),
        ProgramExtractionResult(
            program_name="AIME I",
            audience_grades=["9th grade", "10th grade", "11th grade", "12th grade"],
            date_start="2026-02-05",
            date_end="",
            cost="",
            eligibility="AMC 10/12 qualifiers only",
            is_open=True,
            opportunity_type="Competitions",
        ),
        ProgramExtractionResult(
            program_name="American Regions Math League (ARML)",
            audience_grades=["9th grade", "10th grade", "11th grade", "12th grade"],
            date_start="2026-05-29",
            date_end="2026-05-30",
            cost="",
            eligibility="By evaluation and invitation",
            is_open=True,
            opportunity_type="Competitions",
        ),
    ]

    def _body(self) -> str:
        return (FIXTURES_DIR / "sd_math_circle_calendar.csv").read_text()

    def _source(self) -> SourceConfig:
        return SourceConfig(
            source_id="fixture_sd_math_circle",
            org_name="Fixture San Diego Math Circle",
            adapter_type="program_page_multi",
            config={
                "url": self.URL,
                "program_kind": "program",
                "opportunity_type": "Competitions",
            },
        )

    def test_n_dated_rows_yield_n_distinct_competitions_events(self, tmp_path):
        llm_client = FixtureProgramLLMClient(list_responses={self.URL: self._RESULTS})
        adapter = ProgramPageMultiAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=self.URL), status=200, body=self._body())

        events = list(adapter.extract(raw, self._source()))

        assert len(events) == 5
        assert all(e.opportunity_type == "Competitions" for e in events)
        assert all(e.url == self.URL for e in events)
        assert all(e.source_id == "fixture_sd_math_circle" for e in events)

        titles = [e.title for e in events]
        assert titles == [
            "AMC 10 A and AMC 12 A",
            "AMC 10 B and AMC 12 B",
            "AMC 8",
            "AIME I",
            "American Regions Math League (ARML)",
        ]
        # Each record keeps its own distinct start date -- proves
        # independent per-record mapping, not one shared date (the
        # real live LLM call's actual, wrong failure mode for this
        # page -- see class docstring) applied to every result.
        starts = [e.start.date().isoformat() for e in events]
        assert starts == ["2025-11-05", "2025-11-13", "2026-01-25", "2026-02-05", "2026-05-29"]
        assert len(set(starts)) == 5

        arml = events[-1]
        assert arml.end.date().isoformat() == "2026-05-30"


class TestSDCECFixtureExtraction:
    """Sprint 029 ticket 004 (issue 30, SUC-047): SDCEC's hand-curated
    youth STEM event list, registered as ``program_page_multi``
    (``registry/sources/sdcec.toml``), with no ``opportunity_type``
    override -- the list mixes competitions with other opportunity
    types, so each item keeps the LLM's own per-record classification
    (matching ``TestSDFestivalOfScienceEngineeringRegistration``'s/
    ticket 003's identical no-override reasoning).

    This proves the *mechanism* SUC-047's Main Flow describes -- one
    fetched page, run through ``extract_programs()``, with N
    independently-typed inline records (including the Engineers Week
    Awards Banquet) each mapped to its own ``Event`` -- using a canned
    ``FixtureProgramLLMClient`` result list, the same "mechanism is
    fixture-proven instead" approach ticket 003 used
    (``TestSDFestivalOfScienceEngineeringListingSource``) once its own
    live verification found the real page's content did not exercise
    the happy path. ``sdcec.toml``'s own live-verified finding is that
    the real ``AnthropicProgramLLMClient`` call is non-deterministic on
    the real ``/stem`` page (0/17/21/32 distinct result sets across four
    real calls) and that no live Feb 20 2026 Engineers Week awards
    record currently exists on the site at all -- the real source is
    registered ``enabled = false`` for exactly those reasons (see that
    file's own header comment). This test demonstrates the adapter's
    N-results-to-N-Events mapping itself is sound, the same code path
    every other ``program_page_multi`` source already relies on.

    Fixture body is
    ``tests/fixtures/program_pages/sdcec_stem_page.html`` -- a small
    fixture reproducing the real page's shape: an unlabeled "current"
    curated list followed by an undated-by-item "Prior sTEm Events"
    archive section on the same page.
    """

    URL = "https://www.sandiegoengineers.org/stem"

    #: Three distinct items from the "current" section, standing in for
    #: a correct extraction of this page's curated list -- deliberately
    #: independently typed (Competitions, Camps, Out-of-school
    #: Programs), per SUC-047's own "no override, let the LLM classify
    #: each record independently" design.
    _RESULTS = [
        ProgramExtractionResult(
            program_name="San Diego Engineers Week Awards Banquet",
            audience_grades=[],
            date_start="2026-02-20",
            date_end="",
            cost="",
            eligibility="K-12 and professional honorees",
            is_open=True,
            opportunity_type="Competitions",
        ),
        ProgramExtractionResult(
            program_name="Optics Workshop",
            audience_grades=["3rd grade", "4th grade", "5th grade", "6th grade", "7th grade", "8th grade"],
            date_start="2026-09-12",
            date_end="",
            cost="",
            eligibility="girls grade 3-8",
            is_open=True,
            opportunity_type="Camps",
        ),
        ProgramExtractionResult(
            program_name="Congressional App Challenge",
            audience_grades=["8th grade", "9th grade", "10th grade", "11th grade", "12th grade"],
            date_start="2026-06-01",
            date_end="2026-10-28",
            cost="",
            eligibility="teens 13-18",
            is_open=True,
            opportunity_type="Competitions",
        ),
    ]

    def _body(self) -> str:
        return (FIXTURES_DIR / "sdcec_stem_page.html").read_text()

    def _source(self) -> SourceConfig:
        return SourceConfig(
            source_id="fixture_sdcec",
            org_name="Fixture San Diego County Engineering Council",
            adapter_type="program_page_multi",
            config={
                "url": self.URL,
                "program_kind": "program",
                # Deliberately no opportunity_type override -- see class
                # docstring.
            },
        )

    def test_n_curated_items_yield_n_independently_typed_events(self, tmp_path):
        llm_client = FixtureProgramLLMClient(list_responses={self.URL: self._RESULTS})
        adapter = ProgramPageMultiAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=self.URL), status=200, body=self._body())

        events = list(adapter.extract(raw, self._source()))

        assert len(events) == 3
        assert all(e.url == self.URL for e in events)
        assert all(e.source_id == "fixture_sdcec" for e in events)

        awards, optics, cac = events
        assert awards.title == "San Diego Engineers Week Awards Banquet"
        assert awards.start == datetime.fromisoformat("2026-02-20")
        assert awards.opportunity_type == "Competitions"

        assert optics.opportunity_type == "Camps"
        assert cac.opportunity_type == "Competitions"

        # Independently classified -- no config override forced a
        # single shared opportunity_type onto all three (SUC-047's own
        # "no override" design point).
        assert len({e.opportunity_type for e in events}) == 2
        assert len({e.identity_key() for e in events}) == 3

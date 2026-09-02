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
        llm_client = _llm_client()
        adapter = ProgramPageMultiAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        list(adapter.extract(raw, _source()))

        assert llm_client.list_calls == [(PAGE_URL, _page_body())]
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

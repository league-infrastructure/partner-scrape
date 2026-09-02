"""Tests for partner_scrape.adapters.program_page: the ``program_page`` adapter.

Sprint 027 ticket 003. Every test drives the adapter directly (construction
+ ``.discover()``/``.extract()`` calls), matching ``tests/test_adapters_lever.py``'s
and ``tests/test_adapters_listing_html.py``'s existing convention rather than
going through ``adapters.run()``. No test here opens a real network socket or
calls the real Anthropic API -- LLM extraction is always driven through
``program_llm.FixtureProgramLLMClient`` over the saved page fixture at
``tests/fixtures/program_pages/prose_program_page.html``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from partner_scrape.adapters import ADAPTERS, get_adapter
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.program_cache import ProgramExtractionCache
from partner_scrape.adapters.program_llm import (
    PROGRAM_LLM_CONFIDENCE,
    PROGRAM_LLM_SOURCE,
    FixtureProgramLLMClient,
    ProgramExtractionResult,
)
from partner_scrape.adapters.program_page import ProgramPageAdapter
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Event, Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "program_pages"
PAGE_URL = "https://example.org/programs/fre-hs"


def _page_body() -> str:
    return (FIXTURES_DIR / "prose_program_page.html").read_text()


def _extraction_result(**overrides) -> ProgramExtractionResult:
    defaults = dict(
        program_name="Fixture Research Experience for High School Students",
        audience_grades=["10th grade", "11th grade", "12th grade"],
        date_start="2026-12-01",
        date_end="2027-02-15",
        cost="$2,500 stipend",
        eligibility="Current 10th-12th grade students residing in San Diego County.",
        is_open=True,
        opportunity_type="Out-of-school Programs",
    )
    defaults.update(overrides)
    return ProgramExtractionResult(**defaults)


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


def _source(
    program_kind: str | None = "internship",
    url: str = PAGE_URL,
    opportunity_type: str | None = None,
    apply_url: str | None = None,
) -> SourceConfig:
    config: dict = {"url": url}
    if program_kind is not None:
        config["program_kind"] = program_kind
    if opportunity_type is not None:
        config["opportunity_type"] = opportunity_type
    if apply_url is not None:
        config["apply_url"] = apply_url
    return SourceConfig(
        source_id="fixture_program",
        org_name="Fixture Program",
        adapter_type="program_page",
        config=config,
    )


def _llm_client(result: ProgramExtractionResult | None = None) -> FixtureProgramLLMClient:
    return FixtureProgramLLMClient(responses={PAGE_URL: result or _extraction_result()})


class TestDiscover:
    def test_discover_returns_exactly_one_ref_for_the_configured_url(self, tmp_path):
        adapter = ProgramPageAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))

        refs = adapter.discover(_source(), FixtureFetcher({}))

        assert [r.url for r in refs] == [PAGE_URL]

    def test_missing_url_raises(self, tmp_path):
        adapter = ProgramPageAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        source = SourceConfig(
            source_id="fixture_program",
            org_name="Fixture Program",
            adapter_type="program_page",
            config={"program_kind": "internship"},
        )

        try:
            adapter.discover(source, FixtureFetcher({}))
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError for missing url")


class TestEndToEndExtraction:
    def test_full_chain_produces_one_event_with_expected_fields(self, tmp_path):
        llm_client = _llm_client()
        adapter = ProgramPageAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        source = _source(program_kind="internship")
        fetcher = _fetcher()

        refs = adapter.discover(source, fetcher)
        assert len(refs) == 1
        raw = adapter.fetch(refs[0], fetcher, source)
        events = list(adapter.extract(raw, source))

        assert len(events) == 1
        event = events[0]
        assert event.kind == "internship"
        assert event.title == "Fixture Research Experience for High School Students"
        assert event.start == datetime.fromisoformat("2026-12-01")
        assert event.end == datetime.fromisoformat("2027-02-15")
        assert event.eligibility == "Current 10th-12th grade students residing in San Diego County."
        assert event.opportunity_type == "Out-of-school Programs"
        assert event.cost == "$2,500 stipend"
        assert event.registration_url == PAGE_URL
        assert event.url == PAGE_URL
        assert event.source_id == "fixture_program"

        for field_name in ("title", "start", "end", "eligibility", "opportunity_type", "cost", "registration_url"):
            assert event.field_provenance[field_name] == Provenance(
                source=PROGRAM_LLM_SOURCE, confidence=PROGRAM_LLM_CONFIDENCE
            )

    def test_program_kind_program_with_opportunity_type_override(self, tmp_path):
        llm_client = _llm_client()
        adapter = ProgramPageAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        source = _source(program_kind="program", opportunity_type="Funding Opportunities")
        fetcher = _fetcher()

        raw = adapter.fetch(EventRef(url=PAGE_URL), fetcher, source)
        events = list(adapter.extract(raw, source))

        assert len(events) == 1
        event = events[0]
        assert event.kind == "program"
        assert event.opportunity_type == "Funding Opportunities"
        assert event.field_provenance["opportunity_type"] == Provenance(
            source="program_page", confidence=1.0
        )

    def test_apply_url_override_is_used_as_registration_url(self, tmp_path):
        apply_url = "https://example.org/apply/fre-hs"
        llm_client = _llm_client()
        adapter = ProgramPageAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        source = _source(apply_url=apply_url)
        fetcher = _fetcher()

        raw = adapter.fetch(EventRef(url=PAGE_URL), fetcher, source)
        events = list(adapter.extract(raw, source))

        assert events[0].registration_url == apply_url


class TestProgramKind:
    def test_internship_program_kind_produces_internship_event(self, tmp_path):
        adapter = ProgramPageAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, _source(program_kind="internship")))

        assert events[0].kind == "internship"

    def test_program_program_kind_produces_program_event(self, tmp_path):
        adapter = ProgramPageAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, _source(program_kind="program")))

        assert events[0].kind == "program"

    def test_missing_program_kind_is_logged_and_skipped(self, tmp_path):
        adapter = ProgramPageAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, _source(program_kind=None)))

        assert events == []

    def test_invalid_program_kind_is_logged_and_skipped(self, tmp_path):
        adapter = ProgramPageAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, _source(program_kind="event")))

        assert events == []


class TestCache:
    def test_second_extract_for_unchanged_body_makes_no_further_llm_call(self, tmp_path):
        llm_client = _llm_client()
        cache = ProgramExtractionCache(tmp_path)
        adapter = ProgramPageAdapter(llm_client=llm_client, cache=cache)
        source = _source()
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        first = list(adapter.extract(raw, source))
        assert len(llm_client.calls) == 1

        second = list(adapter.extract(raw, source))
        assert len(llm_client.calls) == 1

        assert len(first) == len(second) == 1
        assert first[0].title == second[0].title

    def test_changed_body_makes_a_fresh_llm_call(self, tmp_path):
        cache = ProgramExtractionCache(tmp_path)
        llm_client = FixtureProgramLLMClient(
            responses={
                (PAGE_URL, "body one"): _extraction_result(program_name="First"),
                (PAGE_URL, "body two"): _extraction_result(program_name="Second"),
            },
            key_fn=lambda url, body: (url, body),
        )
        adapter = ProgramPageAdapter(llm_client=llm_client, cache=cache)
        source = _source()

        raw_one = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body="body one")
        raw_two = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body="body two")

        events_one = list(adapter.extract(raw_one, source))
        events_two = list(adapter.extract(raw_two, source))

        assert len(llm_client.calls) == 2
        assert events_one[0].title == "First"
        assert events_two[0].title == "Second"


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self, tmp_path):
        adapter = ProgramPageAdapter(llm_client=_llm_client(), cache=ProgramExtractionCache(tmp_path))
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []
        assert adapter.llm_client.calls == []


class TestClosedPageStillEmitted:
    def test_closed_page_with_no_future_dates_is_still_emitted_as_an_event(self, tmp_path):
        """Filtering "is this still current" happens at export time
        (``export.writer.is_current_or_upcoming``), never here -- a closed
        page with no known future date_end/date_start still produces an
        Event.
        """
        result = _extraction_result(is_open=False, date_start="", date_end="")
        adapter = ProgramPageAdapter(
            llm_client=FixtureProgramLLMClient(responses={PAGE_URL: result}),
            cache=ProgramExtractionCache(tmp_path),
        )
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, _source()))

        assert len(events) == 1
        assert events[0].start is None
        assert events[0].end is None


class TestDispatchRegistration:
    def test_program_page_resolves_via_get_adapter_to_a_working_instance(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SCRAPE_CACHE_DIR", str(tmp_path))
        assert ADAPTERS["program_page"] is ProgramPageAdapter

        adapter = get_adapter("program_page")

        assert isinstance(adapter, ProgramPageAdapter)
        # Zero-arg construction still produces a fully-working instance --
        # the real AnthropicProgramLLMClient/ProgramExtractionCache fill in
        # as defaults (adapters/DESIGN.md's documented deviation).
        refs = adapter.discover(_source(), FixtureFetcher({}))
        assert [r.url for r in refs] == [PAGE_URL]

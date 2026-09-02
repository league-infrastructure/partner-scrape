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

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
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
from partner_scrape.extract.ladder import reduce_html_to_text
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

    def test_extract_program_raising_is_logged_and_skipped_not_raised(self, tmp_path, caplog):
        # Sprint 027 ticket 006's own live verification found a real
        # UCSD Summer Program Finder card (www.rmtlacademy.org) whose
        # fetched body alone exceeded the model's context window,
        # raising anthropic.BadRequestError from inside
        # llm_client.extract_program() -- previously uncaught here.
        # FixtureProgramLLMClient raises a plain KeyError for a URL
        # absent from its `responses` dict, exercising the identical
        # "the LLM call itself raised" code path.
        adapter = ProgramPageAdapter(
            llm_client=FixtureProgramLLMClient(responses={}), cache=ProgramExtractionCache(tmp_path)
        )
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        with caplog.at_level(logging.WARNING):
            events = list(adapter.extract(raw, _source()))

        assert events == []
        assert "extract_program" in caplog.text


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


class TestSoldOutCampDescription:
    """AC (028-003): a resolved ``"Camps"`` record with ``is_open=False``
    gets ``Event.description`` set to a sold-out note; every other
    ``opportunity_type`` leaves it unset, exactly matching pre-ticket
    behavior.
    """

    def test_sold_out_camp_record_gets_a_sold_out_description(self, tmp_path):
        result = _extraction_result(is_open=False, opportunity_type="Camps")
        adapter = ProgramPageAdapter(
            llm_client=FixtureProgramLLMClient(responses={PAGE_URL: result}),
            cache=ProgramExtractionCache(tmp_path),
        )
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, _source(program_kind="program")))

        assert len(events) == 1
        assert events[0].description == "Sold out"
        assert events[0].field_provenance["description"] == Provenance(
            source=PROGRAM_LLM_SOURCE, confidence=PROGRAM_LLM_CONFIDENCE
        )

    def test_sold_out_camp_via_config_opportunity_type_override_still_gets_description(self, tmp_path):
        # opportunity_type resolved via the config override, not the
        # LLM's own classification -- the branch must fire on the
        # *resolved* value either way.
        result = _extraction_result(is_open=False, opportunity_type="Out-of-school Programs")
        adapter = ProgramPageAdapter(
            llm_client=FixtureProgramLLMClient(responses={PAGE_URL: result}),
            cache=ProgramExtractionCache(tmp_path),
        )
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(
            adapter.extract(raw, _source(program_kind="program", opportunity_type="Camps"))
        )

        assert len(events) == 1
        assert events[0].description == "Sold out"

    def test_non_camps_is_open_false_leaves_description_unset(self, tmp_path):
        # AC: a fixture record with is_open=False and a non-"Camps"
        # opportunity_type (an internship) leaves Event.description
        # unset, exactly matching pre-ticket behavior.
        result = _extraction_result(is_open=False, opportunity_type="Out-of-school Programs")
        adapter = ProgramPageAdapter(
            llm_client=FixtureProgramLLMClient(responses={PAGE_URL: result}),
            cache=ProgramExtractionCache(tmp_path),
        )
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, _source(program_kind="internship")))

        assert len(events) == 1
        assert events[0].description == ""
        assert "description" not in events[0].field_provenance

    def test_open_camp_record_leaves_description_unset(self, tmp_path):
        result = _extraction_result(is_open=True, opportunity_type="Camps")
        adapter = ProgramPageAdapter(
            llm_client=FixtureProgramLLMClient(responses={PAGE_URL: result}),
            cache=ProgramExtractionCache(tmp_path),
        )
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, _source(program_kind="program")))

        assert len(events) == 1
        assert events[0].description == ""


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


# ---------------------------------------------------------------------
# HTML-to-text reduction before caching/LLM extraction (sprint 028,
# issue 36)
# ---------------------------------------------------------------------

#: Shared with tests/test_extract_ladder.py -- the ~900KB bloated fixture
#: representative of the SD Foundation site's own live-measured template
#: bloat (a large repeated nav menu plus an inline script payload on
#: every page).
BLOATED_PAGE_URL = "https://example.org/scholarships/community"


def _bloated_page_body() -> str:
    return (FIXTURES_DIR / "sd_foundation_bloated_page.html").read_text()


class TestCacheKeyIsDerivedFromReducedTextNotRawBody:
    """AC: a fixture test proves the extraction cache key is derived from
    the *reduced* text: a content-only change to a stripped element (a
    ``<script>`` block) does not invalidate an existing cache entry.
    """

    def test_changing_only_a_stripped_script_block_is_still_a_cache_hit(self, tmp_path):
        page_with_script_a = (
            "<html><head><script>var trackingId = 'AAA111';</script></head>"
            "<body><main><h1>Fixture Reduction Cache Program</h1>"
            "<p>Applications open on December 1, 2026 and are due by "
            "February 15, 2027.</p></main></body></html>"
        )
        page_with_script_b = (
            "<html><head><script>var trackingId = 'ZZZ999-completely-different';"
            "</script></head>"
            "<body><main><h1>Fixture Reduction Cache Program</h1>"
            "<p>Applications open on December 1, 2026 and are due by "
            "February 15, 2027.</p></main></body></html>"
        )
        # The two raw bodies genuinely differ -- if the cache still hashed
        # raw.body (pre-sprint-028 behavior), this would be a cache miss.
        assert page_with_script_a != page_with_script_b
        # ...but they reduce to the identical visible text, since
        # <script> content is stripped before hashing.
        assert reduce_html_to_text(page_with_script_a) == reduce_html_to_text(page_with_script_b)

        cache = ProgramExtractionCache(tmp_path)
        llm_client = FixtureProgramLLMClient(responses={PAGE_URL: _extraction_result()})
        adapter = ProgramPageAdapter(llm_client=llm_client, cache=cache)
        source = _source()

        raw_a = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=page_with_script_a)
        raw_b = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=page_with_script_b)

        events_a = list(adapter.extract(raw_a, source))
        assert len(llm_client.calls) == 1

        events_b = list(adapter.extract(raw_b, source))
        assert len(llm_client.calls) == 1  # still one call -- cache hit, not a miss

        assert len(events_a) == len(events_b) == 1
        assert events_a[0].title == events_b[0].title


class TestCompetitionSourceExtraction:
    """Sprint 029 ticket 001's own Testing requirement (SUC-044's own
    Acceptance Criteria): a ``FixtureProgramLLMClient``-based fixture
    test proving one of this ticket's registered competition pages maps
    to a correctly-dated, ``"Competitions"``-typed ``Event`` via the
    existing ``_extract_one_program`` mapping -- the identical
    ``program_page`` mechanism sprint 027/028 already ship and test
    above, exercised here with ``config.opportunity_type =
    "Competitions"`` instead of ``"Funding Opportunities"``/``"Camps"``.
    No new adapter code: one representative fixture is sufficient, per
    the ticket's own Testing note, since the mapping logic itself is
    unchanged and already covered by the tests above.
    """

    def test_competition_page_maps_to_a_correctly_dated_competitions_event(self, tmp_path):
        result = _extraction_result(
            program_name="SeaPerch San Diego Regional",
            audience_grades=["6th grade", "7th grade", "8th grade", "9th grade", "10th grade"],
            date_start="2026-04-04",
            date_end="2026-04-04",
            cost="",
            eligibility="San Diego County student teams building an underwater ROV.",
            is_open=True,
            opportunity_type="Out-of-school Programs",  # LLM's own guess -- must lose to the config override
        )
        llm_client = FixtureProgramLLMClient(responses={PAGE_URL: result})
        adapter = ProgramPageAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        source = _source(program_kind="program", opportunity_type="Competitions")
        fetcher = _fetcher()

        refs = adapter.discover(source, fetcher)
        raw = adapter.fetch(refs[0], fetcher, source)
        events = list(adapter.extract(raw, source))

        assert len(events) == 1
        event = events[0]
        assert event.kind == "program"
        assert event.title == "SeaPerch San Diego Regional"
        assert event.start == datetime.fromisoformat("2026-04-04")
        assert event.end == datetime.fromisoformat("2026-04-04")
        assert event.opportunity_type == "Competitions"
        assert event.field_provenance["opportunity_type"] == Provenance(
            source="program_page", confidence=1.0
        )


@dataclass
class _RecordingLLMClient:
    """(Sprint 029 ticket 006) A ``ProgramLLMClient`` test double that
    records the ``profile``/``reference_date`` it was called with --
    unlike ``FixtureProgramLLMClient``, which deliberately ignores both
    (see its own docstring). Used only to prove
    ``program_page.py``'s own profile-selection logic
    (``_resolve_extraction_profile``), not to exercise the LLM client
    contract itself (already covered by ``test_adapters_program_llm.py``).
    """

    result: ProgramExtractionResult
    profile_calls: list[str] = field(default_factory=list)
    reference_date_calls: list[date | None] = field(default_factory=list)

    def extract_program(
        self, url: str, body: str, *, profile: str = "program", reference_date: date | None = None
    ) -> ProgramExtractionResult:
        self.profile_calls.append(profile)
        self.reference_date_calls.append(reference_date)
        return self.result

    def extract_programs(
        self, url: str, body: str, *, profile: str = "program", reference_date: date | None = None
    ) -> list[ProgramExtractionResult]:
        raise NotImplementedError("not exercised by these tests")


class TestExtractionProfileSelection:
    """AC (029-006): ``_extract_one_program`` selects ``profile=
    "competition"`` from ``source.config.get("opportunity_type") ==
    "Competitions"`` -- no new registry ``config`` key -- and threads a
    non-``None`` ``reference_date`` through on every call. Every other
    ``opportunity_type`` (including none at all) keeps the default
    ``profile="program"``, matching pre-ticket behavior exactly.
    """

    def test_competitions_opportunity_type_selects_the_competition_profile(self, tmp_path):
        llm_client = _RecordingLLMClient(result=_extraction_result(opportunity_type="Competitions"))
        adapter = ProgramPageAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        source = _source(program_kind="program", opportunity_type="Competitions")
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        list(adapter.extract(raw, source))

        assert llm_client.profile_calls == ["competition"]
        assert llm_client.reference_date_calls[0] is not None

    def test_non_competitions_opportunity_type_keeps_the_default_program_profile(self, tmp_path):
        llm_client = _RecordingLLMClient(result=_extraction_result(opportunity_type="Camps"))
        adapter = ProgramPageAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        source = _source(program_kind="program", opportunity_type="Camps")
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        list(adapter.extract(raw, source))

        assert llm_client.profile_calls == ["program"]

    def test_no_opportunity_type_override_keeps_the_default_program_profile(self, tmp_path):
        llm_client = _RecordingLLMClient(result=_extraction_result())
        adapter = ProgramPageAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        source = _source(program_kind="internship")
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        list(adapter.extract(raw, source))

        assert llm_client.profile_calls == ["program"]


class TestCompetitionRegistrationDeadlineSeparation:
    """AC (029-006): a ``FixtureProgramLLMClient``-based fixture test
    proving the competition profile correctly separates an event date
    from a distinct registration deadline on one synthetic,
    SeaPerch-shaped page: one page whose text carries both an event date
    and an earlier "TDR due" deadline. The resulting ``Event`` has
    ``start`` == the event date, ``description`` carrying the
    registration deadline note, and no wrong-field collision -- directly
    reproducing (and proving fixed) live-verification's
    ``seaperch-sd-regional`` finding, where the pre-revision prompt
    mapped only the TDR deadline into ``date_end`` and left ``date_start``
    empty.
    """

    def test_event_date_and_registration_deadline_map_to_distinct_fields(self, tmp_path):
        result = _extraction_result(
            program_name="SeaPerch San Diego Regional",
            date_start="2026-04-04",
            date_end="2026-04-04",
            registration_deadline="2026-03-27",
            opportunity_type="Competitions",
        )
        adapter = ProgramPageAdapter(
            llm_client=FixtureProgramLLMClient(responses={PAGE_URL: result}),
            cache=ProgramExtractionCache(tmp_path),
        )
        source = _source(program_kind="program", opportunity_type="Competitions")
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, source))

        assert len(events) == 1
        event = events[0]
        # The event's own date -- never the registration deadline.
        assert event.start == datetime.fromisoformat("2026-04-04")
        assert event.end == datetime.fromisoformat("2026-04-04")
        # The registration deadline surfaces via description, not
        # start/end -- no wrong-field collision.
        assert event.description == "Registration deadline: 2026-03-27"
        assert event.start != datetime.fromisoformat("2026-03-27")
        assert event.end != datetime.fromisoformat("2026-03-27")
        assert event.field_provenance["description"] == Provenance(
            source=PROGRAM_LLM_SOURCE, confidence=PROGRAM_LLM_CONFIDENCE
        )

    def test_no_registration_deadline_leaves_description_unset_for_a_competition(self, tmp_path):
        result = _extraction_result(
            date_start="2026-04-04",
            date_end="",
            registration_deadline="",
            opportunity_type="Competitions",
        )
        adapter = ProgramPageAdapter(
            llm_client=FixtureProgramLLMClient(responses={PAGE_URL: result}),
            cache=ProgramExtractionCache(tmp_path),
        )
        source = _source(program_kind="program", opportunity_type="Competitions")
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, source))

        assert len(events) == 1
        assert events[0].description == ""

    def test_registration_deadline_on_a_non_competition_record_leaves_description_unset(self, tmp_path):
        # A registration_deadline can only be non-empty via the
        # competition profile in production, but _map_result_to_event's
        # own gate is on the *resolved opportunity_type*, not on whether
        # the field happens to be set -- proven directly here.
        result = _extraction_result(
            registration_deadline="2026-03-27", opportunity_type="Out-of-school Programs"
        )
        adapter = ProgramPageAdapter(
            llm_client=FixtureProgramLLMClient(responses={PAGE_URL: result}),
            cache=ProgramExtractionCache(tmp_path),
        )
        raw = RawResponse(ref=EventRef(url=PAGE_URL), status=200, body=_page_body())

        events = list(adapter.extract(raw, _source(program_kind="program")))

        assert len(events) == 1
        assert events[0].description == ""


class TestOversizedPageExtractsSuccessfullyAfterReduction:
    """AC: a ``FixtureProgramLLMClient``-based fixture test proves the
    reduced ~900KB fixture page (representative of the SD Foundation
    site's own live-measured template bloat, issue 36) still yields the
    correct program fields -- where the unreduced raw body alone
    (859KB+) would have exceeded the model's ~200K-token context window
    and raised ``anthropic.BadRequestError`` in production, per the two
    live sprint-027 failures this ticket closes.
    """

    def test_bloated_page_extracts_the_correct_program_fields(self, tmp_path):
        result = _extraction_result(
            program_name="Fixture SD Foundation Community Scholarship",
            date_start="2026-11-01",
            date_end="2027-01-15",
            cost="$5,000 scholarship",
            eligibility="Current 12th grade students residing in San Diego County.",
            opportunity_type="Funding Opportunities",
        )
        llm_client = FixtureProgramLLMClient(responses={BLOATED_PAGE_URL: result})
        adapter = ProgramPageAdapter(llm_client=llm_client, cache=ProgramExtractionCache(tmp_path))
        source = _source(program_kind="program", url=BLOATED_PAGE_URL)
        fetcher = _fetcher(url=BLOATED_PAGE_URL, body=_bloated_page_body())

        refs = adapter.discover(source, fetcher)
        raw = adapter.fetch(refs[0], fetcher, source)
        events = list(adapter.extract(raw, source))

        # The reduced text actually sent to the LLM client is well under
        # the raw fetched body's size -- this is what keeps a page this
        # size from ever reaching the model's context limit.
        assert len(llm_client.calls) == 1
        called_url, called_body = llm_client.calls[0]
        assert called_url == BLOATED_PAGE_URL
        assert len(called_body) < 10_000
        assert len(called_body) < len(raw.body) / 50

        assert len(events) == 1
        event = events[0]
        assert event.title == "Fixture SD Foundation Community Scholarship"
        assert event.start == datetime.fromisoformat("2026-11-01")
        assert event.end == datetime.fromisoformat("2027-01-15")
        assert event.cost == "$5,000 scholarship"
        assert event.eligibility == "Current 12th grade students residing in San Diego County."

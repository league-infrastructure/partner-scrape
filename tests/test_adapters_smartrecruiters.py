"""Tests for partner_scrape.adapters.smartrecruiters: the SmartRecruiters ATS adapter.

Every test drives the adapter through a fixture Fetcher returning
recorded/synthesized SmartRecruiters postings JSON
(tests/fixtures/smartrecruiters/) -- no test here opens a real network
socket, per this sprint's "no live network in tests" acceptance
criterion.

``tests/fixtures/smartrecruiters/postings_page1.json`` mixes six
postings so a single fixture exercises every filtering axis at once,
mirroring ``tests/fixtures/greenhouse/jobs.json``'s convention:
  - "Software Engineering Intern" (San Diego, Engineering, Intern) --
    keeps: internship + STEM + San Diego.
  - "Senior Software Engineer" (San Diego, Engineering, Full-time) --
    drops: not an internship/early-career commitment or title.
  - "Data Science Intern" (Austin, Engineering, Intern) -- drops: not
    San Diego-local.
  - "Marketing Intern" (San Diego, Marketing, Intern) -- drops: not
    STEM.
  - a record with no ``name`` key -- malformed, must be skipped without
    aborting the rest of the page.
  - "Bioinformatics Intern" (La Jolla, Engineering, Intern) -- drops
    under the default ``location_keywords`` (not "San Diego"), but is
    kept when a source overrides ``location_keywords`` to include
    "La Jolla".

``postings_page2.json`` carries one more matching posting
("Hardware Engineering Intern", San Diego) -- its own ``totalFound=150``
(with ``postings_page1.json``, PAGE_SIZE=100) forces a 2-page
``discover()`` result, proving the second page is actually fetched and
its postings included in the final result, not just the first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.smartrecruiters import (
    DEFAULT_API_BASE,
    PAGE_SIZE,
    SmartRecruitersAdapter,
)
from partner_scrape.fetch import DEFAULT_RATE_LIMIT_SECONDS
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "smartrecruiters"

COMPANY = "FixtureCo"
BASE_URL = f"{DEFAULT_API_BASE}/{COMPANY}/postings"


def _page_url(offset: int) -> str:
    return f"{BASE_URL}?limit={PAGE_SIZE}&offset={offset}"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


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
    company: str = COMPANY,
    location_keywords: list[str] | None = None,
    acquisition_policy: dict | None = None,
) -> SourceConfig:
    config: dict = {"company": company}
    if location_keywords is not None:
        config["location_keywords"] = location_keywords
    return SourceConfig(
        source_id="fixture_co",
        org_name="Fixture Co",
        adapter_type="smartrecruiters",
        config=config,
        acquisition_policy=acquisition_policy or {},
    )


def _two_page_fetcher() -> FixtureFetcher:
    return FixtureFetcher(
        {
            _page_url(0): _response(_read_fixture("postings_page1.json")),
            _page_url(PAGE_SIZE): _response(_read_fixture("postings_page2.json")),
        }
    )


def _single_page_fetcher() -> FixtureFetcher:
    return FixtureFetcher({_page_url(0): _response(_read_fixture("postings_single_page.json"))})


def _empty_fetcher() -> FixtureFetcher:
    return FixtureFetcher({_page_url(0): _response(_read_fixture("postings_empty.json"))})


class TestDiscover:
    def test_discover_returns_one_ref_per_page_derived_from_total_found(self):
        adapter = SmartRecruitersAdapter()

        refs = adapter.discover(_source(), _two_page_fetcher())

        assert [r.url for r in refs] == [_page_url(0), _page_url(PAGE_SIZE)]
        assert [r.context for r in refs] == [{"offset": 0}, {"offset": PAGE_SIZE}]

    def test_discover_single_page_case_returns_exactly_one_ref(self):
        adapter = SmartRecruitersAdapter()

        refs = adapter.discover(_source(), _single_page_fetcher())

        assert [r.url for r in refs] == [_page_url(0)]

    def test_discover_honors_an_api_base_override(self):
        adapter = SmartRecruitersAdapter()
        source = SourceConfig(
            source_id="fixture_co",
            org_name="Fixture Co",
            adapter_type="smartrecruiters",
            config={"company": COMPANY, "api_base": "https://example.org/custom/companies"},
        )
        fetcher = FixtureFetcher(
            {
                f"https://example.org/custom/companies/{COMPANY}/postings"
                f"?limit={PAGE_SIZE}&offset=0": _response(_read_fixture("postings_single_page.json"))
            }
        )

        refs = adapter.discover(source, fetcher)

        assert refs[0].url.startswith("https://example.org/custom/companies")

    def test_missing_company_raises(self):
        adapter = SmartRecruitersAdapter()
        source = SourceConfig(
            source_id="fixture_co",
            org_name="Fixture Co",
            adapter_type="smartrecruiters",
            config={},
        )

        try:
            adapter.discover(source, FixtureFetcher({}))
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError for missing company")

    def test_probe_failure_degrades_to_one_page(self):
        adapter = SmartRecruitersAdapter()
        fetcher = FixtureFetcher({_page_url(0): _response("", status=500)})

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == [_page_url(0)]

    def test_probe_unparseable_json_degrades_to_one_page(self):
        adapter = SmartRecruitersAdapter()
        fetcher = FixtureFetcher({_page_url(0): _response("not json {")})

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == [_page_url(0)]


class TestFieldMapping:
    def test_matching_posting_maps_all_documented_fields(self):
        events = run(_source(), _two_page_fetcher())

        intern = next(e for e in events if e.title == "Software Engineering Intern")
        assert intern.kind == "internship"
        assert intern.source_id == "fixture_co"
        assert intern.external_id == "744000100000001"
        assert intern.start == datetime(2026, 6, 1, 9, 30, tzinfo=timezone.utc)
        assert intern.location == "San Diego, California, United States"
        assert (
            intern.registration_url
            == f"https://jobs.smartrecruiters.com/{COMPANY}/744000100000001"
        )

    def test_matching_posting_gets_classification_defaults_and_no_cost(self):
        events = run(_source(), _two_page_fetcher())

        intern = next(e for e in events if e.title == "Software Engineering Intern")
        assert intern.age_grade_level == ["Grades 9-12", "Undergraduate"]
        assert intern.time_of_day == ["All Day"]
        assert intern.cost == ""
        assert intern.cost_range == ""
        assert "cost" not in intern.field_provenance
        assert "cost_range" not in intern.field_provenance

    def test_every_field_the_adapter_sets_has_smartrecruiters_provenance_at_full_confidence(self):
        events = run(_source(), _two_page_fetcher())

        intern = next(e for e in events if e.title == "Software Engineering Intern")
        assert intern.field_provenance
        for prov in intern.field_provenance.values():
            assert prov == Provenance(source="smartrecruiters", confidence=1.0)


class TestPagination:
    def test_second_page_postings_are_included_in_the_result(self):
        events = run(_source(), _two_page_fetcher())

        titles = {e.title for e in events}
        assert "Hardware Engineering Intern" in titles


class TestFiltering:
    def test_only_the_internship_stem_san_diego_postings_survive_under_default_keywords(self):
        events = run(_source(), _two_page_fetcher())

        titles = {e.title for e in events}
        assert titles == {"Software Engineering Intern", "Hardware Engineering Intern"}

    def test_non_internship_posting_is_dropped(self):
        events = run(_source(), _two_page_fetcher())
        assert "Senior Software Engineer" not in {e.title for e in events}

    def test_non_local_posting_is_dropped(self):
        events = run(_source(), _two_page_fetcher())
        assert "Data Science Intern" not in {e.title for e in events}

    def test_non_stem_posting_is_dropped(self):
        events = run(_source(), _two_page_fetcher())
        assert "Marketing Intern" not in {e.title for e in events}


class TestLocationKeywordsOverride:
    def test_override_widens_the_match_set_with_no_code_change(self):
        source = _source(location_keywords=["La Jolla", "San Diego"])

        events = run(source, _two_page_fetcher())

        titles = {e.title for e in events}
        assert "Bioinformatics Intern" in titles

    def test_bioinformatics_intern_dropped_by_default_keywords(self):
        events = run(_source(), _two_page_fetcher())
        assert "Bioinformatics Intern" not in {e.title for e in events}


class TestAcquisitionPolicyThreading:
    def test_sources_acquisition_policy_reaches_fetcher_get(self):
        fetcher = _single_page_fetcher()
        source = _source(acquisition_policy={"rate_limit_seconds": 4.0, "respect_robots": False})

        run(source, fetcher)

        assert fetcher.policy_calls[_page_url(0)] == (4.0, False)

    def test_source_with_no_acquisition_policy_still_gets_polite_fetcher_defaults(self):
        fetcher = _single_page_fetcher()

        run(_source(), fetcher)

        assert fetcher.policy_calls[_page_url(0)] == (DEFAULT_RATE_LIMIT_SECONDS, True)


class TestMalformedRecordIsolation:
    def test_missing_name_record_is_skipped_rest_of_page_survives(self):
        events = run(_source(location_keywords=["La Jolla", "San Diego"]), _two_page_fetcher())

        # 6 records on page 1 (1 missing name, skipped; 3 filtered out;
        # 2 kept under widened keywords) + 1 kept record on page 2 = 3.
        assert len(events) == 3
        assert all(e.title for e in events)


class TestEmptyResponse:
    def test_empty_content_list_yields_zero_events_and_no_exception(self):
        events = run(_source(), _empty_fetcher())
        assert events == []


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self):
        adapter = SmartRecruitersAdapter()
        raw = RawResponse(ref=EventRef(url=_page_url(0)), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_events_without_raising(self):
        adapter = SmartRecruitersAdapter()
        raw = RawResponse(ref=EventRef(url=_page_url(0)), status=200, body="not json {")

        assert list(adapter.extract(raw, _source())) == []

    def test_unexpected_json_shape_returns_no_events_without_raising(self):
        adapter = SmartRecruitersAdapter()
        raw = RawResponse(ref=EventRef(url=_page_url(0)), status=200, body="[]")

        assert list(adapter.extract(raw, _source())) == []

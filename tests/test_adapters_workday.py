"""Tests for partner_scrape.adapters.workday: the Workday CXS ATS adapter.

Every test drives the adapter through a fixture Fetcher returning
recorded/hand-modeled Workday jobPostings JSON
(tests/fixtures/workday/) -- no test here opens a real network socket,
per this sprint's "no live network in tests" acceptance criterion.

Unlike every other adapter in this family (greenhouse/lever/
smartrecruiters/workable), every one of a Workday source's pages shares
the *same* URL -- pagination lives entirely in the POST body's
``offset`` field (this is exactly why ``PoliteFetcher.post()``,
ticket 004, never caches). ``FixtureFetcher.post`` below is keyed by
``offset`` rather than URL for this reason.

``tests/fixtures/workday/jobs_page1.json`` mixes six real-record-shaped
postings so a single fixture exercises every filtering axis at once,
mirroring ``tests/fixtures/smartrecruiters/postings_page1.json``'s
convention:
  - "Software Engineering Intern" (San Diego) -- keeps: internship +
    STEM + San Diego.
  - "Senior Software Engineer" (San Diego) -- drops: not an
    internship/early-career title.
  - "Data Science Intern" (Austin) -- drops: not San Diego-local.
  - "Marketing Intern" (San Diego) -- drops: not STEM (Workday's
    list-view API has no department field to check either).
  - a record with no ``title`` key -- malformed, must be skipped
    without aborting the rest of the page.
  - "2027 High School Engineering Intern Program - San Diego CA" (San
    Diego, ``postedOn="Posted 30+ Days Ago"``) -- models Northrop
    Grumman's HS Internship Program req (see adapters/workday.py's
    module docstring for why this is hand-modeled rather than a live
    capture: the real req lives on a Workday site that returns 403 to
    this project's bot). Also this fixture's relative-date-only record,
    proving no ``Event.start`` gets fabricated from it.
  - "Bioinformatics Intern" (La Jolla) -- drops under the default
    ``location_keywords`` (not "San Diego"), but is kept when a source
    overrides ``location_keywords`` to include "La Jolla".

``jobs_page2.json`` carries one more matching posting ("Hardware
Engineering Intern", San Diego) -- its own ``total=25`` (with
``jobs_page1.json``, ``PAGE_SIZE=20``) forces a 2-page ``discover()``
result, proving the second page is actually fetched (via a distinct
``offset``, not a distinct URL) and its postings included in the final
result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.workday import (
    MAX_PAGES,
    PAGE_SIZE,
    WorkdayAdapter,
    _careers_url,
    _jobs_url,
)
from partner_scrape.fetch import DEFAULT_RATE_LIMIT_SECONDS
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "workday"

TENANT = "ngc"
SITE = "Fixture_External_Site"
API_BASE = "https://ngc.wd1.myworkdayjobs.com"
JOBS_URL = f"{API_BASE}/wday/cxs/{TENANT}/{SITE}/jobs"
CAREERS_URL = f"{API_BASE}/{SITE}"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def _response(body: str, status: int = 200) -> FetchResponse:
    return FetchResponse(url=JOBS_URL, status=status, headers={}, body=body)


@dataclass
class FixtureFetcher:
    """Fetcher test double -- returns canned FetchResponses, no socket.

    Keyed by the POST body's ``offset`` (not URL): every Workday page
    shares one URL, so a URL-keyed double (this family's usual
    convention, e.g. ``tests/test_adapters_smartrecruiters.py``) cannot
    tell pages apart here -- see this module's own docstring.
    """

    responses: dict[int, FetchResponse]
    calls: list[tuple[str, dict[str, Any], dict[str, str] | None]] = field(default_factory=list)
    policy_calls: dict[int, tuple[float, bool]] = field(default_factory=dict)

    def post(
        self,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
        rate_limit_seconds: float = 1.0,
        respect_robots: bool = True,
    ) -> FetchResponse:
        offset = body.get("offset", 0)
        self.calls.append((url, body, headers))
        self.policy_calls[offset] = (rate_limit_seconds, respect_robots)
        return self.responses[offset]


def _source(
    tenant: str = TENANT,
    site: str = SITE,
    api_base: str = API_BASE,
    location_keywords: list[str] | None = None,
    acquisition_policy: dict | None = None,
    config_overrides: dict | None = None,
) -> SourceConfig:
    config: dict = {"tenant": tenant, "site": site, "api_base": api_base}
    if location_keywords is not None:
        config["location_keywords"] = location_keywords
    if config_overrides:
        config.update(config_overrides)
    return SourceConfig(
        source_id="fixture_co",
        org_name="Fixture Co",
        adapter_type="workday",
        config=config,
        acquisition_policy=acquisition_policy or {},
    )


def _two_page_fetcher() -> FixtureFetcher:
    return FixtureFetcher(
        {
            0: _response(_read_fixture("jobs_page1.json")),
            PAGE_SIZE: _response(_read_fixture("jobs_page2.json")),
        }
    )


def _single_page_fetcher() -> FixtureFetcher:
    return FixtureFetcher({0: _response(_read_fixture("jobs_single_page.json"))})


def _empty_fetcher() -> FixtureFetcher:
    return FixtureFetcher({0: _response(_read_fixture("jobs_empty.json"))})


class TestUrlBuilding:
    def test_jobs_url_joins_api_base_tenant_and_site(self):
        assert _jobs_url(_source()) == JOBS_URL

    def test_careers_url_joins_api_base_and_site(self):
        assert _careers_url(_source()) == CAREERS_URL

    def test_api_base_trailing_slash_does_not_double_up(self):
        source = _source(api_base=f"{API_BASE}/")
        assert _jobs_url(source) == JOBS_URL
        assert _careers_url(source) == CAREERS_URL


class TestDiscover:
    def test_discover_returns_one_ref_per_page_derived_from_total(self):
        adapter = WorkdayAdapter()

        refs = adapter.discover(_source(), _two_page_fetcher())

        assert [r.url for r in refs] == [JOBS_URL, JOBS_URL]
        assert [r.context for r in refs] == [{"offset": 0}, {"offset": PAGE_SIZE}]

    def test_discover_single_page_case_returns_exactly_one_ref(self):
        adapter = WorkdayAdapter()

        refs = adapter.discover(_source(), _single_page_fetcher())

        assert [r.url for r in refs] == [JOBS_URL]
        assert refs[0].context == {"offset": 0}

    def test_probe_body_uses_offset_zero_and_empty_search_text(self):
        adapter = WorkdayAdapter()
        fetcher = _single_page_fetcher()

        adapter.discover(_source(), fetcher)

        probe_url, probe_body, _ = fetcher.calls[0]
        assert probe_url == JOBS_URL
        assert probe_body == {"appliedFacets": {}, "limit": PAGE_SIZE, "offset": 0, "searchText": ""}

    def test_probe_failure_degrades_to_one_page(self):
        adapter = WorkdayAdapter()
        fetcher = FixtureFetcher({0: _response("", status=500)})

        refs = adapter.discover(_source(), fetcher)

        assert [r.context for r in refs] == [{"offset": 0}]

    def test_probe_unparseable_json_degrades_to_one_page(self):
        adapter = WorkdayAdapter()
        fetcher = FixtureFetcher({0: _response("not json {")})

        refs = adapter.discover(_source(), fetcher)

        assert [r.context for r in refs] == [{"offset": 0}]

    def test_missing_tenant_raises_key_error(self):
        adapter = WorkdayAdapter()
        source = SourceConfig(
            source_id="fixture_co",
            org_name="Fixture Co",
            adapter_type="workday",
            config={"site": SITE, "api_base": API_BASE},
        )

        try:
            adapter.discover(source, FixtureFetcher({}))
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError for missing tenant")

    def test_page_count_capped_at_max_pages(self):
        adapter = WorkdayAdapter()
        # A total far exceeding MAX_PAGES * PAGE_SIZE -- a misreporting
        # source must not enumerate an unbounded number of refs.
        huge_total = (MAX_PAGES + 50) * PAGE_SIZE
        fetcher = FixtureFetcher(
            {0: _response(f'{{"total": {huge_total}, "jobPostings": []}}')}
        )

        refs = adapter.discover(_source(), fetcher)

        assert len(refs) == MAX_PAGES


class TestFetch:
    def test_fetch_posts_the_offset_from_the_refs_context(self):
        adapter = WorkdayAdapter()
        fetcher = _two_page_fetcher()
        ref = EventRef(url=JOBS_URL, context={"offset": PAGE_SIZE})

        raw = adapter.fetch(ref, fetcher, _source())

        assert raw.status == 200
        _, body, _ = fetcher.calls[0]
        assert body["offset"] == PAGE_SIZE

    def test_fetch_sends_browser_like_headers_with_referer_and_accept(self):
        adapter = WorkdayAdapter()
        fetcher = _single_page_fetcher()
        ref = EventRef(url=JOBS_URL, context={"offset": 0})

        adapter.fetch(ref, fetcher, _source())

        _, _, headers = fetcher.calls[0]
        assert headers["Accept"] == "application/json"
        assert headers["Referer"] == CAREERS_URL
        assert "Mozilla" in headers["User-Agent"]


class TestFieldMapping:
    def test_matching_posting_maps_all_documented_fields(self):
        events = run(_source(), _two_page_fetcher())

        intern = next(e for e in events if e.title == "Software Engineering Intern")
        assert intern.kind == "internship"
        assert intern.source_id == "fixture_co"
        assert intern.external_id == "R10000001"
        assert intern.location == "United States-California-San Diego"
        assert (
            intern.registration_url
            == f"{CAREERS_URL}/job/United-States-California-San-Diego/"
            "Software-Engineering-Intern_R10000001"
        )

    def test_matching_posting_gets_no_start_and_no_description(self):
        events = run(_source(), _two_page_fetcher())

        intern = next(e for e in events if e.title == "Software Engineering Intern")
        assert intern.start is None
        assert intern.description == ""

    def test_matching_posting_gets_classification_defaults_and_no_cost(self):
        events = run(_source(), _two_page_fetcher())

        intern = next(e for e in events if e.title == "Software Engineering Intern")
        assert intern.age_grade_level == ["Grades 9-12", "Undergraduate"]
        assert intern.time_of_day == ["All Day"]
        assert intern.cost == ""
        assert intern.cost_range == ""
        assert "cost" not in intern.field_provenance
        assert "cost_range" not in intern.field_provenance

    def test_every_field_the_adapter_sets_has_workday_provenance_at_full_confidence(self):
        events = run(_source(), _two_page_fetcher())

        intern = next(e for e in events if e.title == "Software Engineering Intern")
        assert intern.field_provenance
        for prov in intern.field_provenance.values():
            assert prov == Provenance(source="workday", confidence=1.0)


class TestRelativeDateNeverBecomesStart:
    def test_no_event_produced_by_this_adapter_ever_gets_a_start(self):
        """Workday's list-view API's only date signal is always a
        relative string -- no event this adapter produces should ever
        carry a fabricated ``start``.
        """
        events = run(_source(), _two_page_fetcher())

        assert events  # sanity: the fixture does produce matches
        assert all(e.start is None for e in events)

    def test_posted_30_plus_days_ago_posting_specifically_gets_no_start(self):
        events = run(_source(), _two_page_fetcher())

        hs_program = next(
            e for e in events if "High School Engineering Intern Program" in e.title
        )
        assert hs_program.start is None
        assert "start" not in hs_program.field_provenance


class TestHighSchoolInternshipProgramFixture:
    def test_hs_internship_program_req_survives_classification(self):
        """Models Northrop Grumman's HS Internship Program req -- see
        adapters/workday.py's module docstring and this test file's own
        docstring for why this record is hand-modeled rather than a
        live capture.
        """
        events = run(_source(), _two_page_fetcher())

        titles = {e.title for e in events}
        assert "2027 High School Engineering Intern Program - San Diego CA" in titles


class TestPagination:
    def test_second_page_postings_are_included_in_the_result(self):
        events = run(_source(), _two_page_fetcher())

        titles = {e.title for e in events}
        assert "Hardware Engineering Intern" in titles


class TestFiltering:
    def test_only_the_internship_stem_san_diego_postings_survive_under_default_keywords(self):
        events = run(_source(), _two_page_fetcher())

        titles = {e.title for e in events}
        assert titles == {
            "Software Engineering Intern",
            "2027 High School Engineering Intern Program - San Diego CA",
            "Hardware Engineering Intern",
        }

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
    def test_sources_acquisition_policy_reaches_fetcher_post(self):
        fetcher = _single_page_fetcher()
        source = _source(acquisition_policy={"rate_limit_seconds": 4.0, "respect_robots": False})

        run(source, fetcher)

        assert fetcher.policy_calls[0] == (4.0, False)

    def test_source_with_no_acquisition_policy_still_gets_polite_fetcher_defaults(self):
        fetcher = _single_page_fetcher()

        run(_source(), fetcher)

        assert fetcher.policy_calls[0] == (DEFAULT_RATE_LIMIT_SECONDS, True)


class TestMalformedRecordIsolation:
    def test_missing_title_record_is_skipped_rest_of_page_survives(self):
        events = run(_source(location_keywords=["La Jolla", "San Diego"]), _two_page_fetcher())

        # Page 1: 7 records (1 missing title, skipped; 3 filtered out;
        # 3 kept under widened keywords) + page 2: 1 kept = 4.
        assert len(events) == 4
        assert all(e.title for e in events)

    def test_non_dict_job_record_is_skipped(self):
        adapter = WorkdayAdapter()
        raw = RawResponse(
            ref=EventRef(url=JOBS_URL, context={"offset": 0}),
            status=200,
            body='{"total": 1, "jobPostings": ["not-an-object"]}',
        )

        assert list(adapter.extract(raw, _source())) == []


class TestEmptyResponse:
    def test_empty_job_postings_yields_zero_events_and_no_exception(self):
        events = run(_source(), _empty_fetcher())
        assert events == []


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self):
        adapter = WorkdayAdapter()
        raw = RawResponse(ref=EventRef(url=JOBS_URL, context={"offset": 0}), status=403, body="")

        assert list(adapter.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_events_without_raising(self):
        adapter = WorkdayAdapter()
        raw = RawResponse(
            ref=EventRef(url=JOBS_URL, context={"offset": 0}), status=200, body="not json {"
        )

        assert list(adapter.extract(raw, _source())) == []

    def test_unexpected_json_shape_returns_no_events_without_raising(self):
        adapter = WorkdayAdapter()
        raw = RawResponse(
            ref=EventRef(url=JOBS_URL, context={"offset": 0}), status=200, body="[]"
        )

        assert list(adapter.extract(raw, _source())) == []

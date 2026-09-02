"""Tests for partner_scrape.adapters.neogov: the NEOGOV/governmentjobs.com ATS adapter.

Every test drives the adapter through a fixture Fetcher returning
recorded/synthesized ``loadJobsOnMaps`` JSON
(tests/fixtures/neogov/) -- no test here opens a real network socket,
per this sprint's "no live network in tests" acceptance criterion.

``tests/fixtures/neogov/jobs.json`` mixes seven postings so a single
fixture exercises every filtering axis at once, mirroring
``tests/fixtures/workable/jobs.json``'s convention:
  - "Software Engineering Intern" (FixtureAgency, IT, "Internship"
    category) -- keeps: internship + STEM + San Diego (location
    "City of FixtureAgency, CA" matches the default ``["San Diego"]``
    keyword only via this fixture's own ``_source()`` override below --
    see ``LOCATION_KEYWORDS`` on why a synthetic city needs one).
  - "Senior Civil Engineer" (FixtureAgency, Public Works, "Engineering"
    category) -- drops: not an internship/early-career commitment or
    title.
  - "Data Science Intern" (Austin, TX, "Internship" category) -- drops:
    not San Diego-local.
  - "Marketing Intern" (FixtureAgency, Marketing and Communications,
    "Internship" category) -- drops: not STEM.
  - a record with no ``Classification`` key -- malformed, must be
    skipped without aborting the rest of the response.
  - "Bioinformatics Intern" (La Jolla, CA, "Internship" category) --
    drops under the default location keywords, but is kept when a
    source overrides ``location_keywords`` to include "La Jolla".
  - "Student Worker-...-Undergraduate, Graduate/Tech and High School"
    (FixtureAgency, Human Resources, "Internship" category) -- drops:
    reproduces the real County of San Diego live-verification finding
    (ticket 006 Notes) that an ``"Internship"``-categorized posting can
    still have no STEM-coded title/department.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.neogov import DEFAULT_API_BASE, NeogovAdapter
from partner_scrape.fetch import DEFAULT_RATE_LIMIT_SECONDS
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "neogov"

AGENCY = "fixtureagency"
JOBS_URL = f"{DEFAULT_API_BASE}/{AGENCY}/home/loadJobsOnMaps"

#: The fixture's "local" postings use a synthetic city name
#: ("City of FixtureAgency, CA") rather than a real San Diego one, so
#: every test below passes this override rather than relying on the
#: real ``ats_filters.DEFAULT_LOCATION_KEYWORDS`` -- mirrors
#: ``test_adapters_smartrecruiters.py``'s/``test_adapters_workable.py``'s
#: own ``location_keywords`` override pattern, used here for the base
#: matching set instead of only the widened one.
LOCATION_KEYWORDS = ["FixtureAgency"]


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
    header_calls: dict[str, dict[str, str]] = field(default_factory=dict)

    def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        rate_limit_seconds: float = 1.0,
        respect_robots: bool = True,
    ) -> FetchResponse:
        self.calls.append(url)
        self.policy_calls[url] = (rate_limit_seconds, respect_robots)
        self.header_calls[url] = headers or {}
        return self.responses[url]


def _source(
    agency: str = AGENCY,
    location_keywords: list[str] | None = LOCATION_KEYWORDS,
    acquisition_policy: dict | None = None,
) -> SourceConfig:
    config: dict = {"agency": agency}
    if location_keywords is not None:
        config["location_keywords"] = location_keywords
    return SourceConfig(
        source_id="fixture_agency",
        org_name="Fixture Agency",
        adapter_type="neogov",
        config=config,
        acquisition_policy=acquisition_policy or {},
    )


def _fetcher(fixture_name: str = "jobs.json") -> FixtureFetcher:
    return FixtureFetcher({JOBS_URL: _response(_read_fixture(fixture_name))})


class TestDiscover:
    def test_discover_returns_exactly_one_ref_for_the_agency_url(self):
        adapter = NeogovAdapter()

        refs = adapter.discover(_source(), FixtureFetcher({}))

        assert [r.url for r in refs] == [JOBS_URL]
        assert refs[0].context == {"agency": AGENCY}

    def test_discover_honors_an_api_base_override(self):
        adapter = NeogovAdapter()
        source = SourceConfig(
            source_id="fixture_agency",
            org_name="Fixture Agency",
            adapter_type="neogov",
            config={"agency": AGENCY, "api_base": "https://example.org/custom/careers"},
        )

        refs = adapter.discover(source, FixtureFetcher({}))

        assert refs[0].url == f"https://example.org/custom/careers/{AGENCY}/home/loadJobsOnMaps"

    def test_missing_agency_raises(self):
        adapter = NeogovAdapter()
        source = SourceConfig(
            source_id="fixture_agency",
            org_name="Fixture Agency",
            adapter_type="neogov",
            config={},
        )

        try:
            adapter.discover(source, FixtureFetcher({}))
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError for missing agency")


class TestFetchHeaders:
    def test_fetch_sends_the_three_documented_headers(self):
        adapter = NeogovAdapter()
        fetcher = _fetcher()
        ref = EventRef(url=JOBS_URL, context={"agency": AGENCY})

        adapter.fetch(ref, fetcher, _source())

        headers = fetcher.header_calls[JOBS_URL]
        assert headers["X-Requested-With"] == "XMLHttpRequest"
        assert headers["Accept"] == "application/json, text/javascript, */*; q=0.01"
        assert headers["Referer"] == f"{DEFAULT_API_BASE}/{AGENCY}"


class TestFieldMapping:
    def test_matching_posting_maps_all_documented_fields(self):
        events = run(_source(), _fetcher())

        intern = next(e for e in events if e.title == "Software Engineering Intern")
        assert intern.kind == "internship"
        assert intern.source_id == "fixture_agency"
        assert intern.external_id == "9000001"
        assert intern.start == datetime(2026, 6, 1, tzinfo=timezone.utc)
        assert intern.location == "City of FixtureAgency, CA"
        assert (
            intern.registration_url
            == f"{DEFAULT_API_BASE}/{AGENCY}/jobs/9000001/software-engineering-intern"
        )
        assert "paid summer intern" in intern.description

    def test_matching_posting_gets_classification_defaults_and_no_cost(self):
        events = run(_source(), _fetcher())

        intern = next(e for e in events if e.title == "Software Engineering Intern")
        assert intern.age_grade_level == ["Grades 9-12", "Undergraduate"]
        assert intern.time_of_day == ["All Day"]
        assert intern.cost == ""
        assert intern.cost_range == ""
        assert "cost" not in intern.field_provenance
        assert "cost_range" not in intern.field_provenance
        assert intern.end is None

    def test_every_field_the_adapter_sets_has_neogov_provenance_at_full_confidence(self):
        events = run(_source(), _fetcher())

        intern = next(e for e in events if e.title == "Software Engineering Intern")
        assert intern.field_provenance
        for prov in intern.field_provenance.values():
            assert prov == Provenance(source="neogov", confidence=1.0)


class TestFiltering:
    def test_only_the_internship_stem_local_posting_survives_under_fixture_keywords(self):
        events = run(_source(), _fetcher())

        titles = {e.title for e in events}
        assert titles == {"Software Engineering Intern"}

    def test_non_internship_posting_is_dropped(self):
        events = run(_source(), _fetcher())
        assert "Senior Civil Engineer" not in {e.title for e in events}

    def test_non_local_posting_is_dropped(self):
        events = run(_source(), _fetcher())
        assert "Data Science Intern" not in {e.title for e in events}

    def test_non_stem_posting_is_dropped(self):
        events = run(_source(), _fetcher())
        assert "Marketing Intern" not in {e.title for e in events}

    def test_internship_categorized_but_non_stem_student_worker_posting_is_dropped(self):
        events = run(_source(), _fetcher())
        titles = {e.title for e in events}
        assert not any(t.startswith("Student Worker") for t in titles)


class TestLocationKeywordsOverride:
    def test_override_widens_the_match_set_with_no_code_change(self):
        source = _source(location_keywords=["La Jolla", "FixtureAgency"])

        events = run(source, _fetcher())

        titles = {e.title for e in events}
        assert "Bioinformatics Intern" in titles

    def test_bioinformatics_intern_dropped_by_fixture_default_keywords(self):
        events = run(_source(), _fetcher())
        assert "Bioinformatics Intern" not in {e.title for e in events}


class TestAcquisitionPolicyThreading:
    def test_sources_acquisition_policy_reaches_fetcher_get(self):
        fetcher = _fetcher()
        source = _source(acquisition_policy={"rate_limit_seconds": 4.0, "respect_robots": False})

        run(source, fetcher)

        assert fetcher.policy_calls[JOBS_URL] == (4.0, False)

    def test_source_with_no_acquisition_policy_still_gets_polite_fetcher_defaults(self):
        fetcher = _fetcher()

        run(_source(), fetcher)

        assert fetcher.policy_calls[JOBS_URL] == (DEFAULT_RATE_LIMIT_SECONDS, True)


class TestMalformedRecordIsolation:
    def test_missing_classification_record_is_skipped_rest_of_response_survives(self):
        events = run(_source(location_keywords=["La Jolla", "FixtureAgency"]), _fetcher())

        # 7 records in the fixture: 1 missing Classification (skipped),
        # 4 filtered out by classify_posting (non-internship, non-local,
        # non-STEM, internship-but-non-STEM student worker), 2 kept
        # under the widened keywords.
        assert len(events) == 2
        assert all(e.title for e in events)


class TestEmptyResponse:
    def test_empty_job_list_yields_zero_events_and_no_exception(self):
        events = run(_source(), _fetcher("jobs_empty.json"))
        assert events == []


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self):
        adapter = NeogovAdapter()
        raw = RawResponse(ref=EventRef(url=JOBS_URL), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_events_without_raising(self):
        adapter = NeogovAdapter()
        raw = RawResponse(ref=EventRef(url=JOBS_URL), status=200, body="not json {")

        assert list(adapter.extract(raw, _source())) == []

    def test_unexpected_json_shape_returns_no_events_without_raising(self):
        adapter = NeogovAdapter()
        raw = RawResponse(ref=EventRef(url=JOBS_URL), status=200, body="[]")

        assert list(adapter.extract(raw, _source())) == []

    def test_success_false_returns_no_events_without_raising(self):
        adapter = NeogovAdapter()
        raw = RawResponse(
            ref=EventRef(url=JOBS_URL), status=200, body='{"success": false, "jobList": []}'
        )

        assert list(adapter.extract(raw, _source())) == []

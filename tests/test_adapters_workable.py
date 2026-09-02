"""Tests for partner_scrape.adapters.workable: the Workable ATS adapter.

Every test drives the adapter through a fixture Fetcher returning
recorded/synthesized Workable widget-account JSON
(tests/fixtures/workable/) -- no test here opens a real network socket,
per this sprint's "no live network in tests" acceptance criterion.

``tests/fixtures/workable/jobs.json`` mixes six postings so a single
fixture exercises every filtering axis at once, mirroring
``tests/fixtures/greenhouse/jobs.json``'s convention -- including at
least one confirmed-shape paid 9-week-summer-internship posting per
this ticket's own acceptance criteria:
  - "Software Engineering Summer Internship - Airport Operations" (San Diego,
    Information & Technology Services, "Internship") -- keeps:
    internship + STEM + San Diego. Reproduces the real account's
    confirmed paid-9-week-summer-internship shape (issue 31's own
    census finding), which is not among this account's *currently*
    open postings (live-verified 2026-09-02: 0 of 5 current postings
    are internships) -- see ticket 003's Notes.
  - "Airport Traffic Officer" (San Diego, Landside Operations,
    "Full-time") -- drops: not an internship/early-career commitment or
    title.
  - "Data Analytics Intern" (Los Angeles) -- drops: not San Diego-local.
  - "Marketing Coordinator Intern" (San Diego, Art & Customer
    Relations) -- drops: not STEM.
  - a record with no ``title`` key -- malformed, must be skipped
    without aborting the rest of the response.
  - "Bioinformatics Intern" (La Jolla) -- drops under the default
    ``location_keywords`` (not "San Diego"), but is kept when a source
    overrides ``location_keywords`` to include "La Jolla".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.workable import DEFAULT_API_BASE, WorkableAdapter
from partner_scrape.fetch import DEFAULT_RATE_LIMIT_SECONDS
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "workable"

ACCOUNT = "fixture-regional-authority"
ACCOUNT_URL = f"{DEFAULT_API_BASE}/{ACCOUNT}?details=true"


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
    account: str = ACCOUNT,
    location_keywords: list[str] | None = None,
    acquisition_policy: dict | None = None,
) -> SourceConfig:
    config: dict = {"account": account}
    if location_keywords is not None:
        config["location_keywords"] = location_keywords
    return SourceConfig(
        source_id="fixture_authority",
        org_name="Fixture Regional Authority",
        adapter_type="workable",
        config=config,
        acquisition_policy=acquisition_policy or {},
    )


def _fetcher(fixture_name: str = "jobs.json") -> FixtureFetcher:
    return FixtureFetcher({ACCOUNT_URL: _response(_read_fixture(fixture_name))})


class TestDiscover:
    def test_discover_returns_exactly_one_ref_for_the_account_url(self):
        adapter = WorkableAdapter()

        refs = adapter.discover(_source(), FixtureFetcher({}))

        assert [r.url for r in refs] == [ACCOUNT_URL]

    def test_discover_honors_an_api_base_override(self):
        adapter = WorkableAdapter()
        source = SourceConfig(
            source_id="fixture_authority",
            org_name="Fixture Regional Authority",
            adapter_type="workable",
            config={"account": ACCOUNT, "api_base": "https://example.org/custom/accounts"},
        )

        refs = adapter.discover(source, FixtureFetcher({}))

        assert [r.url for r in refs] == [
            f"https://example.org/custom/accounts/{ACCOUNT}?details=true"
        ]

    def test_missing_account_raises(self):
        adapter = WorkableAdapter()
        source = SourceConfig(
            source_id="fixture_authority",
            org_name="Fixture Regional Authority",
            adapter_type="workable",
            config={},
        )

        try:
            adapter.discover(source, FixtureFetcher({}))
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError for missing account")


class TestFieldMapping:
    def test_matching_posting_maps_all_documented_fields(self):
        events = run(_source(), _fetcher())

        intern = next(
            e for e in events if e.title == "Software Engineering Summer Internship - Airport Operations"
        )
        assert intern.kind == "internship"
        assert intern.source_id == "fixture_authority"
        assert intern.external_id == "FIX0001"
        assert intern.start == datetime(2026, 4, 15, tzinfo=timezone.utc)
        assert intern.location == "San Diego, California"
        assert intern.registration_url == "https://apply.workable.com/j/FIX0001/apply"
        assert "9-week paid summer internship" in intern.description
        assert "&amp;" not in intern.description
        assert "&" in intern.description
        assert "<p>" not in intern.description

    def test_matching_posting_gets_classification_defaults_and_no_cost(self):
        events = run(_source(), _fetcher())

        intern = next(
            e for e in events if e.title == "Software Engineering Summer Internship - Airport Operations"
        )
        assert intern.age_grade_level == ["Grades 9-12", "Undergraduate"]
        assert intern.time_of_day == ["All Day"]
        assert intern.cost == ""
        assert intern.cost_range == ""
        assert "cost" not in intern.field_provenance
        assert "cost_range" not in intern.field_provenance

    def test_every_field_the_adapter_sets_has_workable_provenance_at_full_confidence(self):
        events = run(_source(), _fetcher())

        intern = next(
            e for e in events if e.title == "Software Engineering Summer Internship - Airport Operations"
        )
        assert intern.field_provenance
        for prov in intern.field_provenance.values():
            assert prov == Provenance(source="workable", confidence=1.0)


class TestFiltering:
    def test_only_the_internship_stem_san_diego_posting_survives_under_default_keywords(self):
        events = run(_source(), _fetcher())

        titles = {e.title for e in events}
        assert titles == {"Software Engineering Summer Internship - Airport Operations"}

    def test_non_internship_posting_is_dropped(self):
        events = run(_source(), _fetcher())
        assert "Airport Traffic Officer" not in {e.title for e in events}

    def test_non_local_posting_is_dropped(self):
        events = run(_source(), _fetcher())
        assert "Data Analytics Intern" not in {e.title for e in events}

    def test_non_stem_posting_is_dropped(self):
        events = run(_source(), _fetcher())
        assert "Marketing Coordinator Intern" not in {e.title for e in events}


class TestLocationKeywordsOverride:
    def test_override_widens_the_match_set_with_no_code_change(self):
        source = _source(location_keywords=["La Jolla", "San Diego"])

        events = run(source, _fetcher())

        titles = {e.title for e in events}
        assert titles == {
            "Software Engineering Summer Internship - Airport Operations",
            "Bioinformatics Intern",
        }

    def test_bioinformatics_intern_dropped_by_default_keywords(self):
        events = run(_source(), _fetcher())
        assert "Bioinformatics Intern" not in {e.title for e in events}


class TestAcquisitionPolicyThreading:
    def test_sources_acquisition_policy_reaches_fetcher_get(self):
        fetcher = _fetcher()
        source = _source(acquisition_policy={"rate_limit_seconds": 4.0, "respect_robots": False})

        run(source, fetcher)

        assert fetcher.policy_calls[ACCOUNT_URL] == (4.0, False)

    def test_source_with_no_acquisition_policy_still_gets_polite_fetcher_defaults(self):
        fetcher = _fetcher()

        run(_source(), fetcher)

        assert fetcher.policy_calls[ACCOUNT_URL] == (DEFAULT_RATE_LIMIT_SECONDS, True)


class TestMalformedRecordIsolation:
    def test_missing_title_record_is_skipped_rest_of_response_survives(self):
        events = run(_source(location_keywords=["La Jolla", "San Diego"]), _fetcher())

        # 6 records in the fixture: 1 missing title (skipped), 3 filtered
        # out by classify_posting, 2 kept under the widened keywords.
        assert len(events) == 2
        assert all(e.title for e in events)


class TestEmptyResponse:
    def test_empty_jobs_list_yields_zero_events_and_no_exception(self):
        events = run(_source(), _fetcher("jobs_empty.json"))
        assert events == []


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self):
        adapter = WorkableAdapter()
        raw = RawResponse(ref=EventRef(url=ACCOUNT_URL), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_events_without_raising(self):
        adapter = WorkableAdapter()
        raw = RawResponse(ref=EventRef(url=ACCOUNT_URL), status=200, body="not json {")

        assert list(adapter.extract(raw, _source())) == []

    def test_unexpected_json_shape_returns_no_events_without_raising(self):
        adapter = WorkableAdapter()
        raw = RawResponse(ref=EventRef(url=ACCOUNT_URL), status=200, body="[]")

        assert list(adapter.extract(raw, _source())) == []

"""Tests for partner_scrape.adapters.greenhouse: the Greenhouse ATS adapter.

Every test drives the adapter through a fixture Fetcher returning
recorded/synthesized Greenhouse board JSON (tests/fixtures/greenhouse/)
-- no test here opens a real network socket, per sprint.md's test
strategy for the Adapter Framework and this ticket's "ALL tests
offline" constraint.

``tests/fixtures/greenhouse/jobs.json`` mixes six postings so a single
fixture exercises every filtering axis at once:
  - "Software Engineering Intern" (San Diego, Engineering) -- keeps:
    internship + STEM + San Diego.
  - "Senior Software Engineer" (San Diego, Engineering) -- drops: not
    an internship/early-career title.
  - "Data Science Intern" (Austin) -- drops: not San Diego-local.
  - "Marketing Intern" (San Diego, Marketing) -- drops: not STEM.
  - a record with no ``title`` key -- malformed, must be skipped without
    aborting the rest of the response.
  - "Bioinformatics Intern" (La Jolla) -- drops under the default
    ``location_keywords`` (not "San Diego"), but is kept when a source
    overrides ``location_keywords`` to include "La Jolla".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.greenhouse import DEFAULT_API_BASE, GreenhouseAdapter
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "greenhouse"

BOARD_TOKEN = "fixtureco"
BOARD_URL = f"{DEFAULT_API_BASE}/{BOARD_TOKEN}/jobs?content=true"


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

    def get(self, url: str, headers: dict[str, str] | None = None) -> FetchResponse:
        self.calls.append(url)
        return self.responses[url]


def _source(board_token: str = BOARD_TOKEN, location_keywords: list[str] | None = None) -> SourceConfig:
    config: dict = {"board_token": board_token}
    if location_keywords is not None:
        config["location_keywords"] = location_keywords
    return SourceConfig(
        source_id="fixture_co",
        org_name="Fixture Co",
        adapter_type="greenhouse",
        config=config,
    )


def _fetcher(fixture_name: str = "jobs.json") -> FixtureFetcher:
    return FixtureFetcher({BOARD_URL: _response(_read_fixture(fixture_name))})


class TestDiscover:
    def test_discover_returns_exactly_one_ref_for_the_board_url(self):
        adapter = GreenhouseAdapter()

        refs = adapter.discover(_source(), FixtureFetcher({}))

        assert [r.url for r in refs] == [BOARD_URL]

    def test_discover_honors_an_api_base_override(self):
        adapter = GreenhouseAdapter()
        source = SourceConfig(
            source_id="fixture_co",
            org_name="Fixture Co",
            adapter_type="greenhouse",
            config={"board_token": BOARD_TOKEN, "api_base": "https://example.org/custom/boards"},
        )

        refs = adapter.discover(source, FixtureFetcher({}))

        assert [r.url for r in refs] == [
            f"https://example.org/custom/boards/{BOARD_TOKEN}/jobs?content=true"
        ]

    def test_missing_board_token_raises(self):
        adapter = GreenhouseAdapter()
        source = SourceConfig(
            source_id="fixture_co",
            org_name="Fixture Co",
            adapter_type="greenhouse",
            config={},
        )

        try:
            adapter.discover(source, FixtureFetcher({}))
        except KeyError:
            pass
        else:
            raise AssertionError("expected KeyError for missing board_token")


class TestFieldMapping:
    def test_matching_posting_maps_all_documented_fields(self):
        events = run(_source(), _fetcher())

        assert len(events) == 1
        intern = events[0]
        assert intern.title == "Software Engineering Intern"
        assert intern.kind == "internship"
        assert intern.source_id == "fixture_co"
        assert intern.external_id == "8632329001"
        assert intern.start == datetime.fromisoformat("2026-06-01T09:30:00-07:00")
        assert intern.location == "San Diego, California, United States"
        assert intern.registration_url == "https://boards.greenhouse.io/fixtureco/jobs/8632329001"
        assert "Join our engineering team for a summer internship" in intern.description
        assert "&amp;" not in intern.description
        assert "&" in intern.description
        assert "<p>" not in intern.description

    def test_matching_posting_gets_classification_defaults_and_no_cost(self):
        events = run(_source(), _fetcher())

        intern = events[0]
        assert intern.age_grade_level == ["Grades 9-12", "Undergraduate"]
        assert intern.time_of_day == ["All Day"]
        assert intern.cost == ""
        assert intern.cost_range == ""
        assert "cost" not in intern.field_provenance
        assert "cost_range" not in intern.field_provenance

    def test_every_field_the_adapter_sets_has_greenhouse_provenance_at_full_confidence(self):
        events = run(_source(), _fetcher())

        intern = events[0]
        assert intern.field_provenance
        for prov in intern.field_provenance.values():
            assert prov == Provenance(source="greenhouse", confidence=1.0)


class TestFiltering:
    def test_only_the_internship_stem_san_diego_posting_survives_under_default_keywords(self):
        events = run(_source(), _fetcher())

        titles = {e.title for e in events}
        assert titles == {"Software Engineering Intern"}

    def test_non_internship_posting_is_dropped(self):
        events = run(_source(), _fetcher())
        assert "Senior Software Engineer" not in {e.title for e in events}

    def test_non_local_posting_is_dropped(self):
        events = run(_source(), _fetcher())
        assert "Data Science Intern" not in {e.title for e in events}

    def test_non_stem_posting_is_dropped(self):
        events = run(_source(), _fetcher())
        assert "Marketing Intern" not in {e.title for e in events}


class TestLocationKeywordsOverride:
    def test_override_widens_the_match_set_with_no_code_change(self):
        source = _source(location_keywords=["La Jolla", "San Diego"])

        events = run(source, _fetcher())

        titles = {e.title for e in events}
        assert titles == {"Software Engineering Intern", "Bioinformatics Intern"}

    def test_bioinformatics_intern_dropped_by_default_keywords(self):
        events = run(_source(), _fetcher())
        assert "Bioinformatics Intern" not in {e.title for e in events}


class TestMalformedRecordIsolation:
    def test_missing_title_record_is_skipped_rest_of_response_survives(self):
        events = run(_source(location_keywords=["La Jolla", "San Diego"]), _fetcher())

        # 6 records in the fixture: 1 missing title (skipped), 4 filtered
        # out by classify_posting, 2 kept under the widened keywords.
        assert len(events) == 2
        assert all(e.title for e in events)


class TestEmptyResponse:
    def test_empty_jobs_list_yields_zero_events_and_no_exception(self):
        events = run(_source(), _fetcher("jobs_empty.json"))
        assert events == []


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self):
        adapter = GreenhouseAdapter()
        raw = RawResponse(ref=EventRef(url=BOARD_URL), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_events_without_raising(self):
        adapter = GreenhouseAdapter()
        raw = RawResponse(ref=EventRef(url=BOARD_URL), status=200, body="not json {")

        assert list(adapter.extract(raw, _source())) == []

    def test_unexpected_json_shape_returns_no_events_without_raising(self):
        adapter = GreenhouseAdapter()
        raw = RawResponse(ref=EventRef(url=BOARD_URL), status=200, body="[]")

        assert list(adapter.extract(raw, _source())) == []

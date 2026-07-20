"""Tests for partner_scrape.adapters.tec: the TEC REST adapter.

Every test drives the adapter through a fixture Fetcher returning
recorded/synthesized TEC API JSON (tests/fixtures/tec/) -- no test here
opens a real network socket, per sprint.md's test strategy for the
Adapter Framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.tec import PAGE_SIZE, TecRestAdapter
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "tec"

API_BASE = "https://example.org/wp-json/tribe/events/v1/events/"
PROBE_URL = f"{API_BASE}?per_page={PAGE_SIZE}&status=publish&start_date=now"
PAGE1_URL = f"{API_BASE}?per_page={PAGE_SIZE}&page=1&status=publish&start_date=now"
PAGE2_URL = f"{API_BASE}?per_page={PAGE_SIZE}&page=2&status=publish&start_date=now"


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


def _source(api_base: str = API_BASE) -> SourceConfig:
    return SourceConfig(
        source_id="fixture_org",
        org_name="Fixture Org",
        adapter_type="tec_rest",
        config={"api_base": api_base},
    )


def _two_page_fetcher() -> FixtureFetcher:
    page1_body = _read_fixture("events_page1.json")
    return FixtureFetcher(
        {
            # The probe (per_page=50) only needs a parseable total_pages --
            # reusing page1's body is fine, its total_pages value (2) is
            # what discover() actually reads.
            PROBE_URL: _response(page1_body),
            PAGE1_URL: _response(page1_body),
            PAGE2_URL: _response(_read_fixture("events_page2.json")),
        }
    )


class TestFieldMapping:
    def test_valid_event_maps_all_documented_fields(self):
        events = run(_source(), _two_page_fetcher())

        tide_pool = next(e for e in events if e.title == "Tide Pool Exploration")
        assert tide_pool.start == datetime(2026, 8, 15, 9, 0, 0)
        assert tide_pool.end == datetime(2026, 8, 15, 11, 0, 0)
        assert tide_pool.all_day is False
        assert tide_pool.location == "Cabrillo Tide Pools, 1800 Cabrillo Memorial Dr, San Diego, CA"
        assert tide_pool.cost == "$5"
        assert tide_pool.registration_url == "https://example.org/event/tide-pool-exploration/"
        assert tide_pool.image_url == "https://example.org/wp-content/uploads/tide-pool.jpg"
        assert tide_pool.categories == ["Marine Science", "Family"]
        assert tide_pool.tags == ["tide pools", "outdoor"]
        assert "Explore local tide pools" in tide_pool.description
        assert "<p>" not in tide_pool.description
        assert tide_pool.kind == "event"
        assert tide_pool.source_id == "fixture_org"
        assert tide_pool.external_id == "4501"

    def test_every_field_the_adapter_sets_has_tec_rest_provenance_at_full_confidence(self):
        events = run(_source(), _two_page_fetcher())

        tide_pool = next(e for e in events if e.title == "Tide Pool Exploration")
        assert tide_pool.field_provenance
        for prov in tide_pool.field_provenance.values():
            assert prov == Provenance(source="tec_rest", confidence=1.0)

    def test_all_day_event_with_sparse_fields_maps_defaults_cleanly(self):
        events = run(_source(), _two_page_fetcher())

        beach = next(e for e in events if e.title == "Beach Cleanup")
        assert beach.all_day is True
        assert beach.cost == "Free"
        assert beach.location == ""
        assert beach.categories == []
        assert beach.tags == []
        assert beach.image_url == ""
        assert "location" not in beach.field_provenance
        assert "description" not in beach.field_provenance


class TestPagination:
    def test_probe_and_both_pages_are_fetched_in_order_until_exhausted(self):
        fetcher = _two_page_fetcher()

        run(_source(), fetcher)

        assert fetcher.calls == [PROBE_URL, PAGE1_URL, PAGE2_URL]

    def test_single_page_when_total_pages_is_one(self):
        body = _read_fixture("events_empty.json")
        fetcher = FixtureFetcher({PROBE_URL: _response(body), PAGE1_URL: _response(body)})

        events = run(_source(), fetcher)

        assert events == []
        assert fetcher.calls == [PROBE_URL, PAGE1_URL]


class TestMalformedRecordIsolation:
    def test_missing_title_and_bad_date_records_are_skipped_rest_of_page_survives(self):
        events = run(_source(), _two_page_fetcher())

        titles = {e.title for e in events}
        assert titles == {"Tide Pool Exploration", "Beach Cleanup"}
        assert len(events) == 2


class TestEmptyResponse:
    def test_empty_events_list_yields_zero_events_and_no_exception(self):
        body = _read_fixture("events_empty.json")
        fetcher = FixtureFetcher({PROBE_URL: _response(body), PAGE1_URL: _response(body)})

        events = run(_source(), fetcher)

        assert events == []


class TestKindDefault:
    def test_kind_defaults_to_event_for_every_emitted_record(self):
        events = run(_source(), _two_page_fetcher())

        assert events  # sanity: fixtures did produce events
        assert all(e.kind == "event" for e in events)


class TestExtractRobustness:
    def test_non_200_page_status_returns_no_events_without_raising(self):
        adapter = TecRestAdapter()
        raw = RawResponse(ref=EventRef(url=PAGE1_URL), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_events_without_raising(self):
        adapter = TecRestAdapter()
        raw = RawResponse(ref=EventRef(url=PAGE1_URL), status=200, body="not json {")

        assert list(adapter.extract(raw, _source())) == []


class TestDiscoverProbeFailureHandling:
    def test_probe_non_200_status_degrades_to_a_single_page(self):
        fetcher = FixtureFetcher({PROBE_URL: _response("", status=500)})
        adapter = TecRestAdapter()

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == [PAGE1_URL]

    def test_probe_unparseable_json_degrades_to_a_single_page(self):
        fetcher = FixtureFetcher({PROBE_URL: _response("not json")})
        adapter = TecRestAdapter()

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == [PAGE1_URL]

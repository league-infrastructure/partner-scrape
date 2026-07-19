"""Tests for partner_scrape.adapters.localist: the UCSD Localist adapter.

Every test drives the adapter through a fixture Fetcher returning
recorded/synthesized Localist API JSON (tests/fixtures/localist/) -- no
test here opens a real network socket, per sprint.md's test strategy for
the Adapter Framework.

The critical case this module proves: Localist's API returns one row
per matching *day* for a recurring event, not one row per event
(sprint.md's Localist Adapter architecture, confirmed live during
sprint 003 planning) -- ``events_page1.json`` repeats one event's ``id``
across three rows (mirroring the live-captured "Shark Summer" shape) to
exercise the required id-based dedup-within-page step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.localist import DEFAULT_DAYS, DEFAULT_PP, LocalistAdapter
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "localist"

API_BASE = "https://calendar.example.edu/api/2/events"
GROUP_ID = "49845193640602"
PROBE_URL = f"{API_BASE}?group_id={GROUP_ID}&days={DEFAULT_DAYS}&pp=1&page=1"
PAGE1_URL = f"{API_BASE}?group_id={GROUP_ID}&days={DEFAULT_DAYS}&pp={DEFAULT_PP}&page=1"
PAGE2_URL = f"{API_BASE}?group_id={GROUP_ID}&days={DEFAULT_DAYS}&pp={DEFAULT_PP}&page=2"


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


def _source(**config_overrides) -> SourceConfig:
    config = {"api_base": API_BASE, "group_id": GROUP_ID, **config_overrides}
    return SourceConfig(
        source_id="fixture_org",
        org_name="Fixture Org",
        adapter_type="localist",
        config=config,
    )


def _two_page_fetcher() -> FixtureFetcher:
    page1_body = _read_fixture("events_page1.json")
    return FixtureFetcher(
        {
            # The probe (pp=1) only needs a parseable page.total -- reusing
            # page1's body is fine, its "page":{"total": 2} value is what
            # discover() actually reads.
            PROBE_URL: _response(page1_body),
            PAGE1_URL: _response(page1_body),
            PAGE2_URL: _response(_read_fixture("events_page2.json")),
        }
    )


class TestFieldMapping:
    def test_valid_event_maps_all_documented_fields(self):
        events = run(_source(), _two_page_fetcher())

        lab = next(e for e in events if e.title == "Tide Pool Discovery Lab")
        assert lab.start == datetime(2026, 8, 10, 0, 0, 0)
        assert lab.end == datetime(2026, 8, 10, 0, 0, 0)
        assert lab.location == "Birch Aquarium at Scripps, Tide Pool Plaza"
        assert lab.cost == "$5"
        assert lab.registration_url == "https://calendar.example.edu/event/tide_pool_lab"
        assert lab.image_url == "https://calendar.example.edu/photos/tide_pool_lab.jpg"
        assert lab.tags == ["tide pools"]
        assert lab.categories == ["marine science", "family"]
        assert lab.description == "Hands-on exploration of local tide pool ecosystems."
        assert lab.kind == "event"
        assert lab.source_id == "fixture_org"
        assert lab.external_id == "60000000000001"

    def test_url_with_trailing_space_is_stripped(self):
        events = run(_source(), _two_page_fetcher())

        shark = next(e for e in events if e.title == "Shark Summer")
        assert shark.registration_url == "https://calendar.example.edu/event/shark_summer"

    def test_every_field_the_adapter_sets_has_localist_provenance_at_full_confidence(self):
        events = run(_source(), _two_page_fetcher())

        lab = next(e for e in events if e.title == "Tide Pool Discovery Lab")
        assert lab.field_provenance
        for prov in lab.field_provenance.values():
            assert prov == Provenance(source="localist", confidence=1.0)

    def test_sparse_event_falls_back_to_urlname_and_leaves_optional_fields_unset(self):
        events = run(_source(), _two_page_fetcher())

        sparse = next(e for e in events if e.title == "Members Night")
        assert sparse.registration_url == "https://calendar.example.edu/event/members_night"
        assert sparse.location == ""
        assert sparse.cost == ""
        assert sparse.tags == []
        assert sparse.categories == []
        assert sparse.image_url == ""
        assert "location" not in sparse.field_provenance
        assert "description" not in sparse.field_provenance
        assert "cost" not in sparse.field_provenance


class TestRecurringEventDedup:
    """The critical case: a recurring event repeated as multiple day-rows."""

    def test_same_id_repeated_across_daily_rows_yields_exactly_one_event(self):
        events = run(_source(), _two_page_fetcher())

        shark_summer_events = [e for e in events if e.external_id == "52950294007943"]
        assert len(shark_summer_events) == 1
        assert shark_summer_events[0].title == "Shark Summer"

    def test_dedup_happens_within_extract_of_a_single_page(self):
        # Direct extract() call over one page's raw response, isolated
        # from discover()/pagination -- proves the dedup step lives in
        # extract() itself, matching sprint.md's "within one fetched
        # page" scope (not a hardcoded global check).
        adapter = LocalistAdapter()
        raw = RawResponse(
            ref=EventRef(url=PAGE1_URL), status=200, body=_read_fixture("events_page1.json")
        )

        events = list(adapter.extract(raw, _source()))

        assert sum(1 for e in events if e.external_id == "52950294007943") == 1

    def test_total_unique_events_across_both_pages(self):
        events = run(_source(), _two_page_fetcher())

        titles = sorted(e.title for e in events)
        assert titles == [
            "Members Night",
            "Ocean Explorers Camp",
            "Shark Summer",
            "Tide Pool Discovery Lab",
        ]


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

    def test_custom_days_and_pp_config_change_the_query_url(self):
        custom_source = _source(days=30, pp=10)
        probe_url = f"{API_BASE}?group_id={GROUP_ID}&days=30&pp=1&page=1"
        page1_url = f"{API_BASE}?group_id={GROUP_ID}&days=30&pp=10&page=1"
        body = _read_fixture("events_empty.json")
        fetcher = FixtureFetcher({probe_url: _response(body), page1_url: _response(body)})

        events = run(custom_source, fetcher)

        assert events == []
        assert fetcher.calls == [probe_url, page1_url]


class TestMalformedRecordIsolation:
    def test_missing_title_record_is_skipped_rest_of_page_survives(self):
        events = run(_source(), _two_page_fetcher())

        titles = {e.title for e in events}
        assert "" not in titles
        assert {"Shark Summer", "Tide Pool Discovery Lab", "Members Night"} <= titles


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
        adapter = LocalistAdapter()
        raw = RawResponse(ref=EventRef(url=PAGE1_URL), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []

    def test_unparseable_json_body_returns_no_events_without_raising(self):
        adapter = LocalistAdapter()
        raw = RawResponse(ref=EventRef(url=PAGE1_URL), status=200, body="not json {")

        assert list(adapter.extract(raw, _source())) == []

    def test_unexpected_json_shape_returns_no_events_without_raising(self):
        adapter = LocalistAdapter()
        raw = RawResponse(ref=EventRef(url=PAGE1_URL), status=200, body="[]")

        assert list(adapter.extract(raw, _source())) == []

    def test_event_wrapper_missing_or_null_is_skipped_without_raising(self):
        adapter = LocalistAdapter()
        raw = RawResponse(
            ref=EventRef(url=PAGE1_URL),
            status=200,
            body='{"page": {"current": 1, "total": 1}, "events": [{"event": null}, {}]}',
        )

        assert list(adapter.extract(raw, _source())) == []


class TestDiscoverProbeFailureHandling:
    def test_probe_non_200_status_degrades_to_a_single_page(self):
        fetcher = FixtureFetcher({PROBE_URL: _response("", status=500)})
        adapter = LocalistAdapter()

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == [PAGE1_URL]

    def test_probe_unparseable_json_degrades_to_a_single_page(self):
        fetcher = FixtureFetcher({PROBE_URL: _response("not json")})
        adapter = LocalistAdapter()

        refs = adapter.discover(_source(), fetcher)

        assert [r.url for r in refs] == [PAGE1_URL]

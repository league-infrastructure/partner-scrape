"""Tests for partner_scrape.adapters.ical: the iCal/RSS adapter.

Every test drives the adapter through a fixture Fetcher returning
recorded/synthesized ``.ics`` bodies (tests/fixtures/ical/) -- no test
here opens a real network socket, per sprint.md's test strategy for the
Adapter Framework.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from partner_scrape.adapters import run
from partner_scrape.adapters.base import EventRef, RawResponse
from partner_scrape.adapters.ical import (
    MAX_RRULE_INSTANCES,
    MAX_RRULE_WINDOW_DAYS,
    ICalAdapter,
    _expand_rrule,
)
from partner_scrape.fetch.fetcher import FetchResponse
from partner_scrape.model import Provenance
from partner_scrape.registry.schema import SourceConfig

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "ical"

FEED_URL = "https://example.org/events/?ical=1"


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


def _source() -> SourceConfig:
    return SourceConfig(
        source_id="fixture_org",
        org_name="Fixture Org",
        adapter_type="ical",
        config={"feed_url": FEED_URL},
    )


def _feed_fetcher(body: str) -> FixtureFetcher:
    return FixtureFetcher({FEED_URL: _response(body)})


class TestFieldMapping:
    def test_non_recurring_vevent_maps_all_documented_fields(self):
        events = run(_source(), _feed_fetcher(_read_fixture("simple.ics")))

        tide_pool = next(e for e in events if e.title == "Tide Pool Exploration")
        assert tide_pool.start == datetime(2026, 8, 15, 9, 0, 0)
        assert tide_pool.end == datetime(2026, 8, 15, 11, 0, 0)
        assert tide_pool.all_day is False
        assert tide_pool.location == "Cabrillo Tide Pools, San Diego, CA"
        assert "naturalist guide" in tide_pool.description
        assert tide_pool.kind == "event"
        assert tide_pool.source_id == "fixture_org"
        assert tide_pool.external_id == "evt-tide-pool@example.org"

    def test_every_field_the_adapter_sets_has_ical_provenance_at_full_confidence(self):
        events = run(_source(), _feed_fetcher(_read_fixture("simple.ics")))

        tide_pool = next(e for e in events if e.title == "Tide Pool Exploration")
        assert tide_pool.field_provenance
        for prov in tide_pool.field_provenance.values():
            assert prov == Provenance(source="ical", confidence=1.0)


class TestRecurringExpansion:
    def test_bounded_rrule_count_5_yields_five_events(self):
        events = run(_source(), _feed_fetcher(_read_fixture("simple.ics")))

        story_times = [e for e in events if e.title == "Weekly Story Time"]
        assert len(story_times) == 5

    def test_recurring_occurrences_have_distinct_weekly_start_times(self):
        events = run(_source(), _feed_fetcher(_read_fixture("simple.ics")))

        story_times = sorted(
            (e for e in events if e.title == "Weekly Story Time"), key=lambda e: e.start
        )
        starts = [e.start for e in story_times]
        assert starts == [datetime(2026, 8, 3, 10, 0, 0) + timedelta(weeks=i) for i in range(5)]
        # Each occurrence preserves the master VEVENT's 30-minute duration.
        assert all(e.end == e.start + timedelta(minutes=30) for e in story_times)

    def test_recurring_occurrences_get_distinct_external_ids(self):
        events = run(_source(), _feed_fetcher(_read_fixture("simple.ics")))

        story_times = [e for e in events if e.title == "Weekly Story Time"]
        external_ids = {e.external_id for e in story_times}
        assert len(external_ids) == 5

    def test_unbounded_rrule_is_capped_at_max_instances(self):
        events = run(_source(), _feed_fetcher(_read_fixture("unbounded_rrule.ics")))

        assert len(events) == MAX_RRULE_INSTANCES
        assert all(e.title == "Daily Drop-In Hours" for e in events)

    def test_unbounded_rrule_occurrences_never_exceed_the_180_day_window(self):
        events = run(_source(), _feed_fetcher(_read_fixture("unbounded_rrule.ics")))

        starts = sorted(e.start for e in events)
        horizon = starts[0] + timedelta(days=MAX_RRULE_WINDOW_DAYS)
        assert all(start <= horizon for start in starts)

    def test_expand_rrule_stops_at_the_180_day_window_before_52_instances(self):
        # A weekly-forever rule: 52 weekly instances would span 357 days,
        # well past the 180-day window -- the day bound must trigger
        # first, capping well under MAX_RRULE_INSTANCES.
        dtstart = datetime(2026, 1, 1, 9, 0, 0)
        occurrences = _expand_rrule(dtstart, "FREQ=WEEKLY")

        assert len(occurrences) < MAX_RRULE_INSTANCES
        assert occurrences[-1] <= dtstart + timedelta(days=MAX_RRULE_WINDOW_DAYS)

    def test_expand_rrule_stops_at_52_instances_before_the_180_day_window(self):
        # A daily-forever rule: 52 daily instances span only 51 days,
        # well inside the 180-day window -- the instance bound must
        # trigger first.
        dtstart = datetime(2026, 1, 1, 9, 0, 0)
        occurrences = _expand_rrule(dtstart, "FREQ=DAILY")

        assert len(occurrences) == MAX_RRULE_INSTANCES


class TestMalformedRecordIsolation:
    def test_vevent_with_no_summary_is_skipped_rest_of_feed_survives(self):
        events = run(_source(), _feed_fetcher(_read_fixture("simple.ics")))

        titles = {e.title for e in events}
        assert titles == {"Tide Pool Exploration", "Weekly Story Time"}


class TestMalformedAndEmptyFeed:
    def test_unparseable_ics_yields_zero_events_and_a_logged_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            events = run(_source(), _feed_fetcher("this is not a calendar at all"))

        assert events == []
        assert "unparseable" in caplog.text

    def test_empty_body_yields_zero_events_and_a_logged_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            events = run(_source(), _feed_fetcher(""))

        assert events == []
        assert "empty" in caplog.text

    def test_calendar_with_no_vevents_yields_zero_events_without_raising(self):
        empty_calendar = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Fixture//EN\r\nEND:VCALENDAR\r\n"
        )

        events = run(_source(), _feed_fetcher(empty_calendar))

        assert events == []


class TestExtractRobustness:
    def test_non_200_status_returns_no_events_without_raising(self):
        adapter = ICalAdapter()
        raw = RawResponse(ref=EventRef(url=FEED_URL), status=500, body="")

        assert list(adapter.extract(raw, _source())) == []


class TestIcalIsRegistered:
    def test_importing_the_adapters_package_registers_ical(self):
        import partner_scrape.adapters as adapters_pkg

        assert adapters_pkg.ADAPTERS["ical"] is adapters_pkg.ICalAdapter

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
from partner_scrape.fetch import DEFAULT_RATE_LIMIT_SECONDS
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
    #: Every call's rate_limit_seconds/respect_robots, keyed by URL --
    #: sprint 015 ticket 003's acquisition_kwargs() threading, recorded
    #: separately from ``calls`` so existing ``calls == [...]``-style
    #: assertions elsewhere in this file are unaffected.
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


def _source(acquisition_policy: dict | None = None) -> SourceConfig:
    return SourceConfig(
        source_id="fixture_org",
        org_name="Fixture Org",
        adapter_type="ical",
        config={"feed_url": FEED_URL},
        acquisition_policy=acquisition_policy or {},
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


class TestAcquisitionPolicyThreading:
    def test_sources_acquisition_policy_reaches_fetcher_get(self):
        fetcher = _feed_fetcher(_read_fixture("simple.ics"))
        source = _source(acquisition_policy={"rate_limit_seconds": 0.5, "respect_robots": False})

        run(source, fetcher)

        assert fetcher.policy_calls[FEED_URL] == (0.5, False)

    def test_source_with_no_acquisition_policy_still_gets_polite_fetcher_defaults(self):
        fetcher = _feed_fetcher(_read_fixture("simple.ics"))

        run(_source(), fetcher)

        assert fetcher.policy_calls[FEED_URL] == (DEFAULT_RATE_LIMIT_SECONDS, True)


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


class TestTockifyTTLTolerance:
    """(Sprint 016 ticket 001) county-parks (Tockify) emits
    ``X-PUBLISHED-TTL:P15M`` at the calendar level -- a non-standard
    duration value ``icalendar``'s strict parser can reject. The fixture
    body below is built from the real value sprint 015 ticket 005 measured
    live against ``county-parks``.
    """

    def test_ttl_body_parses_and_yields_fixture_vevents(self):
        events = run(_source(), _feed_fetcher(_read_fixture("tockify_ttl.ics")))

        titles = {e.title for e in events}
        assert titles == {"Ranger Talk: Tide Pool Ecology", "Guided Trail Hike"}

        ranger_talk = next(e for e in events if e.title == "Ranger Talk: Tide Pool Ecology")
        assert ranger_talk.start == datetime(2026, 8, 15, 9, 0, 0)
        assert ranger_talk.location == "Cabrillo National Monument, San Diego, CA"

    def test_feed_without_ttl_property_is_unaffected(self):
        # simple.ics carries no X-PUBLISHED-TTL property at all -- the
        # pre-parse strip must be a no-op for every other already-
        # registered ical source, not just "doesn't crash." Matches
        # TestFieldMapping's own field assertions exactly.
        events = run(_source(), _feed_fetcher(_read_fixture("simple.ics")))

        tide_pool = next(e for e in events if e.title == "Tide Pool Exploration")
        assert tide_pool.start == datetime(2026, 8, 15, 9, 0, 0)
        assert tide_pool.location == "Cabrillo Tide Pools, San Diego, CA"


class TestMultiRruleSalvage:
    """(Sprint 016 ticket 001) sd-astronomy-association (Google Calendar)
    has at least one VEVENT with more than one RRULE property; icalendar
    returns a Python ``list`` for ``component.get("rrule")`` in that case.
    The fixture VEVENT below carries two structurally different RRULEs
    (``FREQ=WEEKLY;COUNT=3`` then ``FREQ=DAILY;COUNT=10``) so a wrong
    salvage choice (second rule, or both merged) is distinguishable from
    the correct one (first rule only, three weekly occurrences).
    """

    def test_multi_rrule_vevent_salvages_via_first_rule_others_unaffected(self, caplog):
        with caplog.at_level(logging.WARNING):
            events = run(_source(), _feed_fetcher(_read_fixture("multi_rrule.ics")))

        star_party = sorted(
            (e for e in events if e.title == "Star Party at Tierra del Sol"),
            key=lambda e: e.start,
        )
        assert len(star_party) == 3
        assert [e.start for e in star_party] == [
            datetime(2026, 8, 1, 19, 0, 0) + timedelta(weeks=i) for i in range(3)
        ]

        # The feed's other, well-formed VEVENTs are unaffected by the
        # multi-RRULE VEVENT's salvage.
        other_titles = {e.title for e in events if e.title != "Star Party at Tierra del Sol"}
        assert other_titles == {"Monthly Member Meeting", "Solar Viewing"}

        assert "has 2 RRULE properties" in caplog.text
        assert "discarding 1" in caplog.text


class TestTtlAndMultiRruleRegression:
    def test_combined_pre_fix_crash_inputs_no_longer_abort_extract(self):
        """Regression: sprint 015 ticket 005 live-measured both crash
        inputs on real feeds -- county-parks' ``X-PUBLISHED-TTL:P15M``
        (``InvalidCalendar`` before any VEVENT was read) and
        sd-astronomy-association's multi-RRULE VEVENT (``AttributeError``
        aborting ``extract()`` mid-loop). This fixture combines both
        triggers with a normal VEVENT in one feed and proves neither
        aborts ``extract()`` -- every VEVENT yields.
        """
        events = run(
            _source(), _feed_fetcher(_read_fixture("ttl_and_multi_rrule_regression.ics"))
        )

        titles = {e.title for e in events}
        assert "Ranger Talk: Tide Pool Ecology" in titles
        assert "Guided Trail Hike" in titles
        assert "Star Party at Tierra del Sol" in titles

        star_party = [e for e in events if e.title == "Star Party at Tierra del Sol"]
        assert len(star_party) == 3  # salvaged via the first RRULE, not dropped


class TestWidenedExceptionIsolation:
    def test_extract_isolates_an_exception_type_outside_the_original_tuple(
        self, caplog, monkeypatch
    ):
        """Regression: before this ticket, ``extract()``'s per-VEVENT catch
        was ``(ValueError, TypeError, KeyError)`` -- narrower than this
        module's own top-level ``except Exception`` around
        ``Calendar.from_ical()``. A multi-RRULE VEVENT's ``AttributeError``
        (``'list' object has no attribute 'to_ical'``) escaped that tuple
        and aborted the whole source instead of being skipped (sprint 015
        ticket 005's live measurement against sd-astronomy-association).
        This proves the now-widened catch isolates an exception type
        outside the original tuple, using the exact ``AttributeError``
        message that issue measured -- independent of the RRULE-salvage
        fix itself, which now prevents that particular AttributeError from
        ever reaching this catch in production.
        """
        adapter = ICalAdapter()
        original_extract_component = adapter._extract_component
        calls = {"n": 0}

        def poisoned(component, source):
            calls["n"] += 1
            if calls["n"] == 1:
                raise AttributeError("'list' object has no attribute 'to_ical'")
            return original_extract_component(component, source)

        monkeypatch.setattr(adapter, "_extract_component", poisoned)

        raw = RawResponse(ref=EventRef(url=FEED_URL), status=200, body=_read_fixture("simple.ics"))
        with caplog.at_level(logging.WARNING):
            events = list(adapter.extract(raw, _source()))

        # simple.ics has 3 VEVENTs, processed in file order: Tide Pool
        # Exploration (poisoned -- raises AttributeError, skipped), Weekly
        # Story Time (real _extract_component, RRULE-expands to 5), and
        # the no-SUMMARY VEVENT (real _extract_component, raises its own
        # ValueError, also skipped). The AttributeError from the first
        # VEVENT does not abort the loop -- the second VEVENT's real
        # occurrences still yield.
        assert calls["n"] == 3
        titles = {e.title for e in events}
        assert titles == {"Weekly Story Time"}
        assert "Skipping malformed VEVENT" in caplog.text
        assert "to_ical" in caplog.text

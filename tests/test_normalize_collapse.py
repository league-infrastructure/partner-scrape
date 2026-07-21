"""Tests for partner_scrape.normalize.collapse: recurring-instance collapse.

Hand-built Event fixtures per the ticket's Approach ("test each function
against hand-built Event/Opportunity fixtures rather than only through
the full pipeline") -- no adapters, no network.
"""

from __future__ import annotations

from datetime import date, datetime

from partner_scrape.model import Event
from partner_scrape.normalize.collapse import collapse_recurring, recurring_key

# An arbitrary date well before every event in this file, so `today` makes
# all occurrences 'upcoming' -> next-occurrence == first == the pre-fix span.
_BEFORE_ALL = date(2020, 1, 1)


def _event(
    source_id: str = "tlc",
    title: str = "Beach Cleanup",
    start: datetime | None = None,
    end: datetime | None = None,
    confidence: float = 1.0,
    description: str = "",
) -> Event:
    event = Event(source_id=source_id)
    event.set("title", title, source="fixture", confidence=confidence)
    if start is not None:
        event.set("start", start, source="fixture", confidence=confidence)
    if end is not None:
        event.set("end", end, source="fixture", confidence=confidence)
    if description:
        event.set("description", description, source="fixture", confidence=confidence)
    return event


class TestRecurringKey:
    def test_key_is_source_id_and_normalized_title(self):
        event = _event(source_id="tlc", title="Beach Cleanup!!")
        assert recurring_key(event) == ("tlc", "beach cleanup")


class TestNonRecurring:
    def test_single_event_produces_one_instance_with_repeat_count_one(self):
        event = _event(start=datetime(2026, 8, 1, 9, 0))

        instances = collapse_recurring([event], _BEFORE_ALL)

        assert len(instances) == 1
        assert instances[0].repeat_count == 1
        assert instances[0].sources == frozenset({"tlc"})
        assert instances[0].last_seen == datetime(2026, 8, 1).date()

    def test_single_event_fields_are_preserved(self):
        event = _event(start=datetime(2026, 8, 1, 9, 0), description="Pick up trash on the beach")

        instances = collapse_recurring([event], _BEFORE_ALL)

        assert instances[0].event.title == "Beach Cleanup"
        assert instances[0].event.description == "Pick up trash on the beach"
        assert instances[0].event.start == datetime(2026, 8, 1, 9, 0)


class TestRecurringCollapse:
    def test_same_source_and_title_collapses_to_one_instance(self):
        events = [
            _event(start=datetime(2026, 8, 1, 9, 0)),
            _event(start=datetime(2026, 9, 1, 9, 0)),
            _event(start=datetime(2026, 10, 1, 9, 0)),
        ]

        instances = collapse_recurring(events, _BEFORE_ALL)

        assert len(instances) == 1
        assert instances[0].repeat_count == 3

    def test_span_covers_first_to_last_date(self):
        events = [
            _event(start=datetime(2026, 10, 1, 9, 0)),
            _event(start=datetime(2026, 8, 1, 9, 0)),
            _event(start=datetime(2026, 9, 1, 9, 0)),
        ]

        instances = collapse_recurring(events, _BEFORE_ALL)

        assert instances[0].event.start == datetime(2026, 8, 1, 9, 0)
        assert instances[0].event.end == datetime(2026, 10, 1, 9, 0)
        assert instances[0].last_seen == datetime(2026, 10, 1).date()

    def test_most_complete_instance_is_the_representative(self):
        sparse = _event(start=datetime(2026, 8, 1, 9, 0), confidence=1.0)
        rich = _event(
            start=datetime(2026, 9, 1, 9, 0),
            description="A full description of the recurring event",
            confidence=1.0,
        )

        instances = collapse_recurring([sparse, rich], _BEFORE_ALL)

        assert instances[0].event.description == "A full description of the recurring event"

    def test_higher_confidence_instance_wins_over_more_complete_lower_confidence_one(self):
        low_confidence_but_longer = _event(
            start=datetime(2026, 8, 1, 9, 0),
            description="A much longer description of this event, quite detailed",
            confidence=0.3,
        )
        high_confidence = _event(
            start=datetime(2026, 9, 1, 9, 0), description="Short", confidence=1.0
        )

        instances = collapse_recurring([low_confidence_but_longer, high_confidence], _BEFORE_ALL)

        assert instances[0].event.description == "Short"


class TestNoFalseMerges:
    def test_different_titles_are_not_collapsed(self):
        events = [
            _event(title="Beach Cleanup", start=datetime(2026, 8, 1, 9, 0)),
            _event(title="Tide Pool Walk", start=datetime(2026, 8, 1, 9, 0)),
        ]

        instances = collapse_recurring(events, _BEFORE_ALL)

        assert len(instances) == 2
        assert all(inst.repeat_count == 1 for inst in instances)

    def test_different_source_ids_with_the_same_title_are_not_collapsed_at_this_stage(self):
        events = [
            _event(source_id="tlc", title="Beach Cleanup", start=datetime(2026, 8, 1, 9, 0)),
            _event(source_id="crf", title="Beach Cleanup", start=datetime(2026, 8, 1, 9, 0)),
        ]

        instances = collapse_recurring(events, _BEFORE_ALL)

        assert len(instances) == 2
        assert {inst.event.source_id for inst in instances} == {"tlc", "crf"}


class TestNextUpcomingOccurrence:
    """Issue 005: a collapsed recurring/ongoing record shows its NEXT
    upcoming date, never a stale past first-ever occurrence."""

    TODAY = date(2026, 7, 20)

    def test_recurring_start_is_next_upcoming_not_first_ever(self):
        # A weekly series that started in the past and continues into the future.
        events = [
            _event(start=datetime(2026, 2, 7, 10, 0), end=datetime(2026, 2, 7, 11, 0)),
            _event(start=datetime(2026, 7, 25, 10, 0), end=datetime(2026, 7, 25, 11, 0)),
            _event(start=datetime(2026, 8, 22, 10, 0), end=datetime(2026, 8, 22, 11, 0)),
        ]
        [inst] = collapse_recurring(events, self.TODAY)
        # start = next occurrence >= today (Jul 25), NOT the first-ever (Feb 7)
        assert inst.event.start == datetime(2026, 7, 25, 10, 0)
        assert inst.event.start.date() >= self.TODAY
        # end still spans to the last occurrence
        assert inst.event.end == datetime(2026, 8, 22, 11, 0)

    def test_single_ongoing_event_with_past_start_future_end_clamps_to_today(self):
        # An exhibit running past->future with no discrete upcoming occurrence.
        ongoing = _event(start=datetime(2026, 6, 1, 9, 0), end=datetime(2026, 8, 31, 17, 0))
        [inst] = collapse_recurring([ongoing], self.TODAY)
        assert inst.event.start.date() == self.TODAY  # "available now", not Jun 1

    def test_future_only_series_is_unchanged(self):
        events = [
            _event(start=datetime(2026, 9, 1, 10, 0)),
            _event(start=datetime(2026, 9, 8, 10, 0)),
        ]
        [inst] = collapse_recurring(events, self.TODAY)
        assert inst.event.start == datetime(2026, 9, 1, 10, 0)  # earliest upcoming

    def test_genuinely_past_event_keeps_earliest_start(self):
        # No future occurrence, no future end -> unchanged; the export's
        # current+upcoming filter drops it downstream.
        past = _event(start=datetime(2026, 5, 1, 10, 0), end=datetime(2026, 5, 1, 11, 0))
        [inst] = collapse_recurring([past], self.TODAY)
        assert inst.event.start == datetime(2026, 5, 1, 10, 0)

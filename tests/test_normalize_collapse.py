"""Tests for partner_scrape.normalize.collapse: recurring-instance collapse.

Hand-built Event fixtures per the ticket's Approach ("test each function
against hand-built Event/Opportunity fixtures rather than only through
the full pipeline") -- no adapters, no network.
"""

from __future__ import annotations

from datetime import datetime

from partner_scrape.model import Event
from partner_scrape.normalize.collapse import collapse_recurring, recurring_key


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

        instances = collapse_recurring([event])

        assert len(instances) == 1
        assert instances[0].repeat_count == 1
        assert instances[0].sources == frozenset({"tlc"})
        assert instances[0].last_seen == datetime(2026, 8, 1).date()

    def test_single_event_fields_are_preserved(self):
        event = _event(start=datetime(2026, 8, 1, 9, 0), description="Pick up trash on the beach")

        instances = collapse_recurring([event])

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

        instances = collapse_recurring(events)

        assert len(instances) == 1
        assert instances[0].repeat_count == 3

    def test_span_covers_first_to_last_date(self):
        events = [
            _event(start=datetime(2026, 10, 1, 9, 0)),
            _event(start=datetime(2026, 8, 1, 9, 0)),
            _event(start=datetime(2026, 9, 1, 9, 0)),
        ]

        instances = collapse_recurring(events)

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

        instances = collapse_recurring([sparse, rich])

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

        instances = collapse_recurring([low_confidence_but_longer, high_confidence])

        assert instances[0].event.description == "Short"


class TestNoFalseMerges:
    def test_different_titles_are_not_collapsed(self):
        events = [
            _event(title="Beach Cleanup", start=datetime(2026, 8, 1, 9, 0)),
            _event(title="Tide Pool Walk", start=datetime(2026, 8, 1, 9, 0)),
        ]

        instances = collapse_recurring(events)

        assert len(instances) == 2
        assert all(inst.repeat_count == 1 for inst in instances)

    def test_different_source_ids_with_the_same_title_are_not_collapsed_at_this_stage(self):
        events = [
            _event(source_id="tlc", title="Beach Cleanup", start=datetime(2026, 8, 1, 9, 0)),
            _event(source_id="crf", title="Beach Cleanup", start=datetime(2026, 8, 1, 9, 0)),
        ]

        instances = collapse_recurring(events)

        assert len(instances) == 2
        assert {inst.event.source_id for inst in instances} == {"tlc", "crf"}

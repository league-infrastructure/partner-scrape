"""Tests for partner_scrape.normalize.dedup: cross-source identity + merge.

Hand-built Event/Instance fixtures per the ticket's Approach -- no
adapters, no network. Cross-source dedup groups across `source_id`
(unlike collapse.py's recurring grouping, which is per-source) -- see
dedup.py's module docstring.
"""

from __future__ import annotations

from datetime import datetime

from partner_scrape.model import Event
from partner_scrape.normalize.dedup import (
    cross_source_identity,
    dedup_cross_source,
    pick_best,
    score_event,
)
from partner_scrape.normalize.instance import Instance


def _event(
    source_id: str = "tlc",
    title: str = "Beach Cleanup",
    start: datetime | None = None,
    location: str = "",
    confidence: float = 1.0,
    description: str = "",
) -> Event:
    event = Event(source_id=source_id)
    event.set("title", title, source="fixture", confidence=confidence)
    if start is not None:
        event.set("start", start, source="fixture", confidence=confidence)
    if location:
        event.set("location", location, source="fixture", confidence=confidence)
    if description:
        event.set("description", description, source="fixture", confidence=confidence)
    return event


def _instance(event: Event) -> Instance:
    return Instance(event=event, sources=frozenset({event.source_id}))


class TestCrossSourceIdentity:
    def test_identity_is_normalized_title_date_and_venue(self):
        event = _event(
            title="Beach Cleanup!!",
            start=datetime(2026, 8, 1, 9, 0),
            location="Ocean Beach, San Diego",
        )
        assert cross_source_identity(event) == (
            "beach cleanup",
            datetime(2026, 8, 1).date(),
            "ocean beach san diego",
        )

    def test_no_start_uses_none_for_date_component(self):
        event = _event(title="Beach Cleanup")
        assert cross_source_identity(event)[1] is None


class TestScoreEvent:
    def test_higher_average_confidence_scores_higher(self):
        low = _event(confidence=0.3)
        high = _event(confidence=0.9)
        assert score_event(high) > score_event(low)

    def test_more_populated_fields_breaks_a_confidence_tie(self):
        sparse = _event(confidence=1.0)
        rich = _event(confidence=1.0, description="Full description", location="Somewhere")
        assert score_event(rich) > score_event(sparse)

    def test_confidence_outranks_completeness(self):
        low_confidence_rich = _event(
            confidence=0.2, description="A very long and complete description", location="Somewhere"
        )
        high_confidence_sparse = _event(confidence=1.0)
        assert score_event(high_confidence_sparse) > score_event(low_confidence_rich)


class TestPickBest:
    def test_returns_the_highest_scoring_event(self):
        low = _event(title="Low", confidence=0.2)
        high = _event(title="High", confidence=1.0)
        assert pick_best([low, high]).title == "High"


class TestDedupCrossSource:
    def test_matching_title_date_venue_across_sources_merges_to_one_instance(self):
        a = _instance(
            _event(
                source_id="tec_source",
                title="Tide Pool Exploration",
                start=datetime(2026, 8, 15, 9, 0),
                location="Cabrillo Tide Pools",
                confidence=1.0,
            )
        )
        b = _instance(
            _event(
                source_id="wp_source",
                title="tide pool exploration!!",
                start=datetime(2026, 8, 15, 9, 0),
                location="Cabrillo Tide Pools",
                confidence=0.5,
            )
        )

        merged = dedup_cross_source([a, b])

        assert len(merged) == 1

    def test_higher_confidence_field_values_are_retained(self):
        a = _instance(
            _event(
                source_id="tec_source",
                title="Tide Pool Exploration",
                start=datetime(2026, 8, 15, 9, 0),
                location="Cabrillo Tide Pools",
                confidence=1.0,
                description="Full accurate description from TEC",
            )
        )
        b = _instance(
            _event(
                source_id="wp_source",
                title="Tide Pool Exploration",
                start=datetime(2026, 8, 15, 9, 0),
                location="Cabrillo Tide Pools",
                confidence=0.5,
                description="Vague WP blurb",
            )
        )

        merged = dedup_cross_source([a, b])

        assert merged[0].event.description == "Full accurate description from TEC"
        assert merged[0].event.source_id == "tec_source"

    def test_contributing_source_set_is_recorded_not_dropped(self):
        a = _instance(
            _event(
                source_id="tec_source",
                start=datetime(2026, 8, 15, 9, 0),
                location="Cabrillo Tide Pools",
            )
        )
        b = _instance(
            _event(
                source_id="wp_source",
                start=datetime(2026, 8, 15, 9, 0),
                location="Cabrillo Tide Pools",
            )
        )

        merged = dedup_cross_source([a, b])

        assert merged[0].sources == frozenset({"tec_source", "wp_source"})

    def test_different_dates_are_not_collapsed(self):
        a = _instance(
            _event(
                source_id="tec_source",
                start=datetime(2026, 8, 15, 9, 0),
                location="Cabrillo Tide Pools",
            )
        )
        b = _instance(
            _event(
                source_id="wp_source",
                start=datetime(2026, 8, 16, 9, 0),
                location="Cabrillo Tide Pools",
            )
        )

        merged = dedup_cross_source([a, b])

        assert len(merged) == 2

    def test_different_venues_are_not_collapsed(self):
        a = _instance(
            _event(
                source_id="tec_source",
                start=datetime(2026, 8, 15, 9, 0),
                location="Cabrillo Tide Pools",
            )
        )
        b = _instance(
            _event(
                source_id="wp_source",
                start=datetime(2026, 8, 15, 9, 0),
                location="Balboa Park",
            )
        )

        merged = dedup_cross_source([a, b])

        assert len(merged) == 2

    def test_same_title_only_no_date_or_venue_match_is_not_collapsed(self):
        a = _instance(_event(source_id="tec_source", title="Family STEM Night"))
        b = _instance(
            _event(
                source_id="wp_source",
                title="Family STEM Night",
                start=datetime(2026, 8, 15, 9, 0),
                location="Balboa Park",
            )
        )

        merged = dedup_cross_source([a, b])

        assert len(merged) == 2

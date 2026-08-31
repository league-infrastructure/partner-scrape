"""Tests for partner_scrape.normalize.dedup: cross-source identity + merge.

Hand-built Event/Instance fixtures per the ticket's Approach -- no
adapters, no network. Cross-source dedup groups across `source_id`
(unlike collapse.py's recurring grouping, which is per-source) -- see
dedup.py's module docstring.
"""

from __future__ import annotations

from datetime import datetime

from partner_scrape.model import Event, normalize_title
from partner_scrape.normalize.dedup import (
    cross_source_identity,
    dedup_cross_source,
    normalize_venue,
    pick_best,
    score_event,
)
from partner_scrape.normalize.instance import Instance

#: The exact recorded Balboa Park / Fleet strings (sprint 015 ticket
#: 004's live measurement, sprint 016 ticket 003's fixture basis).
BALBOA_PARK_TEC_VENUE = "Fleet Science Center, 1875 El Prado, San Diego, CA"
FLEET_DEFAULT_LOCATION = "1875 El Prado, San Diego, CA 92101"


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


class TestNormalizeVenue:
    def test_balboa_park_and_fleet_strings_normalize_to_the_same_token(self):
        """The recorded sprint 015 ticket 004 mismatch pair -- must now match."""
        assert normalize_venue(BALBOA_PARK_TEC_VENUE) == normalize_venue(FLEET_DEFAULT_LOCATION)
        assert normalize_venue(BALBOA_PARK_TEC_VENUE) == "1875 el prado"

    def test_different_street_numbers_on_the_same_street_do_not_match(self):
        """Two real, different Balboa Park buildings -- must never collapse."""
        assert normalize_venue("1875 El Prado, San Diego, CA") != normalize_venue(
            "1889 El Prado, San Diego, CA"
        )

    def test_comma_less_string_falls_back_to_normalize_title_unchanged(self):
        """A comma-less string is never treated as a single street-address
        segment, even if it starts with a digit -- prevents city/state/ZIP
        text from being swallowed into the venue token."""
        assert normalize_venue("1875 El Prado San Diego CA 92101") == normalize_title(
            "1875 El Prado San Diego CA 92101"
        )

    def test_comma_delimited_but_no_segment_matches_shape_falls_back(self):
        """Two purely name-based venue strings -- no segment starts with a
        street number, so the whole-string fallback applies."""
        assert normalize_venue("Fleet Science Center, Balboa Park") == normalize_title(
            "Fleet Science Center, Balboa Park"
        )

    def test_empty_location_falls_back_to_normalize_title(self):
        assert normalize_venue("") == normalize_title("")


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

    def test_balboa_park_and_fleet_educator_open_house_collapses(self):
        """The recorded sprint 015 ticket 004 mismatch pair, same title+date --
        must now collapse per issue 39 / sprint 016 ticket 003."""
        a = _instance(
            _event(
                source_id="balboa-park",
                title="Educator Open House",
                start=datetime(2026, 9, 24, 17, 0),
                location=BALBOA_PARK_TEC_VENUE,
                confidence=1.0,
            )
        )
        b = _instance(
            _event(
                source_id="fleet-science-center",
                title="Educator Open House",
                start=datetime(2026, 9, 24, 17, 0),
                location=FLEET_DEFAULT_LOCATION,
                confidence=1.0,
            )
        )

        merged = dedup_cross_source([a, b])

        assert len(merged) == 1
        assert merged[0].sources == frozenset({"balboa-park", "fleet-science-center"})

    def test_different_street_numbers_do_not_collapse(self):
        """Two real, different Balboa Park buildings on the same street --
        must never collapse (issue 39's over-collapse guard)."""
        a = _instance(
            _event(
                source_id="tec_source",
                title="Member Preview Night",
                start=datetime(2026, 9, 24, 17, 0),
                location="1875 El Prado, San Diego, CA",
            )
        )
        b = _instance(
            _event(
                source_id="wp_source",
                title="Member Preview Night",
                start=datetime(2026, 9, 24, 17, 0),
                location="1889 El Prado, San Diego, CA",
            )
        )

        merged = dedup_cross_source([a, b])

        assert len(merged) == 2

    def test_no_detectable_street_address_reproduces_todays_fallback_outcome(self):
        """Two purely name-based venue strings with no comma at all --
        proves the fallback path (today's exact normalize_title-only
        behavior), not just the new address-match path."""
        a = _instance(
            _event(
                source_id="tec_source",
                title="Member Preview Night",
                start=datetime(2026, 9, 24, 17, 0),
                location="Fleet Science Center",
            )
        )
        b = _instance(
            _event(
                source_id="wp_source",
                title="Member Preview Night",
                start=datetime(2026, 9, 24, 17, 0),
                location="The Fleet",
            )
        )

        merged = dedup_cross_source([a, b])

        assert len(merged) == 2

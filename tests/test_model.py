"""Tests for partner_scrape.model: Event, provenance, and identity keys."""

from datetime import datetime

import pytest

from partner_scrape.model import Event, Provenance, identity_key, normalize_title, same_record


class TestEventDefaults:
    def test_kind_defaults_to_event(self):
        event = Event()
        assert event.kind == "event"

    def test_content_fields_have_sane_empty_defaults(self):
        event = Event()
        assert event.title == ""
        assert event.description == ""
        assert event.start is None
        assert event.end is None
        assert event.all_day is False
        assert event.location == ""
        assert event.latitude is None
        assert event.longitude is None
        assert event.cost == ""
        assert event.registration_url == ""
        assert event.image_url == ""
        assert event.categories == []
        assert event.tags == []
        assert event.field_provenance == {}

    def test_kind_can_be_program_or_internship(self):
        assert Event(kind="program").kind == "program"
        assert Event(kind="internship").kind == "internship"

    def test_default_list_fields_are_not_shared_between_instances(self):
        a = Event()
        b = Event()
        a.categories.append("stem")
        assert b.categories == []


class TestEventSet:
    def test_set_updates_value_and_provenance(self):
        event = Event()
        event.set("title", "Robotics Night", source="tec_rest", confidence=0.95)

        assert event.title == "Robotics Night"
        assert event.field_provenance["title"] == Provenance(source="tec_rest", confidence=0.95)

    def test_set_multiple_fields_records_provenance_independently(self):
        event = Event()
        event.set("title", "Robotics Night", source="tec_rest", confidence=0.95)
        event.set("cost", "Free", source="tec_rest", confidence=0.6)

        assert set(event.field_provenance.keys()) == {"title", "cost"}
        assert event.field_provenance["cost"].confidence == 0.6

    def test_unset_fields_have_no_provenance_entry(self):
        event = Event()
        event.set("title", "Robotics Night", source="tec_rest", confidence=0.95)

        assert "description" not in event.field_provenance
        assert "cost" not in event.field_provenance

    def test_set_unknown_field_raises(self):
        event = Event()
        with pytest.raises(AttributeError):
            event.set("not_a_real_field", "x", source="tec_rest", confidence=1.0)


class TestEventClassificationFields:
    """The six LLM-enrichment fields added in sprint 002 ticket 003.

    Additive-only: defaults must reproduce sprint 001 behavior (no
    provenance entry, empty/None values) until something calls
    ``Event.set(...)`` for one of them -- see normalize/run.py's
    fallback-to-taxonomy.py conditional, which keys off exactly this
    default/provenance distinction.
    """

    def test_defaults_are_unset(self):
        event = Event()
        assert event.relevant is None
        assert event.relevance_reason == ""
        assert event.areas_of_interest == []
        assert event.age_grade_level == []
        assert event.cost_range == ""
        assert event.time_of_day == []
        assert event.field_provenance == {}

    def test_default_list_fields_are_not_shared_between_instances(self):
        a = Event()
        b = Event()
        a.areas_of_interest.append("Engineering")
        a.age_grade_level.append("Family")
        a.time_of_day.append("Morning")
        assert b.areas_of_interest == []
        assert b.age_grade_level == []
        assert b.time_of_day == []

    def test_relevant_and_relevance_reason_round_trip_through_set(self):
        event = Event()
        event.set("relevant", True, source="llm_enrichment", confidence=0.9)
        event.set(
            "relevance_reason",
            "STEM robotics camp for youth",
            source="llm_enrichment",
            confidence=0.9,
        )

        assert event.relevant is True
        assert event.relevance_reason == "STEM robotics camp for youth"
        assert event.field_provenance["relevant"] == Provenance(
            source="llm_enrichment", confidence=0.9
        )
        assert event.field_provenance["relevance_reason"] == Provenance(
            source="llm_enrichment", confidence=0.9
        )

    def test_relevant_can_be_set_false(self):
        event = Event()
        event.set("relevant", False, source="llm_enrichment", confidence=0.9)
        assert event.relevant is False

    def test_areas_of_interest_round_trips_through_set(self):
        event = Event()
        event.set(
            "areas_of_interest", ["Engineering", "Physics"], source="llm_enrichment", confidence=0.85
        )
        assert event.areas_of_interest == ["Engineering", "Physics"]
        assert event.field_provenance["areas_of_interest"] == Provenance(
            source="llm_enrichment", confidence=0.85
        )

    def test_age_grade_level_round_trips_through_set(self):
        event = Event()
        event.set("age_grade_level", ["Grades 6-8"], source="llm_enrichment", confidence=0.85)
        assert event.age_grade_level == ["Grades 6-8"]
        assert event.field_provenance["age_grade_level"] == Provenance(
            source="llm_enrichment", confidence=0.85
        )

    def test_cost_range_round_trips_through_set(self):
        event = Event()
        event.set("cost_range", "Free", source="llm_enrichment", confidence=0.85)
        assert event.cost_range == "Free"
        assert event.field_provenance["cost_range"] == Provenance(
            source="llm_enrichment", confidence=0.85
        )

    def test_time_of_day_round_trips_through_set(self):
        event = Event()
        event.set("time_of_day", ["Evening"], source="llm_enrichment", confidence=0.85)
        assert event.time_of_day == ["Evening"]
        assert event.field_provenance["time_of_day"] == Provenance(
            source="llm_enrichment", confidence=0.85
        )

    def test_each_classification_field_provenance_recorded_independently(self):
        event = Event()
        event.set("cost_range", "Free", source="llm_enrichment", confidence=0.85)

        assert set(event.field_provenance.keys()) == {"cost_range"}
        assert "areas_of_interest" not in event.field_provenance
        assert "age_grade_level" not in event.field_provenance
        assert "time_of_day" not in event.field_provenance
        assert "relevant" not in event.field_provenance


class TestNormalizeTitle:
    def test_lowercases_and_strips_punctuation(self):
        assert normalize_title("Robotics Night!!") == "robotics night"

    def test_collapses_whitespace(self):
        assert normalize_title("  Robotics   Night  ") == "robotics night"

    def test_handles_mixed_punctuation_and_case(self):
        assert normalize_title("STEM Fair: Grades 6-8 (Free!)") == "stem fair grades 68 free"


class TestIdentityKey:
    def test_uses_source_and_external_id_when_present(self):
        event = Event(source_id="tlc", external_id="evt-123", title="Whatever")
        assert identity_key(event) == ("tlc", "evt-123")

    def test_falls_back_to_normalized_title_and_start_date_without_external_id(self):
        event = Event(
            source_id="tlc",
            external_id="",
            title="Beach Cleanup!",
            start=datetime(2026, 8, 1, 9, 0),
        )
        assert identity_key(event) == ("tlc", "beach cleanup", datetime(2026, 8, 1).date())

    def test_fallback_with_no_start_uses_none_for_date(self):
        event = Event(source_id="tlc", external_id="", title="Beach Cleanup!")
        assert identity_key(event) == ("tlc", "beach cleanup", None)

    def test_event_identity_key_method_matches_module_function(self):
        event = Event(source_id="tlc", external_id="evt-123")
        assert event.identity_key() == identity_key(event)


class TestSameRecord:
    def test_same_identity_key_is_same_record(self):
        a = Event(source_id="tlc", external_id="evt-123", title="A")
        b = Event(source_id="tlc", external_id="evt-123", title="A (updated)")
        assert same_record(a, b) is True

    def test_different_identity_key_is_not_same_record(self):
        a = Event(source_id="tlc", external_id="evt-123")
        b = Event(source_id="tlc", external_id="evt-456")
        assert same_record(a, b) is False

    def test_fallback_identity_matches_on_title_and_date(self):
        a = Event(
            source_id="tlc",
            title="Beach Cleanup",
            start=datetime(2026, 8, 1, 9, 0),
        )
        b = Event(
            source_id="tlc",
            title="beach cleanup!!",
            start=datetime(2026, 8, 1, 15, 0),
        )
        assert same_record(a, b) is True

    def test_fallback_identity_differs_on_different_dates(self):
        a = Event(source_id="tlc", title="Beach Cleanup", start=datetime(2026, 8, 1))
        b = Event(source_id="tlc", title="Beach Cleanup", start=datetime(2026, 8, 2))
        assert same_record(a, b) is False

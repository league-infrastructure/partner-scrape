"""Tests for partner_scrape.normalize.run: the normalize.run() entry point.

Exercises the full collapse -> dedup -> map pipeline together, covering
the ticket's acceptance criteria that only make sense at the entry-point
level (full Opportunity field presence, end-to-end partner join,
end-to-end cross-source/recurring collapse). Per-stage behavior is
covered in test_normalize_{taxonomy,collapse,dedup,partners}.py -- this
file is deliberately thin on stage-internal edge cases.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from partner_scrape.model import Event
from partner_scrape.normalize.run import Opportunity, run

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PARTNERS_PATH = FIXTURES_DIR / "partners.json"


def _event(
    source_id: str = "coastalrootsfarm",
    title: str = "Farm Tour",
    start: datetime | None = None,
    end: datetime | None = None,
    location: str = "",
    confidence: float = 1.0,
    description: str = "",
    cost: str = "",
) -> Event:
    event = Event(source_id=source_id)
    event.set("title", title, source="fixture", confidence=confidence)
    if start is not None:
        event.set("start", start, source="fixture", confidence=confidence)
    if end is not None:
        event.set("end", end, source="fixture", confidence=confidence)
    if location:
        event.set("location", location, source="fixture", confidence=confidence)
    if description:
        event.set("description", description, source="fixture", confidence=confidence)
    if cost:
        event.set("cost", cost, source="fixture", confidence=confidence)
    return event


class TestFieldMapping:
    def test_every_site_schema_field_is_present_never_missing(self):
        event = _event(start=datetime(2026, 8, 1, 9, 0))

        [opportunity] = run([event], PARTNERS_PATH)

        for f in (
            "slug", "title", "partner_name", "partner_id", "description", "link",
            "availability", "date_start", "date_end", "age_grade_level", "cost_range",
            "time_of_day", "opportunity_type", "areas_of_interest", "specific_attention",
            "financial_support", "ngss_aligned", "location", "latitude", "longitude",
            "contact_name", "contact_email", "contact_phone", "logo_src",
        ):
            assert hasattr(opportunity, f), f"missing field {f!r}"

    def test_unknown_values_are_empty_string_or_list_never_none(self):
        event = _event(start=datetime(2026, 8, 1, 9, 0))

        [opportunity] = run([event], PARTNERS_PATH)

        assert opportunity.description == ""
        assert opportunity.contact_name == ""
        assert opportunity.contact_email == ""
        assert opportunity.contact_phone == ""
        assert opportunity.specific_attention == []
        assert opportunity.date_end == ""

    def test_maps_title_and_date_start(self):
        event = _event(title="Farm Tour", start=datetime(2026, 8, 1, 9, 0))

        [opportunity] = run([event], PARTNERS_PATH)

        assert opportunity.title == "Farm Tour"
        assert opportunity.date_start.startswith("2026-08-01T09:00:00")


class TestTaxonomyDerivation:
    def test_areas_age_time_of_day_and_cost_are_derived(self):
        event = _event(
            title="Family Tide Pool Walk",
            start=datetime(2026, 8, 1, 9, 0),
            description="A morning tide pool exploration for the whole family",
            cost="Free",
        )

        [opportunity] = run([event], PARTNERS_PATH)

        assert "Biology / LifeSciences" in opportunity.areas_of_interest
        assert opportunity.age_grade_level == ["Family"]
        assert opportunity.time_of_day == ["Morning"]
        assert opportunity.cost_range == "Free"


class TestLLMClassificationOverride:
    """`_to_opportunity` prefers an Event's own LLM-set classification
    fields over taxonomy.py's keyword derivation, checked independently
    per field via `field_provenance` (sprint 002 ticket 003)."""

    def _event_with_taxonomy_fields(self, **llm_overrides) -> Event:
        """A base Event whose text/cost/start would keyword-derive to
        areas_of_interest=["Biology / LifeSciences"], age_grade_level=["Family"],
        cost_range="Free", time_of_day=["Morning"] -- matching
        TestTaxonomyDerivation's fixture above -- with any of
        ``llm_overrides`` applied via `Event.set(...)` as if an
        LLMEnricher had run.
        """
        event = _event(
            source_id="crf",
            title="Family Tide Pool Walk",
            start=datetime(2026, 8, 1, 9, 0),
            description="A morning tide pool exploration for the whole family",
            cost="Free",
        )
        for field_name, value in llm_overrides.items():
            event.set(field_name, value, source="llm_enrichment", confidence=0.9)
        return event

    def test_no_llm_fields_set_behaves_like_sprint_001_for_all_four_fields(self):
        event = self._event_with_taxonomy_fields()
        assert event.field_provenance.keys() & {
            "areas_of_interest",
            "age_grade_level",
            "cost_range",
            "time_of_day",
        } == set()

        [opportunity] = run([event], PARTNERS_PATH)

        assert opportunity.areas_of_interest == ["Biology / LifeSciences"]
        assert opportunity.age_grade_level == ["Family"]
        assert opportunity.cost_range == "Free"
        assert opportunity.time_of_day == ["Morning"]

    def test_llm_set_areas_of_interest_overrides_keyword_derivation(self):
        event = self._event_with_taxonomy_fields(areas_of_interest=["Engineering"])

        [opportunity] = run([event], PARTNERS_PATH)

        assert opportunity.areas_of_interest == ["Engineering"]
        # The other three fields were not LLM-set on this Event, so they
        # still fall back to keyword derivation independently.
        assert opportunity.age_grade_level == ["Family"]
        assert opportunity.cost_range == "Free"
        assert opportunity.time_of_day == ["Morning"]

    def test_llm_set_age_grade_level_overrides_keyword_derivation(self):
        event = self._event_with_taxonomy_fields(age_grade_level=["Grades 9-12"])

        [opportunity] = run([event], PARTNERS_PATH)

        assert opportunity.age_grade_level == ["Grades 9-12"]
        assert opportunity.areas_of_interest == ["Biology / LifeSciences"]

    def test_llm_set_cost_range_overrides_keyword_derivation(self):
        event = self._event_with_taxonomy_fields(cost_range="Less than $25")

        [opportunity] = run([event], PARTNERS_PATH)

        assert opportunity.cost_range == "Less than $25"
        assert opportunity.areas_of_interest == ["Biology / LifeSciences"]

    def test_llm_set_time_of_day_overrides_keyword_derivation(self):
        event = self._event_with_taxonomy_fields(time_of_day=["Evening"])

        [opportunity] = run([event], PARTNERS_PATH)

        assert opportunity.time_of_day == ["Evening"]
        assert opportunity.areas_of_interest == ["Biology / LifeSciences"]

    def test_mixed_some_llm_set_some_unset_on_the_same_event(self):
        event = self._event_with_taxonomy_fields(
            cost_range="Less than $100", time_of_day=["Evening"]
        )

        [opportunity] = run([event], PARTNERS_PATH)

        assert opportunity.cost_range == "Less than $100"
        assert opportunity.time_of_day == ["Evening"]
        # areas_of_interest and age_grade_level were left unset on this
        # Event, so each independently falls back to its keyword value.
        assert opportunity.areas_of_interest == ["Biology / LifeSciences"]
        assert opportunity.age_grade_level == ["Family"]


class TestPartnerJoin:
    def test_matching_org_gets_partner_id_logo_and_geo_populated(self):
        event = _event(source_id="crf", start=datetime(2026, 8, 1, 9, 0))

        [opportunity] = run(
            [event], PARTNERS_PATH, source_org_names={"crf": "Coastal Roots Farm"}
        )

        assert opportunity.partner_id == 101
        assert opportunity.partner_name == "Coastal Roots Farm"
        assert opportunity.logo_src == "coastal_roots_farm.jpg"
        assert opportunity.latitude == "33.05"
        assert opportunity.longitude == "-117.26"

    def test_unmatched_org_still_produces_a_valid_opportunity_with_partner_id_unset(self):
        event = _event(source_id="unknown_org", start=datetime(2026, 8, 1, 9, 0))

        [opportunity] = run(
            [event], PARTNERS_PATH, source_org_names={"unknown_org": "Some Org Not Listed"}
        )

        assert isinstance(opportunity, Opportunity)
        assert opportunity.partner_id is None
        assert opportunity.partner_name == "Some Org Not Listed"

    def test_missing_source_org_names_entry_falls_back_to_source_id(self):
        event = _event(source_id="no_mapping_provided", start=datetime(2026, 8, 1, 9, 0))

        [opportunity] = run([event], PARTNERS_PATH)

        assert opportunity.partner_id is None
        assert opportunity.partner_name == "no_mapping_provided"


class TestCrossSourceDedup:
    def test_two_sources_with_matching_title_date_venue_collapse_to_one_opportunity(self):
        a = _event(
            source_id="tec_source",
            title="Tide Pool Exploration",
            start=datetime(2026, 8, 15, 9, 0),
            location="Cabrillo Tide Pools",
            confidence=1.0,
            description="Full accurate TEC description",
        )
        b = _event(
            source_id="wp_source",
            title="Tide Pool Exploration",
            start=datetime(2026, 8, 15, 9, 0),
            location="Cabrillo Tide Pools",
            confidence=0.5,
            description="Vague WP blurb",
        )

        opportunities = run([a, b], PARTNERS_PATH)

        assert len(opportunities) == 1
        assert opportunities[0].description == "Full accurate TEC description"
        assert opportunities[0].sources == frozenset({"tec_source", "wp_source"})

    def test_differing_date_or_venue_is_not_collapsed(self):
        a = _event(
            source_id="tec_source",
            title="Tide Pool Exploration",
            start=datetime(2026, 8, 15, 9, 0),
            location="Cabrillo Tide Pools",
        )
        b = _event(
            source_id="wp_source",
            title="Tide Pool Exploration",
            start=datetime(2026, 8, 16, 9, 0),
            location="Cabrillo Tide Pools",
        )

        opportunities = run([a, b], PARTNERS_PATH)

        assert len(opportunities) == 2


class TestRecurringCollapse:
    def test_n_recurring_instances_collapse_with_repeats_text(self):
        events = [
            _event(source_id="crf", title="Farm Camp", start=datetime(2026, 8, 1, 9, 0)),
            _event(source_id="crf", title="Farm Camp", start=datetime(2026, 8, 8, 9, 0)),
            _event(source_id="crf", title="Farm Camp", start=datetime(2026, 8, 15, 9, 0)),
        ]

        opportunities = run(events, PARTNERS_PATH)

        assert len(opportunities) == 1
        assert "Repeats 3 times through 2026-08-15" in opportunities[0].availability

    def test_a_single_non_recurring_event_has_no_repeats_text(self):
        event = _event(start=datetime(2026, 8, 1, 9, 0))

        [opportunity] = run([event], PARTNERS_PATH)

        assert opportunity.availability == ""

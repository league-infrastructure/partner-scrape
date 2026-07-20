"""Tests for partner_scrape.normalize.taxonomy: keyword-rule derivation.

Every case is spot-checked against dev/export_site.py's rule set
(ticket 006's acceptance criteria: "behavior matches dev/export_site.py's
rules on the same inputs, spot-checked, not required to be
byte-identical") -- no network, no adapter/Event fixtures needed, since
these are pure text/value -> tags functions.
"""

from __future__ import annotations

from datetime import datetime

from partner_scrape.normalize.taxonomy import (
    classify_opportunity_type,
    AGE_KEYWORDS,
    AREA_KEYWORDS,
    build_taxonomy_text,
    derive_age_grade_level,
    derive_areas_of_interest,
    derive_time_of_day,
    map_cost,
    tag_by_keywords,
)


class TestTagByKeywords:
    def test_matches_are_returned_in_rule_order(self):
        text = "Learn chemistry and then some physics"
        assert tag_by_keywords(text, AREA_KEYWORDS) == ["Chemistry", "Physics"]

    def test_case_insensitive(self):
        assert tag_by_keywords("ROBOT CLUB", AREA_KEYWORDS) == [
            "Coding/Computer Science/Cyber Security"
        ]

    def test_no_match_returns_empty_list(self):
        assert tag_by_keywords("A picnic in the park", AREA_KEYWORDS) == []

    def test_a_label_is_never_repeated(self):
        text = "code code coding programming"
        assert tag_by_keywords(text, AREA_KEYWORDS) == ["Coding/Computer Science/Cyber Security"]


class TestDeriveAreasOfInterest:
    def test_matching_text_returns_matched_labels(self):
        assert derive_areas_of_interest("Tide pool exploration at the aquarium") == [
            "Biology / LifeSciences"
        ]

    def test_multiple_matching_areas_all_returned(self):
        result = derive_areas_of_interest("Robot building and marine biology camp")
        assert result == ["Biology / LifeSciences", "Coding/Computer Science/Cyber Security"]

    def test_unmatched_text_defaults_to_general_science(self):
        assert derive_areas_of_interest("A picnic in the park") == ["General Science"]


class TestDeriveAgeGradeLevel:
    def test_family_keyword_matches(self):
        assert derive_age_grade_level("A fun event for the whole family") == ["Family"]

    def test_unmatched_text_returns_empty_list_no_default(self):
        assert derive_age_grade_level("Tide pool exploration") == []

    def test_grades_6_8_keyword_matches(self):
        assert derive_age_grade_level("For middle school students") == ["Grades 6-8"]


class TestMapCost:
    def test_empty_string_is_unknown(self):
        assert map_cost("") == ""

    def test_free_keyword(self):
        assert map_cost("Free admission") == "Free"

    def test_zero_dollar_variants_are_free(self):
        assert map_cost("$0") == "Free"
        assert map_cost("$0.00") == "Free"

    def test_dollar_amount_under_25(self):
        assert map_cost("$5") == "Less than $25"

    def test_dollar_amount_between_25_and_50(self):
        assert map_cost("$30") == "Less than $50"

    def test_dollar_amount_between_100_and_200(self):
        assert map_cost("$150") == "Less than $200"

    def test_dollar_amount_200_or_over(self):
        assert map_cost("$250") == "Greater than $200"

    def test_multiple_amounts_uses_the_lowest(self):
        assert map_cost("$10-$60") == "Less than $25"

    def test_unparseable_short_text_is_passed_through(self):
        assert map_cost("Included with admission") == "Included with admission"

    def test_unparseable_long_text_becomes_empty(self):
        long_text = "x" * 41
        assert map_cost(long_text) == ""


class TestDeriveTimeOfDay:
    def test_all_day_overrides_start_time(self):
        assert derive_time_of_day(datetime(2026, 8, 1, 9, 0), all_day=True) == ["All Day"]

    def test_none_start_and_not_all_day_is_unknown(self):
        assert derive_time_of_day(None, all_day=False) == []

    def test_morning_before_noon(self):
        assert derive_time_of_day(datetime(2026, 8, 1, 9, 0), all_day=False) == ["Morning"]

    def test_afternoon_between_noon_and_five(self):
        assert derive_time_of_day(datetime(2026, 8, 1, 14, 30), all_day=False) == ["Afternoon"]

    def test_evening_at_or_after_five(self):
        assert derive_time_of_day(datetime(2026, 8, 1, 18, 0), all_day=False) == ["Evening"]

    def test_boundary_noon_is_afternoon(self):
        assert derive_time_of_day(datetime(2026, 8, 1, 12, 0), all_day=False) == ["Afternoon"]

    def test_boundary_five_pm_is_evening(self):
        assert derive_time_of_day(datetime(2026, 8, 1, 17, 0), all_day=False) == ["Evening"]


class TestBuildTaxonomyText:
    def test_joins_title_description_categories_and_tags(self):
        text = build_taxonomy_text(
            "Tide Pool Walk", "Explore the shore", ["Marine Science"], ["tide pools", "outdoor"]
        )
        assert text == "Tide Pool Walk Explore the shore Marine Science tide pools outdoor"

    def test_empty_categories_and_tags_still_joins_cleanly(self):
        text = build_taxonomy_text("Title", "Description", [], [])
        assert text == "Title Description  "


class TestClassifyOpportunityType:
    """opportunity_type must be classified from text, not blindly defaulted."""

    def test_volunteering_signals(self):
        for text in ["Beach Cleanup at Mission Bay", "Habitat Restoration volunteer day",
                     "Creek to Bay Clean-up", "Trail work and stewardship"]:
            assert classify_opportunity_type(text) == "Volunteering", text

    def test_online_signals(self):
        assert classify_opportunity_type("Virtual webinar on native bees") == "Online"

    def test_school_program_signals(self):
        assert classify_opportunity_type("Field trip for schools") == "School Programs"
        assert classify_opportunity_type("Classroom curriculum workshop") == "School Programs"

    def test_bare_school_words_do_not_false_positive(self):
        # "preschool"/"school-age" are AUDIENCE terms, not School Programs
        assert classify_opportunity_type("Preschool story time") == "Out-of-school Programs"
        assert classify_opportunity_type("School-age science club") == "Out-of-school Programs"

    def test_unmatched_text_falls_back_to_default(self):
        assert classify_opportunity_type("Tide Pool Exploration") == "Out-of-school Programs"

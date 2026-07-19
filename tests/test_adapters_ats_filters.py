"""Tests for partner_scrape.adapters.ats_filters: the shared ATS classifier.

Every function under test is a pure function over plain strings -- no
Fetcher, no Event, no network -- per ticket 002's acceptance criteria
("independently unit-testable without either adapter"). Table-driven
per predicate, plus the combined ``classify_posting`` gate.
"""

from __future__ import annotations

import pytest

from partner_scrape.adapters.ats_filters import (
    DEFAULT_AGE_GRADE_LEVEL,
    DEFAULT_LOCATION_KEYWORDS,
    DEFAULT_TIME_OF_DAY,
    PostingVerdict,
    classify_posting,
    is_internship_posting,
    is_local_posting,
    is_stem_posting,
)


class TestIsInternshipPosting:
    @pytest.mark.parametrize(
        "title",
        [
            "Software Engineering Intern",
            "Biology Research Intern",
            "Data Science Co-op",
            "Data Science Coop",
            "Data Science Co op",
            "Marketing Apprenticeship",
            "Summer Intern",
            "Interns Wanted",
            "Early-Career Software Engineer",
            "Early career Software Engineer",
        ],
    )
    def test_positive_titles_match(self, title):
        assert is_internship_posting(title) is True

    @pytest.mark.parametrize(
        "title",
        [
            "Senior Software Engineer",
            "VP of Sales",
            "International Sales Manager",
            "Internal Audit Manager",
            "Internationalization Engineer",
        ],
    )
    def test_negative_titles_do_not_match(self, title):
        assert is_internship_posting(title) is False

    def test_word_boundary_safe_international_does_not_false_positive(self):
        # The specific regression case called out in the ticket's
        # acceptance criteria: "international"/"internal" must not
        # match on the "intern" substring.
        assert is_internship_posting("International Sales Manager") is False
        assert is_internship_posting("Internal Audit Manager") is False

    def test_commitment_field_alone_can_signal_internship(self):
        # Lever's categories.commitment often says "Intern"/"Internship"
        # directly even when the title doesn't (sprint.md SUC-002).
        assert is_internship_posting("Software Engineer", commitment="Internship") is True

    def test_commitment_field_does_not_mask_a_negative_title(self):
        assert is_internship_posting("Senior Software Engineer", commitment="Full-time") is False

    def test_empty_commitment_default_does_not_error(self):
        assert is_internship_posting("Senior Software Engineer") is False


class TestIsStemPosting:
    @pytest.mark.parametrize(
        "title",
        [
            "Bioinformatics Intern",
            "Data Science Intern",
            "Hardware Engineering Intern",
            "Software Engineering Intern",
            "Biology Research Intern",
            "Firmware Engineer Intern",
            "Robotics Intern",
            "Machine Learning Intern",
            "Chemistry Lab Intern",
            "Physics Research Intern",
            "Mechanical Engineering Intern",
            "Electrical Engineering Co-op",
            "Aerospace Engineering Intern",
            "Semiconductor Test Engineer Intern",
            "Wireless Systems Intern",
            "Manufacturing Engineer Intern",
            "R&D Intern",
            "Genomics Research Intern",
            "Data Scientist",
        ],
    )
    def test_positive_titles_match(self, title):
        assert is_stem_posting(title) is True

    @pytest.mark.parametrize(
        "title",
        [
            "Marketing Intern",
            "HR Coordinator Intern",
            "VP of Sales",
            "Executive Assistant Intern",
            "Sales Development Representative",
        ],
    )
    def test_negative_titles_do_not_match(self, title):
        assert is_stem_posting(title) is False

    def test_department_field_alone_can_signal_stem(self):
        assert is_stem_posting("Summer Intern", department="Engineering") is True

    def test_department_field_does_not_mask_a_negative_title(self):
        # Title carries no STEM signal and neither does department.
        assert is_stem_posting("Marketing Intern", department="Marketing") is False

    def test_empty_department_default_does_not_error(self):
        assert is_stem_posting("Marketing Intern") is False


class TestIsLocalPosting:
    @pytest.mark.parametrize(
        "location",
        [
            "San Diego, CA",
            "San Diego, California",
            "san diego, ca",
            "Downtown San Diego",
        ],
    )
    def test_positive_locations_match_under_default_keywords(self, location):
        assert is_local_posting(location) is True

    @pytest.mark.parametrize(
        "location",
        [
            "Remote",
            "Austin, TX",
            "New York, NY",
            "",
        ],
    )
    def test_negative_locations_do_not_match_under_default_keywords(self, location):
        assert is_local_posting(location) is False

    def test_remote_combined_with_san_diego_still_matches(self):
        # Documented Remote-handling: a bare "Remote" carries no
        # geographic signal and does not match, but "Remote" combined
        # with an explicit San Diego mention does, since the substring
        # is still present.
        assert is_local_posting("Remote - San Diego, CA") is True
        assert is_local_posting("Remote (San Diego)") is True

    def test_location_keywords_override_changes_match_set(self):
        assert is_local_posting("La Jolla, CA", keywords=["La Jolla", "San Diego"]) is True
        assert is_local_posting("San Diego, CA", keywords=["La Jolla", "San Diego"]) is True
        assert is_local_posting("Austin, TX", keywords=["La Jolla", "San Diego"]) is False

    def test_location_keywords_override_can_narrow_default_match(self):
        # "San Diego, CA" matches the default keyword set but not a
        # narrower override that excludes it.
        assert is_local_posting("San Diego, CA", keywords=["La Jolla"]) is False

    def test_default_keywords_constant_is_san_diego(self):
        assert DEFAULT_LOCATION_KEYWORDS == ["San Diego"]


class TestClassifyPosting:
    def test_matching_posting_returns_verdict_with_defaults(self):
        verdict = classify_posting(
            title="Software Engineering Intern",
            location="San Diego, CA",
        )
        assert verdict == PostingVerdict(
            age_grade_level=list(DEFAULT_AGE_GRADE_LEVEL),
            time_of_day=list(DEFAULT_TIME_OF_DAY),
        )

    def test_graduate_keyword_in_title_adds_graduate_level(self):
        verdict = classify_posting(
            title="PhD Research Intern",
            location="San Diego, CA",
        )
        assert verdict is not None
        assert verdict.age_grade_level == ["Grades 9-12", "Undergraduate", "Graduate"]

    def test_undergraduate_in_title_does_not_false_positive_graduate(self):
        # "Undergraduate" contains "graduate" as a substring but not as
        # a whole word -- must not spuriously add "Graduate" twice or
        # trigger the PhD/graduate-level branch.
        verdict = classify_posting(
            title="Undergraduate Research Intern",
            location="San Diego, CA",
        )
        assert verdict is not None
        assert verdict.age_grade_level == ["Grades 9-12", "Undergraduate"]

    def test_fails_when_not_an_internship(self):
        assert (
            classify_posting(
                title="Senior Software Engineer",
                location="San Diego, CA",
            )
            is None
        )

    def test_fails_when_not_stem(self):
        assert (
            classify_posting(
                title="Marketing Intern",
                location="San Diego, CA",
            )
            is None
        )

    def test_fails_when_not_local(self):
        assert (
            classify_posting(
                title="Software Engineering Intern",
                location="Remote",
            )
            is None
        )

    def test_fails_when_all_three_checks_fail(self):
        assert (
            classify_posting(
                title="VP of Sales",
                location="Austin, TX",
            )
            is None
        )

    def test_location_keywords_override_propagates_through_classify(self):
        assert (
            classify_posting(
                title="Software Engineering Intern",
                location="La Jolla, CA",
            )
            is None
        )
        verdict = classify_posting(
            title="Software Engineering Intern",
            location="La Jolla, CA",
            location_keywords=["La Jolla", "San Diego"],
        )
        assert verdict is not None

    def test_commitment_and_department_fields_are_honored(self):
        verdict = classify_posting(
            title="Summer Program",
            commitment="Internship",
            department="Engineering",
            location="San Diego, CA",
        )
        assert verdict is not None

    def test_verdict_never_carries_cost_range(self):
        verdict = classify_posting(
            title="Software Engineering Intern",
            location="San Diego, CA",
        )
        assert verdict is not None
        assert not hasattr(verdict, "cost_range")
        assert not hasattr(verdict, "cost")
